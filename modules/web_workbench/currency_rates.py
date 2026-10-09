"""固定来源的参考汇率查询；界面及业务金额继续以人民币保存。"""
from __future__ import annotations

from datetime import date
import json
import math
import threading
import time
from urllib.request import Request, urlopen


CURRENCIES = frozenset({'CNY', 'USD', 'EUR', 'GBP', 'JPY', 'HKD', 'AUD', 'CAD', 'SGD'})
MAX_RESPONSE = 65536
CACHE_SECONDS = 6 * 3600


class CurrencyRateError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status
        self.code = 'BAD_REQUEST' if status == 400 else 'CURRENCY_RATE_UNAVAILABLE'


class CurrencyRates:
    def __init__(self, opener=None, clock=None):
        self._open = opener or urlopen
        self._clock = clock or time.monotonic
        self._cache = {}
        self._lock = threading.Lock()

    def get(self, currency, refresh=False):
        if not isinstance(currency, str) or currency not in CURRENCIES:
            raise CurrencyRateError('不支持的换算币种', 400)
        if currency == 'CNY':
            return {'currency':'CNY', 'cny_per_unit':1, 'date':date.today().isoformat(),
                    'source':'CNY', 'source_url':'https://frankfurter.dev/', 'cached':False, 'stale':False}
        with self._lock:
            saved = self._cache.get(currency)
        if not refresh and saved and self._clock() - saved[0] < CACHE_SECONDS:
            return {**saved[1], 'cached':True, 'stale':False}
        try:
            result = self._fetch(currency)
        except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
            if saved:
                return {**saved[1], 'cached':True, 'stale':True,
                        'warning':'参考汇率刷新失败，沿用下述日期的已有参考值；可手动修改。'}
            raise CurrencyRateError('暂时无法取得参考汇率，请稍后重试或手动填写。') from error
        with self._lock:
            self._cache[currency] = (self._clock(), result)
        return dict(result)

    def _fetch(self, currency):
        url = f'https://api.frankfurter.dev/v2/rate/{currency.lower()}/cny'
        request = Request(url, headers={'User-Agent':'InboundRoute/1.0', 'Accept':'application/json'})
        with self._open(request, timeout=8) as response:
            body = response.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE:
            raise ValueError('汇率响应过大')
        value = json.loads(body)
        if not isinstance(value, dict) or value.get('base') != currency or value.get('quote') != 'CNY':
            raise ValueError('汇率方向不匹配')
        rate = value['rate']
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or not 0 < rate <= 1000000:
            raise ValueError('无效的参考汇率')
        stamp = value['date']
        if not isinstance(stamp, str) or date.fromisoformat(stamp).isoformat() != stamp:
            raise ValueError('无效的汇率日期')
        return {'currency':currency, 'cny_per_unit':rate, 'date':stamp, 'source':'Frankfurter',
                'source_url':'https://frankfurter.dev/', 'cached':False, 'stale':False}
