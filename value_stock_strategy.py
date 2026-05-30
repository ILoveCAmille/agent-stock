#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
低估值量化交易策略
实现基于持股周期和RSI超买的买卖择时策略
"""

import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from quant_factors import QuantFactors


class ValueStockStrategy:
    """低估值量化交易策略"""

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
        self.max_stocks = 4              # 账户最大持股数
        self.max_position_per_stock = 0.3  # 个股最大仓位30%
        self.max_daily_buy = 2           # 单日最大买入数
        self.holding_period = 30         # 持股周期（天）
        self.rsi_period = 14             # RSI计算周期
        self.rsi_overbought = 70         # RSI超买阈值

        # 持仓信息
        self.positions: Dict[str, Dict] = {}  # {股票代码: {买入价, 数量, 买入日期, 持有天数}}
        self.trade_history: List[Dict] = []

        # 当日交易计数
        self.daily_buy_count = 0
        self.current_date = None

    def reset_daily_counter(self, date):
        """重置当日计数器"""
        if self.current_date != date:
            self.current_date = date
            self.daily_buy_count = 0

    def can_buy(self, stock_code: str) -> tuple:
        """
        检查是否可以买入

        Returns:
            (是否可买, 原因)
        """
        if stock_code in self.positions:
            return False, "已持有该股票"

        if len(self.positions) >= self.max_stocks:
            return False, f"已达最大持股数限制({self.max_stocks}只)"

        if self.daily_buy_count >= self.max_daily_buy:
            return False, f"今日已达最大买入数限制({self.max_daily_buy}只)"

        if self.available_cash <= 0:
            return False, "可用资金不足"

        return True, "可以买入"

    def calculate_buy_amount(self, stock_price: float) -> tuple:
        """
        计算买入数量

        Args:
            stock_price: 股票价格

        Returns:
            (买入股数, 买入金额)
        """
        max_amount = self.available_cash
        max_per_stock = self.initial_capital * self.max_position_per_stock
        target_amount = min(max_amount, max_per_stock)

        # A股100股为1手
        shares = int(target_amount / stock_price / 100) * 100

        if shares < 100:
            return 0, 0

        actual_amount = shares * stock_price
        return shares, actual_amount

    def buy(self, stock_code: str, stock_name: str, price: float, date: str) -> tuple:
        """
        执行买入操作

        Returns:
            (是否成功, 消息, 交易详情)
        """
        can, reason = self.can_buy(stock_code)
        if not can:
            return False, reason, None

        shares, amount = self.calculate_buy_amount(price)
        if shares == 0:
            return False, "资金不足以买入1手", None

        # 更新持仓
        self.positions[stock_code] = {
            'name': stock_name,
            'buy_price': price,
            'shares': shares,
            'amount': amount,
            'buy_date': date,
            'holding_days': 0
        }

        self.available_cash -= amount
        self.daily_buy_count += 1

        trade = {
            'action': '买入',
            'code': stock_code,
            'name': stock_name,
            'price': price,
            'shares': shares,
            'amount': amount,
            'date': date,
            'reason': '开盘买入信号'
        }
        self.trade_history.append(trade)

        msg = f"买入 {stock_code} {stock_name} {shares}股 @ {price}元, 金额: {amount:.2f}元"
        return True, msg, trade

    def calculate_rsi(self, stock_code: str) -> Optional[float]:
        """
        计算股票的RSI指标

        Args:
            stock_code: 股票代码

        Returns:
            RSI值 或 None
        """
        try:
            # 获取近60天日线数据
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=(datetime.now() - timedelta(days=90)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="qfq"
            )

            if df is None or len(df) < self.rsi_period + 1:
                return None

            # 计算RSI
            close = df['收盘'].astype(float)
            delta = close.diff()
            gain = delta.where(delta > 0, 0)
            loss = (-delta).where(delta < 0, 0)

            avg_gain = gain.rolling(window=self.rsi_period).mean()
            avg_loss = loss.rolling(window=self.rsi_period).mean()

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            latest_rsi = rsi.iloc[-1]
            return round(float(latest_rsi), 2) if pd.notna(latest_rsi) else None

        except Exception as e:
            self.logger.warning(f"RSI计算失败 {stock_code}: {e}")
            return None

    def calculate_enhanced_rsi(self, stock_code: str) -> dict:
        """
        使用QuantFactors计算增强版RSI和相关指标（优化版）
        
        Returns:
            dict包含RSI_14, RSI_6, ADX, ATR_pct, Trend_Strength等
        """
        try:
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=(datetime.now() - timedelta(days=120)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="qfq"
            )
            
            if df is None or len(df) < 30:
                return {}
            
            close = df['收盘'].astype(float)
            high = df['最高'].astype(float)
            low = df['最低'].astype(float)
            volume = df['成交量'].astype(float)
            
            result = {
                'RSI_14': round(float(QuantFactors.rsi(close, 14).iloc[-1]), 2),
                'RSI_6': round(float(QuantFactors.rsi(close, 6).iloc[-1]), 2),
                'ADX': round(float(QuantFactors.adx(high, low, close).iloc[-1]), 2),
                'ATR': round(float(QuantFactors.atr(high, low, close).iloc[-1]), 4),
                'ATR_pct': round(float(QuantFactors.atr_percent(high, low, close).iloc[-1]), 2),
                'Trend_Strength': round(float(QuantFactors.trend_strength(close).iloc[-1]), 2),
                'Williams_R': round(float(QuantFactors.williams_r(high, low, close).iloc[-1]), 2),
                'VPD': round(float(QuantFactors.volume_price_divergence(close, volume).iloc[-1]), 2),
            }
            
            # Stochastic RSI
            stoch_k, stoch_d = QuantFactors.stoch_rsi(close)
            result['Stoch_K'] = round(float(stoch_k.iloc[-1]), 2) if pd.notna(stoch_k.iloc[-1]) else 50
            result['Stoch_D'] = round(float(stoch_d.iloc[-1]), 2) if pd.notna(stoch_d.iloc[-1]) else 50
            
            return result
            
        except Exception as e:
            self.logger.warning(f"增强RSI计算失败 {stock_code}: {e}")
            return {}
    
    def should_sell(self, stock_code: str, current_date: str = None,
                    current_price: float = None, atr: float = None,
                    adx: float = None, trend_strength: float = None) -> tuple:
        """
        判断是否应该卖出（优化版：集成ATR追踪止损 + 多因子判断）
        
        策略：
        1. 持股满30天强制卖出
        2. RSI超买（>75）卖出
        3. ATR追踪止损保护利润
        4. ADX+趋势强度组合判断趋势反转
        5. 量价背离预警
        
        Returns:
            (是否卖出, 原因, 指标详情)
        """
        if stock_code not in self.positions:
            return False, "未持有该股票", None
        
        position = self.positions[stock_code]
        position['holding_days'] += 1
        
        # 获取增强指标
        indicators = self.calculate_enhanced_rsi(stock_code)
        rsi = indicators.get('RSI_14')
        
        # 条件1：持股满30天
        if position['holding_days'] >= self.holding_period:
            return True, f"持股满{self.holding_period}天，到期卖出", indicators
        
        # 条件2：RSI超买（使用增强RSI）
        if rsi is not None and rsi > self.rsi_overbought:
            return True, f"RSI={rsi} 超买（>{self.rsi_overbought}），卖出离场", indicators
        
        # 条件3：ATR追踪止损（新增）
        if current_price is not None:
            atr_val = atr or indicators.get('ATR', 0)
            if atr_val > 0:
                # 盈利时启用追踪止损
                if current_price > position['buy_price']:
                    trailing_stop = current_price - atr_val * 2.5
                    if 'trailing_stop' not in position or trailing_stop > position.get('trailing_stop', 0):
                        position['trailing_stop'] = trailing_stop
                    elif current_price <= position.get('trailing_stop', 0):
                        profit_pct = (current_price - position['buy_price']) / position['buy_price'] * 100
                        return True, f"ATR追踪止盈（{profit_pct:+.2f}%）", indicators
                
                # 亏损时ATR止损
                stop_loss = position['buy_price'] - atr_val * 2
                if current_price <= stop_loss:
                    loss_pct = (current_price - position['buy_price']) / position['buy_price'] * 100
                    return True, f"ATR止损（{loss_pct:+.2f}%）", indicators
        
        # 条件4：ADX趋势反转 + 趋势强度组合判断（新增）
        adx_val = adx or indicators.get('ADX', 0)
        trend_val = trend_strength or indicators.get('Trend_Strength', 0)
        if adx_val > 25 and trend_val < -15:
            return True, f"趋势反转（ADX={adx_val:.1f}, 趋势={trend_val:.1f}）", indicators
        
        # 条件5：量价背离预警（新增）
        vpd = indicators.get('VPD', 0)
        if vpd < -30 and rsi is not None and rsi > 60:
            return True, f"量价顶背离（VPD={vpd:.1f}, RSI={rsi:.1f}）", indicators
        
        return False, f"继续持有 (已持{position['holding_days']}天, RSI={rsi})", indicators

    def sell(self, stock_code: str, price: float, date: str, reason: str = "") -> tuple:
        """
        执行卖出操作

        Returns:
            (是否成功, 消息, 交易详情)
        """
        if stock_code not in self.positions:
            return False, "未持有该股票", None

        position = self.positions[stock_code]
        amount = position['shares'] * price
        profit = amount - position['amount']
        profit_pct = (price - position['buy_price']) / position['buy_price'] * 100

        trade = {
            'action': '卖出',
            'code': stock_code,
            'name': position['name'],
            'price': price,
            'shares': position['shares'],
            'amount': amount,
            'date': date,
            'buy_price': position['buy_price'],
            'profit': profit,
            'profit_pct': round(profit_pct, 2),
            'holding_days': position['holding_days'],
            'reason': reason
        }
        self.trade_history.append(trade)

        self.available_cash += amount
        del self.positions[stock_code]

        emoji = "🟢" if profit >= 0 else "🔴"
        msg = f"{emoji} 卖出 {stock_code} {position['name']} {position['shares']}股 @ {price}元, 盈亏: {profit:.2f}元 ({profit_pct:+.2f}%), 原因: {reason}"
        return True, msg, trade

    def calculate_position_size_v2(self, stock_price: float, atr: float = None,
                                     indicators: dict = None) -> tuple[int, float, str]:
        """
        智能仓位管理（优化版：基于波动率和趋势强度）
        
        Args:
            stock_price: 股票价格
            atr: ATR值
            indicators: 技术指标字典
        
        Returns:
            (买入股数, 买入金额, 仓位策略说明)
        """
        max_amount = self.available_cash
        max_per_stock = self.initial_capital * self.max_position_per_stock
        
        if atr is not None and atr > 0:
            atr_pct = (atr / stock_price) * 100
            
            # 根据趋势强度调整仓位
            trend = indicators.get('Trend_Strength', 0) if indicators else 0
            adx_val = indicators.get('ADX', 0) if indicators else 0
            
            base_pct = QuantFactors.volatility_adjusted_position(atr_pct, target_risk=2.0)
            
            # 趋势向上且ADX强，增加仓位
            if trend > 10 and adx_val > 25:
                adjusted_pct = min(base_pct * 1.2, self.max_position_per_stock)
                method = f"波动率+强趋势仓位({adjusted_pct*100:.1f}%)"
            # 趋势向下，减少仓位
            elif trend < -10:
                adjusted_pct = base_pct * 0.7
                method = f"波动率+弱趋势仓位({adjusted_pct*100:.1f}%)"
            else:
                adjusted_pct = base_pct
                method = f"波动率仓位({adjusted_pct*100:.1f}%)"
            
            target_amount = min(max_amount, max_per_stock, self.initial_capital * adjusted_pct)
        else:
            target_amount = min(max_amount, max_per_stock)
            method = f"固定仓位({self.max_position_per_stock*100:.0f}%)"
        
        shares = int(target_amount / stock_price / 100) * 100
        
        if shares < 100:
            return 0, 0, "资金不足"
        
        actual_amount = shares * stock_price
        return shares, actual_amount, method
    
    def get_portfolio_summary(self) -> Dict:
        """获取投资组合摘要（增强版）"""
        total_position_value = sum(
            pos['shares'] * pos['buy_price'] for pos in self.positions.values()
        )
        total_assets = self.available_cash + total_position_value

        # 统计交易
        sells = [t for t in self.trade_history if t['action'] == '卖出']
        total_profit = sum(t.get('profit', 0) for t in sells)
        win_trades = sum(1 for t in sells if t.get('profit', 0) > 0)
        total_trades = len(sells)
        win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
        
        # 盈亏比（新增）
        profits = [t['profit'] for t in sells if t.get('profit', 0) > 0]
        losses = [t['profit'] for t in sells if t.get('profit', 0) <= 0]
        avg_profit = np.mean(profits) if profits else 0
        avg_loss = np.mean(losses) if losses else 0
        profit_loss_ratio = abs(avg_profit / avg_loss) if avg_loss != 0 else 0
        
        # 最大持仓天数
        avg_holding = np.mean([t.get('holding_days', 0) for t in sells]) if sells else 0

        return {
            'initial_capital': self.initial_capital,
            'available_cash': round(self.available_cash, 2),
            'position_value': round(total_position_value, 2),
            'total_assets': round(total_assets, 2),
            'total_return': round((total_assets - self.initial_capital) / self.initial_capital * 100, 2),
            'total_profit': round(total_profit, 2),
            'holding_count': len(self.positions),
            'max_stocks': self.max_stocks,
            'total_trades': total_trades,
            'win_trades': win_trades,
            'win_rate': round(win_rate, 2),
            'profit_loss_ratio': round(profit_loss_ratio, 2),
            'avg_holding_days': round(avg_holding, 1),
            'avg_profit': round(avg_profit, 2),
            'avg_loss': round(avg_loss, 2)
        }

    def get_positions(self) -> List[Dict]:
        """获取当前持仓列表"""
        positions = []
        for code, pos in self.positions.items():
            positions.append({
                'code': code,
                'name': pos['name'],
                'buy_price': pos['buy_price'],
                'shares': pos['shares'],
                'amount': pos['amount'],
                'buy_date': pos['buy_date'],
                'holding_days': pos['holding_days']
            })
        return positions

    def get_trade_history(self) -> List[Dict]:
        """获取交易历史"""
        return self.trade_history
