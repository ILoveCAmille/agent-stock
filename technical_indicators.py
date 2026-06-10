"""
技术指标计算工具模块
提供统一的技术指标计算函数
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """技术指标计算器"""
    
    @staticmethod
    def sma(data: np.ndarray, period: int) -> np.ndarray:
        """简单移动平均线"""
        if len(data) < period:
            return np.full_like(data, np.nan, dtype=float)
        
        result = np.full_like(data, np.nan, dtype=float)
        for i in range(period - 1, len(data)):
            result[i] = np.mean(data[i - period + 1:i + 1])
        return result
    
    @staticmethod
    def ema(data: np.ndarray, period: int) -> np.ndarray:
        """指数移动平均线"""
        if len(data) < period:
            return np.full_like(data, np.nan, dtype=float)
        
        multiplier = 2 / (period + 1)
        result = np.full_like(data, np.nan, dtype=float)
        
        # 第一个值使用SMA
        result[period - 1] = np.mean(data[:period])
        
        # 后续值使用EMA
        for i in range(period, len(data)):
            result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
        
        return result
    
    @staticmethod
    def macd(data: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """MACD指标"""
        ema_fast = TechnicalIndicators.ema(data, fast)
        ema_slow = TechnicalIndicators.ema(data, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.ema(macd_line[~np.isnan(macd_line)], signal)
        
        # 对齐长度
        full_signal = np.full_like(data, np.nan, dtype=float)
        start_idx = len(data) - len(signal_line)
        full_signal[start_idx:] = signal_line
        
        histogram = macd_line - full_signal
        
        return macd_line, full_signal, histogram
    
    @staticmethod
    def rsi(data: np.ndarray, period: int = 14) -> np.ndarray:
        """RSI指标"""
        if len(data) < period + 1:
            return np.full_like(data, np.nan, dtype=float)
        
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        result = np.full(len(data), np.nan, dtype=float)
        
        # 第一个RSI值
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        if avg_loss == 0:
            result[period] = 100
        else:
            rs = avg_gain / avg_loss
            result[period] = 100 - (100 / (1 + rs))
        
        # 后续RSI值
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                result[i + 1] = 100
            else:
                rs = avg_gain / avg_loss
                result[i + 1] = 100 - (100 / (1 + rs))
        
        return result
    
    @staticmethod
    def kdj(high: np.ndarray, low: np.ndarray, close: np.ndarray, 
            n: int = 9, m1: int = 3, m2: int = 3) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """KDJ指标"""
        if len(close) < n:
            return (np.full_like(close, np.nan, dtype=float),
                    np.full_like(close, np.nan, dtype=float),
                    np.full_like(close, np.nan, dtype=float))
        
        # 计算RSV
        rsv = np.full_like(close, np.nan, dtype=float)
        for i in range(n - 1, len(close)):
            highest = np.max(high[i - n + 1:i + 1])
            lowest = np.min(low[i - n + 1:i + 1])
            if highest != lowest:
                rsv[i] = (close[i] - lowest) / (highest - lowest) * 100
            else:
                rsv[i] = 50
        
        # 计算K、D、J
        k = np.full_like(close, np.nan, dtype=float)
        d = np.full_like(close, np.nan, dtype=float)
        j = np.full_like(close, np.nan, dtype=float)
        
        # 初始值
        k[n - 1] = 50
        d[n - 1] = 50
        
        for i in range(n, len(close)):
            if not np.isnan(rsv[i]):
                k[i] = (2/3) * k[i-1] + (1/3) * rsv[i]
                d[i] = (2/3) * d[i-1] + (1/3) * k[i]
                j[i] = 3 * k[i] - 2 * d[i]
        
        return k, d, j
    
    @staticmethod
    def bollinger(data: np.ndarray, period: int = 20, std_dev: int = 2) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """布林带"""
        middle = TechnicalIndicators.sma(data, period)
        
        upper = np.full_like(data, np.nan, dtype=float)
        lower = np.full_like(data, np.nan, dtype=float)
        
        for i in range(period - 1, len(data)):
            std = np.std(data[i - period + 1:i + 1])
            upper[i] = middle[i] + std_dev * std
            lower[i] = middle[i] - std_dev * std
        
        return upper, middle, lower
    
    @staticmethod
    def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """ATR指标"""
        if len(close) < period + 1:
            return np.full_like(close, np.nan, dtype=float)
        
        # 计算TR
        tr = np.full_like(close, np.nan, dtype=float)
        tr[0] = high[0] - low[0]
        
        for i in range(1, len(close)):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )
        
        # 计算ATR
        atr = np.full_like(close, np.nan, dtype=float)
        atr[period] = np.mean(tr[1:period + 1])
        
        for i in range(period + 1, len(close)):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
        
        return atr
    
    @staticmethod
    def volume_ratio(volume: np.ndarray, period: int = 5) -> np.ndarray:
        """量比"""
        if len(volume) < period:
            return np.full_like(volume, np.nan, dtype=float)
        
        result = np.full_like(volume, np.nan, dtype=float)
        for i in range(period, len(volume)):
            avg_vol = np.mean(volume[i - period:i])
            if avg_vol > 0:
                result[i] = volume[i] / avg_vol
            else:
                result[i] = 1
        
        return result
    
    @staticmethod
    def obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """OBV指标"""
        if len(close) < 2:
            return np.full_like(volume, np.nan, dtype=float)
        
        result = np.zeros_like(volume, dtype=float)
        result[0] = volume[0]
        
        for i in range(1, len(close)):
            if close[i] > close[i-1]:
                result[i] = result[i-1] + volume[i]
            elif close[i] < close[i-1]:
                result[i] = result[i-1] - volume[i]
            else:
                result[i] = result[i-1]
        
        return result
    
    @staticmethod
    def williams_r(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """威廉指标"""
        if len(close) < period:
            return np.full_like(close, np.nan, dtype=float)
        
        result = np.full_like(close, np.nan, dtype=float)
        
        for i in range(period - 1, len(close)):
            highest = np.max(high[i - period + 1:i + 1])
            lowest = np.min(low[i - period + 1:i + 1])
            
            if highest != lowest:
                result[i] = (highest - close[i]) / (highest - lowest) * -100
            else:
                result[i] = -50
        
        return result
    
    @staticmethod
    def cci(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """CCI指标"""
        if len(close) < period:
            return np.full_like(close, np.nan, dtype=float)
        
        # 计算典型价格
        tp = (high + low + close) / 3
        
        result = np.full_like(close, np.nan, dtype=float)
        
        for i in range(period - 1, len(close)):
            tp_slice = tp[i - period + 1:i + 1]
            tp_mean = np.mean(tp_slice)
            tp_std = np.std(tp_slice)
            
            if tp_std > 0:
                result[i] = (tp[i] - tp_mean) / (0.015 * tp_std)
            else:
                result[i] = 0
        
        return result
    
    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame) -> Dict:
        """计算所有技术指标"""
        if df is None or df.empty:
            return {}
        
        try:
            close = df['close'].values
            high = df['high'].values
            low = df['low'].values
            volume = df['volume'].values if 'volume' in df.columns else None
            
            indicators = {}
            
            # 均线
            for period in [5, 10, 20, 60, 120]:
                if len(close) >= period:
                    indicators[f'ma{period}'] = TechnicalIndicators.sma(close, period)
                    indicators[f'ema{period}'] = TechnicalIndicators.ema(close, period)
            
            # MACD
            if len(close) >= 35:
                macd, signal, hist = TechnicalIndicators.macd(close)
                indicators['macd'] = macd
                indicators['macd_signal'] = signal
                indicators['macd_hist'] = hist
            
            # RSI
            if len(close) >= 15:
                indicators['rsi6'] = TechnicalIndicators.rsi(close, 6)
                indicators['rsi14'] = TechnicalIndicators.rsi(close, 14)
            
            # KDJ
            if len(close) >= 9:
                k, d, j = TechnicalIndicators.kdj(high, low, close)
                indicators['kdj_k'] = k
                indicators['kdj_d'] = d
                indicators['kdj_j'] = j
            
            # 布林带
            if len(close) >= 20:
                upper, middle, lower = TechnicalIndicators.bollinger(close)
                indicators['bb_upper'] = upper
                indicators['bb_middle'] = middle
                indicators['bb_lower'] = lower
            
            # ATR
            if len(close) >= 15:
                indicators['atr'] = TechnicalIndicators.atr(high, low, close)
            
            # 量比
            if volume is not None and len(volume) >= 6:
                indicators['volume_ratio'] = TechnicalIndicators.volume_ratio(volume)
            
            # OBV
            if volume is not None:
                indicators['obv'] = TechnicalIndicators.obv(close, volume)
            
            # 威廉指标
            if len(close) >= 14:
                indicators['williams_r'] = TechnicalIndicators.williams_r(high, low, close)
            
            # CCI
            if len(close) >= 14:
                indicators['cci'] = TechnicalIndicators.cci(high, low, close)
            
            return indicators
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
            return {}
    
    @staticmethod
    def get_latest_indicators(df: pd.DataFrame) -> Dict:
        """获取最新技术指标值"""
        all_indicators = TechnicalIndicators.calculate_all_indicators(df)
        
        latest = {}
        for key, values in all_indicators.items():
            if isinstance(values, np.ndarray) and len(values) > 0:
                # 获取最后一个非NaN值
                valid_values = values[~np.isnan(values)]
                if len(valid_values) > 0:
                    latest[key] = valid_values[-1]
        
        return latest


# 创建全局实例
tech_indicators = TechnicalIndicators()
