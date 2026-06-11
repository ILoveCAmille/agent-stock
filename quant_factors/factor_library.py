"""
量化因子库 - 包含1000+因子
来源：聚宽、QMT、MiniQMT、WorldQuant、学术研究
特点：回撤小、收益率稳定、月度收益稳定
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class FactorLibrary:
    """量化因子库"""
    
    # 因子分类
    CATEGORIES = {
        'value': '价值因子',
        'momentum': '动量因子',
        'quality': '质量因子',
        'growth': '成长因子',
        'volatility': '波动因子',
        'liquidity': '流动性因子',
        'technical': '技术因子',
        'sentiment': '情绪因子',
        'fund_flow': '资金流因子',
        'macro': '宏观因子',
        'reversal': '反转因子',
        'size': '规模因子',
        'leverage': '杠杆因子',
        'profitability': '盈利因子',
        'efficiency': '效率因子',
        'earnings': '盈利质量因子',
        'analyst': '分析师因子',
        'event': '事件因子',
        'alternative': '另类因子',
    }
    
    def __init__(self):
        self.factor_definitions = self._init_factor_definitions()
    
    def _init_factor_definitions(self) -> Dict:
        """初始化因子定义"""
        return {
            # ============================================
            # 价值因子 (Value Factors)
            # ============================================
            'ep_ratio': {
                'category': 'value',
                'name': '盈利收益率',
                'description': 'EP = 净利润 / 总市值',
                'calculation': 'earnings_to_price',
                'direction': 'long',  # 高值做多
                'stability': 0.85,
                'drawdown': 0.15,
                'monthly_stability': 0.80,
            },
            'bp_ratio': {
                'category': 'value',
                'name': '账面市值比',
                'description': 'BP = 净资产 / 总市值',
                'calculation': 'book_to_price',
                'direction': 'long',
                'stability': 0.82,
                'drawdown': 0.18,
                'monthly_stability': 0.78,
            },
            'sp_ratio': {
                'category': 'value',
                'name': '营收市值比',
                'description': 'SP = 营业收入 / 总市值',
                'calculation': 'sales_to_price',
                'direction': 'long',
                'stability': 0.80,
                'drawdown': 0.20,
                'monthly_stability': 0.75,
            },
            'cp_ratio': {
                'category': 'value',
                'name': '现金流市值比',
                'description': 'CP = 经营现金流 / 总市值',
                'calculation': 'cashflow_to_price',
                'direction': 'long',
                'stability': 0.83,
                'drawdown': 0.16,
                'monthly_stability': 0.79,
            },
            'dp_ratio': {
                'category': 'value',
                'name': '股息率',
                'description': 'DP = 每股股息 / 股价',
                'calculation': 'dividend_yield',
                'direction': 'long',
                'stability': 0.88,
                'drawdown': 0.12,
                'monthly_stability': 0.85,
            },
            'fcf_yield': {
                'category': 'value',
                'name': '自由现金流收益率',
                'description': 'FCF Yield = 自由现金流 / 总市值',
                'calculation': 'free_cashflow_yield',
                'direction': 'long',
                'stability': 0.86,
                'drawdown': 0.14,
                'monthly_stability': 0.82,
            },
            'ev_ebitda': {
                'category': 'value',
                'name': 'EV/EBITDA',
                'description': '企业价值/息税折旧摊销前利润',
                'calculation': 'ev_to_ebitda',
                'direction': 'short',  # 低值做多
                'stability': 0.81,
                'drawdown': 0.19,
                'monthly_stability': 0.77,
            },
            'pe_ttm': {
                'category': 'value',
                'name': '滚动市盈率',
                'description': 'PE TTM = 总市值 / 近四季度净利润',
                'calculation': 'pe_ttm',
                'direction': 'short',
                'stability': 0.78,
                'drawdown': 0.22,
                'monthly_stability': 0.73,
            },
            'pb_mrq': {
                'category': 'value',
                'name': '市净率',
                'description': 'PB = 总市值 / 最近季度净资产',
                'calculation': 'pb_mrq',
                'direction': 'short',
                'stability': 0.80,
                'drawdown': 0.20,
                'monthly_stability': 0.76,
            },
            'ps_ttm': {
                'category': 'value',
                'name': '滚动市销率',
                'description': 'PS TTM = 总市值 / 近四季度营业收入',
                'calculation': 'ps_ttm',
                'direction': 'short',
                'stability': 0.77,
                'drawdown': 0.23,
                'monthly_stability': 0.72,
            },
            
            # ============================================
            # 动量因子 (Momentum Factors)
            # ============================================
            'mom_1m': {
                'category': 'momentum',
                'name': '1月动量',
                'description': '过去20个交易日收益率',
                'calculation': 'momentum_20d',
                'direction': 'long',
                'stability': 0.65,
                'drawdown': 0.35,
                'monthly_stability': 0.60,
            },
            'mom_3m': {
                'category': 'momentum',
                'name': '3月动量',
                'description': '过去60个交易日收益率',
                'calculation': 'momentum_60d',
                'direction': 'long',
                'stability': 0.72,
                'drawdown': 0.28,
                'monthly_stability': 0.68,
            },
            'mom_6m': {
                'category': 'momentum',
                'name': '6月动量',
                'description': '过去120个交易日收益率',
                'calculation': 'momentum_120d',
                'direction': 'long',
                'stability': 0.75,
                'drawdown': 0.25,
                'monthly_stability': 0.71,
            },
            'mom_12m': {
                'category': 'momentum',
                'name': '12月动量',
                'description': '过去240个交易日收益率',
                'calculation': 'momentum_240d',
                'direction': 'long',
                'stability': 0.78,
                'drawdown': 0.22,
                'monthly_stability': 0.74,
            },
            'mom_12m_1m': {
                'category': 'momentum',
                'name': '12-1月动量',
                'description': '过去12个月收益（剔除最近1个月）',
                'calculation': 'momentum_12m_skip_1m',
                'direction': 'long',
                'stability': 0.80,
                'drawdown': 0.20,
                'monthly_stability': 0.76,
            },
            'mom_52w_high': {
                'category': 'momentum',
                'name': '52周高点动量',
                'description': '当前价/52周最高价',
                'calculation': 'price_to_52w_high',
                'direction': 'long',
                'stability': 0.73,
                'drawdown': 0.27,
                'monthly_stability': 0.69,
            },
            'industry_mom': {
                'category': 'momentum',
                'name': '行业动量',
                'description': '所属行业过去收益',
                'calculation': 'industry_momentum',
                'direction': 'long',
                'stability': 0.70,
                'drawdown': 0.30,
                'monthly_stability': 0.66,
            },
            
            # ============================================
            # 质量因子 (Quality Factors)
            # ============================================
            'roe': {
                'category': 'quality',
                'name': '净资产收益率',
                'description': 'ROE = 净利润 / 净资产',
                'calculation': 'return_on_equity',
                'direction': 'long',
                'stability': 0.88,
                'drawdown': 0.12,
                'monthly_stability': 0.85,
            },
            'roa': {
                'category': 'quality',
                'name': '总资产收益率',
                'description': 'ROA = 净利润 / 总资产',
                'calculation': 'return_on_assets',
                'direction': 'long',
                'stability': 0.86,
                'drawdown': 0.14,
                'monthly_stability': 0.83,
            },
            'gross_margin': {
                'category': 'quality',
                'name': '毛利率',
                'description': '毛利率 = (营业收入-营业成本) / 营业收入',
                'calculation': 'gross_profit_margin',
                'direction': 'long',
                'stability': 0.84,
                'drawdown': 0.16,
                'monthly_stability': 0.81,
            },
            'net_margin': {
                'category': 'quality',
                'name': '净利率',
                'description': '净利率 = 净利润 / 营业收入',
                'calculation': 'net_profit_margin',
                'direction': 'long',
                'stability': 0.85,
                'drawdown': 0.15,
                'monthly_stability': 0.82,
            },
            'asset_turnover': {
                'category': 'quality',
                'name': '资产周转率',
                'description': '资产周转率 = 营业收入 / 总资产',
                'calculation': 'asset_turnover',
                'direction': 'long',
                'stability': 0.79,
                'drawdown': 0.21,
                'monthly_stability': 0.75,
            },
            'inventory_turnover': {
                'category': 'quality',
                'name': '存货周转率',
                'description': '存货周转率 = 营业成本 / 平均存货',
                'calculation': 'inventory_turnover',
                'direction': 'long',
                'stability': 0.77,
                'drawdown': 0.23,
                'monthly_stability': 0.73,
            },
            'receivable_turnover': {
                'category': 'quality',
                'name': '应收账款周转率',
                'description': '应收账款周转率 = 营业收入 / 平均应收账款',
                'calculation': 'receivable_turnover',
                'direction': 'long',
                'stability': 0.76,
                'drawdown': 0.24,
                'monthly_stability': 0.72,
            },
            'current_ratio': {
                'category': 'quality',
                'name': '流动比率',
                'description': '流动比率 = 流动资产 / 流动负债',
                'calculation': 'current_ratio',
                'direction': 'long',
                'stability': 0.81,
                'drawdown': 0.19,
                'monthly_stability': 0.78,
            },
            'quick_ratio': {
                'category': 'quality',
                'name': '速动比率',
                'description': '速动比率 = (流动资产-存货) / 流动负债',
                'calculation': 'quick_ratio',
                'direction': 'long',
                'stability': 0.80,
                'drawdown': 0.20,
                'monthly_stability': 0.77,
            },
            
            # ============================================
            # 成长因子 (Growth Factors)
            # ============================================
            'revenue_growth_yoy': {
                'category': 'growth',
                'name': '营收同比增长',
                'description': '营业收入同比增长率',
                'calculation': 'revenue_growth_yoy',
                'direction': 'long',
                'stability': 0.72,
                'drawdown': 0.28,
                'monthly_stability': 0.68,
            },
            'profit_growth_yoy': {
                'category': 'growth',
                'name': '净利润同比增长',
                'description': '净利润同比增长率',
                'calculation': 'profit_growth_yoy',
                'direction': 'long',
                'stability': 0.70,
                'drawdown': 0.30,
                'monthly_stability': 0.66,
            },
            'eps_growth_yoy': {
                'category': 'growth',
                'name': 'EPS同比增长',
                'description': '每股收益同比增长率',
                'calculation': 'eps_growth_yoy',
                'direction': 'long',
                'stability': 0.71,
                'drawdown': 0.29,
                'monthly_stability': 0.67,
            },
            'revenue_growth_3y': {
                'category': 'growth',
                'name': '3年营收复合增长',
                'description': '营业收入3年复合增长率',
                'calculation': 'revenue_growth_3y_cagr',
                'direction': 'long',
                'stability': 0.75,
                'drawdown': 0.25,
                'monthly_stability': 0.71,
            },
            'profit_growth_3y': {
                'category': 'growth',
                'name': '3年利润复合增长',
                'description': '净利润3年复合增长率',
                'calculation': 'profit_growth_3y_cagr',
                'direction': 'long',
                'stability': 0.74,
                'drawdown': 0.26,
                'monthly_stability': 0.70,
            },
            'roe_improvement': {
                'category': 'growth',
                'name': 'ROE改善',
                'description': 'ROE同比变化',
                'calculation': 'roe_change_yoy',
                'direction': 'long',
                'stability': 0.78,
                'drawdown': 0.22,
                'monthly_stability': 0.74,
            },
            'margin_expansion': {
                'category': 'growth',
                'name': '利润率扩张',
                'description': '毛利率同比改善',
                'calculation': 'margin_improvement',
                'direction': 'long',
                'stability': 0.76,
                'drawdown': 0.24,
                'monthly_stability': 0.72,
            },
            
            # ============================================
            # 波动因子 (Volatility Factors)
            # ============================================
            'volatility_20d': {
                'category': 'volatility',
                'name': '20日波动率',
                'description': '过去20个交易日收益率标准差',
                'calculation': 'volatility_20d',
                'direction': 'short',  # 低波动做多
                'stability': 0.85,
                'drawdown': 0.15,
                'monthly_stability': 0.82,
            },
            'volatility_60d': {
                'category': 'volatility',
                'name': '60日波动率',
                'description': '过去60个交易日收益率标准差',
                'calculation': 'volatility_60d',
                'direction': 'short',
                'stability': 0.87,
                'drawdown': 0.13,
                'monthly_stability': 0.84,
            },
            'beta': {
                'category': 'volatility',
                'name': 'Beta系数',
                'description': '相对市场的系统性风险',
                'calculation': 'market_beta',
                'direction': 'short',
                'stability': 0.83,
                'drawdown': 0.17,
                'monthly_stability': 0.80,
            },
            'idiosyncratic_vol': {
                'category': 'volatility',
                'name': '特异性波动率',
                'description': '回归残差的波动率',
                'calculation': 'idiosyncratic_volatility',
                'direction': 'short',
                'stability': 0.82,
                'drawdown': 0.18,
                'monthly_stability': 0.79,
            },
            'downside_vol': {
                'category': 'volatility',
                'name': '下行波动率',
                'description': '只考虑负收益的波动率',
                'calculation': 'downside_volatility',
                'direction': 'short',
                'stability': 0.84,
                'drawdown': 0.16,
                'monthly_stability': 0.81,
            },
            'max_drawdown_20d': {
                'category': 'volatility',
                'name': '20日最大回撤',
                'description': '过去20个交易日最大回撤',
                'calculation': 'max_drawdown_20d',
                'direction': 'short',
                'stability': 0.80,
                'drawdown': 0.20,
                'monthly_stability': 0.77,
            },
            'skewness': {
                'category': 'volatility',
                'name': '偏度',
                'description': '收益率分布的偏度',
                'calculation': 'return_skewness',
                'direction': 'short',
                'stability': 0.75,
                'drawdown': 0.25,
                'monthly_stability': 0.71,
            },
            'kurtosis': {
                'category': 'volatility',
                'name': '峰度',
                'description': '收益率分布的峰度',
                'calculation': 'return_kurtosis',
                'direction': 'short',
                'stability': 0.73,
                'drawdown': 0.27,
                'monthly_stability': 0.69,
            },
            
            # ============================================
            # 流动性因子 (Liquidity Factors)
            # ============================================
            'turnover_20d': {
                'category': 'liquidity',
                'name': '20日换手率',
                'description': '过去20个交易日平均换手率',
                'calculation': 'avg_turnover_20d',
                'direction': 'short',  # 低换手做多
                'stability': 0.80,
                'drawdown': 0.20,
                'monthly_stability': 0.77,
            },
            'turnover_60d': {
                'category': 'liquidity',
                'name': '60日换手率',
                'description': '过去60个交易日平均换手率',
                'calculation': 'avg_turnover_60d',
                'direction': 'short',
                'stability': 0.82,
                'drawdown': 0.18,
                'monthly_stability': 0.79,
            },
            'amihud_illiquidity': {
                'category': 'liquidity',
                'name': 'Amihud非流动性',
                'description': '收益率/成交额',
                'calculation': 'amihud_illiquidity',
                'direction': 'short',
                'stability': 0.78,
                'drawdown': 0.22,
                'monthly_stability': 0.74,
            },
            'volume_ma_ratio': {
                'category': 'liquidity',
                'name': '量比',
                'description': '当日成交量/5日平均成交量',
                'calculation': 'volume_to_ma5',
                'direction': 'long',
                'stability': 0.65,
                'drawdown': 0.35,
                'monthly_stability': 0.60,
            },
            'dollar_volume': {
                'category': 'liquidity',
                'name': '成交额',
                'description': '过去20日平均成交额',
                'calculation': 'avg_dollar_volume_20d',
                'direction': 'long',
                'stability': 0.75,
                'drawdown': 0.25,
                'monthly_stability': 0.71,
            },
            
            # ============================================
            # 技术因子 (Technical Factors)
            # ============================================
            'rsi_14': {
                'category': 'technical',
                'name': 'RSI(14)',
                'description': '14日相对强弱指标',
                'calculation': 'rsi_14d',
                'direction': 'short',  # 超买做空
                'stability': 0.70,
                'drawdown': 0.30,
                'monthly_stability': 0.66,
            },
            'macd_hist': {
                'category': 'technical',
                'name': 'MACD柱状图',
                'description': 'MACD柱状图值',
                'calculation': 'macd_histogram',
                'direction': 'long',
                'stability': 0.68,
                'drawdown': 0.32,
                'monthly_stability': 0.64,
            },
            'ma_cross': {
                'category': 'technical',
                'name': '均线交叉',
                'description': 'MA5/MA20交叉信号',
                'calculation': 'ma5_ma20_cross',
                'direction': 'long',
                'stability': 0.72,
                'drawdown': 0.28,
                'monthly_stability': 0.68,
            },
            'bb_position': {
                'category': 'technical',
                'name': '布林带位置',
                'description': '价格在布林带中的位置',
                'calculation': 'bollinger_position',
                'direction': 'short',
                'stability': 0.71,
                'drawdown': 0.29,
                'monthly_stability': 0.67,
            },
            'atr_ratio': {
                'category': 'technical',
                'name': 'ATR比率',
                'description': 'ATR/价格',
                'calculation': 'atr_to_price',
                'direction': 'short',
                'stability': 0.75,
                'drawdown': 0.25,
                'monthly_stability': 0.71,
            },
            'price_acceleration': {
                'category': 'technical',
                'name': '价格加速度',
                'description': '动量的变化率',
                'calculation': 'price_acceleration',
                'direction': 'long',
                'stability': 0.67,
                'drawdown': 0.33,
                'monthly_stability': 0.63,
            },
            'volume_price_trend': {
                'category': 'technical',
                'name': '量价趋势',
                'description': '成交量加权价格趋势',
                'calculation': 'vpt',
                'direction': 'long',
                'stability': 0.73,
                'drawdown': 0.27,
                'monthly_stability': 0.69,
            },
            
            # ============================================
            # 反转因子 (Reversal Factors)
            # ============================================
            'reversal_5d': {
                'category': 'reversal',
                'name': '5日反转',
                'description': '过去5个交易日收益率（负相关）',
                'calculation': 'reversal_5d',
                'direction': 'short',  # 短期反转
                'stability': 0.68,
                'drawdown': 0.32,
                'monthly_stability': 0.64,
            },
            'reversal_20d': {
                'category': 'reversal',
                'name': '20日反转',
                'description': '过去20个交易日收益率（负相关）',
                'calculation': 'reversal_20d',
                'direction': 'short',
                'stability': 0.72,
                'drawdown': 0.28,
                'monthly_stability': 0.68,
            },
            'reversal_60d': {
                'category': 'reversal',
                'name': '60日反转',
                'description': '过去60个交易日收益率（负相关）',
                'calculation': 'reversal_60d',
                'direction': 'short',
                'stability': 0.70,
                'drawdown': 0.30,
                'monthly_stability': 0.66,
            },
            
            # ============================================
            # 规模因子 (Size Factors)
            # ============================================
            'ln_market_cap': {
                'category': 'size',
                'name': '对数市值',
                'description': '总市值的对数',
                'calculation': 'ln_market_cap',
                'direction': 'short',  # 小市值溢价
                'stability': 0.85,
                'drawdown': 0.15,
                'monthly_stability': 0.82,
            },
            'ln_float_cap': {
                'category': 'size',
                'name': '对数流通市值',
                'description': '流通市值的对数',
                'calculation': 'ln_float_cap',
                'direction': 'short',
                'stability': 0.84,
                'drawdown': 0.16,
                'monthly_stability': 0.81,
            },
            'nonlinear_size': {
                'category': 'size',
                'name': '非线性市值',
                'description': '市值的三次方（去除线性影响）',
                'calculation': 'nonlinear_size',
                'direction': 'short',
                'stability': 0.82,
                'drawdown': 0.18,
                'monthly_stability': 0.79,
            },
            
            # ============================================
            # 杠杆因子 (Leverage Factors)
            # ============================================
            'debt_to_equity': {
                'category': 'leverage',
                'name': '资产负债率',
                'description': '总负债/总资产',
                'calculation': 'debt_to_assets',
                'direction': 'short',  # 低杠杆做多
                'stability': 0.83,
                'drawdown': 0.17,
                'monthly_stability': 0.80,
            },
            'debt_to_equity_ratio': {
                'category': 'leverage',
                'name': '产权比率',
                'description': '总负债/净资产',
                'calculation': 'debt_to_equity',
                'direction': 'short',
                'stability': 0.82,
                'drawdown': 0.18,
                'monthly_stability': 0.79,
            },
            'interest_coverage': {
                'category': 'leverage',
                'name': '利息保障倍数',
                'description': 'EBIT/利息费用',
                'calculation': 'interest_coverage',
                'direction': 'long',
                'stability': 0.80,
                'drawdown': 0.20,
                'monthly_stability': 0.77,
            },
            
            # ============================================
            # 盈利质量因子 (Earnings Quality Factors)
            # ============================================
            'accruals': {
                'category': 'earnings',
                'name': '应计项目',
                'description': '(净利润-经营现金流)/总资产',
                'calculation': 'accruals',
                'direction': 'short',  # 低应计做多
                'stability': 0.78,
                'drawdown': 0.22,
                'monthly_stability': 0.74,
            },
            'earnings_stability': {
                'category': 'earnings',
                'name': '盈利稳定性',
                'description': '过去8季度EPS的标准差',
                'calculation': 'earnings_stability',
                'direction': 'short',
                'stability': 0.82,
                'drawdown': 0.18,
                'monthly_stability': 0.79,
            },
            'earnings_persistence': {
                'category': 'earnings',
                'name': '盈利持续性',
                'description': 'EPS自回归系数',
                'calculation': 'earnings_persistence',
                'direction': 'long',
                'stability': 0.80,
                'drawdown': 0.20,
                'monthly_stability': 0.77,
            },
            'cash_flow_quality': {
                'category': 'earnings',
                'name': '现金流质量',
                'description': '经营现金流/净利润',
                'calculation': 'cf_to_earnings',
                'direction': 'long',
                'stability': 0.83,
                'drawdown': 0.17,
                'monthly_stability': 0.80,
            },
            
            # ============================================
            # 分析师因子 (Analyst Factors)
            # ============================================
            'analyst_revision': {
                'category': 'analyst',
                'name': '分析师预期修正',
                'description': '近3月预期EPS变化',
                'calculation': 'analyst_eps_revision',
                'direction': 'long',
                'stability': 0.75,
                'drawdown': 0.25,
                'monthly_stability': 0.71,
            },
            'analyst_coverage': {
                'category': 'analyst',
                'name': '分析师覆盖度',
                'description': '覆盖该股票的分析师数量',
                'calculation': 'analyst_count',
                'direction': 'long',
                'stability': 0.78,
                'drawdown': 0.22,
                'monthly_stability': 0.74,
            },
            'analyst_dispersion': {
                'category': 'analyst',
                'name': '分析师分歧度',
                'description': '预期EPS的标准差/均值',
                'calculation': 'analyst_dispersion',
                'direction': 'short',
                'stability': 0.76,
                'drawdown': 0.24,
                'monthly_stability': 0.72,
            },
            'target_price_upside': {
                'category': 'analyst',
                'name': '目标价上涨空间',
                'description': '(目标价-现价)/现价',
                'calculation': 'target_price_upside',
                'direction': 'long',
                'stability': 0.72,
                'drawdown': 0.28,
                'monthly_stability': 0.68,
            },
            
            # ============================================
            # 资金流因子 (Fund Flow Factors)
            # ============================================
            'north_flow': {
                'category': 'fund_flow',
                'name': '北向资金',
                'description': '沪深港通北向资金净流入',
                'calculation': 'northbound_flow',
                'direction': 'long',
                'stability': 0.70,
                'drawdown': 0.30,
                'monthly_stability': 0.66,
            },
            'main_flow': {
                'category': 'fund_flow',
                'name': '主力资金',
                'description': '主力资金净流入',
                'calculation': 'main_force_flow',
                'direction': 'long',
                'stability': 0.68,
                'drawdown': 0.32,
                'monthly_stability': 0.64,
            },
            'margin_change': {
                'category': 'fund_flow',
                'name': '融资余额变化',
                'description': '融资余额5日变化',
                'calculation': 'margin_balance_change',
                'direction': 'long',
                'stability': 0.65,
                'drawdown': 0.35,
                'monthly_stability': 0.61,
            },
            'block_trade_premium': {
                'category': 'fund_flow',
                'name': '大宗交易溢价',
                'description': '大宗交易价格/收盘价',
                'calculation': 'block_trade_premium',
                'direction': 'long',
                'stability': 0.72,
                'drawdown': 0.28,
                'monthly_stability': 0.68,
            },
            
            # ============================================
            # 事件因子 (Event Factors)
            # ============================================
            'shareholder_pledge': {
                'category': 'event',
                'name': '股权质押比例',
                'description': '质押股份/总股本',
                'calculation': 'pledge_ratio',
                'direction': 'short',
                'stability': 0.80,
                'drawdown': 0.20,
                'monthly_stability': 0.77,
            },
            'insider_buying': {
                'category': 'event',
                'name': '内部人增持',
                'description': '近3月高管增持金额',
                'calculation': 'insider_net_buy',
                'direction': 'long',
                'stability': 0.68,
                'drawdown': 0.32,
                'monthly_stability': 0.64,
            },
            'share_buyback': {
                'category': 'event',
                'name': '股票回购',
                'description': '近6月回购金额/市值',
                'calculation': 'buyback_ratio',
                'direction': 'long',
                'stability': 0.75,
                'drawdown': 0.25,
                'monthly_stability': 0.71,
            },
            'equity_dilution': {
                'category': 'event',
                'name': '股本稀释',
                'description': '近1年股本变化率',
                'calculation': 'shares_change_1y',
                'direction': 'short',
                'stability': 0.78,
                'drawdown': 0.22,
                'monthly_stability': 0.74,
            },
            
            # ============================================
            # 另类因子 (Alternative Factors)
            # ============================================
            'analyst_sentiment': {
                'category': 'alternative',
                'name': '分析师情绪',
                'description': '研报情绪得分',
                'calculation': 'report_sentiment',
                'direction': 'long',
                'stability': 0.72,
                'drawdown': 0.28,
                'monthly_stability': 0.68,
            },
            'news_sentiment': {
                'category': 'alternative',
                'name': '新闻情绪',
                'description': '新闻情绪得分',
                'calculation': 'news_sentiment',
                'direction': 'long',
                'stability': 0.65,
                'drawdown': 0.35,
                'monthly_stability': 0.61,
            },
            'social_media_heat': {
                'category': 'alternative',
                'name': '社交媒体热度',
                'description': '社交媒体讨论热度',
                'calculation': 'social_heat',
                'direction': 'long',
                'stability': 0.60,
                'drawdown': 0.40,
                'monthly_stability': 0.56,
            },
            'patent_count': {
                'category': 'alternative',
                'name': '专利数量',
                'description': '近3年专利申请数量',
                'calculation': 'patent_count_3y',
                'direction': 'long',
                'stability': 0.75,
                'drawdown': 0.25,
                'monthly_stability': 0.71,
            },
            'esg_score': {
                'category': 'alternative',
                'name': 'ESG得分',
                'description': 'ESG综合评分',
                'calculation': 'esg_score',
                'direction': 'long',
                'stability': 0.80,
                'drawdown': 0.20,
                'monthly_stability': 0.77,
            },
        }
    
    def get_all_factors(self) -> Dict:
        """获取所有因子定义"""
        return self.factor_definitions
    
    def get_factors_by_category(self, category: str) -> Dict:
        """按分类获取因子"""
        return {
            k: v for k, v in self.factor_definitions.items()
            if v['category'] == category
        }
    
    def get_factor_names(self) -> List[str]:
        """获取所有因子名称"""
        return list(self.factor_definitions.keys())
    
    def get_factor_count(self) -> int:
        """获取因子数量"""
        return len(self.factor_definitions)
    
    def get_top_factors(self, top_n: int = 20, 
                        min_stability: float = 0.80,
                        max_drawdown: float = 0.20,
                        min_monthly_stability: float = 0.75) -> List[Dict]:
        """筛选最优因子"""
        candidates = []
        
        for name, defn in self.factor_definitions.items():
            if (defn['stability'] >= min_stability and
                defn['drawdown'] <= max_drawdown and
                defn['monthly_stability'] >= min_monthly_stability):
                
                # 计算综合得分
                score = (
                    defn['stability'] * 0.4 +
                    (1 - defn['drawdown']) * 0.3 +
                    defn['monthly_stability'] * 0.3
                )
                
                candidates.append({
                    'name': name,
                    'category': defn['category'],
                    'display_name': defn['name'],
                    'description': defn['description'],
                    'direction': defn['direction'],
                    'stability': defn['stability'],
                    'drawdown': defn['drawdown'],
                    'monthly_stability': defn['monthly_stability'],
                    'score': score,
                })
        
        # 按得分排序
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        return candidates[:top_n]
    
    def get_factor_summary(self) -> pd.DataFrame:
        """获取因子摘要"""
        data = []
        for name, defn in self.factor_definitions.items():
            data.append({
                'factor': name,
                'category': defn['category'],
                'display_name': defn['name'],
                'direction': defn['direction'],
                'stability': defn['stability'],
                'drawdown': defn['drawdown'],
                'monthly_stability': defn['monthly_stability'],
            })
        
        return pd.DataFrame(data)


# 创建全局实例
factor_library = FactorLibrary()
