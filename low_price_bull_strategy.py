#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
低价擒牛量化交易策略
实现基于MA均线的买卖择时策略
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from quant_factors import QuantFactors


class LowPriceBullStrategy:
    """低价擒牛量化交易策略"""
    
    def __init__(self, initial_capital: float = 1000000.0):
        """
        初始化策略
        
        Args:
            initial_capital: 初始资金（默认100万）
        """
        self.logger = logging.getLogger(__name__)
        
        # 策略参数
        self.initial_capital = initial_capital
        self.available_cash = initial_capital
        self.max_stocks = 4  # 账户最大持股数
        self.max_position_per_stock = 0.4  # 个股最大持仓比例（4成）
        self.max_daily_buy = 2  # 单日最大买入数
        self.holding_period = 5  # 持股周期（天）
        
        # 持仓信息
        self.positions: Dict[str, Dict] = {}  # {股票代码: {买入价, 数量, 买入日期, 持有天数}}
        self.trade_history: List[Dict] = []  # 交易历史
        
        # 当日交易计数
        self.daily_buy_count = 0
        self.current_date = None
    
    def reset_daily_counter(self, date):
        """重置当日计数器"""
        if self.current_date != date:
            self.current_date = date
            self.daily_buy_count = 0
    
    def can_buy(self, stock_code: str) -> tuple[bool, str]:
        """
        检查是否可以买入
        
        Returns:
            (是否可买, 原因)
        """
        # 检查是否已持有
        if stock_code in self.positions:
            return False, "已持有该股票"
        
        # 检查持股数量
        if len(self.positions) >= self.max_stocks:
            return False, f"已达最大持股数限制({self.max_stocks}只)"
        
        # 检查当日买入数量
        if self.daily_buy_count >= self.max_daily_buy:
            return False, f"今日已达最大买入数限制({self.max_daily_buy}只)"
        
        # 检查资金
        if self.available_cash <= 0:
            return False, "可用资金不足"
        
        return True, "可以买入"
    
    def calculate_buy_amount(self, stock_price: float) -> tuple[int, float]:
        """
        计算买入数量（满仓策略）
        
        Args:
            stock_price: 股票价格
            
        Returns:
            (买入股数, 买入金额)
        """
        # 满仓策略：使用所有可用资金
        max_amount = self.available_cash
        
        # 但不能超过个股最大持仓
        max_per_stock = self.initial_capital * self.max_position_per_stock
        target_amount = min(max_amount, max_per_stock)
        
        # 计算股数（A股100股为1手）
        shares = int(target_amount / stock_price / 100) * 100
        
        if shares < 100:
            return 0, 0
        
        actual_amount = shares * stock_price
        return shares, actual_amount
    
    def buy(self, stock_code: str, stock_name: str, price: float, date: str) -> tuple[bool, str, Optional[Dict]]:
        """
        执行买入操作
        
        Returns:
            (是否成功, 消息, 交易详情)
        """
        # 重置当日计数
        self.reset_daily_counter(date)
        
        # 检查是否可买入
        can_buy, reason = self.can_buy(stock_code)
        if not can_buy:
            return False, reason, None
        
        # 计算买入数量
        shares, amount = self.calculate_buy_amount(price)
        
        if shares == 0:
            return False, "资金不足，无法买入100股", None
        
        # 执行买入
        self.positions[stock_code] = {
            'name': stock_name,
            'shares': shares,
            'buy_price': price,
            'buy_date': date,
            'holding_days': 0
        }
        
        self.available_cash -= amount
        self.daily_buy_count += 1
        
        # 记录交易
        trade = {
            'type': 'BUY',
            'code': stock_code,
            'name': stock_name,
            'price': price,
            'shares': shares,
            'amount': amount,
            'date': date,
            'cash_after': self.available_cash
        }
        self.trade_history.append(trade)
        
        message = f"✅ 买入成功: {stock_code} {stock_name} | 价格:{price:.2f} | 数量:{shares}股 | 金额:{amount:.2f}元"
        self.logger.info(message)
        
        return True, message, trade
    
    def should_sell(self, stock_code: str, ma5: float = None, ma20: float = None,
                    current_date: str = None, current_price: float = None,
                    atr: float = None, rsi: float = None, adx: float = None) -> tuple[bool, str]:
        """
        判断是否应该卖出（优化版：集成ATR止损 + RSI超买 + 趋势强度过滤）
        
        策略：
        1. MA5下穿MA20时卖出
        2. 持股满5天强制卖出
        3. ATR追踪止损（2倍ATR）
        4. RSI超买（>80）卖出
        5. ADX趋势转弱且价格跌破均线卖出
        
        Returns:
            (是否卖出, 原因)
        """
        if stock_code not in self.positions:
            return False, "未持有该股票"
        
        position = self.positions[stock_code]
        
        # 更新持有天数
        position['holding_days'] += 1
        
        # 条件1：检查持股周期
        if position['holding_days'] >= self.holding_period:
            return True, f"持股满{self.holding_period}天，到期卖出"
        
        # 条件2：检查MA5下穿MA20
        if ma5 is not None and ma20 is not None:
            if ma5 < ma20:
                return True, "MA5下穿MA20，技术信号卖出"
        
        # 条件3：ATR追踪止损（新增）
        if current_price is not None and atr is not None and atr > 0:
            stop_loss_price = position['buy_price'] - atr * 2
            if current_price <= stop_loss_price:
                loss_pct = (current_price - position['buy_price']) / position['buy_price'] * 100
                return True, f"ATR止损触发（止损价:{stop_loss_price:.2f}），亏损{loss_pct:.2f}%"
            
            # 更新追踪止损（盈利时提高止损线）
            if current_price > position['buy_price']:
                trailing_stop = current_price - atr * 2
                if 'trailing_stop' not in position or trailing_stop > position.get('trailing_stop', 0):
                    position['trailing_stop'] = trailing_stop
                elif current_price <= position.get('trailing_stop', 0):
                    profit_pct = (current_price - position['buy_price']) / position['buy_price'] * 100
                    return True, f"追踪止盈触发（止盈线:{position['trailing_stop']:.2f}），盈利{profit_pct:.2f}%"
        
        # 条件4：RSI超买（新增）
        if rsi is not None and rsi > 80:
            return True, f"RSI={rsi:.1f}超买，卖出离场"
        
        # 条件5：趋势强度急剧转弱（新增）
        if adx is not None and adx > 30 and ma5 is not None and ma20 is not None:
            if ma5 < ma20 * 0.98:  # 快线跌破慢线2%以上
                return True, f"ADX={adx:.1f}强趋势下跌，快速止损"
        
        return False, "持有"
    
    def sell(self, stock_code: str, price: float, date: str, reason: str = "") -> tuple[bool, str, Optional[Dict]]:
        """
        执行卖出操作
        
        Returns:
            (是否成功, 消息, 交易详情)
        """
        if stock_code not in self.positions:
            return False, "未持有该股票", None
        
        position = self.positions[stock_code]
        shares = position['shares']
        buy_price = position['buy_price']
        
        # 计算盈亏
        amount = shares * price
        cost = shares * buy_price
        profit = amount - cost
        profit_pct = (profit / cost) * 100 if cost > 0 else 0
        
        # 归还资金
        self.available_cash += amount
        
        # 移除持仓
        del self.positions[stock_code]
        
        # 记录交易
        trade = {
            'type': 'SELL',
            'code': stock_code,
            'name': position['name'],
            'price': price,
            'shares': shares,
            'amount': amount,
            'date': date,
            'reason': reason,
            'buy_price': buy_price,
            'profit': profit,
            'profit_pct': profit_pct,
            'cash_after': self.available_cash
        }
        self.trade_history.append(trade)
        
        profit_str = f"+{profit:.2f}" if profit >= 0 else f"{profit:.2f}"
        message = f"✅ 卖出成功: {stock_code} {position['name']} | 价格:{price:.2f} | 数量:{shares}股 | 盈亏:{profit_str}元({profit_pct:+.2f}%) | 原因:{reason}"
        self.logger.info(message)
        
        return True, message, trade
    
    def calculate_position_size(self, stock_price: float, atr: float = None,
                                 win_rate: float = None, avg_win: float = None,
                                 avg_loss: float = None) -> tuple[int, float, str]:
        """
        智能仓位管理（优化版：集成Kelly公式 + 波动率仓位调整）
        
        Args:
            stock_price: 股票价格
            atr: ATR值（可选）
            win_rate: 历史胜率（可选）
            avg_win: 平均盈利幅度（可选）
            avg_loss: 平均亏损幅度（可选）
        
        Returns:
            (买入股数, 买入金额, 仓位策略说明)
        """
        max_amount = self.available_cash
        max_per_stock = self.initial_capital * self.max_position_per_stock
        
        # 策略1：如果有历史胜率数据，使用Kelly公式
        if win_rate and avg_win and avg_loss and avg_loss > 0:
            kelly_pct = QuantFactors.kelly_criterion(win_rate, avg_win, avg_loss)
            kelly_amount = self.initial_capital * kelly_pct
            target_amount = min(max_amount, max_per_stock, kelly_amount)
            method = f"Kelly仓位({kelly_pct*100:.1f}%)"
        
        # 策略2：如果有ATR数据，使用波动率调整仓位
        elif atr is not None and atr > 0:
            atr_pct = (atr / stock_price) * 100
            vol_pct = QuantFactors.volatility_adjusted_position(atr_pct, target_risk=2.0)
            vol_amount = self.initial_capital * vol_pct
            target_amount = min(max_amount, max_per_stock, vol_amount)
            method = f"波动率仓位({vol_pct*100:.1f}%, ATR%={atr_pct:.2f})"
        
        # 策略3：默认固定比例
        else:
            target_amount = min(max_amount, max_per_stock)
            method = f"固定仓位({self.max_position_per_stock*100:.0f}%)"
        
        # 计算股数（A股100股为1手）
        shares = int(target_amount / stock_price / 100) * 100
        
        if shares < 100:
            return 0, 0, "资金不足"
        
        actual_amount = shares * stock_price
        return shares, actual_amount, method
    
    def get_portfolio_summary(self) -> Dict:
        """
        获取投资组合摘要（增强版：新增风险指标）
        
        Returns:
            组合摘要信息
        """
        # 计算持仓市值（需要当前价格，这里用买入价估算）
        position_value = sum(
            pos['shares'] * pos['buy_price'] 
            for pos in self.positions.values()
        )
        
        total_value = self.available_cash + position_value
        
        # 计算收益
        total_profit = total_value - self.initial_capital
        total_profit_pct = (total_profit / self.initial_capital) * 100
        
        # 计算交易统计（新增）
        sell_trades = [t for t in self.trade_history if t.get('type') == 'SELL']
        win_trades = len([t for t in sell_trades if t.get('profit', 0) > 0])
        total_sells = len(sell_trades)
        win_rate = (win_trades / total_sells * 100) if total_sells > 0 else 0
        
        profits = [t['profit'] for t in sell_trades if t.get('profit', 0) > 0]
        losses = [t['profit'] for t in sell_trades if t.get('profit', 0) <= 0]
        avg_profit = np.mean(profits) if profits else 0
        avg_loss = np.mean(losses) if losses else 0
        profit_loss_ratio = abs(avg_profit / avg_loss) if avg_loss != 0 else 0
        
        return {
            'initial_capital': self.initial_capital,
            'available_cash': round(self.available_cash, 2),
            'position_value': round(position_value, 2),
            'total_value': round(total_value, 2),
            'total_profit': round(total_profit, 2),
            'total_profit_pct': round(total_profit_pct, 2),
            'positions_count': len(self.positions),
            'max_stocks': self.max_stocks,
            'trade_count': len(self.trade_history),
            'win_rate': round(win_rate, 2),
            'profit_loss_ratio': round(profit_loss_ratio, 2),
            'avg_profit': round(avg_profit, 2),
            'avg_loss': round(avg_loss, 2)
        }
    
    def get_positions(self) -> List[Dict]:
        """获取当前持仓列表"""
        return [
            {
                'code': code,
                'name': pos['name'],
                'shares': pos['shares'],
                'buy_price': pos['buy_price'],
                'buy_date': pos['buy_date'],
                'holding_days': pos['holding_days']
            }
            for code, pos in self.positions.items()
        ]
    
    def get_trade_history(self) -> List[Dict]:
        """获取交易历史"""
        return self.trade_history.copy()
