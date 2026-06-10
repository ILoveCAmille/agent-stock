"""
全市场数据源集成模块
整合多个免费数据源，提供统一的全市场数据获取接口
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import logging
import requests
import json
from functools import lru_cache

logger = logging.getLogger(__name__)


class FullMarketDataSource:
    """全市场数据源管理器"""
    
    # 数据源优先级配置
    DATA_SOURCE_PRIORITY = {
        'realtime': ['eastmoney', 'sina', 'tencent'],
        'history': ['eastmoney', 'sina', 'tencent', 'tushare'],
        'financial': ['eastmoney', 'sina', 'tushare'],
        'index': ['eastmoney', 'sina'],
        'sector': ['eastmoney', 'ths'],
    }
    
    def __init__(self):
        self._cache = {}
        self._cache_ttl = 300  # 5分钟缓存
        self._health_status = {}
        
    # ==================== 实时行情数据 ====================
    
    def get_all_a_stock_realtime(self) -> Optional[pd.DataFrame]:
        """获取全A股实时行情（东方财富）
        
        Returns:
            DataFrame: 包含所有A股的实时行情数据
            列: 代码, 名称, 最新价, 涨跌幅, 涨跌额, 成交量, 成交额, 振幅, 
                最高, 最低, 今开, 昨收, 量比, 换手率, 市盈率-动态, 市净率, 
                总市值, 流通市值, 涨速, 5分钟涨跌, 60日涨跌幅, 年初至今涨跌幅
        """
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                logger.info(f"获取全A股实时行情成功: {len(df)}只股票")
                return df
        except Exception as e:
            logger.error(f"东财获取全A股行情失败: {e}")
        
        # 备用：新浪
        try:
            df = ak.stock_zh_a_spot()
            if df is not None and not df.empty:
                logger.info(f"新浪获取全A股行情成功: {len(df)}只股票")
                return df
        except Exception as e:
            logger.error(f"新浪获取全A股行情失败: {e}")
        
        return None
    
    def get_sh_a_stock_realtime(self) -> Optional[pd.DataFrame]:
        """获取沪A股实时行情"""
        try:
            return ak.stock_sh_a_spot_em()
        except Exception as e:
            logger.error(f"获取沪A股行情失败: {e}")
            return None
    
    def get_sz_a_stock_realtime(self) -> Optional[pd.DataFrame]:
        """获取深A股实时行情"""
        try:
            return ak.stock_sz_a_spot_em()
        except Exception as e:
            logger.error(f"获取深A股行情失败: {e}")
            return None
    
    def get_bj_a_stock_realtime(self) -> Optional[pd.DataFrame]:
        """获取京A股实时行情"""
        try:
            return ak.stock_bj_a_spot_em()
        except Exception as e:
            logger.error(f"获取京A股行情失败: {e}")
            return None
    
    def get_stock_realtime_quote(self, symbol: str) -> Optional[Dict]:
        """获取单只股票实时行情"""
        try:
            df = ak.stock_bid_ask_em(symbol=symbol)
            if df is not None and not df.empty:
                result = {}
                for _, row in df.iterrows():
                    result[row['item']] = row['value']
                return result
        except Exception as e:
            logger.error(f"获取{symbol}行情失败: {e}")
        return None
    
    # ==================== 历史行情数据 ====================
    
    def get_stock_history(self, symbol: str, period: str = "daily",
                          start_date: str = None, end_date: str = None,
                          adjust: str = "qfq") -> Optional[pd.DataFrame]:
        """获取股票历史行情数据
        
        Args:
            symbol: 股票代码，如 "000001"
            period: 周期，daily/weekly/monthly
            start_date: 开始日期，格式 YYYYMMDD
            end_date: 结束日期，格式 YYYYMMDD
            adjust: 复权类型，qfq前复权/hfq后复权/""不复权
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        
        # 东财数据源
        try:
            df = ak.stock_zh_a_hist(symbol=symbol, period=period,
                                     start_date=start_date, end_date=end_date,
                                     adjust=adjust)
            if df is not None and not df.empty:
                df = self._standardize_history_columns(df)
                return df
        except Exception as e:
            logger.error(f"东财获取{symbol}历史数据失败: {e}")
        
        # 新浪数据源
        try:
            market = "sh" if symbol.startswith("6") else "sz"
            df = ak.stock_zh_index_daily(symbol=f"{market}{symbol}")
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"新浪获取{symbol}历史数据失败: {e}")
        
        return None
    
    def _standardize_history_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化历史数据列名"""
        column_mapping = {
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume',
            '成交额': 'amount', '振幅': 'amplitude', '涨跌幅': 'pct_change',
            '涨跌额': 'change', '换手率': 'turnover'
        }
        df = df.rename(columns=column_mapping)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        return df
    
    # ==================== 指数数据 ====================
    
    def get_all_index_realtime(self, symbol: str = "沪深重要指数") -> Optional[pd.DataFrame]:
        """获取所有指数实时行情
        
        Args:
            symbol: 指数类别，可选 "沪深重要指数", "上证系列指数", "深证系列指数", "中证系列指数"
        """
        try:
            df = ak.stock_zh_index_spot_em(symbol=symbol)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取指数行情失败: {e}")
        
        # 备用：新浪
        try:
            df = ak.stock_zh_index_spot_sina()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"新浪获取指数行情失败: {e}")
        
        return None
    
    def get_index_history(self, symbol: str, period: str = "daily",
                          start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        """获取指数历史数据"""
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        
        try:
            df = ak.index_zh_a_hist(symbol=symbol, period=period,
                                     start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                df = self._standardize_history_columns(df)
                return df
        except Exception as e:
            logger.error(f"获取指数{symbol}历史数据失败: {e}")
        
        return None
    
    # ==================== 板块数据 ====================
    
    def get_sector_realtime(self, sector_type: str = "行业") -> Optional[pd.DataFrame]:
        """获取板块实时行情
        
        Args:
            sector_type: 板块类型，"行业" 或 "概念"
        """
        try:
            if sector_type == "行业":
                df = ak.stock_board_industry_name_em()
            else:
                df = ak.stock_board_concept_name_em()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取{sector_type}板块行情失败: {e}")
        return None
    
    def get_sector_stocks(self, sector_name: str, sector_type: str = "行业") -> Optional[pd.DataFrame]:
        """获取板块成份股"""
        try:
            if sector_type == "行业":
                df = ak.stock_board_industry_cons_em(symbol=sector_name)
            else:
                df = ak.stock_board_concept_cons_em(symbol=sector_name)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取{sector_name}成份股失败: {e}")
        return None
    
    # ==================== 资金流向数据 ====================
    
    def get_stock_fund_flow(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取个股资金流向"""
        try:
            df = ak.stock_individual_fund_flow(stock=symbol, market="sh" if symbol.startswith("6") else "sz")
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取{symbol}资金流向失败: {e}")
        return None
    
    def get_market_fund_flow(self) -> Optional[pd.DataFrame]:
        """获取大盘资金流向"""
        try:
            df = ak.stock_market_fund_flow()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取大盘资金流向失败: {e}")
        return None
    
    def get_sector_fund_flow(self, sector_type: str = "行业") -> Optional[pd.DataFrame]:
        """获取板块资金流向"""
        try:
            if sector_type == "行业":
                df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
            else:
                df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="概念资金流")
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取{sector_type}资金流向失败: {e}")
        return None
    
    # ==================== 财务数据 ====================
    
    def get_stock_financial(self, symbol: str) -> Optional[Dict]:
        """获取股票财务数据"""
        result = {}
        
        # 基本信息
        try:
            info = ak.stock_individual_info_em(symbol=symbol)
            if info is not None and not info.empty:
                result['basic_info'] = info
        except Exception as e:
            logger.error(f"获取{symbol}基本信息失败: {e}")
        
        # 财务指标
        try:
            indicators = ak.stock_financial_analysis_indicator(symbol=symbol)
            if indicators is not None and not indicators.empty:
                result['financial_indicators'] = indicators
        except Exception as e:
            logger.error(f"获取{symbol}财务指标失败: {e}")
        
        return result if result else None
    
    # ==================== 龙虎榜数据 ====================
    
    def get_longhubang_data(self, date: str = None) -> Optional[pd.DataFrame]:
        """获取龙虎榜数据"""
        if not date:
            date = datetime.now().strftime('%Y%m%d')
        
        try:
            df = ak.stock_lhb_detail_em(start_date=date, end_date=date)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取龙虎榜数据失败: {e}")
        return None
    
    # ==================== 涨跌停数据 ====================
    
    def get_limit_up_stocks(self, date: str = None) -> Optional[pd.DataFrame]:
        """获取涨停股票池"""
        if not date:
            date = datetime.now().strftime('%Y%m%d')
        
        try:
            df = ak.stock_zt_pool_em(date=date)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取涨停股票失败: {e}")
        return None
    
    def get_limit_down_stocks(self, date: str = None) -> Optional[pd.DataFrame]:
        """获取跌停股票池"""
        if not date:
            date = datetime.now().strftime('%Y%m%d')
        
        try:
            df = ak.stock_zt_pool_dtgc_em(date=date)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取跌停股票失败: {e}")
        return None
    
    # ==================== 融资融券数据 ====================
    
    def get_margin_data(self, date: str = None) -> Optional[pd.DataFrame]:
        """获取融资融券数据"""
        try:
            df = ak.stock_margin_sse(start_date=date, end_date=date)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取融资融券数据失败: {e}")
        return None
    
    # ==================== 北向资金数据 ====================
    
    def get_north_fund_flow(self) -> Optional[pd.DataFrame]:
        """获取北向资金流向"""
        try:
            df = ak.stock_hsgt_north_net_flow_in_em(symbol="北向")
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取北向资金失败: {e}")
        return None
    
    # ==================== 股票列表 ====================
    
    def get_stock_list(self, market: str = "all") -> Optional[pd.DataFrame]:
        """获取股票列表
        
        Args:
            market: 市场，all/sh/sz/bj
        """
        try:
            if market == "all":
                df = ak.stock_info_a_code_name()
            elif market == "sh":
                df = ak.stock_info_sh_name_code()
            elif market == "sz":
                df = ak.stock_info_sz_name_code()
            elif market == "bj":
                df = ak.stock_info_bj_name_code()
            else:
                df = ak.stock_info_a_code_name()
            
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取{market}股票列表失败: {e}")
        return None
    
    # ==================== 市场统计数据 ====================
    
    def get_market_statistics(self) -> Dict:
        """获取市场统计数据"""
        stats = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'sse_summary': None,
            'szse_summary': None,
            'total_stocks': 0,
            'up_count': 0,
            'down_count': 0,
            'flat_count': 0,
            'limit_up': 0,
            'limit_down': 0,
        }
        
        # 上交所统计
        try:
            sse = ak.stock_sse_summary()
            if sse is not None and not sse.empty:
                stats['sse_summary'] = sse
        except Exception as e:
            logger.error(f"获取上交所统计失败: {e}")
        
        # 深交所统计
        try:
            szse = ak.stock_szse_summary(date=datetime.now().strftime('%Y%m%d'))
            if szse is not None and not szse.empty:
                stats['szse_summary'] = szse
        except Exception as e:
            logger.error(f"获取深交所统计失败: {e}")
        
        # 涨跌统计
        try:
            df = self.get_all_a_stock_realtime()
            if df is not None and not df.empty:
                stats['total_stocks'] = len(df)
                pct_change = df['涨跌幅'].dropna()
                stats['up_count'] = len(pct_change[pct_change > 0])
                stats['down_count'] = len(pct_change[pct_change < 0])
                stats['flat_count'] = len(pct_change[pct_change == 0])
                stats['limit_up'] = len(pct_change[pct_change >= 9.8])
                stats['limit_down'] = len(pct_change[pct_change <= -9.8])
        except Exception as e:
            logger.error(f"获取涨跌统计失败: {e}")
        
        return stats
    
    # ==================== 数据源健康检查 ====================
    
    def check_data_source_health(self) -> Dict:
        """检查数据源健康状态"""
        health = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'sources': {},
        }
        
        # 检查东财
        try:
            df = ak.stock_zh_a_spot_em()
            health['sources']['eastmoney'] = {
                'status': 'ok' if df is not None and not df.empty else 'error',
                'records': len(df) if df is not None else 0,
            }
        except Exception as e:
            health['sources']['eastmoney'] = {'status': 'error', 'error': str(e)}
        
        # 检查新浪
        try:
            df = ak.stock_zh_index_spot_sina()
            health['sources']['sina'] = {
                'status': 'ok' if df is not None and not df.empty else 'error',
                'records': len(df) if df is not None else 0,
            }
        except Exception as e:
            health['sources']['sina'] = {'status': 'error', 'error': str(e)}
        
        # 检查AKShare版本
        health['akshare_version'] = ak.__version__
        
        return health
    
    # ==================== 批量数据获取 ====================
    
    def batch_get_stock_info(self, symbols: List[str], max_workers: int = 5) -> Dict[str, Dict]:
        """批量获取股票信息"""
        results = {}
        
        for symbol in symbols:
            try:
                info = ak.stock_individual_info_em(symbol=symbol)
                if info is not None and not info.empty:
                    results[symbol] = info.to_dict('records')
            except Exception as e:
                logger.error(f"获取{symbol}信息失败: {e}")
                results[symbol] = {'error': str(e)}
        
        return results
    
    # ==================== 搜索功能 ====================
    
    def search_stock(self, keyword: str) -> Optional[List[Dict]]:
        """搜索股票"""
        try:
            df = ak.stock_info_a_code_name()
            if df is not None and not df.empty:
                # 按代码或名称搜索
                mask = df['code'].str.contains(keyword) | df['name'].str.contains(keyword)
                result = df[mask].head(20)
                return result.to_dict('records')
        except Exception as e:
            logger.error(f"搜索股票失败: {e}")
        return None


# 创建全局实例
full_market_data = FullMarketDataSource()
