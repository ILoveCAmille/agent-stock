#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试多种免费股票数据接口的可用性"""
import os
import sys

# 清除代理
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(key, None)

import requests
import json

print("=" * 70)
print("测试免费股票数据接口可用性")
print("=" * 70)

results = {}

# ==================== 方案1: 腾讯股票接口 ====================
print("\n[方案1] 腾讯股票实时行情接口...")
try:
    # 腾讯接口: http://qt.gtimg.cn/q=sh600519
    r = requests.get("http://qt.gtimg.cn/q=sh600519", timeout=10)
    if r.status_code == 200 and len(r.text) > 50:
        print(f"  ✅ 腾讯接口可用! 数据长度: {len(r.text)}")
        print(f"  数据预览: {r.text[:200]}...")
        results['tencent'] = True
    else:
        print(f"  ❌ 腾讯接口返回异常: status={r.status_code}")
        results['tencent'] = False
except Exception as e:
    print(f"  ❌ 腾讯接口失败: {e}")
    results['tencent'] = False

# ==================== 方案2: 新浪股票接口 ====================
print("\n[方案2] 新浪股票实时行情接口...")
try:
    # 新浪接口: http://hq.sinajs.cn/list=sh600519
    r = requests.get("http://hq.sinajs.cn/list=sh600519", 
                      headers={"Referer": "http://finance.sina.com.cn"}, timeout=10)
    if r.status_code == 200 and len(r.text) > 50:
        print(f"  ✅ 新浪接口可用! 数据长度: {len(r.text)}")
        print(f"  数据预览: {r.text[:200]}...")
        results['sina'] = True
    else:
        print(f"  ❌ 新浪接口返回异常: status={r.status_code}")
        results['sina'] = False
except Exception as e:
    print(f"  ❌ 新浪接口失败: {e}")
    results['sina'] = False

# ==================== 方案3: 东方财富K线接口(直接HTTP) ====================
print("\n[方案3] 东方财富K线接口(直接HTTP)...")
try:
    url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": "101",  # 日K
        "fqt": "1",    # 前复权
        "secid": "1.600519",
        "beg": "20250101",
        "end": "20260530"
    }
    # 注意: 用http而不是https
    r = requests.get(url, params=params, timeout=10)
    if r.status_code == 200:
        data = r.json()
        klines = data.get('data', {}).get('klines', [])
        if klines:
            print(f"  ✅ 东方财富HTTP接口可用! 获取 {len(klines)} 条K线")
            print(f"  最新: {klines[-1]}")
            results['eastmoney_http'] = True
        else:
            print(f"  ❌ 东方财富HTTP返回空数据")
            results['eastmoney_http'] = False
    else:
        print(f"  ❌ 东方财富HTTP返回: {r.status_code}")
        results['eastmoney_http'] = False
except Exception as e:
    print(f"  ❌ 东方财富HTTP失败: {e}")
    results['eastmoney_http'] = False

# ==================== 方案4: baostock ====================
print("\n[方案4] baostock(免费A股数据)...")
try:
    import baostock as bs
    lg = bs.login()
    if lg.error_code == '0':
        rs = bs.query_history_k_data_plus("sh.600519",
            "date,code,open,high,low,close,volume,amount",
            start_date="2025-01-01", end_date="2026-05-30",
            frequency="d", adjustflag="2")
        if rs.error_code == '0':
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            print(f"  ✅ baostock可用! 获取 {len(data_list)} 条K线")
            if data_list:
                print(f"  最新: {data_list[-1]}")
            results['baostock'] = True
        else:
            print(f"  ❌ baostock查询失败: {rs.error_msg}")
            results['baostock'] = False
        bs.logout()
    else:
        print(f"  ❌ baostock登录失败: {lg.error_msg}")
        results['baostock'] = False
except ImportError:
    print("  ❌ baostock未安装 (pip install baostock)")
    results['baostock'] = 'not_installed'
except Exception as e:
    print(f"  ❌ baostock失败: {e}")
    results['baostock'] = False

# ==================== 方案5: akshare直接HTTP(绕过https) ====================
print("\n[方案5] akshare(清除代理后测试)...")
try:
    # 强制清除所有代理
    session = requests.Session()
    session.trust_env = False
    
    import akshare as ak
    # Monkey-patch requests to bypass proxy
    import akshare.stock_feature.stock_hist_em as hist_module
    
    df = ak.stock_zh_a_hist(symbol="600519", period="daily",
                             start_date="20250101", end_date="20260530", adjust="qfq")
    if df is not None and not df.empty:
        print(f"  ✅ akshare可用! 获取 {len(df)} 条K线")
        print(f"  最新: {df.tail(1).to_string()}")
        results['akshare'] = True
    else:
        print(f"  ❌ akshare返回空数据")
        results['akshare'] = False
except Exception as e:
    print(f"  ❌ akshare失败: {e}")
    results['akshare'] = False

# ==================== 方案6: yfinance ====================
print("\n[方案6] yfinance(雅虎财经)...")
try:
    import yfinance as yf
    ticker = yf.Ticker("600519.SS")
    df = ticker.history(period="1y")
    if not df.empty:
        print(f"  ✅ yfinance可用! 获取 {len(df)} 条K线")
        results['yfinance'] = True
    else:
        print(f"  ❌ yfinance返回空数据")
        results['yfinance'] = False
except ImportError:
    print("  ❌ yfinance未安装")
    results['yfinance'] = 'not_installed'
except Exception as e:
    print(f"  ❌ yfinance失败: {e}")
    results['yfinance'] = False

# ==================== 方案7: 必应API(测试) ====================
print("\n[方案7] biyingapi(免费股票API)...")
try:
    url = "http://api.biyingapi.com/hsrl/ssjy/600519/sdfg56655ertghdsf36"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        data = r.json()
        if isinstance(data, dict) and 'p' in data:
            print(f"  ✅ biyingapi可用! 当前价格: {data.get('p')}")
            results['biyingapi'] = True
        elif isinstance(data, list) and len(data) > 0:
            print(f"  ✅ biyingapi可用! 获取 {len(data)} 条数据")
            results['biyingapi'] = True
        else:
            print(f"  ❌ biyingapi返回格式异常: {str(data)[:100]}")
            results['biyingapi'] = False
    else:
        print(f"  ❌ biyingapi返回: {r.status_code}")
        results['biyingapi'] = False
except Exception as e:
    print(f"  ❌ biyingapi失败: {e}")
    results['biyingapi'] = False

# ==================== 方案8: 网易财经 ====================
print("\n[方案8] 网易财经历史数据接口...")
try:
    # 网易接口: http://quotes.money.163.com/service/chddata.html
    url = "http://quotes.money.163.com/service/chddata.html"
    params = {
        "code": "0600519",  # 0=上海, 1=深圳
        "start": "20250101",
        "end": "20260530",
        "fields": "TCLOSE;HIGH;LOW;TOPEN;LCLOSE;CHG;PCHG;VOTURNOVER;VATURNOVER"
    }
    r = requests.get(url, params=params, timeout=10)
    if r.status_code == 200 and len(r.content) > 100:
        lines = r.content.decode('gbk').strip().split('\n')
        print(f"  ✅ 网易财经可用! 获取 {len(lines)-1} 条K线")
        if len(lines) > 1:
            print(f"  最新: {lines[1][:100]}")
        results['netease'] = True
    else:
        print(f"  ❌ 网易财经返回: {r.status_code}, 长度={len(r.content)}")
        results['netease'] = False
except Exception as e:
    print(f"  ❌ 网易财经失败: {e}")
    results['netease'] = False

# ==================== 汇总 ====================
print("\n" + "=" * 70)
print("📊 接口可用性汇总")
print("=" * 70)

available = []
for name, status in results.items():
    emoji = "✅" if status is True else ("⚠️" if status == 'not_installed' else "❌")
    print(f"  {emoji} {name}: {status}")
    if status is True:
        available.append(name)

print(f"\n可用接口: {len(available)}/{len(results)}")
if available:
    print(f"推荐使用: {', '.join(available)}")
else:
    print("当前网络环境无法连接任何股票数据接口，建议检查网络/代理设置")