"""
基本面分析技能
提供公司基本面分析能力
"""

import logging
from typing import Dict, List, Optional
from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class FundamentalAnalysisSkill(BaseSkill):
    """基本面分析技能"""
    
    def __init__(self):
        super().__init__()
    
    def get_company_info(self, stock_code: str) -> Dict:
        """获取公司基本信息"""
        info = {}
        try:
            import akshare as ak
            df = ak.stock_individual_info_em(symbol=stock_code)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    key = row['item']
                    value = row['value']
                    if key == '股票简称':
                        info['name'] = value
                    elif key == '总市值':
                        info['market_cap'] = value
                    elif key == '流通市值':
                        info['float_market_cap'] = value
                    elif key == '行业':
                        info['industry'] = value
                    elif key == '上市时间':
                        info['list_date'] = value
        except Exception as e:
            logger.error(f"获取公司信息失败: {e}")
        return info
    
    def get_valuation_metrics(self, stock_code: str) -> Dict:
        """获取估值指标"""
        metrics = {}
        try:
            import akshare as ak
            
            # 获取实时行情（包含PE、PB）
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                stock = df[df['代码'] == stock_code]
                if not stock.empty:
                    row = stock.iloc[0]
                    metrics['pe'] = row.get('市盈率-动态', '')
                    metrics['pb'] = row.get('市净率', '')
                    metrics['total_mv'] = row.get('总市值', '')
                    metrics['float_mv'] = row.get('流通市值', '')
        except Exception as e:
            logger.error(f"获取估值指标失败: {e}")
        return metrics
    
    def analyze_valuation(self, pe: float, pb: float, industry_pe: float = None) -> Dict:
        """分析估值水平"""
        analysis = {
            'pe_level': 'unknown',
            'pb_level': 'unknown',
            'overall': 'unknown',
            'details': []
        }
        
        try:
            # PE分析
            if pe and pe > 0:
                if pe < 15:
                    analysis['pe_level'] = 'low'
                    analysis['details'].append(f'PE={pe:.1f}，估值较低')
                elif pe < 30:
                    analysis['pe_level'] = 'medium'
                    analysis['details'].append(f'PE={pe:.1f}，估值适中')
                elif pe < 50:
                    analysis['pe_level'] = 'high'
                    analysis['details'].append(f'PE={pe:.1f}，估值偏高')
                else:
                    analysis['pe_level'] = 'very_high'
                    analysis['details'].append(f'PE={pe:.1f}，估值很高')
            
            # PB分析
            if pb and pb > 0:
                if pb < 1:
                    analysis['pb_level'] = 'low'
                    analysis['details'].append(f'PB={pb:.2f}，破净')
                elif pb < 2:
                    analysis['pb_level'] = 'medium'
                    analysis['details'].append(f'PB={pb:.2f}，估值适中')
                elif pb < 5:
                    analysis['pb_level'] = 'high'
                    analysis['details'].append(f'PB={pb:.2f}，估值偏高')
                else:
                    analysis['pb_level'] = 'very_high'
                    analysis['details'].append(f'PB={pb:.2f}，估值很高')
            
            # 综合评估
            pe_score = {'low': 4, 'medium': 3, 'high': 2, 'very_high': 1, 'unknown': 0}
            pb_score = {'low': 4, 'medium': 3, 'high': 2, 'very_high': 1, 'unknown': 0}
            
            total = pe_score.get(analysis['pe_level'], 0) + pb_score.get(analysis['pb_level'], 0)
            
            if total >= 7:
                analysis['overall'] = 'undervalued'
            elif total >= 5:
                analysis['overall'] = 'fair'
            elif total >= 3:
                analysis['overall'] = 'overvalued'
            else:
                analysis['overall'] = 'very_overvalued'
                
        except Exception as e:
            logger.error(f"分析估值水平失败: {e}")
        
        return analysis
    
    def get_dividend_history(self, stock_code: str) -> List[Dict]:
        """获取分红历史"""
        dividends = []
        try:
            import akshare as ak
            df = ak.stock_dividend_cninfo(symbol=stock_code)
            if df is not None and not df.empty:
                for _, row in df.head(5).iterrows():
                    dividends.append({
                        'year': row.get('报告期', ''),
                        'dividend': row.get('现金分红-股息(元)', ''),
                        'ex_date': row.get('除权除息日', '')
                    })
        except Exception as e:
            logger.error(f"获取分红历史失败: {e}")
        return dividends
    
    def get_skill_description(self) -> str:
        """获取技能描述"""
        return """
【基本面分析技能】
- 获取公司基本信息和估值指标
- 分析估值水平（PE、PB）
- 获取分红历史
- 行业对比分析
"""
