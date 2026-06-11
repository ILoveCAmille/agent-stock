"""
动态因子权重调整器
根据市场状态动态调整因子权重
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DynamicWeightAdjuster:
    """动态因子权重调整器"""
    
    # 默认权重
    DEFAULT_WEIGHTS = {
        'momentum': 0.15,
        'growth': 0.15,
        'quality': 0.20,
        'value': 0.20,
        'low_volatility': 0.15,
        'size': 0.10,
        'fund_flow': 0.05,
    }
    
    # 因子类别映射
    FACTOR_CATEGORY_MAP = {
        # 动量因子
        'mom_1m': 'momentum', 'mom_3m': 'momentum', 'mom_6m': 'momentum',
        'mom_12m': 'momentum', 'mom_12m_1m': 'momentum', 'price_momentum': 'momentum',
        
        # 成长因子
        'revenue_growth': 'growth', 'profit_growth': 'growth', 'eps_growth': 'growth',
        'revenue_growth_3y': 'growth', 'profit_growth_3y': 'growth',
        
        # 质量因子
        'roe': 'quality', 'roa': 'quality', 'gross_margin': 'quality',
        'net_margin': 'quality', 'asset_turnover': 'quality',
        
        # 价值因子
        'ep_ratio': 'value', 'bp_ratio': 'value', 'sp_ratio': 'value',
        'dp_ratio': 'value', 'fcf_yield': 'value', 'pe_ttm': 'value',
        
        # 低波动因子
        'volatility_20d': 'low_volatility', 'volatility_60d': 'low_volatility',
        'beta': 'low_volatility', 'downside_vol': 'low_volatility',
        
        # 规模因子
        'ln_market_cap': 'size', 'ln_float_cap': 'size',
        
        # 资金流因子
        'main_net_flow': 'fund_flow', 'north_net_flow': 'fund_flow',
        'margin_balance': 'fund_flow',
    }
    
    def __init__(self):
        self.current_weights = self.DEFAULT_WEIGHTS.copy()
        self.weight_history = []
    
    def adjust_weights(self, market_state: Dict, factor_performance: Dict = None) -> Dict:
        """
        根据市场状态调整因子权重
        
        Args:
            market_state: 市场状态（来自MarketStateIdentifier）
            factor_performance: 因子绩效数据（可选）
            
        Returns:
            调整后的权重
        """
        state = market_state.get('state', 'sideways')
        
        # 获取基础权重（根据市场状态）
        base_weights = market_state.get('factor_weights', self.DEFAULT_WEIGHTS)
        
        # 如果有因子绩效数据，进行微调
        if factor_performance:
            adjusted_weights = self._adjust_by_performance(base_weights, factor_performance)
        else:
            adjusted_weights = base_weights.copy()
        
        # 归一化权重
        total = sum(adjusted_weights.values())
        if total > 0:
            adjusted_weights = {k: v / total for k, v in adjusted_weights.items()}
        
        # 记录历史
        self.current_weights = adjusted_weights
        self.weight_history.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'market_state': state,
            'weights': adjusted_weights.copy(),
        })
        
        return adjusted_weights
    
    def _adjust_by_performance(self, base_weights: Dict, factor_performance: Dict) -> Dict:
        """根据因子绩效微调权重"""
        adjusted = base_weights.copy()
        
        # 获取各因子的ICIR
        icir_scores = factor_performance.get('icir_scores', {})
        
        if icir_scores:
            # 根据ICIR调整权重
            for factor, icir in icir_scores.items():
                category = self.FACTOR_CATEGORY_MAP.get(factor, '')
                if category in adjusted:
                    # ICIR越高，权重增加
                    adjustment = icir * 0.1  # 最大调整10%
                    adjusted[category] = max(0.05, adjusted[category] + adjustment)
        
        return adjusted
    
    def get_weight_for_factor(self, factor_name: str) -> float:
        """获取单个因子的权重"""
        category = self.FACTOR_CATEGORY_MAP.get(factor_name, '')
        return self.current_weights.get(category, 0.1)
    
    def get_all_weights(self) -> Dict:
        """获取所有权重"""
        return self.current_weights.copy()
    
    def get_weight_history(self) -> List[Dict]:
        """获取权重历史"""
        return self.weight_history
    
    def format_weights_report(self) -> str:
        """格式化权重报告"""
        report = []
        report.append("=" * 50)
        report.append("当前因子权重配置")
        report.append("=" * 50)
        
        for category, weight in sorted(self.current_weights.items(), key=lambda x: x[1], reverse=True):
            bar = "█" * int(weight * 50)
            report.append(f"{category:<20} {weight*100:>6.1f}% {bar}")
        
        report.append("")
        report.append("=" * 50)
        
        return "\n".join(report)


class AdaptiveWeightSystem:
    """自适应权重系统"""
    
    def __init__(self):
        self.market_identifier = None
        self.weight_adjuster = DynamicWeightAdjuster()
        self.data_source = None
        
        self._init_components()
    
    def _init_components(self):
        """初始化组件"""
        try:
            from market_state_identifier import market_state_identifier
            self.market_identifier = market_state_identifier
        except ImportError:
            logger.error("无法导入市场状态识别器")
        
        try:
            from backtest.data_source_manager import DataSourceManager
            self.data_source = DataSourceManager()
        except ImportError:
            logger.error("无法导入数据源管理器")
    
    def get_current_weights(self, index_code: str = '000001') -> Dict:
        """获取当前最优权重"""
        if not self.market_identifier or not self.data_source:
            return self.weight_adjuster.DEFAULT_WEIGHTS
        
        # 获取指数数据
        index_data = self.data_source.get_index_data(index_code, days=120)
        
        if index_data.empty:
            return self.weight_adjuster.DEFAULT_WEIGHTS
        
        # 识别市场状态
        market_state = self.market_identifier.identify_market_state(index_data)
        
        # 调整权重
        weights = self.weight_adjuster.adjust_weights(market_state)
        
        return weights
    
    def get_strategy_report(self, index_code: str = '000001') -> str:
        """获取策略报告"""
        if not self.market_identifier or not self.data_source:
            return "系统未初始化"
        
        # 获取指数数据
        index_data = self.data_source.get_index_data(index_code, days=120)
        
        if index_data.empty:
            return "无法获取指数数据"
        
        # 识别市场状态
        market_state = self.market_identifier.identify_market_state(index_data)
        
        # 调整权重
        weights = self.weight_adjuster.adjust_weights(market_state)
        
        # 生成报告
        report = []
        report.append(self.market_identifier.format_report(market_state))
        report.append("")
        report.append(self.weight_adjuster.format_weights_report())
        
        return "\n".join(report)


# 创建全局实例
dynamic_weight_adjuster = DynamicWeightAdjuster()
adaptive_weight_system = AdaptiveWeightSystem()
