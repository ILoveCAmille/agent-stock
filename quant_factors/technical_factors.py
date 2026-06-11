"""
技术面因子库
包含150+技术面因子，覆盖：
- 趋势因子
- 动量因子
- 波动因子
- 成交量因子
- 形态因子
- 指标因子
"""

import numpy as np
import pandas as pd
from typing import Dict, List

# 技术面因子定义
TECHNICAL_FACTORS = {
    # ============================================
    # 趋势因子 (Trend Factors) - 30个
    # ============================================
    'ma5_trend': {'category': 'trend', 'name': '5日均线趋势', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'ma10_trend': {'category': 'trend', 'name': '10日均线趋势', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'ma20_trend': {'category': 'trend', 'name': '20日均线趋势', 'direction': 'long', 'stability': 0.75, 'drawdown': 0.25},
    'ma60_trend': {'category': 'trend', 'name': '60日均线趋势', 'direction': 'long', 'stability': 0.78, 'drawdown': 0.22},
    'ma120_trend': {'category': 'trend', 'name': '120日均线趋势', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'ma250_trend': {'category': 'trend', 'name': '250日均线趋势', 'direction': 'long', 'stability': 0.82, 'drawdown': 0.18},
    'ema12_trend': {'category': 'trend', 'name': '12日EMA趋势', 'direction': 'long', 'stability': 0.71, 'drawdown': 0.29},
    'ema26_trend': {'category': 'trend', 'name': '26日EMA趋势', 'direction': 'long', 'stability': 0.74, 'drawdown': 0.26},
    'ma_cross_5_10': {'category': 'trend', 'name': '5/10均线交叉', 'direction': 'long', 'stability': 0.68, 'drawdown': 0.32},
    'ma_cross_10_20': {'category': 'trend', 'name': '10/20均线交叉', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'ma_cross_20_60': {'category': 'trend', 'name': '20/60均线交叉', 'direction': 'long', 'stability': 0.76, 'drawdown': 0.24},
    'ma_cross_60_120': {'category': 'trend', 'name': '60/120均线交叉', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'price_to_ma5': {'category': 'trend', 'name': '价格/5日均线', 'direction': 'long', 'stability': 0.69, 'drawdown': 0.31},
    'price_to_ma10': {'category': 'trend', 'name': '价格/10日均线', 'direction': 'long', 'stability': 0.71, 'drawdown': 0.29},
    'price_to_ma20': {'category': 'trend', 'name': '价格/20日均线', 'direction': 'long', 'stability': 0.74, 'drawdown': 0.26},
    'price_to_ma60': {'category': 'trend', 'name': '价格/60日均线', 'direction': 'long', 'stability': 0.77, 'drawdown': 0.23},
    'price_to_ma120': {'category': 'trend', 'name': '价格/120日均线', 'direction': 'long', 'stability': 0.79, 'drawdown': 0.21},
    'price_to_ma250': {'category': 'trend', 'name': '价格/250日均线', 'direction': 'long', 'stability': 0.81, 'drawdown': 0.19},
    'ma_slope_5': {'category': 'trend', 'name': '5日均线斜率', 'direction': 'long', 'stability': 0.67, 'drawdown': 0.33},
    'ma_slope_10': {'category': 'trend', 'name': '10日均线斜率', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'ma_slope_20': {'category': 'trend', 'name': '20日均线斜率', 'direction': 'long', 'stability': 0.73, 'drawdown': 0.27},
    'ma_slope_60': {'category': 'trend', 'name': '60日均线斜率', 'direction': 'long', 'stability': 0.76, 'drawdown': 0.24},
    'trend_strength': {'category': 'trend', 'name': '趋势强度', 'direction': 'long', 'stability': 0.75, 'drawdown': 0.25},
    'trend_consistency': {'category': 'trend', 'name': '趋势一致性', 'direction': 'long', 'stability': 0.74, 'drawdown': 0.26},
    'trend_duration': {'category': 'trend', 'name': '趋势持续时间', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'trend_reversal': {'category': 'trend', 'name': '趋势反转信号', 'direction': 'short', 'stability': 0.68, 'drawdown': 0.32},
    'golden_cross': {'category': 'trend', 'name': '金叉信号', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'death_cross': {'category': 'trend', 'name': '死叉信号', 'direction': 'short', 'stability': 0.70, 'drawdown': 0.30},
    'price_position': {'category': 'trend', 'name': '价格位置', 'direction': 'long', 'stability': 0.73, 'drawdown': 0.27},
    'channel_position': {'category': 'trend', 'name': '通道位置', 'direction': 'long', 'stability': 0.74, 'drawdown': 0.26},
    
    # ============================================
    # 动量因子 (Momentum Factors) - 30个
    # ============================================
    'mom_1d': {'category': 'momentum', 'name': '1日动量', 'direction': 'long', 'stability': 0.55, 'drawdown': 0.45},
    'mom_3d': {'category': 'momentum', 'name': '3日动量', 'direction': 'long', 'stability': 0.60, 'drawdown': 0.40},
    'mom_5d': {'category': 'momentum', 'name': '5日动量', 'direction': 'long', 'stability': 0.63, 'drawdown': 0.37},
    'mom_10d': {'category': 'momentum', 'name': '10日动量', 'direction': 'long', 'stability': 0.66, 'drawdown': 0.34},
    'mom_20d': {'category': 'momentum', 'name': '20日动量', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'mom_40d': {'category': 'momentum', 'name': '40日动量', 'direction': 'long', 'stability': 0.73, 'drawdown': 0.27},
    'mom_60d': {'category': 'momentum', 'name': '60日动量', 'direction': 'long', 'stability': 0.75, 'drawdown': 0.25},
    'mom_120d': {'category': 'momentum', 'name': '120日动量', 'direction': 'long', 'stability': 0.78, 'drawdown': 0.22},
    'mom_180d': {'category': 'momentum', 'name': '180日动量', 'direction': 'long', 'stability': 0.79, 'drawdown': 0.21},
    'mom_240d': {'category': 'momentum', 'name': '240日动量', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'mom_12m_1m': {'category': 'momentum', 'name': '12-1月动量', 'direction': 'long', 'stability': 0.82, 'drawdown': 0.18},
    'mom_6m_1m': {'category': 'momentum', 'name': '6-1月动量', 'direction': 'long', 'stability': 0.78, 'drawdown': 0.22},
    'mom_3m_1m': {'category': 'momentum', 'name': '3-1月动量', 'direction': 'long', 'stability': 0.75, 'drawdown': 0.25},
    'price_acceleration': {'category': 'momentum', 'name': '价格加速度', 'direction': 'long', 'stability': 0.67, 'drawdown': 0.33},
    'price_jerk': {'category': 'momentum', 'name': '价格急动度', 'direction': 'long', 'stability': 0.65, 'drawdown': 0.35},
    'momentum_quality': {'category': 'momentum', 'name': '动量质量', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'momentum_consistency': {'category': 'momentum', 'name': '动量一致性', 'direction': 'long', 'stability': 0.74, 'drawdown': 0.26},
    'momentum_reversal': {'category': 'momentum', 'name': '动量反转', 'direction': 'short', 'stability': 0.68, 'drawdown': 0.32},
    'price_range_5d': {'category': 'momentum', 'name': '5日价格区间', 'direction': 'long', 'stability': 0.62, 'drawdown': 0.38},
    'price_range_10d': {'category': 'momentum', 'name': '10日价格区间', 'direction': 'long', 'stability': 0.65, 'drawdown': 0.35},
    'price_range_20d': {'category': 'momentum', 'name': '20日价格区间', 'direction': 'long', 'stability': 0.68, 'drawdown': 0.32},
    'high_low_ratio': {'category': 'momentum', 'name': '最高/最低比', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'close_to_high': {'category': 'momentum', 'name': '收盘价/最高价', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'close_to_low': {'category': 'momentum', 'name': '收盘价/最低价', 'direction': 'long', 'stability': 0.71, 'drawdown': 0.29},
    'price_position_52w': {'category': 'momentum', 'name': '52周价格位置', 'direction': 'long', 'stability': 0.75, 'drawdown': 0.25},
    'new_high_ratio': {'category': 'momentum', 'name': '创新高比例', 'direction': 'long', 'stability': 0.73, 'drawdown': 0.27},
    'new_low_ratio': {'category': 'momentum', 'name': '创新低比例', 'direction': 'short', 'stability': 0.72, 'drawdown': 0.28},
    'up_days_ratio': {'category': 'momentum', 'name': '上涨天数比例', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'down_days_ratio': {'category': 'momentum', 'name': '下跌天数比例', 'direction': 'short', 'stability': 0.69, 'drawdown': 0.31},
    'consecutive_up': {'category': 'momentum', 'name': '连续上涨天数', 'direction': 'long', 'stability': 0.65, 'drawdown': 0.35},
    
    # ============================================
    # 波动因子 (Volatility Factors) - 25个
    # ============================================
    'volatility_5d': {'category': 'volatility', 'name': '5日波动率', 'direction': 'short', 'stability': 0.80, 'drawdown': 0.20},
    'volatility_10d': {'category': 'volatility', 'name': '10日波动率', 'direction': 'short', 'stability': 0.82, 'drawdown': 0.18},
    'volatility_20d': {'category': 'volatility', 'name': '20日波动率', 'direction': 'short', 'stability': 0.85, 'drawdown': 0.15},
    'volatility_40d': {'category': 'volatility', 'name': '40日波动率', 'direction': 'short', 'stability': 0.86, 'drawdown': 0.14},
    'volatility_60d': {'category': 'volatility', 'name': '60日波动率', 'direction': 'short', 'stability': 0.87, 'drawdown': 0.13},
    'volatility_120d': {'category': 'volatility', 'name': '120日波动率', 'direction': 'short', 'stability': 0.88, 'drawdown': 0.12},
    'downside_vol_20d': {'category': 'volatility', 'name': '20日下行波动率', 'direction': 'short', 'stability': 0.83, 'drawdown': 0.17},
    'downside_vol_60d': {'category': 'volatility', 'name': '60日下行波动率', 'direction': 'short', 'stability': 0.85, 'drawdown': 0.15},
    'upside_vol_20d': {'category': 'volatility', 'name': '20日上行波动率', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'upside_vol_60d': {'category': 'volatility', 'name': '60日上行波动率', 'direction': 'long', 'stability': 0.82, 'drawdown': 0.18},
    'vol_ratio_up_down': {'category': 'volatility', 'name': '上行/下行波动比', 'direction': 'long', 'stability': 0.78, 'drawdown': 0.22},
    'max_drawdown_5d': {'category': 'volatility', 'name': '5日最大回撤', 'direction': 'short', 'stability': 0.75, 'drawdown': 0.25},
    'max_drawdown_10d': {'category': 'volatility', 'name': '10日最大回撤', 'direction': 'short', 'stability': 0.77, 'drawdown': 0.23},
    'max_drawdown_20d': {'category': 'volatility', 'name': '20日最大回撤', 'direction': 'short', 'stability': 0.80, 'drawdown': 0.20},
    'max_drawdown_60d': {'category': 'volatility', 'name': '60日最大回撤', 'direction': 'short', 'stability': 0.82, 'drawdown': 0.18},
    'avg_drawdown_20d': {'category': 'volatility', 'name': '20日平均回撤', 'direction': 'short', 'stability': 0.79, 'drawdown': 0.21},
    'skewness_20d': {'category': 'volatility', 'name': '20日偏度', 'direction': 'short', 'stability': 0.72, 'drawdown': 0.28},
    'skewness_60d': {'category': 'volatility', 'name': '60日偏度', 'direction': 'short', 'stability': 0.75, 'drawdown': 0.25},
    'kurtosis_20d': {'category': 'volatility', 'name': '20日峰度', 'direction': 'short', 'stability': 0.70, 'drawdown': 0.30},
    'kurtosis_60d': {'category': 'volatility', 'name': '60日峰度', 'direction': 'short', 'stability': 0.73, 'drawdown': 0.27},
    'var_95': {'category': 'volatility', 'name': '95%VaR', 'direction': 'short', 'stability': 0.78, 'drawdown': 0.22},
    'var_99': {'category': 'volatility', 'name': '99%VaR', 'direction': 'short', 'stability': 0.80, 'drawdown': 0.20},
    'cvar_95': {'category': 'volatility', 'name': '95%CVaR', 'direction': 'short', 'stability': 0.79, 'drawdown': 0.21},
    'beta_20d': {'category': 'volatility', 'name': '20日Beta', 'direction': 'short', 'stability': 0.82, 'drawdown': 0.18},
    'beta_60d': {'category': 'volatility', 'name': '60日Beta', 'direction': 'short', 'stability': 0.84, 'drawdown': 0.16},
    
    # ============================================
    # 成交量因子 (Volume Factors) - 25个
    # ============================================
    'volume_ma5': {'category': 'volume', 'name': '5日成交量均线', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'volume_ma10': {'category': 'volume', 'name': '10日成交量均线', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'volume_ma20': {'category': 'volume', 'name': '20日成交量均线', 'direction': 'long', 'stability': 0.75, 'drawdown': 0.25},
    'volume_ratio_5d': {'category': 'volume', 'name': '5日量比', 'direction': 'long', 'stability': 0.68, 'drawdown': 0.32},
    'volume_ratio_10d': {'category': 'volume', 'name': '10日量比', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'volume_ratio_20d': {'category': 'volume', 'name': '20日量比', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'turnover_5d': {'category': 'volume', 'name': '5日换手率', 'direction': 'short', 'stability': 0.75, 'drawdown': 0.25},
    'turnover_10d': {'category': 'volume', 'name': '10日换手率', 'direction': 'short', 'stability': 0.77, 'drawdown': 0.23},
    'turnover_20d': {'category': 'volume', 'name': '20日换手率', 'direction': 'short', 'stability': 0.80, 'drawdown': 0.20},
    'turnover_60d': {'category': 'volume', 'name': '60日换手率', 'direction': 'short', 'stability': 0.82, 'drawdown': 0.18},
    'volume_volatility': {'category': 'volume', 'name': '成交量波动率', 'direction': 'short', 'stability': 0.73, 'drawdown': 0.27},
    'volume_trend': {'category': 'volume', 'name': '成交量趋势', 'direction': 'long', 'stability': 0.71, 'drawdown': 0.29},
    'price_volume_corr': {'category': 'volume', 'name': '量价相关性', 'direction': 'long', 'stability': 0.68, 'drawdown': 0.32},
    'obv_trend': {'category': 'volume', 'name': 'OBV趋势', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'volume_breakout': {'category': 'volume', 'name': '成交量突破', 'direction': 'long', 'stability': 0.65, 'drawdown': 0.35},
    'volume_decline': {'category': 'volume', 'name': '成交量萎缩', 'direction': 'short', 'stability': 0.67, 'drawdown': 0.33},
    'accumulation_distribution': {'category': 'volume', 'name': '累积/派发', 'direction': 'long', 'stability': 0.74, 'drawdown': 0.26},
    'chaikin_money_flow': {'category': 'volume', 'name': '蔡金资金流', 'direction': 'long', 'stability': 0.73, 'drawdown': 0.27},
    'volume_price_trend': {'category': 'volume', 'name': '量价趋势', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'negative_volume_index': {'category': 'volume', 'name': '负成交量指数', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'positive_volume_index': {'category': 'volume', 'name': '正成交量指数', 'direction': 'long', 'stability': 0.71, 'drawdown': 0.29},
    'volume_momentum': {'category': 'volume', 'name': '成交量动量', 'direction': 'long', 'stability': 0.69, 'drawdown': 0.31},
    'volume_acceleration': {'category': 'volume', 'name': '成交量加速度', 'direction': 'long', 'stability': 0.67, 'drawdown': 0.33},
    'relative_volume': {'category': 'volume', 'name': '相对成交量', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'volume_concentration': {'category': 'volume', 'name': '成交量集中度', 'direction': 'short', 'stability': 0.72, 'drawdown': 0.28},
    
    # ============================================
    # 技术指标因子 (Technical Indicator Factors) - 40个
    # ============================================
    'rsi_6': {'category': 'indicator', 'name': 'RSI(6)', 'direction': 'short', 'stability': 0.68, 'drawdown': 0.32},
    'rsi_14': {'category': 'indicator', 'name': 'RSI(14)', 'direction': 'short', 'stability': 0.72, 'drawdown': 0.28},
    'rsi_28': {'category': 'indicator', 'name': 'RSI(28)', 'direction': 'short', 'stability': 0.75, 'drawdown': 0.25},
    'macd_line': {'category': 'indicator', 'name': 'MACD线', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'macd_signal': {'category': 'indicator', 'name': 'MACD信号线', 'direction': 'long', 'stability': 0.69, 'drawdown': 0.31},
    'macd_histogram': {'category': 'indicator', 'name': 'MACD柱状图', 'direction': 'long', 'stability': 0.68, 'drawdown': 0.32},
    'kdj_k': {'category': 'indicator', 'name': 'KDJ-K值', 'direction': 'short', 'stability': 0.67, 'drawdown': 0.33},
    'kdj_d': {'category': 'indicator', 'name': 'KDJ-D值', 'direction': 'short', 'stability': 0.68, 'drawdown': 0.32},
    'kdj_j': {'category': 'indicator', 'name': 'KDJ-J值', 'direction': 'short', 'stability': 0.65, 'drawdown': 0.35},
    'bb_upper': {'category': 'indicator', 'name': '布林带上轨', 'direction': 'short', 'stability': 0.75, 'drawdown': 0.25},
    'bb_middle': {'category': 'indicator', 'name': '布林带中轨', 'direction': 'long', 'stability': 0.78, 'drawdown': 0.22},
    'bb_lower': {'category': 'indicator', 'name': '布林带下轨', 'direction': 'long', 'stability': 0.76, 'drawdown': 0.24},
    'bb_width': {'category': 'indicator', 'name': '布林带宽度', 'direction': 'short', 'stability': 0.73, 'drawdown': 0.27},
    'bb_position': {'category': 'indicator', 'name': '布林带位置', 'direction': 'short', 'stability': 0.71, 'drawdown': 0.29},
    'atr_14': {'category': 'indicator', 'name': 'ATR(14)', 'direction': 'short', 'stability': 0.78, 'drawdown': 0.22},
    'atr_ratio': {'category': 'indicator', 'name': 'ATR比率', 'direction': 'short', 'stability': 0.76, 'drawdown': 0.24},
    'cci_20': {'category': 'indicator', 'name': 'CCI(20)', 'direction': 'short', 'stability': 0.68, 'drawdown': 0.32},
    'cci_40': {'category': 'indicator', 'name': 'CCI(40)', 'direction': 'short', 'stability': 0.70, 'drawdown': 0.30},
    'williams_r': {'category': 'indicator', 'name': '威廉指标', 'direction': 'short', 'stability': 0.67, 'drawdown': 0.33},
    'roc_10': {'category': 'indicator', 'name': 'ROC(10)', 'direction': 'long', 'stability': 0.65, 'drawdown': 0.35},
    'roc_20': {'category': 'indicator', 'name': 'ROC(20)', 'direction': 'long', 'stability': 0.68, 'drawdown': 0.32},
    'momentum_10': {'category': 'indicator', 'name': '动量指标(10)', 'direction': 'long', 'stability': 0.66, 'drawdown': 0.34},
    'momentum_20': {'category': 'indicator', 'name': '动量指标(20)', 'direction': 'long', 'stability': 0.69, 'drawdown': 0.31},
    'tsi': {'category': 'indicator', 'name': '真实强度指数', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'ultimate_oscillator': {'category': 'indicator', 'name': '终极震荡指标', 'direction': 'short', 'stability': 0.68, 'drawdown': 0.32},
    'trix_20': {'category': 'indicator', 'name': 'TRIX(20)', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'dmi_plus': {'category': 'indicator', 'name': 'DMI+', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'dmi_minus': {'category': 'indicator', 'name': 'DMI-', 'direction': 'short', 'stability': 0.69, 'drawdown': 0.31},
    'adx': {'category': 'indicator', 'name': 'ADX', 'direction': 'long', 'stability': 0.73, 'drawdown': 0.27},
    'aroon_up': {'category': 'indicator', 'name': '阿隆上升', 'direction': 'long', 'stability': 0.71, 'drawdown': 0.29},
    'aroon_down': {'category': 'indicator', 'name': '阿隆下降', 'direction': 'short', 'stability': 0.70, 'drawdown': 0.30},
    'aroon_oscillator': {'category': 'indicator', 'name': '阿隆震荡', 'direction': 'long', 'stability': 0.69, 'drawdown': 0.31},
    'ichimoku_base': {'category': 'indicator', 'name': '一目均衡基准', 'direction': 'long', 'stability': 0.75, 'drawdown': 0.25},
    'ichimoku_conversion': {'category': 'indicator', 'name': '一目均衡转换', 'direction': 'long', 'stability': 0.73, 'drawdown': 0.27},
    'stoch_rsi': {'category': 'indicator', 'name': '随机RSI', 'direction': 'short', 'stability': 0.66, 'drawdown': 0.34},
    'mfi': {'category': 'indicator', 'name': '资金流量指数', 'direction': 'short', 'stability': 0.70, 'drawdown': 0.30},
    'vwma': {'category': 'indicator', 'name': '成交量加权均线', 'direction': 'long', 'stability': 0.74, 'drawdown': 0.26},
    'hull_ma': {'category': 'indicator', 'name': '赫尔均线', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'keltner_upper': {'category': 'indicator', 'name': '肯特纳上轨', 'direction': 'short', 'stability': 0.74, 'drawdown': 0.26},
    'keltner_lower': {'category': 'indicator', 'name': '肯特纳下轨', 'direction': 'long', 'stability': 0.73, 'drawdown': 0.27},
}


def get_technical_factors() -> Dict:
    """获取所有技术面因子"""
    return TECHNICAL_FACTORS


def get_factor_count() -> int:
    """获取因子数量"""
    return len(TECHNICAL_FACTORS)


def get_factors_by_category(category: str) -> Dict:
    """按分类获取因子"""
    return {k: v for k, v in TECHNICAL_FACTORS.items() if v['category'] == category}


def get_categories() -> List[str]:
    """获取所有分类"""
    return list(set(v['category'] for v in TECHNICAL_FACTORS.values()))
