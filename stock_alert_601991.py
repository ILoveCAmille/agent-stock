#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大唐发电(601991) 智能买卖点提醒系统
=====================================
功能：
  1. 每个交易日 9:30-11:30 / 13:00-15:00 每5分钟检查一次
  2. 基于多技术指标（MA/RSI/MACD/KDJ）综合评分生成买入/卖出信号
  3. 信号变化时通过 QQ 邮箱发送提醒
  4. 支持持仓盈亏跟踪

使用方法：
  python stock_alert_601991.py
  python stock_alert_601991.py --once    # 只运行一次（测试用）
  python stock_alert_601991.py --test    # 发送测试邮件

依赖（项目已安装）：
  - akshare（实时行情）
  - pandas / numpy（数据处理）
  - 复用项目 notification_service.py 的邮件发送

配置（在 .env 中）：
  DTCB_COST_PRICE=2.85    # 大唐发电持仓成本价（可选，默认自动获取）
  DTCB_SHARES=7000        # 持仓股数
"""

import sys
import os
import time
import json
import logging
import argparse
from datetime import datetime, time as dtime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ── 日志 ─────────────────────────────────────────────
LOG_FILE = Path(__file__).parent / "stock_alert_601991.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("DTCB_Alert")

# ── 信号状态持久化文件 ───────────────────────────────
STATE_FILE = Path(__file__).parent / ".dtcb_signal_state.json"


# ══════════════════════════════════════════════════════════
#  配置
# ══════════════════════════════════════════════════════════
class Config:
    STOCK_CODE = "601991"
    STOCK_NAME = "大唐发电"
    MARKET = "SH"  # 上海

    # 持仓信息（可在 .env 中覆盖）
    COST_PRICE: float = None  # None = 自动从历史数据获取
    SHARES: int = 7000

    # 检查间隔（秒）
    CHECK_INTERVAL_SEC = 300  # 5 分钟

    # 交易时段
    TRADING_SESSIONS = [
        (dtime(9, 30), dtime(11, 30)),
        (dtime(13, 0), dtime(15, 0)),
    ]

    # ── 信号阈值 ──
    # 卖出信号权重
    RSI_OVERBOUGHT = 70
    RSI_OVERBOUGHT_WARN = 65

    # 买入信号权重
    RSI_OVERSOLD = 35
    RSI_OVERSOLD_WARN = 40

    # 止损/止盈
    TRAILING_STOP_PCT = 0.08   # 从20日最高点回撤 8% 止损
    PROFIT_TARGET_PCT = 0.20   # 盈利 20% 止盈提醒

    # ── 价格触发线（两次卖出方案）──
    # 每档触发后自动标记已触发，不会重复提醒
    STOP_LOSS_PRICE = 7.50       # 止损线：跌破全卖
    SELL_TARGET_1 = 8.80         # 第一卖点
    SELL_TARGET_1_SHARES = 4000
    SELL_TARGET_2 = 9.20         # 第二卖点
    SELL_TARGET_2_SHARES = 3000

    # 发送邮件的最小信号变化间隔（秒），防止同信号反复发送
    MIN_ALERT_INTERVAL = 1800  # 30 分钟

    @classmethod
    def load_from_env(cls):
        """从环境变量加载配置"""
        from dotenv import load_dotenv
        load_dotenv(override=True)
        if os.getenv("DTCB_COST_PRICE"):
            cls.COST_PRICE = float(os.getenv("DTCB_COST_PRICE"))
        if os.getenv("DTCB_SHARES"):
            cls.SHARES = int(os.getenv("DTCB_SHARES"))


# ══════════════════════════════════════════════════════════
#  交易时间判断
# ══════════════════════════════════════════════════════════
def is_trading_day() -> bool:
    """判断今天是否为交易日（周一至周五，简易版）"""
    return datetime.now().weekday() < 5


def is_trading_time() -> bool:
    """判断当前是否在 A 股交易时段内"""
    if not is_trading_day():
        return False
    now = dtime(datetime.now().hour, datetime.now().minute, datetime.now().second)
    for start, end in Config.TRADING_SESSIONS:
        if start <= now <= end:
            return True
    return False


def next_trading_time_str() -> str:
    """返回距离下一个交易时段的描述"""
    if not is_trading_day():
        return "非交易日（周末），等待周一开盘"
    now = dtime(datetime.now().hour, datetime.now().minute)
    for start, end in Config.TRADING_SESSIONS:
        if now < start:
            return f"{start.strftime('%H:%M')} 开盘"
        if now <= end:
            return "正在交易中"
    return "今日交易已结束"


# ══════════════════════════════════════════════════════════
#  数据获取
# ══════════════════════════════════════════════════════════
def fetch_realtime_quote(symbol: str) -> dict | None:
    """通过 AKShare 获取实时行情（分钟级）"""
    try:
        import akshare as ak

        # 1. 分钟级数据（最新价）
        min_df = ak.stock_zh_a_hist_min_em(symbol=symbol, period="1", adjust="")
        if min_df.empty:
            logger.warning(f"AKShare 分钟数据为空: {symbol}")
            return None

        latest = min_df.iloc[-1]
        current_price = float(latest["收盘"])
        update_time = str(latest["时间"])

        # 2. 日线历史（昨收、今日统计）
        hist_df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="")
        if len(hist_df) >= 2:
            pre_close = float(hist_df.iloc[-2]["收盘"])
            today = hist_df.iloc[-1]
            open_price = float(today["开盘"])
            high_price = float(today["最高"])
            low_price = float(today["最低"])
            volume = float(today.get("成交量", 0))
            turnover = float(today.get("换手率", 0))
        else:
            pre_close = current_price
            open_price = current_price
            high_price = current_price
            low_price = current_price
            volume = 0
            turnover = 0

        change_pct = ((current_price - pre_close) / pre_close * 100) if pre_close > 0 else 0
        change_amt = current_price - pre_close

        return {
            "price": round(current_price, 2),
            "open": round(open_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "pre_close": round(pre_close, 2),
            "change_pct": round(change_pct, 2),
            "change_amt": round(change_amt, 2),
            "volume": int(volume),
            "turnover": round(turnover, 2),
            "update_time": update_time,
        }
    except Exception as e:
        logger.error(f"获取实时行情失败: {e}")
        return None


def fetch_history(symbol: str, days: int = 120) -> pd.DataFrame | None:
    """获取历史日K线数据"""
    try:
        import akshare as ak
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
        if df.empty:
            return None
        df = df.rename(columns={
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume",
            "成交额": "amount",
        })
        df["date"] = pd.to_datetime(df["date"])
        for col in ["open", "close", "high", "low"]:
            df[col] = df[col].astype(float)
        df = df.sort_values("date").reset_index(drop=True)
        return df
    except Exception as e:
        logger.error(f"获取历史数据失败: {e}")
        return None


# ══════════════════════════════════════════════════════════
#  技术指标计算
# ══════════════════════════════════════════════════════════
def compute_ma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(window=period).mean()


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3):
    """计算 KDJ 指标"""
    low_min = df["low"].rolling(window=n).min()
    high_max = df["high"].rolling(window=n).max()
    rsv = ((df["close"] - low_min) / (high_max - low_min + 1e-10)) * 100
    k = rsv.ewm(alpha=1 / m1, adjust=False).mean()
    d = k.ewm(alpha=1 / m2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def compute_indicators(df: pd.DataFrame) -> dict:
    """计算所有技术指标，返回最新值"""
    close = df["close"]
    high = df["high"]
    low = df["low"]

    result = {}

    # 均线
    for p in [5, 10, 20, 60]:
        ma = compute_ma(close, p)
        result[f"ma{p}"] = round(float(ma.iloc[-1]), 2) if not pd.isna(ma.iloc[-1]) else None

    # RSI
    rsi = compute_rsi(close, 14)
    result["rsi14"] = round(float(rsi.iloc[-1]), 1) if not pd.isna(rsi.iloc[-1]) else None

    # MACD
    macd_l, sig_l, hist = compute_macd(close)
    result["macd"] = round(float(macd_l.iloc[-1]), 4) if not pd.isna(macd_l.iloc[-1]) else None
    result["macd_signal"] = round(float(sig_l.iloc[-1]), 4) if not pd.isna(sig_l.iloc[-1]) else None
    result["macd_hist"] = round(float(hist.iloc[-1]), 4) if not pd.isna(hist.iloc[-1]) else None
    # 金叉/死叉判断（需要前一个值）
    result["macd_golden_cross"] = (
        macd_l.iloc[-1] > sig_l.iloc[-1] and macd_l.iloc[-2] <= sig_l.iloc[-2]
    ) if len(macd_l) >= 2 else False
    result["macd_death_cross"] = (
        macd_l.iloc[-1] < sig_l.iloc[-1] and macd_l.iloc[-2] >= sig_l.iloc[-2]
    ) if len(macd_l) >= 2 else False

    # KDJ
    k, d, j = compute_kdj(df)
    result["kdj_k"] = round(float(k.iloc[-1]), 1) if not pd.isna(k.iloc[-1]) else None
    result["kdj_d"] = round(float(d.iloc[-1]), 1) if not pd.isna(d.iloc[-1]) else None
    result["kdj_j"] = round(float(j.iloc[-1]), 1) if not pd.isna(j.iloc[-1]) else None
    result["kdj_golden_cross"] = (
        k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2]
    ) if len(k) >= 2 else False
    result["kdj_death_cross"] = (
        k.iloc[-1] < d.iloc[-1] and k.iloc[-2] >= d.iloc[-2]
    ) if len(k) >= 2 else False

    # MA 交叉
    ma5 = compute_ma(close, 5)
    ma20 = compute_ma(close, 20)
    result["ma_golden_cross"] = (
        ma5.iloc[-1] > ma20.iloc[-1] and ma5.iloc[-2] <= ma20.iloc[-2]
    ) if len(ma5) >= 2 else False
    result["ma_death_cross"] = (
        ma5.iloc[-1] < ma20.iloc[-1] and ma5.iloc[-2] >= ma20.iloc[-2]
    ) if len(ma5) >= 2 else False

    # 20日最高价（用于移动止损）
    result["high_20d"] = round(float(high.tail(20).max()), 2)

    # 当前价格
    result["price"] = round(float(close.iloc[-1]), 2)

    return result


# ══════════════════════════════════════════════════════════
#  信号生成
# ══════════════════════════════════════════════════════════
class SignalType:
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    WATCH_BUY = "watch_buy"
    STRONG_SELL = "strong_sell"
    SELL = "sell"
    WATCH_SELL = "watch_sell"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    HOLD = "hold"

    LABELS = {
        "strong_buy": "🟢🟢 强烈买入",
        "buy": "🟢 买入信号",
        "watch_buy": "👀 关注买入",
        "strong_sell": "🔴🔴 强烈卖出",
        "sell": "🔴 卖出信号",
        "watch_sell": "👀 关注卖出",
        "stop_loss": "⛔ 紧急止损",
        "take_profit": "💰 止盈提醒",
        "hold": "⚪ 持有观望",
    }


def generate_signal(indicators: dict, cost_price: float | None) -> dict:
    """
    基于多指标综合评分生成买卖信号

    卖出评分项（当前满仓时重点关注）：
      - RSI(14) > 70:  +2
      - RSI(14) > 65:  +1
      - MA5 < MA20:     +1
      - MACD 死叉:      +2
      - KDJ K < D 且 K > 80: +1
      - 价格 < MA20:    +1
      - 价格从20日高点回撤 > 8%: 直接触发止损

    买入评分项：
      - RSI(14) < 35:  +2
      - RSI(14) < 40:  +1
      - MA5 > MA20:     +1
      - MACD 金叉:      +2
      - KDJ K > D 且 K < 30: +1
      - 价格 > MA10:    +1
    """
    sell_score = 0
    buy_score = 0
    reasons = []

    price = indicators.get("price", 0)
    rsi = indicators.get("rsi14", 50)
    ma5 = indicators.get("ma5")
    ma10 = indicators.get("ma10")
    ma20 = indicators.get("ma20")

    # ── 卖出评分 ──
    if rsi is not None:
        if rsi > Config.RSI_OVERBOUGHT:
            sell_score += 2
            reasons.append(f"RSI={rsi:.1f}（严重超买）")
        elif rsi > Config.RSI_OVERBOUGHT_WARN:
            sell_score += 1
            reasons.append(f"RSI={rsi:.1f}（超买预警）")

    if ma5 is not None and ma20 is not None and ma5 < ma20:
        sell_score += 1
        reasons.append(f"MA5({ma5:.2f}) < MA20({ma20:.2f})（空头排列）")

    if indicators.get("macd_death_cross"):
        sell_score += 2
        reasons.append("MACD 死叉")

    k = indicators.get("kdj_k")
    d = indicators.get("kdj_d")
    if k is not None and d is not None and k < d and k > 80:
        sell_score += 1
        reasons.append(f"KDJ 高位死叉(K={k:.1f}, D={d:.1f})")

    if ma20 is not None and price < ma20:
        sell_score += 1
        reasons.append(f"价格({price:.2f}) < MA20({ma20:.2f})（弱势）")

    # ── 买入评分 ──
    if rsi is not None:
        if rsi < Config.RSI_OVERSOLD:
            buy_score += 2
            reasons.append(f"RSI={rsi:.1f}（严重超卖）")
        elif rsi < Config.RSI_OVERSOLD_WARN:
            buy_score += 1
            reasons.append(f"RSI={rsi:.1f}（超卖区域）")

    if ma5 is not None and ma20 is not None and ma5 > ma20:
        buy_score += 1
        reasons.append(f"MA5({ma5:.2f}) > MA20({ma20:.2f})（多头排列）")

    if indicators.get("macd_golden_cross"):
        buy_score += 2
        reasons.append("MACD 金叉")

    if k is not None and d is not None and k > d and k < 30:
        buy_score += 1
        reasons.append(f"KDJ 低位金叉(K={k:.1f}, D={d:.1f})")

    if ma10 is not None and price > ma10:
        buy_score += 1
        reasons.append(f"价格({price:.2f}) > MA10({ma10:.2f})")

    # ── 紧急信号 ──
    high_20d = indicators.get("high_20d", 0)
    if high_20d > 0 and price < high_20d * (1 - Config.TRAILING_STOP_PCT):
        signal_type = SignalType.STOP_LOSS
        reasons.insert(0, f"从20日高点{high_20d:.2f}回撤 > {Config.TRAILING_STOP_PCT:.0%}（现价{price:.2f}）")
        return {"signal": signal_type, "score": 99, "reasons": reasons, "buy_score": 0, "sell_score": 99}

    if cost_price and cost_price > 0 and price >= cost_price * (1 + Config.PROFIT_TARGET_PCT):
        profit_pct = (price - cost_price) / cost_price * 100
        signal_type = SignalType.TAKE_PROFIT
        reasons.insert(0, f"盈利 {profit_pct:.1f}%（成本{cost_price:.2f}，现价{price:.2f}）")
        return {"signal": signal_type, "score": 80, "reasons": reasons, "buy_score": 0, "sell_score": 80}

    # ── 综合判断 ──
    if sell_score >= 4:
        signal_type = SignalType.STRONG_SELL
    elif sell_score >= 2:
        signal_type = SignalType.SELL
    elif sell_score >= 1:
        signal_type = SignalType.WATCH_SELL
    elif buy_score >= 4:
        signal_type = SignalType.STRONG_BUY
    elif buy_score >= 2:
        signal_type = SignalType.BUY
    elif buy_score >= 1:
        signal_type = SignalType.WATCH_BUY
    else:
        signal_type = SignalType.HOLD

    return {
        "signal": signal_type,
        "score": max(sell_score, buy_score),
        "sell_score": sell_score,
        "buy_score": buy_score,
        "reasons": reasons,
    }


# ══════════════════════════════════════════════════════════
#  信号状态管理（防重复）
# ══════════════════════════════════════════════════════════
def load_signal_state() -> dict:
    """加载上次信号状态"""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_signal_state(state: dict):
    """保存信号状态"""
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def should_send_alert(new_signal_type: str, new_score: int) -> tuple[bool, str]:
    """
    判断是否需要发送新提醒
    返回 (是否发送, 原因)
    """
    state = load_signal_state()
    last_signal = state.get("last_signal", "")
    last_time_str = state.get("last_alert_time", "")
    last_score = state.get("last_score", 0)

    # 首次运行
    if not last_signal:
        return True, "首次运行"

    # 信号类型变了
    if new_signal_type != last_signal:
        return True, f"信号变化: {SignalType.LABELS.get(last_signal, last_signal)} → {SignalType.LABELS.get(new_signal_type, new_signal_type)}"

    # 同类信号但分数变化 >= 2
    if abs(new_score - last_score) >= 2:
        return True, f"信号强度变化: {last_score} → {new_score}"

    # 距离上次发送超过最小间隔（强制重发）
    if last_time_str:
        try:
            last_time = datetime.fromisoformat(last_time_str)
            if (datetime.now() - last_time).total_seconds() > Config.MIN_ALERT_INTERVAL:
                return True, "定期重发（超过30分钟）"
        except Exception:
            pass

    return False, "信号未变化"


# ══════════════════════════════════════════════════════════
#  邮件发送
# ══════════════════════════════════════════════════════════
def send_email_alert(
    signal_type: str,
    signal_data: dict,
    quote: dict,
    indicators: dict,
    cost_price: float | None,
) -> bool:
    """通过项目现有的 notification_service 发送邮件"""
    try:
        # 确保项目根目录在 path 中
        project_root = Path(__file__).parent
        sys.path.insert(0, str(project_root))

        from notification_service import notification_service

        label = SignalType.LABELS.get(signal_type, signal_type)
        price = quote["price"]
        change_pct = quote["change_pct"]

        # 计算盈亏
        profit_info = ""
        if cost_price and cost_price > 0:
            profit_pct = (price - cost_price) / cost_price * 100
            profit_amt = (price - cost_price) * Config.SHARES
            emoji = "📈" if profit_pct >= 0 else "📉"
            profit_info = f"""
        <tr><td><strong>💰 浮动盈亏</strong></td><td>{emoji} {profit_pct:+.2f}%（{profit_amt:+,.0f}元）</td></tr>"""

        # MA 指标行
        ma_row = ""
        for p in [5, 10, 20, 60]:
            v = indicators.get(f"ma{p}")
            if v is not None:
                rel = "↑" if price > v else "↓"
                ma_row += f"<tr><td>MA{p}</td><td>{v:.2f} {rel}</td></tr>"

        html = f"""
        <html><body style="font-family:'Microsoft YaHei',Arial,sans-serif;padding:0;margin:0;background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);">
        <div style="max-width:600px;margin:0 auto;background:rgba(255,255,255,0.06);border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.3);border:1px solid rgba(255,255,255,0.1);">

        <!-- 头部 -->
        <div style="background:linear-gradient(135deg,rgba(102,126,234,0.3),rgba(118,75,162,0.3));color:#fff;padding:24px;text-align:center;">
            <h1 style="margin:0;font-size:22px;">{label}</h1>
            <p style="margin:8px 0 0;opacity:0.8;font-size:14px;">
                {Config.STOCK_NAME}（{Config.STOCK_CODE}）| {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </p>
        </div>

        <!-- 价格卡片 -->
        <div style="padding:20px 24px;text-align:center;background:rgba(255,255,255,0.04);">
            <div style="font-size:36px;font-weight:bold;color:{'#e74c3c' if change_pct < 0 else '#27ae60'};">¥{price:.2f}</div>
            <div style="font-size:16px;color:{'#e74c3c' if change_pct < 0 else '#27ae60'};margin-top:4px;">
                {change_pct:+.2f}%（{quote['change_amt']:+.2f}）
            </div>
        </div>

        <!-- 详细指标 -->
        <div style="padding:20px 24px;">
            <table style="width:100%;border-collapse:collapse;font-size:14px;color:#e0e0e0;">
                <tr style="background:rgba(255,255,255,0.06);"><td style="padding:8px 12px;font-weight:bold;">📊 指标</td><td style="padding:8px 12px;font-weight:bold;">数值</td></tr>
                <tr><td style="padding:6px 12px;">开盘</td><td>{quote['open']:.2f}</td></tr>
                <tr><td style="padding:6px 12px;">最高</td><td style="color:#27ae60;">{quote['high']:.2f}</td></tr>
                <tr><td style="padding:6px 12px;">最低</td><td style="color:#e74c3c;">{quote['low']:.2f}</td></tr>
                <tr><td style="padding:6px 12px;">昨收</td><td>{quote['pre_close']:.2f}</td></tr>
                {ma_row}
                <tr><td style="padding:6px 12px;">RSI(14)</td><td>{indicators.get('rsi14','N/A')}</td></tr>
                <tr><td style="padding:6px 12px;">MACD</td><td>{indicators.get('macd','N/A')}</td></tr>
                <tr><td style="padding:6px 12px;">KDJ(K/D/J)</td><td>{indicators.get('kdj_k','N/A')}/{indicators.get('kdj_d','N/A')}/{indicators.get('kdj_j','N/A')}</td></tr>
                <tr><td style="padding:6px 12px;">成交量</td><td>{quote['volume']:,}手</td></tr>
                <tr><td style="padding:6px 12px;">换手率</td><td>{quote['turnover']}%</td></tr>
                {profit_info}
                <tr><td style="padding:6px 12px;">卖出评分</td><td style="color:#e74c3c;font-weight:bold;">{signal_data.get('sell_score',0)}</td></tr>
                <tr><td style="padding:6px 12px;">买入评分</td><td style="color:#27ae60;font-weight:bold;">{signal_data.get('buy_score',0)}</td></tr>
            </table>
        </div>

        <!-- 信号原因 -->
        <div style="padding:0 24px 20px;">
            <h3 style="font-size:15px;color:#ffffff;margin:0 0 8px;">📝 信号触发原因：</h3>
            <ul style="margin:0;padding-left:20px;color:rgba(255,255,255,0.75);line-height:1.8;">
                {''.join(f'<li>{r}</li>' for r in signal_data.get('reasons', []))}
            </ul>
        </div>

        <!-- 底部 -->
        <div style="background:rgba(255,255,255,0.04);padding:12px 24px;text-align:center;font-size:12px;color:rgba(255,255,255,0.4);border-top:1px solid rgba(255,255,255,0.08);">
            AI 股票分析系统 · 大唐发电智能提醒 · <a href="https://github.com/aiagents-stock" style="color:#667eea;">GitHub</a>
            <br>⚠ 本提醒仅供参考，不构成投资建议
        </div>

        </div></body></html>
        """

        subject = f"{label} - {Config.STOCK_NAME}({Config.STOCK_CODE}) ¥{price:.2f}"

        # 使用 notification_service 的底层邮件发送
        success = notification_service._send_custom_email(
            subject=subject,
            html_body=html,
            text_body=f"{label}\n{Config.STOCK_NAME}({Config.STOCK_CODE})\n当前价: ¥{price:.2f}\n涨跌幅: {change_pct:+.2f}%\n卖出评分: {signal_data.get('sell_score',0)}\n买入评分: {signal_data.get('buy_score',0)}\n原因: {', '.join(signal_data.get('reasons', []))}",
        )
        return success
    except Exception as e:
        logger.error(f"发送邮件失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ══════════════════════════════════════════════════════════
#  价格触发线检查（两次卖出 + 止损）
# ══════════════════════════════════════════════════════════
def check_price_levels(price: float, state: dict) -> dict | None:
    """
    检查当前价格是否触发预设的买卖价位。
    每档只触发一次（记录在 state 中）。
    返回触发信息 dict 或 None。
    """
    triggered = state.get("price_levels_triggered", [])

    # 止损线（最高优先级）
    if price <= Config.STOP_LOSS_PRICE and "stop_loss" not in triggered:
        pct = (price - Config.COST_PRICE) / Config.COST_PRICE * 100 if Config.COST_PRICE else 0
        return {
            "level": "stop_loss",
            "label": "⛔ 止损触发",
            "price_target": Config.STOP_LOSS_PRICE,
            "shares": Config.SHARES,
            "action": "全部卖出",
            "detail": f"价格 {price:.2f} 跌破止损线 {Config.STOP_LOSS_PRICE}（成本 ¥{Config.COST_PRICE}，亏损 {pct:+.1f}%）",
            "tag": "stop_loss",
        }

    # 第一卖点
    if price >= Config.SELL_TARGET_1 and "target_1" not in triggered:
        pct = (price - Config.COST_PRICE) / Config.COST_PRICE * 100 if Config.COST_PRICE else 0
        return {
            "level": "target_1",
            "label": f"💰 止盈第一目标",
            "price_target": Config.SELL_TARGET_1,
            "shares": Config.SELL_TARGET_1_SHARES,
            "action": f"卖出 {Config.SELL_TARGET_1_SHARES} 股",
            "detail": f"价格 {price:.2f} 触及第一卖点 {Config.SELL_TARGET_1}（盈利 {pct:+.1f}%，卖出 {Config.SELL_TARGET_1_SHARES} 股）",
            "tag": "target_1",
        }

    # 第二卖点
    if price >= Config.SELL_TARGET_2 and "target_2" not in triggered:
        pct = (price - Config.COST_PRICE) / Config.COST_PRICE * 100 if Config.COST_PRICE else 0
        return {
            "level": "target_2",
            "label": f"💰💰 止盈第二目标",
            "price_target": Config.SELL_TARGET_2,
            "shares": Config.SELL_TARGET_2_SHARES,
            "action": f"卖出 {Config.SELL_TARGET_2_SHARES} 股（全部清仓）",
            "detail": f"价格 {price:.2f} 触及第二卖点 {Config.SELL_TARGET_2}（盈利 {pct:+.1f}%，卖出剩余 {Config.SELL_TARGET_2_SHARES} 股，清仓）",
            "tag": "target_2",
        }

    return None


def send_price_alert(level_info: dict, quote: dict) -> bool:
    """发送价格触发线提醒邮件"""
    try:
        project_root = Path(__file__).parent
        sys.path.insert(0, str(project_root))
        from notification_service import notification_service

        price = quote["price"]
        change_pct = quote["change_pct"]
        cost = Config.COST_PRICE or 0

        # 盈亏计算
        if cost > 0:
            profit_pct = (price - cost) / cost * 100
            profit_amt = (price - cost) * level_info["shares"]
            profit_line = f"<tr><td><strong>💰 盈亏</strong></td><td>{profit_pct:+.1f}%（{profit_amt:+,.0f}元）</td></tr>"
        else:
            profit_line = ""

        is_stop = level_info["level"] == "stop_loss"
        bg_color = "#c0392b" if is_stop else "#27ae60"
        gradient = "linear-gradient(135deg,#c0392b,#e74c3c)" if is_stop else "linear-gradient(135deg,#1a6e30,#27ae60)"

        html = f"""
        <html><body style="font-family:'Microsoft YaHei',Arial,sans-serif;padding:0;margin:0;background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);">
        <div style="max-width:600px;margin:0 auto;background:rgba(255,255,255,0.06);border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.3);border:1px solid rgba(255,255,255,0.1);">

        <div style="background:linear-gradient(135deg,{gradient});color:#fff;padding:28px;text-align:center;">
            <h1 style="margin:0;font-size:24px;">{level_info['label']}</h1>
            <p style="margin:10px 0 0;opacity:0.8;font-size:14px;">
                {Config.STOCK_NAME}（{Config.STOCK_CODE}）| {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </p>
        </div>

        <div style="padding:24px;text-align:center;background:rgba(255,255,255,0.04);">
            <div style="font-size:48px;font-weight:bold;color:{bg_color};">¥{price:.2f}</div>
            <div style="font-size:16px;color:{bg_color};margin-top:6px;">触发了 {level_info['price_target']} 价位线</div>
        </div>

        <div style="padding:20px 24px;">
            <table style="width:100%;border-collapse:collapse;font-size:14px;color:#e0e0e0;">
                <tr style="background:rgba(255,255,255,0.06);"><td style="padding:10px 12px;font-weight:bold;">📋 项目</td><td style="padding:10px 12px;font-weight:bold;">详情</td></tr>
                <tr><td style="padding:8px 12px;">当前价</td><td style="font-weight:bold;color:{bg_color};">¥{price:.2f}</td></tr>
                <tr><td style="padding:8px 12px;">涨跌幅</td><td>{change_pct:+.2f}%</td></tr>
                <tr><td style="padding:8px 12px;">成本价</td><td>¥{cost:.2f}</td></tr>
                <tr><td style="padding:8px 12px;">触发价位</td><td style="font-weight:bold;">¥{level_info['price_target']}</td></tr>
                <tr><td style="padding:8px 12px;"><strong>🎯 建议操作</strong></td><td style="font-weight:bold;font-size:16px;color:{bg_color};">{level_info['action']}</td></tr>
                {profit_line}
                <tr><td style="padding:8px 12px;">成交量</td><td>{quote.get('volume',0):,}手</td></tr>
                <tr><td style="padding:8px 12px;">换手率</td><td>{quote.get('turnover',0)}%</td></tr>
            </table>
        </div>

        <div style="margin:0 24px 20px;padding:16px;background:rgba(243,156,18,0.1);border-left:4px solid #f39c12;border-radius:8px;color:#f0d080;">
            <strong>⚠ 操作提醒：</strong><br>
            {level_info['detail']}<br>
            请登录券商 APP 执行操作。
        </div>

        <div style="background:rgba(255,255,255,0.04);padding:12px 24px;text-align:center;font-size:12px;color:rgba(255,255,255,0.4);border-top:1px solid rgba(255,255,255,0.08);">
            AI 股票分析系统 · 大唐发电价格触发提醒
            <br>⚠ 本提醒仅供参考，不构成投资建议
        </div>

        </div></body></html>
        """

        subject = f"{level_info['label']} - {Config.STOCK_NAME} ¥{price:.2f} | {level_info['action']}"

        success = notification_service._send_custom_email(
            subject=subject,
            html_body=html,
            text_body=f"{level_info['label']}\n{Config.STOCK_NAME}({Config.STOCK_CODE})\n当前价: ¥{price:.2f}\n触发价位: ¥{level_info['price_target']}\n操作: {level_info['action']}\n详情: {level_info['detail']}",
        )
        return success
    except Exception as e:
        logger.error(f"价格提醒邮件发送失败: {e}")
        return False


# ══════════════════════════════════════════════════════════
#  主循环
# ══════════════════════════════════════════════════════════
def run_once(verbose: bool = True) -> dict | None:
    """执行一次完整的检查-分析-提醒流程"""
    symbol = Config.STOCK_CODE

    # 1. 获取实时行情
    quote = fetch_realtime_quote(symbol)
    if not quote:
        logger.error("获取实时行情失败，跳过本轮")
        return None

    price = quote["price"]

    if verbose:
        logger.info(
            f"📊 {Config.STOCK_NAME} | 现价: ¥{price:.2f} | "
            f"涨跌: {quote['change_pct']:+.2f}% | 昨收: {quote['pre_close']:.2f}"
        )

    # 2. 优先检查价格触发线（止损/止盈价位）
    state = load_signal_state()
    level_info = check_price_levels(price, state)
    result = {"quote": quote, "price_alert_sent": False, "signal_alert_sent": False}

    if level_info:
        tag = level_info["tag"]
        if verbose:
            logger.info(f"🚨 价格触发: {level_info['label']} | ¥{price:.2f} 触及 ¥{level_info['price_target']} | {level_info['action']}")

        success = send_price_alert(level_info, quote)
        if success:
            logger.info("✅ 价格触发邮件发送成功")
            result["price_alert_sent"] = True
            # 标记该价位已触发，不再重复
            triggered = state.get("price_levels_triggered", [])
            if tag not in triggered:
                triggered.append(tag)
            state["price_levels_triggered"] = triggered
            state["last_price_alert_time"] = datetime.now().isoformat()
            state["last_price"] = price
            save_signal_state(state)
        else:
            logger.error("❌ 价格触发邮件发送失败")

    # 3. 获取历史数据 + 计算技术指标
    df = fetch_history(symbol, days=120)
    if df is None or len(df) < 30:
        logger.error("历史数据不足，无法计算指标")
        return result if result.get("price_alert_sent") else None

    indicators = compute_indicators(df)
    if verbose:
        logger.info(
            f"📈 指标 | MA5:{indicators.get('ma5','?')} | MA20:{indicators.get('ma20','?')} | "
            f"RSI:{indicators.get('rsi14','?')} | MACD:{indicators.get('macd','?')} | "
            f"KDJ:{indicators.get('kdj_k','?')}/{indicators.get('kdj_d','?')}/{indicators.get('kdj_j','?')}"
        )

    # 4. 生成技术信号
    cost_price = Config.COST_PRICE
    signal_data = generate_signal(indicators, cost_price)
    signal_type = signal_data["signal"]
    label = SignalType.LABELS.get(signal_type, signal_type)

    if verbose:
        logger.info(
            f"🎯 信号: {label} | 卖出评分:{signal_data['sell_score']} | "
            f"买入评分:{signal_data['buy_score']} | 原因: {'; '.join(signal_data['reasons'][:3])}"
        )

    # 5. 是否发送技术信号提醒
    should_send, reason = should_send_alert(signal_type, signal_data["score"])
    if verbose:
        logger.info(f"📬 发送决策: {'发送' if should_send else '跳过'}（{reason}）")

    if should_send and signal_type != SignalType.HOLD:
        logger.info(f"✉ 正在发送技术信号邮件...")
        success = send_email_alert(signal_type, signal_data, quote, indicators, cost_price)
        if success:
            logger.info("✅ 技术信号邮件发送成功")
            result["signal_alert_sent"] = True
            state = load_signal_state()
            state["last_signal"] = signal_type
            state["last_score"] = signal_data["score"]
            state["last_alert_time"] = datetime.now().isoformat()
            state["last_price"] = price
            save_signal_state(state)
        else:
            logger.error("❌ 技术信号邮件发送失败")

    # 更新常规状态
    state = load_signal_state()
    state["last_signal"] = signal_type
    state["last_score"] = signal_data["score"]
    state["last_price"] = price
    state["last_check_time"] = datetime.now().isoformat()
    save_signal_state(state)

    result["indicators"] = indicators
    result["signal"] = signal_data
    return result


def main_loop():
    """主循环：交易时间每5分钟执行一次"""
    logger.info("=" * 60)
    logger.info(f"  🚀 大唐发电(601991) 智能买卖点提醒系统 启动")
    logger.info(f"  检查间隔: {Config.CHECK_INTERVAL_SEC}秒")
    logger.info(f"  交易时段: 9:30-11:30, 13:00-15:00（周一至周五）")
    if Config.COST_PRICE:
        logger.info(f"  持仓成本: ¥{Config.COST_PRICE:.2f} × {Config.SHARES}股")
    else:
        logger.info(f"  持仓: {Config.SHARES}股（未设置成本价）")
    logger.info(f"  价格触发线:")
    logger.info(f"    第一卖点: ¥{Config.SELL_TARGET_1} → 卖 {Config.SELL_TARGET_1_SHARES} 股 (+{(Config.SELL_TARGET_1/Config.COST_PRICE-1)*100:.1f}%)")
    logger.info(f"    第二卖点: ¥{Config.SELL_TARGET_2} → 卖 {Config.SELL_TARGET_2_SHARES} 股 (+{(Config.SELL_TARGET_2/Config.COST_PRICE-1)*100:.1f}%)")
    logger.info(f"    止损线:   ¥{Config.STOP_LOSS_PRICE} → 全部清仓 ({(Config.STOP_LOSS_PRICE/Config.COST_PRICE-1)*100:.1f}%)")
    logger.info(f"  通知邮箱: 已配置（QQ邮箱）")
    logger.info("=" * 60)

    last_status_log = None

    while True:
        try:
            now = datetime.now()

            if is_trading_time():
                # 交易时段：执行检查
                logger.info(f"\n⏰ [{now.strftime('%H:%M:%S')}] 执行盘中检查...")
                result = run_once(verbose=True)

                if result and result.get("alert_sent"):
                    logger.info("📨 已发送提醒邮件，请查收 QQ 邮箱")

                logger.info(f"⏳ 等待 {Config.CHECK_INTERVAL_SEC} 秒后下次检查...")
                time.sleep(Config.CHECK_INTERVAL_SEC)

            else:
                # 非交易时段：等待，定期输出状态
                next_info = next_trading_time_str()
                status = f"⏸ 非交易时段 | {next_info}"
                if status != last_status_log:
                    logger.info(status)
                    last_status_log = status

                # 计算需要等待多久
                if is_trading_day():
                    now_t = dtime(now.hour, now.minute)
                    # 找到下一个交易时段
                    for start, end in Config.TRADING_SESSIONS:
                        if now_t < start:
                            wait_seconds = (datetime.combine(now.date(), start) - now).total_seconds()
                            wait_seconds = min(wait_seconds, 300)  # 最多等5分钟再检查
                            time.sleep(max(wait_seconds, 30))
                            break
                    else:
                        # 今天交易已结束
                        time.sleep(300)
                else:
                    # 非交易日
                    time.sleep(600)  # 10分钟检查一次

        except KeyboardInterrupt:
            logger.info("\n⏹ 用户中断，系统退出")
            break
        except Exception as e:
            logger.error(f"主循环异常: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(60)


# ══════════════════════════════════════════════════════════
#  入口
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="大唐发电(601991) 智能买卖点提醒系统")
    parser.add_argument("--once", action="store_true", help="只运行一次检查后退出")
    parser.add_argument("--test", action="store_true", help="发送测试邮件")
    args = parser.parse_args()

    Config.load_from_env()

    if args.test:
        # 发送测试邮件
        logger.info("📧 发送测试邮件...")
        from notification_service import notification_service
        success, msg = notification_service.send_test_email()
        logger.info(f"{'✅' if success else '❌'} {msg}")
        sys.exit(0)

    if args.once:
        logger.info("🔍 执行单次检查...")
        result = run_once(verbose=True)
        if result:
            signal_data = result.get("signal")
            if signal_data:
                signal_type = signal_data["signal"]
                label = SignalType.LABELS.get(signal_type, signal_type)
                logger.info(f"\n{'='*40}")
                logger.info(f"  最终信号: {label}")
                logger.info(f"  卖出评分: {signal_data['sell_score']}")
                logger.info(f"  买入评分: {signal_data['buy_score']}")
                logger.info(f"  触发原因: {'; '.join(signal_data['reasons'][:5])}")
            logger.info(f"  价格触发: {'已触发' if result.get('price_alert_sent') else '未触发'}")
            logger.info(f"  技术信号: {'已发送' if result.get('signal_alert_sent') else '未触发发送条件'}")
            logger.info(f"{'='*40}")
        sys.exit(0)

    # 默认：持续运行
    main_loop()
