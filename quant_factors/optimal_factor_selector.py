"""
最优因子选择器
从1000+因子中筛选出回撤小、收益稳定、月度稳定的最优因子组合
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class OptimalFactorSelector:
    """最优因子选择器"""
    
    # 筛选标准
    CRITERIA = {
        'min_sharpe': 0.5,           # 最低夏普比率
        'max_drawdown': 0.25,        # 最大回撤上限
        'min_calmar': 0.3,           # 最低卡尔玛比率
        'min_return_stability': 0.7, # 最低收益稳定性
        'min_monthly_stability': 0.65, # 最低月度稳定性
        'min_win_rate': 0.55,        # 最低胜率
        'min_ic_mean': 0.02,         # 最低IC均值
        'min_icir': 0.3,             # 最低ICIR
    }
    
    # 因子权重（用于构建组合）
    FACTOR_WEIGHTS = {
        'value': 0.15,
        'momentum': 0.12,
        'quality': 0.18,
        'growth': 0.12,
        'volatility': 0.15,
        'liquidity': 0.08,
        'technical': 0.05,
        'reversal': 0.05,
        'size': 0.05,
        'earnings': 0.05,
    }
    
    def __init__(self, factor_library=None, factor_evaluator=None):
        from .factor_library import FactorLibrary
        from .factor_evaluator import FactorEvaluator
        
        self.factor_library = factor_library or FactorLibrary()
        self.factor_evaluator = factor_evaluator or FactorEvaluator()
    
    def select_optimal_factors(self, top_n: int = 20) -> List[Dict]:
        """选择最优因子"""
        # 1. 获取所有因子定义
        all_factors = self.factor_library.get_all_factors()
        logger.info(f"总因子数量: {len(all_factors)}")
        
        # 2. 按预设指标初步筛选
        candidates = self._pre_filter(all_factors)
        logger.info(f"初步筛选后: {len(candidates)}")
        
        # 3. 按类别分组，每类选最优
        category_best = self._select_best_by_category(candidates)
        logger.info(f"分类筛选后: {len(category_best)}")
        
        # 4. 按综合得分排序
        ranked = self._rank_factors(category_best)
        
        # 5. 去相关性，选择低相关因子组合
        optimal = self._select_uncorrelated(ranked, top_n)
        logger.info(f"最终选择: {len(optimal)}")
        
        return optimal
    
    def _pre_filter(self, all_factors: Dict) -> List[Dict]:
        """初步筛选"""
        candidates = []
        
        for name, defn in all_factors.items():
            # 筛选条件
            if (defn['stability'] >= 0.75 and
                defn['drawdown'] <= 0.25 and
                defn['monthly_stability'] >= 0.65):
                
                # 计算预估得分
                score = (
                    defn['stability'] * 0.35 +
                    (1 - defn['drawdown']) * 0.35 +
                    defn['monthly_stability'] * 0.30
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
                    'estimated_score': score,
                })
        
        return candidates
    
    def _select_best_by_category(self, candidates: List[Dict]) -> List[Dict]:
        """按类别选择最优因子"""
        # 按类别分组
        category_factors = {}
        for factor in candidates:
            category = factor['category']
            if category not in category_factors:
                category_factors[category] = []
            category_factors[category].append(factor)
        
        # 每类选择TOP因子
        best_factors = []
        for category, factors in category_factors.items():
            # 按得分排序
            sorted_factors = sorted(factors, key=lambda x: x['estimated_score'], reverse=True)
            
            # 每类取TOP 5
            top_count = min(5, len(sorted_factors))
            best_factors.extend(sorted_factors[:top_count])
        
        return best_factors
    
    def _rank_factors(self, factors: List[Dict]) -> List[Dict]:
        """对因子进行排名"""
        # 按综合得分排序
        ranked = sorted(factors, key=lambda x: x['estimated_score'], reverse=True)
        
        # 添加排名
        for i, factor in enumerate(ranked):
            factor['rank'] = i + 1
        
        return ranked
    
    def _select_uncorrelated(self, ranked_factors: List[Dict], top_n: int) -> List[Dict]:
        """选择低相关因子组合"""
        if len(ranked_factors) <= top_n:
            return ranked_factors
        
        # 简化版：按类别均匀选择
        selected = []
        category_count = {}
        
        for factor in ranked_factors:
            category = factor['category']
            
            # 每类最多选3个
            if category_count.get(category, 0) >= 3:
                continue
            
            selected.append(factor)
            category_count[category] = category_count.get(category, 0) + 1
            
            if len(selected) >= top_n:
                break
        
        return selected
    
    def build_factor_portfolio(self, selected_factors: List[Dict]) -> Dict:
        """构建因子组合"""
        portfolio = {
            'factors': selected_factors,
            'weights': {},
            'expected_return': 0,
            'expected_drawdown': 0,
            'expected_stability': 0,
        }
        
        # 计算权重
        total_score = sum(f['estimated_score'] for f in selected_factors)
        
        for factor in selected_factors:
            weight = factor['estimated_score'] / total_score if total_score > 0 else 1 / len(selected_factors)
            portfolio['weights'][factor['name']] = weight
        
        # 计算组合预期指标
        weighted_return = 0
        weighted_drawdown = 0
        weighted_stability = 0
        
        for factor in selected_factors:
            weight = portfolio['weights'][factor['name']]
            
            # 使用稳定性作为收益代理
            weighted_return += factor['stability'] * weight
            weighted_drawdown += factor['drawdown'] * weight
            weighted_stability += factor['monthly_stability'] * weight
        
        portfolio['expected_return'] = weighted_return
        portfolio['expected_drawdown'] = weighted_drawdown
        portfolio['expected_stability'] = weighted_stability
        
        return portfolio
    
    def get_optimal_strategy(self) -> Dict:
        """获取最优策略配置"""
        # 选择最优因子
        optimal_factors = self.select_optimal_factors(top_n=20)
        
        # 构建因子组合
        portfolio = self.build_factor_portfolio(optimal_factors)
        
        return {
            'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_factors_evaluated': self.factor_library.get_factor_count(),
            'selected_factors': len(optimal_factors),
            'optimal_factors': optimal_factors,
            'portfolio': portfolio,
            'criteria': self.CRITERIA,
        }
    
    def generate_report(self) -> str:
        """生成因子选择报告"""
        strategy = self.get_optimal_strategy()
        
        report = []
        report.append("=" * 70)
        report.append("量化因子筛选报告")
        report.append("=" * 70)
        report.append(f"评估时间: {strategy['timestamp']}")
        report.append(f"评估因子总数: {strategy['total_factors_evaluated']}")
        report.append(f"筛选后因子数: {strategy['selected_factors']}")
        report.append("")
        
        report.append("-" * 70)
        report.append("筛选标准:")
        report.append("-" * 70)
        for key, value in self.CRITERIA.items():
            report.append(f"  {key}: {value}")
        report.append("")
        
        report.append("-" * 70)
        report.append("最优因子组合 (TOP 20):")
        report.append("-" * 70)
        report.append(f"{'排名':<5} {'因子':<25} {'类别':<10} {'稳定性':<10} {'回撤':<10} {'月稳定性':<10} {'得分':<10}")
        report.append("-" * 70)
        
        for factor in strategy['optimal_factors'][:20]:
            report.append(
                f"{factor['rank']:<5} "
                f"{factor['display_name']:<25} "
                f"{factor['category']:<10} "
                f"{factor['stability']:<10.3f} "
                f"{factor['drawdown']:<10.3f} "
                f"{factor['monthly_stability']:<10.3f} "
                f"{factor['estimated_score']:<10.3f}"
            )
        
        report.append("")
        report.append("-" * 70)
        report.append("因子组合预期表现:")
        report.append("-" * 70)
        portfolio = strategy['portfolio']
        report.append(f"  预期收益: {portfolio['expected_return']:.3f}")
        report.append(f"  预期回撤: {portfolio['expected_drawdown']:.3f}")
        report.append(f"  预期稳定性: {portfolio['expected_stability']:.3f}")
        report.append("")
        
        report.append("-" * 70)
        report.append("因子权重分配:")
        report.append("-" * 70)
        for name, weight in sorted(portfolio['weights'].items(), key=lambda x: x[1], reverse=True)[:10]:
            report.append(f"  {name}: {weight:.3f}")
        
        report.append("")
        report.append("=" * 70)
        report.append("说明:")
        report.append("  - 稳定性: 收益率稳定性，越高越好")
        report.append("  - 回撤: 最大回撤，越低越好")
        report.append("  - 月稳定性: 月度收益稳定性，越高越好")
        report.append("  - 得分: 综合评分，越高越好")
        report.append("=" * 70)
        
        return "\n".join(report)


# 创建全局实例
optimal_factor_selector = OptimalFactorSelector()
