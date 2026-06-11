"""
回测引擎
支持多因子策略回测，计算各种绩效指标
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, initial_capital: float = 1000000, commission: float = 0.001,
                 slippage: float = 0.001, stamp_tax: float = 0.001):
        """
        初始化回测引擎
        
        Args:
            initial_capital: 初始资金
            commission: 佣金率
            slippage: 滑点
            stamp_tax: 印花税（卖出时收取）
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.stamp_tax = stamp_tax
        
        # 回测状态
        self.capital = initial_capital
        self.positions = {}  # {stock_code: {'shares': int, 'cost': float, 'entry_date': str}}
        self.trades = []  # 交易记录
        self.portfolio_values = []  # 组合价值序列
        self.daily_returns = []  # 日收益率序列
        
    def run_backtest(self, stock_data: Dict[str, pd.DataFrame], 
                     signal_func: Callable,
                     start_date: str, end_date: str,
                     rebalance_freq: str = 'daily',
                     top_n: int = 10) -> Dict:
        """
        运行回测
        
        Args:
            stock_data: 股票历史数据 {code: DataFrame}
            signal_func: 信号生成函数，返回 {code: signal_dict}
            start_date: 开始日期
            end_date: 结束日期
            rebalance_freq: 调仓频率 (daily/weekly/monthly)
            top_n: 持仓股票数量
            
        Returns:
            回测结果字典
        """
        logger.info(f"Starting backtest from {start_date} to {end_date}")
        
        # 重置状态
        self._reset()
        
        # 获取所有交易日
        all_dates = self._get_trading_dates(stock_data, start_date, end_date)
        
        if not all_dates:
            logger.error("No trading dates found")
            return self._empty_result()
        
        # 确定调仓日
        rebalance_dates = self._get_rebalance_dates(all_dates, rebalance_freq)
        
        # 逐日回测
        current_date_idx = 0
        
        for date in all_dates:
            date_str = date.strftime('%Y-%m-%d') if isinstance(date, datetime) else date
            
            # 获取当日数据
            daily_data = self._get_daily_data(stock_data, date)
            
            if not daily_data:
                continue
            
            # 更新持仓市值
            self._update_portfolio_value(daily_data, date_str)
            
            # 检查是否为调仓日
            if date_str in rebalance_dates or date == all_dates[0]:
                # 生成信号
                signals = signal_func(daily_data, date_str)
                
                # 执行调仓
                self._rebalance(signals, daily_data, date_str, top_n)
            
            current_date_idx += 1
        
        # 计算绩效指标
        results = self._calculate_performance()
        
        logger.info(f"Backtest completed. Total return: {results.get('total_return', 0)*100:.2f}%")
        
        return results
    
    def _reset(self):
        """重置回测状态"""
        self.capital = self.initial_capital
        self.positions = {}
        self.trades = []
        self.portfolio_values = []
        self.daily_returns = []
    
    def _get_trading_dates(self, stock_data: Dict[str, pd.DataFrame], 
                           start_date: str, end_date: str) -> List:
        """获取交易日列表"""
        all_dates = set()
        
        for code, df in stock_data.items():
            if 'date' in df.columns:
                dates = df['date'].tolist()
            elif 'Date' in df.columns:
                dates = df['Date'].tolist()
            elif isinstance(df.index, pd.DatetimeIndex):
                dates = df.index.tolist()
            else:
                continue
            
            for d in dates:
                d_str = d.strftime('%Y-%m-%d') if isinstance(d, datetime) else str(d)
                if start_date <= d_str <= end_date:
                    all_dates.add(d_str)
        
        return sorted(list(all_dates))
    
    def _get_rebalance_dates(self, all_dates: List, freq: str) -> List:
        """获取调仓日"""
        if freq == 'daily':
            return all_dates
        
        rebalance_dates = []
        
        if freq == 'weekly':
            # 每周一调仓
            for date_str in all_dates:
                date = datetime.strptime(date_str, '%Y-%m-%d')
                if date.weekday() == 0:  # 周一
                    rebalance_dates.append(date_str)
        
        elif freq == 'monthly':
            # 每月第一个交易日调仓
            current_month = None
            for date_str in all_dates:
                month = date_str[:7]  # YYYY-MM
                if month != current_month:
                    rebalance_dates.append(date_str)
                    current_month = month
        
        return rebalance_dates
    
    def _get_daily_data(self, stock_data: Dict[str, pd.DataFrame], date: str) -> Dict:
        """获取当日数据"""
        daily_data = {}
        
        for code, df in stock_data.items():
            if 'date' in df.columns:
                row = df[df['date'] == date]
            elif 'Date' in df.columns:
                row = df[df['Date'] == date]
            elif isinstance(df.index, pd.DatetimeIndex):
                if date in df.index:
                    row = df.loc[date]
                else:
                    continue
            else:
                continue
            
            if not row.empty:
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]
                
                daily_data[code] = {
                    'close': row.get('close', row.get('Close', 0)),
                    'open': row.get('open', row.get('Open', 0)),
                    'high': row.get('high', row.get('High', 0)),
                    'low': row.get('low', row.get('Low', 0)),
                    'volume': row.get('volume', row.get('Volume', 0)),
                }
        
        return daily_data
    
    def _update_portfolio_value(self, daily_data: Dict, date: str):
        """更新组合市值"""
        total_value = self.capital
        
        for code, position in self.positions.items():
            if code in daily_data:
                current_price = daily_data[code]['close']
                position_value = position['shares'] * current_price
                total_value += position_value
        
        self.portfolio_values.append({
            'date': date,
            'value': total_value,
            'capital': self.capital,
            'positions_value': total_value - self.capital,
        })
        
        # 计算日收益率
        if len(self.portfolio_values) > 1:
            prev_value = self.portfolio_values[-2]['value']
            daily_return = (total_value - prev_value) / prev_value
            self.daily_returns.append({
                'date': date,
                'return': daily_return,
            })
    
    def _rebalance(self, signals: Dict, daily_data: Dict, date: str, top_n: int):
        """执行调仓"""
        if not signals:
            return
        
        # 按信号得分排序
        sorted_signals = sorted(signals.items(), 
                               key=lambda x: x[1].get('score', 0), 
                               reverse=True)
        
        # 选出TOP N
        target_stocks = [code for code, _ in sorted_signals[:top_n]]
        
        # 卖出不在目标列表的股票
        stocks_to_sell = [code for code in self.positions if code not in target_stocks]
        
        for code in stocks_to_sell:
            if code in daily_data:
                self._sell_stock(code, daily_data[code]['close'], date)
        
        # 买入新目标股票（等权重配置）
        stocks_to_buy = [code for code in target_stocks if code not in self.positions]
        
        if stocks_to_buy:
            # 计算每只股票的目标金额
            total_value = self._get_total_value(daily_data)
            target_per_stock = total_value / top_n
            
            for code in stocks_to_buy:
                if code in daily_data:
                    current_price = daily_data[code]['close']
                    if current_price > 0:
                        # 计算可买股数（100股整数倍）
                        shares = int(target_per_stock / current_price / 100) * 100
                        if shares >= 100:
                            self._buy_stock(code, shares, current_price, date)
    
    def _buy_stock(self, code: str, shares: int, price: float, date: str):
        """买入股票"""
        # 计算成本（含佣金和滑点）
        actual_price = price * (1 + self.slippage)
        cost = shares * actual_price
        commission = cost * self.commission
        total_cost = cost + commission
        
        if total_cost > self.capital:
            # 资金不足，减少股数
            shares = int(self.capital / actual_price / 100) * 100
            if shares < 100:
                return
            cost = shares * actual_price
            commission = cost * self.commission
            total_cost = cost + commission
        
        # 扣除资金
        self.capital -= total_cost
        
        # 记录持仓
        self.positions[code] = {
            'shares': shares,
            'cost': actual_price,
            'entry_date': date,
            'entry_price': actual_price,
        }
        
        # 记录交易
        self.trades.append({
            'date': date,
            'code': code,
            'action': 'buy',
            'shares': shares,
            'price': actual_price,
            'cost': total_cost,
            'commission': commission,
        })
    
    def _sell_stock(self, code: str, price: float, date: str):
        """卖出股票"""
        if code not in self.positions:
            return
        
        position = self.positions[code]
        shares = position['shares']
        
        # 计算收入（扣除佣金、滑点和印花税）
        actual_price = price * (1 - self.slippage)
        revenue = shares * actual_price
        commission = revenue * self.commission
        stamp_tax = revenue * self.stamp_tax
        net_revenue = revenue - commission - stamp_tax
        
        # 增加资金
        self.capital += net_revenue
        
        # 计算盈亏
        pnl = net_revenue - (shares * position['cost'])
        pnl_pct = pnl / (shares * position['cost'])
        
        # 记录交易
        self.trades.append({
            'date': date,
            'code': code,
            'action': 'sell',
            'shares': shares,
            'price': actual_price,
            'revenue': net_revenue,
            'commission': commission,
            'stamp_tax': stamp_tax,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'holding_days': (datetime.strptime(date, '%Y-%m-%d') - 
                           datetime.strptime(position['entry_date'], '%Y-%m-%d')).days,
        })
        
        # 删除持仓
        del self.positions[code]
    
    def _get_total_value(self, daily_data: Dict) -> float:
        """获取总市值"""
        total = self.capital
        for code, position in self.positions.items():
            if code in daily_data:
                total += position['shares'] * daily_data[code]['close']
        return total
    
    def _calculate_performance(self) -> Dict:
        """计算绩效指标"""
        if not self.portfolio_values:
            return self._empty_result()
        
        # 转换为DataFrame
        pv_df = pd.DataFrame(self.portfolio_values)
        pv_df['date'] = pd.to_datetime(pv_df['date'])
        pv_df = pv_df.set_index('date')
        
        returns_df = pd.DataFrame(self.daily_returns)
        if not returns_df.empty:
            returns_df['date'] = pd.to_datetime(returns_df['date'])
            returns_df = returns_df.set_index('date')
        
        # 基本指标
        initial_value = self.portfolio_values[0]['value']
        final_value = self.portfolio_values[-1]['value']
        total_return = (final_value - initial_value) / initial_value
        
        # 年化收益
        n_days = (pv_df.index[-1] - pv_df.index[0]).days
        n_years = n_days / 365
        annual_return = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0
        
        # 波动率
        if not returns_df.empty:
            daily_vol = returns_df['return'].std()
            annual_vol = daily_vol * np.sqrt(252)
        else:
            daily_vol = 0
            annual_vol = 0
        
        # 夏普比率
        risk_free_rate = 0.03
        sharpe_ratio = (annual_return - risk_free_rate) / annual_vol if annual_vol > 0 else 0
        
        # 最大回撤
        cumulative = pv_df['value'] / pv_df['value'].iloc[0]
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdown.min())
        
        # 卡尔玛比率
        calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0
        
        # 胜率
        if not returns_df.empty:
            win_rate = (returns_df['return'] > 0).mean()
        else:
            win_rate = 0
        
        # 交易统计
        buy_trades = [t for t in self.trades if t['action'] == 'buy']
        sell_trades = [t for t in self.trades if t['action'] == 'sell']
        
        profitable_trades = [t for t in sell_trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in sell_trades if t.get('pnl', 0) < 0]
        
        win_rate_trades = len(profitable_trades) / len(sell_trades) if sell_trades else 0
        
        avg_profit = np.mean([t['pnl'] for t in profitable_trades]) if profitable_trades else 0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0
        
        profit_loss_ratio = abs(avg_profit / avg_loss) if avg_loss != 0 else 0
        
        # 月度收益
        monthly_returns = self._calculate_monthly_returns(pv_df)
        monthly_win_rate = (monthly_returns > 0).mean() if not monthly_returns.empty else 0
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': final_value,
            'total_return': total_return,
            'annual_return': annual_return,
            'annual_volatility': annual_vol,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'calmar_ratio': calmar_ratio,
            'win_rate': win_rate,
            'monthly_win_rate': monthly_win_rate,
            'total_trades': len(self.trades),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'profitable_trades': len(profitable_trades),
            'losing_trades': len(losing_trades),
            'win_rate_trades': win_rate_trades,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'profit_loss_ratio': profit_loss_ratio,
            'avg_holding_days': self._calculate_avg_holding_days(),
            'portfolio_values': self.portfolio_values,
            'daily_returns': self.daily_returns,
            'trades': self.trades,
            'monthly_returns': monthly_returns.to_dict() if not monthly_returns.empty else {},
        }
    
    def _calculate_monthly_returns(self, pv_df: pd.DataFrame) -> pd.Series:
        """计算月度收益"""
        monthly = pv_df['value'].resample('ME').last()
        monthly_returns = monthly.pct_change().dropna()
        return monthly_returns
    
    def _calculate_avg_holding_days(self) -> float:
        """计算平均持仓天数"""
        holding_days = [t.get('holding_days', 0) for t in self.trades if t['action'] == 'sell']
        return np.mean(holding_days) if holding_days else 0
    
    def _empty_result(self) -> Dict:
        """空结果"""
        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.initial_capital,
            'total_return': 0,
            'annual_return': 0,
            'annual_volatility': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'calmar_ratio': 0,
            'win_rate': 0,
            'monthly_win_rate': 0,
            'total_trades': 0,
            'buy_trades': 0,
            'sell_trades': 0,
            'profitable_trades': 0,
            'losing_trades': 0,
            'win_rate_trades': 0,
            'avg_profit': 0,
            'avg_loss': 0,
            'profit_loss_ratio': 0,
            'avg_holding_days': 0,
            'portfolio_values': [],
            'daily_returns': [],
            'trades': [],
            'monthly_returns': {},
        }


class FactorBacktester:
    """因子回测器"""
    
    def __init__(self, backtest_engine: BacktestEngine = None):
        self.engine = backtest_engine or BacktestEngine()
    
    def backtest_factor(self, factor_values: Dict[str, pd.Series], 
                        stock_data: Dict[str, pd.DataFrame],
                        start_date: str, end_date: str,
                        top_n: int = 10, rebalance_freq: str = 'monthly') -> Dict:
        """
        回测单个因子
        
        Args:
            factor_values: 因子值 {code: Series}
            stock_data: 股票历史数据 {code: DataFrame}
            start_date: 开始日期
            end_date: 结束日期
            top_n: 持仓数量
            rebalance_freq: 调仓频率
            
        Returns:
            回测结果
        """
        # 构建信号函数
        def signal_func(daily_data, date):
            signals = {}
            for code in daily_data:
                if code in factor_values:
                    fv = factor_values[code]
                    if date in fv.index:
                        signals[code] = {
                            'score': fv[date],
                            'signal': 'buy',
                        }
            return signals
        
        # 运行回测
        results = self.engine.run_backtest(
            stock_data=stock_data,
            signal_func=signal_func,
            start_date=start_date,
            end_date=end_date,
            rebalance_freq=rebalance_freq,
            top_n=top_n,
        )
        
        return results
    
    def compare_factors(self, factor_results: Dict[str, Dict]) -> pd.DataFrame:
        """比较多个因子的回测结果"""
        comparison = []
        
        for factor_name, result in factor_results.items():
            comparison.append({
                'factor': factor_name,
                'total_return': result.get('total_return', 0),
                'annual_return': result.get('annual_return', 0),
                'sharpe_ratio': result.get('sharpe_ratio', 0),
                'max_drawdown': result.get('max_drawdown', 0),
                'calmar_ratio': result.get('calmar_ratio', 0),
                'win_rate': result.get('win_rate', 0),
                'monthly_win_rate': result.get('monthly_win_rate', 0),
                'total_trades': result.get('total_trades', 0),
            })
        
        df = pd.DataFrame(comparison)
        
        # 计算综合得分
        if not df.empty:
            df['composite_score'] = (
                df['sharpe_ratio'].clip(-3, 3) / 3 * 0.3 +
                df['calmar_ratio'].clip(0, 5) / 5 * 0.2 +
                df['win_rate'] * 0.2 +
                df['monthly_win_rate'] * 0.15 +
                (1 - df['max_drawdown'].clip(0, 1)) * 0.15
            )
            df = df.sort_values('composite_score', ascending=False)
        
        return df
    
    def generate_report(self, results: Dict) -> str:
        """生成回测报告"""
        report = []
        report.append("=" * 60)
        report.append("回测报告")
        report.append("=" * 60)
        report.append(f"回测时间: {results.get('start_date', 'N/A')} ~ {results.get('end_date', 'N/A')}")
        report.append(f"初始资金: {results.get('initial_capital', 0):,.0f}")
        report.append(f"最终资金: {results.get('final_capital', 0):,.0f}")
        report.append("")
        
        report.append("-" * 60)
        report.append("收益指标:")
        report.append("-" * 60)
        report.append(f"总收益率: {results.get('total_return', 0)*100:.2f}%")
        report.append(f"年化收益率: {results.get('annual_return', 0)*100:.2f}%")
        report.append(f"年化波动率: {results.get('annual_volatility', 0)*100:.2f}%")
        report.append("")
        
        report.append("-" * 60)
        report.append("风险指标:")
        report.append("-" * 60)
        report.append(f"夏普比率: {results.get('sharpe_ratio', 0):.2f}")
        report.append(f"最大回撤: {results.get('max_drawdown', 0)*100:.2f}%")
        report.append(f"卡尔玛比率: {results.get('calmar_ratio', 0):.2f}")
        report.append("")
        
        report.append("-" * 60)
        report.append("交易统计:")
        report.append("-" * 60)
        report.append(f"总交易次数: {results.get('total_trades', 0)}")
        report.append(f"买入次数: {results.get('buy_trades', 0)}")
        report.append(f"卖出次数: {results.get('sell_trades', 0)}")
        report.append(f"盈利交易: {results.get('profitable_trades', 0)}")
        report.append(f"亏损交易: {results.get('losing_trades', 0)}")
        report.append(f"交易胜率: {results.get('win_rate_trades', 0)*100:.2f}%")
        report.append(f"平均盈利: {results.get('avg_profit', 0):,.0f}")
        report.append(f"平均亏损: {results.get('avg_loss', 0):,.0f}")
        report.append(f"盈亏比: {results.get('profit_loss_ratio', 0):.2f}")
        report.append(f"平均持仓天数: {results.get('avg_holding_days', 0):.0f}")
        report.append("")
        
        report.append("-" * 60)
        report.append("月度统计:")
        report.append("-" * 60)
        report.append(f"月度胜率: {results.get('monthly_win_rate', 0)*100:.2f}%")
        report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)


# 创建全局实例
backtest_engine = BacktestEngine()
factor_backtester = FactorBacktester(backtest_engine)
