"""
量化因子库
包含1000+因子，覆盖：
- 价值因子
- 动量因子
- 质量因子
- 成长因子
- 波动因子
- 流动性因子
- 技术因子
- 情绪因子
- 资金流因子
- 宏观因子
"""

from .factor_library import FactorLibrary
from .factor_evaluator import FactorEvaluator
from .optimal_factor_selector import OptimalFactorSelector

__all__ = ['FactorLibrary', 'FactorEvaluator', 'OptimalFactorSelector']
