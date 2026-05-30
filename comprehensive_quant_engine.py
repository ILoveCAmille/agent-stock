#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合量化因子引擎
整合技术指标、资金流向、散户情绪、经济周期、股票基本面五大维度
为综合买卖决策提供多因子评分

回测模式下，使用可从历史数据中计算的代理指标来近似实时数据
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from quant_factors import QuantFactors


class ComprehensiveQuantEngine:
    """综合量化因子引擎 - 五大维度评分系统（支持市值自适应权重）"""
    
    # 各维度默认权重（中等市值平衡型）
    DEFAULT_WEIGHTS = {
        'technical': 0.30,      # 技术指标
        'fund_flow': 0.25,      # 资金流向
        'sentiment': 0.15,      # 散户情绪
        'macro_cycle': 0.15,    # 经济周期
        'fundamental': 0.15,    # 股票基本面
    }
    
    # 市值自适应权重预设
    # 小市值/妖股：技术指标和散户情绪占主导（价格波动大，受情绪驱动明显）
    # 大市值/蓝筹股：基本面和行业发展逻辑占主导（机构持仓多，估值驱动）
    CAP_STYLE_WEIGHTS = {
        'small_cap': {
            'name': '小市值/妖股风格',
            'description': '技术指标和情绪驱动为主，资金流向辅助确认',
            'weights': {
                'technical': 0.40,      # 技术指标权重最高
                'fund_flow': 0.20,      # 资金流向（游资行为）
                'sentiment': 0.25,      # 散户情绪权重高（妖股特征）
                'macro_cycle': 0.05,    # 经济周期影响小
                'fundamental': 0.10,    # 基本面参考权重低
            }
        },
        'mid_cap': {
            'name': '中等市值风格',
            'description': '技术与基本面平衡，兼顾资金和情绪',
            'weights': {
                'technical': 0.30,
                'fund_flow': 0.25,
                'sentiment': 0.15,
                'macro_cycle': 0.15,
                'fundamental': 0.15,
            }
        },
        'large_cap': {
            'name': '大市值/蓝筹风格',
            'description': '基本面和行业逻辑驱动为主，宏观周期辅助判断',
            'weights': {
                'technical': 0.15,      # 技术指标权重降低
                'fund_flow': 0.20,      # 资金流向（机构动向）
                'sentiment': 0.05,      # 散户情绪影响小
                'macro_cycle': 0.25,    # 经济周期权重高
                'fundamental': 0.35,    # 基本面权重最高
            }
        },
    }
    
    # 市值阈值（单位：亿元）
    CAP_THRESHOLDS = {
        'small_cap_max': 100,      # 小市值上限100亿
        'large_cap_min': 500,      # 大市值下限500亿
    }
    
    def __init__(self, weights: Dict[str, float] = None, cap_style: str = None):
        """
        初始化引擎
        
        Args:
            weights: 自定义权重（优先级最高）
            cap_style: 市值风格 ('small_cap', 'mid_cap', 'large_cap')
                      设置后自动使用对应的市值自适应权重
        """
        self.logger = logging.getLogger(__name__)
        self.qf = QuantFactors()
        
        if weights:
            self.weights = weights
        elif cap_style and cap_style in self.CAP_STYLE_WEIGHTS:
            self.weights = self.CAP_STYLE_WEIGHTS[cap_style]['weights']
            self.logger.info(f"使用{self.CAP_STYLE_WEIGHTS[cap_style]['name']}权重")
        else:
            self.weights = self.DEFAULT_WEIGHTS
    
    @staticmethod
    def detect_cap_style(market_cap: float = None, stock_code: str = None,
                          avg_amount: float = None) -> str:
        """
        根据市值或股票特征自动检测市值风格
        
        Args:
            market_cap: 总市值（亿元）
            stock_code: 股票代码（通过代码前缀辅助判断）
            avg_amount: 日均成交额（万元，作为辅助判断指标）
        
        Returns:
            'small_cap', 'mid_cap', 'large_cap'
        """
        # 优先通过市值判断
        if market_cap is not None:
            if market_cap < ComprehensiveQuantEngine.CAP_THRESHOLDS['small_cap_max']:
                return 'small_cap'
            elif market_cap >= ComprehensiveQuantEngine.CAP_THRESHOLDS['large_cap_min']:
                return 'large_cap'
            else:
                return 'mid_cap'
        
        # 通过股票代码前缀辅助判断（A股规则）
        if stock_code is not None:
            code = str(stock_code).zfill(6)
            # 创业板(300)/科创板(688)/北交所(8xx) 通常小盘股多
            if code.startswith('300') or code.startswith('301'):
                return 'small_cap'  # 创业板偏向小盘成长
            elif code.startswith('688') or code.startswith('689'):
                return 'small_cap'  # 科创板偏向小盘科技
            elif code.startswith('8'):
                return 'small_cap'  # 北交所偏向小盘
            # 沪深主板大市值
            elif code.startswith('60') and not code.startswith('688'):
                return 'mid_cap'    # 上海主板中等偏大
            elif code.startswith('000'):
                return 'mid_cap'    # 深圳主板中等
        
        # 通过日均成交额辅助判断
        if avg_amount is not None:
            if avg_amount < 5000:     # 日均成交额<5000万
                return 'small_cap'
            elif avg_amount > 50000:  # 日均成交额>5亿
                return 'large_cap'
        
        return 'mid_cap'
    
    @staticmethod
    def compute_adaptive_weights(market_cap: float = None, stock_code: str = None,
                                  avg_amount: float = None,
                                  volatility_regime: float = None) -> Dict[str, float]:
        """
        计算自适应权重（综合考虑市值和市场环境）
        
        Args:
            market_cap: 总市值（亿元）
            stock_code: 股票代码
            avg_amount: 日均成交额（万元）
            volatility_regime: 当前波动率水平（ATR百分比）
        
        Returns:
            调整后的权重字典
        """
        engine_cls = ComprehensiveQuantEngine
        cap_style = engine_cls.detect_cap_style(market_cap, stock_code, avg_amount)
        weights = dict(engine_cls.CAP_STYLE_WEIGHTS[cap_style]['weights'])
        
        # 根据波动率微调：高波动时增加技术指标和情绪权重
        if volatility_regime is not None:
            if volatility_regime > 5:  # 高波动
                weights['technical'] += 0.05
                weights['sentiment'] += 0.05
                weights['macro_cycle'] -= 0.05
                weights['fundamental'] -= 0.05
            elif volatility_regime < 1.5:  # 低波动
                weights['fundamental'] += 0.05
                weights['macro_cycle'] += 0.05
                weights['technical'] -= 0.05
                weights['sentiment'] -= 0.05
        
        # 确保权重非负且总和为1
        for k in weights:
            weights[k] = max(0.02, weights[k])
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}
        
        return weights
    
    # ==================== 技术指标维度 ====================
    
    def compute_technical_score(self, df: pd.DataFrame) -> pd.Series:
        """
        计算技术指标综合评分 (0-100)
        
        整合以下技术因子:
        - RSI动量
        - MACD趋势
        - 布林带位置
        - 均线排列
        - ADX趋势强度
        - KDJ超买超卖
        - 量价关系
        """
        scores = pd.DataFrame(index=df.index)
        
        # 1. RSI评分 (权重20%)
        rsi = df['RSI_14'] if 'RSI_14' in df.columns else QuantFactors.rsi(df['Close'], 14)
        scores['rsi'] = np.where(
            rsi < 30, 80 + (30 - rsi),
            np.where(rsi > 70, 30 - (rsi - 70), 50 + (rsi - 50) * 0.5)
        ).clip(0, 100)
        
        # 2. MACD评分 (权重20%)
        if 'MACD' in df.columns and 'MACD_signal' in df.columns:
            macd = df['MACD']
            macd_signal = df['MACD_signal']
            macd_hist = df.get('MACD_histogram', macd - macd_signal)
            # MACD金叉/死叉 + 柱状图方向
            macd_cross = np.where(macd > macd_signal, 1, -1)
            macd_momentum = np.where(macd_hist > macd_hist.shift(1), 1, -1)
            scores['macd'] = (50 + macd_cross * 20 + macd_momentum * 10).clip(0, 100)
        else:
            # 使用自定义MACD
            ema12 = df['Close'].ewm(span=12, adjust=False).mean()
            ema26 = df['Close'].ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            histogram = macd_line - signal_line
            macd_cross = np.where(macd_line > signal_line, 1, -1)
            macd_momentum = np.where(histogram > histogram.shift(1), 1, -1)
            scores['macd'] = (50 + macd_cross * 20 + macd_momentum * 10).clip(0, 100)
        
        # 3. 布林带位置评分 (权重15%)
        if 'BB_upper' in df.columns and 'BB_lower' in df.columns:
            bb_upper = df['BB_upper']
            bb_lower = df['BB_lower']
            bb_middle = df.get('BB_middle', (bb_upper + bb_lower) / 2)
        else:
            bb_middle = df['Close'].rolling(20).mean()
            bb_std = df['Close'].rolling(20).std()
            bb_upper = bb_middle + 2 * bb_std
            bb_lower = bb_middle - 2 * bb_std
        
        bb_width = bb_upper - bb_lower
        bb_position = np.where(bb_width > 0, (df['Close'] - bb_lower) / bb_width, 0.5)
        # 越接近下轨越有买入价值，越接近上轨越需要卖出
        scores['bollinger'] = (100 - bb_position * 100).clip(0, 100)
        
        # 4. 均线排列评分 (权重15%)
        ma5 = df['Close'].rolling(5).mean()
        ma10 = df['Close'].rolling(10).mean()
        ma20 = df['Close'].rolling(20).mean()
        ma60 = df['Close'].rolling(60).mean()
        
        alignment = pd.Series(0.0, index=df.index)
        alignment += np.where(ma5 > ma10, 0.25, -0.25)
        alignment += np.where(ma10 > ma20, 0.25, -0.25)
        alignment += np.where(ma20 > ma60, 0.25, -0.25)
        alignment += np.where(ma5 > ma60, 0.25, -0.25)
        scores['ma_alignment'] = (50 + alignment * 50).clip(0, 100)
        
        # 5. ADX趋势强度评分 (权重10%)
        adx_val = df['ADX'] if 'ADX' in df.columns else QuantFactors.adx(df['High'], df['Low'], df['Close'])
        trend = df['Trend_Strength'] if 'Trend_Strength' in df.columns else QuantFactors.trend_strength(df['Close'])
        
        trend_score = np.where(
            adx_val > 25,
            np.where(trend > 0, 60 + np.minimum(adx_val - 25, 30), 40 - np.minimum(np.abs(trend), 30)),
            40 + adx_val * 0.4
        )
        scores['trend'] = pd.Series(trend_score, index=df.index).clip(0, 100)
        
        # 6. KDJ/随机RSI评分 (权重10%)
        stoch_k = df.get('Stoch_K', None)
        if stoch_k is None:
            rsi_val = df['RSI_14'] if 'RSI_14' in df.columns else QuantFactors.rsi(df['Close'], 14)
            stoch_k = ((rsi_val - rsi_val.rolling(14).min()) / 
                       (rsi_val.rolling(14).max() - rsi_val.rolling(14).min())) * 100
        
        scores['kdj'] = (100 - stoch_k).clip(0, 100)
        
        # 7. 量价关系评分 (权重10%)
        vol_ma5 = df['Volume'].rolling(5).mean()
        vol_ma20 = df['Volume'].rolling(20).mean()
        vol_ratio = np.where(vol_ma5 > 0, df['Volume'] / vol_ma5, 1)
        price_up = np.where(df['Close'] > df['Close'].shift(1), 1, 0)
        # 价涨量增=好，价涨量缩=背离(差)
        vol_price_score = np.where(
            price_up & (vol_ratio > 1.2), 75,  # 放量上涨
            np.where(price_up & (vol_ratio < 0.8), 45,  # 缩量上涨(顶背离风险)
            np.where(~price_up & (vol_ratio > 1.2), 30,  # 放量下跌
            np.where(~price_up & (vol_ratio < 0.8), 60,  # 缩量下跌(底背离机会)
            50))))  # 正常
        scores['vol_price'] = pd.Series(vol_price_score, index=df.index).clip(0, 100)
        
        # 加权综合技术评分
        weights = {
            'rsi': 0.20,
            'macd': 0.20,
            'bollinger': 0.15,
            'ma_alignment': 0.15,
            'trend': 0.10,
            'kdj': 0.10,
            'vol_price': 0.10
        }
        
        total = pd.Series(0.0, index=df.index)
        for factor, w in weights.items():
            total += scores[factor].fillna(50) * w
        
        return total.clip(0, 100)
    
    # ==================== 资金流向维度 ====================
    
    def compute_fund_flow_score(self, df: pd.DataFrame) -> pd.Series:
        """
        计算资金流向评分 (0-100)
        
        回测模式下使用量价代理指标:
        - 主力资金代理: 大单占比(通过成交量异常检测)
        - 资金动量: OBV趋势
        - 资金集中度: 量比和换手率
        - VWAP偏离度: 价格相对于VWAP的位置
        """
        scores = pd.DataFrame(index=df.index)
        
        # 1. OBV趋势 (代理主力资金动向)
        obv = QuantFactors.obv(df['Close'], df['Volume'])
        obv_ma20 = obv.rolling(20).mean()
        obv_ma5 = obv.rolling(5).mean()
        # OBV短期均线在长期均线上方 = 资金持续流入
        obv_signal = np.where(obv_ma5 > obv_ma20, 1, -1)
        obv_strength = np.abs(obv_ma5 - obv_ma20) / (np.abs(obv_ma20) + 1e-10) * 100
        obv_strength = np.minimum(obv_strength, 30)  # 限制范围
        scores['obv'] = (50 + obv_signal * obv_strength).clip(0, 100)
        
        # 2. 量比分析 (代理大单活跃度)
        vol_ma5 = df['Volume'].rolling(5).mean()
        vol_ma20 = df['Volume'].rolling(20).mean()
        vol_ratio_5 = np.where(vol_ma5 > 0, df['Volume'] / vol_ma5, 1)
        vol_ratio_20 = np.where(vol_ma20 > 0, df['Volume'] / vol_ma20, 1)
        
        # 放量伴随上涨 = 主力资金流入
        price_change = df['Close'].pct_change()
        fund_direction = np.where(
            (vol_ratio_5 > 1.3) & (price_change > 0), 80,  # 放量上涨，主力资金流入
            np.where(
                (vol_ratio_5 > 1.3) & (price_change < 0), 25,  # 放量下跌，主力资金流出
                np.where(
                    (vol_ratio_5 < 0.7) & (price_change > 0), 55,  # 缩量上涨，散户推动
                    np.where(
                        (vol_ratio_5 < 0.7) & (price_change < 0), 45,  # 缩量下跌，自然调整
                        50  # 正常
                    )
                )
            )
        )
        scores['vol_direction'] = pd.Series(fund_direction, index=df.index).clip(0, 100)
        
        # 3. VWAP偏离度 (机构成本参考)
        vwap = QuantFactors.vwap(df['High'], df['Low'], df['Close'], df['Volume'], 20)
        vwap_deviation = np.where(vwap > 0, (df['Close'] - vwap) / vwap * 100, 0)
        # 价格低于VWAP = 低于机构成本，有上涨空间
        scores['vwap'] = (50 - vwap_deviation * 5).clip(0, 100)
        
        # 4. 资金集中度 (通过成交量分布判断)
        # 近5日成交量占近20日比例
        vol_concentration = np.where(vol_ma20 > 0, 
                                     df['Volume'].rolling(5).sum() / df['Volume'].rolling(20).sum() * 4,
                                     1)
        # 集中度 > 1 表示近期资金集中流入
        scores['concentration'] = (50 + (vol_concentration - 1) * 50).clip(0, 100)
        
        # 5. 大单代理指标 (通过日内振幅和成交量综合判断)
        # 大阳线+放量 = 主力介入
        daily_range = (df['High'] - df['Low']) / df['Close'] * 100
        body_pct = (df['Close'] - df['Open']) / df['Open'] * 100
        big_move = np.where(
            (body_pct > 2) & (vol_ratio_5 > 1.5), 80,  # 大阳线放量
            np.where(
                (body_pct < -2) & (vol_ratio_5 > 1.5), 20,  # 大阴线放量
                50
            )
        )
        scores['big_move'] = pd.Series(big_move, index=df.index).clip(0, 100)
        
        # 加权综合资金评分
        weights = {
            'obv': 0.25,
            'vol_direction': 0.25,
            'vwap': 0.20,
            'concentration': 0.15,
            'big_move': 0.15
        }
        
        total = pd.Series(0.0, index=df.index)
        for factor, w in weights.items():
            total += scores[factor].fillna(50) * w
        
        return total.clip(0, 100)
    
    # ==================== 散户情绪维度 ====================
    
    def compute_sentiment_score(self, df: pd.DataFrame, 
                                 market_df: pd.DataFrame = None) -> pd.Series:
        """
        计算散户情绪评分 (0-100)
        
        代理指标:
        - ARBR情绪指标 (人气指标和意愿指标)
        - 换手率异常
        - 涨跌停效应 (通过极端涨跌幅检测)
        - 市场恐慌贪婪 (通过波动率和趋势)
        - 散户行为模式 (追涨杀跌检测)
        """
        scores = pd.DataFrame(index=df.index)
        
        # 1. AR指标 (人气指标) - 代理散户情绪热度
        ho = df['High'] - df['Open']
        ol = df['Open'] - df['Low']
        ar = (ho.rolling(26).sum() / ol.rolling(26).sum() * 100).replace([np.inf, -np.inf], np.nan)
        # AR > 150 过热(卖出), AR < 70 过冷(买入)
        ar_score = np.where(
            ar > 180, 15,
            np.where(ar > 150, 30,
            np.where(ar < 40, 90,
            np.where(ar < 70, 75,
            50 + (ar - 100) * 0.2))))
        scores['ar'] = pd.Series(ar_score, index=df.index).clip(0, 100)
        
        # 2. BR指标 (意愿指标) - 代理投机情绪
        hcy = df['High'] - df['Close'].shift(1)
        cyl = df['Close'].shift(1) - df['Low']
        br = (hcy.rolling(26).sum() / cyl.rolling(26).sum() * 100).replace([np.inf, -np.inf], np.nan)
        br_score = np.where(
            br > 400, 15,
            np.where(br > 300, 30,
            np.where(br < 30, 90,
            np.where(br < 50, 75,
            50 + (br - 150) * 0.15))))
        scores['br'] = pd.Series(br_score, index=df.index).clip(0, 100)
        
        # 3. 换手率异常 (散户活跃度代理)
        vol_ma20 = df['Volume'].rolling(20).mean()
        turnover_ratio = np.where(vol_ma20 > 0, df['Volume'] / vol_ma20, 1)
        # 极高换手率 = 散户蜂拥(反向指标)
        turnover_score = np.where(
            turnover_ratio > 3, 25,  # 极度活跃，可能见顶
            np.where(turnover_ratio > 2, 35,
            np.where(turnover_ratio < 0.3, 70,  # 极度低迷，可能见底
            np.where(turnover_ratio < 0.5, 60,
            50 + (1 - turnover_ratio) * 10))))
        scores['turnover'] = pd.Series(turnover_score, index=df.index).clip(0, 100)
        
        # 4. 散户追涨杀跌检测
        # 连续上涨天数
        up_days = pd.Series(0, index=df.index, dtype=int)
        for i in range(1, len(df)):
            if df['Close'].iloc[i] > df['Close'].iloc[i-1]:
                up_days.iloc[i] = up_days.iloc[i-1] + 1 if up_days.iloc[i-1] > 0 else 1
            else:
                up_days.iloc[i] = up_days.iloc[i-1] - 1 if up_days.iloc[i-1] < 0 else -1
        
        # 连续上涨过多 = 散户追涨(反向), 连续下跌过多 = 散户杀跌(反向)
        chase_score = np.where(
            up_days > 5, 30,  # 连续上涨过多
            np.where(up_days > 3, 40,
            np.where(up_days < -5, 75,  # 连续下跌过多(反弹机会)
            np.where(up_days < -3, 65,
            50))))
        scores['chase'] = pd.Series(chase_score, index=df.index).clip(0, 100)
        
        # 5. 波动率恐慌指标
        atr_pct = QuantFactors.atr_percent(df['High'], df['Low'], df['Close'], 14)
        # 高波动率 = 恐慌, 低波动率 = 平静
        vol_score = np.where(
            atr_pct > 5, 70,  # 高波动，恐慌抛售后可能反弹
            np.where(atr_pct > 3, 55,
            np.where(atr_pct < 1, 45,  # 低波动，平静期
            50)))
        scores['volatility_fear'] = pd.Series(vol_score, index=df.index).clip(0, 100)
        
        # 如果有大盘数据，计算市场整体情绪
        if market_df is not None and not market_df.empty:
            market_change = market_df['Close'].pct_change()
            market_ma20 = market_df['Close'].rolling(20).mean()
            market_trend = np.where(market_df['Close'] > market_ma20, 1, -1)
            market_score = (50 + market_trend * 15).clip(0, 100)
            scores['market_mood'] = pd.Series(market_score, index=market_df.index).reindex(df.index, method='ffill').fillna(50)
        else:
            scores['market_mood'] = pd.Series(50, index=df.index)
        
        # 加权综合情绪评分
        weights = {
            'ar': 0.20,
            'br': 0.20,
            'turnover': 0.15,
            'chase': 0.15,
            'volatility_fear': 0.15,
            'market_mood': 0.15
        }
        
        total = pd.Series(0.0, index=df.index)
        for factor, w in weights.items():
            total += scores[factor].fillna(50) * w
        
        return total.clip(0, 100)
    
    # ==================== 经济周期维度 ====================
    
    def compute_macro_cycle_score(self, df: pd.DataFrame,
                                   market_df: pd.DataFrame = None) -> pd.Series:
        """
        计算经济周期评分 (0-100)
        
        回测模式下使用市场代理指标:
        - 市场趋势周期 (长中短期均线判断牛熊)
        - 市场宽度 (通过个股与大盘的相关性)
        - 市场波动率周期 (VIX代理)
        - 季节性因子
        - 美林时钟代理 (通过市场风格判断)
        """
        scores = pd.DataFrame(index=df.index)
        
        # 使用大盘数据作为经济周期代理
        if market_df is not None and not market_df.empty:
            ref = market_df
        else:
            ref = df  # 如果没有大盘数据，用个股数据代替
        
        close = ref['Close']
        
        # 1. 市场趋势周期 (长期均线判断牛熊)
        ma60 = close.rolling(60).mean()
        ma120 = close.rolling(120).mean()
        ma250 = close.rolling(250).mean()
        
        # 牛市/熊市判断
        bull_bear = np.where(
            (close > ma60) & (ma60 > ma120) & (ma120 > ma250), 80,  # 完全牛市
            np.where(
                (close > ma60) & (ma60 > ma120), 70,  # 中期牛市
                np.where(
                    close > ma60, 60,  # 短期上涨
                    np.where(
                        (close < ma60) & (ma60 < ma120) & (ma120 < ma250), 20,  # 完全熊市
                        np.where(
                            (close < ma60) & (ma60 < ma120), 30,  # 中期熊市
                            np.where(close < ma60, 40,  # 短期下跌
                            50)
                        )
                    )
                )
            )
        )
        scores['market_cycle'] = pd.Series(bull_bear, index=ref.index).reindex(df.index, method='ffill').fillna(50)
        
        # 2. 市场动量周期 (中期动量)
        mom_20 = close.pct_change(20) * 100
        mom_60 = close.pct_change(60) * 100
        
        momentum_score = np.where(
            (mom_20 > 5) & (mom_60 > 10), 80,  # 强势上涨
            np.where(mom_20 > 0, 60,  # 温和上涨
            np.where(mom_20 > -5, 45,  # 小幅下跌
            np.where(mom_60 < -10, 25,  # 持续下跌
            35))))
        scores['momentum'] = pd.Series(momentum_score, index=ref.index).reindex(df.index, method='ffill').fillna(50)
        
        # 3. 波动率周期 (市场恐慌/贪婪代理)
        volatility = close.pct_change().rolling(20).std() * np.sqrt(252) * 100
        vol_score = np.where(
            volatility > 40, 30,  # 高波动(恐慌期)
            np.where(volatility > 25, 40,
            np.where(volatility < 10, 65,  # 低波动(平静期，适合入场)
            50)))
        scores['vol_cycle'] = pd.Series(vol_score, index=ref.index).reindex(df.index, method='ffill').fillna(50)
        
        # 4. 季节性因子 (A股日历效应)
        if hasattr(df.index, 'month'):
            month = df.index.month
        elif isinstance(df.index, pd.DatetimeIndex):
            month = df.index.month
        else:
            month = pd.Series(6, index=df.index)  # 默认中性
        
        # A股季节性: 1月效应, 春季躁动, 金九银十
        seasonal_score = np.where(
            (month == 1) | (month == 2), 65,  # 春季躁动
            np.where(month == 3, 60,
            np.where((month >= 4) & (month <= 5), 55,
            np.where((month >= 6) & (month <= 8), 45,  # 五穷六绝
            np.where((month >= 9) & (month <= 10), 55,  # 金九银十
            np.where(month >= 11, 50,  # 年末
            50))))))
        scores['seasonal'] = pd.Series(seasonal_score, index=df.index).clip(0, 100)
        
        # 5. 利率环境代理 (通过银行股和债券相关指标)
        # 简化: 使用市场PE估值分位数代理
        pe_proxy = close / close.rolling(252).mean()  # 价格相对于年均线的位置
        rate_score = np.where(
            pe_proxy > 1.3, 35,  # 估值偏高
            np.where(pe_proxy > 1.1, 45,
            np.where(pe_proxy < 0.8, 75,  # 估值偏低
            np.where(pe_proxy < 0.9, 65,
            55))))
        scores['rate_env'] = pd.Series(rate_score, index=ref.index).reindex(df.index, method='ffill').fillna(50)
        
        # 加权综合经济周期评分
        weights = {
            'market_cycle': 0.30,
            'momentum': 0.25,
            'vol_cycle': 0.20,
            'seasonal': 0.10,
            'rate_env': 0.15
        }
        
        total = pd.Series(0.0, index=df.index)
        for factor, w in weights.items():
            total += scores[factor].fillna(50) * w
        
        return total.clip(0, 100)
    
    # ==================== 股票基本面维度 ====================
    
    def compute_fundamental_score(self, df: pd.DataFrame,
                                   pe_ratio: float = None,
                                   pb_ratio: float = None,
                                   roe: float = None,
                                   revenue_growth: float = None,
                                   profit_growth: float = None) -> pd.Series:
        """
        计算股票基本面评分 (0-100)
        
        对于回测，基本面变化较慢，使用提供的静态值或从价格趋势中推断
        
        Args:
            df: OHLCV数据
            pe_ratio: 市盈率 (可选)
            pb_ratio: 市净率 (可选)
            roe: 净资产收益率 (可选)
            revenue_growth: 营收增长率 (可选)
            profit_growth: 净利润增长率 (可选)
        """
        scores = pd.DataFrame(index=df.index)
        
        # 1. 盈利能力评分
        if roe is not None:
            if roe > 20:
                profit_score = 85
            elif roe > 15:
                profit_score = 75
            elif roe > 10:
                profit_score = 65
            elif roe > 5:
                profit_score = 50
            else:
                profit_score = 35
        else:
            # 从价格趋势推断盈利能力 (持续上涨的股票通常基本面较好)
            ma120 = df['Close'].rolling(120).mean()
            price_above_ma120 = np.where(df['Close'] > ma120, 1, 0)
            profit_score_arr = np.where(price_above_ma120, 65, 40)
            profit_score = pd.Series(profit_score_arr, index=df.index).fillna(50)
        
        if isinstance(profit_score, (int, float)):
            scores['profitability'] = profit_score
        else:
            scores['profitability'] = profit_score
        
        # 2. 估值水平评分
        if pe_ratio is not None:
            if 0 < pe_ratio < 10:
                valuation_score = 85  # 极低估值
            elif pe_ratio < 15:
                valuation_score = 75
            elif pe_ratio < 25:
                valuation_score = 60
            elif pe_ratio < 40:
                valuation_score = 45
            elif pe_ratio < 60:
                valuation_score = 35
            else:
                valuation_score = 20  # 高估值
        else:
            # 从价格相对位置推断估值
            pct_from_high = (df['Close'].rolling(252).max() - df['Close']) / df['Close'].rolling(252).max() * 100
            valuation_score = (40 + pct_from_high * 0.8).clip(20, 85)
        
        if isinstance(valuation_score, (int, float)):
            scores['valuation'] = valuation_score
        else:
            scores['valuation'] = valuation_score
        
        # 3. 成长性评分
        if revenue_growth is not None and profit_growth is not None:
            growth = (revenue_growth + profit_growth) / 2
            if growth > 30:
                growth_score = 90
            elif growth > 20:
                growth_score = 80
            elif growth > 10:
                growth_score = 70
            elif growth > 0:
                growth_score = 55
            else:
                growth_score = 30
        else:
            # 从中期价格动量推断成长性
            mom_60 = df['Close'].pct_change(60) * 100
            growth_score = (50 + mom_60 * 1.5).clip(20, 90)
        
        if isinstance(growth_score, (int, float)):
            scores['growth'] = growth_score
        else:
            scores['growth'] = growth_score
        
        # 4. 财务健康度
        if pb_ratio is not None:
            if 0 < pb_ratio < 1:
                health_score = 80  # 破净，价值洼地
            elif pb_ratio < 2:
                health_score = 70
            elif pb_ratio < 3:
                health_score = 55
            elif pb_ratio < 5:
                health_score = 40
            else:
                health_score = 30
        else:
            # 从波动率推断财务健康度 (低波动通常意味着基本面稳定)
            atr_pct = QuantFactors.atr_percent(df['High'], df['Low'], df['Close'], 20)
            health_score = (60 - atr_pct * 5).clip(20, 80)
        
        if isinstance(health_score, (int, float)):
            scores['health'] = health_score
        else:
            scores['health'] = health_score
        
        # 5. 市值因子 (大盘股通常更稳定)
        # 使用价格*成交量作为市值代理
        avg_amount = df['Volume'] * df['Close']
        amount_ma = avg_amount.rolling(60).mean()
        amount_rank = amount_ma.rank(pct=True) * 100
        cap_score = (40 + amount_rank * 0.3).clip(30, 70)
        scores['market_cap'] = cap_score
        
        # 加权综合基本面评分
        weights = {
            'profitability': 0.25,
            'valuation': 0.25,
            'growth': 0.20,
            'health': 0.20,
            'market_cap': 0.10
        }
        
        total = pd.Series(0.0, index=df.index)
        for factor, w in weights.items():
            total += scores[factor].fillna(50) * w
        
        return total.clip(0, 100)
    
    # ==================== 综合评分 ====================
    
    def compute_comprehensive_score(self, df: pd.DataFrame,
                                     market_df: pd.DataFrame = None,
                                     pe_ratio: float = None,
                                     pb_ratio: float = None,
                                     roe: float = None,
                                     revenue_growth: float = None,
                                     profit_growth: float = None,
                                     weights: Dict[str, float] = None) -> pd.DataFrame:
        """
        计算五维度综合评分
        
        Args:
            df: OHLCV数据 (必须包含 Open, High, Low, Close, Volume)
            market_df: 大盘指数数据 (可选，用于宏观周期和情绪分析)
            pe_ratio: 市盈率 (可选)
            pb_ratio: 市净率 (可选)
            roe: ROE (可选)
            revenue_growth: 营收增长率 (可选)
            profit_growth: 净利润增长率 (可选)
            weights: 自定义维度权重 (可选)
        
        Returns:
            DataFrame: 添加了各维度评分和综合评分的DataFrame
        """
        w = weights or self.weights
        
        df = df.copy()
        
        # 确保有足够的数据
        if len(df) < 120:
            self.logger.warning(f"数据量不足({len(df)}条)，建议至少120条以上以获得准确评分")
        
        # 计算各维度评分
        self.logger.info("计算技术指标评分...")
        df['Score_Technical'] = self.compute_technical_score(df)
        
        self.logger.info("计算资金流向评分...")
        df['Score_FundFlow'] = self.compute_fund_flow_score(df)
        
        self.logger.info("计算散户情绪评分...")
        df['Score_Sentiment'] = self.compute_sentiment_score(df, market_df)
        
        self.logger.info("计算经济周期评分...")
        df['Score_MacroCycle'] = self.compute_macro_cycle_score(df, market_df)
        
        self.logger.info("计算股票基本面评分...")
        df['Score_Fundamental'] = self.compute_fundamental_score(
            df, pe_ratio, pb_ratio, roe, revenue_growth, profit_growth
        )
        
        # 计算综合评分
        df['Score_Comprehensive'] = (
            df['Score_Technical'] * w['technical'] +
            df['Score_FundFlow'] * w['fund_flow'] +
            df['Score_Sentiment'] * w['sentiment'] +
            df['Score_MacroCycle'] * w['macro_cycle'] +
            df['Score_Fundamental'] * w['fundamental']
        ).clip(0, 100)
        
        # 生成交易信号
        df['Signal'] = 0
        
        # 买入条件: 综合评分高 + 各维度不冲突
        buy_condition = (
            (df['Score_Comprehensive'] > 65) &
            (df['Score_Technical'] > 55) &
            (df['Score_FundFlow'] > 50) &
            (df['Score_Sentiment'] > 40)
        )
        df.loc[buy_condition, 'Signal'] = 1
        
        # 卖出条件: 综合评分低 或 任一关键维度极差
        sell_condition = (
            (df['Score_Comprehensive'] < 35) |
            (df['Score_Technical'] < 25) |
            ((df['Score_FundFlow'] < 30) & (df['Score_Sentiment'] < 35))
        )
        df.loc[sell_condition, 'Signal'] = -1
        
        self.logger.info("综合评分计算完成")
        
        return df
    
    def compute_all_factors(self, df: pd.DataFrame, market_df: pd.DataFrame = None) -> pd.DataFrame:
        """
        计算所有基础技术因子（用于回测引擎）
        
        Args:
            df: 原始OHLCV数据
            market_df: 大盘数据(可选)
        
        Returns:
            添加了所有因子的DataFrame
        """
        df = df.copy()
        
        # 计算基础技术指标
        df['ATR'] = QuantFactors.atr(df['High'], df['Low'], df['Close'])
        df['ATR_pct'] = QuantFactors.atr_percent(df['High'], df['Low'], df['Close'])
        df['ADX'] = QuantFactors.adx(df['High'], df['Low'], df['Close'])
        df['RSI_14'] = QuantFactors.rsi(df['Close'], 14)
        df['RSI_6'] = QuantFactors.rsi(df['Close'], 6)
        df['Trend_Strength'] = QuantFactors.trend_strength(df['Close'])
        df['VPD'] = QuantFactors.volume_price_divergence(df['Close'], df['Volume'])
        df['OBV'] = QuantFactors.obv(df['Close'], df['Volume'])
        df['VWAP'] = QuantFactors.vwap(df['High'], df['Low'], df['Close'], df['Volume'])
        
        # MACD
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_histogram'] = df['MACD'] - df['MACD_signal']
        
        # 布林带
        df['BB_middle'] = df['Close'].rolling(20).mean()
        bb_std = df['Close'].rolling(20).std()
        df['BB_upper'] = df['BB_middle'] + 2 * bb_std
        df['BB_lower'] = df['BB_middle'] - 2 * bb_std
        
        # 均线
        for period in [5, 10, 20, 60, 120, 250]:
            df[f'MA{period}'] = df['Close'].rolling(period).mean()
        
        # 成交量均线
        df['Vol_MA5'] = df['Volume'].rolling(5).mean()
        df['Vol_MA20'] = df['Volume'].rolling(20).mean()
        df['Volume_Ratio'] = np.where(df['Vol_MA5'] > 0, df['Volume'] / df['Vol_MA5'], 1)
        
        return df


# 全局实例
comprehensive_engine = ComprehensiveQuantEngine()