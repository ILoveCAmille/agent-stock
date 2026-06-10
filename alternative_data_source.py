"""
备用数据源模块
当东财API不可用时，使用新浪/腾讯API获取数据
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class AlternativeDataSource:
    """备用数据源"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False
    
    def get_stock_realtime(self, symbol: str) -> Optional[Dict]:
        """获取股票实时行情（新浪）"""
        try:
            market = "sh" if symbol.startswith("6") else "sz"
            url = f"https://hq.sinajs.cn/list={market}{symbol}"
            headers = {'Referer': 'https://finance.sina.com.cn'}
            
            r = self.session.get(url, headers=headers, timeout=10)
            content = r.text
            
            if '="' in content:
                data = content.split('"')[1].split(',')
                if len(data) > 30:
                    return {
                        'name': data[0],
                        'open': float(data[1]),
                        'prev_close': float(data[2]),
                        'latest': float(data[3]),
                        'high': float(data[4]),
                        'low': float(data[5]),
                        'volume': float(data[8]),
                        'amount': float(data[9]),
                        'date': data[30],
                        'time': data[31],
                    }
        except Exception as e:
            logger.error(f"Sina realtime failed for {symbol}: {e}")
        return None
    
    def get_stock_history_sina(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """获取股票历史数据（新浪）"""
        try:
            market = "sh" if symbol.startswith("6") else "sz"
            url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {
                'symbol': f"{market}{symbol}",
                'scale': '240',  # 日线
                'ma': 'no',
                'datalen': str(days)
            }
            headers = {'Referer': 'https://finance.sina.com.cn'}
            
            r = self.session.get(url, params=params, headers=headers, timeout=10)
            data = r.json()
            
            if data and len(data) > 0:
                df = pd.DataFrame(data)
                df['day'] = pd.to_datetime(df['day'])
                df = df.rename(columns={'day': 'date'})
                return df
        except Exception as e:
            logger.error(f"Sina history failed for {symbol}: {e}")
        return None
    
    def get_stock_info_sina(self, symbol: str) -> Optional[Dict]:
        """获取股票基本信息（新浪）"""
        realtime = self.get_stock_realtime(symbol)
        if realtime:
            return {
                'symbol': symbol,
                'name': realtime['name'],
                'current_price': realtime['latest'],
                'change_percent': ((realtime['latest'] - realtime['prev_close']) / realtime['prev_close'] * 100) if realtime['prev_close'] > 0 else 0,
                'open': realtime['open'],
                'high': realtime['high'],
                'low': realtime['low'],
                'prev_close': realtime['prev_close'],
                'volume': realtime['volume'],
                'amount': realtime['amount'],
            }
        return None
    
    def get_index_realtime(self, index_code: str) -> Optional[Dict]:
        """获取指数实时行情"""
        try:
            market = "sh" if index_code.startswith("0000") else "sz"
            url = f"https://hq.sinajs.cn/list={market}{index_code}"
            headers = {'Referer': 'https://finance.sina.com.cn'}
            
            r = self.session.get(url, headers=headers, timeout=10)
            content = r.text
            
            if '="' in content:
                data = content.split('"')[1].split(',')
                if len(data) > 30:
                    return {
                        'name': data[0],
                        'open': float(data[1]),
                        'prev_close': float(data[2]),
                        'latest': float(data[3]),
                        'high': float(data[4]),
                        'low': float(data[5]),
                        'volume': float(data[8]),
                        'amount': float(data[9]),
                    }
        except Exception as e:
            logger.error(f"Sina index failed for {index_code}: {e}")
        return None
    
    def batch_get_realtime(self, symbols: list) -> Dict[str, Dict]:
        """批量获取实时行情"""
        results = {}
        
        # 构建批量请求
        market_symbols = []
        for symbol in symbols:
            market = "sh" if symbol.startswith("6") else "sz"
            market_symbols.append(f"{market}{symbol}")
        
        try:
            url = f"https://hq.sinajs.cn/list={','.join(market_symbols)}"
            headers = {'Referer': 'https://finance.sina.com.cn'}
            
            r = self.session.get(url, headers=headers, timeout=15)
            content = r.text
            
            for line in content.strip().split('\n'):
                if '="' in line:
                    parts = line.split('=')
                    code_part = parts[0].split('_')[-1]
                    symbol = code_part[2:]  # Remove sh/sz prefix
                    
                    data = parts[1].strip('"').split(',')
                    if len(data) > 30:
                        results[symbol] = {
                            'name': data[0],
                            'latest': float(data[3]),
                            'prev_close': float(data[2]),
                            'change_percent': ((float(data[3]) - float(data[2])) / float(data[2]) * 100) if float(data[2]) > 0 else 0,
                            'volume': float(data[8]),
                            'amount': float(data[9]),
                        }
        except Exception as e:
            logger.error(f"Batch get failed: {e}")
        
        return results


# 创建全局实例
alt_data_source = AlternativeDataSource()
