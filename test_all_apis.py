#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面测试免费股票数据API接口
测试尽可能多的免费数据源，找出在当前网络下可用的接口
"""
import os
import sys
import time
import json

# 清除代理
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

import requests
import pandas as pd

print("=" * 80)
print("全面测试免费股票数据API接口")
print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

TEST_CODE = "600519"  # 贵州茅台
TEST_NAME = "贵州茅台"
results = {}

def test_api(name, func):
    """测试一个API并记录结果"""
    print(f"\n[{name}]")
    try:
        data = func()
        if data is not None and data is not False:
            results[name] = {"status": "✅ 可用", "data": data}
            return True
        else:
            results[name] = {"status": "❌ 失败", "data": None}
            return False
    except Exception as e:
        results[name] = {"status": f"❌ 错误: {str(e)[:80]}", "data": None}
        print(f"  ❌ {e}")
        return False


# ==================== 1. 新浪K线API ====================
def test_sina_kline():
    url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": f"sh{TEST_CODE}", "scale": "240", "ma": "no", "datalen": "100"}
    r = requests.get(url, params=params, headers={"Referer": "http://finance.sina.com.cn"}, timeout=15)
    data = r.json()
    if data and len(data) > 0:
        print(f"  ✅ 获取 {len(data)} 条日K线 (新浪K线JSON)")
        print(f"  最新: {data[-1]}")
        return len(data)
    return None
test_api("1. 新浪K线API (历史K线)", test_sina_kline)

# ==================== 2. 腾讯实时行情 ====================
def test_tencent_realtime():
    url = f"http://qt.gtimg.cn/q=sh{TEST_CODE}"
    r = requests.get(url, timeout=10)
    if r.status_code == 200 and len(r.text) > 50:
        fields = r.text.split('"')[1].split('~')
        name, price, change = fields[1], fields[3], fields[32]
        print(f"  ✅ {name} 价格:{price} 涨跌:{change}%")
        return f"价格:{price}"
    return None
test_api("2. 腾讯实时行情", test_tencent_realtime)

# ==================== 3. 新浪实时行情 ====================
def test_sina_realtime():
    url = f"http://hq.sinajs.cn/list=sh{TEST_CODE}"
    r = requests.get(url, headers={"Referer": "http://finance.sina.com.cn"}, timeout=10)
    if r.status_code == 200 and len(r.text) > 50:
        fields = r.text.split('"')[1].split(',')
        print(f"  ✅ {fields[0]} 开盘:{fields[1]} 收盘:{fields[3]}")
        return f"收盘:{fields[3]}"
    return None
test_api("3. 新浪实时行情", test_sina_realtime)

# ==================== 4. biyingapi ====================
def test_biyingapi():
    url = f"http://api.biyingapi.com/hsrl/ssjy/{TEST_CODE}/sdfg56655ertghdsf36"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        data = r.json()
        if isinstance(data, dict) and 'p' in data:
            print(f"  ✅ 价格:{data['p']} 市值:{float(data.get('sz',0))/1e8:.0f}亿 PE:{data.get('pe')}")
            return f"价格:{data['p']}"
    return None
test_api("4. biyingapi (实时+基本面)", test_biyingapi)

# ==================== 5. 东方财富HTTP K线 ====================
def test_eastmoney_http():
    url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {"fields1":"f1,f2,f3,f4,f5,f6","fields2":"f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
              "ut":"7eea3edcaed734bea9cbfc24409ed989","klt":"101","fqt":"1",
              "secid":f"1.{TEST_CODE}","beg":"20260101","end":"20260530"}
    r = requests.get(url, params=params, timeout=15)
    data = r.json()
    klines = data.get('data', {}).get('klines', [])
    if klines:
        print(f"  ✅ 获取 {len(klines)} 条K线")
        print(f"  最新: {klines[-1]}")
        return len(klines)
    return None
test_api("5. 东方财富HTTP (历史K线)", test_eastmoney_http)

# ==================== 6. 腾讯历史K线 ====================
def test_tencent_kline():
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh{TEST_CODE},day,,100,qfq"
    r = requests.get(url, timeout=15)
    if r.status_code == 200:
        data = r.json()
        klines = data.get('data', {}).get(f'sh{TEST_CODE}', {})
        day_data = klines.get('qfqday', klines.get('day', []))
        if day_data:
            print(f"  ✅ 获取 {len(day_data)} 条K线")
            print(f"  最新: {day_data[-1]}")
            return len(day_data)
    return None
test_api("6. 腾讯历史K线 (前复权)", test_tencent_kline)

# ==================== 7. 腾讯不复权K线 ====================
def test_tencent_kline_bfq():
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh{TEST_CODE},day,,,100"
    r = requests.get(url, timeout=15)
    if r.status_code == 200:
        data = r.json()
        klines = data.get('data', {}).get(f'sh{TEST_CODE}', {})
        day_data = klines.get('day', [])
        if day_data:
            print(f"  ✅ 获取 {len(day_data)} 条K线")
            return len(day_data)
    return None
test_api("7. 腾讯历史K线 (不复权)", test_tencent_kline_bfq)

# ==================== 8. 新浪分时数据 ====================
def test_sina_minute():
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": f"sh{TEST_CODE}", "scale": "5", "ma": "no", "datalen": "100"}
    r = requests.get(url, params=params, headers={"Referer": "http://finance.sina.com.cn"}, timeout=15)
    data = r.json()
    if data and len(data) > 0:
        print(f"  ✅ 获取 {len(data)} 条5分钟K线")
        return len(data)
    return None
test_api("8. 新浪5分钟K线", test_sina_minute)

# ==================== 9. 新浪周K线 ====================
def test_sina_week():
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": f"sh{TEST_CODE}", "scale": "1200", "ma": "no", "datalen": "100"}
    r = requests.get(url, params=params, headers={"Referer": "http://finance.sina.com.cn"}, timeout=15)
    data = r.json()
    if data and len(data) > 0:
        print(f"  ✅ 获取 {len(data)} 条周K线")
        return len(data)
    return None
test_api("9. 新浪周K线", test_sina_week)

# ==================== 10. 新浪板块数据 ====================
def test_sina_sector():
    url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    params = {"page": "1", "num": "10", "sort": "changepercent", "asc": "0", "node": "hs_a", "symbol": "", "_s_r_a": "sort"}
    r = requests.get(url, params=params, headers={"Referer": "http://finance.sina.com.cn"}, timeout=15)
    data = r.json()
    if data and len(data) > 0:
        print(f"  ✅ 获取 {len(data)} 只A股行情")
        return len(data)
    return None
test_api("10. 新浪A股全市场行情", test_sina_sector)

# ==================== 11. 腾讯板块排行 ====================
def test_tencent_rank():
    url = "http://qt.gtimg.cn/q=sh000001,sz399001,sz399006"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        lines = r.text.strip().split('\n')
        print(f"  ✅ 获取 {len(lines)} 个指数行情")
        for line in lines[:3]:
            if '"' in line:
                fields = line.split('"')[1].split('~')
                if len(fields) > 4:
                    print(f"     {fields[1]}: {fields[3]}")
        return len(lines)
    return None
test_api("11. 腾讯指数行情", test_tencent_rank)

# ==================== 12. 腾讯个股资金流向 ====================
def test_tencent_fund_flow():
    url = f"http://qt.gtimg.cn/q=ff_sh{TEST_CODE}"
    r = requests.get(url, timeout=10)
    if r.status_code == 200 and len(r.text) > 50:
        print(f"  ✅ 资金流向数据长度: {len(r.text)} bytes")
        return len(r.text)
    return None
test_api("12. 腾讯资金流向", test_tencent_fund_flow)

# ==================== 13. 东方财富实时行情 ====================
def test_eastmoney_realtime():
    url = "http://push2.eastmoney.com/api/qt/stock/get"
    params = {"secid": f"1.{TEST_CODE}", "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f170"}
    r = requests.get(url, params=params, timeout=15)
    data = r.json()
    d = data.get('data', {})
    if d and 'f43' in d:
        price = d.get('f43', 0) / 100 if isinstance(d.get('f43'), int) else d.get('f43')
        print(f"  ✅ 价格:{price} 最高:{d.get('f44')} 最低:{d.get('f45')}")
        return f"价格:{price}"
    return None
test_api("13. 东方财富实时行情", test_eastmoney_realtime)

# ==================== 14. 东方财富资金流向 ====================
def test_eastmoney_fund_flow():
    url = "http://push2.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {"secid": f"1.{TEST_CODE}", "fields1": "f1,f2,f3,f7", "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
              "lmt": "20", "klt": "101"}
    r = requests.get(url, params=params, timeout=15)
    data = r.json()
    klines = data.get('data', {}).get('klines', [])
    if klines:
        print(f"  ✅ 获取 {len(klines)} 天资金流向数据")
        print(f"  最新: {klines[-1][:80]}")
        return len(klines)
    return None
test_api("14. 东方财富资金流向", test_eastmoney_fund_flow)

# ==================== 15. 新浪股票详情 ====================
def test_sina_detail():
    url = f"http://finance.sina.com.cn/realstock/company/sh{TEST_CODE}/nc.shtml"
    r = requests.get(url, timeout=10, headers={"Referer": "http://finance.sina.com.cn"})
    if r.status_code == 200 and len(r.text) > 1000:
        print(f"  ✅ 页面大小: {len(r.text)} bytes")
        return len(r.text)
    return None
test_api("15. 新浪股票详情页", test_sina_detail)

# ==================== 16. 百度股票 ====================
def test_baidu_stock():
    url = f"https://finance.pae.baidu.com/vapi/v1/getquotation?srcid=5353&pointType=string&group=quotation_kline_ab&query={TEST_CODE}&code={TEST_CODE}&market_type=ab&newFormat=1&is_498=1&finClientType=pc"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get('ResultCode') == 0:
                print(f"  ✅ 百度股票接口可用")
                return True
    except:
        pass
    return None
test_api("16. 百度股票", test_baidu_stock)

# ==================== 17. ifeng凤凰财经 ====================
def test_ifeng():
    url = f"http://api.finance.ifeng.com/akdaily/?code=sh{TEST_CODE}&type=last"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            records = data.get('record', [])
            if records:
                print(f"  ✅ 获取 {len(records)} 条K线 (凤凰财经)")
                return len(records)
    except Exception as e:
        print(f"  ❌ {e}")
    return None
test_api("17. 凤凰财经K线", test_ifeng)

# ==================== 18. 巨潮资讯 ====================
def test_cninfo():
    url = "http://webapi.cninfo.com.cn/api/sysapi/p_sysapi1135"
    try:
        r = requests.post(url, data={"scode": TEST_CODE, "sdate": "20260101", "edate": "20260530"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            records = data.get('records', [])
            if records:
                print(f"  ✅ 获取 {len(records)} 条数据 (巨潮)")
                return len(records)
    except Exception as e:
        print(f"  ❌ {e}")
    return None
test_api("18. 巨潮资讯", test_cninfo)

# ==================== 19. 通达信HTTP ====================
def test_tdx_http():
    url = f"http://qt.gtimg.cn/q=sh{TEST_CODE}"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        # 解析通达信格式
        print(f"  ✅ 通达信格式数据: {len(r.text)} bytes")
        return True
    return None
test_api("19. 通达信行情", test_tdx_http)

# ==================== 20. 和讯网 ====================
def test_hexun():
    url = f"http://stockdata.stock.hexun.com/zrbg/data/zrbList.aspx?count=5&pname={TEST_CODE}"
    try:
        r = requests.get(url, timeout=10, headers={"Referer": "http://stock.hexun.com"})
        if r.status_code == 200 and len(r.content) > 100:
            print(f"  ✅ 和讯数据: {len(r.content)} bytes")
            return len(r.content)
    except Exception as e:
        print(f"  ❌ {e}")
    return None
test_api("20. 和讯网数据", test_hexun)


# ==================== 汇总 ====================
print("\n" + "=" * 80)
print("📊 API可用性汇总")
print("=" * 80)

available = []
failed = []

for name, info in results.items():
    status = info['status']
    if '✅' in status:
        available.append(name)
        print(f"  {status}  {name}")
    else:
        failed.append(name)
        print(f"  {status}  {name}")

print(f"\n✅ 可用: {len(available)}/{len(results)}")
print(f"❌ 不可用: {len(failed)}/{len(results)}")
print(f"\n可用接口列表:")
for name in available:
    print(f"  • {name}")

# 保存结果
output_file = "api_test_results.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump({
        "test_time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "total": len(results),
        "available": len(available),
        "available_list": available,
        "failed_list": failed,
        "details": {k: v['status'] for k, v in results.items()}
    }, f, ensure_ascii=False, indent=2)

print(f"\n💾 结果已保存: {output_file}")