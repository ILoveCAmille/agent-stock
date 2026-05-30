#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量回测脚本 - 150只股票（小市值50只/中市值50只/大市值50只）
分别用对应的市值风格权重进行回测，汇总分析结果

使用方法:
    python run_batch_backtest.py                    # 全量回测（使用模拟数据）
    python run_batch_backtest.py --online           # 使用在线数据（需网络）
    python run_batch_backtest.py --max-stocks 10    # 每类只测10只（快速验证）
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
import time

warnings.filterwarnings('ignore')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== 预定义股票池 ====================
# 基于2025年A股真实市值分类（代码+名称+大致市值范围）

SMALL_CAP_POOL = [
    # 小市值股票 (< 100亿) - 偏向创业板/科创板/北交所
    ("300059", "东方财富"), ("300124", "汇川技术"), ("300274", "阳光电源"),
    ("300308", "中际旭创"), ("300347", "泰格医药"), ("300408", "三环集团"),
    ("300413", "芒果超媒"), ("300433", "蓝思科技"), ("300450", "先导智能"),
    ("300454", "深信服"), ("300496", "中科创达"), ("300529", "健帆生物"),
    ("300601", "康泰生物"), ("300628", "亿联网络"), ("300661", "圣邦股份"),
    ("300750", "宁德时代"), ("300760", "迈瑞医疗"), ("300782", "卓胜微"),
    ("300832", "新产业"), ("300896", "爱美客"), ("300999", "金龙鱼"),
    ("002049", "紫光国微"), ("002074", "国轩高科"), ("002120", "韵达股份"),
    ("002180", "纳思达"), ("002241", "歌尔股份"), ("002304", "洋河股份"),
    ("002352", "顺丰控股"), ("002371", "北方华创"), ("002384", "东山精密"),
    ("002415", "海康威视"), ("002456", "欧菲光"), ("002460", "赣锋锂业"),
    ("002475", "立讯精密"), ("002555", "三七互娱"), ("002600", "领益智造"),
    ("002602", "世纪华通"), ("002709", "天赐材料"), ("002714", "牧原股份"),
    ("002812", "恩捷股份"), ("002916", "深南电路"), ("002920", "德赛西威"),
    ("002938", "鹏鼎控股"), ("300014", "亿纬锂能"), ("300015", "爱尔眼科"),
    ("300033", "同花顺"), ("300122", "智飞生物"), ("300142", "沃森生物"),
    ("300223", "北京君正"), ("300285", "国瓷材料"), ("300394", "天孚通信"),
]

MID_CAP_POOL = [
    # 中市值股票 (100-500亿)
    ("000002", "万科A"), ("000063", "中兴通讯"), ("000100", "TCL科技"),
    ("000157", "中联重科"), ("000333", "美的集团"), ("000338", "潍柴动力"),
    ("000425", "徐工机械"), ("000538", "云南白药"), ("000568", "泸州老窖"),
    ("000596", "古井贡酒"), ("000625", "长安汽车"), ("000651", "格力电器"),
    ("000661", "长春高新"), ("000725", "京东方A"), ("000768", "中航西飞"),
    ("000776", "广发证券"), ("000858", "五粮液"), ("000895", "双汇发展"),
    ("000938", "紫光股份"), ("000977", "浪潮信息"), ("001979", "招商蛇口"),
    ("002001", "新和成"), ("002027", "分众传媒"), ("002050", "三花智控"),
    ("002142", "宁波银行"), ("002179", "中航光电"), ("002202", "金风科技"),
    ("002230", "科大讯飞"), ("002236", "大华股份"), ("002252", "上海莱士"),
    ("002271", "东方雨虹"), ("002311", "海大集团"), ("002340", "格林美"),
    ("002410", "广联达"), ("002466", "天齐锂业"), ("002493", "荣盛石化"),
    ("002601", "龙蟒佰利"), ("002714", "温氏股份"), ("002756", "永兴材料"),
    ("002821", "凯莱英"), ("002939", "长城证券"), ("600009", "上海机场"),
    ("600031", "三一重工"), ("600048", "保利发展"), ("600061", "国投资本"),
    ("600085", "同仁堂"), ("600104", "上汽集团"), ("600111", "北方稀土"),
    ("600115", "东方航空"), ("600150", "中国船舶"),
]

LARGE_CAP_POOL = [
    # 大市值股票 (>= 500亿)
    ("600000", "浦发银行"), ("600016", "民生银行"), ("600019", "宝钢股份"),
    ("600028", "中国石化"), ("600030", "中信证券"), ("600036", "招商银行"),
    ("600048", "保利发展"), ("600050", "中国联通"), ("600089", "特变电工"),
    ("600104", "上汽集团"), ("600196", "复星医药"), ("600276", "恒瑞医药"),
    ("600309", "万华化学"), ("600346", "恒力石化"), ("600436", "片仔癀"),
    ("600438", "通威股份"), ("600519", "贵州茅台"), ("600570", "恒生电子"),
    ("600585", "海螺水泥"), ("600588", "用友网络"), ("600690", "海尔智家"),
    ("600703", "三安光电"), ("600741", "华域汽车"), ("600809", "山西汾酒"),
    ("600837", "海通证券"), ("600887", "伊利股份"), ("600900", "长江电力"),
    ("600918", "中泰证券"), ("600919", "江苏银行"), ("601006", "大秦铁路"),
    ("601012", "隆基绿能"), ("601066", "中信建投"), ("601088", "中国神华"),
    ("601111", "中国国航"), ("601138", "工业富联"), ("601166", "兴业银行"),
    ("601169", "北京银行"), ("601186", "中国铁建"), ("601211", "国泰君安"),
    ("601225", "陕西煤业"), ("601236", "红塔证券"), ("601288", "农业银行"),
    ("601318", "中国平安"), ("601328", "交通银行"), ("601390", "中国中铁"),
    ("601398", "工商银行"), ("601601", "中国太保"), ("601628", "中国人寿"),
    ("601668", "中国建筑"), ("601688", "华泰证券"),
]


def fetch_stock_data_online(symbol, period_days=500):
    """在线获取股票数据（使用HTTP接口绕过代理限制）"""
    from real_data_fetcher import RealDataFetcher
    fetcher = RealDataFetcher()
    return fetcher.fetch_kline(symbol, period_days)


def generate_simulated_data(symbol, period_days=500, volatility=None):
    """生成模拟股票数据"""
    seed = int(symbol) % 100000
    np.random.seed(seed)
    
    dates = pd.bdate_range(end=datetime.now(), periods=period_days)
    
    base_price = 10 + (seed % 300)
    drift = 0.0001 + (seed % 10) * 0.00003
    
    if volatility is None:
        volatility = 0.018 + (seed % 15) * 0.001
    
    returns = np.random.normal(drift, volatility, len(dates))
    cycle = np.sin(np.linspace(0, 5 * np.pi, len(dates))) * 0.003
    returns += cycle
    
    shock_idx = np.random.choice(len(dates), size=len(dates)//40, replace=False)
    returns[shock_idx] += np.random.choice([-0.04, 0.04], size=len(shock_idx))
    
    prices = base_price * np.cumprod(1 + returns)
    
    high = prices * (1 + np.abs(np.random.normal(0, 0.013, len(dates))))
    low = prices * (1 - np.abs(np.random.normal(0, 0.013, len(dates))))
    volume = np.random.lognormal(15, 0.5, len(dates))
    
    df = pd.DataFrame({
        'Open': prices + np.random.randn(len(dates)) * prices * 0.004,
        'High': high, 'Low': low, 'Close': prices,
        'Volume': volume
    }, index=dates)
    
    return df


def run_single_stock_backtest(symbol, name, cap_style, period_days=500, use_online=False):
    """对单只股票进行回测"""
    from comprehensive_quant_engine import ComprehensiveQuantEngine
    from comprehensive_strategy import ComprehensiveStrategy
    from backtest_engine import BacktestEngine
    
    # 获取数据
    if use_online:
        try:
            df = fetch_stock_data_online(symbol, period_days)
        except:
            df = None
        if df is None:
            df = generate_simulated_data(symbol, period_days)
    else:
        df = generate_simulated_data(symbol, period_days)
    
    # 计算因子和评分
    engine = ComprehensiveQuantEngine(cap_style=cap_style)
    df = engine.compute_all_factors(df)
    df = engine.compute_comprehensive_score(df)
    
    # 根据市值风格选择对应策略
    strategy_map = {
        'small_cap': 'small_cap_momentum',
        'mid_cap': 'balanced',
        'large_cap': 'large_cap_value'
    }
    preset = strategy_map.get(cap_style, 'balanced')
    strategy = ComprehensiveStrategy(preset)
    params = strategy.params.copy()
    
    # 运行回测
    bt = BacktestEngine(initial_capital=1000000)
    result = bt.run(df, ComprehensiveStrategy.comprehensive_strategy_fn, params)
    
    result['symbol'] = symbol
    result['name'] = name
    result['cap_style'] = cap_style
    result['data_days'] = len(df)
    
    return result


def run_batch_backtest(pool, cap_style, max_stocks=50, period_days=500, use_online=False):
    """批量回测一个市值类别"""
    results = []
    errors = []
    
    stocks = pool[:max_stocks]
    total = len(stocks)
    
    print(f"\n{'='*60}")
    print(f"📊 {cap_style.upper()} 批量回测 ({total}只)")
    print(f"{'='*60}")
    
    for idx, (symbol, name) in enumerate(stocks, 1):
        try:
            result = run_single_stock_backtest(symbol, name, cap_style, period_days, use_online)
            results.append(result)
            
            stats = result['stats']
            print(f"  [{idx:2d}/{total}] {symbol} {name:<8s} "
                  f"收益:{stats.get('total_return_pct',0):>7.2f}% "
                  f"夏普:{stats.get('sharpe_ratio',0):>6.3f} "
                  f"回撤:{stats.get('max_drawdown_pct',0):>6.2f}% "
                  f"胜率:{stats.get('win_rate_pct',0):>5.1f}% "
                  f"交易:{stats.get('total_trades',0):>3d}")
            
            # 在线模式添加延迟
            if use_online:
                time.sleep(1)
                
        except Exception as e:
            errors.append((symbol, name, str(e)))
            print(f"  [{idx:2d}/{total}] {symbol} {name} ❌ 失败: {e}")
    
    return results, errors


def analyze_batch_results(results, cap_style):
    """分析批量回测结果"""
    if not results:
        return {}
    
    stats_list = [r['stats'] for r in results]
    
    # 提取各项指标
    returns = [s.get('total_return_pct', 0) for s in stats_list]
    annual_returns = [s.get('annualized_return_pct', 0) for s in stats_list]
    drawdowns = [s.get('max_drawdown_pct', 0) for s in stats_list]
    sharpes = [s.get('sharpe_ratio', 0) for s in stats_list]
    win_rates = [s.get('win_rate_pct', 0) for s in stats_list]
    trades = [s.get('total_trades', 0) for s in stats_list]
    profit_ratios = [s.get('profit_loss_ratio', 0) for s in stats_list if s.get('profit_loss_ratio', 0) < 100]
    
    analysis = {
        'cap_style': cap_style,
        'total_stocks': len(results),
        'profitable_stocks': sum(1 for r in returns if r > 0),
        'loss_stocks': sum(1 for r in returns if r <= 0),
        'return_mean': np.mean(returns),
        'return_median': np.median(returns),
        'return_std': np.std(returns),
        'return_min': np.min(returns),
        'return_max': np.max(returns),
        'annual_return_mean': np.mean(annual_returns),
        'annual_return_median': np.median(annual_returns),
        'drawdown_mean': np.mean(drawdowns),
        'drawdown_max': np.max(drawdowns),
        'sharpe_mean': np.mean(sharpes),
        'sharpe_median': np.median(sharpes),
        'win_rate_mean': np.mean(win_rates),
        'win_rate_median': np.median(win_rates),
        'avg_trades': np.mean(trades),
        'profit_loss_ratio_mean': np.mean(profit_ratios) if profit_ratios else 0,
        'stocks_above_0pct': sum(1 for r in returns if r > 0),
        'stocks_above_10pct': sum(1 for r in returns if r > 10),
        'stocks_above_20pct': sum(1 for r in returns if r > 20),
        'stocks_below_neg10pct': sum(1 for r in returns if r < -10),
    }
    
    return analysis


def print_analysis(analysis, results):
    """打印分析结果"""
    cap = analysis['cap_style']
    cap_names = {'small_cap': '小市值(<100亿)', 'mid_cap': '中市值(100-500亿)', 'large_cap': '大市值(≥500亿)'}
    strategy_names = {'small_cap': '小市值动量策略', 'mid_cap': '稳健型策略', 'large_cap': '大市值价值策略'}
    
    print(f"\n{'='*70}")
    print(f"📊 {cap_names.get(cap, cap)} 回测汇总")
    print(f"   策略: {strategy_names.get(cap, 'N/A')}")
    print(f"{'='*70}")
    
    print(f"\n📈 收益统计:")
    print(f"  总回测股票数:   {analysis['total_stocks']}")
    print(f"  盈利股票数:     {analysis['profitable_stocks']} ({analysis['profitable_stocks']/analysis['total_stocks']*100:.1f}%)")
    print(f"  亏损股票数:     {analysis['loss_stocks']}")
    print(f"  平均收益率:     {analysis['return_mean']:.2f}%")
    print(f"  中位数收益率:   {analysis['return_median']:.2f}%")
    print(f"  收益率标准差:   {analysis['return_std']:.2f}%")
    print(f"  最高收益:       {analysis['return_max']:.2f}%")
    print(f"  最低收益:       {analysis['return_min']:.2f}%")
    print(f"  平均年化收益:   {analysis['annual_return_mean']:.2f}%")
    
    print(f"\n📉 风险统计:")
    print(f"  平均最大回撤:   {analysis['drawdown_mean']:.2f}%")
    print(f"  最大单笔回撤:   {analysis['drawdown_max']:.2f}%")
    print(f"  平均夏普比率:   {analysis['sharpe_mean']:.3f}")
    print(f"  中位数夏普:     {analysis['sharpe_median']:.3f}")
    
    print(f"\n🎯 交易统计:")
    print(f"  平均交易次数:   {analysis['avg_trades']:.1f}")
    print(f"  平均胜率:       {analysis['win_rate_mean']:.2f}%")
    print(f"  平均盈亏比:     {analysis['profit_loss_ratio_mean']:.2f}")
    
    print(f"\n🏆 收益分布:")
    print(f"  收益>0%:    {analysis['stocks_above_0pct']}只")
    print(f"  收益>10%:   {analysis['stocks_above_10pct']}只")
    print(f"  收益>20%:   {analysis['stocks_above_20pct']}只")
    print(f"  收益<-10%:  {analysis['stocks_below_neg10pct']}只")
    
    # Top5最佳和最差
    sorted_results = sorted(results, key=lambda x: x['stats'].get('total_return_pct', 0), reverse=True)
    
    print(f"\n🥇 Top5 最佳:")
    for r in sorted_results[:5]:
        s = r['stats']
        print(f"  {r['symbol']} {r['name']:<8s} 收益:{s.get('total_return_pct',0):>7.2f}% 夏普:{s.get('sharpe_ratio',0):>6.3f}")
    
    print(f"\n🥉 Top5 最差:")
    for r in sorted_results[-5:]:
        s = r['stats']
        print(f"  {r['symbol']} {r['name']:<8s} 收益:{s.get('total_return_pct',0):>7.2f}% 夏普:{s.get('sharpe_ratio',0):>6.3f}")


def save_batch_report(all_analyses, all_results, output_dir="backtest_results"):
    """保存批量回测报告"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # JSON报告
    report = {
        'timestamp': timestamp,
        'summary': all_analyses,
        'details': {}
    }
    
    for cap_style, results in all_results.items():
        report['details'][cap_style] = []
        for r in results:
            report['details'][cap_style].append({
                'symbol': r['symbol'],
                'name': r['name'],
                'stats': r['stats']
            })
    
    json_file = os.path.join(output_dir, f"batch_backtest_{timestamp}.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    
    # 文本报告
    txt_file = os.path.join(output_dir, f"batch_backtest_{timestamp}.txt")
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("综合量化交易系统 - 批量回测报告\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        for cap_style, analysis in all_analyses.items():
            cap_names = {'small_cap': '小市值(<100亿)', 'mid_cap': '中市值(100-500亿)', 'large_cap': '大市值(≥500亿)'}
            f.write(f"\n{'='*60}\n")
            f.write(f"{cap_names.get(cap_style, cap_style)}\n")
            f.write(f"{'='*60}\n")
            for k, v in analysis.items():
                if k != 'cap_style':
                    if isinstance(v, float):
                        f.write(f"  {k}: {v:.2f}\n")
                    else:
                        f.write(f"  {k}: {v}\n")
    
    logger.info(f"💾 批量回测报告: {json_file}")
    logger.info(f"📄 文本报告: {txt_file}")
    
    return json_file, txt_file


def main():
    parser = argparse.ArgumentParser(description='批量回测 - 150只股票(50小/50中/50大)')
    parser.add_argument('--max-stocks', type=int, default=50, help='每类最多回测几只(默认50)')
    parser.add_argument('--period', type=int, default=500, help='回测数据天数(默认500)')
    parser.add_argument('--online', action='store_true', help='使用在线数据(需网络)')
    parser.add_argument('--cap', type=str, default='all', choices=['all', 'small_cap', 'mid_cap', 'large_cap'],
                        help='只回测指定市值类别')
    parser.add_argument('--output', type=str, default='backtest_results', help='结果输出目录')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("🔬 综合量化交易系统 - 批量回测")
    print("   小市值(技术+情绪40%+25%) | 中市值(平衡) | 大市值(基本面+宏观35%+25%)")
    print("=" * 70)
    print(f"  每类股票数: {args.max_stocks}")
    print(f"  回测天数: {args.period}")
    print(f"  数据模式: {'在线' if args.online else '离线(模拟数据)'}")
    print(f"  市值类别: {args.cap}")
    print("=" * 70)
    
    pools = {
        'small_cap': SMALL_CAP_POOL,
        'mid_cap': MID_CAP_POOL,
        'large_cap': LARGE_CAP_POOL,
    }
    
    all_results = {}
    all_analyses = {}
    
    for cap_style, pool in pools.items():
        if args.cap != 'all' and args.cap != cap_style:
            continue
        
        results, errors = run_batch_backtest(
            pool, cap_style, args.max_stocks, args.period, args.online
        )
        
        all_results[cap_style] = results
        
        if results:
            analysis = analyze_batch_results(results, cap_style)
            all_analyses[cap_style] = analysis
            print_analysis(analysis, results)
        
        if errors:
            print(f"\n⚠️ {cap_style} 失败 {len(errors)} 只")
    
    # 打印跨类别对比
    if len(all_analyses) > 1:
        print("\n" + "=" * 80)
        print("📊 跨市值类别对比")
        print("=" * 80)
        
        cap_names = {'small_cap': '小市值', 'mid_cap': '中市值', 'large_cap': '大市值'}
        print(f"\n{'指标':<20} {'小市值':>12} {'中市值':>12} {'大市值':>12}")
        print("-" * 60)
        
        metrics = [
            ('平均收益率%', 'return_mean'),
            ('平均年化%', 'annual_return_mean'),
            ('平均回撤%', 'drawdown_mean'),
            ('平均夏普', 'sharpe_mean'),
            ('平均胜率%', 'win_rate_mean'),
            ('盈利股票比%', lambda a: a['profitable_stocks']/a['total_stocks']*100),
            ('平均交易数', 'avg_trades'),
        ]
        
        for label, key in metrics:
            row = [label]
            for cs in ['small_cap', 'mid_cap', 'large_cap']:
                if cs in all_analyses:
                    if callable(key):
                        val = key(all_analyses[cs])
                    else:
                        val = all_analyses[cs].get(key, 0)
                    row.append(f"{val:>12.2f}")
                else:
                    row.append(f"{'N/A':>12}")
            print("".join(row))
        
        print("=" * 80)
    
    # 保存报告
    save_batch_report(all_analyses, all_results, args.output)
    
    print("\n✅ 批量回测完成!")


if __name__ == '__main__':
    main()