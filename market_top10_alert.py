#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全A股市场 TOP10 智能选股推送系统
======================================
功能：
  1. 每日 9:35（开盘后）和 14:30（收盘前）各扫描一次全 A 股
  2. 基于 7 因子模型（动量/价值/质量/成长/流动性/波动/资金流）打分排名
  3. 附带大盘指数快照 + 热门 ETF 推荐
  4. 通过 QQ 邮箱推送 HTML 精美报告
  5. 仅交易日运行，非交易日自动休眠

使用方法：
  python market_top10_alert.py             # 持续运行（定时扫描）
  python market_top10_alert.py --once      # 立即扫描一次
  python market_top10_alert.py --install   # 安装为 Windows 计划任务

依赖：
  - 复用 quant_stock_scanner.py 的 MultiFactorStockSelector
  - 复用 notification_service.py 的邮件发送
  - AKShare / 新浪 API（免费）
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

# ── 项目根目录 ────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── 日志 ─────────────────────────────────────────────
LOG_FILE = PROJECT_ROOT / "market_top10_alert.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("Top10_Alert")

# ── 状态文件 ─────────────────────────────────────────
STATE_FILE = PROJECT_ROOT / ".top10_scan_state.json"

# ══════════════════════════════════════════════════════════
#  Config
# ══════════════════════════════════════════════════════════
class Config:
    TOP_N = 10
    ETF_TOP_N = 5

    # 扫描时间点
    SCAN_TIMES = ["09:35", "14:30"]

    # 交易时段（用于判断是否在交易日内）
    TRADING_SESSIONS = [
        (dtime(9, 30), dtime(11, 30)),
        (dtime(13, 0), dtime(15, 0)),
    ]

    # 大盘指数
    INDICES = {
        "sh000001": "上证指数",
        "sz399001": "深证成指",
        "sz399006": "创业板指",
        "sh000688": "科创50",
    }


def is_trading_day() -> bool:
    return datetime.now().weekday() < 5


def is_trading_time() -> bool:
    if not is_trading_day():
        return False
    now = dtime(datetime.now().hour, datetime.now().minute)
    for start, end in Config.TRADING_SESSIONS:
        if start <= now <= end:
            return True
    return False


# ══════════════════════════════════════════════════════════
#  大盘指数快照
# ══════════════════════════════════════════════════════════
def fetch_index_snapshot() -> list[dict]:
    """获取主要指数实时行情（新浪API，免费）"""
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
            if len(data) < 4:
                continue

            name = Config.INDICES.get(sym, sym)
            latest = float(data[3]) if data[3] else 0
            prev_close = float(data[2]) if data[2] else 1
            change_pct = (latest - prev_close) / prev_close * 100 if prev_close > 0 else 0

            results.append({
                "name": name,
                "latest": round(latest, 2),
                "change_pct": round(change_pct, 2),
                "high": round(float(data[4]), 2) if len(data) > 4 and data[4] else 0,
                "low": round(float(data[5]), 2) if len(data) > 5 and data[5] else 0,
                "amount": round(float(data[9]) / 1e8, 1) if len(data) > 9 and data[9] else 0,
            })
    except Exception as e:
        logger.warning(f"指数数据获取失败: {e}")

    return results


# ══════════════════════════════════════════════════════════
#  ETF 热门推荐
# ══════════════════════════════════════════════════════════
def fetch_top_etfs(top_n: int = 5) -> list[dict]:
    """获取热门 ETF（按成交额排序）"""
    try:
        import akshare as ak
        df = ak.fund_etf_spot_em()
        if df is None or df.empty:
            return []

        # 按成交额排序，取TOP
        df = df.sort_values("成交额", ascending=False)
        results = []
        for _, row in df.head(top_n * 3).iterrows():
            code = str(row.get("代码", ""))
            name = str(row.get("名称", ""))
            price = float(row.get("最新价", 0))
            change_pct = float(row.get("涨跌幅", 0)) if row.get("涨跌幅") else 0
            amount = float(row.get("成交额", 0))
            if price <= 0 or amount <= 0:
                continue
            results.append({
                "code": code,
                "name": name,
                "price": round(price, 3),
                "change_pct": round(change_pct, 2),
                "amount": round(amount / 1e8, 2),
            })
            if len(results) >= top_n:
                break
        return results
    except Exception as e:
        logger.warning(f"ETF数据获取失败: {e}")
        return []


# ══════════════════════════════════════════════════════════
#  风控过滤器：排除退市风险 + A杀风险股票
# ══════════════════════════════════════════════════════════
class RiskFilter:
    """风控过滤器 — 剔除高风险股票"""

    # ── 硬过滤（一项触发即排除）──
    MIN_PRICE = 3.0            # 最低股价（面值退市风险）
    MIN_MARKET_CAP = 30        # 最低总市值（亿）
    MAX_TURNOVER = 15.0        # 最高换手率（%）
    MAX_D60_RETURN = 80.0      # 60日最高涨幅（%）
    MAX_AMPLITUDE = 12.0       # 当日最高振幅（%）
    MAX_PE = 200               # PE 上限

    # ── 黑名单关键词 ──
    NAME_BLACKLIST = ["ST", "退", "*ST"]

    @classmethod
    def filter(cls, candidates: list[dict]) -> tuple[list[dict], list[dict]]:
        """
        过滤高风险股票
        返回: (通过列表, 被拒列表)
        """
        passed = []
        rejected = []

        # 获取补充数据（市值、振幅等）
        extra_data = cls._fetch_extra_data([s["code"] for s in candidates])

        for s in candidates:
            code = s.get("code", "")
            name = s.get("name", "")
            price = s.get("price", 0)
            extra = extra_data.get(code, {})

            reasons = []

            # 1. 黑名单关键词
            for kw in cls.NAME_BLACKLIST:
                if kw in name:
                    reasons.append(f"名称含「{kw}」")
                    break

            # 2. 股价过低（面值退市风险）
            if price < cls.MIN_PRICE:
                reasons.append(f"股价 ¥{price:.2f} < ¥{cls.MIN_PRICE}（面值退市风险）")

            # 3. 亏损股（PE 为负）
            pe = s.get("pe", 0)
            if pe and pe < 0:
                reasons.append(f"PE={pe:.1f}（亏损股，可能 ST）")

            # 4. PE 过高
            if pe and pe > cls.MAX_PE:
                reasons.append(f"PE={pe:.1f} > {cls.MAX_PE}（估值异常）")

            # 5. 市值过小
            mkt_cap = extra.get("market_cap", 0)
            if 0 < mkt_cap < cls.MIN_MARKET_CAP:
                reasons.append(f"总市值 {mkt_cap:.1f}亿 < {cls.MIN_MARKET_CAP}亿")

            # 6. 换手率异常
            turnover = s.get("turnover", 0)
            if turnover > cls.MAX_TURNOVER:
                reasons.append(f"换手率 {turnover:.1f}% > {cls.MAX_TURNOVER}%（庄股/游资炒作）")

            # 7. 短期暴涨（A杀前兆）
            d60 = s.get("d60_return", 0)
            if d60 > cls.MAX_D60_RETURN:
                reasons.append(f"60日涨幅 {d60:.1f}% > {cls.MAX_D60_RETURN}%（A杀风险）")

            # 8. 当日振幅过大
            amp = extra.get("amplitude", 0)
            if amp > cls.MAX_AMPLITUDE:
                reasons.append(f"振幅 {amp:.1f}% > {cls.MAX_AMPLITUDE}%（异常波动）")

            if reasons:
                rejected.append({**s, "reject_reasons": reasons})
            else:
                # 附加市值、振幅到通过股票
                passed.append({**s, "market_cap": mkt_cap, "amplitude": amp})

        return passed, rejected

    @classmethod
    def _fetch_extra_data(cls, codes: list[str]) -> dict:
        """获取补充风控数据（市值、振幅）"""
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                return {}

            # 构建代码→数据映射
            lookup = {}
            for _, row in df.iterrows():
                code = str(row.get("代码", ""))
                if code not in codes:
                    continue
                mkt_cap = float(row.get("总市值", 0)) / 1e8 if row.get("总市值") else 0
                amp = float(row.get("振幅", 0)) if row.get("振幅") else 0
                lookup[code] = {
                    "market_cap": round(mkt_cap, 1),
                    "amplitude": round(amp, 1),
                }

            # 补充：对未获取到的代码重试
            for code in codes:
                if code not in lookup:
                    lookup[code] = {"market_cap": 0, "amplitude": 0}

            return lookup
        except Exception as e:
            logger.warning(f"风控数据获取失败: {e}")
            return {c: {"market_cap": 0, "amplitude": 0} for c in codes}


# ══════════════════════════════════════════════════════════
#  股票扫描（复用现有引擎 + 风控过滤）
# ══════════════════════════════════════════════════════════
def fetch_top_stocks(top_n: int = 10) -> list[dict]:
    """使用 MultiFactorStockSelector 扫描全A股，经风控过滤后返回 TOP N"""
    try:
        from quant_stock_scanner import MultiFactorStockSelector
        selector = MultiFactorStockSelector()

        # 先取 3 倍数量，留足过滤余量
        fetch_n = min(top_n * 3, 50)
        candidates = selector.get_top_stocks(top_n=fetch_n)
        logger.info(f"扫描完成，候选 {len(candidates)} 只")

        if not candidates:
            return []

        # 风控过滤
        passed, rejected = RiskFilter.filter(candidates)

        if rejected:
            logger.info(f"风控过滤：排除 {len(rejected)} 只高风险股票")
            for r in rejected:
                logger.info(f"  ❌ {r['code']} {r['name']} — {', '.join(r['reject_reasons'])}")

        if passed:
            logger.info(f"风控过滤：通过 {len(passed)} 只，取 TOP{top_n}")
        else:
            logger.warning("风控过滤后无股票通过，降级返回原始候选")

        return passed[:top_n]

    except Exception as e:
        logger.error(f"股票扫描失败: {e}")
        import traceback
        traceback.print_exc()
        return []


# ══════════════════════════════════════════════════════════
#  邮件报告
# ══════════════════════════════════════════════════════════
def send_report(stocks: list[dict], indices: list[dict], etfs: list[dict],
                filter_stats: dict = None) -> bool:
    """生成并发送 HTML 邮件报告"""
    try:
        from notification_service import notification_service

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        is_am = datetime.now().hour < 12
        session_label = "早盘扫描" if is_am else "午后扫描"

        # ── 风控统计 ──
        filter_html = ""
        if filter_stats:
            scanned = filter_stats.get("scanned", 0)
            passed_n = filter_stats.get("passed", 0)
            rejected_n = filter_stats.get("rejected", 0)
            filter_html = f"""
            <div style="margin:8px 0;font-size:12px;color:#666;">
                🛡 风控过滤：扫描 {scanned} 只 → 通过 {passed_n} 只 → 排除 {rejected_n} 只
            </div>"""

        # ── 大盘指数行 ──
        index_rows = ""
        for idx in indices:
            color = "#e74c3c" if idx["change_pct"] < 0 else "#27ae60"
            sign = "+" if idx["change_pct"] >= 0 else ""
            index_rows += f"""
            <tr>
                <td style="padding:4px 8px;">{idx['name']}</td>
                <td style="padding:4px 8px;font-weight:bold;">{idx['latest']:.2f}</td>
                <td style="padding:4px 8px;color:{color};">{sign}{idx['change_pct']:.2f}%</td>
                <td style="padding:4px 8px;font-size:12px;color:#999;">成交 {idx.get('amount',0)}亿</td>
            </tr>"""

        # ── ETF 推荐行 ──
        etf_rows = ""
        if etfs:
            for i, etf in enumerate(etfs, 1):
                color = "#e74c3c" if etf["change_pct"] < 0 else "#27ae60"
                sign = "+" if etf["change_pct"] >= 0 else ""
                etf_rows += f"""
                <tr>
                    <td style="padding:4px 8px;">{i}</td>
                    <td style="padding:4px 8px;">{etf['code']}</td>
                    <td style="padding:4px 8px;">{etf['name']}</td>
                    <td style="padding:4px 8px;">{etf['price']:.3f}</td>
                    <td style="padding:4px 8px;color:{color};">{sign}{etf['change_pct']:.2f}%</td>
                    <td style="padding:4px 8px;">{etf['amount']:.1f}亿</td>
                </tr>"""
        else:
            etf_rows = '<tr><td colspan="6" style="padding:8px;color:#999;text-align:center;">ETF 数据暂不可用</td></tr>'

        # ── 股票 TOP10 行 ──
        stock_rows = ""
        for i, s in enumerate(stocks, 1):
            cp = s.get("change_pct", 0)
            color = "#e74c3c" if cp < 0 else "#27ae60"
            sign = "+" if cp >= 0 else ""
            pe = s.get("pe", 0)
            pe_str = f"{pe:.1f}" if pe and pe > 0 else "-"
            pb = s.get("pb", 0)
            pb_str = f"{pb:.2f}" if pb and pb > 0 else "-"
            score = s.get("total_score", 0)
            mkt_cap = s.get("market_cap", 0)
            mkt_str = f"{mkt_cap:.0f}亿" if mkt_cap > 0 else "-"

            # 得分颜色
            if score >= 80:
                sc_color = "#27ae60"
            elif score >= 60:
                sc_color = "#f39c12"
            else:
                sc_color = "#e74c3c"

            stock_rows += f"""
            <tr>
                <td style="padding:6px 8px;font-weight:bold;text-align:center;">{i}</td>
                <td style="padding:6px 8px;">{s.get('code','')}</td>
                <td style="padding:6px 8px;font-weight:bold;">{s.get('name','')}</td>
                <td style="padding:6px 8px;">{s.get('price',0):.2f}</td>
                <td style="padding:6px 8px;color:{color};">{sign}{cp:.2f}%</td>
                <td style="padding:6px 8px;">{pe_str}</td>
                <td style="padding:6px 8px;">{pb_str}</td>
                <td style="padding:6px 8px;font-size:12px;">{mkt_str}</td>
                <td style="padding:6px 8px;font-weight:bold;color:{sc_color};">{score:.1f}</td>
            </tr>"""

        # ── 因子得分详情 ──
        factor_rows = ""
        for s in stocks:
            factor_rows += f"""
            <tr>
                <td style="padding:3px 6px;font-size:12px;">{s.get('code','')}</td>
                <td style="padding:3px 6px;font-size:12px;">{s.get('name','')[:4]}</td>
                <td style="padding:3px 6px;font-size:12px;">{s.get('momentum_score',0):.0f}</td>
                <td style="padding:3px 6px;font-size:12px;">{s.get('value_score',0):.0f}</td>
                <td style="padding:3px 6px;font-size:12px;">{s.get('quality_score',0):.0f}</td>
                <td style="padding:3px 6px;font-size:12px;">{s.get('growth_score',0):.0f}</td>
                <td style="padding:3px 6px;font-size:12px;">{s.get('liquidity_score',0):.0f}</td>
                <td style="padding:3px 6px;font-size:12px;">{s.get('volatility_score',0):.0f}</td>
                <td style="padding:3px 6px;font-size:12px;">{s.get('fund_flow_score',0):.0f}</td>
            </tr>"""

        html = f"""
<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:'Microsoft YaHei',Arial,sans-serif;padding:0;margin:0;background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);">

<div style="max-width:680px;margin:0 auto;background:rgba(255,255,255,0.06);border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.3);border:1px solid rgba(255,255,255,0.1);">

<!-- Header -->
<div style="background:linear-gradient(135deg,rgba(102,126,234,0.3),rgba(118,75,162,0.3));color:#fff;padding:20px 24px;text-align:center;">
    <h1 style="margin:0;font-size:20px;">📊 AI 量化选股 TOP{Config.TOP_N}</h1>
    <p style="margin:6px 0 0;opacity:0.8;font-size:13px;">{session_label} | {now_str}</p>
</div>

<!-- 大盘指数 -->
<div style="padding:16px 24px;border-bottom:1px solid rgba(255,255,255,0.08);">
    <h3 style="margin:0 0 10px;font-size:14px;color:#ffffff;">📈 大盘指数</h3>
    <table style="width:100%;border-collapse:collapse;font-size:13px;color:#e0e0e0;">
        {index_rows if index_rows else '<tr><td colspan="4" style="color:rgba(255,255,255,0.4);">数据暂不可用</td></tr>'}
    </table>
</div>

<!-- ETF 推荐 -->
<div style="padding:16px 24px;border-bottom:1px solid rgba(255,255,255,0.08);">
    <h3 style="margin:0 0 10px;font-size:14px;color:#ffffff;">🔥 热门 ETF TOP{Config.ETF_TOP_N}（按成交额）</h3>
    <table style="width:100%;border-collapse:collapse;font-size:12px;color:#e0e0e0;">
        <tr style="background:rgba(255,255,255,0.06);">
            <th style="padding:4px 8px;text-align:left;">#</th>
            <th style="padding:4px 8px;text-align:left;">代码</th>
            <th style="padding:4px 8px;text-align:left;">名称</th>
            <th style="padding:4px 8px;text-align:left;">价格</th>
            <th style="padding:4px 8px;text-align:left;">涨跌</th>
            <th style="padding:4px 8px;text-align:left;">成交额</th>
        </tr>
        {etf_rows}
    </table>
</div>

<!-- TOP10 股票 -->
<div style="padding:16px 24px;border-bottom:1px solid rgba(255,255,255,0.08);">
    <h3 style="margin:0 0 10px;font-size:14px;color:#ffffff;">🏆 多因子选股 TOP{len(stocks)}</h3>
    {filter_html}
    <table style="width:100%;border-collapse:collapse;font-size:13px;color:#e0e0e0;">
        <tr style="background:rgba(255,255,255,0.06);">
            <th style="padding:6px 8px;">#</th><th style="padding:6px 8px;">代码</th><th style="padding:6px 8px;">名称</th>
            <th style="padding:6px 8px;">现价</th><th style="padding:6px 8px;">涨跌</th>
            <th style="padding:6px 8px;">PE</th><th style="padding:6px 8px;">PB</th><th style="padding:6px 8px;">市值</th><th style="padding:6px 8px;">得分</th>
        </tr>
        {stock_rows}
    </table>
</div>

<!-- 因子详情 -->
<div style="padding:16px 24px;border-bottom:1px solid rgba(255,255,255,0.08);">
    <h3 style="margin:0 0 10px;font-size:14px;color:#ffffff;">📐 因子得分明细</h3>
    <table style="width:100%;border-collapse:collapse;font-size:11px;color:#e0e0e0;">
        <tr style="background:rgba(255,255,255,0.06);">
            <th style="padding:3px 6px;">代码</th><th style="padding:3px 6px;">名称</th>
            <th style="padding:3px 6px;">动量</th><th style="padding:3px 6px;">价值</th><th style="padding:3px 6px;">质量</th>
            <th style="padding:3px 6px;">成长</th><th style="padding:3px 6px;">流动</th><th style="padding:3px 6px;">波动</th>
            <th style="padding:3px 6px;">资金</th>
        </tr>
        {factor_rows}
    </table>
    <p style="margin:8px 0 0;font-size:11px;color:rgba(255,255,255,0.4);">
        因子权重：动量15% | 价值20% | 质量20% | 成长15% | 流动性10% | 波动10% | 资金流10%
    </p>
</div>

<!-- Footer -->
<div style="background:rgba(255,255,255,0.04);padding:12px 24px;text-align:center;font-size:11px;color:rgba(255,255,255,0.35);">
    ⚠ 本报告由 AI 量化系统自动生成，仅供参考，不构成投资建议。<br>
    投资有风险，入市需谨慎。
</div>

</div></body></html>
"""

        subject = f"📊 AI量化选股 TOP{len(stocks)} - {session_label} {now_str}"

        success = notification_service._send_custom_email(
            subject=subject,
            html_body=html,
            text_body=f"AI量化选股 TOP{len(stocks)}\n扫描时间: {now_str}\n\n"
                      f"TOP{len(stocks)}:\n" +
                      "\n".join(f"{i}. {s['code']} {s['name']} ¥{s['price']:.2f} {s['change_pct']:+.2f}% 得分{s['total_score']:.1f}"
                                for i, s in enumerate(stocks, 1)),
        )
        return success
    except Exception as e:
        logger.error(f"发送报告失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ══════════════════════════════════════════════════════════
#  单次扫描
# ══════════════════════════════════════════════════════════
def run_scan() -> bool:
    """执行一次完整扫描并发送报告"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("=" * 50)
    logger.info(f"🔍 开始全市场扫描 {now_str}")
    logger.info("=" * 50)

    # 1. 大盘指数
    logger.info("[1/3] 获取大盘指数...")
    indices = fetch_index_snapshot()
    for idx in indices:
        logger.info(f"  {idx['name']}: {idx['latest']:.2f} ({idx['change_pct']:+.2f}%)")

    # 2. ETF
    logger.info("[2/3] 获取热门 ETF...")
    etfs = fetch_top_etfs(Config.ETF_TOP_N)
    logger.info(f"  获取 {len(etfs)} 只 ETF")

    # 3. 股票扫描
    logger.info("[3/3] 多因子扫描全A股（约需30-60秒）...")
    stocks = fetch_top_stocks(Config.TOP_N)

    if not stocks:
        logger.error("❌ 股票扫描为空，跳过发送")
        return False

    for i, s in enumerate(stocks, 1):
        logger.info(f"  {i}. {s['code']} {s['name']} ¥{s['price']:.2f} 得分{s['total_score']:.1f}")

    # 4. 发送
    logger.info("📧 发送邮件报告...")
    filter_stats = {
        "scanned": min(Config.TOP_N * 3, 50),
        "passed": len(stocks),
        "rejected": min(Config.TOP_N * 3, 50) - len(stocks),
    }
    success = send_report(stocks, indices, etfs, filter_stats)
    if success:
        logger.info("✅ 报告发送成功")
        # 保存状态
        STATE_FILE.write_text(json.dumps({
            "last_scan": now_str,
            "top_codes": [s["code"] for s in stocks],
            "stock_count": len(stocks),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        logger.error("❌ 报告发送失败")

    return success


# ══════════════════════════════════════════════════════════
#  调度循环
# ══════════════════════════════════════════════════════════
def main_loop():
    """主循环：交易日在 9:35 和 14:30 各扫描一次"""
    logger.info("=" * 60)
    logger.info("  📊 AI 量化选股 TOP10 推送系统 启动")
    logger.info(f"  扫描时间: {', '.join(Config.SCAN_TIMES)}")
    logger.info(f"  选股模型: 7因子（动量/价值/质量/成长/流动/波动/资金）")
    logger.info(f"  通知邮箱: QQ邮箱")
    logger.info("=" * 60)

    today_scans = set()  # 今天已经执行过的扫描时间点

    while True:
        try:
            now = datetime.now()

            if not is_trading_day():
                # 非交易日
                logger.info("⏸ 非交易日，休眠中...")
                today_scans.clear()
                time.sleep(600)
                continue

            if not is_trading_time():
                # 交易日但不在交易时间
                now_t = dtime(now.hour, now.minute)
                for start, _ in Config.TRADING_SESSIONS:
                    if now_t < start:
                        wait = (datetime.combine(now.date(), start) - now).total_seconds()
                        wait = min(wait, 300)
                        time.sleep(max(wait, 30))
                        break
                else:
                    # 收盘后，重置今日扫描记录
                    if today_scans:
                        logger.info("🔚 今日交易结束，扫描记录已重置")
                    today_scans.clear()
                    time.sleep(300)
                continue

            # 交易时间内：检查是否到了扫描时间点
            now_str = now.strftime("%H:%M")
            for scan_time in Config.SCAN_TIMES:
                if now_str.startswith(scan_time[:5]) and scan_time not in today_scans:
                    logger.info(f"⏰ 到达扫描时间点: {scan_time}")
                    try:
                        run_scan()
                    except Exception as e:
                        logger.error(f"扫描异常: {e}")
                    today_scans.add(scan_time)
                    break

            time.sleep(30)  # 每30秒检查一次是否到扫描时间

        except KeyboardInterrupt:
            logger.info("\n⏹ 用户中断，系统退出")
            break
        except Exception as e:
            logger.error(f"主循环异常: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(60)


# ══════════════════════════════════════════════════════════
#  安装为 Windows 计划任务
# ══════════════════════════════════════════════════════════
def install_task():
    """安装为 Windows 计划任务（管理员运行）"""
    import subprocess

    python_path = sys.executable
    script_path = Path(__file__).resolve()

    cmds = [
        'schtasks /Delete /TN "AI_Top10_Scan" /F',
        f'schtasks /Create /TN "AI_Top10_Scan" /TR "\\"{python_path}\\" \\"{script_path}\\"" /SC ONLOGON /DELAY 0000:30 /RL HIGHEST /F',
        'schtasks /Run /TN "AI_Top10_Scan"',
    ]

    for cmd in cmds:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(result.stdout.strip() or result.stderr.strip())

    print()
    print("Task 'AI_Top10_Scan' installed.")
    print("It will auto-start on login and scan at 09:35 and 14:30 on trading days.")
    print(f"Log: {LOG_FILE}")


# ══════════════════════════════════════════════════════════
#  入口
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI量化选股 TOP10 推送系统")
    parser.add_argument("--once", action="store_true", help="立即扫描一次")
    parser.add_argument("--install", action="store_true", help="安装为 Windows 计划任务")
    args = parser.parse_args()

    if args.install:
        install_task()
        sys.exit(0)

    if args.once:
        logger.info("🔍 执行单次扫描...")
        run_scan()
        sys.exit(0)

    main_loop()
