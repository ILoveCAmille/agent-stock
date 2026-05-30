#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断DNS和各域名连通性"""
import os
import socket

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(key, None)

domains = [
    ("qt.gtimg.cn", 80, "腾讯行情"),
    ("hq.sinajs.cn", 80, "新浪行情"),
    ("push2his.eastmoney.com", 80, "东方财富K线"),
    ("api.biyingapi.com", 80, "biyingapi"),
]

print("DNS解析测试:")
for domain, port, name in domains:
    try:
        ip = socket.gethostbyname(domain)
        print(f"  {name} ({domain}): {ip}")
    except Exception as e:
        print(f"  {name} ({domain}): DNS失败 - {e}")

print("\nTCP连接测试:")
for domain, port, name in domains:
    try:
        sock = socket.create_connection((domain, port), timeout=5)
        print(f"  ✅ {name} ({domain}:{port}): 连接成功")
        sock.close()
    except Exception as e:
        print(f"  ❌ {name} ({domain}:{port}): {e}")

print("\nHTTP请求测试:")
import requests
for domain, port, name in domains:
    try:
        if "gtimg" in domain:
            r = requests.get(f"http://{domain}/q=sh600519", timeout=10)
        elif "sinajs" in domain:
            r = requests.get(f"http://{domain}/list=sh600519", 
                           headers={"Referer":"http://finance.sina.com.cn"}, timeout=10)
        elif "eastmoney" in domain:
            r = requests.get(f"http://{domain}/api/qt/stock/kline/get",
                           params={"secid":"1.600519","klt":"101","fqt":"1",
                                   "beg":"20260501","end":"20260530",
                                   "fields1":"f1","fields2":"f51,f52,f53,f54,f55,f56"},
                           timeout=10)
        elif "biyingapi" in domain:
            r = requests.get(f"http://{domain}/hsrl/ssjy/600519/sdfg56655ertghdsf36", timeout=10)
        print(f"  ✅ {name}: HTTP {r.status_code}, {len(r.content)} bytes")
    except Exception as e:
        print(f"  ❌ {name}: {e}")

# 额外测试: 备用域名
print("\n备用接口测试:")
alt_tests = [
    ("http://qt.gtimg.cn/q=sh600519", "腾讯实时"),
    ("http://hq.sinajs.cn/list=sh600519", "新浪实时"),
    ("http://api.biyingapi.com/hsrl/ssjy/600519/sdfg56655ertghdsf36", "biyingapi"),
    ("http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh600519&scale=240&ma=no&datalen=100", "新浪K线"),
]
for url, name in alt_tests:
    try:
        r = requests.get(url, headers={"Referer":"http://finance.sina.com.cn"}, timeout=10)
        print(f"  ✅ {name}: {r.status_code}, {len(r.content)} bytes")
        if len(r.content) > 100:
            print(f"     预览: {r.text[:150]}...")
    except Exception as e:
        print(f"  ❌ {name}: {e}")