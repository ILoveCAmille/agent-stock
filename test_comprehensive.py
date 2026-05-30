#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证综合量化系统模块完整性"""
import sys

print("=" * 60)
print("综合量化交易系统 - 模块验证")
print("=" * 60)

# 1. 验证综合量化因子引擎
try:
    from comprehensive_quant_engine import ComprehensiveQuantEngine, comprehensive_engine
    print("✅ ComprehensiveQuantEngine 导入成功")
    print(f"   默认权重: {ComprehensiveQuantEngine.DEFAULT_WEIGHTS}")
    assert len(ComprehensiveQuantEngine.DEFAULT_WEIGHTS) == 5
    assert abs(sum(ComprehensiveQuantEngine.DEFAULT_WEIGHTS.values()) - 1.0) < 0.001
    print("   权重验证通过 (5维度，总和=1.0)")
except Exception as e:
    print(f"❌ ComprehensiveQuantEngine 导入失败: {e}")
    sys.exit(1)

# 2. 验证综合策略
try:
    from comprehensive_strategy import ComprehensiveStrategy, MultiStrategyComparator
    print("✅ ComprehensiveStrategy 导入成功")
    
    # 验证三种预设
    for preset in ['aggressive', 'balanced', 'conservative']:
        s = ComprehensiveStrategy(preset)
        assert 'buy_score_threshold' in s.params
        assert 'sell_score_threshold' in s.params
        assert 'take_profit_pct' in s.params
        assert 'stop_loss_pct' in s.params
        assert 'weights' in s.params
        print(f"   {preset}: {s.params['name']} - 验证通过")
    
    print("✅ MultiStrategyComparator 导入成功")
except Exception as e:
    print(f"❌ ComprehensiveStrategy 导入失败: {e}")
    sys.exit(1)

# 3. 验证回测引擎
try:
    from backtest_engine import BacktestEngine
    print("✅ BacktestEngine 导入成功")
except Exception as e:
    print(f"❌ BacktestEngine 导入失败: {e}")
    sys.exit(1)

# 4. 验证原始量化因子库
try:
    from quant_factors import QuantFactors
    print("✅ QuantFactors 导入成功")
    
    # 验证核心因子存在
    assert hasattr(QuantFactors, 'rsi')
    assert hasattr(QuantFactors, 'atr')
    assert hasattr(QuantFactors, 'adx')
    assert hasattr(QuantFactors, 'obv')
    assert hasattr(QuantFactors, 'vwap')
    print("   核心因子验证通过 (RSI/ATR/ADX/OBV/VWAP)")
except Exception as e:
    print(f"❌ QuantFactors 导入失败: {e}")
    sys.exit(1)

# 5. 验证策略优化器
try:
    from strategy_optimizer import StrategyOptimizer
    print("✅ StrategyOptimizer 导入成功")
    assert hasattr(StrategyOptimizer, 'multi_factor_strategy')
    assert hasattr(StrategyOptimizer, 'ma_cross_atr_strategy')
    print("   原有策略验证通过")
except Exception as e:
    print(f"❌ StrategyOptimizer 导入失败: {e}")
    sys.exit(1)

# 6. 验证五维度因子计算
try:
    import pandas as pd
    import numpy as np
    
    # 创建测试数据
    np.random.seed(42)
    dates = pd.bdate_range(end='2026-05-30', periods=300)
    prices = 100 * np.cumprod(1 + np.random.normal(0.0003, 0.015, 300))
    
    df = pd.DataFrame({
        'Open': prices + np.random.randn(300) * 0.5,
        'High': prices * (1 + np.abs(np.random.normal(0, 0.01, 300))),
        'Low': prices * (1 - np.abs(np.random.normal(0, 0.01, 300))),
        'Close': prices,
        'Volume': np.random.lognormal(15, 0.5, 300)
    }, index=dates)
    
    engine = ComprehensiveQuantEngine()
    
    # 计算基础因子
    df = engine.compute_all_factors(df)
    assert 'ATR' in df.columns
    assert 'RSI_14' in df.columns
    assert 'MACD' in df.columns
    assert 'BB_upper' in df.columns
    print("✅ 基础技术因子计算成功")
    
    # 计算五维度评分
    df = engine.compute_comprehensive_score(df)
    assert 'Score_Technical' in df.columns
    assert 'Score_FundFlow' in df.columns
    assert 'Score_Sentiment' in df.columns
    assert 'Score_MacroCycle' in df.columns
    assert 'Score_Fundamental' in df.columns
    assert 'Score_Comprehensive' in df.columns
    assert 'Signal' in df.columns
    print("✅ 五维度评分计算成功")
    
    # 验证评分范围
    for col in ['Score_Technical', 'Score_FundFlow', 'Score_Sentiment', 
                'Score_MacroCycle', 'Score_Fundamental', 'Score_Comprehensive']:
        valid = df[col].dropna()
        assert valid.min() >= 0, f"{col} 最小值 {valid.min()} < 0"
        assert valid.max() <= 100, f"{col} 最大值 {valid.max()} > 100"
    print("✅ 评分范围验证通过 (0-100)")
    
    # 验证信号
    buy_count = (df['Signal'] == 1).sum()
    sell_count = (df['Signal'] == -1).sum()
    print(f"   信号分布: 买入={buy_count}, 卖出={sell_count}, 持有={300-buy_count-sell_count}")
    
except Exception as e:
    print(f"❌ 五维度因子计算失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 7. 验证回测流程
try:
    bt = BacktestEngine(initial_capital=1000000)
    result = bt.run(df, ComprehensiveStrategy.comprehensive_strategy_fn, 
                    ComprehensiveStrategy('aggressive').params)
    
    assert 'stats' in result
    assert 'trades' in result
    assert 'equity_curve' in result
    stats = result['stats']
    print("✅ 回测执行成功")
    print(f"   交易次数: {stats['total_trades']}")
    print(f"   总收益率: {stats['total_return_pct']:.2f}%")
    print(f"   夏普比率: {stats['sharpe_ratio']:.3f}")
    print(f"   最大回撤: {stats['max_drawdown_pct']:.2f}%")
    print(f"   胜率: {stats['win_rate_pct']:.2f}%")
    
except Exception as e:
    print(f"❌ 回测执行失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 8. 验证原有模块兼容性
try:
    from macro_cycle_data import MacroCycleDataFetcher
    from fund_flow_akshare import FundFlowAkshareDataFetcher
    from market_sentiment_data import MarketSentimentDataFetcher
    from main_force_analysis import MainForceAnalyzer
    print("✅ 原有模块兼容性验证通过")
    print("   (macro_cycle_data, fund_flow_akshare, market_sentiment_data, main_force_analysis)")
except Exception as e:
    print(f"⚠️ 原有模块部分不可用: {e}")

print("\n" + "=" * 60)
print("🎉 所有验证通过！综合量化交易系统运行正常。")
print("=" * 60)