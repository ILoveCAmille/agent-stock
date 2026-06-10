"""
资金流向分析技能
提供主力资金和北向资金分析
"""

import logging
from typing import Dict, List, Optional
import pandas as pd
from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class FundFlowSkill(BaseSkill):
    """资金流向分析技能"""
    
    def __init__(self):
        super().__init__()
    
    def get_stock_fund_flow(self, stock_code: str) -> Dict:
        """获取个股资金流向"""
        result = {
            'main_net': 0,
            'super_large_net': 0,
            'large_net': 0,
            'medium_net': 0,
            'small_net': 0,
            'history': []
        }
        
        try:
            import akshare as ak
            market = "sh" if stock_code.startswith("6") else "sz"
            df = ak.stock_individual_fund_flow(stock=stock_code, market=market)
            
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                result['main_net'] = latest.get('主力净流入-净额', 0)
                result['super_large_net'] = latest.get('超大单净流入-净额', 0)
                result['large_net'] = latest.get('大单净流入-净额', 0)
                result['medium_net'] = latest.get('中单净流入-净额', 0)
                result['small_net'] = latest.get('小单净流入-净额', 0)
                
                # 近5日历史
                for _, row in df.tail(5).iterrows():
                    result['history'].append({
                        'date': row.get('日期', ''),
                        'main_net': row.get('主力净流入-净额', 0),
                        'main_pct': row.get('主力净流入-净占比', 0)
                    })
        except Exception as e:
            logger.error(f"获取个股资金流向失败: {e}")
        
        return result
    
    def get_market_fund_flow(self) -> Dict:
        """获取大盘资金流向"""
        result = {
            'main_net': 0,
            'history': []
        }
        
        try:
            import akshare as ak
            df = ak.stock_market_fund_flow()
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                result['main_net'] = latest.get('主力净流入-净额', 0)
                
                for _, row in df.tail(5).iterrows():
                    result['history'].append({
                        'date': row.get('日期', ''),
                        'main_net': row.get('主力净流入-净额', 0)
                    })
        except Exception as e:
            logger.error(f"获取大盘资金流向失败: {e}")
        
        return result
    
    def get_north_fund_flow(self) -> Dict:
        """获取北向资金流向"""
        result = {
            'net_flow': 0,
            'history': []
        }
        
        try:
            import akshare as ak
            df = ak.stock_hsgt_north_net_flow_in_em(symbol="北向")
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                result['net_flow'] = latest.get('当日净流入', 0)
                
                for _, row in df.tail(5).iterrows():
                    result['history'].append({
                        'date': row.get('日期', ''),
                        'net_flow': row.get('当日净流入', 0)
                    })
        except Exception as e:
            logger.error(f"获取北向资金流向失败: {e}")
        
        return result
    
    def analyze_fund_flow(self, fund_data: Dict) -> Dict:
        """分析资金流向"""
        analysis = {
            'trend': 'neutral',
            'main_behavior': 'unknown',
            'details': []
        }
        
        try:
            main_net = fund_data.get('main_net', 0)
            history = fund_data.get('history', [])
            
            # 主力资金分析
            if main_net > 0:
                analysis['details'].append(f'主力净流入{self.format_number(main_net)}')
                if main_net > 1e8:
                    analysis['main_behavior'] = 'strong_buy'
                    analysis['details'].append('主力大幅买入')
                else:
                    analysis['main_behavior'] = 'buy'
            else:
                analysis['details'].append(f'主力净流出{self.format_number(abs(main_net))}')
                if abs(main_net) > 1e8:
                    analysis['main_behavior'] = 'strong_sell'
                    analysis['details'].append('主力大幅卖出')
                else:
                    analysis['main_behavior'] = 'sell'
            
            # 趋势分析
            if len(history) >= 3:
                recent_flows = [h['main_net'] for h in history[-3:]]
                if all(f > 0 for f in recent_flows):
                    analysis['trend'] = 'continuous_inflow'
                    analysis['details'].append('连续3日主力净流入')
                elif all(f < 0 for f in recent_flows):
                    analysis['trend'] = 'continuous_outflow'
                    analysis['details'].append('连续3日主力净流出')
                    
        except Exception as e:
            logger.error(f"分析资金流向失败: {e}")
        
        return analysis
    
    def get_skill_description(self) -> str:
        """获取技能描述"""
        return """
【资金流向分析技能】
- 获取个股资金流向（主力、大单、中单、小单）
- 获取大盘资金流向
- 获取北向资金流向
- 分析资金趋势和主力行为
"""
