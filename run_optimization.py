#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持续优化迭代运行脚本
对多只股票运行多策略参数优化，输出最优结果
"""

import logging
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from strategy_optimizer import StrategyOptimizer, quick_optimize

def run_single_stock_optimization():
    """单股票优化迭代"""
    print("\n" + "=" * 70)
    print("🚀 第1轮优化迭代 - 贵州茅台(600519)")
    print("=" * 70)
    
    results = quick_optimize(symbols=['600519'], iterations=1)
    
    print(f'\n✅ 优化完成！共 {len(results)} 次迭代')
    
    for r in results:
        stats = r.get('stats', {})
        strategy_name = r.get('strategy', 'unknown')
        sharpe = stats.get('sharpe_ratio', 0)
        annual = stats.get('annualized_return_pct', 0)
        max_dd = stats.get('max_drawdown_pct', 0)
        win_rate = stats.get('win_rate_pct', 0)
        trades = stats.get('total_trades', 0)
        best_params = r.get('best_params', {})
        
        print(f'\n📊 策略: {strategy_name}')
        print(f'   夏普比率: {sharpe:.3f}')
        print(f'   年化收益: {annual:.2f}%')
        print(f'   最大回撤: {max_dd:.2f}%')
        print(f'   胜率: {win_rate:.2f}%')
        print(f'   交易次数: {trades}')
        print(f'   最优参数: {best_params}')
    
    return results


def run_multi_stock_optimization():
    """多股票优化迭代（第2轮）"""
    print("\n" + "=" * 70)
    print("🚀 第2轮优化迭代 - 多股票验证")
    print("=" * 70)
    
    # 选择代表性标的：大盘蓝筹+成长股+周期股
    symbols = ['000858', '300750', '601318']
    
    # 只使用表现最好的策略快速验证
    optimizer = StrategyOptimizer()
    
    strategies = {
        'RSI动量': StrategyOptimizer.rsi_momentum_strategy,
        'MA均线交叉': StrategyOptimizer.ma_cross_atr_strategy,
    }
    
    param_grids = {
        'RSI动量': {
            'rsi_period': [6, 14],
            'rsi_oversold': [25, 30, 35],
            'rsi_overbought': [65, 70, 75],
            'trend_filter': [True],
        },
        'MA均线交叉': {
            'fast_period': [3, 5, 8],
            'slow_period': [15, 20, 30],
            'atr_stop_mult': [2.0, 2.5],
            'holding_days': [5, 7],
        },
    }
    
    results = optimizer.continuous_optimize(
        symbols=symbols,
        strategies=strategies,
        param_grids=param_grids,
        iterations=1,
        metric='sharpe_ratio'
    )
    
    print(f'\n✅ 第2轮优化完成！共 {len(results)} 次迭代')
    
    # 汇总最优策略
    if results:
        best = max(results, key=lambda x: x.get('stats', {}).get('sharpe_ratio', -999))
        stats = best.get('stats', {})
        print(f'\n🏆 最优组合:')
        print(f'   股票: {best["symbol"]}')
        print(f'   策略: {best["strategy"]}')
        print(f'   夏普比率: {stats.get("sharpe_ratio", 0):.3f}')
        print(f'   年化收益: {stats.get("annualized_return_pct", 0):.2f}%')
        print(f'   最大回撤: {stats.get("max_drawdown_pct", 0):.2f}%')
        print(f'   胜率: {stats.get("win_rate_pct", 0):.2f}%')
        print(f'   最优参数: {best.get("best_params", {})}')
    
    return results


if __name__ == '__main__':
    print("\n" + "#" * 70)
    print("🔥 量化策略持续优化迭代器")
    print("#" * 70)
    
    # 第1轮：单股票深度优化
    r1 = run_single_stock_optimization()
    
    # 第2轮：多股票验证
    r2 = run_multi_stock_optimization()
    
    print("\n" + "#" * 70)
    print("✅ 全部优化迭代完成！")
    print(f"   第1轮迭代数: {len(r1)}")
    print(f"   第2轮迭代数: {len(r2)}")
    print(f"   结果已保存至 optimization_results/ 目录")
    print("#" * 70)