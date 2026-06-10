#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强型量化因子库
结合最新开源量化算法优化本地算子
包含：ATR止损、Kelly仓位管理、ADX趋势强度、多因子复合评分、量价背离检测
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging


class QuantFactors:
    """量化因子计算库"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    # ==================== 波动率因子 ====================
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        计算ATR（平均真实波幅）- 用于动态止损和仓位管理
        
        Args:
            high: 最高价序列
            low: 最低价序列
            close: 收盘价序列
            period: 计算周期（默认14天）
        
        Returns:
            ATR序列
        """
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.ewm(span=period, adjust=False).mean()
        return atr
    
    @staticmethod
    def atr_percent(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        计算ATR百分比（ATR占收盘价的比例）
        用于标准化不同价格股票的波动率比较
        """
        atr_val = QuantFactors.atr(high, low, close, period)
        return (atr_val / close) * 100
    
    # ==================== 趋势强度因子 ====================
    
    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        计算ADX（平均趋向指数）- 衡量趋势强度
        ADX > 25: 强趋势
        ADX < 20: 弱趋势/震荡
        
        Args:
            high: 最高价序列
            low: 最低价序列
            close: 收盘价序列
            period: 计算周期
        
        Returns:
            ADX序列
        """
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        atr_val = QuantFactors.atr(high, low, close, period)
        
        plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr_val)
        minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr_val)
        
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.ewm(span=period, adjust=False).mean()
        
        return adx
    
    @staticmethod
    def trend_strength(close: pd.Series, period: int = 20) -> pd.Series:
        """
        趋势强度指标（自定义）
        基于价格相对于均线的位置和斜率
        返回值：-100 到 100，正值为上涨趋势，负值为下跌趋势
        """
        ma = close.rolling(window=period).mean()
        deviation = ((close - ma) / ma) * 100
        slope = ma.diff(5) / ma.shift(5) * 100  # 5日均线斜率
        
        # 综合偏离度和斜率
        strength = deviation * 0.6 + slope * 0.4
        return strength.clip(-100, 100)
    
    # ==================== 动量因子 ====================
    
    @staticmethod
    def rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """
        RSI（相对强弱指数）- 使用Wilder平滑法（更准确）
        
        Args:
            close: 收盘价序列
            period: 计算周期（默认14）
        
        Returns:
            RSI序列
        """
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        
        # Wilder平滑（等效于EMA的alpha=1/period）
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def stoch_rsi(close: pd.Series, rsi_period: int = 14, stoch_period: int = 14, 
                  k_period: int = 3, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        """
        Stochastic RSI - 比普通RSI更敏感的超买超卖指标
        
        Returns:
            (K线, D线)
        """
        rsi_val = QuantFactors.rsi(close, rsi_period)
        stoch_k = ((rsi_val - rsi_val.rolling(stoch_period).min()) / 
                   (rsi_val.rolling(stoch_period).max() - rsi_val.rolling(stoch_period).min())) * 100
        stoch_k = stoch_k.rolling(k_period).mean()
        stoch_d = stoch_k.rolling(d_period).mean()
        return stoch_k, stoch_d
    
    @staticmethod
    def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        威廉指标 - 超买超卖判断
        -20 以上为超买，-80 以下为超卖
        """
        highest = high.rolling(window=period).max()
        lowest = low.rolling(window=period).min()
        wr = -100 * (highest - close) / (highest - lowest)
        return wr
    
    # ==================== 量价因子 ====================
    
    @staticmethod
    def volume_price_divergence(close: pd.Series, volume: pd.Series, period: int = 20) -> pd.Series:
        """
        量价背离检测
        价格上涨但成交量下降 = 顶背离（负值）
        价格下跌但成交量下降 = 底背离（正值）
        
        Returns:
            背离强度 (-100 到 100)
        """
        price_change = close.pct_change(period) * 100
        volume_change = volume.pct_change(period) * 100
        
        # 背离度 = 价格变化方向与成交量变化方向的不一致程度
        divergence = np.where(
            price_change > 0,
            np.where(volume_change < 0, -(price_change.abs() + volume_change.abs()) / 2, 0),  # 顶背离
            np.where(volume_change < 0, (price_change.abs() + volume_change.abs()) / 2, 0)    # 底背离
        )
        
        return pd.Series(divergence, index=close.index).clip(-100, 100)
    
    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        OBV（能量潮指标）- 通过成交量判断趋势
        """
        direction = np.where(close > close.shift(1), 1, np.where(close < close.shift(1), -1, 0))
        obv = (volume * direction).cumsum()
        return obv
    
    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 20) -> pd.Series:
        """
        VWAP（成交量加权平均价格）- 机构常用的参考价位
        """
        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).rolling(period).sum() / volume.rolling(period).sum()
        return vwap
    
    # ==================== 仓位管理因子 ====================
    
    @staticmethod
    def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Kelly公式计算最优仓位比例
        
        Args:
            win_rate: 胜率 (0-1)
            avg_win: 平均盈利幅度
            avg_loss: 平均亏损幅度（正数）
        
        Returns:
            最优仓位比例 (0-1)
        """
        if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
            return 0.0
        
        b = avg_win / avg_loss  # 赔率
        kelly = (win_rate * b - (1 - win_rate)) / b
        
        # 使用半Kelly（更保守）
        kelly = max(0, kelly) * 0.5
        
        # 限制最大仓位
        return min(kelly, 0.25)
    
    @staticmethod
    def volatility_adjusted_position(atr_pct: float, target_risk: float = 2.0, 
                                      max_position: float = 0.25) -> float:
        """
        基于波动率的动态仓位管理
        
        Args:
            atr_pct: ATR百分比
            target_risk: 目标风险百分比（默认2%）
            max_position: 最大仓位比例
        
        Returns:
            建议仓位比例
        """
        if atr_pct <= 0:
            return 0.0
        
        position = target_risk / atr_pct
        return min(position, max_position)
    
    # ==================== 止损止盈因子 ====================
    
    @staticmethod
    def trailing_stop_multiplier(atr: float, multiplier: float = 2.0) -> float:
        """
        基于ATR的追踪止损距离
        
        Args:
            atr: 当前ATR值
            multiplier: ATR倍数（默认2.0）
        
        Returns:
            追踪止损距离
        """
        return atr * multiplier
    
    @staticmethod
    def dynamic_stop_loss(entry_price: float, atr: float, method: str = 'atr') -> Dict:
        """
        动态止损计算
        
        Args:
            entry_price: 入场价格
            atr: 当前ATR值
            method: 止损方法 ('atr', 'percent', 'chandelier')
        
        Returns:
            止损信息字典
        """
        if method == 'atr':
            # ATR止损：2倍ATR
            stop_distance = atr * 2
            stop_price = entry_price - stop_distance
            stop_pct = (stop_distance / entry_price) * 100
            
        elif method == 'percent':
            # 百分比止损：5%
            stop_pct = 5.0
            stop_price = entry_price * 0.95
            stop_distance = entry_price * 0.05
            
        elif method == 'chandelier':
            # Chandelier止损：3倍ATR（更宽松）
            stop_distance = atr * 3
            stop_price = entry_price - stop_distance
            stop_pct = (stop_distance / entry_price) * 100
        
        else:
            raise ValueError(f"Unknown method: {method}")
        
        return {
            'stop_price': round(stop_price, 2),
            'stop_distance': round(stop_distance, 2),
            'stop_pct': round(stop_pct, 2),
            'method': method
        }
    
    @staticmethod
    def profit_target(entry_price: float, atr: float, risk_reward_ratio: float = 2.0) -> Dict:
        """
        基于风险回报比的止盈目标
        
        Args:
            entry_price: 入场价格
            atr: 当前ATR值
            risk_reward_ratio: 风险回报比（默认2:1）
        
        Returns:
            止盈目标信息
        """
        stop_distance = atr * 2
        target_distance = stop_distance * risk_reward_ratio
        
        target1 = entry_price + target_distance * 0.5  # 第一目标：1:1
        target2 = entry_price + target_distance           # 第二目标：2:1
        target3 = entry_price + target_distance * 1.5     # 第三目标：3:1
        
        return {
            'target1': round(target1, 2),
            'target2': round(target2, 2),
            'target3': round(target3, 2),
            'risk_reward_ratio': risk_reward_ratio
        }
    
    # ==================== 多因子复合评分 ====================
    
    @staticmethod
    def composite_score(
        rsi_value: float,
        adx_value: float,
        atr_pct: float,
        volume_ratio: float,
        trend_strength: float,
        ma_alignment: float,
        weights: Dict = None
    ) -> float:
        """
        多因子复合评分（0-100分）
        
        Args:
            rsi_value: RSI值 (0-100)
            adx_value: ADX值 (0-100)
            atr_pct: ATR百分比
            volume_ratio: 成交量比率（当前/均量）
            trend_strength: 趋势强度 (-100 到 100)
            ma_alignment: 均线排列得分 (-1 到 1)
            weights: 各因子权重（可选）
        
        Returns:
            综合评分 (0-100)
        """
        if weights is None:
            weights = {
                'momentum': 0.25,      # 动量因子
                'trend': 0.25,         # 趋势因子
                'volume': 0.20,        # 量能因子
                'volatility': 0.15,    # 波动率因子
                'alignment': 0.15      # 均线排列因子
            }
        
        # 1. 动量评分 (RSI)
        if rsi_value < 30:
            momentum_score = 80 + (30 - rsi_value)  # 超卖，看涨信号
        elif rsi_value > 70:
            momentum_score = 30 - (rsi_value - 70)  # 超买，看跌信号
        else:
            momentum_score = 50 + (rsi_value - 50) * 0.5  # 中性区域
        momentum_score = np.clip(momentum_score, 0, 100)
        
        # 2. 趋势评分 (ADX + 趋势方向)
        if adx_value > 25:
            trend_score = 60 + min(adx_value - 25, 30)  # 强趋势加分
            if trend_strength < 0:
                trend_score = 40 - min(abs(trend_strength), 30)  # 下跌趋势减分
        else:
            trend_score = 40 + adx_value * 0.4  # 弱趋势
        trend_score = np.clip(trend_score, 0, 100)
        
        # 3. 量能评分
        if volume_ratio > 1.5:
            volume_score = 70 + min((volume_ratio - 1.5) * 20, 30)  # 放量
        elif volume_ratio < 0.5:
            volume_score = 30 - (0.5 - volume_ratio) * 20  # 极度缩量
        else:
            volume_score = 40 + volume_ratio * 20  # 正常量能
        volume_score = np.clip(volume_score, 0, 100)
        
        # 4. 波动率评分
        if atr_pct < 2:
            volatility_score = 70  # 低波动，适合稳健策略
        elif atr_pct < 5:
            volatility_score = 50  # 中等波动
        else:
            volatility_score = 30  # 高波动，风险较大
        volatility_score = np.clip(volatility_score, 0, 100)
        
        # 5. 均线排列评分
        alignment_score = 50 + ma_alignment * 50
        alignment_score = np.clip(alignment_score, 0, 100)
        
        # 加权计算
        total_score = (
            momentum_score * weights['momentum'] +
            trend_score * weights['trend'] +
            volume_score * weights['volume'] +
            volatility_score * weights['volatility'] +
            alignment_score * weights['alignment']
        )
        
        return round(total_score, 1)
    
    @staticmethod
    def ma_alignment_score(ma5: float, ma10: float, ma20: float, ma60: float) -> float:
        """
        均线排列评分
        多头排列：MA5 > MA10 > MA20 > MA60 → +1.0
        空头排列：MA5 < MA10 < MA20 < MA60 → -1.0
        
        Returns:
            排列得分 (-1.0 到 1.0)
        """
        score = 0.0
        
        # 短期均线在长期均线上方加分
        if ma5 > ma10:
            score += 0.25
        if ma10 > ma20:
            score += 0.25
        if ma20 > ma60:
            score += 0.25
        if ma5 > ma60:
            score += 0.25
        
        # 短期均线在长期均线下方减分
        if ma5 < ma10:
            score -= 0.25
        if ma10 < ma20:
            score -= 0.25
        if ma20 < ma60:
            score -= 0.25
        if ma5 < ma60:
            score -= 0.25
        
        return score
    
    # ==================== 信号生成 ====================
    
    @staticmethod
    def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
        """
        基于多因子生成交易信号
        
        Args:
            df: 包含OHLCV数据的DataFrame（列名：Open, High, Low, Close, Volume）
        
        Returns:
            添加了信号列的DataFrame
        """
        df = df.copy()
        
        # 计算各因子
        df['ATR'] = QuantFactors.atr(df['High'], df['Low'], df['Close'])
        df['ATR_pct'] = QuantFactors.atr_percent(df['High'], df['Low'], df['Close'])
        df['ADX'] = QuantFactors.adx(df['High'], df['Low'], df['Close'])
        df['RSI_14'] = QuantFactors.rsi(df['Close'], 14)
        df['RSI_6'] = QuantFactors.rsi(df['Close'], 6)
        df['Stoch_K'], df['Stoch_D'] = QuantFactors.stoch_rsi(df['Close'])
        df['Williams_R'] = QuantFactors.williams_r(df['High'], df['Low'], df['Close'])
        df['VPD'] = QuantFactors.volume_price_divergence(df['Close'], df['Volume'])
        df['OBV'] = QuantFactors.obv(df['Close'], df['Volume'])
        df['VWAP'] = QuantFactors.vwap(df['High'], df['Low'], df['Close'], df['Volume'])
        df['Trend_Strength'] = QuantFactors.trend_strength(df['Close'])
        
        # 新增：布林带（均值回归）
        bb = QuantFactors.bollinger_bands(df['Close'])
        df['BB_Upper'] = bb['BB_Upper']
        df['BB_Middle'] = bb['BB_Middle']
        df['BB_Lower'] = bb['BB_Lower']
        df['BB_Pct'] = bb['BB_Pct']
        df['BB_Width'] = bb['BB_Width']
        
        # 新增：KDJ 随机指标
        kdj = QuantFactors.kdj(df['High'], df['Low'], df['Close'])
        df['KDJ_K'] = kdj['K']
        df['KDJ_D'] = kdj['D']
        df['KDJ_J'] = kdj['J']
        
        # 新增：CCI 顺势指标
        df['CCI'] = QuantFactors.cci(df['High'], df['Low'], df['Close'])
        
        # 新增：MFI 资金流量指标
        df['MFI'] = QuantFactors.money_flow_index(df['High'], df['Low'], df['Close'], df['Volume'])
        
        # 新增：BIAS 乖离率
        bias = QuantFactors.bias(df['Close'])
        df['BIAS_6'] = bias['BIAS_6']
        df['BIAS_12'] = bias['BIAS_12']
        df['BIAS_24'] = bias['BIAS_24']
        
        # 新增：TRIX 趋势指标
        trix = QuantFactors.trix(df['Close'])
        df['TRIX'] = trix['TRIX']
        df['TRIX_Signal'] = trix['TRIX_Signal']
        
        # 新增：ROC 变动率
        df['ROC'] = QuantFactors.roc(df['Close'])
        
        # 新增：PSY 心理线
        df['PSY'] = QuantFactors.psychology_line(df['Close'])
        
        # 均线
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA10'] = df['Close'].rolling(10).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        # 成交量均线
        df['Vol_MA5'] = df['Volume'].rolling(5).mean()
        df['Vol_MA20'] = df['Volume'].rolling(20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Vol_MA5']
        
        # 均线排列评分
        df['MA_Alignment'] = df.apply(
            lambda row: QuantFactors.ma_alignment_score(
                row['MA5'], row['MA10'], row['MA20'], row['MA60']
            ) if pd.notna(row['MA60']) else 0,
            axis=1
        )
        
        # 多因子复合评分
        df['Composite_Score'] = df.apply(
            lambda row: QuantFactors.composite_score(
                rsi_value=row['RSI_14'],
                adx_value=row['ADX'],
                atr_pct=row['ATR_pct'],
                volume_ratio=row['Volume_Ratio'],
                trend_strength=row['Trend_Strength'],
                ma_alignment=row['MA_Alignment']
            ) if pd.notna(row['ADX']) else 50,
            axis=1
        )
        
        # 生成信号
        df['Signal'] = 0  # 0: 持有, 1: 买入, -1: 卖出
        
        # 买入信号：多因子评分 > 70 且 RSI < 70 且 趋势向上
        buy_condition = (
            (df['Composite_Score'] > 70) &
            (df['RSI_14'] < 70) &
            (df['Trend_Strength'] > 0) &
            (df['MA_Alignment'] > 0)
        )
        df.loc[buy_condition, 'Signal'] = 1
        
        # 卖出信号：多因子评分 < 30 或 RSI > 80 或 趋势转弱
        sell_condition = (
            (df['Composite_Score'] < 30) |
            (df['RSI_14'] > 80) |
            ((df['Trend_Strength'] < -20) & (df['ADX'] > 25))
        )
        df.loc[sell_condition, 'Signal'] = -1
        
        # 动态止损止盈
        df['Stop_Loss'] = df['Close'] - df['ATR'] * 2
        df['Take_Profit_1'] = df['Close'] + df['ATR'] * 2  # 1:1
        df['Take_Profit_2'] = df['Close'] + df['ATR'] * 4  # 2:1
        
        # 建议仓位（基于波动率）
        df['Suggested_Position'] = df['ATR_pct'].apply(
            lambda x: QuantFactors.volatility_adjusted_position(x) if pd.notna(x) and x > 0 else 0.1
        )
        
        return df


    # ==================== 补充主流因子 ====================

    @staticmethod
    def bollinger_bands(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
        """
        布林带（Bollinger Bands）- 均值回归核心指标

        Args:
            close: 收盘价序列
            period: 移动平均周期（默认20）
            std_dev: 标准差倍数（默认2.0）

        Returns:
            DataFrame: BB_Upper, BB_Middle, BB_Lower, BB_Width, BB_Pct
        """
        bb = pd.DataFrame(index=close.index)
        bb['BB_Middle'] = close.rolling(window=period).mean()
        rolling_std = close.rolling(window=period).std()
        bb['BB_Upper'] = bb['BB_Middle'] + std_dev * rolling_std
        bb['BB_Lower'] = bb['BB_Middle'] - std_dev * rolling_std
        bb['BB_Width'] = (bb['BB_Upper'] - bb['BB_Lower']) / bb['BB_Middle']  # 带宽
        bb['BB_Pct'] = (close - bb['BB_Lower']) / (bb['BB_Upper'] - bb['BB_Lower'])  # %B
        return bb

    @staticmethod
    def kdj(high: pd.Series, low: pd.Series, close: pd.Series,
            n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
        """
        KDJ 随机指标 - 超买超卖判断

        Args:
            high, low, close: 价格序列
            n: RSV 周期（默认9）
            m1: K 平滑周期（默认3）
            m2: D 平滑周期（默认3）

        Returns:
            DataFrame: K, D, J
        """
        kdj = pd.DataFrame(index=close.index)
        lowest_low = low.rolling(window=n, min_periods=1).min()
        highest_high = high.rolling(window=n, min_periods=1).max()
        rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
        rsv = rsv.fillna(50)

        k = pd.Series(index=close.index, dtype=float)
        d = pd.Series(index=close.index, dtype=float)
        k.iloc[0] = 50
        d.iloc[0] = 50
        for i in range(1, len(close)):
            k.iloc[i] = (2 / m1) * rsv.iloc[i] + (1 - 2 / m1) * k.iloc[i - 1]
            d.iloc[i] = (2 / m2) * k.iloc[i] + (1 - 2 / m2) * d.iloc[i - 1]

        kdj['K'] = k
        kdj['D'] = d
        kdj['J'] = 3 * k - 2 * d
        return kdj

    @staticmethod
    def cci(high: pd.Series, low: pd.Series, close: pd.Series,
            period: int = 14) -> pd.Series:
        """
        CCI 顺势指标 - 判断趋势强度和超买超卖

        Args:
            high, low, close: 价格序列
            period: 计算周期（默认14）

        Returns:
            CCI 序列
        """
        tp = (high + low + close) / 3
        sma = tp.rolling(window=period).mean()
        mad = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
        cci = (tp - sma) / (0.015 * mad)
        return cci

    @staticmethod
    def momentum(close: pd.Series, period: int = 10) -> pd.Series:
        """
        动量因子 - 衡量价格变化速度

        Args:
            close: 收盘价序列
            period: 动量周期（默认10）

        Returns:
            动量值序列
        """
        return close - close.shift(period)

    @staticmethod
    def roc(close: pd.Series, period: int = 12) -> pd.Series:
        """
        ROC 变动率 - 价格变化百分比

        Args:
            close: 收盘价序列
            period: 计算周期（默认12）

        Returns:
            ROC 序列（百分比）
        """
        prev = close.shift(period)
        return (close - prev) / prev * 100

    @staticmethod
    def bias(close: pd.Series, periods: List[int] = None) -> pd.DataFrame:
        """
        BIAS 乖离率 - 价格偏离均线程度（均值回归信号）

        Args:
            close: 收盘价序列
            periods: 均线周期列表（默认[6, 12, 24]）

        Returns:
            DataFrame: BIAS_6, BIAS_12, BIAS_24
        """
        if periods is None:
            periods = [6, 12, 24]
        bias_df = pd.DataFrame(index=close.index)
        for p in periods:
            ma = close.rolling(window=p).mean()
            bias_df[f'BIAS_{p}'] = (close - ma) / ma * 100
        return bias_df

    @staticmethod
    def trix(close: pd.Series, period: int = 12, signal: int = 9) -> pd.DataFrame:
        """
        TRIX 三重指数平滑移动平均 - 趋势跟踪指标

        Args:
            close: 收盘价序列
            period: EMA 周期（默认12）
            signal: 信号线周期（默认9）

        Returns:
            DataFrame: TRIX, TRIX_Signal
        """
        trix_df = pd.DataFrame(index=close.index)
        ema1 = close.ewm(span=period, adjust=False).mean()
        ema2 = ema1.ewm(span=period, adjust=False).mean()
        ema3 = ema2.ewm(span=period, adjust=False).mean()
        trix_df['TRIX'] = (ema3 - ema3.shift(1)) / ema3.shift(1) * 100
        trix_df['TRIX_Signal'] = trix_df['TRIX'].rolling(window=signal).mean()
        return trix_df

    @staticmethod
    def psychology_line(close: pd.Series, period: int = 12) -> pd.Series:
        """
        PSY 心理线 - 市场情绪指标

        Args:
            close: 收盘价序列
            period: 计算周期（默认12）

        Returns:
            PSY 序列（百分比）
        """
        up = (close > close.shift(1)).astype(int)
        psy = up.rolling(window=period).sum() / period * 100
        return psy

    @staticmethod
    def volume_ratio(volume: pd.Series, period: int = 5) -> pd.Series:
        """
        量比 - 当日成交量与过去N日平均成交量的比值

        Args:
            volume: 成交量序列
            period: 平均周期（默认5）

        Returns:
            量比序列
        """
        avg_vol = volume.rolling(window=period).mean()
        return volume / avg_vol

    @staticmethod
    def money_flow_index(high: pd.Series, low: pd.Series, close: pd.Series,
                         volume: pd.Series, period: int = 14) -> pd.Series:
        """
        MFI 资金流量指标 - 结合价格和成交量的RSI变体

        Args:
            high, low, close, volume: 价格和成交量序列
            period: 计算周期（默认14）

        Returns:
            MFI 序列
        """
        tp = (high + low + close) / 3
        mf = tp * volume
        tp_diff = tp.diff()
        pos_mf = pd.Series(np.where(tp_diff > 0, mf, 0), index=close.index)
        neg_mf = pd.Series(np.where(tp_diff < 0, mf, 0), index=close.index)
        pos_sum = pos_mf.rolling(window=period).sum()
        neg_sum = neg_mf.rolling(window=period).sum()
        mfi = 100 - (100 / (1 + pos_sum / neg_sum.replace(0, np.nan)))
        return mfi


# 全局实例
quant_factors = QuantFactors()
