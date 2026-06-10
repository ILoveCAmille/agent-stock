"""
数据爬取技能
提供基础数据爬取能力
"""

import requests
import json
import logging
import pandas as pd
from typing import Dict, List, Optional
from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class DataScrapingSkill(BaseSkill):
    """数据爬取技能"""
    
    def __init__(self):
        super().__init__()
    
    def get_realtime_quote(self, stock_code: str) -> Optional[Dict]:
        """获取实时行情（新浪）"""
        try:
            market = "sh" if stock_code.startswith("6") else "sz"
            url = f"https://hq.sinajs.cn/list={market}{stock_code}"
            headers = {'Referer': 'https://finance.sina.com.cn'}
            
            response = self._safe_get(url, headers=headers, timeout=10)
            if response:
                content = response.text
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
                            'time': data[31]
                        }
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
        return None
    
    def get_stock_list(self, market: str = 'all') -> pd.DataFrame:
        """获取股票列表"""
        try:
            import akshare as ak
            df = ak.stock_info_a_code_name()
            return df
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return pd.DataFrame()
    
    def get_index_quote(self, index_code: str) -> Optional[Dict]:
        """获取指数行情"""
        try:
            market = "sh" if index_code.startswith("0000") else "sz"
            url = f"https://hq.sinajs.cn/list={market}{index_code}"
            headers = {'Referer': 'https://finance.sina.com.cn'}
            
            response = self._safe_get(url, headers=headers, timeout=10)
            if response:
                content = response.text
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
                            'amount': float(data[9])
                        }
        except Exception as e:
            logger.error(f"获取指数行情失败: {e}")
        return None
    
    def get_market_breadth(self) -> Dict:
        """获取市场宽度（涨跌家数）"""
        result = {
            'up_count': 0,
            'down_count': 0,
            'flat_count': 0,
            'limit_up': 0,
            'limit_down': 0
        }
        
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                pct_change = df['涨跌幅'].dropna()
                result['up_count'] = len(pct_change[pct_change > 0])
                result['down_count'] = len(pct_change[pct_change < 0])
                result['flat_count'] = len(pct_change[pct_change == 0])
                result['limit_up'] = len(pct_change[pct_change >= 9.8])
                result['limit_down'] = len(pct_change[pct_change <= -9.8])
        except Exception as e:
            logger.error(f"获取市场宽度失败: {e}")
        
        return result
    
    def get_sector_data(self, sector_type: str = 'industry') -> pd.DataFrame:
        """获取板块数据"""
        try:
            import akshare as ak
            if sector_type == 'industry':
                df = ak.stock_board_industry_name_em()
            else:
                df = ak.stock_board_concept_name_em()
            return df
        except Exception as e:
            logger.error(f"获取板块数据失败: {e}")
            return pd.DataFrame()
    
    def get_stock_history(self, stock_code: str, days: int = 30) -> pd.DataFrame:
        """获取股票历史数据"""
        try:
            market = "sh" if stock_code.startswith("6") else "sz"
            url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {
                'symbol': f"{market}{stock_code}",
                'scale': '240',
                'ma': 'no',
                'datalen': str(days)
            }
            headers = {'Referer': 'https://finance.sina.com.cn'}
            
            response = self._safe_get(url, params=params, headers=headers, timeout=15)
            if response:
                data = response.json()
                if data:
                    df = pd.DataFrame(data)
                    df['day'] = pd.to_datetime(df['day'])
                    return df
        except Exception as e:
            logger.error(f"获取股票历史数据失败: {e}")
        return pd.DataFrame()
    
    def get_skill_description(self) -> str:
        """获取技能描述"""
        return """
【数据爬取技能】
- 实时行情数据（新浪/腾讯）
- 股票列表和板块数据
- 指数行情数据
- 市场宽度统计（涨跌家数）
- 历史K线数据
"""
