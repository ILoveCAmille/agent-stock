"""
市场情绪分析技能
提供市场情绪指标分析
"""

import logging
from typing import Dict, List, Optional
import numpy as np
from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class MarketSentimentSkill(BaseSkill):
    """市场情绪分析技能"""
    
    def __init__(self):
        super().__init__()
    
    def get_market_sentiment(self) -> Dict:
        """获取市场情绪数据"""
        sentiment = {
            'advance_decline': self._get_advance_decline(),
            'limit_stats': self._get_limit_stats(),
            'turnover': self._get_turnover_stats(),
            'volatility': self._get_volatility()
        }
        return sentiment
    
    def _get_advance_decline(self) -> Dict:
        """获取涨跌家数"""
        result = {'up': 0, 'down': 0, 'flat': 0, 'ratio': 1}
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                pct = df['涨跌幅'].dropna()
                result['up'] = len(pct[pct > 0])
                result['down'] = len(pct[pct < 0])
                result['flat'] = len(pct[pct == 0])
                if result['down'] > 0:
                    result['ratio'] = result['up'] / result['down']
        except Exception as e:
            logger.error(f"获取涨跌家数失败: {e}")
        return result
    
    def _get_limit_stats(self) -> Dict:
        """获取涨跌停统计"""
        result = {'limit_up': 0, 'limit_down': 0}
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                pct = df['涨跌幅'].dropna()
                result['limit_up'] = len(pct[pct >= 9.8])
                result['limit_down'] = len(pct[pct <= -9.8])
        except Exception as e:
            logger.error(f"获取涨跌停统计失败: {e}")
        return result
    
    def _get_turnover_stats(self) -> Dict:
        """获取换手率统计"""
        result = {'avg_turnover': 0, 'high_turnover_count': 0}
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                turnover = df['换手率'].dropna()
                result['avg_turnover'] = turnover.mean()
                result['high_turnover_count'] = len(turnover[turnover > 10])
        except Exception as e:
            logger.error(f"获取换手率统计失败: {e}")
        return result
    
    def _get_volatility(self) -> Dict:
        """获取波动率"""
        result = {'avg_amplitude': 0}
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                amplitude = df['振幅'].dropna()
                result['avg_amplitude'] = amplitude.mean()
        except Exception as e:
            logger.error(f"获取波动率失败: {e}")
        return result
    
    def calculate_sentiment_score(self, sentiment_data: Dict) -> float:
        """计算情绪得分 (0-100)"""
        score = 50
        
        try:
            # 涨跌比得分
            ad = sentiment_data.get('advance_decline', {})
            ratio = ad.get('ratio', 1)
            if ratio > 2:
                score += 15
            elif ratio > 1.5:
                score += 10
            elif ratio < 0.5:
                score -= 15
            elif ratio < 0.67:
                score -= 10
            
            # 涨跌停得分
            limits = sentiment_data.get('limit_stats', {})
            limit_up = limits.get('limit_up', 0)
            limit_down = limits.get('limit_down', 0)
            
            if limit_up > 50:
                score += 10
            elif limit_up > 20:
                score += 5
            
            if limit_down > 50:
                score -= 10
            elif limit_down > 20:
                score -= 5
            
            # 波动率得分
            volatility = sentiment_data.get('volatility', {})
            amplitude = volatility.get('avg_amplitude', 0)
            if amplitude > 5:
                score += 5  # 高波动可能意味着机会
            
        except Exception as e:
            logger.error(f"计算情绪得分失败: {e}")
        
        return max(0, min(100, score))
    
    def analyze_market_mood(self, score: float) -> Dict:
        """分析市场情绪"""
        mood = {
            'level': 'neutral',
            'description': '',
            'suggestion': ''
        }
        
        if score >= 80:
            mood['level'] = 'extreme_greed'
            mood['description'] = '市场极度贪婪'
            mood['suggestion'] = '注意回调风险，考虑获利了结'
        elif score >= 65:
            mood['level'] = 'greed'
            mood['description'] = '市场情绪偏贪婪'
            mood['suggestion'] = '保持警惕，控制仓位'
        elif score >= 45:
            mood['level'] = 'neutral'
            mood['description'] = '市场情绪中性'
            mood['suggestion'] = '正常操作，精选个股'
        elif score >= 30:
            mood['level'] = 'fear'
            mood['description'] = '市场情绪偏恐惧'
            mood['suggestion'] = '可能是机会，关注超跌反弹'
        else:
            mood['level'] = 'extreme_fear'
            mood['description'] = '市场极度恐惧'
            mood['suggestion'] = '可能是底部区域，分批建仓'
        
        return mood
    
    def get_skill_description(self) -> str:
        """获取技能描述"""
        return """
【市场情绪分析技能】
- 获取涨跌家数和涨跌停统计
- 计算情绪得分（0-100）
- 分析市场情绪（贪婪/恐惧）
- 提供情绪驱动的交易建议
"""
