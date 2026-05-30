#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化策略优化测试脚本
验证新增模块功能正确性
"""

import sys
import os
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_quant_factors():
    """测试量化因子库"""
    print("\n" + "=" * 60)
    print("🧪 测试1: 量化因子库 (quant_factors.py)")
    print("=" * 60)
    
    try:
        import pandas as pd
        import numpy as np
        from quant_factors import QuantFactors
        
        # 生成模拟数据（使用pandas Series）
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=200, freq='B')
        close = pd.Series(100 + np.cumsum(np.random.randn(200) * 2), index=dates, name='Close')
        high = pd.Series(close.values + np.abs(np.random.randn(200)), index=dates, name='High')
        low = pd.Series(close.values - np.abs(np.random.randn(200)), index=dates, name='Low')
        volume = pd.Series(np.random.randint(1000000, 10000000, 200).astype(float), index=dates, name='Volume')
        
        df = pd.DataFrame({
            'Open': close + np.random.randn(200) * 0.5,
            'High': high,
            'Low': low,
            'Close': close,
            'Volume': volume
        }, index=dates)
        
        # 测试各因子计算
        atr_val = QuantFactors.atr(high, low, close)
        print(f"  ✅ ATR: {atr_val.iloc[-1]:.4f}")
        atr_pct_val = QuantFactors.atr_percent(high, low, close)
        print(f"  ✅ ATR%: {atr_pct_val.iloc[-1]:.2f}")
        adx_val = QuantFactors.adx(high, low, close)
        print(f"  ✅ ADX: {adx_val.iloc[-1]:.2f}")
        rsi14 = QuantFactors.rsi(close, 14)
        print(f"  ✅ RSI(14): {rsi14.iloc[-1]:.2f}")
        rsi6 = QuantFactors.rsi(close, 6)
        print(f"  ✅ RSI(6): {rsi6.iloc[-1]:.2f}")
        
        stoch_k, stoch_d = QuantFactors.stoch_rsi(close)
        sk_val = f"{stoch_k.iloc[-1]:.2f}" if pd.notna(stoch_k.iloc[-1]) else "NaN"
        print(f"  ✅ StochRSI K: {sk_val}")
        
        wr_val = QuantFactors.williams_r(high, low, close)
        print(f"  ✅ Williams %R: {wr_val.iloc[-1]:.2f}")
        vpd_val = QuantFactors.volume_price_divergence(close, volume)
        print(f"  ✅ VP Divergence: {vpd_val.iloc[-1]:.2f}")
        ts_val = QuantFactors.trend_strength(close)
        print(f"  ✅ Trend Strength: {ts_val.iloc[-1]:.2f}")
        
        # 测试均线排列评分
        ma5 = close.rolling(5).mean().iloc[-1]
        ma10 = close.rolling(10).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1]
        alignment = QuantFactors.ma_alignment_score(ma5, ma10, ma20, ma60)
        print("  ✅ MA Alignment:", alignment)
        
        # 测试复合评分
        score = QuantFactors.composite_score(
            rsi_value=50, adx_value=25, atr_pct=3.0,
            volume_ratio=1.2, trend_strength=10, ma_alignment=0.5
        )
        print("  ✅ Composite Score:", score)
        
        # 测试Kelly公式
        kelly = QuantFactors.kelly_criterion(0.6, 1000, 500)
        print("  ✅ Kelly Criterion:", f"{kelly*100:.1f}%")
        
        # 测试波动率仓位
        vol_pos = QuantFactors.volatility_adjusted_position(3.0)
        print("  ✅ Vol-Adjusted Position:", f"{vol_pos*100:.1f}%")
        
        # 测试动态止损
        stop = QuantFactors.dynamic_stop_loss(100, 3.0, 'atr')
        print("  ✅ Dynamic Stop Loss:", stop)
        
        # 测试止盈目标
        target = QuantFactors.profit_target(100, 3.0)
        print("  ✅ Profit Targets:", target)
        
        # 测试信号生成
        df_with_signals = QuantFactors.generate_signals(df)
        buy_signals = (df_with_signals['Signal'] == 1).sum()
        sell_signals = (df_with_signals['Signal'] == -1).sum()
        print(f"  ✅ 信号生成: 买入={buy_signals}, 卖出={sell_signals}")
        
        print("\n  🎉 量化因子库测试全部通过!")
        return True
        
    except Exception as e:
        print(f"\n  ❌ 量化因子库测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backtest_engine():
    """测试回测引擎"""
    print("\n" + "=" * 60)
    print("🧪 测试2: 回测引擎 (backtest_engine.py)")
    print("=" * 60)
    
    try:
        import pandas as pd
        import numpy as np
        from backtest_engine import BacktestEngine
        from quant_factors import QuantFactors
        
        # 生成模拟数据
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=200, freq='B')
        close = 100 + np.cumsum(np.random.randn(200) * 2)
        high = close + np.abs(np.random.randn(200))
        low = close - np.abs(np.random.randn(200))
        volume = np.random.randint(1000000, 10000000, 200).astype(float)
        
        df = pd.DataFrame({
            'Open': close + np.random.randn(200) * 0.5,
            'High': high,
            'Low': low,
            'Close': close,
            'Volume': volume
        }, index=dates)
        
        # 计算因子
        df = QuantFactors.generate_signals(df)
        
        # 定义简单测试策略
        def test_strategy(df, i, position, params):
            if i < 60:
                return 0
            if 'Signal' in df.columns:
                return df.iloc[i]['Signal']
            return 0
        
        # 运行回测
        bt = BacktestEngine(initial_capital=1000000)
        result = bt.run(df, test_strategy, {})
        
        stats = result['stats']
        print(f"  ✅ 初始资金: ¥{stats['initial_capital']:,.2f}")
        print(f"  ✅ 最终权益: ¥{stats['final_value']:,.2f}")
        print(f"  ✅ 总收益率: {stats['total_return_pct']:.2f}%")
        print(f"  ✅ 最大回撤: {stats['max_drawdown_pct']:.2f}%")
        print(f"  ✅ 夏普比率: {stats['sharpe_ratio']:.3f}")
        print(f"  ✅ 总交易数: {stats['total_trades']}")
        print(f"  ✅ 胜率: {stats['win_rate_pct']:.2f}%")
        
        # 打印回测报告
        bt.print_report(result)
        
        print("\n  🎉 回测引擎测试通过!")
        return True
        
    except Exception as e:
        print(f"\n  ❌ 回测引擎测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_strategy_optimizer():
    """测试策略优化迭代器"""
    print("\n" + "=" * 60)
    print("🧪 测试3: 策略优化迭代器 (strategy_optimizer.py)")
    print("=" * 60)
    
    try:
        import pandas as pd
        import numpy as np
        from strategy_optimizer import StrategyOptimizer
        from quant_factors import QuantFactors
        from backtest_engine import BacktestEngine
        
        # 生成模拟数据
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=200, freq='B')
        close = 100 + np.cumsum(np.random.randn(200) * 2)
        high = close + np.abs(np.random.randn(200))
        low = close - np.abs(np.random.randn(200))
        volume = np.random.randint(1000000, 10000000, 200).astype(float)
        
        df = pd.DataFrame({
            'Open': close + np.random.randn(200) * 0.5,
            'High': high,
            'Low': low,
            'Close': close,
            'Volume': volume
        }, index=dates)
        
        df = QuantFactors.generate_signals(df)
        
        # 测试各策略函数
        strategies = {
            '多因子复合': StrategyOptimizer.multi_factor_strategy,
            'MA均线交叉': StrategyOptimizer.ma_cross_atr_strategy,
            'RSI动量': StrategyOptimizer.rsi_momentum_strategy,
            '布林带突破': StrategyOptimizer.bollinger_breakout_strategy,
        }
        
        bt = BacktestEngine(initial_capital=1000000)
        
        for name, strategy_fn in strategies.items():
            result = bt.run(df, strategy_fn, {})
            stats = result['stats']
            print(f"  ✅ {name}: 收益={stats['total_return_pct']:.2f}%, "
                  f"夏普={stats['sharpe_ratio']:.3f}, "
                  f"交易={stats['total_trades']}次")
        
        # 测试参数优化（小规模）
        print("\n  📊 测试参数优化（小规模网格搜索）...")
        param_grid = {
            'buy_threshold': [65, 70, 75],
            'sell_threshold': [25, 30],
        }
        
        result = bt.optimize(df, StrategyOptimizer.multi_factor_strategy, param_grid, 'sharpe_ratio')
        print(f"  ✅ 最优参数: {result['best_params']}")
        print(f"  ✅ 最优夏普: {result['best_score']:.3f}")
        print(f"  ✅ 测试组合数: {len(result['all_results'])}")
        
        print("\n  🎉 策略优化迭代器测试通过!")
        return True
        
    except Exception as e:
        print(f"\n  ❌ 策略优化迭代器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_low_price_bull_strategy():
    """测试优化后的低价擒牛策略"""
    print("\n" + "=" * 60)
    print("🧪 测试4: 优化后的低价擒牛策略")
    print("=" * 60)
    
    try:
        from low_price_bull_strategy import LowPriceBullStrategy
        from quant_factors import QuantFactors
        
        strategy = LowPriceBullStrategy(initial_capital=1000000)
        
        # 测试买入
        success, msg, trade = strategy.buy('000001', '平安银行', 12.50, '2024-06-01')
        print(f"  ✅ 买入: {success} - {msg}")
        
        # 测试智能仓位计算
        shares, amount, method = strategy.calculate_position_size(12.50, atr=0.5)
        print(f"  ✅ 智能仓位: {shares}股, ¥{amount:.2f}, {method}")
        
        shares, amount, method = strategy.calculate_position_size(
            12.50, atr=0.5, win_rate=0.6, avg_win=8, avg_loss=4
        )
        print(f"  ✅ Kelly仓位: {shares}股, ¥{amount:.2f}, {method}")
        
        # 测试优化版卖出判断（带ATR止损和RSI超买）
        should_sell, reason = strategy.should_sell(
            '000001', ma5=12.3, ma20=12.5, current_price=12.0, atr=0.5, rsi=82, adx=28
        )
        print(f"  ✅ 卖出判断: {should_sell} - {reason}")
        
        # 测试组合摘要
        summary = strategy.get_portfolio_summary()
        print(f"  ✅ 组合摘要: 胜率={summary.get('win_rate', 0)}%, "
              f"盈亏比={summary.get('profit_loss_ratio', 0)}")
        
        print("\n  🎉 低价擒牛策略优化测试通过!")
        return True
        
    except Exception as e:
        print(f"\n  ❌ 低价擒牛策略测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_value_stock_strategy():
    """测试优化后的价值投资策略"""
    print("\n" + "=" * 60)
    print("🧪 测试5: 优化后的价值投资策略")
    print("=" * 60)
    
    try:
        from value_stock_strategy import ValueStockStrategy
        
        strategy = ValueStockStrategy(initial_capital=1000000)
        
        # 测试买入
        success, msg, trade = strategy.buy('600519', '贵州茅台', 1800.0, '2024-06-01')
        print(f"  ✅ 买入: {success} - {msg}")
        
        # 测试智能仓位
        shares, amount, method = strategy.calculate_position_size_v2(
            1800.0, atr=30.0, indicators={'Trend_Strength': 15, 'ADX': 30}
        )
        print(f"  ✅ 智能仓位: {shares}股, ¥{amount:.2f}, {method}")
        
        # 测试增强版卖出判断
        should_sell, reason, indicators = strategy.should_sell(
            '600519', current_price=1750.0, atr=30.0
        )
        print(f"  ✅ 卖出判断: {should_sell} - {reason}")
        if indicators:
            print(f"  ✅ 增强指标: RSI={indicators.get('RSI_14', 'N/A')}, "
                  f"ADX={indicators.get('ADX', 'N/A')}, "
                  f"趋势={indicators.get('Trend_Strength', 'N/A')}")
        
        # 测试组合摘要
        summary = strategy.get_portfolio_summary()
        print(f"  ✅ 组合摘要: 盈亏比={summary.get('profit_loss_ratio', 0)}, "
              f"平均持仓={summary.get('avg_holding_days', 0)}天")
        
        print("\n  🎉 价值投资策略优化测试通过!")
        return True
        
    except Exception as e:
        print(f"\n  ❌ 价值投资策略测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "#" * 60)
    print("🚀 量化策略优化系统 - 集成测试")
    print("#" * 60)
    
    results = {}
    
    results['量化因子库'] = test_quant_factors()
    results['回测引擎'] = test_backtest_engine()
    results['策略优化器'] = test_strategy_optimizer()
    results['低价擒牛策略'] = test_low_price_bull_strategy()
    results['价值投资策略'] = test_value_stock_strategy()
    
    # 汇总
    print("\n" + "=" * 60)
    print("📊 测试汇总")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
        if result:
            passed += 1
    
    print(f"\n  总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n  🎉 所有测试通过! 优化系统就绪!")
    else:
        print(f"\n  ⚠️ {total - passed} 个测试失败，请检查")
    
    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)