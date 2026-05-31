#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟盘交易系统
使用真实行情数据驱动，无需外部券商账户
支持：买入/卖出/持仓管理/盈亏追踪/交易记录/策略自动执行

使用方法:
    python paper_trading.py                           # 交互模式
    python paper_trading.py --auto --stock 600519     # 自动策略模式
    python paper_trading.py --status                  # 查看持仓状态
"""

import os
import json
import time
import logging
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "买入"
    SELL = "卖出"


class OrderStatus(Enum):
    PENDING = "待执行"
    FILLED = "已成交"
    CANCELLED = "已取消"
    REJECTED = "已拒绝"


@dataclass
class Order:
    """订单"""
    order_id: str
    symbol: str
    side: str
    price: float
    shares: int
    status: str = "待执行"
    created_at: str = ""
    filled_at: str = ""
    filled_price: float = 0.0
    filled_shares: int = 0
    commission: float = 0.0
    reason: str = ""


@dataclass
class Position:
    """持仓"""
    symbol: str
    shares: int
    avg_cost: float
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    entry_date: str = ""
    max_price: float = 0.0
    holding_days: int = 0


class PaperTradingEngine:
    """模拟盘交易引擎"""
    
    def __init__(self, initial_capital: float = 1000000.0,
                 commission_rate: float = 0.0003,
                 stamp_tax_rate: float = 0.001,
                 min_commission: float = 5.0,
                 data_dir: str = ".paper_trading"):
        """
        初始化模拟盘引擎
        
        Args:
            initial_capital: 初始资金（默认100万）
            commission_rate: 佣金费率（万三）
            stamp_tax_rate: 印花税（千一，仅卖出）
            min_commission: 最低佣金
            data_dir: 数据存储目录
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.min_commission = min_commission
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        # 账户状态
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.orders: List[Order] = []
        self.trade_history: List[Dict] = []
        self.order_counter = 0
        
        # 加载历史状态
        self._load_state()
    
    # ==================== 核心交易功能 ====================
    
    def buy(self, symbol: str, price: float, shares: int = 0,
            amount: float = 0, reason: str = "") -> Dict:
        """
        买入股票
        
        Args:
            symbol: 股票代码
            price: 买入价格
            shares: 买入股数（与amount二选一）
            amount: 买入金额（自动计算股数，向下取整到100股）
            reason: 买入原因
        
        Returns:
            交易结果字典
        """
        # 计算股数
        if shares <= 0 and amount > 0:
            shares = int(amount / price / 100) * 100
        elif shares <= 0:
            return {"success": False, "error": "无效的股数或金额"}
        
        # 确保是100的倍数（A股规则）
        shares = int(shares / 100) * 100
        if shares < 100:
            return {"success": False, "error": "股数不足100股"}
        
        # 计算费用
        cost = shares * price
        commission = max(cost * self.commission_rate, self.min_commission)
        total_cost = cost + commission
        
        # 检查资金
        if total_cost > self.cash:
            max_shares = int((self.cash - self.min_commission) / price / 100) * 100
            if max_shares < 100:
                return {"success": False, "error": f"资金不足，需要{total_cost:.2f}，可用{self.cash:.2f}"}
            shares = max_shares
            cost = shares * price
            commission = max(cost * self.commission_rate, self.min_commission)
            total_cost = cost + commission
        
        # 创建订单
        self.order_counter += 1
        order = Order(
            order_id=f"PT{self.order_counter:06d}",
            symbol=symbol, side="买入",
            price=price, shares=shares,
            status="已成交",
            created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            filled_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            filled_price=price, filled_shares=shares,
            commission=commission, reason=reason
        )
        self.orders.append(order)
        
        # 更新资金
        self.cash -= total_cost
        
        # 更新持仓
        if symbol in self.positions:
            pos = self.positions[symbol]
            total_shares = pos.shares + shares
            pos.avg_cost = (pos.avg_cost * pos.shares + price * shares) / total_shares
            pos.shares = total_shares
        else:
            self.positions[symbol] = Position(
                symbol=symbol, shares=shares,
                avg_cost=price, current_price=price,
                market_value=cost,
                entry_date=datetime.now().strftime('%Y-%m-%d'),
                max_price=price, holding_days=0
            )
        
        # 记录交易历史
        self.trade_history.append({
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "type": "买入", "symbol": symbol,
            "price": price, "shares": shares,
            "cost": total_cost, "commission": commission,
            "reason": reason,
            "cash_after": self.cash
        })
        
        self._save_state()
        
        logger.info(f"🟢 买入 {symbol} {shares}股 @ ¥{price:.2f} 花费 ¥{total_cost:.2f} (佣金¥{commission:.2f})")
        
        return {
            "success": True, "order_id": order.order_id,
            "symbol": symbol, "shares": shares, "price": price,
            "cost": total_cost, "commission": commission,
            "cash_after": self.cash
        }
    
    def sell(self, symbol: str, price: float, shares: int = 0,
             reason: str = "") -> Dict:
        """
        卖出股票
        
        Args:
            symbol: 股票代码
            price: 卖出价格
            shares: 卖出股数（0=全部卖出）
            reason: 卖出原因
        
        Returns:
            交易结果字典
        """
        # 检查持仓
        if symbol not in self.positions:
            return {"success": False, "error": f"没有{symbol}的持仓"}
        
        pos = self.positions[symbol]
        
        # 卖出全部
        if shares <= 0:
            shares = pos.shares
        
        if shares > pos.shares:
            return {"success": False, "error": f"持仓不足，持有{pos.shares}股，尝试卖出{shares}股"}
        
        # 计算费用
        revenue = shares * price
        commission = max(revenue * self.commission_rate, self.min_commission)
        stamp_tax = revenue * self.stamp_tax_rate
        net_revenue = revenue - commission - stamp_tax
        
        # 计算盈亏
        cost_basis = pos.avg_cost * shares
        profit = net_revenue - cost_basis
        profit_pct = (profit / cost_basis) * 100
        
        # 创建订单
        self.order_counter += 1
        order = Order(
            order_id=f"PT{self.order_counter:06d}",
            symbol=symbol, side="卖出",
            price=price, shares=shares,
            status="已成交",
            created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            filled_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            filled_price=price, filled_shares=shares,
            commission=commission, reason=reason
        )
        self.orders.append(order)
        
        # 更新资金
        self.cash += net_revenue
        
        # 更新持仓
        pos.shares -= shares
        if pos.shares <= 0:
            del self.positions[symbol]
        
        # 记录交易历史
        self.trade_history.append({
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "type": "卖出", "symbol": symbol,
            "price": price, "shares": shares,
            "revenue": net_revenue,
            "commission": commission,
            "stamp_tax": stamp_tax,
            "profit": profit, "profit_pct": profit_pct,
            "holding_days": pos.holding_days,
            "reason": reason,
            "cash_after": self.cash
        })
        
        self._save_state()
        
        emoji = "🟢" if profit > 0 else "🔴"
        logger.info(f"{emoji} 卖出 {symbol} {shares}股 @ ¥{price:.2f} "
                     f"盈亏 ¥{profit:+.2f} ({profit_pct:+.2f}%) 持仓{pos.holding_days}天")
        
        return {
            "success": True, "order_id": order.order_id,
            "symbol": symbol, "shares": shares, "price": price,
            "revenue": net_revenue, "commission": commission,
            "stamp_tax": stamp_tax,
            "profit": profit, "profit_pct": profit_pct,
            "holding_days": pos.holding_days,
            "cash_after": self.cash
        }
    
    # ==================== 持仓和账户查询 ====================
    
    def update_prices(self, prices: Dict[str, float]):
        """更新持仓价格"""
        for symbol, price in prices.items():
            if symbol in self.positions:
                pos = self.positions[symbol]
                pos.current_price = price
                pos.market_value = pos.shares * price
                pos.unrealized_pnl = (price - pos.avg_cost) * pos.shares
                pos.unrealized_pnl_pct = ((price - pos.avg_cost) / pos.avg_cost) * 100
                if price > pos.max_price:
                    pos.max_price = price
                # 计算持仓天数
                try:
                    entry = datetime.strptime(pos.entry_date, '%Y-%m-%d')
                    pos.holding_days = (datetime.now() - entry).days
                except:
                    pos.holding_days = 0
    
    def get_account_summary(self) -> Dict:
        """获取账户摘要"""
        total_market_value = sum(p.market_value for p in self.positions.values())
        total_unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        total_assets = self.cash + total_market_value
        total_return = total_assets - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100
        
        # 交易统计
        sell_trades = [t for t in self.trade_history if t['type'] == '卖出']
        total_trades = len(sell_trades)
        win_trades = len([t for t in sell_trades if t.get('profit', 0) > 0])
        
        return {
            "initial_capital": self.initial_capital,
            "total_assets": total_assets,
            "cash": self.cash,
            "market_value": total_market_value,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "unrealized_pnl": total_unrealized_pnl,
            "position_count": len(self.positions),
            "total_trades": total_trades,
            "win_trades": win_trades,
            "win_rate": (win_trades / total_trades * 100) if total_trades > 0 else 0,
            "order_count": len(self.orders)
        }
    
    def get_positions_df(self) -> pd.DataFrame:
        """获取持仓DataFrame"""
        if not self.positions:
            return pd.DataFrame()
        
        rows = []
        for symbol, pos in self.positions.items():
            rows.append({
                "代码": symbol,
                "持仓": pos.shares,
                "成本价": round(pos.avg_cost, 2),
                "现价": round(pos.current_price, 2),
                "市值": round(pos.market_value, 2),
                "浮盈": round(pos.unrealized_pnl, 2),
                "盈亏%": round(pos.unrealized_pnl_pct, 2),
                "最高价": round(pos.max_price, 2),
                "持仓天": pos.holding_days,
                "买入日": pos.entry_date
            })
        
        return pd.DataFrame(rows)
    
    def print_account_status(self):
        """打印账户状态"""
        summary = self.get_account_summary()
        
        print("\n" + "=" * 70)
        print("💰 模拟盘账户状态")
        print("=" * 70)
        print(f"  初始资金:  ¥{summary['initial_capital']:>14,.2f}")
        print(f"  总资产:    ¥{summary['total_assets']:>14,.2f}")
        print(f"  可用资金:  ¥{summary['cash']:>14,.2f}")
        print(f"  持仓市值:  ¥{summary['market_value']:>14,.2f}")
        
        emoji = "🟢" if summary['total_return'] >= 0 else "🔴"
        print(f"  {emoji} 总盈亏:  ¥{summary['total_return']:>+14,.2f} ({summary['total_return_pct']:+.2f}%)")
        print(f"  📊 未实现:  ¥{summary['unrealized_pnl']:>+14,.2f}")
        
        print(f"\n📈 交易统计:")
        print(f"  持仓数量:  {summary['position_count']}")
        print(f"  总交易:    {summary['total_trades']}")
        print(f"  胜率:      {summary['win_rate']:.1f}%")
        
        # 持仓详情
        if self.positions:
            print(f"\n📋 持仓详情:")
            pos_df = self.get_positions_df()
            print(pos_df.to_string(index=False))
        
        # 最近交易
        if self.trade_history:
            print(f"\n📝 最近5笔交易:")
            for t in self.trade_history[-5:]:
                emoji = "🟢" if t['type'] == '买入' else ("🟢" if t.get('profit', 0) > 0 else "🔴")
                if t['type'] == '买入':
                    print(f"  {emoji} {t['time']} 买入 {t['symbol']} {t['shares']}股 @ ¥{t['price']:.2f}")
                else:
                    print(f"  {emoji} {t['time']} 卖出 {t['symbol']} {t['shares']}股 @ ¥{t['price']:.2f} "
                          f"盈亏¥{t.get('profit',0):+.2f}({t.get('profit_pct',0):+.2f}%)")
        
        print("=" * 70)
    
    # ==================== 自动策略执行 ====================
    
    def run_strategy(self, symbol: str, preset: str = 'balanced',
                     check_interval: int = 60, max_iterations: int = 0):
        """
        运行自动策略
        
        Args:
            symbol: 股票代码
            preset: 策略预设
            check_interval: 检查间隔（秒）
            max_iterations: 最大迭代次数（0=无限）
        """
        from real_data_fetcher import RealDataFetcher
        from comprehensive_quant_engine import ComprehensiveQuantEngine
        from comprehensive_strategy import ComprehensiveStrategy
        
        fetcher = RealDataFetcher(cache_dir=".cache/stock_data")
        strategy = ComprehensiveStrategy(preset)
        params = strategy.params
        
        iteration = 0
        
        print(f"\n🤖 启动自动策略: {params['name']}")
        print(f"   股票: {symbol}")
        print(f"   检查间隔: {check_interval}秒")
        print(f"   买入阈值: {params['buy_score_threshold']}")
        print(f"   止盈: {params['take_profit_pct']}%  止损: {params['stop_loss_pct']}%")
        print()
        
        while max_iterations == 0 or iteration < max_iterations:
            iteration += 1
            
            try:
                # 获取最新数据
                df = fetcher.fetch_kline(symbol, 500)
                if df is None:
                    logger.warning("数据获取失败，等待重试...")
                    time.sleep(check_interval)
                    continue
                
                # 计算因子和评分
                engine = ComprehensiveQuantEngine(
                    cap_style=ComprehensiveQuantEngine.detect_cap_style(
                        stock_code=symbol, 
                        avg_amount=df['Volume'].tail(20).mean() * df['Close'].tail(20).mean() / 10000
                    )
                )
                df = engine.compute_all_factors(df)
                df = engine.compute_comprehensive_score(df)
                
                # 获取最新数据
                latest = df.iloc[-1]
                close = latest['Close']
                comp_score = latest['Score_Comprehensive']
                tech_score = latest['Score_Technical']
                fund_score = latest['Score_FundFlow']
                
                # 更新持仓价格
                real_quote = fetcher.fetch_realtime(symbol)
                if real_quote:
                    close = real_quote.get('price', close)
                
                self.update_prices({symbol: close})
                
                # 检查是否需要交易
                has_position = symbol in self.positions
                
                if has_position:
                    # 检查卖出条件
                    pos = self.positions[symbol]
                    profit_pct = (close - pos.avg_cost) / pos.avg_cost * 100
                    
                    sell_reason = ""
                    if profit_pct >= params['take_profit_pct']:
                        sell_reason = f"止盈({profit_pct:.1f}%)"
                    elif profit_pct <= -params['stop_loss_pct']:
                        sell_reason = f"止损({profit_pct:.1f}%)"
                    elif comp_score < params['sell_score_threshold']:
                        sell_reason = f"评分恶化({comp_score:.1f}<{params['sell_score_threshold']})"
                    elif pos.holding_days >= params['max_holding_days']:
                        sell_reason = f"持仓超时({pos.holding_days}天)"
                    
                    if sell_reason:
                        result = self.sell(symbol, close, reason=sell_reason)
                        self.print_account_status()
                else:
                    # 检查买入条件
                    if comp_score > params['buy_score_threshold'] and tech_score > params['tech_min']:
                        # 分配仓位（默认30%资金）
                        position_pct = 0.3
                        result = self.buy(symbol, close, 
                                         amount=self.cash * position_pct,
                                         reason=f"综合评分{comp_score:.1f}")
                        self.print_account_status()
                
                # 打印状态
                now = datetime.now().strftime('%H:%M:%S')
                pos_info = ""
                if symbol in self.positions:
                    p = self.positions[symbol]
                    pos_info = f" 持仓{p.shares}股 成本{p.avg_cost:.2f} 浮盈{p.unrealized_pnl_pct:+.2f}%"
                
                logger.info(f"[{now}] #{iteration} {symbol} ¥{close:.2f} "
                            f"综合{comp_score:.1f} 技术{tech_score:.1f} 资金{fund_score:.1f}{pos_info}")
                
            except Exception as e:
                logger.error(f"策略执行错误: {e}")
            
            # 等待下一次检查
            if max_iterations == 0 or iteration < max_iterations:
                time.sleep(check_interval)
    
    # ==================== 状态持久化 ====================
    
    def _save_state(self):
        """保存状态到文件"""
        state = {
            "cash": self.cash,
            "initial_capital": self.initial_capital,
            "order_counter": self.order_counter,
            "positions": {k: asdict(v) for k, v in self.positions.items()},
            "trade_history": self.trade_history[-200:],  # 保留最近200笔
            "saved_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        filepath = os.path.join(self.data_dir, "account_state.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def _load_state(self):
        """从文件加载状态"""
        filepath = os.path.join(self.data_dir, "account_state.json")
        if not os.path.exists(filepath):
            return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            self.cash = state.get('cash', self.initial_capital)
            self.initial_capital = state.get('initial_capital', self.initial_capital)
            self.order_counter = state.get('order_counter', 0)
            self.trade_history = state.get('trade_history', [])
            
            for symbol, pos_data in state.get('positions', {}).items():
                self.positions[symbol] = Position(**pos_data)
            
            logger.info(f"📂 加载模拟盘状态: 资金¥{self.cash:,.2f} 持仓{len(self.positions)}只")
        except Exception as e:
            logger.warning(f"加载状态失败: {e}")
    
    def reset(self):
        """重置账户"""
        self.cash = self.initial_capital
        self.positions = {}
        self.orders = []
        self.trade_history = []
        self.order_counter = 0
        self._save_state()
        logger.info("🔄 模拟盘已重置")


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(description='模拟盘交易系统')
    parser.add_argument('--capital', type=float, default=1000000, help='初始资金（默认100万）')
    parser.add_argument('--stock', type=str, default='600519', help='股票代码')
    parser.add_argument('--preset', type=str, default='balanced',
                        choices=['aggressive', 'balanced', 'conservative'],
                        help='策略类型')
    parser.add_argument('--auto', action='store_true', help='自动策略模式')
    parser.add_argument('--status', action='store_true', help='查看账户状态')
    parser.add_argument('--reset', action='store_true', help='重置账户')
    parser.add_argument('--buy', type=float, help='手动买入（指定价格）')
    parser.add_argument('--sell', type=float, help='手动卖出（指定价格）')
    parser.add_argument('--shares', type=int, default=0, help='股数（0=自动计算）')
    parser.add_argument('--interval', type=int, default=300, help='自动检查间隔（秒，默认300）')
    parser.add_argument('--amount', type=float, default=0, help='买入金额')
    
    args = parser.parse_args()
    
    engine = PaperTradingEngine(initial_capital=args.capital)
    
    if args.reset:
        engine.reset()
        print("✅ 模拟盘已重置")
        return
    
    if args.status:
        engine.print_account_status()
        return
    
    if args.buy:
        from real_data_fetcher import RealDataFetcher
        fetcher = RealDataFetcher()
        price = args.buy
        amount = args.amount if args.amount > 0 else engine.cash * 0.3
        result = engine.buy(args.stock, price, shares=args.shares, amount=amount,
                            reason="手动买入")
        print(f"买入结果: {result}")
        engine.print_account_status()
        return
    
    if args.sell:
        from real_data_fetcher import RealDataFetcher
        fetcher = RealDataFetcher()
        result = engine.sell(args.stock, args.sell, shares=args.shares, reason="手动卖出")
        print(f"卖出结果: {result}")
        engine.print_account_status()
        return
    
    if args.auto:
        print("\n" + "=" * 70)
        print("🤖 模拟盘自动策略模式")
        print("=" * 70)
        engine.print_account_status()
        engine.run_strategy(args.stock, args.preset, args.interval)
        return
    
    # 默认显示状态
    engine.print_account_status()


if __name__ == '__main__':
    main()