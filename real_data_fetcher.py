#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实股票数据获取器
使用HTTP接口绕过HTTPS代理限制，获取真实A股数据

可用接口:
1. 东方财富HTTP - 历史K线数据（日/周/月）
2. 腾讯股票 - 实时行情
3. 新浪股票 - 实时行情
"""

import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import time

logger = logging.getLogger(__name__)


class RealDataFetcher:
    """真实股票数据获取器（HTTP接口）"""
    
    def __init__(self):
        # 清除系统代理（测试证明 requests.get 直接可用）
        for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
            os.environ.pop(key, None)
    
    def fetch_kline(self, symbol: str, period_days: int = 500) -> pd.DataFrame:
        """
        从东方财富获取历史K线数据
        
        Args:
            symbol: 6位股票代码
            period_days: 获取天数
        
        Returns:
            标准化的OHLCV DataFrame
        """
        # 确定市场代码
        market = self._get_market_code(symbol)
        secid = f"{market}.{symbol}"
        
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y%m%d')
        
        url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "klt": "101",  # 日K
            "fqt": "1",    # 前复权
            "secid": secid,
            "beg": start_date,
            "end": end_date
        }
        
        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200:
                raise ValueError(f"HTTP {r.status_code}")
            
            data = r.json()
            klines = data.get('data', {}).get('klines', [])
            
            if not klines:
                raise ValueError("返回空数据")
            
            # 解析K线数据: 日期,开盘,收盘,最高,最低,成交量,成交额,...
            rows = []
            for line in klines:
                parts = line.split(',')
                if len(parts) >= 7:
                    rows.append({
                        'Date': parts[0],
                        'Open': float(parts[1]),
                        'Close': float(parts[2]),
                        'High': float(parts[3]),
                        'Low': float(parts[4]),
                        'Volume': float(parts[5]),
                        'Amount': float(parts[6])
                    })
            
            df = pd.DataFrame(rows)
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            
            logger.info(f"✅ {symbol} 获取 {len(df)} 条K线 ({df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')})")
            return df
            
        except Exception as e:
            logger.error(f"❌ {symbol} K线获取失败: {e}")
            return None
    
    def fetch_realtime(self, symbol: str) -> dict:
        """
        从腾讯接口获取实时行情
        
        Args:
            symbol: 6位股票代码
        
        Returns:
            实时行情字典
        """
        market = 'sh' if symbol.startswith(('6', '5')) else 'sz'
        url = f"http://qt.gtimg.cn/q={market}{symbol}"
        
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200 and len(r.text) > 50:
                return self._parse_tencent_quote(r.text)
        except Exception as e:
            logger.warning(f"腾讯接口失败: {e}")
        
        return None
    
    def fetch_stock_info(self, symbol: str) -> dict:
        """
        从biyingapi获取股票基本信息（市值、PE等）
        """
        try:
            url = f"http://api.biyingapi.com/hsrl/ssjy/{symbol}/sdfg56655ertghdsf36"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and 'p' in data:
                    return {
                        'symbol': symbol,
                        'price': float(data.get('p', 0)),
                        'market_cap': float(data.get('sz', 0)),  # 总市值（元）
                        'market_cap_yi': float(data.get('sz', 0)) / 1e8,  # 总市值（亿）
                        'pe': float(data.get('pe', 0)),
                        'pb': float(data.get('sjl', 0)),
                        'change_pct': float(data.get('pc', 0)),
                        'volume': float(data.get('v', 0)),
                        'amount': float(data.get('cje', 0)),
                        'turnover_rate': float(data.get('hs', 0)),
                    }
        except Exception as e:
            logger.warning(f"biyingapi失败: {e}")
        
        return None
    
    def batch_fetch_klines(self, symbols: list, period_days: int = 500, 
                           delay: float = 0.3) -> dict:
        """
        批量获取K线数据
        
        Args:
            symbols: 股票代码列表
            period_days: 获取天数
            delay: 每次请求间隔（秒）
        
        Returns:
            {symbol: DataFrame} 字典
        """
        results = {}
        total = len(symbols)
        
        for idx, symbol in enumerate(symbols, 1):
            df = self.fetch_kline(symbol, period_days)
            if df is not None and len(df) > 120:
                results[symbol] = df
            
            if idx < total:
                time.sleep(delay)
            
            if idx % 10 == 0:
                logger.info(f"进度: {idx}/{total}, 成功: {len(results)}")
        
        logger.info(f"批量获取完成: {len(results)}/{total} 只股票")
        return results
    
    def _get_market_code(self, symbol: str) -> str:
        """判断市场代码"""
        if symbol.startswith(('6', '5')):
            return '1'  # 上海
        elif symbol.startswith(('0', '3')):
            return '0'  # 深圳
        elif symbol.startswith('8') or symbol.startswith('4'):
            return '0'  # 北交所
        return '1'
    
    def _parse_tencent_quote(self, text: str) -> dict:
        """解析腾讯行情数据"""
        try:
            # v_sh600519="1~贵州茅台~600519~1326.00~1275.98~..."
            data_str = text.split('"')[1]
            fields = data_str.split('~')
            
            return {
                'name': fields[1],
                'symbol': fields[2],
                'price': float(fields[3]),
                'prev_close': float(fields[4]),
                'open': float(fields[5]),
                'volume': float(fields[6]),  # 成交量(手)
                'buy_vol': float(fields[7]),
                'sell_vol': float(fields[8]),
                'change_pct': float(fields[32]) if len(fields) > 32 else 0,
                'pe': float(fields[39]) if len(fields) > 39 else 0,
                'market_cap': float(fields[45]) if len(fields) > 45 else 0,  # 总市值(万)
            }
        except Exception as e:
            logger.warning(f"解析腾讯数据失败: {e}")
            return None


# 全局实例
real_data_fetcher = RealDataFetcher()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    fetcher = RealDataFetcher()
    
    # 测试获取茅台K线
    print("\n获取600519(贵州茅台)历史K线...")
    df = fetcher.fetch_kline("600519", 500)
    if df is not None:
        print(f"获取 {len(df)} 条数据")
        print(f"时间范围: {df.index[0]} ~ {df.index[-1]}")
        print(f"\n最新5天:")
        print(df.tail())
    
    # 测试获取实时行情
    print("\n获取600519实时行情...")
    quote = fetcher.fetch_realtime("600519")
    if quote:
        print(f"股票: {quote['name']} 价格: {quote['price']} 涨跌: {quote['change_pct']}%")
    
    # 测试获取基本信息
    print("\n获取600519基本信息...")
    info = fetcher.fetch_stock_info("600519")
    if info:
        print(f"总市值: {info['market_cap_yi']:.0f}亿 PE: {info['pe']} PB: {info['pb']}")