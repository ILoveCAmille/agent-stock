#!/usr/bin/env python3
import os
print("HTTP_PROXY:", os.environ.get('HTTP_PROXY', 'not set'))
print("HTTPS_PROXY:", os.environ.get('HTTPS_PROXY', 'not set'))
print("http_proxy:", os.environ.get('http_proxy', 'not set'))
print("https_proxy:", os.environ.get('https_proxy', 'not set'))

# 尝试清除代理并直连
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(key, None)

print("\n清除代理后测试直连...")

# 测试1: requests直接请求东方财富
import requests
try:
    r = requests.get("https://push2his.eastmoney.com/api/qt/stock/kline/get",
                      params={"fields1":"f1,f2,f3,f4,f5,f6","fields2":"f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
                              "ut":"7eea3edcaed734bea9cbfc24409ed989","klt":"101","fqt":"1",
                              "secid":"1.600519","beg":"20260101","end":"20260530"},
                      timeout=10)
    print(f"直连东方财富: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        klines = data.get('data', {}).get('klines', [])
        print(f"  获取 {len(klines)} 条K线数据")
except Exception as e:
    print(f"直连失败: {e}")

# 测试2: 用session关闭代理
try:
    s = requests.Session()
    s.trust_env = False
    r = s.get("https://push2his.eastmoney.com/api/qt/stock/kline/get",
               params={"fields1":"f1,f2,f3,f4,f5,f6","fields2":"f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
                       "ut":"7eea3edcaed734bea9cbfc24409ed989","klt":"101","fqt":"1",
                       "secid":"1.600519","beg":"20260101","end":"20260530"},
               timeout=10)
    print(f"Session直连: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        klines = data.get('data', {}).get('klines', [])
        print(f"  获取 {len(klines)} 条K线数据")
except Exception as e:
    print(f"Session直连失败: {e}")

# 测试3: tushare
try:
    import tushare as ts
    token = os.environ.get('TUSHARE_TOKEN', '')
    if token:
        pro = ts.pro_api(token)
        df = pro.daily(ts_code='600519.SH', start_date='20260101', end_date='20260530')
        print(f"tushare: {len(df)} 条数据")
    else:
        print("tushare: 未配置token")
except Exception as e:
    print(f"tushare失败: {e}")