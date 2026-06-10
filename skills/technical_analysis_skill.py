"""
技术分析技能
提供技术指标计算和图表形态识别
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class TechnicalAnalysisSkill(BaseSkill):
    """技术分析技能"""
    
    def __init__(self):
        super().__init__()
    
    def calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """计算技术指标"""
        indicators = {}
        
        if df is None or df.empty or len(df) < 20:
            return indicators
        
        try:
            close = df['close'].values if 'close' in df.columns else df['Close'].values
            high = df['high'].values if 'high' in df.columns else df['High'].values
            low = df['low'].values if 'low' in df.columns else df['Low'].values
            volume = df['volume'].values if 'volume' in df.columns else df['Volume'].values
            
            # 均线系统
            indicators['ma5'] = self._calculate_ma(close, 5)
            indicators['ma10'] = self._calculate_ma(close, 10)
            indicators['ma20'] = self._calculate_ma(close, 20)
            indicators['ma60'] = self._calculate_ma(close, 60)
            
            # RSI
            indicators['rsi6'] = self._calculate_rsi(close, 6)
            indicators['rsi14'] = self._calculate_rsi(close, 14)
            
            # MACD
            macd, signal, hist = self._calculate_macd(close)
            indicators['macd'] = macd
            indicators['macd_signal'] = signal
            indicators['macd_hist'] = hist
            
            # KDJ
            k, d, j = self._calculate_kdj(high, low, close)
            indicators['kdj_k'] = k
            indicators['kdj_d'] = d
            indicators['kdj_j'] = j
            
            # 布林带
            upper, middle, lower = self._calculate_bollinger(close)
            indicators['bb_upper'] = upper
            indicators['bb_middle'] = middle
            indicators['bb_lower'] = lower
            
            # 量比
            indicators['volume_ratio'] = self._calculate_volume_ratio(volume)
            
            # ATR
            indicators['atr'] = self._calculate_atr(high, low, close)
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
        
        return indicators
    
    def _calculate_ma(self, data: np.ndarray, period: int) -> Optional[float]:
        """计算移动平均线"""
        if len(data) < period:
            return None
        return np.mean(data[-period:])
    
    def _calculate_rsi(self, data: np.ndarray, period: int = 14) -> Optional[float]:
        """计算RSI"""
        if len(data) < period + 1:
            return None
        
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_macd(self, data: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple:
        """计算MACD"""
        if len(data) < slow + signal:
            return None, None, None
        
        ema_fast = self._ema(data, fast)
        ema_slow = self._ema(data, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(macd_line[~np.isnan(macd_line)], signal)
        
        full_signal = np.full_like(data, np.nan, dtype=float)
        start_idx = len(data) - len(signal_line)
        full_signal[start_idx:] = signal_line
        
        histogram = macd_line - full_signal
        
        return macd_line[-1], full_signal[-1], histogram[-1]
    
    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """计算指数移动平均"""
        multiplier = 2 / (period + 1)
        ema = np.zeros_like(data, dtype=float)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]
        return ema
    
    def _calculate_kdj(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
                       n: int = 9, m1: int = 3, m2: int = 3) -> Tuple:
        """计算KDJ"""
        if len(close) < n:
            return None, None, None
        
        rsv = np.full_like(close, np.nan, dtype=float)
        for i in range(n - 1, len(close)):
            highest = np.max(high[i - n + 1:i + 1])
            lowest = np.min(low[i - n + 1:i + 1])
            if highest != lowest:
                rsv[i] = (close[i] - lowest) / (highest - lowest) * 100
            else:
                rsv[i] = 50
        
        k = np.full_like(close, np.nan, dtype=float)
        d = np.full_like(close, np.nan, dtype=float)
        j = np.full_like(close, np.nan, dtype=float)
        
        k[n - 1] = 50
        d[n - 1] = 50
        
        for i in range(n, len(close)):
            if not np.isnan(rsv[i]):
                k[i] = (2/3) * k[i-1] + (1/3) * rsv[i]
                d[i] = (2/3) * d[i-1] + (1/3) * k[i]
                j[i] = 3 * k[i] - 2 * d[i]
        
        return k[-1], d[-1], j[-1]
    
    def _calculate_bollinger(self, data: np.ndarray, period: int = 20, std_dev: int = 2) -> Tuple:
        """计算布林带"""
        if len(data) < period:
            return None, None, None
        
        middle = np.mean(data[-period:])
        std = np.std(data[-period:])
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        
        return upper, middle, lower
    
    def _calculate_volume_ratio(self, volume: np.ndarray, period: int = 5) -> Optional[float]:
        """计算量比"""
        if len(volume) < period + 1:
            return None
        
        avg_vol = np.mean(volume[-period-1:-1])
        if avg_vol > 0:
            return volume[-1] / avg_vol
        return 1
    
    def _calculate_atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> Optional[float]:
        """计算ATR"""
        if len(close) < period + 1:
            return None
        
        tr = np.zeros(len(close))
        tr[0] = high[0] - low[0]
        
        for i in range(1, len(close)):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )
        
        return np.mean(tr[-period:])
    
    def identify_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """识别图表形态"""
        patterns = []
        
        if df is None or df.empty or len(df) < 20:
            return patterns
        
        try:
            close = df['close'].values if 'close' in df.columns else df['Close'].values
            
            # 检测金叉/死叉
            ma5 = self._calculate_ma(close, 5)
            ma10 = self._calculate_ma(close, 10)
            ma20 = self._calculate_ma(close, 20)
            
            if ma5 and ma10 and ma20:
                if ma5 > ma10 > ma20:
                    patterns.append({
                        'name': '均线多头排列',
                        'signal': 'bullish',
                        'description': 'MA5 > MA10 > MA20，趋势向上'
                    })
                elif ma5 < ma10 < ma20:
                    patterns.append({
                        'name': '均线空头排列',
                        'signal': 'bearish',
                        'description': 'MA5 < MA10 < MA20，趋势向下'
                    })
            
            # 检测RSI超买超卖
            rsi = self._calculate_rsi(close, 14)
            if rsi:
                if rsi > 70:
                    patterns.append({
                        'name': 'RSI超买',
                        'signal': 'bearish',
                        'description': f'RSI={rsi:.1f}，处于超买区域'
                    })
                elif rsi < 30:
                    patterns.append({
                        'name': 'RSI超卖',
                        'signal': 'bullish',
                        'description': f'RSI={rsi:.1f}，处于超卖区域'
                    })
            
            # 检测MACD金叉/死叉
            macd, signal, hist = self._calculate_macd(close)
            if macd and signal:
                if macd > signal and hist > 0:
                    patterns.append({
                        'name': 'MACD金叉',
                        'signal': 'bullish',
                        'description': 'MACD线上穿信号线'
                    })
                elif macd < signal and hist < 0:
                    patterns.append({
                        'name': 'MACD死叉',
                        'signal': 'bearish',
                        'description': 'MACD线下穿信号线'
                    })
            
        except Exception as e:
            logger.error(f"识别图表形态失败: {e}")
        
        return patterns
    
    def generate_signals(self, indicators: Dict) -> List[Dict]:
        """生成交易信号"""
        signals = []
        
        try:
            # RSI信号
            rsi = indicators.get('rsi14')
            if rsi:
                if rsi > 70:
                    signals.append({
                        'type': 'sell',
                        'strength': 'medium',
                        'reason': f'RSI超买({rsi:.1f})'
                    })
                elif rsi < 30:
                    signals.append({
                        'type': 'buy',
                        'strength': 'medium',
                        'reason': f'RSI超卖({rsi:.1f})'
                    })
            
            # MACD信号
            macd = indicators.get('macd')
            signal = indicators.get('macd_signal')
            hist = indicators.get('macd_hist')
            
            if macd and signal and hist:
                if macd > signal and hist > 0:
                    signals.append({
                        'type': 'buy',
                        'strength': 'strong',
                        'reason': 'MACD金叉'
                    })
                elif macd < signal and hist < 0:
                    signals.append({
                        'type': 'sell',
                        'strength': 'strong',
                        'reason': 'MACD死叉'
                    })
            
            # 均线信号
            ma5 = indicators.get('ma5')
            ma20 = indicators.get('ma20')
            
            if ma5 and ma20:
                if ma5 > ma20:
                    signals.append({
                        'type': 'buy',
                        'strength': 'medium',
                        'reason': '短期均线在长期均线之上'
                    })
                else:
                    signals.append({
                        'type': 'sell',
                        'strength': 'medium',
                        'reason': '短期均线在长期均线之下'
                    })
            
        except Exception as e:
            logger.error(f"生成交易信号失败: {e}")
        
        return signals
    
    def get_skill_description(self) -> str:
        """获取技能描述"""
        return """
【技术分析技能】
- 计算技术指标（MA、RSI、MACD、KDJ、布林带、ATR）
- 识别图表形态（金叉/死叉、超买/超卖）
- 生成交易信号
- 趋势判断和支撑阻力分析
"""
