#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股周度市场总结与下周展望
==========================
每周六 10:00 自动生成并推送 HTML 报告，包含：
  1. 大盘指数周度回顾（上证/深证/创业板/科创50）
  2. 行业板块涨跌排名（TOP10 + BOTTOM5）
  3. 市场情绪指标（涨跌比、量能、涨停跌停）
  4. 下周技术面展望（趋势/支撑压力/关注方向）

使用方法：
  python weekly_market_report.py             # 持续运行（每周六 10:00）
  python weekly_market_report.py --once      # 立即生成一次
  python weekly_market_report.py --install   # 安装为 Windows 计划任务
"""

import sys
import os
import time
import json
import logging
import argparse
from datetime import datetime, time as dtime, timedelta
from pathlib import Path

import requests
import numpy as np

# ── 项目根目录 ──
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── 日志 ──
LOG_FILE = PROJECT_ROOT / "weekly_market_report.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("WeeklyReport")


# ══════════════════════════════════════════════════════════
#  Config
# ══════════════════════════════════════════════════════════
class Config:
    RUN_DAY = 5          # 周六 (0=Mon, 5=Sat)
    RUN_HOUR = 10        # 上午 10:00
    RUN_MINUTE = 0

    INDICES = {
        "sh000001": "上证指数",
        "sz399001": "深证成指",
        "sz399006": "创业板指",
        "sh000688": "科创50",
        "sh000300": "沪深300",
    }

    # 行业板块数量
    TOP_SECTORS = 10
    BOTTOM_SECTORS = 5

    # 技术指标参数
    MA_PERIODS = [5, 10, 20, 60]


# ══════════════════════════════════════════════════════════
#  工具函数
# ══════════════════════════════════════════════════════════
def is_saturday() -> bool:
    return datetime.now().weekday() == 5


def is_schedule_time() -> bool:
    now = datetime.now()
    return now.weekday() == Config.RUN_DAY and now.hour == Config.RUN_HOUR and now.minute < 5


# ══════════════════════════════════════════════════════════
#  数据获取
# ══════════════════════════════════════════════════════════
def fetch_index_weekly() -> list[dict]:
    """获取主要指数本周 & 上周表现"""
    results = []
    session = requests.Session()
    session.trust_env = False

    symbols = list(Config.INDICES.keys())
    url = f"https://hq.sinajs.cn/list={','.join(symbols)}"
    headers = {"Referer": "https://finance.sina.com.cn"}

    try:
        r = session.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return results

        for line in r.text.strip().split("\n"):
            if '="' not in line:
                continue
            parts = line.split("=")
            sym = parts[0].split("_")[-1]
            data = parts[1].strip('"').split(",")
            if len(data) < 6:
                continue

            name = Config.INDICES.get(sym, sym)
            latest = float(data[3]) if data[3] else 0
            prev_close = float(data[2]) if data[2] else 1
            high = float(data[4]) if data[4] else 0
            low = float(data[5]) if data[5] else 0
            amount = float(data[9]) if len(data) > 9 and data[9] else 0

            results.append({
                "name": name,
                "latest": round(latest, 2),
                "prev_close": round(prev_close, 2),
                "week_change": round((latest / prev_close - 1) * 100, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "amount": round(amount / 1e8, 1),
            })
    except Exception as e:
        logger.warning(f"指数数据获取失败: {e}")

    # 补充：获取周线数据计算更多指标
    try:
        import akshare as ak
        for idx_info in results:
            sym_map = {
                "上证指数": "000001", "深证成指": "399001",
                "创业板指": "399006", "科创50": "000688", "沪深300": "000300",
            }
            code = sym_map.get(idx_info["name"])
            if not code:
                continue
            try:
                df = ak.stock_zh_index_daily_em(symbol=f"sh{code}" if code.startswith("0") else f"sz{code}")
                if df is not None and len(df) >= 60:
                    close = df["close"].astype(float)
                    for p in Config.MA_PERIODS:
                        ma = close.rolling(p).mean()
                        idx_info[f"ma{p}"] = round(float(ma.iloc[-1]), 2) if not pd.isna(ma.iloc[-1]) else 0
                    # 近4周趋势
                    idx_info["week4_change"] = round((close.iloc[-1] / close.iloc[-20] - 1) * 100, 2) if len(close) >= 20 else 0
            except:
                pass
    except Exception as e:
        logger.warning(f"周线数据补充失败: {e}")

    return results


def fetch_sector_rankings() -> tuple[list[dict], list[dict]]:
    """获取行业板块本周涨跌排名"""
    top_sectors = []
    bottom_sectors = []

    try:
        import akshare as ak
        import pandas as pd

        # 获取行业板块列表
        try:
            sector_df = ak.stock_board_industry_name_em()
        except:
            # fallback: 用概念板块
            sector_df = ak.stock_board_concept_name_em()

        if sector_df is None or sector_df.empty:
            return top_sectors, bottom_sectors

        sectors = []
        for _, row in sector_df.iterrows():
            name = str(row.get("板块名称", row.get("概念名称", "")))
            code = str(row.get("板块代码", row.get("概念代码", "")))
            if name and code:
                sectors.append({"name": name, "code": code})

        if not sectors:
            return top_sectors, bottom_sectors

        # 获取每个板块的近期涨跌幅
        scored = []
        for sec in sectors:
            try:
                hist = ak.stock_board_industry_hist_em(
                    symbol=sec["name"],
                    period="周线",
                    adjust=""
                )
                if hist is not None and len(hist) >= 2:
                    this_week = float(hist.iloc[-1]["收盘"])
                    last_week = float(hist.iloc[-2]["收盘"])
                    pct = (this_week / last_week - 1) * 100
                    scored.append({**sec, "week_pct": round(pct, 2)})
            except:
                pass

        scored.sort(key=lambda x: x["week_pct"], reverse=True)
        top_sectors = scored[:Config.TOP_SECTORS]
        bottom_sectors = sorted(scored, key=lambda x: x["week_pct"])[:Config.BOTTOM_SECTORS]

    except Exception as e:
        logger.warning(f"板块数据获取失败: {e}")

    return top_sectors, bottom_sectors


def fetch_market_breadth() -> dict:
    """获取市场情绪指标"""
    result = {
        "up_count": 0,
        "down_count": 0,
        "flat_count": 0,
        "limit_up": 0,
        "limit_down": 0,
        "total_volume": 0,
        "avg_change": 0,
    }

    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return result

        pct = df["涨跌幅"].astype(float)
        result["up_count"] = int((pct > 0).sum())
        result["down_count"] = int((pct < 0).sum())
        result["flat_count"] = int((pct == 0).sum())
        result["avg_change"] = round(float(pct.mean()), 2)

        # 涨停/跌停（近似：涨跌幅 >= 9.5% / <= -9.5%）
        result["limit_up"] = int((pct >= 9.5).sum())
        result["limit_down"] = int((pct <= -9.5).sum())

        # 总成交额
        if "成交额" in df.columns:
            result["total_volume"] = round(float(df["成交额"].sum()) / 1e8, 0)

    except Exception as e:
        logger.warning(f"市场情绪数据获取失败: {e}")

    return result


# ══════════════════════════════════════════════════════════
#  下周展望 — 基于技术面的规则推断
# ══════════════════════════════════════════════════════════
def generate_outlook(indices: list[dict], breadth: dict) -> dict:
    """基于数据生成下周展望"""

    # 1. 综合判断大盘趋势
    bullish_score = 0
    bearish_score = 0
    details = []

    # 检查每个指数的 MA 排列
    for idx in indices:
        name = idx["name"]
        price = idx["latest"]
        ma5 = idx.get("ma5", 0)
        ma10 = idx.get("ma10", 0)
        ma20 = idx.get("ma20", 0)
        ma60 = idx.get("ma60", 0)

        # MA 多头排列
        if ma5 and ma20 and ma5 > ma20:
            details.append(f"{name} MA5↑MA20（短期多头）")
            bullish_score += 1
        elif ma5 and ma20 and ma5 < ma20:
            details.append(f"{name} MA5↓MA20（短期偏空）")
            bearish_score += 1

        # 价格 vs MA60（中长期趋势）
        if ma60 and price > ma60:
            bullish_score += 1
        elif ma60 and price < ma60:
            bearish_score += 2  # 中长期偏空权重更高
            details.append(f"{name} 低于 MA60（中长期偏弱）")

    # 2. 涨跌比判断
    total = breadth.get("up_count", 0) + breadth.get("down_count", 0) + breadth.get("flat_count", 0)
    if total > 0:
        up_ratio = breadth.get("up_count", 0) / total
        if up_ratio > 0.6:
            details.append(f"上涨家数占比 {up_ratio:.0%}（普涨，情绪偏暖）")
            bullish_score += 1
        elif up_ratio < 0.4:
            details.append(f"上涨家数占比 {up_ratio:.0%}（普跌，情绪偏冷）")
            bearish_score += 2

    # 3. 涨停跌停比
    limit_up = breadth.get("limit_up", 0)
    limit_down = breadth.get("limit_down", 0)
    if limit_down > limit_up * 2:
        details.append(f"跌停 {limit_down} 家 远超 涨停 {limit_up} 家（恐慌信号）")
        bearish_score += 2
    elif limit_up > limit_down * 2:
        details.append(f"涨停 {limit_up} 家 远超 跌停 {limit_down} 家（强势信号）")
        bullish_score += 1

    # 4. 综合结论
    net_score = bullish_score - bearish_score
    if net_score >= 3:
        outlook = "偏乐观"
        outlook_color = "#27ae60"
        suggestion = "下周初可适当积极，关注突破信号。仓位建议 6-7 成。"
    elif net_score >= 1:
        outlook = "中性偏多"
        outlook_color = "#2ecc71"
        suggestion = "震荡中寻找结构性机会，控制仓位在 5-6 成。关注强势板块龙头。"
    elif net_score >= -1:
        outlook = "中性偏谨慎"
        outlook_color = "#f39c12"
        suggestion = "市场方向不明，降低仓位至 3-5 成。等待明确信号再加仓。"
    elif net_score >= -3:
        outlook = "偏谨慎"
        outlook_color = "#e67e22"
        suggestion = "下行风险加大，仓位控制在 3 成以下。以防守为主，回避高估值。"
    else:
        outlook = "防御"
        outlook_color = "#e74c3c"
        suggestion = "市场偏弱，建议轻仓或空仓观望。保留现金等待更好的入场时机。"

    # 5. 支撑/压力位（用沪深300或上证指数）
    main_idx = next((i for i in indices if "上证" in i["name"]), None)
    support = None
    resistance = None
    if main_idx:
        support = main_idx.get("low", main_idx["latest"] * 0.97)
        resistance = main_idx.get("high", main_idx["latest"] * 1.03)

    return {
        "outlook": outlook,
        "outlook_color": outlook_color,
        "net_score": net_score,
        "suggestion": suggestion,
        "details": details,
        "support": round(support, 2) if support else None,
        "resistance": round(resistance, 2) if resistance else None,
    }


# ══════════════════════════════════════════════════════════
#  邮件报告
# ══════════════════════════════════════════════════════════
def send_weekly_report(
    indices: list[dict],
    top_sectors: list[dict],
    bottom_sectors: list[dict],
    breadth: dict,
    outlook: dict,
) -> bool:
    """生成并发送 HTML 周报"""
    try:
        from notification_service import notification_service

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        # 获取本周日期范围
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        friday = monday + timedelta(days=4)
        week_range = f"{monday.strftime('%m/%d')} - {friday.strftime('%m/%d')}"

        # ── 大盘指数表格 ──
        idx_rows = ""
        for idx in indices:
            chg = idx["week_change"]
            color = "#e74c3c" if chg < 0 else "#27ae60"
            sign = "+" if chg >= 0 else ""
            ma_info = ""
            if idx.get("ma20"):
                above_ma20 = "↑" if idx["latest"] > idx["ma20"] else "↓"
                ma_info = f'<span style="font-size:11px;color:#888;">MA20 {idx["ma20"]:.0f} {above_ma20}</span>'
            idx_rows += f"""
            <tr>
                <td style="padding:6px 10px;font-weight:bold;">{idx['name']}</td>
                <td style="padding:6px 10px;">{idx['latest']:.2f}</td>
                <td style="padding:6px 10px;color:{color};font-weight:bold;">{sign}{chg:.2f}%</td>
                <td style="padding:6px 10px;font-size:12px;">高 {idx['high']:.2f} / 低 {idx['low']:.2f}</td>
                <td style="padding:6px 10px;font-size:12px;">{idx.get('amount',0):.0f}亿</td>
                <td style="padding:6px 10px;">{ma_info}</td>
            </tr>"""

        # ── 板块排名 ──
        sector_top_rows = ""
        for i, s in enumerate(top_sectors, 1):
            chg = s["week_pct"]
            color = "#e74c3c" if chg < 0 else "#27ae60"
            sign = "+" if chg >= 0 else ""
            sector_top_rows += f"""
            <tr>
                <td style="padding:4px 8px;text-align:center;">{i}</td>
                <td style="padding:4px 8px;">{s['name']}</td>
                <td style="padding:4px 8px;color:{color};font-weight:bold;">{sign}{chg:.2f}%</td>
            </tr>"""

        sector_bot_rows = ""
        for i, s in enumerate(bottom_sectors, 1):
            chg = s["week_pct"]
            sector_bot_rows += f"""
            <tr>
                <td style="padding:4px 8px;text-align:center;">{i}</td>
                <td style="padding:4px 8px;">{s['name']}</td>
                <td style="padding:4px 8px;color:#e74c3c;font-weight:bold;">{chg:+.2f}%</td>
            </tr>"""

        # ── 情绪指标 ──
        total_stocks = breadth["up_count"] + breadth["down_count"] + breadth["flat_count"]
        up_ratio = breadth["up_count"] / total_stocks * 100 if total_stocks > 0 else 0
        vol_str = f"{breadth['total_volume']:.0f}亿" if breadth["total_volume"] else "N/A"

        # ── 展望详情 ──
        outlook_details = ""
        for d in outlook["details"]:
            outlook_details += f"<li>{d}</li>"

        support_str = f"{outlook['support']:.0f}" if outlook["support"] else "-"
        resistance_str = f"{outlook['resistance']:.0f}" if outlook["resistance"] else "-"

        html = f"""
<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:'Microsoft YaHei',Arial,sans-serif;padding:0;margin:0;background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);">

<div style="max-width:680px;margin:0 auto;background:rgba(255,255,255,0.06);border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.3);border:1px solid rgba(255,255,255,0.1);">

<!-- Header -->
<div style="background:linear-gradient(135deg,rgba(102,126,234,0.3),rgba(118,75,162,0.3));color:#fff;padding:24px;text-align:center;">
    <h1 style="margin:0;font-size:22px;">📊 A股周度市场总结</h1>
    <p style="margin:8px 0 0;opacity:0.8;">{week_range} | 报告生成: {now_str}</p>
</div>

<!-- 大盘指数 -->
<div style="padding:18px 24px;border-bottom:1px solid rgba(255,255,255,0.08);">
    <h3 style="margin:0 0 12px;font-size:15px;color:#ffffff;">📈 大盘指数周度回顾</h3>
    <table style="width:100%;border-collapse:collapse;font-size:13px;color:#e0e0e0;">
        <tr style="background:rgba(255,255,255,0.06);">
            <th style="padding:6px 10px;text-align:left;">指数</th>
            <th style="padding:6px 10px;text-align:left;">收盘</th>
            <th style="padding:6px 10px;text-align:left;">周涨跌</th>
            <th style="padding:6px 10px;text-align:left;">周高低</th>
            <th style="padding:6px 10px;text-align:left;">成交额</th>
            <th style="padding:6px 10px;text-align:left;">均线</th>
        </tr>
        {idx_rows if idx_rows else '<tr><td colspan="6" style="color:rgba(255,255,255,0.4);">数据暂不可用</td></tr>'}
    </table>
</div>

<!-- 市场情绪 -->
<div style="padding:18px 24px;border-bottom:1px solid rgba(255,255,255,0.08);">
    <h3 style="margin:0 0 12px;font-size:15px;color:#ffffff;">📉 市场情绪指标</h3>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <tr>
            <td style="padding:8px 12px;background:rgba(39,174,96,0.1);border-radius:8px;width:22%;text-align:center;">
                <strong style="color:#ffffff;">上涨</strong><br><span style="font-size:18px;color:#27ae60;">{breadth['up_count']}</span> <span style="color:rgba(255,255,255,0.6);">家</span>
            </td>
            <td style="padding:8px 12px;background:rgba(231,76,60,0.1);border-radius:8px;width:22%;text-align:center;">
                <strong style="color:#ffffff;">下跌</strong><br><span style="font-size:18px;color:#e74c3c;">{breadth['down_count']}</span> <span style="color:rgba(255,255,255,0.6);">家</span>
            </td>
            <td style="padding:8px 12px;background:rgba(243,156,18,0.1);border-radius:8px;width:22%;text-align:center;">
                <strong style="color:#ffffff;">涨停</strong><br><span style="font-size:18px;color:#f39c12;">{breadth['limit_up']}</span> <span style="color:rgba(255,255,255,0.6);">家</span>
            </td>
            <td style="padding:8px 12px;background:rgba(192,57,43,0.1);border-radius:8px;width:22%;text-align:center;">
                <strong style="color:#ffffff;">跌停</strong><br><span style="font-size:18px;color:#c0392b;">{breadth['limit_down']}</span> <span style="color:rgba(255,255,255,0.6);">家</span>
            </td>
        </tr>
    </table>
    <p style="margin:6px 0 0;font-size:12px;color:rgba(255,255,255,0.4);">
        上涨占比: {up_ratio:.1f}% | 平均涨跌: {breadth['avg_change']:+.2f}% | 总成交: {vol_str}
    </p>
</div>

<!-- 板块排名 -->
<div style="padding:18px 24px;border-bottom:1px solid rgba(255,255,255,0.08);">
    <table style="width:100%;"><tr>
    <td style="width:50%;vertical-align:top;padding-right:12px;">
        <h3 style="margin:0 0 10px;font-size:15px;color:#27ae60;">🔥 周涨幅 TOP{len(top_sectors)}</h3>
        <table style="width:100%;border-collapse:collapse;font-size:12px;color:#e0e0e0;">
            <tr style="background:rgba(255,255,255,0.06);"><th style="padding:4px 8px;">#</th><th style="padding:4px 8px;">板块</th><th style="padding:4px 8px;">涨跌</th></tr>
            {sector_top_rows if sector_top_rows else '<tr><td colspan="3" style="color:rgba(255,255,255,0.4);">数据暂不可用</td></tr>'}
        </table>
    </td>
    <td style="width:50%;vertical-align:top;padding-left:12px;">
        <h3 style="margin:0 0 10px;font-size:15px;color:#e74c3c;">📉 周跌幅 TOP{len(bottom_sectors)}</h3>
        <table style="width:100%;border-collapse:collapse;font-size:12px;color:#e0e0e0;">
            <tr style="background:rgba(255,255,255,0.06);"><th style="padding:4px 8px;">#</th><th style="padding:4px 8px;">板块</th><th style="padding:4px 8px;">涨跌</th></tr>
            {sector_bot_rows if sector_bot_rows else '<tr><td colspan="3" style="color:rgba(255,255,255,0.4);">数据暂不可用</td></tr>'}
        </table>
    </td>
    </tr></table>
</div>

<!-- 下周展望 -->
<div style="padding:18px 24px;border-bottom:1px solid rgba(255,255,255,0.08);">
    <h3 style="margin:0 0 12px;font-size:15px;color:#ffffff;">🎯 下周展望</h3>

    <div style="text-align:center;padding:16px;background:rgba(255,255,255,0.04);border-radius:12px;margin-bottom:12px;border:1px solid rgba(255,255,255,0.08);">
        <div style="font-size:14px;color:rgba(255,255,255,0.6);">综合评分: <span style="font-weight:bold;font-size:20px;color:{outlook['outlook_color']};">{outlook['net_score']:+d}</span></div>
        <div style="font-size:24px;font-weight:bold;color:{outlook['outlook_color']};margin:8px 0;">{outlook['outlook']}</div>
        <div style="font-size:13px;color:rgba(255,255,255,0.5);">上证支撑 {support_str} — 压力 {resistance_str}</div>
    </div>

    <div style="background:rgba(255,255,255,0.04);padding:14px 16px;border-radius:8px;border-left:4px solid {outlook['outlook_color']};margin-bottom:12px;color:#e0e0e0;">
        <strong>💡 操作建议：</strong>{outlook['suggestion']}
    </div>

    <h4 style="margin:12px 0 6px;font-size:13px;color:rgba(255,255,255,0.7);">📋 判断依据</h4>
    <ul style="margin:0;padding-left:20px;font-size:12px;color:rgba(255,255,255,0.6);line-height:1.8;">
        {outlook_details}
    </ul>
</div>

<!-- Footer -->
<div style="background:rgba(255,255,255,0.04);padding:12px 24px;text-align:center;font-size:11px;color:rgba(255,255,255,0.35);">
    ⚠ 本周报由 AI 量化系统自动生成，仅供参考，不构成投资建议。<br>
    市场有风险，投资需谨慎。报告基于技术面规则推断，不代表未来走势。
</div>

</div></body></html>
"""

        subject = f"📊 A股周报 {week_range} — {outlook['outlook']}"

        success = notification_service._send_custom_email(
            subject=subject,
            html_body=html,
            text_body=f"A股周报 {week_range}\n综合评分: {outlook['net_score']:+d} — {outlook['outlook']}\n建议: {outlook['suggestion']}",
        )
        return success

    except Exception as e:
        logger.error(f"发送周报失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ══════════════════════════════════════════════════════════
#  生成报告
# ══════════════════════════════════════════════════════════
def generate_report() -> bool:
    """执行完整报告生成流程"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("=" * 50)
    logger.info(f"📊 开始生成周度市场报告 {now_str}")
    logger.info("=" * 50)

    # 1. 指数
    logger.info("[1/3] 获取大盘指数...")
    indices = fetch_index_weekly()
    for idx in indices:
        logger.info(f"  {idx['name']}: {idx['latest']:.2f} ({idx['week_change']:+.2f}%)")

    # 2. 板块
    logger.info("[2/3] 获取板块排名...")
    top_sectors, bottom_sectors = fetch_sector_rankings()
    logger.info(f"  TOP5: {', '.join(s['name'] for s in top_sectors[:5])}")

    # 3. 情绪
    logger.info("[3/3] 获取市场情绪...")
    breadth = fetch_market_breadth()
    logger.info(f"  涨{breadth['up_count']} / 跌{breadth['down_count']} / 涨停{breadth['limit_up']} / 跌停{breadth['limit_down']}")

    # 4. 展望
    outlook = generate_outlook(indices, breadth)
    logger.info(f"  综合评分: {outlook['net_score']:+d} — {outlook['outlook']}")
    logger.info(f"  建议: {outlook['suggestion']}")

    # 5. 发送
    logger.info("📧 发送周报邮件...")
    success = send_weekly_report(indices, top_sectors, bottom_sectors, breadth, outlook)
    if success:
        logger.info("✅ 周报发送成功")
    else:
        logger.error("❌ 周报发送失败")

    return success


# ══════════════════════════════════════════════════════════
#  调度循环
# ══════════════════════════════════════════════════════════
def main_loop():
    """主循环：每周六 10:00 执行"""
    logger.info("=" * 60)
    logger.info("  📊 A股周度市场报告系统 启动")
    logger.info(f"  执行时间: 每周六 {Config.RUN_HOUR:02d}:{Config.RUN_MINUTE:02d}")
    logger.info(f"  报告内容: 大盘 + 板块 + 情绪 + 下周展望")
    logger.info("=" * 60)

    has_run_this_week = False

    while True:
        try:
            now = datetime.now()

            if is_schedule_time() and not has_run_this_week:
                logger.info(f"⏰ 到达周报时间: {now.strftime('%Y-%m-%d %H:%M')}")
                try:
                    generate_report()
                except Exception as e:
                    logger.error(f"生成周报异常: {e}")
                has_run_this_week = True
                time.sleep(120)
            elif not is_saturday():
                has_run_this_week = False
                next_sat = now + timedelta(days=(5 - now.weekday()) % 7)
                if next_sat <= now:
                    next_sat += timedelta(days=7)
                logger.info(f"⏸ 非周六，下次报告: {next_sat.strftime('%m/%d %H:%M')}")
                time.sleep(3600)
            else:
                time.sleep(60)

        except KeyboardInterrupt:
            logger.info("\n⏹ 用户中断")
            break
        except Exception as e:
            logger.error(f"主循环异常: {e}")
            time.sleep(300)


# ══════════════════════════════════════════════════════════
#  安装为 Windows 计划任务
# ══════════════════════════════════════════════════════════
def install_task():
    import subprocess
    python_path = sys.executable
    script_path = Path(__file__).resolve()

    cmds = [
        'schtasks /Delete /TN "AI_WeeklyReport" /F',
        f'schtasks /Create /TN "AI_WeeklyReport" /TR "\\"{python_path}\\" \\"{script_path}\\"" /SC WEEKLY /D SAT /ST 10:00 /RL HIGHEST /F',
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(result.stdout.strip() or result.stderr.strip())

    print("\nTask 'AI_WeeklyReport' installed.")
    print("Runs every Saturday at 10:00 AM.")
    print(f"Log: {LOG_FILE}")


# ══════════════════════════════════════════════════════════
#  入口
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A股周度市场总结与下周展望")
    parser.add_argument("--once", action="store_true", help="立即生成一次")
    parser.add_argument("--install", action="store_true", help="安装为 Windows 计划任务（每周六 10:00）")
    args = parser.parse_args()

    if args.install:
        install_task()
        sys.exit(0)

    if args.once:
        logger.info("🔍 立即生成周报...")
        generate_report()
        sys.exit(0)

    main_loop()
