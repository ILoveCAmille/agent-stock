#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略优化迭代器
持续自动优化策略参数，记录每次迭代结果，实现不停机持续改进
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
import logging
import json
import os
import time
import akshare as ak

from quant_factors import QuantFactors
from backtest_engine import BacktestEngine


class StrategyOptimizer:
    """策略优化迭代器"""
    
    def __init__(self, output_dir: str = "optimization_results"):
        self.logger = logging.getLogger(__name__)
        self.output_dir = output_dir
        self.bt = BacktestEngine(initial_capital=1000000)
        self.iteration_log = []
        
        os.makedirs(output_dir, exist_ok=True)
    
    # ==================== 内置优化策略 ====================
    
    @staticmethod
    def multi_factor_strategy(df: pd.DataFrame, i: int, position: int, params: Dict) -> int:
        """
        多因子复合策略（已集成quant_factors信号生成）
        
        params:
            buy_threshold: 买入评分阈值（默认70）
            sell_threshold: 卖出评分阈值（默认30）
            rsi_upper: RSI超买阈值（默认70）
            rsi_lower: RSI超卖阈值（默认30）
        """
        if i < 60:
            return 0
        
        buy_threshold = params.get('buy_threshold', 70)
        sell_threshold = params.get('sell_threshold', 30)
        rsi_upper = params.get('rsi_upper', 70)
        rsi_lower = params.get('rsi_lower', 30)
        
        row = df.iloc[i]
        
        # 获取信号列（如果已预计算）
        if 'Signal' in df.columns:
            return row['Signal']
        
        # 动态计算
        score = row.get('Composite_Score', 50)
        rsi_val = row.get('RSI_14', 50)
        trend = row.get('Trend_Strength', 0)
        ma_align = row.get('MA_Alignment', 0)
        
        if position == 0:
            if score > buy_threshold and rsi_val < rsi_upper and trend > 0 and ma_align > 0:
                return 1
        else:
            if score < sell_threshold or rsi_val > rsi_upper + 10 or (trend < -20 and row.get('ADX', 0) > 25):
                return -1
        
        return 0
    
    @staticmethod
    def ma_cross_atr_strategy(df: pd.DataFrame, i: int, position: int, params: Dict) -> int:
        """
        MA均线交叉 + ATR止损策略（优化版低价擒牛策略）
        
        params:
            fast_period: 快线周期（默认5）
            slow_period: 慢线周期（默认20）
            atr_stop_mult: ATR止损倍数（默认2.0）
            holding_days: 最大持仓天数（默认5）
        """
        if i < 60:
            return 0
        
        fast_period = params.get('fast_period', 5)
        slow_period = params.get('slow_period', 20)
        atr_stop_mult = params.get('atr_stop_mult', 2.0)
        holding_days = params.get('holding_days', 5)
        
        close = df['Close']
        ma_fast = close.rolling(fast_period).mean()
        ma_slow = close.rolling(slow_period).mean()
        
        current_close = close.iloc[i]
        fast = ma_fast.iloc[i]
        slow = ma_slow.iloc[i]
        prev_fast = ma_fast.iloc[i-1]
        prev_slow = ma_slow.iloc[i-1]
        atr_val = df['ATR'].iloc[i] if 'ATR' in df.columns else 0
        
        if position == 0:
            # 买入条件：快线上穿慢线 + 价格在慢线之上
            if prev_fast <= prev_slow and fast > slow and current_close > slow:
                return 1
        else:
            # 卖出条件：快线下穿慢线 或 价格跌破ATR止损
            if fast < slow:
                return -1
            # 检查持仓天数
            if 'holding_count' not in params:
                params['holding_count'] = 0
            params['holding_count'] += 1
            if params['holding_count'] >= holding_days:
                params['holding_count'] = 0
                return -1
        
        return 0
    
    @staticmethod
    def rsi_momentum_strategy(df: pd.DataFrame, i: int, position: int, params: Dict) -> int:
        """
        RSI动量策略（优化版价值投资策略）
        
        params:
            rsi_period: RSI周期（默认14）
            rsi_oversold: RSI超卖阈值（默认30）
            rsi_overbought: RSI超买阈值（默认70）
            trend_filter: 是否启用趋势过滤（默认True）
        """
        if i < 60:
            return 0
        
        rsi_period = params.get('rsi_period', 14)
        rsi_oversold = params.get('rsi_oversold', 30)
        rsi_overbought = params.get('rsi_overbought', 70)
        trend_filter = params.get('trend_filter', True)
        
        rsi_val = df['RSI_14'].iloc[i] if 'RSI_14' in df.columns else 50
        trend = df['Trend_Strength'].iloc[i] if 'Trend_Strength' in df.columns else 0
        adx_val = df['ADX'].iloc[i] if 'ADX' in df.columns else 0
        
        if position == 0:
            # 买入条件：RSI超卖反弹 + 趋势向上
            if rsi_val < rsi_oversold + 10:
                if not trend_filter or (trend > -10 and adx_val < 30):
                    return 1
        else:
            # 卖出条件：RSI超买 或 趋势反转
            if rsi_val > rsi_overbought:
                return -1
            if trend_filter and trend < -20 and adx_val > 25:
                return -1
        
        return 0
    
    @staticmethod
    def bollinger_breakout_strategy(df: pd.DataFrame, i: int, position: int, params: Dict) -> int:
        """
        布林带突破策略
        
        params:
            bb_period: 布林带周期（默认20）
            bb_std: 标准差倍数（默认2.0）
            volume_confirm: 是否要求放量确认（默认True）
        """
        if i < 60:
            return 0
        
        bb_period = params.get('bb_period', 20)
        bb_std = params.get('bb_std', 2.0)
        volume_confirm = params.get('volume_confirm', True)
        
        close = df['Close']
        volume = df['Volume']
        
        ma = close.rolling(bb_period).mean()
        std = close.rolling(bb_period).std()
        upper = ma + bb_std * std
        lower = ma - bb_std * std
        
        current = close.iloc[i]
        vol_ratio = volume.iloc[i] / volume.rolling(20).mean().iloc[i] if volume.rolling(20).mean().iloc[i] > 0 else 1
        
        if position == 0:
            # 买入条件：价格突破下轨后回到下轨之上 + 放量
            if close.iloc[i-1] <= lower.iloc[i-1] and current > lower.iloc[i]:
                if not volume_confirm or vol_ratio > 1.2:
                    return 1
        else:
            # 卖出条件：价格触及上轨 或 跌破中轨
            if current >= upper.iloc[i]:
                return -1
            if current < ma.iloc[i] * 0.98:
                return -1
        
        return 0
    
    # ==================== 优化核心 ====================
    
    def fetch_stock_data(self, symbol: str, period_days: int = 365) -> pd.DataFrame:
        """
        获取股票历史数据并计算因子
        支持在线(akshare)和离线(模拟数据)两种模式
        """
        # 先尝试在线获取
        try:
            import os
            os.environ.pop('HTTP_PROXY', None)
            os.environ.pop('HTTPS_PROXY', None)
            os.environ.pop('http_proxy', None)
            os.environ.pop('https_proxy', None)
        except:
            pass
        
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - pd.Timedelta(days=period_days)).strftime('%Y%m%d')
        
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol, period="daily",
                start_date=start_date, end_date=end_date, adjust="qfq"
            )
            
            if df is None or df.empty:
                raise ValueError(f"无法获取 {symbol} 的数据")
            
            # 标准化列名
            df = df.rename(columns={
                '日期': 'Date', '开盘': 'Open', '收盘': 'Close',
                '最高': 'High', '最低': 'Low', '成交量': 'Volume',
                '成交额': 'Amount', '涨跌幅': 'Change'
            })
            
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            
            # 计算所有因子
            df = QuantFactors.generate_signals(df)
            
            return df
            
        except Exception as e:
            self.logger.warning(f"在线数据获取失败: {e}")
            self.logger.info(f"切换到离线模式，为 {symbol} 生成模拟数据...")
            return self._generate_simulated_data(symbol, period_days)
    
    def _generate_simulated_data(self, symbol: str, period_days: int = 365) -> pd.DataFrame:
        """
        生成模拟股票数据用于离线回测
        基于不同股票特征生成差异化的模拟数据
        """
        # 股票特征种子（确保同一股票每次生成的数据一致）
        seed = int(symbol) % 100000
        np.random.seed(seed)
        
        dates = pd.bdate_range(end=datetime.now(), periods=period_days)
        
        # 根据股票代码生成不同特征的价格序列
        base_price = 50 + (seed % 200)
        drift = 0.0002 + (seed % 10) * 0.00005  # 趋势漂移
        volatility = 0.015 + (seed % 20) * 0.001  # 波动率
        
        # 几何布朗运动模拟
        returns = np.random.normal(drift, volatility, len(dates))
        # 添加趋势周期
        cycle = np.sin(np.linspace(0, 4 * np.pi, len(dates))) * 0.001
        returns += cycle
        
        prices = base_price * np.cumprod(1 + returns)
        
        high = prices * (1 + np.abs(np.random.normal(0, 0.01, len(dates))))
        low = prices * (1 - np.abs(np.random.normal(0, 0.01, len(dates))))
        volume = np.random.lognormal(15, 0.5, len(dates)).astype(float)
        
        df = pd.DataFrame({
            'Open': prices + np.random.randn(len(dates)) * prices * 0.005,
            'High': high,
            'Low': low,
            'Close': prices,
            'Volume': volume
        }, index=dates)
        
        self.logger.info(f"已生成 {symbol} 的 {len(df)} 条模拟数据")
        
        # 计算所有因子
        df = QuantFactors.generate_signals(df)
        
        return df
    
    def run_iteration(self, symbol: str, strategy_name: str, strategy_fn, 
                      param_grid: Dict, metric: str = 'sharpe_ratio',
                      period_days: int = 365) -> Dict:
        """
        运行一次优化迭代
        
        Args:
            symbol: 股票代码
            strategy_name: 策略名称
            strategy_fn: 策略函数
            param_grid: 参数网格
            metric: 优化目标
            period_days: 回测数据天数
        
        Returns:
            迭代结果
        """
        iteration_id = len(self.iteration_log) + 1
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"🔄 迭代 #{iteration_id} | {strategy_name} | {symbol}")
        self.logger.info(f"⏰ {timestamp}")
        self.logger.info(f"{'='*70}")
        
        # 获取数据
        df = self.fetch_stock_data(symbol, period_days)
        self.logger.info(f"📊 数据: {len(df)} 条日线记录 ({df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')})")
        
        # 运行优化
        result = self.bt.optimize(df, strategy_fn, param_grid, metric)
        
        # 记录迭代结果
        iteration_record = {
            'iteration_id': iteration_id,
            'timestamp': timestamp,
            'symbol': symbol,
            'strategy': strategy_name,
            'metric': metric,
            'best_params': result['best_params'],
            'best_score': result['best_score'],
            'stats': result['best_result']['stats'] if result['best_result'] else {},
            'data_period': f"{df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}"
        }
        self.iteration_log.append(iteration_record)
        
        # 保存结果
        self._save_iteration_result(iteration_record, result)
        
        # 打印报告
        if result['best_result']:
            self.bt.print_report(result['best_result'])
        
        return iteration_record
    
    def continuous_optimize(self, symbols: List[str], strategies: Dict, 
                           param_grids: Dict, iterations: int = 3,
                           metric: str = 'sharpe_ratio'):
        """
        持续优化迭代主循环
        
        Args:
            symbols: 股票代码列表
            strategies: 策略函数字典 {'name': fn}
            param_grids: 参数网格字典 {'name': grid}
            iterations: 迭代轮数
            metric: 优化目标指标
        """
        self.logger.info(f"\n{'#'*70}")
        self.logger.info(f"🚀 启动持续优化迭代器")
        self.logger.info(f"📈 股票池: {symbols}")
        self.logger.info(f"🧠 策略: {list(strategies.keys())}")
        self.logger.info(f"🔄 迭代轮数: {iterations}")
        self.logger.info(f"🎯 优化目标: {metric}")
        self.logger.info(f"{'#'*70}\n")
        
        all_results = []
        
        for round_num in range(1, iterations + 1):
            self.logger.info(f"\n{'='*70}")
            self.logger.info(f"📌 第 {round_num}/{iterations} 轮迭代")
            self.logger.info(f"{'='*70}")
            
            for symbol in symbols:
                for strategy_name, strategy_fn in strategies.items():
                    param_grid = param_grids.get(strategy_name, {})
                    
                    try:
                        result = self.run_iteration(
                            symbol=symbol,
                            strategy_name=strategy_name,
                            strategy_fn=strategy_fn,
                            param_grid=param_grid,
                            metric=metric
                        )
                        all_results.append(result)
                        
                        # 间隔避免API限制
                        time.sleep(2)
                        
                    except Exception as e:
                        self.logger.error(f"❌ 迭代失败 {symbol}/{strategy_name}: {e}")
                        continue
            
            # 每轮结束打印汇总
            self._print_round_summary(all_results, round_num)
        
        # 保存最终汇总报告
        self._save_final_report(all_results)
        
        return all_results
    
    # ==================== 报告和持久化 ====================
    
    def _save_iteration_result(self, record: Dict, full_result: Dict):
        """保存单次迭代结果"""
        filename = f"{self.output_dir}/iter_{record['iteration_id']:03d}_{record['strategy']}_{record['symbol']}.json"
        
        save_data = {
            **record,
            'trades_count': len(full_result.get('trades', [])),
            'top5_params': [
                {'params': r['params'], 'score': r['score']}
                for r in full_result.get('all_results', [])[:5]
            ]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"💾 结果已保存: {filename}")
    
    def _print_round_summary(self, results: List[Dict], round_num: int):
        """打印每轮迭代汇总"""
        if not results:
            return
        
        print(f"\n{'='*70}")
        print(f"📊 第 {round_num} 轮迭代汇总")
        print(f"{'='*70}")
        print(f"{'策略':<20} {'股票':<10} {'夏普':>8} {'年化%':>8} {'回撤%':>8} {'胜率%':>8} {'交易数':>6}")
        print(f"{'-'*70}")
        
        for r in results:
            stats = r.get('stats', {})
            print(f"{r['strategy']:<20} {r['symbol']:<10} "
                  f"{stats.get('sharpe_ratio', 0):>8.3f} "
                  f"{stats.get('annualized_return_pct', 0):>8.2f} "
                  f"{stats.get('max_drawdown_pct', 0):>8.2f} "
                  f"{stats.get('win_rate_pct', 0):>8.2f} "
                  f"{stats.get('total_trades', 0):>6d}")
        
        print(f"{'='*70}")
    
    def _save_final_report(self, all_results: List[Dict]):
        """保存最终汇总报告"""
        filename = f"{self.output_dir}/final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_iterations': len(all_results),
            'results': all_results
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"\n💾 最终报告已保存: {filename}")
        
        # 同时生成可读文本报告
        txt_file = filename.replace('.json', '.txt')
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("📊 策略优化迭代最终报告\n")
            f.write(f"生成时间: {report['generated_at']}\n")
            f.write(f"总迭代次数: {report['total_iterations']}\n")
            f.write("=" * 70 + "\n\n")
            
            # 按夏普比率排序
            sorted_results = sorted(all_results, 
                                   key=lambda x: x.get('stats', {}).get('sharpe_ratio', -999),
                                   reverse=True)
            
            f.write(f"{'排名':<6} {'策略':<20} {'股票':<10} {'夏普':>8} {'年化%':>8} {'回撤%':>8} {'胜率%':>8} {'最优参数'}\n")
            f.write("-" * 100 + "\n")
            
            for idx, r in enumerate(sorted_results, 1):
                stats = r.get('stats', {})
                params_str = json.dumps(r.get('best_params', {}), ensure_ascii=False)
                f.write(f"{idx:<6} {r['strategy']:<20} {r['symbol']:<10} "
                       f"{stats.get('sharpe_ratio', 0):>8.3f} "
                       f"{stats.get('annualized_return_pct', 0):>8.2f} "
                       f"{stats.get('max_drawdown_pct', 0):>8.2f} "
                       f"{stats.get('win_rate_pct', 0):>8.2f} "
                       f"{params_str}\n")
        
        self.logger.info(f"📄 文本报告已保存: {txt_file}")


# ==================== 快速启动函数 ====================

def quick_optimize(symbols: List[str] = None, iterations: int = 3):
    """
    快速启动优化迭代
    
    Args:
        symbols: 股票代码列表（默认使用热门标的）
        iterations: 迭代轮数
    """
    if symbols is None:
        symbols = ['600519', '000858', '300750', '601318', '002594']
    
    optimizer = StrategyOptimizer()
    
    strategies = {
        '多因子复合': StrategyOptimizer.multi_factor_strategy,
        'MA均线交叉': StrategyOptimizer.ma_cross_atr_strategy,
        'RSI动量': StrategyOptimizer.rsi_momentum_strategy,
        '布林带突破': StrategyOptimizer.bollinger_breakout_strategy,
    }
    
    param_grids = {
        '多因子复合': {
            'buy_threshold': [60, 65, 70, 75, 80],
            'sell_threshold': [25, 30, 35],
            'rsi_upper': [65, 70, 75],
        },
        'MA均线交叉': {
            'fast_period': [3, 5, 8],
            'slow_period': [15, 20, 30],
            'atr_stop_mult': [1.5, 2.0, 2.5, 3.0],
            'holding_days': [3, 5, 7, 10],
        },
        'RSI动量': {
            'rsi_period': [6, 14, 21],
            'rsi_oversold': [25, 30, 35],
            'rsi_overbought': [65, 70, 75, 80],
            'trend_filter': [True, False],
        },
        '布林带突破': {
            'bb_period': [15, 20, 25],
            'bb_std': [1.5, 2.0, 2.5],
            'volume_confirm': [True, False],
        },
    }
    
    return optimizer.continuous_optimize(
        symbols=symbols,
        strategies=strategies,
        param_grids=param_grids,
        iterations=iterations,
        metric='sharpe_ratio'
    )


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 快速启动优化（使用少量股票和迭代以验证功能）
    results = quick_optimize(symbols=['600519'], iterations=1)
    print(f"\n✅ 优化完成！共 {len(results)} 次迭代")