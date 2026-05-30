#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试数据接口稳定性"""
import os
# 清除代理
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(key, None)

import akshare as ak
import pandas as pd

print("测试akshare数据接口...")
print("=" * 60)

# 测试1: 个股历史数据
try:
    df = ak.stock_zh_a_hist(symbol='600519', period='daily', 
                             start_date='20260101', end_date='20260530', adjust='qfq')
    print(f"✅ stock_zh_a_hist: {len(df)} 条数据")
    print(f"   列名: {df.columns.tolist()}")
    print(f"   最新: {df.tail(1).to_string()}")
except Exception as e:
    print(f"❌ stock_zh_a_hist 失败: {e}")

# 测试2: 获取A股实时行情（用于获取市值）
try:
    df = ak.stock_zh_a_spot_em()
    print(f"\n✅ stock_zh_a_spot_em: {len(df)} 只股票")
    print(f"   列名: {df.columns.tolist()[:10]}...")
    # 检查市值列
    if '总市值' in df.columns:
        df['总市值亿'] = df['总市值'] / 1e8
        print(f"   市值范围: {df['总市值亿'].min():.1f}亿 ~ {df['总市值亿'].max():.1f}亿")
except Exception as e:
    print(f"❌ stock_zh_a_spot_em 失败: {e}")

# 测试3: 按市值分类
try:
    df_spot = ak.stock_zh_a_spot_em()
    df_spot['总市值亿'] = df_spot['总市值'] / 1e8
    
    small = df_spot[(df_spot['总市值亿'] > 0) & (df_spot['总市值亿'] < 100)]
    mid = df_spot[(df_spot['总市值亿'] >= 100) & (df_spot['总市值亿'] < 500)]
    large = df_spot[df_spot['总市值亿'] >= 500]
    
    print(f"\n市值分布:")
    print(f"   小市值(<100亿): {len(small)} 只")
    print(f"   中市值(100-500亿): {len(mid)} 只")
    print(f"   大市值(≥500亿): {len(large)} 只")
    
    # 取流动性最好的（按成交额排序）
    if '成交额' in df_spot.columns:
        print(f"\n小市值Top5(按成交额):")
        top_small = small.nlargest(5, '成交额')[['代码', '名称', '总市值亿', '成交额', '涨跌幅']]
        print(top_small.to_string(index=False))
        
        print(f"\n大市值Top5(按成交额):")
        top_large = large.nlargest(5, '成交额')[['代码', '名称', '总市值亿', '成交额', '涨跌幅']]
        print(top_large.to_string(index=False))
except Exception as e:
    print(f"❌ 市值分类失败: {e}")

print("\n" + "=" * 60)
print("接口测试完成")