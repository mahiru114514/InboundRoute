"""geohash 编码（缓存键用 geohash7，约 153m 见方）。纯标准库，无第三方依赖。"""
from __future__ import annotations

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def encode(lat: float, lng: float, precision: int = 7) -> str:
    if precision <= 0:
        return ""
    lat_lo, lat_hi = -90.0, 90.0
    lng_lo, lng_hi = -180.0, 180.0
    bits = 0
    bit_count = 0
    even = True
    out = []
    while len(out) < precision:
        if even:
            mid = (lng_lo + lng_hi) / 2.0
            if lng >= mid:
                bits = (bits << 1) | 1
                lng_lo = mid
            else:
                bits = bits << 1
                lng_hi = mid
        else:
            mid = (lat_lo + lat_hi) / 2.0
            if lat >= mid:
                bits = (bits << 1) | 1
                lat_lo = mid
            else:
                bits = bits << 1
                lat_hi = mid
        even = not even
        bit_count += 1
        if bit_count == 5:
            out.append(_BASE32[bits])
            bits = 0
            bit_count = 0
    return "".join(out)