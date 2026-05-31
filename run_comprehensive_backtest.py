#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合量化策略回测脚本
整合五维度评分系统进行历史数据回测

使用方法:
    python run_comprehensive_backtest.py                    # 默认回测
    python run_comprehensive_backtest.py --stock 600519     # 指定股票
    python run_comprehensive_backtest.py --preset aggressive # 指定策略类型
    python run_comprehensive_backtest.py --compare           # 对比所有策略
"""

import sys
import os
import logging
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import json

warnings.filterwarnings('ignore')

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_stock_data(symbol: str, period_days: int = 750) -> pd.DataFrame:
    """
    获取股票历史数据（使用新浪K线API + 东方财富备用）
    
    Args:
        symbol: 股票代码
        period_days: 获取天数（建议至少750天以确保有足够的MA250数据）
    
    Returns:
        标准化的OHLCV DataFrame
    """
    from real_data_fetcher import RealDataFetcher
    
    logger.info(f"正在获取 {symbol} 的历史数据...")
    
    fetcher = RealDataFetcher()
    df = fetcher.fetch_kline(symbol, period_days)
    
    if df is not None and len(df) > 60:
        logger.info(f"✅ 成功获取 {len(df)} 条真实数据 ({df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')})")
        return df
    
    logger.warning("真实数据获取失败，切换到模拟数据...")
    return _generate_simulated_data(symbol, period_days)


def _generate_simulated_data(symbol: str, period_days: int = 750) -> pd.DataFrame:
    """生成模拟股票数据用于离线回测"""
    seed = int(symbol) % 100000
    np.random.seed(seed)
    
    dates = pd.bdate_range(end=datetime.now(), periods=period_days)
    
    base_price = 50 + (seed % 200)
    drift = 0.0002 + (seed % 10) * 0.00005
    volatility = 0.015 + (seed % 20) * 0.001
    
    # 添加趋势周期
    returns = np.random.normal(drift, volatility, len(dates))
    cycle = np.sin(np.linspace(0, 6 * np.pi, len(dates))) * 0.002
    returns += cycle
    
    # 添加事件冲击
    shock_indices = np.random.choice(len(dates), size=len(dates)//50, replace=False)
    returns[shock_indices] += np.random.choice([-0.05, 0.05], size=len(shock_indices))
    
    prices = base_price * np.cumprod(1 + returns)
    
    high = prices * (1 + np.abs(np.random.normal(0, 0.012, len(dates))))
    low = prices * (1 - np.abs(np.random.normal(0, 0.012, len(dates))))
    volume = np.random.lognormal(15, 0.5, len(dates)).astype(float)
    
    df = pd.DataFrame({
        'Open': prices + np.random.randn(len(dates)) * prices * 0.005,
        'High': high,
        'Low': low,
        'Close': prices,
        'Volume': volume
    }, index=dates)
    
    logger.info(f"✅ 已生成 {len(df)} 条模拟数据")
    return df


def fetch_market_index(period_days: int = 750) -> pd.DataFrame:
    """获取大盘指数数据（上证指数）"""
    import akshare as ak
    
    for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        os.environ.pop(key, None)
    
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y%m%d')
    
    try:
        df = ak.stock_zh_a_hist(
            symbol="000001", period="daily",
            start_date=start_date, end_date=end_date, adjust="qfq"
        )
        
        if df is not None and not df.empty:
            df = df.rename(columns={
                '日期': 'Date', '开盘': 'Open', '收盘': 'Close',
                '最高': 'High', '最低': 'Low', '成交量': 'Volume'
            })
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            logger.info(f"✅ 获取上证指数数据 {len(df)} 条")
            return df
    except Exception as e:
        logger.warning(f"获取上证指数失败: {e}")
    
    return None


def prepare_comprehensive_data(df: pd.DataFrame, market_df: pd.DataFrame = None,
                                cap_style: str = None, stock_code: str = None) -> pd.DataFrame:
    """
    准备综合回测数据：计算所有因子和五维度评分
    
    Args:
        df: 股票OHLCV数据
        market_df: 大盘数据(可选)
    
    Returns:
        包含所有因子和评分的DataFrame
    """
    from comprehensive_quant_engine import ComprehensiveQuantEngine
    
    if cap_style:
        engine = ComprehensiveQuantEngine(cap_style=cap_style)
        logger.info(f"🎯 使用{ComprehensiveQuantEngine.CAP_STYLE_WEIGHTS[cap_style]['name']}权重")
    else:
        detected_style = ComprehensiveQuantEngine.detect_cap_style(stock_code=stock_code)
        engine = ComprehensiveQuantEngine(cap_style=detected_style)
        logger.info(f"🔍 自动检测市值风格: {detected_style} ({ComprehensiveQuantEngine.CAP_STYLE_WEIGHTS[detected_style]['name']})")
    
    # 1. 计算基础技术因子
    logger.info("📊 步骤1/2: 计算基础技术因子...")
    df = engine.compute_all_factors(df, market_df)
    
    # 2. 计算五维度综合评分
    logger.info("📊 步骤2/2: 计算五维度综合评分...")
    df = engine.compute_comprehensive_score(df, market_df)
    
    return df


def run_single_backtest(df: pd.DataFrame, preset: str = 'balanced', 
                         custom_params: dict = None) -> dict:
    """运行单个策略回测"""
    from backtest_engine import BacktestEngine
    from comprehensive_strategy import ComprehensiveStrategy
    
    bt = BacktestEngine(initial_capital=1000000)
    strategy = ComprehensiveStrategy(preset, custom_params)
    
    params = strategy.params.copy()
    
    logger.info(f"\n🚀 运行 {params['name']} 回测...")
    result = bt.run(df, ComprehensiveStrategy.comprehensive_strategy_fn, params)
    
    return result


def run_comparison_backtest(df: pd.DataFrame) -> dict:
    """运行多策略对比回测"""
    from backtest_engine import BacktestEngine
    from comprehensive_strategy import MultiStrategyComparator
    
    bt = BacktestEngine(initial_capital=1000000)
    comparator = MultiStrategyComparator()
    comparator.add_all_presets()
    
    results = comparator.run_comparison(df, bt)
    
    return results


def print_score_summary(df: pd.DataFrame):
    """打印评分统计摘要"""
    score_cols = [
        'Score_Technical', 'Score_FundFlow', 'Score_Sentiment',
        'Score_MacroCycle', 'Score_Fundamental', 'Score_Comprehensive'
    ]
    
    print("\n" + "=" * 80)
    print("📊 五维度评分统计摘要")
    print("=" * 80)
    
    print(f"\n{'维度':<25} {'均值':>8} {'中位数':>8} {'最小值':>8} {'最大值':>8} {'标准差':>8}")
    print("-" * 75)
    
    for col in score_cols:
        if col in df.columns:
            data = df[col].dropna()
            name = col.replace('Score_', '')
            print(f"{name:<25} {data.mean():>8.2f} {data.median():>8.2f} {data.min():>8.2f} {data.max():>8.2f} {data.std():>8.2f}")
    
    # 信号统计
    if 'Signal' in df.columns:
        buy_count = (df['Signal'] == 1).sum()
        sell_count = (df['Signal'] == -1).sum()
        hold_count = (df['Signal'] == 0).sum()
        total = len(df)
        
        print(f"\n信号分布: 买入={buy_count}({buy_count/total*100:.1f}%) "
              f"卖出={sell_count}({sell_count/total*100:.1f}%) "
              f"持有={hold_count}({hold_count/total*100:.1f}%)")


def print_comparison_report(results: dict):
    """打印策略对比报告"""
    print("\n" + "=" * 100)
    print("📊 综合策略对比报告")
    print("=" * 100)
    
    # 按夏普比率排序
    sorted_results = sorted(
        results.items(),
        key=lambda x: x[1]['stats'].get('sharpe_ratio', -999),
        reverse=True
    )
    
    print(f"\n{'排名':<4} {'策略名称':<20} {'总收益%':>10} {'年化%':>10} {'回撤%':>8} {'夏普':>8} {'胜率%':>8} {'盈亏比':>8} {'交易数':>6} {'持仓天':>6}")
    print("-" * 100)
    
    for rank, (name, result) in enumerate(sorted_results, 1):
        stats = result['stats']
        print(f"{rank:<4} {name:<20} "
              f"{stats.get('total_return_pct', 0):>10.2f} "
              f"{stats.get('annualized_return_pct', 0):>10.2f} "
              f"{stats.get('max_drawdown_pct', 0):>8.2f} "
              f"{stats.get('sharpe_ratio', 0):>8.3f} "
              f"{stats.get('win_rate_pct', 0):>8.2f} "
              f"{stats.get('profit_loss_ratio', 0):>8.2f} "
              f"{stats.get('total_trades', 0):>6d} "
              f"{stats.get('avg_holding_days', 0):>6.1f}")
    
    print("=" * 100)
    
    # 找出最优策略
    if sorted_results:
        best_name, best_result = sorted_results[0]
        print(f"\n🏆 最优策略: {best_name}")
        print(f"   夏普比率: {best_result['stats'].get('sharpe_ratio', 0):.3f}")
        print(f"   年化收益: {best_result['stats'].get('annualized_return_pct', 0):.2f}%")
        print(f"   最大回撤: {best_result['stats'].get('max_drawdown_pct', 0):.2f}%")
        print(f"   胜率: {best_result['stats'].get('win_rate_pct', 0):.2f}%")


def save_results(results: dict, symbol: str, output_dir: str = "backtest_results"):
    """保存回测结果"""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 保存JSON
    save_data = {
        'symbol': symbol,
        'timestamp': timestamp,
        'strategies': {}
    }
    
    for name, result in results.items():
        save_data['strategies'][name] = {
            'stats': result['stats'],
            'params': result.get('params', {}),
            'trades_count': len(result.get('trades', []))
        }
    
    json_file = os.path.join(output_dir, f"backtest_{symbol}_{timestamp}.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    # 保存文本报告
    txt_file = os.path.join(output_dir, f"backtest_{symbol}_{timestamp}.txt")
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(f"{'='*80}\n")
        f.write(f"综合量化策略回测报告\n")
        f.write(f"股票代码: {symbol}\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*80}\n\n")
        
        for name, result in results.items():
            stats = result['stats']
            f.write(f"【{name}】\n")
            f.write(f"  初始资金: ¥{stats.get('initial_capital', 0):,.2f}\n")
            f.write(f"  最终权益: ¥{stats.get('final_value', 0):,.2f}\n")
            f.write(f"  总收益率: {stats.get('total_return_pct', 0):.2f}%\n")
            f.write(f"  年化收益: {stats.get('annualized_return_pct', 0):.2f}%\n")
            f.write(f"  最大回撤: {stats.get('max_drawdown_pct', 0):.2f}%\n")
            f.write(f"  夏普比率: {stats.get('sharpe_ratio', 0):.3f}\n")
            f.write(f"  胜率: {stats.get('win_rate_pct', 0):.2f}%\n")
            f.write(f"  盈亏比: {stats.get('profit_loss_ratio', 0):.2f}\n")
            f.write(f"  交易次数: {stats.get('total_trades', 0)}\n")
            f.write(f"  平均持仓: {stats.get('avg_holding_days', 0):.1f}天\n")
            f.write(f"\n")
    
    logger.info(f"💾 结果已保存: {json_file}")
    logger.info(f"📄 文本报告: {txt_file}")
    
    return json_file, txt_file


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='综合量化策略回测')
    parser.add_argument('--stock', type=str, default='600519', help='股票代码（默认: 600519 贵州茅台）')
    parser.add_argument('--preset', type=str, default='balanced', 
                        choices=['aggressive', 'balanced', 'conservative', 
                                 'small_cap_momentum', 'large_cap_value'],
                        help='策略类型（默认: balanced）')
    parser.add_argument('--cap-style', type=str, default=None,
                        choices=['small_cap', 'mid_cap', 'large_cap'],
                        help='市值风格（small_cap重技术+情绪，large_cap重基本面+宏观）')
    parser.add_argument('--market-cap', type=float, default=None,
                        help='股票总市值（亿元），用于自动判断市值风格')
    parser.add_argument('--period', type=int, default=750, help='回测数据天数（默认: 750）')
    parser.add_argument('--compare', action='store_true', help='对比所有策略')
    parser.add_argument('--no-market', action='store_true', help='不获取大盘数据')
    parser.add_argument('--simulated', action='store_true', help='强制使用模拟数据（不联网）')
    parser.add_argument('--output', type=str, default='backtest_results', help='结果输出目录')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("🔬 综合量化交易策略回测系统")
    print("   整合: 技术指标 | 资金流向 | 散户情绪 | 经济周期 | 股票基本面")
    print("=" * 80)
    cap_style = args.cap_style
    if cap_style is None and args.market_cap is not None:
        from comprehensive_quant_engine import ComprehensiveQuantEngine
        cap_style = ComprehensiveQuantEngine.detect_cap_style(
            market_cap=args.market_cap, stock_code=args.stock)
    
    print(f"  股票代码: {args.stock}")
    print(f"  策略类型: {args.preset}")
    print(f"  市值风格: {cap_style or '自动(默认mid_cap)'}")
    print(f"  回测天数: {args.period}")
    print(f"  对比模式: {'是' if args.compare else '否'}")
    print("=" * 80)
    
    # 1. 获取数据
    print("\n📥 步骤1: 获取历史数据...")
    if args.simulated:
        logger.info("使用模拟数据模式")
        df = _generate_simulated_data(args.stock, args.period)
    else:
        df = fetch_stock_data(args.stock, args.period)
    
    if df is None or len(df) < 120:
        logger.error("❌ 数据不足，无法进行回测（需要至少120条数据）")
        sys.exit(1)
    
    # 2. 获取大盘数据（可选）
    market_df = None
    if not args.no_market:
        print("\n📥 获取大盘指数数据...")
        market_df = fetch_market_index(args.period)
    
    # 3. 计算综合因子和评分
    print("\n📊 步骤2: 计算五维度综合因子和评分...")
    df = prepare_comprehensive_data(df, market_df, cap_style=cap_style, stock_code=args.stock)
    
    # 打印评分摘要
    print_score_summary(df)
    
    # 4. 运行回测
    if args.compare:
        print("\n🔄 步骤3: 运行多策略对比回测...")
        results = run_comparison_backtest(df)
        print_comparison_report(results)
    else:
        print(f"\n🔄 步骤3: 运行 {args.preset} 策略回测...")
        result = run_single_backtest(df, args.preset)
        
        from backtest_engine import BacktestEngine
        bt = BacktestEngine(initial_capital=1000000)
        bt.print_report(result)
        
        results = {args.preset: result}
    
    # 5. 保存结果
    print("\n💾 步骤4: 保存回测结果...")
    save_results(results, args.stock, args.output)
    
    print("\n✅ 回测完成!")
    
    return results


if __name__ == '__main__':
    results = main()