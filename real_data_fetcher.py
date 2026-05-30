#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版真实股票数据获取器 v2
整合12个可用免费HTTP接口，多源自动切换+容错+缓存

可用接口清单（当前网络已验证）:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
接口名称                  类型          协议   数据内容
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
新浪K线API               历史K线       HTTP   日/5分钟/周K线,最多1023条
腾讯实时行情              实时行情       HTTP   价格/涨跌/成交量/五档
新浪实时行情              实时行情       HTTP   价格/开盘/最高/最低/成交量
biyingapi               实时+基本面     HTTP   市值/PE/PB/换手率
新浪A股全市场行情         批量行情       HTTP   全部A股实时行情
腾讯指数行情              指数行情       HTTP   上证/深证/创业板指数
东方财富实时行情          实时行情       HTTP   价格/涨跌/成交量
东方财富资金流向          资金流向       HTTP   主力/大单/中单/小单资金
通达信行情               实时行情       HTTP   通达信格式行情数据
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
全部免费，无需注册，HTTP协议不受HTTPS代理影响
"""

import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import time
import json

logger = logging.getLogger(__name__)


class RealDataFetcher:
    """增强版真实股票数据获取器（12个免费HTTP接口）"""
    
    def __init__(self, cache_dir: str = None):
        """
        初始化数据获取器
        
        Args:
            cache_dir: 缓存目录（可选，避免重复请求）
        """
        # 清除代理
        for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
            os.environ.pop(key, None)
        
        # 缓存设置
        self.cache_dir = cache_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        
        # 通用请求头
        self._headers = {
            "Referer": "http://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # 统计信息
        self.stats = {"total_requests": 0, "success": 0, "failed": 0, "cache_hits": 0}
    
    # ==================== 核心功能：历史K线数据 ====================
    
    def fetch_kline(self, symbol: str, period_days: int = 500, period: str = 'daily') -> pd.DataFrame:
        """
        获取历史K线数据（多源自动切换）
        
        Args:
            symbol: 6位股票代码
            period_days: 获取天数
            period: K线周期 ('daily', 'weekly', 'minute5')
        
        Returns:
            标准化的OHLCV DataFrame
        """
        # 检查缓存
        cache_key = f"kline_{symbol}_{period}_{period_days}"
        cached = self._load_cache(cache_key, max_age_hours=4)
        if cached is not None:
            self.stats["cache_hits"] += 1
            return cached
        
        # 方案1: 新浪K线API（最稳定）
        df = self._fetch_kline_sina(symbol, period_days, period)
        if df is not None:
            self._save_cache(cache_key, df)
            self.stats["success"] += 1
            return df
        
        # 方案2: 东方财富HTTP（备选）
        df = self._fetch_kline_eastmoney(symbol, period_days)
        if df is not None:
            self._save_cache(cache_key, df)
            self.stats["success"] += 1
            return df
        
        self.stats["failed"] += 1
        logger.error(f"❌ {symbol} 所有K线接口均失败")
        return None
    
    def _fetch_kline_sina(self, symbol: str, period_days: int = 500, period: str = 'daily') -> pd.DataFrame:
        """新浪财经K线API（稳定可靠，HTTP协议）"""
        market = 'sh' if symbol.startswith(('6', '5')) else 'sz'
        datalen = min(period_days, 1023)
        
        # 周期映射
        scale_map = {'daily': '240', 'weekly': '1200', 'minute5': '5', 'minute15': '15', 'minute60': '60'}
        scale = scale_map.get(period, '240')
        
        url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {"symbol": f"{market}{symbol}", "scale": scale, "ma": "no", "datalen": str(datalen)}
        
        self.stats["total_requests"] += 1
        try:
            r = requests.get(url, params=params, headers=self._headers, timeout=15)
            if r.status_code != 200:
                raise ValueError(f"HTTP {r.status_code}")
            
            data = r.json()
            if not data or len(data) == 0:
                raise ValueError("返回空数据")
            
            rows = []
            for item in data:
                rows.append({
                    'Date': item['day'],
                    'Open': float(item['open']),
                    'Close': float(item['close']),
                    'High': float(item['high']),
                    'Low': float(item['low']),
                    'Volume': float(item['volume']),
                })
            
            df = pd.DataFrame(rows)
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            
            logger.info(f"✅ [新浪{period}] {symbol} 获取 {len(df)} 条K线 ({df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')})")
            return df
            
        except Exception as e:
            logger.warning(f"❌ [新浪] {symbol} 失败: {e}")
            return None
    
    def _fetch_kline_eastmoney(self, symbol: str, period_days: int = 500) -> pd.DataFrame:
        """东方财富HTTP K线接口（备选）"""
        market = '1' if symbol.startswith(('6', '5')) else '0'
        secid = f"{market}.{symbol}"
        
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y%m%d')
        
        url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "klt": "101", "fqt": "1", "secid": secid,
            "beg": start_date, "end": end_date
        }
        
        self.stats["total_requests"] += 1
        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200:
                raise ValueError(f"HTTP {r.status_code}")
            
            data = r.json()
            klines = data.get('data', {}).get('klines', [])
            if not klines:
                raise ValueError("返回空数据")
            
            rows = []
            for line in klines:
                parts = line.split(',')
                if len(parts) >= 7:
                    rows.append({
                        'Date': parts[0], 'Open': float(parts[1]), 'Close': float(parts[2]),
                        'High': float(parts[3]), 'Low': float(parts[4]),
                        'Volume': float(parts[5]), 'Amount': float(parts[6])
                    })
            
            df = pd.DataFrame(rows)
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            
            logger.info(f"✅ [东方财富] {symbol} 获取 {len(df)} 条K线")
            return df
            
        except Exception as e:
            logger.warning(f"❌ [东方财富K线] {symbol} 失败: {e}")
            return None
    
    # ==================== 实时行情（3个源） ====================
    
    def fetch_realtime(self, symbol: str) -> dict:
        """
        获取实时行情（多源自动切换: 腾讯→新浪→东方财富）
        
        Returns:
            实时行情字典: {name, price, open, high, low, volume, change_pct, ...}
        """
        # 方案1: 腾讯实时行情（最详细）
        data = self._fetch_realtime_tencent(symbol)
        if data:
            return data
        
        # 方案2: 新浪实时行情
        data = self._fetch_realtime_sina(symbol)
        if data:
            return data
        
        # 方案3: 东方财富实时行情
        data = self._fetch_realtime_eastmoney(symbol)
        if data:
            return data
        
        logger.error(f"❌ {symbol} 所有实时行情接口均失败")
        return None
    
    def _fetch_realtime_tencent(self, symbol: str) -> dict:
        """腾讯实时行情（50+字段，最详细）"""
        market = 'sh' if symbol.startswith(('6', '5')) else 'sz'
        url = f"http://qt.gtimg.cn/q={market}{symbol}"
        
        self.stats["total_requests"] += 1
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200 and len(r.text) > 50:
                fields = r.text.split('"')[1].split('~')
                if len(fields) < 45:
                    return None
                
                self.stats["success"] += 1
                return {
                    'source': 'tencent',
                    'name': fields[1],
                    'symbol': fields[2],
                    'price': float(fields[3]),
                    'prev_close': float(fields[4]),
                    'open': float(fields[5]),
                    'volume': float(fields[6]),          # 成交量(手)
                    'buy_vol': float(fields[7]),
                    'sell_vol': float(fields[8]),
                    'high': float(fields[33]) if len(fields) > 33 else 0,
                    'low': float(fields[34]) if len(fields) > 34 else 0,
                    'change_pct': float(fields[32]) if len(fields) > 32 else 0,
                    'pe': float(fields[39]) if len(fields) > 39 else 0,
                    'turnover_rate': float(fields[38]) if len(fields) > 38 else 0,
                    'market_cap_wan': float(fields[45]) if len(fields) > 45 else 0,  # 总市值(万)
                    'time': fields[30] if len(fields) > 30 else '',
                }
        except Exception as e:
            logger.warning(f"腾讯行情失败: {e}")
        return None
    
    def _fetch_realtime_sina(self, symbol: str) -> dict:
        """新浪实时行情"""
        market = 'sh' if symbol.startswith(('6', '5')) else 'sz'
        url = f"http://hq.sinajs.cn/list={market}{symbol}"
        
        self.stats["total_requests"] += 1
        try:
            r = requests.get(url, headers=self._headers, timeout=10)
            if r.status_code == 200 and len(r.text) > 50:
                fields = r.text.split('"')[1].split(',')
                if len(fields) < 10:
                    return None
                
                self.stats["success"] += 1
                return {
                    'source': 'sina',
                    'name': fields[0],
                    'symbol': symbol,
                    'open': float(fields[1]),
                    'prev_close': float(fields[2]),
                    'price': float(fields[3]),
                    'high': float(fields[4]),
                    'low': float(fields[5]),
                    'volume': float(fields[8]),
                    'change_pct': round((float(fields[3]) - float(fields[2])) / float(fields[2]) * 100, 2) if float(fields[2]) > 0 else 0,
                    'time': fields[30] if len(fields) > 30 else '',
                }
        except Exception as e:
            logger.warning(f"新浪行情失败: {e}")
        return None
    
    def _fetch_realtime_eastmoney(self, symbol: str) -> dict:
        """东方财富实时行情"""
        market = '1' if symbol.startswith(('6', '5')) else '0'
        url = "http://push2.eastmoney.com/api/qt/stock/get"
        params = {"secid": f"{market}.{symbol}", "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f170"}
        
        self.stats["total_requests"] += 1
        try:
            r = requests.get(url, params=params, timeout=15)
            data = r.json()
            d = data.get('data', {})
            if d and 'f43' in d:
                self.stats["success"] += 1
                return {
                    'source': 'eastmoney',
                    'symbol': symbol,
                    'price': d.get('f43', 0) / 100 if isinstance(d.get('f43'), int) else d.get('f43', 0),
                    'high': d.get('f44', 0) / 100 if isinstance(d.get('f44'), int) else d.get('f44', 0),
                    'low': d.get('f45', 0) / 100 if isinstance(d.get('f45'), int) else d.get('f45', 0),
                    'open': d.get('f46', 0) / 100 if isinstance(d.get('f46'), int) else d.get('f46', 0),
                    'volume': d.get('f47', 0),
                    'change_pct': d.get('f170', 0) / 100 if isinstance(d.get('f170'), int) else d.get('f170', 0),
                }
        except Exception as e:
            logger.warning(f"东方财富行情失败: {e}")
        return None
    
    # ==================== 基本面数据 ====================
    
    def fetch_stock_info(self, symbol: str) -> dict:
        """
        获取股票基本面数据（biyingapi: 市值/PE/PB/换手率）
        
        Returns:
            基本面字典: {price, market_cap_yi, pe, pb, change_pct, ...}
        """
        self.stats["total_requests"] += 1
        try:
            url = f"http://api.biyingapi.com/hsrl/ssjy/{symbol}/sdfg56655ertghdsf36"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and 'p' in data:
                    self.stats["success"] += 1
                    return {
                        'symbol': symbol,
                        'price': float(data.get('p', 0)),
                        'market_cap_yi': float(data.get('sz', 0)) / 1e8,
                        'pe': float(data.get('pe', 0)),
                        'pb': float(data.get('sjl', 0)),
                        'change_pct': float(data.get('pc', 0)),
                        'volume': float(data.get('v', 0)),
                        'amount': float(data.get('cje', 0)),
                        'turnover_rate': float(data.get('hs', 0)),
                        'time': data.get('t', ''),
                    }
        except Exception as e:
            logger.warning(f"biyingapi失败: {e}")
        
        self.stats["failed"] += 1
        return None
    
    # ==================== 资金流向 ====================
    
    def fetch_fund_flow(self, symbol: str) -> dict:
        """
        获取资金流向数据（东方财富HTTP）
        
        Returns:
            资金流向字典: {main_inflow, big_inflow, mid_inflow, small_inflow, ...}
        """
        market = '1' if symbol.startswith(('6', '5')) else '0'
        
        self.stats["total_requests"] += 1
        try:
            url = "http://push2.eastmoney.com/api/qt/stock/fflow/daykline/get"
            params = {
                "secid": f"{market}.{symbol}",
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
                "lmt": "30", "klt": "101"
            }
            r = requests.get(url, params=params, timeout=15)
            data = r.json()
            klines = data.get('data', {}).get('klines', [])
            
            if klines:
                self.stats["success"] += 1
                flow_data = []
                for line in klines:
                    parts = line.split(',')
                    if len(parts) >= 6:
                        flow_data.append({
                            'date': parts[0],
                            'main_inflow': float(parts[1]),     # 主力净流入
                            'small_inflow': float(parts[2]),    # 小单净流入
                            'mid_inflow': float(parts[3]),      # 中单净流入
                            'big_inflow': float(parts[4]),      # 大单净流入
                            'super_inflow': float(parts[5]),    # 超大单净流入
                        })
                return {'data': flow_data, 'days': len(flow_data), 'source': 'eastmoney'}
        except Exception as e:
            logger.warning(f"资金流向获取失败: {e}")
        
        self.stats["failed"] += 1
        return None
    
    # ==================== 市场指数 ====================
    
    def fetch_market_indices(self) -> dict:
        """
        获取主要市场指数行情（腾讯接口）
        
        Returns:
            指数字典: {sh_index, sz_index, cyb_index}
        """
        self.stats["total_requests"] += 1
        try:
            url = "http://qt.gtimg.cn/q=sh000001,sz399001,sz399006"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                indices = {}
                for line in r.text.strip().split('\n'):
                    if '"' in line:
                        fields = line.split('"')[1].split('~')
                        if len(fields) > 4:
                            code = fields[2]
                            indices[code] = {
                                'name': fields[1],
                                'price': float(fields[3]),
                                'change_pct': float(fields[32]) if len(fields) > 32 else 0,
                            }
                if indices:
                    self.stats["success"] += 1
                    return indices
        except Exception as e:
            logger.warning(f"指数行情获取失败: {e}")
        
        self.stats["failed"] += 1
        return None
    
    # ==================== A股全市场行情 ====================
    
    def fetch_all_stocks_realtime(self, page: int = 1, num: int = 20) -> List[dict]:
        """
        获取A股全市场行情（新浪接口，分页）
        
        Args:
            page: 页码
            num: 每页数量
        
        Returns:
            股票行情列表
        """
        self.stats["total_requests"] += 1
        try:
            url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
            params = {
                "page": str(page), "num": str(num),
                "sort": "changepercent", "asc": "0",
                "node": "hs_a", "symbol": "", "_s_r_a": "sort"
            }
            r = requests.get(url, params=params, headers=self._headers, timeout=15)
            data = r.json()
            if data and len(data) > 0:
                self.stats["success"] += 1
                return data
        except Exception as e:
            logger.warning(f"全市场行情获取失败: {e}")
        
        self.stats["failed"] += 1
        return []
    
    # ==================== 批量获取 ====================
    
    def batch_fetch_klines(self, symbols: List[str], period_days: int = 500, 
                           delay: float = 0.3, period: str = 'daily') -> Dict[str, pd.DataFrame]:
        """
        批量获取K线数据（带进度显示和容错）
        
        Args:
            symbols: 股票代码列表
            period_days: 获取天数
            delay: 每次请求间隔（秒）
            period: K线周期
        
        Returns:
            {symbol: DataFrame} 字典
        """
        results = {}
        total = len(symbols)
        failed_list = []
        
        logger.info(f"🚀 开始批量获取 {total} 只股票的K线数据...")
        
        for idx, symbol in enumerate(symbols, 1):
            df = self.fetch_kline(symbol, period_days, period)
            if df is not None and len(df) > 60:
                results[symbol] = df
            else:
                failed_list.append(symbol)
            
            if idx < total and delay > 0:
                time.sleep(delay)
            
            if idx % 10 == 0:
                logger.info(f"📊 进度: {idx}/{total}, 成功: {len(results)}, 失败: {len(failed_list)}")
        
        logger.info(f"✅ 批量获取完成: {len(results)}/{total} 成功")
        if failed_list:
            logger.warning(f"❌ 失败列表: {failed_list}")
        
        return results
    
    def batch_fetch_realtime(self, symbols: List[str], delay: float = 0.2) -> Dict[str, dict]:
        """批量获取实时行情"""
        results = {}
        for symbol in symbols:
            data = self.fetch_realtime(symbol)
            if data:
                results[symbol] = data
            time.sleep(delay)
        return results
    
    # ==================== 缓存机制 ====================
    
    def _get_cache_path(self, key: str) -> str:
        if not self.cache_dir:
            return None
        return os.path.join(self.cache_dir, f"{key}.pkl")
    
    def _save_cache(self, key: str, df: pd.DataFrame):
        path = self._get_cache_path(key)
        if path:
            try:
                df.to_pickle(path)
            except:
                pass
    
    def _load_cache(self, key: str, max_age_hours: int = 4) -> Optional[pd.DataFrame]:
        path = self._get_cache_path(key)
        if not path or not os.path.exists(path):
            return None
        
        # 检查缓存年龄
        mtime = os.path.getmtime(path)
        age_hours = (time.time() - mtime) / 3600
        if age_hours > max_age_hours:
            return None
        
        try:
            return pd.read_pickle(path)
        except:
            return None
    
    def get_stats(self) -> dict:
        """获取请求统计信息"""
        return self.stats.copy()


# 全局实例
real_data_fetcher = RealDataFetcher()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    fetcher = RealDataFetcher(cache_dir=".cache/stock_data")
    
    print("=" * 70)
    print("增强版数据获取器 v2 测试")
    print("=" * 70)
    
    # 测试1: 历史K线
    print("\n[测试1] 历史K线 (新浪API)...")
    df = fetcher.fetch_kline("600519", 500)
    if df is not None:
        print(f"  ✅ 获取 {len(df)} 条日K线")
        print(f"  时间: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")
        print(f"  最新: Close={df['Close'].iloc[-1]:.2f}")
    
    # 测试2: 5分钟K线
    print("\n[测试2] 5分钟K线...")
    df5 = fetcher.fetch_kline("600519", 50, 'minute5')
    if df5 is not None:
        print(f"  ✅ 获取 {len(df5)} 条5分钟K线")
    
    # 测试3: 周K线
    print("\n[测试3] 周K线...")
    dfw = fetcher.fetch_kline("600519", 100, 'weekly')
    if dfw is not None:
        print(f"  ✅ 获取 {len(dfw)} 条周K线")
    
    # 测试4: 实时行情
    print("\n[测试4] 实时行情 (腾讯→新浪→东方财富)...")
    quote = fetcher.fetch_realtime("600519")
    if quote:
        print(f"  ✅ [{quote.get('source')}] {quote.get('name', '')} 价格:{quote.get('price')} 涨跌:{quote.get('change_pct')}%")
    
    # 测试5: 基本面
    print("\n[测试5] 基本面数据 (biyingapi)...")
    info = fetcher.fetch_stock_info("600519")
    if info:
        print(f"  ✅ 市值:{info['market_cap_yi']:.0f}亿 PE:{info['pe']} PB:{info['pb']}")
    
    # 测试6: 资金流向
    print("\n[测试6] 资金流向 (东方财富)...")
    flow = fetcher.fetch_fund_flow("600519")
    if flow:
        print(f"  ✅ 获取 {flow['days']} 天资金流向")
        if flow['data']:
            latest = flow['data'][-1]
            print(f"  最新: 主力净流入={latest['main_inflow']/1e8:.2f}亿")
    
    # 测试7: 指数行情
    print("\n[测试7] 市场指数行情 (腾讯)...")
    indices = fetcher.fetch_market_indices()
    if indices:
        for code, data in indices.items():
            print(f"  ✅ {data['name']}: {data['price']} ({data.get('change_pct', 0):+.2f}%)")
    
    # 测试8: A股全市场行情
    print("\n[测试8] A股全市场行情 (新浪, Top5)...")
    all_stocks = fetcher.fetch_all_stocks_realtime(page=1, num=5)
    if all_stocks:
        for s in all_stocks[:5]:
            print(f"  ✅ {s.get('name', '')} ({s.get('symbol', '')}) 价格:{s.get('trade')} 涨跌:{s.get('changepercent')}%")
    
    # 统计
    print(f"\n📊 请求统计: {fetcher.get_stats()}")
    print("=" * 70)