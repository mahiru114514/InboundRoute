"""坐标系统一（C-铁律-3）。

内部主数据基准为 WGS84；高德/腾讯返回 GCJ-02，百度返回 BD-09。
转换只允许发生在 route_adapter 内部，单向（provider -> WGS84），不得暴露给其他模块。
"""
from __future__ import annotations

import math

# 中国境内坐标体系转换常量（GCJ-02 非线性偏移）
_A = 6378245.0
_EE = 0.00669342162296594323
_X_PI = math.pi * 3000.0 / 180.0


def _out_of_china(lat: float, lng: float) -> bool:
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lat: float, lng: float):
    if _out_of_china(lat, lng):
        return lat, lng
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - _EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (_A / sqrtmagic * math.cos(radlat) * math.pi)
    return lat + dlat, lng + dlng


def gcj02_to_wgs84(lat: float, lng: float):
    if _out_of_china(lat, lng):
        return lat, lng
    glat, glng = wgs84_to_gcj02(lat, lng)
    return lat * 2.0 - glat, lng * 2.0 - glng


def bd09_to_gcj02(lat: float, lng: float):
    x = lng - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * _X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * _X_PI)
    return z * math.sin(theta), z * math.cos(theta)


def gcj02_to_bd09(lat: float, lng: float):
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * _X_PI)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * _X_PI)
    return z * math.sin(theta) + 0.006, z * math.cos(theta) + 0.0065


def to_wgs84(lat: float, lng: float, crs: str):
    """单向转换：三方坐标 -> WGS84。内部基准只允许 WGS84。"""
    crs = (crs or "WGS84").upper()
    if crs == "WGS84":
        return lat, lng
    if crs in ("GCJ-02", "GCJ02", "AMAP", "TENCENT"):
        return gcj02_to_wgs84(lat, lng)
    if crs in ("BD-09", "BD09", "BAIDU"):
        glat, glng = bd09_to_gcj02(lat, lng)
        return gcj02_to_wgs84(glat, glng)
    raise ValueError("不支持的坐标系：" + str(crs))


def from_wgs84(lat: float, lng: float, crs: str):
    """仅供往返测试使用；生产路径只做 provider -> WGS84 单向转换。"""
    crs = (crs or "WGS84").upper()
    if crs == "WGS84":
        return lat, lng
    if crs in ("GCJ-02", "GCJ02", "AMAP", "TENCENT"):
        return wgs84_to_gcj02(lat, lng)
    if crs in ("BD-09", "BD09", "BAIDU"):
        glat, glng = wgs84_to_gcj02(lat, lng)
        return gcj02_to_bd09(glat, glng)
    raise ValueError("不支持的坐标系：" + str(crs))