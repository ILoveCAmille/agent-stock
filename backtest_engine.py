#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
轻量级回测引擎
用于策略验证、参数优化和持续迭代
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Callable
import logging
import json


class BacktestEngine:
    """轻量级回测引擎"""
    
    def __init__(self, initial_capital: float = 1000000.0, commission: float = 0.0003,
                 slippage: float = 0.001, stamp_tax: float = 0.001):
        """
        初始化回测引擎
        
        Args:
            initial_capital: 初始资金
            commission: 佣金费率（万分之三）
            slippage: 滑点（千分之一）
            stamp_tax: 印花税（千分之一，仅卖出时收取）
        """
        self.logger = logging.getLogger(__name__)
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.stamp_tax = stamp_tax
        
    def run(self, df: pd.DataFrame, strategy_fn: Callable, params: Dict = None) -> Dict:
        """
        运行回测
        
        Args:
            df: 包含OHLCV和Signal列的DataFrame
            strategy_fn: 策略函数，接收(df, index, position, params)返回信号
            params: 策略参数
        
        Returns:
            回测结果字典
        """
        if params is None:
            params = {}
        
        # 初始化状态
        cash = self.initial_capital
        position = 0  # 持仓数量
        entry_price = 0.0
        entry_date = None
        trades = []
        equity_curve = []
        daily_returns = []
        
        for i in range(len(df)):
            row = df.iloc[i]
            date = df.index[i] if isinstance(df.index[i], str) else str(df.index[i])
            close = row['Close']
            
            # 获取策略信号
            signal = strategy_fn(df, i, position, params)
            
            # 执行交易
            if signal == 1 and position == 0:  # 买入信号且无持仓
                # 计算实际买入价（含滑点）
                buy_price = close * (1 + self.slippage)
                
                # 计算可买数量
                available = cash * 0.95  # 留5%备用金
                shares = int(available / buy_price / 100) * 100
                
                if shares >= 100:
                    # 计算费用
                    cost = shares * buy_price
                    commission_fee = max(cost * self.commission, 5)  # 最低5元
                    
                    cash -= cost + commission_fee
                    position = shares
                    entry_price = buy_price
                    entry_date = date
                    
                    trades.append({
                        'type': 'BUY',
                        'date': date,
                        'price': round(buy_price, 2),
                        'shares': shares,
                        'cost': round(cost + commission_fee, 2),
                        'cash_after': round(cash, 2)
                    })
            
            elif signal == -1 and position > 0:  # 卖出信号且有持仓
                # 计算实际卖出价（含滑点）
                sell_price = close * (1 - self.slippage)
                
                # 计算费用
                revenue = position * sell_price
                commission_fee = max(revenue * self.commission, 5)
                stamp_fee = revenue * self.stamp_tax
                
                cash += revenue - commission_fee - stamp_fee
                
                # 计算盈亏
                profit = sell_price - entry_price
                profit_pct = (profit / entry_price) * 100
                holding_days = i - df.index.get_loc(entry_date) if entry_date in df.index else 0
                
                trades.append({
                    'type': 'SELL',
                    'date': date,
                    'price': round(sell_price, 2),
                    'shares': position,
                    'revenue': round(revenue - commission_fee - stamp_fee, 2),
                    'profit': round(profit * position, 2),
                    'profit_pct': round(profit_pct, 2),
                    'holding_days': holding_days,
                    'cash_after': round(cash, 2)
                })
                
                position = 0
                entry_price = 0.0
                entry_date = None
            
            # 记录权益
            total_value = cash + position * close
            equity_curve.append({
                'date': date,
                'cash': round(cash, 2),
                'position_value': round(position * close, 2),
                'total_value': round(total_value, 2)
            })
            
            # 计算日收益率
            if len(equity_curve) > 1:
                prev_value = equity_curve[-2]['total_value']
                daily_ret = (total_value - prev_value) / prev_value if prev_value > 0 else 0
                daily_returns.append(daily_ret)
        
        # 计算统计指标
        stats = self._calculate_stats(equity_curve, trades, daily_returns)
        
        return {
            'stats': stats,
            'trades': trades,
            'equity_curve': equity_curve,
            'params': params
        }
    
    def _calculate_stats(self, equity_curve: List[Dict], trades: List[Dict],
                         daily_returns: List[float]) -> Dict:
        """计算回测统计指标"""
        if not equity_curve:
            return {}
        
        final_value = equity_curve[-1]['total_value']
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100
        
        # 交易统计
        sell_trades = [t for t in trades if t['type'] == 'SELL']
        total_trades = len(sell_trades)
        win_trades = len([t for t in sell_trades if t['profit'] > 0])
        lose_trades = len([t for t in sell_trades if t['profit'] <= 0])
        
        win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
        
        # 盈亏统计
        profits = [t['profit'] for t in sell_trades if t['profit'] > 0]
        losses = [t['profit'] for t in sell_trades if t['profit'] <= 0]
        
        avg_profit = np.mean(profits) if profits else 0
        avg_loss = np.mean(losses) if losses else 0
        max_profit = max(profits) if profits else 0
        max_loss = min(losses) if losses else 0
        
        # 盈亏比
        profit_loss_ratio = abs(avg_profit / avg_loss) if avg_loss != 0 else float('inf')
        
        # 最大回撤
        values = [e['total_value'] for e in equity_curve]
        max_drawdown = 0
        peak = values[0]
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_drawdown:
                max_drawdown = dd
        
        # 夏普比率（年化）
        if daily_returns:
            daily_returns_arr = np.array(daily_returns)
            avg_daily_return = np.mean(daily_returns_arr)
            std_daily_return = np.std(daily_returns_arr)
            sharpe = (avg_daily_return / std_daily_return * np.sqrt(252)) if std_daily_return > 0 else 0
        else:
            sharpe = 0
        
        # 年化收益率
        days = len(equity_curve)
        years = days / 252  # 交易日
        annualized_return = ((final_value / self.initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0
        
        # Calmar比率
        calmar = annualized_return / max_drawdown if max_drawdown > 0 else 0
        
        # 平均持仓天数
        avg_holding = np.mean([t.get('holding_days', 0) for t in sell_trades]) if sell_trades else 0
        
        # 连续盈亏
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0
        for t in sell_trades:
            if t['profit'] > 0:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)
        
        return {
            'initial_capital': self.initial_capital,
            'final_value': round(final_value, 2),
            'total_return_pct': round(total_return, 2),
            'annualized_return_pct': round(annualized_return, 2),
            'max_drawdown_pct': round(max_drawdown, 2),
            'sharpe_ratio': round(sharpe, 3),
            'calmar_ratio': round(calmar, 3),
            'total_trades': total_trades,
            'win_trades': win_trades,
            'lose_trades': lose_trades,
            'win_rate_pct': round(win_rate, 2),
            'avg_profit': round(avg_profit, 2),
            'avg_loss': round(avg_loss, 2),
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'profit_loss_ratio': round(profit_loss_ratio, 2),
            'avg_holding_days': round(avg_holding, 1),
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses
        }
    
    def optimize(self, df: pd.DataFrame, strategy_fn: Callable,
                 param_grid: Dict, metric: str = 'sharpe_ratio') -> Dict:
        """
        参数优化（网格搜索）
        
        Args:
            df: OHLCV数据
            strategy_fn: 策略函数
            param_grid: 参数网格，如 {'period': [10, 20, 30], 'threshold': [60, 70, 80]}
            metric: 优化目标指标
        
        Returns:
            最优参数和结果
        """
        from itertools import product
        
        # 生成参数组合
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(product(*param_values))
        
        best_score = float('-inf')
        best_params = {}
        best_result = None
        all_results = []
        
        total = len(param_combinations)
        self.logger.info(f"开始参数优化，共 {total} 种组合")
        
        for i, combo in enumerate(param_combinations):
            params = dict(zip(param_names, combo))
            
            try:
                result = self.run(df, strategy_fn, params)
                score = result['stats'].get(metric, float('-inf'))
                
                all_results.append({
                    'params': params,
                    'score': score,
                    'stats': result['stats']
                })
                
                if score > best_score:
                    best_score = score
                    best_params = params
                    best_result = result
                
                if (i + 1) % 10 == 0:
                    self.logger.info(f"进度: {i+1}/{total}, 当前最优 {metric}: {best_score:.3f}")
                    
            except Exception as e:
                self.logger.warning(f"参数组合 {params} 回测失败: {e}")
                continue
        
        self.logger.info(f"优化完成! 最优参数: {best_params}, {metric}: {best_score:.3f}")
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'best_result': best_result,
            'all_results': sorted(all_results, key=lambda x: x['score'], reverse=True),
            'metric': metric
        }
    
    def print_report(self, result: Dict):
        """打印回测报告"""
        stats = result['stats']
        
        print("\n" + "=" * 70)
        print("📊 回测报告")
        print("=" * 70)
        
        print(f"\n💰 资金概况:")
        print(f"  初始资金:     ¥{stats['initial_capital']:>14,.2f}")
        print(f"  最终权益:     ¥{stats['final_value']:>14,.2f}")
        print(f"  总收益率:     {stats['total_return_pct']:>14.2f}%")
        print(f"  年化收益率:   {stats['annualized_return_pct']:>14.2f}%")
        
        print(f"\n📉 风险指标:")
        print(f"  最大回撤:     {stats['max_drawdown_pct']:>14.2f}%")
        print(f"  夏普比率:     {stats['sharpe_ratio']:>14.3f}")
        print(f"  Calmar比率:   {stats['calmar_ratio']:>14.3f}")
        
        print(f"\n🎯 交易统计:")
        print(f"  总交易次数:   {stats['total_trades']:>14d}")
        print(f"  盈利次数:     {stats['win_trades']:>14d}")
        print(f"  亏损次数:     {stats['lose_trades']:>14d}")
        print(f"  胜率:         {stats['win_rate_pct']:>14.2f}%")
        print(f"  盈亏比:       {stats['profit_loss_ratio']:>14.2f}")
        print(f"  平均持仓天数: {stats['avg_holding_days']:>14.1f}")
        
        print(f"\n📈 盈亏详情:")
        print(f"  平均盈利:     ¥{stats['avg_profit']:>14,.2f}")
        print(f"  平均亏损:     ¥{stats['avg_loss']:>14,.2f}")
        print(f"  最大单笔盈利: ¥{stats['max_profit']:>14,.2f}")
        print(f"  最大单笔亏损: ¥{stats['max_loss']:>14,.2f}")
        print(f"  最大连胜:     {stats['max_consecutive_wins']:>14d}")
        print(f"  最大连亏:     {stats['max_consecutive_losses']:>14d}")
        
        # 打印最近5笔交易
        trades = result.get('trades', [])
        sell_trades = [t for t in trades if t['type'] == 'SELL']
        if sell_trades:
            print(f"\n📋 最近交易 (最多5笔):")
            print(f"  {'日期':<12} {'方向':<6} {'价格':>10} {'盈亏':>12} {'盈亏%':>8} {'持仓天数':>8}")
            print(f"  {'-'*60}")
            for t in sell_trades[-5:]:
                emoji = "🟢" if t['profit'] > 0 else "🔴"
                print(f"  {t['date']:<12} {emoji}卖出 {t['price']:>10.2f} {t['profit']:>+12.2f} {t['profit_pct']:>+8.2f}% {t.get('holding_days', 0):>8d}")
        
        if result.get('params'):
            print(f"\n⚙️ 策略参数: {result['params']}")
        
        print("=" * 70)
    
    def compare_results(self, results: List[Dict], names: List[str] = None):
        """
        对比多个回测结果
        
        Args:
            results: 回测结果列表
            names: 策略名称列表
        """
        if names is None:
            names = [f"策略{i+1}" for i in range(len(results))]
        
        print("\n" + "=" * 90)
        print("📊 策略对比报告")
        print("=" * 90)
        
        headers = ['指标'] + names
        rows = []
        
        metrics = [
            ('总收益率%', 'total_return_pct'),
            ('年化收益率%', 'annualized_return_pct'),
            ('最大回撤%', 'max_drawdown_pct'),
            ('夏普比率', 'sharpe_ratio'),
            ('胜率%', 'win_rate_pct'),
            ('盈亏比', 'profit_loss_ratio'),
            ('总交易数', 'total_trades'),
            ('平均持仓天数', 'avg_holding_days')
        ]
        
        for label, key in metrics:
            row = [label]
            for r in results:
                val = r['stats'].get(key, 'N/A')
                if isinstance(val, float):
                    row.append(f"{val:.2f}")
                else:
                    row.append(str(val))
            rows.append(row)
        
        # 打印表格
        col_widths = [max(len(str(row[i])) for row in [headers] + rows) + 2 for i in range(len(headers))]
        
        header_line = "".join(str(h).ljust(w) for h, w in zip(headers, col_widths))
        print(f"\n{header_line}")
        print("-" * sum(col_widths))
        
        for row in rows:
            line = "".join(str(v).ljust(w) for v, w in zip(row, col_widths))
            print(line)
        
        print("=" * 90)


# 全局实例
backtest_engine = BacktestEngine()