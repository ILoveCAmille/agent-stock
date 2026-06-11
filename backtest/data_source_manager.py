"""
数据源管理器
管理多个数据源，支持缓存和自动切换
"""

import os
import requests
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import json

# Clear proxy
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

logger = logging.getLogger(__name__)


class DataSourceManager:
    """数据源管理器"""
    
    def __init__(self, cache_dir: str = None):
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn'
        })
        
        # 缓存目录
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(__file__), '.cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 内存缓存
        self._memory_cache = {}
        self._cache_ttl = 3600  # 1小时
    
    def get_stock_list(self) -> pd.DataFrame:
        """获取A股股票列表"""
        cache_key = 'stock_list'
        
        # 检查缓存
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            import akshare as ak
            
            # 绕过代理
            old_get = requests.get
            def patched_get(*args, **kwargs):
                kwargs.setdefault('proxies', {'http': None, 'https': None})
                return old_get(*args, **kwargs)
            requests.get = patched_get
            
            try:
                df = ak.stock_info_a_code_name()
            finally:
                requests.get = old_get
            
            if df is not None and not df.empty:
                self._save_to_cache(cache_key, df)
                return df
                
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
        
        return pd.DataFrame()
    
    def get_stock_history(self, code: str, start_date: str = None, end_date: str = None,
                          days: int = 252) -> pd.DataFrame:
        """获取股票历史数据"""
        cache_key = f'history_{code}_{start_date}_{end_date}_{days}'
        
        # 检查缓存
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        # 计算日期
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # 尝试新浪API
        df = self._get_history_from_sina(code, days)
        
        if df is not None and not df.empty:
            self._save_to_cache(cache_key, df)
            return df
        
        # 尝试AKShare
        df = self._get_history_from_akshare(code, start_date, end_date)
        
        if df is not None and not df.empty:
            self._save_to_cache(cache_key, df)
            return df
        
        return pd.DataFrame()
    
    def _get_history_from_sina(self, code: str, days: int = 252) -> Optional[pd.DataFrame]:
        """从新浪获取历史数据"""
        try:
            market = "sh" if code.startswith("6") else "sz"
            url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {
                'symbol': f"{market}{code}",
                'scale': '240',
                'ma': 'no',
                'datalen': str(days)
            }
            
            r = self.session.get(url, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data:
                    df = pd.DataFrame(data)
                    df['day'] = pd.to_datetime(df['day'])
                    df = df.rename(columns={'day': 'date'})
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    return df
        except Exception as e:
            logger.error(f"新浪获取{code}失败: {e}")
        
        return None
    
    def _get_history_from_akshare(self, code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """从AKShare获取历史数据"""
        try:
            import akshare as ak
            
            # 绕过代理
            old_get = requests.get
            def patched_get(*args, **kwargs):
                kwargs.setdefault('proxies', {'http': None, 'https': None})
                return old_get(*args, **kwargs)
            requests.get = patched_get
            
            try:
                start = start_date.replace('-', '')
                end = end_date.replace('-', '')
                
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start,
                    end_date=end,
                    adjust="qfq"
                )
            finally:
                requests.get = old_get
            
            if df is not None and not df.empty:
                df = df.rename(columns={
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount',
                })
                df['date'] = pd.to_datetime(df['date'])
                return df
                
        except Exception as e:
            logger.error(f"AKShare获取{code}失败: {e}")
        
        return None
    
    def get_multiple_stocks(self, codes: List[str], start_date: str = None, 
                           end_date: str = None, days: int = 252) -> Dict[str, pd.DataFrame]:
        """批量获取股票数据"""
        result = {}
        
        for code in codes:
            df = self.get_stock_history(code, start_date, end_date, days)
            if df is not None and not df.empty:
                result[code] = df
            else:
                logger.warning(f"Failed to get data for {code}")
        
        return result
    
    def get_index_data(self, index_code: str, days: int = 252) -> pd.DataFrame:
        """获取指数数据"""
        cache_key = f'index_{index_code}_{days}'
        
        # 检查缓存
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            market = "sh" if index_code.startswith("0000") else "sz"
            url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {
                'symbol': f"{market}{index_code}",
                'scale': '240',
                'ma': 'no',
                'datalen': str(days)
            }
            
            r = self.session.get(url, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data:
                    df = pd.DataFrame(data)
                    df['day'] = pd.to_datetime(df['day'])
                    df = df.rename(columns={'day': 'date'})
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    self._save_to_cache(cache_key, df)
                    return df
        except Exception as e:
            logger.error(f"获取指数{index_code}失败: {e}")
        
        return pd.DataFrame()
    
    def get_sector_data(self, sector_name: str) -> List[Dict]:
        """获取板块股票列表"""
        # 预设板块股票
        sector_stocks = {
            '半导体': ['002371', '688981', '603986', '688008', '688012'],
            '人工智能': ['002230', '688787', '300496', '688256', '300033'],
            '新能源汽车': ['300750', '002594', '002460', '300014', '300124'],
            '医药生物': ['600276', '300760', '000538', '600196', '002001'],
            '军工': ['600760', '600893', '002049', '600862', '600879'],
            '消费': ['600519', '000858', '000568', '002304', '000596'],
            '金融': ['601318', '600036', '601166', '600016', '601328'],
            '科技': ['002475', '300059', '601012', '002415', '300015'],
        }
        
        codes = sector_stocks.get(sector_name, [])
        
        stocks = []
        for code in codes:
            df = self.get_stock_history(code, days=5)
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                stocks.append({
                    'code': code,
                    'price': latest.get('close', 0),
                })
        
        return stocks
    
    def _get_from_cache(self, key: str) -> Optional[pd.DataFrame]:
        """从缓存获取数据"""
        # 检查内存缓存
        if key in self._memory_cache:
            data, timestamp = self._memory_cache[key]
            if (datetime.now() - timestamp).seconds < self._cache_ttl:
                return data
            else:
                del self._memory_cache[key]
        
        # 检查文件缓存
        cache_file = os.path.join(self.cache_dir, f"{key}.pkl")
        if os.path.exists(cache_file):
            try:
                # 检查文件修改时间
                mtime = os.path.getmtime(cache_file)
                if (datetime.now().timestamp() - mtime) < self._cache_ttl:
                    df = pd.read_pickle(cache_file)
                    self._memory_cache[key] = (df, datetime.now())
                    return df
            except Exception as e:
                logger.error(f"读取缓存失败: {e}")
        
        return None
    
    def _save_to_cache(self, key: str, data: pd.DataFrame):
        """保存到缓存"""
        # 保存到内存
        self._memory_cache[key] = (data, datetime.now())
        
        # 保存到文件
        try:
            cache_file = os.path.join(self.cache_dir, f"{key}.pkl")
            data.to_pickle(cache_file)
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
    
    def clear_cache(self):
        """清空缓存"""
        self._memory_cache.clear()
        
        # 清空文件缓存
        try:
            for file in os.listdir(self.cache_dir):
                if file.endswith('.pkl'):
                    os.remove(os.path.join(self.cache_dir, file))
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")


# 创建全局实例
data_source_manager = DataSourceManager()
