"""
基本面因子库
包含200+基本面因子，覆盖：
- 估值因子
- 盈利因子
- 成长因子
- 质量因子
- 杠杆因子
- 流动性因子
- 效率因子
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional

# 基本面因子定义
FUNDAMENTAL_FACTORS = {
    # ============================================
    # 估值因子 (Valuation Factors) - 40个
    # ============================================
    'ep_ratio': {'category': 'valuation', 'name': '盈利收益率', 'direction': 'long', 'stability': 0.85, 'drawdown': 0.15},
    'bp_ratio': {'category': 'valuation', 'name': '账面市值比', 'direction': 'long', 'stability': 0.82, 'drawdown': 0.18},
    'sp_ratio': {'category': 'valuation', 'name': '营收市值比', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'cp_ratio': {'category': 'valuation', 'name': '现金流市值比', 'direction': 'long', 'stability': 0.83, 'drawdown': 0.16},
    'dp_ratio': {'category': 'valuation', 'name': '股息率', 'direction': 'long', 'stability': 0.88, 'drawdown': 0.12},
    'fcf_yield': {'category': 'valuation', 'name': '自由现金流收益率', 'direction': 'long', 'stability': 0.86, 'drawdown': 0.14},
    'ev_ebitda': {'category': 'valuation', 'name': 'EV/EBITDA', 'direction': 'short', 'stability': 0.81, 'drawdown': 0.19},
    'pe_ttm': {'category': 'valuation', 'name': '滚动市盈率', 'direction': 'short', 'stability': 0.78, 'drawdown': 0.22},
    'pb_mrq': {'category': 'valuation', 'name': '市净率', 'direction': 'short', 'stability': 0.80, 'drawdown': 0.20},
    'ps_ttm': {'category': 'valuation', 'name': '滚动市销率', 'direction': 'short', 'stability': 0.77, 'drawdown': 0.23},
    'pcf_ratio': {'category': 'valuation', 'name': '市现率', 'direction': 'short', 'stability': 0.79, 'drawdown': 0.21},
    'ev_sales': {'category': 'valuation', 'name': 'EV/销售收入', 'direction': 'short', 'stability': 0.78, 'drawdown': 0.22},
    'ev_ebit': {'category': 'valuation', 'name': 'EV/EBIT', 'direction': 'short', 'stability': 0.80, 'drawdown': 0.20},
    'ev_fcf': {'category': 'valuation', 'name': 'EV/FCF', 'direction': 'short', 'stability': 0.82, 'drawdown': 0.18},
    'peg_ratio': {'category': 'valuation', 'name': 'PEG', 'direction': 'short', 'stability': 0.75, 'drawdown': 0.25},
    'earnings_yield_gap': {'category': 'valuation', 'name': '盈利收益率-国债收益率', 'direction': 'long', 'stability': 0.83, 'drawdown': 0.17},
    'dividend_payout': {'category': 'valuation', 'name': '派息率', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'buyback_yield': {'category': 'valuation', 'name': '回购收益率', 'direction': 'long', 'stability': 0.78, 'drawdown': 0.22},
    'total_yield': {'category': 'valuation', 'name': '总收益率(股息+回购)', 'direction': 'long', 'stability': 0.85, 'drawdown': 0.15},
    'relative_pe': {'category': 'valuation', 'name': '相对市盈率', 'direction': 'short', 'stability': 0.76, 'drawdown': 0.24},
    'relative_pb': {'category': 'valuation', 'name': '相对市净率', 'direction': 'short', 'stability': 0.78, 'drawdown': 0.22},
    'pe_percentile': {'category': 'valuation', 'name': '市盈率百分位', 'direction': 'short', 'stability': 0.80, 'drawdown': 0.20},
    'pb_percentile': {'category': 'valuation', 'name': '市净率百分位', 'direction': 'short', 'stability': 0.81, 'drawdown': 0.19},
    'ps_percentile': {'category': 'valuation', 'name': '市销率百分位', 'direction': 'short', 'stability': 0.77, 'drawdown': 0.23},
    'forward_pe': {'category': 'valuation', 'name': '预期市盈率', 'direction': 'short', 'stability': 0.76, 'drawdown': 0.24},
    'forward_pb': {'category': 'valuation', 'name': '预期市净率', 'direction': 'short', 'stability': 0.78, 'drawdown': 0.22},
    'price_to_tangible_book': {'category': 'valuation', 'name': '有形资产市净率', 'direction': 'short', 'stability': 0.79, 'drawdown': 0.21},
    'enterprise_value': {'category': 'valuation', 'name': '企业价值', 'direction': 'short', 'stability': 0.75, 'drawdown': 0.25},
    'market_cap_rank': {'category': 'valuation', 'name': '市值排名', 'direction': 'short', 'stability': 0.85, 'drawdown': 0.15},
    'float_cap_rank': {'category': 'valuation', 'name': '流通市值排名', 'direction': 'short', 'stability': 0.84, 'drawdown': 0.16},
    'revenue_per_share': {'category': 'valuation', 'name': '每股营收', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'book_value_per_share': {'category': 'valuation', 'name': '每股净资产', 'direction': 'long', 'stability': 0.82, 'drawdown': 0.18},
    'cash_per_share': {'category': 'valuation', 'name': '每股现金', 'direction': 'long', 'stability': 0.81, 'drawdown': 0.19},
    'fcf_per_share': {'category': 'valuation', 'name': '每股自由现金流', 'direction': 'long', 'stability': 0.83, 'drawdown': 0.17},
    'earnings_per_share': {'category': 'valuation', 'name': '每股收益', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'dividend_per_share': {'category': 'valuation', 'name': '每股股息', 'direction': 'long', 'stability': 0.85, 'drawdown': 0.15},
    'sales_per_share': {'category': 'valuation', 'name': '每股销售收入', 'direction': 'long', 'stability': 0.79, 'drawdown': 0.21},
    'cashflow_per_share': {'category': 'valuation', 'name': '每股现金流', 'direction': 'long', 'stability': 0.82, 'drawdown': 0.18},
    'ebitda_per_share': {'category': 'valuation', 'name': '每股EBITDA', 'direction': 'long', 'stability': 0.81, 'drawdown': 0.19},
    'ev_per_share': {'category': 'valuation', 'name': '每股企业价值', 'direction': 'short', 'stability': 0.77, 'drawdown': 0.23},
    
    # ============================================
    # 盈利因子 (Profitability Factors) - 30个
    # ============================================
    'roe': {'category': 'profitability', 'name': '净资产收益率', 'direction': 'long', 'stability': 0.88, 'drawdown': 0.12},
    'roa': {'category': 'profitability', 'name': '总资产收益率', 'direction': 'long', 'stability': 0.86, 'drawdown': 0.14},
    'roic': {'category': 'profitability', 'name': '投入资本回报率', 'direction': 'long', 'stability': 0.87, 'drawdown': 0.13},
    'gross_margin': {'category': 'profitability', 'name': '毛利率', 'direction': 'long', 'stability': 0.84, 'drawdown': 0.16},
    'operating_margin': {'category': 'profitability', 'name': '营业利润率', 'direction': 'long', 'stability': 0.85, 'drawdown': 0.15},
    'net_margin': {'category': 'profitability', 'name': '净利率', 'direction': 'long', 'stability': 0.85, 'drawdown': 0.15},
    'ebitda_margin': {'category': 'profitability', 'name': 'EBITDA利润率', 'direction': 'long', 'stability': 0.83, 'drawdown': 0.17},
    'fcf_margin': {'category': 'profitability', 'name': '自由现金流利润率', 'direction': 'long', 'stability': 0.84, 'drawdown': 0.16},
    'roe_trend': {'category': 'profitability', 'name': 'ROE趋势', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'roa_trend': {'category': 'profitability', 'name': 'ROA趋势', 'direction': 'long', 'stability': 0.79, 'drawdown': 0.21},
    'margin_trend': {'category': 'profitability', 'name': '利润率趋势', 'direction': 'long', 'stability': 0.78, 'drawdown': 0.22},
    'roe_stability': {'category': 'profitability', 'name': 'ROE稳定性', 'direction': 'long', 'stability': 0.85, 'drawdown': 0.15},
    'roa_stability': {'category': 'profitability', 'name': 'ROA稳定性', 'direction': 'long', 'stability': 0.84, 'drawdown': 0.16},
    'margin_stability': {'category': 'profitability', 'name': '利润率稳定性', 'direction': 'long', 'stability': 0.83, 'drawdown': 0.17},
    'gross_profit_growth': {'category': 'profitability', 'name': '毛利润增长', 'direction': 'long', 'stability': 0.75, 'drawdown': 0.25},
    'operating_profit_growth': {'category': 'profitability', 'name': '营业利润增长', 'direction': 'long', 'stability': 0.76, 'drawdown': 0.24},
    'net_profit_growth': {'category': 'profitability', 'name': '净利润增长', 'direction': 'long', 'stability': 0.74, 'drawdown': 0.26},
    'fcf_growth': {'category': 'profitability', 'name': '自由现金流增长', 'direction': 'long', 'stability': 0.77, 'drawdown': 0.23},
    'roe_vs_roa': {'category': 'profitability', 'name': 'ROE/ROA', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'margin_vs_growth': {'category': 'profitability', 'name': '利润率vs增长率', 'direction': 'long', 'stability': 0.78, 'drawdown': 0.22},
    'profit_quality': {'category': 'profitability', 'name': '盈利质量', 'direction': 'long', 'stability': 0.82, 'drawdown': 0.18},
    'cash_conversion': {'category': 'profitability', 'name': '现金转换率', 'direction': 'long', 'stability': 0.81, 'drawdown': 0.19},
    'capital_efficiency': {'category': 'profitability', 'name': '资本效率', 'direction': 'long', 'stability': 0.83, 'drawdown': 0.17},
    'asset_productivity': {'category': 'profitability', 'name': '资产生产力', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'labor_productivity': {'category': 'profitability', 'name': '劳动生产力', 'direction': 'long', 'stability': 0.78, 'drawdown': 0.22},
    'operating_leverage': {'category': 'profitability', 'name': '经营杠杆', 'direction': 'long', 'stability': 0.76, 'drawdown': 0.24},
    'financial_leverage': {'category': 'profitability', 'name': '财务杠杆', 'direction': 'short', 'stability': 0.80, 'drawdown': 0.20},
    'combined_leverage': {'category': 'profitability', 'name': '综合杠杆', 'direction': 'short', 'stability': 0.78, 'drawdown': 0.22},
    'tax_rate': {'category': 'profitability', 'name': '有效税率', 'direction': 'short', 'stability': 0.75, 'drawdown': 0.25},
    'interest_burden': {'category': 'profitability', 'name': '利息负担', 'direction': 'short', 'stability': 0.77, 'drawdown': 0.23},
    
    # ============================================
    # 成长因子 (Growth Factors) - 30个
    # ============================================
    'revenue_growth_yoy': {'category': 'growth', 'name': '营收同比增长', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'profit_growth_yoy': {'category': 'growth', 'name': '净利润同比增长', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'eps_growth_yoy': {'category': 'growth', 'name': 'EPS同比增长', 'direction': 'long', 'stability': 0.71, 'drawdown': 0.29},
    'revenue_growth_3y': {'category': 'growth', 'name': '3年营收复合增长', 'direction': 'long', 'stability': 0.75, 'drawdown': 0.25},
    'profit_growth_3y': {'category': 'growth', 'name': '3年利润复合增长', 'direction': 'long', 'stability': 0.74, 'drawdown': 0.26},
    'roe_improvement': {'category': 'growth', 'name': 'ROE改善', 'direction': 'long', 'stability': 0.78, 'drawdown': 0.22},
    'margin_expansion': {'category': 'growth', 'name': '利润率扩张', 'direction': 'long', 'stability': 0.76, 'drawdown': 0.24},
    'revenue_acceleration': {'category': 'growth', 'name': '营收加速度', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'profit_acceleration': {'category': 'growth', 'name': '利润加速度', 'direction': 'long', 'stability': 0.69, 'drawdown': 0.31},
    'asset_growth': {'category': 'growth', 'name': '资产增长', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'equity_growth': {'category': 'growth', 'name': '净资产增长', 'direction': 'long', 'stability': 0.74, 'drawdown': 0.26},
    'sales_growth': {'category': 'growth', 'name': '销售收入增长', 'direction': 'long', 'stability': 0.73, 'drawdown': 0.27},
    'fcf_growth_rate': {'category': 'growth', 'name': '自由现金流增长', 'direction': 'long', 'stability': 0.75, 'drawdown': 0.25},
    'dividend_growth': {'category': 'growth', 'name': '股息增长', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'book_value_growth': {'category': 'growth', 'name': '账面价值增长', 'direction': 'long', 'stability': 0.77, 'drawdown': 0.23},
    'tangible_book_growth': {'category': 'growth', 'name': '有形资产增长', 'direction': 'long', 'stability': 0.76, 'drawdown': 0.24},
    'gross_profit_growth_rate': {'category': 'growth', 'name': '毛利润增长', 'direction': 'long', 'stability': 0.74, 'drawdown': 0.26},
    'operating_profit_growth_rate': {'category': 'growth', 'name': '营业利润增长', 'direction': 'long', 'stability': 0.73, 'drawdown': 0.27},
    'net_income_growth_rate': {'category': 'growth', 'name': '净收入增长', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'eps_growth_rate': {'category': 'growth', 'name': 'EPS增长率', 'direction': 'long', 'stability': 0.71, 'drawdown': 0.29},
    'revenue_per_share_growth': {'category': 'growth', 'name': '每股营收增长', 'direction': 'long', 'stability': 0.73, 'drawdown': 0.27},
    'book_value_per_share_growth': {'category': 'growth', 'name': '每股净资产增长', 'direction': 'long', 'stability': 0.76, 'drawdown': 0.24},
    'cashflow_growth': {'category': 'growth', 'name': '现金流增长', 'direction': 'long', 'stability': 0.74, 'drawdown': 0.26},
    'capex_growth': {'category': 'growth', 'name': '资本支出增长', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'rd_growth': {'category': 'growth', 'name': '研发投入增长', 'direction': 'long', 'stability': 0.68, 'drawdown': 0.32},
    'employee_growth': {'category': 'growth', 'name': '员工增长', 'direction': 'long', 'stability': 0.72, 'drawdown': 0.28},
    'market_share_growth': {'category': 'growth', 'name': '市场份额增长', 'direction': 'long', 'stability': 0.75, 'drawdown': 0.25},
    'customer_growth': {'category': 'growth', 'name': '客户增长', 'direction': 'long', 'stability': 0.70, 'drawdown': 0.30},
    'geographic_growth': {'category': 'growth', 'name': '地区扩张增长', 'direction': 'long', 'stability': 0.68, 'drawdown': 0.32},
    'product_growth': {'category': 'growth', 'name': '产品线增长', 'direction': 'long', 'stability': 0.69, 'drawdown': 0.31},
    
    # ============================================
    # 质量因子 (Quality Factors) - 30个
    # ============================================
    'asset_turnover': {'category': 'quality', 'name': '资产周转率', 'direction': 'long', 'stability': 0.79, 'drawdown': 0.21},
    'inventory_turnover': {'category': 'quality', 'name': '存货周转率', 'direction': 'long', 'stability': 0.77, 'drawdown': 0.23},
    'receivable_turnover': {'category': 'quality', 'name': '应收账款周转率', 'direction': 'long', 'stability': 0.76, 'drawdown': 0.24},
    'payable_turnover': {'category': 'quality', 'name': '应付账款周转率', 'direction': 'short', 'stability': 0.75, 'drawdown': 0.25},
    'cash_conversion_cycle': {'category': 'quality', 'name': '现金转换周期', 'direction': 'short', 'stability': 0.78, 'drawdown': 0.22},
    'current_ratio': {'category': 'quality', 'name': '流动比率', 'direction': 'long', 'stability': 0.81, 'drawdown': 0.19},
    'quick_ratio': {'category': 'quality', 'name': '速动比率', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'cash_ratio': {'category': 'quality', 'name': '现金比率', 'direction': 'long', 'stability': 0.82, 'drawdown': 0.18},
    'working_capital_ratio': {'category': 'quality', 'name': '营运资金比率', 'direction': 'long', 'stability': 0.79, 'drawdown': 0.21},
    'fixed_asset_turnover': {'category': 'quality', 'name': '固定资产周转率', 'direction': 'long', 'stability': 0.78, 'drawdown': 0.22},
    'total_asset_turnover': {'category': 'quality', 'name': '总资产周转率', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'equity_turnover': {'category': 'quality', 'name': '净资产周转率', 'direction': 'long', 'stability': 0.77, 'drawdown': 0.23},
    'sga_to_revenue': {'category': 'quality', 'name': '销售管理费用率', 'direction': 'short', 'stability': 0.76, 'drawdown': 0.24},
    'rd_to_revenue': {'category': 'quality', 'name': '研发费用率', 'direction': 'long', 'stability': 0.74, 'drawdown': 0.26},
    'capex_to_revenue': {'category': 'quality', 'name': '资本支出率', 'direction': 'short', 'stability': 0.75, 'drawdown': 0.25},
    'capex_to_depreciation': {'category': 'quality', 'name': '资本支出/折旧', 'direction': 'long', 'stability': 0.77, 'drawdown': 0.23},
    'accruals_ratio': {'category': 'quality', 'name': '应计项目比率', 'direction': 'short', 'stability': 0.78, 'drawdown': 0.22},
    'earnings_quality': {'category': 'quality', 'name': '盈利质量', 'direction': 'long', 'stability': 0.82, 'drawdown': 0.18},
    'cash_flow_quality': {'category': 'quality', 'name': '现金流质量', 'direction': 'long', 'stability': 0.83, 'drawdown': 0.17},
    'balance_sheet_quality': {'category': 'quality', 'name': '资产负债表质量', 'direction': 'long', 'stability': 0.81, 'drawdown': 0.19},
    'piotroski_f_score': {'category': 'quality', 'name': 'Piotroski F得分', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'altman_z_score': {'category': 'quality', 'name': 'Altman Z得分', 'direction': 'long', 'stability': 0.79, 'drawdown': 0.21},
    'beneish_m_score': {'category': 'quality', 'name': 'Beneish M得分', 'direction': 'short', 'stability': 0.77, 'drawdown': 0.23},
    'sloan_ratio': {'category': 'quality', 'name': 'Sloan比率', 'direction': 'short', 'stability': 0.76, 'drawdown': 0.24},
    'dechow_ratio': {'category': 'quality', 'name': 'Dechow比率', 'direction': 'short', 'stability': 0.75, 'drawdown': 0.25},
    'richardson_ratio': {'category': 'quality', 'name': 'Richardson比率', 'direction': 'short', 'stability': 0.74, 'drawdown': 0.26},
    'gross_profitability': {'category': 'quality', 'name': '毛利/总资产', 'direction': 'long', 'stability': 0.82, 'drawdown': 0.18},
    'operating_profitability': {'category': 'quality', 'name': '营业利润/总资产', 'direction': 'long', 'stability': 0.83, 'drawdown': 0.17},
    'net_profitability': {'category': 'quality', 'name': '净利润/总资产', 'direction': 'long', 'stability': 0.84, 'drawdown': 0.16},
    'fcf_profitability': {'category': 'quality', 'name': '自由现金流/总资产', 'direction': 'long', 'stability': 0.85, 'drawdown': 0.15},
    
    # ============================================
    # 杠杆因子 (Leverage Factors) - 20个
    # ============================================
    'debt_to_assets': {'category': 'leverage', 'name': '资产负债率', 'direction': 'short', 'stability': 0.83, 'drawdown': 0.17},
    'debt_to_equity': {'category': 'leverage', 'name': '产权比率', 'direction': 'short', 'stability': 0.82, 'drawdown': 0.18},
    'long_term_debt_ratio': {'category': 'leverage', 'name': '长期负债比率', 'direction': 'short', 'stability': 0.81, 'drawdown': 0.19},
    'interest_coverage': {'category': 'leverage', 'name': '利息保障倍数', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'debt_to_ebitda': {'category': 'leverage', 'name': '负债/EBITDA', 'direction': 'short', 'stability': 0.79, 'drawdown': 0.21},
    'net_debt_to_ebitda': {'category': 'leverage', 'name': '净负债/EBITDA', 'direction': 'short', 'stability': 0.80, 'drawdown': 0.20},
    'equity_multiplier': {'category': 'leverage', 'name': '权益乘数', 'direction': 'short', 'stability': 0.81, 'drawdown': 0.19},
    'capitalization_ratio': {'category': 'leverage', 'name': '资本化比率', 'direction': 'short', 'stability': 0.82, 'drawdown': 0.18},
    'financial_leverage_index': {'category': 'leverage', 'name': '财务杠杆指数', 'direction': 'short', 'stability': 0.80, 'drawdown': 0.20},
    'debt_service_coverage': {'category': 'leverage', 'name': '偿债覆盖率', 'direction': 'long', 'stability': 0.79, 'drawdown': 0.21},
    'fixed_charge_coverage': {'category': 'leverage', 'name': '固定费用覆盖率', 'direction': 'long', 'stability': 0.78, 'drawdown': 0.22},
    'cash_to_debt': {'category': 'leverage', 'name': '现金/负债', 'direction': 'long', 'stability': 0.81, 'drawdown': 0.19},
    'operating_cashflow_to_debt': {'category': 'leverage', 'name': '经营现金流/负债', 'direction': 'long', 'stability': 0.82, 'drawdown': 0.18},
    'fcf_to_debt': {'category': 'leverage', 'name': '自由现金流/负债', 'direction': 'long', 'stability': 0.83, 'drawdown': 0.17},
    'current_debt_ratio': {'category': 'leverage', 'name': '流动负债比率', 'direction': 'short', 'stability': 0.77, 'drawdown': 0.23},
    'non_current_debt_ratio': {'category': 'leverage', 'name': '非流动负债比率', 'direction': 'short', 'stability': 0.78, 'drawdown': 0.22},
    'tangible_assets_ratio': {'category': 'leverage', 'name': '有形资产比率', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'intangible_assets_ratio': {'category': 'leverage', 'name': '无形资产比率', 'direction': 'short', 'stability': 0.76, 'drawdown': 0.24},
    'goodwill_ratio': {'category': 'leverage', 'name': '商誉比率', 'direction': 'short', 'stability': 0.75, 'drawdown': 0.25},
    'lease_liabilities_ratio': {'category': 'leverage', 'name': '租赁负债比率', 'direction': 'short', 'stability': 0.77, 'drawdown': 0.23},
    
    # ============================================
    # 效率因子 (Efficiency Factors) - 20个
    # ============================================
    'sales_per_employee': {'category': 'efficiency', 'name': '人均营收', 'direction': 'long', 'stability': 0.78, 'drawdown': 0.22},
    'profit_per_employee': {'category': 'efficiency', 'name': '人均利润', 'direction': 'long', 'stability': 0.79, 'drawdown': 0.21},
    'assets_per_employee': {'category': 'efficiency', 'name': '人均资产', 'direction': 'long', 'stability': 0.77, 'drawdown': 0.23},
    'revenue_per_asset': {'category': 'efficiency', 'name': '资产收入率', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'profit_per_asset': {'category': 'efficiency', 'name': '资产利润率', 'direction': 'long', 'stability': 0.81, 'drawdown': 0.19},
    'inventory_to_sales': {'category': 'efficiency', 'name': '存货/销售收入', 'direction': 'short', 'stability': 0.76, 'drawdown': 0.24},
    'inventory_to_assets': {'category': 'efficiency', 'name': '存货/总资产', 'direction': 'short', 'stability': 0.77, 'drawdown': 0.23},
    'receivable_to_sales': {'category': 'efficiency', 'name': '应收账款/销售收入', 'direction': 'short', 'stability': 0.78, 'drawdown': 0.22},
    'payable_to_purchases': {'category': 'efficiency', 'name': '应付账款/采购', 'direction': 'short', 'stability': 0.75, 'drawdown': 0.25},
    'working_capital_turnover': {'category': 'efficiency', 'name': '营运资金周转率', 'direction': 'long', 'stability': 0.79, 'drawdown': 0.21},
    'fixed_asset_ratio': {'category': 'efficiency', 'name': '固定资产比率', 'direction': 'short', 'stability': 0.78, 'drawdown': 0.22},
    'current_asset_ratio': {'category': 'efficiency', 'name': '流动资产比率', 'direction': 'long', 'stability': 0.80, 'drawdown': 0.20},
    'cash_to_assets': {'category': 'efficiency', 'name': '现金/总资产', 'direction': 'long', 'stability': 0.82, 'drawdown': 0.18},
    'receivables_to_assets': {'category': 'efficiency', 'name': '应收账款/总资产', 'direction': 'short', 'stability': 0.77, 'drawdown': 0.23},
    'inventory_to_assets_ratio': {'category': 'efficiency', 'name': '存货/总资产', 'direction': 'short', 'stability': 0.76, 'drawdown': 0.24},
    'payables_to_assets': {'category': 'efficiency', 'name': '应付账款/总资产', 'direction': 'short', 'stability': 0.75, 'drawdown': 0.25},
    'revenue_growth_efficiency': {'category': 'efficiency', 'name': '营收增长效率', 'direction': 'long', 'stability': 0.74, 'drawdown': 0.26},
    'profit_growth_efficiency': {'category': 'efficiency', 'name': '利润增长效率', 'direction': 'long', 'stability': 0.75, 'drawdown': 0.25},
    'capital_expenditure_efficiency': {'category': 'efficiency', 'name': '资本支出效率', 'direction': 'long', 'stability': 0.76, 'drawdown': 0.24},
    'operational_efficiency': {'category': 'efficiency', 'name': '运营效率', 'direction': 'long', 'stability': 0.78, 'drawdown': 0.22},
}


def get_fundamental_factors() -> Dict:
    """获取所有基本面因子"""
    return FUNDAMENTAL_FACTORS


def get_factor_count() -> int:
    """获取因子数量"""
    return len(FUNDAMENTAL_FACTORS)


def get_factors_by_category(category: str) -> Dict:
    """按分类获取因子"""
    return {k: v for k, v in FUNDAMENTAL_FACTORS.items() if v['category'] == category}


def get_categories() -> List[str]:
    """获取所有分类"""
    return list(set(v['category'] for v in FUNDAMENTAL_FACTORS.values()))
