"""
市场状态识别器
识别当前市场状态（牛市/熊市/震荡）
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MarketStateIdentifier:
    """市场状态识别器"""
    
    # 市场状态定义
    STATES = {
        'strong_bull': {'name': '强势牛市', 'position': 0.8, 'risk_level': 'high'},
        'mild_bull': {'name': '温和牛市', 'position': 0.6, 'risk_level': 'medium'},
        'sideways': {'name': '震荡市', 'position': 0.5, 'risk_level': 'medium'},
        'mild_bear': {'name': '温和熊市', 'position': 0.3, 'risk_level': 'low'},
        'strong_bear': {'name': '强势熊市', 'position': 0.1, 'risk_level': 'very_low'},
    }
    
    # 因子权重配置
    FACTOR_WEIGHTS = {
        'strong_bull': {
            'momentum': 0.30, 'growth': 0.25, 'quality': 0.15,
            'value': 0.10, 'low_volatility': 0.10, 'size': 0.10,
        },
        'mild_bull': {
            'momentum': 0.25, 'growth': 0.20, 'quality': 0.20,
            'value': 0.15, 'low_volatility': 0.10, 'size': 0.10,
        },
        'sideways': {
            'momentum': 0.15, 'growth': 0.15, 'quality': 0.25,
            'value': 0.20, 'low_volatility': 0.15, 'size': 0.10,
        },
        'mild_bear': {
            'momentum': 0.10, 'growth': 0.10, 'quality': 0.25,
            'value': 0.20, 'low_volatility': 0.25, 'size': 0.10,
        },
        'strong_bear': {
            'momentum': 0.05, 'growth': 0.05, 'quality': 0.20,
            'value': 0.15, 'low_volatility': 0.40, 'size': 0.15,
        },
    }
    
    def __init__(self):
        pass
    
    def identify_market_state(self, index_data: pd.DataFrame) -> Dict:
        """
        识别市场状态
        
        Args:
            index_data: 指数历史数据（包含close列）
            
        Returns:
            市场状态字典
        """
        if index_data.empty or len(index_data) < 60:
            return {
                'state': 'sideways',
                'state_info': self.STATES['sideways'],
                'confidence': 0.5,
                'indicators': {},
            }
        
        close = index_data['close'].values if 'close' in index_data.columns else index_data['Close'].values
        
        # 计算各项指标
        indicators = {}
        
        # 1. 趋势指标
        indicators['trend'] = self._calculate_trend(close)
        
        # 2. 动量指标
        indicators['momentum'] = self._calculate_momentum(close)
        
        # 3. 波动率指标
        indicators['volatility'] = self._calculate_volatility(close)
        
        # 4. 市场宽度指标（使用价格位置作为代理）
        indicators['breadth'] = self._calculate_breadth(close)
        
        # 综合判断市场状态
        state, confidence = self._determine_state(indicators)
        
        return {
            'state': state,
            'state_info': self.STATES[state],
            'confidence': confidence,
            'indicators': indicators,
            'factor_weights': self.FACTOR_WEIGHTS[state],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    
    def _calculate_trend(self, close: np.ndarray) -> Dict:
        """计算趋势指标"""
        # 均线
        ma5 = np.mean(close[-5:])
        ma10 = np.mean(close[-10:])
        ma20 = np.mean(close[-20:])
        ma60 = np.mean(close[-60:]) if len(close) >= 60 else ma20
        
        current_price = close[-1]
        
        # 均线多头排列
        ma_bullish = ma5 > ma10 > ma20 > ma60
        ma_bearish = ma5 < ma10 < ma20 < ma60
        
        # 价格相对均线位置
        price_above_ma20 = current_price > ma20
        price_above_ma60 = current_price > ma60
        
        # 趋势强度
        if ma_bullish and price_above_ma20 and price_above_ma60:
            trend_strength = 2  # 强势上涨
        elif price_above_ma20 and price_above_ma60:
            trend_strength = 1  # 温和上涨
        elif ma_bearish and not price_above_ma20 and not price_above_ma60:
            trend_strength = -2  # 强势下跌
        elif not price_above_ma20 and not price_above_ma60:
            trend_strength = -1  # 温和下跌
        else:
            trend_strength = 0  # 震荡
        
        return {
            'ma5': ma5,
            'ma10': ma10,
            'ma20': ma20,
            'ma60': ma60,
            'current_price': current_price,
            'ma_bullish': ma_bullish,
            'ma_bearish': ma_bearish,
            'price_above_ma20': price_above_ma20,
            'price_above_ma60': price_above_ma60,
            'trend_strength': trend_strength,
        }
    
    def _calculate_momentum(self, close: np.ndarray) -> Dict:
        """计算动量指标"""
        # 各周期收益率
        returns_5d = (close[-1] / close[-6] - 1) * 100 if len(close) > 5 else 0
        returns_10d = (close[-1] / close[-11] - 1) * 100 if len(close) > 10 else 0
        returns_20d = (close[-1] / close[-21] - 1) * 100 if len(close) > 20 else 0
        returns_60d = (close[-1] / close[-61] - 1) * 100 if len(close) > 60 else 0
        
        # RSI
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        rsi = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100
        
        # 动量强度
        if returns_20d > 10 and rsi > 60:
            momentum_strength = 2  # 强势动量
        elif returns_20d > 5 and rsi > 50:
            momentum_strength = 1  # 温和动量
        elif returns_20d < -10 and rsi < 40:
            momentum_strength = -2  # 强势负动量
        elif returns_20d < -5 and rsi < 50:
            momentum_strength = -1  # 温和负动量
        else:
            momentum_strength = 0  # 中性
        
        return {
            'returns_5d': returns_5d,
            'returns_10d': returns_10d,
            'returns_20d': returns_20d,
            'returns_60d': returns_60d,
            'rsi': rsi,
            'momentum_strength': momentum_strength,
        }
    
    def _calculate_volatility(self, close: np.ndarray) -> Dict:
        """计算波动率指标"""
        # 日收益率
        returns = np.diff(close) / close[:-1]
        
        # 波动率
        vol_20d = np.std(returns[-20:]) * np.sqrt(252) * 100
        vol_60d = np.std(returns[-60:]) * np.sqrt(252) * 100 if len(returns) >= 60 else vol_20d
        
        # 最大回撤
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(np.min(drawdown)) * 100
        
        # 波动率水平
        if vol_20d > 30:
            volatility_level = 'high'
        elif vol_20d > 20:
            volatility_level = 'medium'
        else:
            volatility_level = 'low'
        
        return {
            'vol_20d': vol_20d,
            'vol_60d': vol_60d,
            'max_drawdown': max_drawdown,
            'volatility_level': volatility_level,
        }
    
    def _calculate_breadth(self, close: np.ndarray) -> Dict:
        """计算市场宽度指标（使用价格位置作为代理）"""
        # 价格在60日区间的位置
        high_60d = np.max(close[-60:]) if len(close) >= 60 else np.max(close)
        low_60d = np.min(close[-60:]) if len(close) >= 60 else np.min(close)
        
        current_price = close[-1]
        
        if high_60d != low_60d:
            position = (current_price - low_60d) / (high_60d - low_60d)
        else:
            position = 0.5
        
        # 创新高/新低
        is_new_high = current_price >= high_60d * 0.98
        is_new_low = current_price <= low_60d * 1.02
        
        return {
            'high_60d': high_60d,
            'low_60d': low_60d,
            'position': position,
            'is_new_high': is_new_high,
            'is_new_low': is_new_low,
        }
    
    def _determine_state(self, indicators: Dict) -> Tuple[str, float]:
        """确定市场状态"""
        trend = indicators['trend']['trend_strength']
        momentum = indicators['momentum']['momentum_strength']
        volatility = indicators['volatility']['volatility_level']
        position = indicators['breadth']['position']
        
        # 综合评分
        score = 0
        
        # 趋势权重 40%
        score += trend * 0.4
        
        # 动量权重 30%
        score += momentum * 0.3
        
        # 价格位置权重 20%
        if position > 0.7:
            score += 0.2
        elif position < 0.3:
            score -= 0.2
        
        # 波动率调整 10%
        if volatility == 'high':
            score *= 0.9  # 高波动降低信心
        elif volatility == 'low':
            score *= 1.1  # 低波动增加信心
        
        # 确定状态
        if score >= 1.5:
            state = 'strong_bull'
            confidence = min(0.9, 0.5 + score * 0.1)
        elif score >= 0.5:
            state = 'mild_bull'
            confidence = 0.5 + score * 0.1
        elif score >= -0.5:
            state = 'sideways'
            confidence = 0.5
        elif score >= -1.5:
            state = 'mild_bear'
            confidence = 0.5 + abs(score) * 0.1
        else:
            state = 'strong_bear'
            confidence = min(0.9, 0.5 + abs(score) * 0.1)
        
        return state, confidence
    
    def get_factor_weights(self, market_state: str) -> Dict:
        """获取当前市场状态下的因子权重"""
        return self.FACTOR_WEIGHTS.get(market_state, self.FACTOR_WEIGHTS['sideways'])
    
    def format_report(self, market_state: Dict) -> str:
        """格式化市场状态报告"""
        report = []
        report.append("=" * 50)
        report.append("市场状态分析报告")
        report.append("=" * 50)
        report.append(f"分析时间: {market_state.get('timestamp', '')}")
        report.append(f"市场状态: {market_state['state_info']['name']}")
        report.append(f"信心度: {market_state['confidence']*100:.1f}%")
        report.append(f"建议仓位: {market_state['state_info']['position']*100:.0f}%")
        report.append("")
        
        report.append("-" * 50)
        report.append("技术指标:")
        report.append("-" * 50)
        
        indicators = market_state.get('indicators', {})
        
        trend = indicators.get('trend', {})
        report.append(f"趋势强度: {trend.get('trend_strength', 0)}")
        report.append(f"均线多头: {'是' if trend.get('ma_bullish') else '否'}")
        report.append(f"价格在MA20上方: {'是' if trend.get('price_above_ma20') else '否'}")
        
        momentum = indicators.get('momentum', {})
        report.append(f"20日收益: {momentum.get('returns_20d', 0):.2f}%")
        report.append(f"RSI(14): {momentum.get('rsi', 50):.1f}")
        
        volatility = indicators.get('volatility', {})
        report.append(f"20日波动率: {volatility.get('vol_20d', 0):.2f}%")
        report.append(f"最大回撤: {volatility.get('max_drawdown', 0):.2f}%")
        
        report.append("")
        report.append("-" * 50)
        report.append("因子权重配置:")
        report.append("-" * 50)
        
        weights = market_state.get('factor_weights', {})
        for factor, weight in weights.items():
            report.append(f"  {factor}: {weight*100:.0f}%")
        
        report.append("")
        report.append("=" * 50)
        
        return "\n".join(report)


# 创建全局实例
market_state_identifier = MarketStateIdentifier()
