"""
风险评估技能
提供全面的风险识别和评估
"""

import logging
from typing import Dict, List, Optional
from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class RiskAssessmentSkill(BaseSkill):
    """风险评估技能"""
    
    def __init__(self):
        super().__init__()
    
    def get_risk_data(self, stock_code: str) -> Dict:
        """获取风险数据"""
        risk_data = {
            'lifting_ban': self._get_lifting_ban(stock_code),
            'pledge': self._get_pledge_info(stock_code),
            'lawsuit': self._get_lawsuit_info(stock_code),
            'audit_opinion': self._get_audit_opinion(stock_code)
        }
        return risk_data
    
    def _get_lifting_ban(self, stock_code: str) -> Dict:
        """获取限售解禁数据"""
        result = {'has_data': False, 'details': []}
        try:
            import akshare as ak
            df = ak.stock_restricted_release_detail_em(symbol=stock_code)
            if df is not None and not df.empty:
                result['has_data'] = True
                for _, row in df.head(3).iterrows():
                    result['details'].append({
                        'date': row.get('解禁日期', ''),
                        'shares': row.get('解禁股数', ''),
                        'amount': row.get('解禁市值', '')
                    })
        except Exception as e:
            logger.error(f"获取限售解禁数据失败: {e}")
        return result
    
    def _get_pledge_info(self, stock_code: str) -> Dict:
        """获取股权质押数据"""
        result = {'has_data': False, 'pledge_ratio': 0}
        try:
            import akshare as ak
            df = ak.stock_pledge_stat_em()
            if df is not None and not df.empty:
                stock = df[df['证券代码'] == stock_code]
                if not stock.empty:
                    result['has_data'] = True
                    result['pledge_ratio'] = stock.iloc[0].get('质押比例', 0)
        except Exception as e:
            logger.error(f"获取股权质押数据失败: {e}")
        return result
    
    def _get_lawsuit_info(self, stock_code: str) -> Dict:
        """获取诉讼信息"""
        return {'has_data': False, 'details': []}
    
    def _get_audit_opinion(self, stock_code: str) -> Dict:
        """获取审计意见"""
        return {'has_data': False, 'opinion': 'unknown'}
    
    def assess_risk_level(self, risk_data: Dict, indicators: Dict) -> Dict:
        """评估风险水平"""
        assessment = {
            'level': 'medium',
            'score': 50,
            'warnings': [],
            'details': []
        }
        
        try:
            score = 50
            
            # 限售解禁风险
            lifting_ban = risk_data.get('lifting_ban', {})
            if lifting_ban.get('has_data'):
                score += 10
                assessment['warnings'].append('存在限售解禁')
                assessment['details'].append('近期有解禁股票')
            
            # 股权质押风险
            pledge = risk_data.get('pledge', {})
            pledge_ratio = pledge.get('pledge_ratio', 0)
            if pledge_ratio > 50:
                score += 15
                assessment['warnings'].append(f'质押比例过高({pledge_ratio}%)')
            elif pledge_ratio > 30:
                score += 10
                assessment['warnings'].append(f'质押比例偏高({pledge_ratio}%)')
            
            # 波动率风险
            rsi = indicators.get('rsi14', 50)
            if rsi > 80 or rsi < 20:
                score += 10
                assessment['warnings'].append(f'RSI极端({rsi:.1f})')
            
            # 估值风险
            pe = indicators.get('pe', 0)
            if pe and pe > 100:
                score += 15
                assessment['warnings'].append(f'估值过高(PE={pe:.1f})')
            
            # 确定风险等级
            assessment['score'] = min(100, max(0, score))
            
            if score >= 70:
                assessment['level'] = 'high'
            elif score >= 50:
                assessment['level'] = 'medium'
            else:
                assessment['level'] = 'low'
                
        except Exception as e:
            logger.error(f"评估风险水平失败: {e}")
        
        return assessment
    
    def get_skill_description(self) -> str:
        """获取技能描述"""
        return """
【风险评估技能】
- 获取限售解禁数据
- 获取股权质押信息
- 评估风险水平和等级
- 生成风险预警
"""
