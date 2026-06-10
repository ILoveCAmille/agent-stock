#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易日实时股票监控 - 买卖信号 + 邮件通知
功能：
  1. 交易日自动监控股票列表
  2. 使用综合量化引擎分析买卖信号
  3. 触发信号时发送邮件通知
  4. 支持自定义股票列表、策略风格、监控间隔

使用方法：
  python stock_signal_monitor.py                          # 使用默认配置
  python stock_signal_monitor.py --stocks 600519,000858   # 指定股票
  python stock_signal_monitor.py --preset aggressive      # 激进策略
  python stock_signal_monitor.py --interval 300           # 5分钟检查一次
  python stock_signal_monitor.py --test-email             # 测试邮件发送
"""

import os
import sys
import time
import json
import logging
import argparse
import smtplib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 导入项目模块（环境变量已在 config.py 中统一加载）
import config  # noqa: F401 - 确保环境变量已加载

from real_data_fetcher import RealDataFetcher
from comprehensive_quant_engine import ComprehensiveQuantEngine
from comprehensive_strategy import ComprehensiveStrategy

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('stock_monitor.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class EmailSender:
    """邮件发送器"""
    
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', '')
        self.smtp_port = int(os.getenv('SMTP_PORT', '465'))
        self.email_from = os.getenv('EMAIL_FROM', '')
        self.email_password = os.getenv('EMAIL_PASSWORD', '')
        self.email_to = os.getenv('EMAIL_TO', '')
        self.enabled = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
    
    def is_configured(self) -> bool:
        """检查邮件是否配置完整"""
        return all([self.smtp_server, self.email_from, self.email_password, self.email_to])
    
    def send(self, subject: str, html_body: str) -> bool:
        """发送邮件"""
        if not self.enabled or not self.is_configured():
            logger.warning("邮件未配置或未启用，跳过发送")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = subject
            
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15)
                server.starttls()
            
            server.login(self.email_from, self.email_password)
            server.send_message(msg)
            server.quit()
            logger.info(f"✅ 邮件发送成功: {subject}")
            return True
        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}")
            return False
    
    def send_test(self) -> bool:
        """发送测试邮件"""
        subject = "📧 股票监控系统 - 邮件测试"
        html = """
        <html><body>
        <h2 style="color:#28a745;">✅ 邮件配置成功！</h2>
        <p>这是来自<strong>AI股票实时监控系统</strong>的测试邮件。</p>
        <p>收到此邮件说明邮件通知功能已就绪，交易日将自动接收买卖信号通知。</p>
        <hr>
        <p style="color:#666;">发送时间: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
        </body></html>
        """
        return self.send(subject, html)


class StockSignalMonitor:
    """股票买卖信号实时监控器"""
    
    def __init__(self, stocks: List[str] = None, preset: str = 'balanced',
                 check_interval: int = 300, position_pct: float = 0.3):
        """
        初始化监控器
        
        Args:
            stocks: 要监控的股票代码列表
            preset: 策略预设 (aggressive/balanced/conservative)
            check_interval: 检查间隔秒数（默认300秒=5分钟）
            position_pct: 建议仓位比例
        """
        self.stocks = stocks or ['600519', '000858', '600036', '000001', '601318']
        self.preset = preset
        self.check_interval = check_interval
        self.position_pct = position_pct
        
        # 初始化组件
        self.fetcher = RealDataFetcher(cache_dir=".cache/stock_data")
        self.strategy = ComprehensiveStrategy(preset)
        self.params = self.strategy.params
        self.email = EmailSender()
        
        # 信号状态记录（避免重复通知）
        self.signal_state_file = ".signal_state.json"
        self.signal_state = self._load_signal_state()
        
        # 统计
        self.stats = {
            'total_checks': 0,
            'signals_sent': 0,
            'emails_sent': 0,
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _load_signal_state(self) -> Dict:
        """加载信号状态（避免重复通知）"""
        if os.path.exists(self.signal_state_file):
            try:
                with open(self.signal_state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_signal_state(self):
        """保存信号状态"""
        with open(self.signal_state_file, 'w', encoding='utf-8') as f:
            json.dump(self.signal_state, f, ensure_ascii=False, indent=2)
    
    def _should_notify(self, symbol: str, signal_type: str) -> bool:
        """
        判断是否应该发送通知（避免同一信号重复通知）
        同一天同一股票同一类型只通知一次
        """
        today = datetime.now().strftime('%Y-%m-%d')
        key = f"{symbol}_{signal_type}_{today}"
        
        if key in self.signal_state:
            return False
        
        self.signal_state[key] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self._save_signal_state()
        return True
    
    def is_trading_time(self) -> bool:
        """判断当前是否为交易时间"""
        now = datetime.now()
        
        # 周末不交易
        if now.weekday() >= 5:
            return False
        
        # 交易时间段: 9:30-11:30, 13:00-15:00
        current_time = now.hour * 100 + now.minute
        if (930 <= current_time <= 1130) or (1300 <= current_time <= 1500):
            return True
        
        return False
    
    def get_next_trading_time(self) -> str:
        """获取下一个交易时间"""
        now = datetime.now()
        
        if now.weekday() >= 5:
            # 周末，下周一
            days_ahead = 7 - now.weekday()
            next_day = now + timedelta(days=days_ahead)
            return next_day.strftime('%Y-%m-%d') + ' 09:30'
        
        current_time = now.hour * 100 + now.minute
        if current_time < 930:
            return now.strftime('%Y-%m-%d') + ' 09:30'
        elif 1130 < current_time < 1300:
            return now.strftime('%Y-%m-%d') + ' 13:00'
        elif current_time > 1500:
            # 下一个交易日
            if now.weekday() == 4:
                next_day = now + timedelta(days=3)
            else:
                next_day = now + timedelta(days=1)
            return next_day.strftime('%Y-%m-%d') + ' 09:30'
        
        return "已在交易时间内"
    
    def analyze_stock(self, symbol: str) -> Optional[Dict]:
        """
        分析单只股票，返回买卖信号
        
        Returns:
            分析结果字典或None:
            {
                'symbol': '600519',
                'name': '贵州茅台',
                'price': 1800.0,
                'change_pct': 1.5,
                'signal': 'BUY' / 'SELL' / 'HOLD',
                'signal_cn': '买入' / '卖出' / '持有',
                'reason': '综合评分62.3，技术面强势...',
                'scores': {'comprehensive': 62.3, 'technical': 65, ...},
                'details': {...}
            }
        """
        try:
            # 1. 获取K线数据
            df = self.fetcher.fetch_kline(symbol, 500)
            if df is None or len(df) < 50:
                logger.warning(f"{symbol} K线数据不足，跳过")
                return None
            
            # 2. 获取实时行情
            quote = self.fetcher.fetch_realtime(symbol)
            if quote is None:
                logger.warning(f"{symbol} 实时行情获取失败，跳过")
                return None
            
            current_price = quote.get('price', 0)
            if current_price <= 0:
                return None
            
            # 3. 计算量化因子
            avg_amount = df['Volume'].tail(20).mean() * df['Close'].tail(20).mean() / 10000
            cap_style = ComprehensiveQuantEngine.detect_cap_style(
                stock_code=symbol, avg_amount=avg_amount
            )
            engine = ComprehensiveQuantEngine(cap_style=cap_style)
            df = engine.compute_all_factors(df)
            df = engine.compute_comprehensive_score(df)
            
            # 4. 获取最新评分
            latest = df.iloc[-1]
            comp_score = latest.get('Score_Comprehensive', 50)
            tech_score = latest.get('Score_Technical', 50)
            fund_score = latest.get('Score_FundFlow', 50)
            sent_score = latest.get('Score_Sentiment', 50)
            macro_score = latest.get('Score_MacroCycle', 50)
            funda_score = latest.get('Score_Fundamental', 50)
            
            # 5. 判断信号
            signal = 'HOLD'
            signal_cn = '持有'
            reasons = []
            
            # 买入条件
            if (comp_score > self.params['buy_score_threshold'] and 
                tech_score > self.params['tech_min']):
                signal = 'BUY'
                signal_cn = '买入'
                reasons.append(f"综合评分{comp_score:.1f}>{self.params['buy_score_threshold']}")
                reasons.append(f"技术面{tech_score:.1f}>{self.params['tech_min']}")
                
                if fund_score > self.params.get('fund_min', 48):
                    reasons.append(f"资金流入({fund_score:.1f})")
            
            # 卖出条件
            elif comp_score < self.params['sell_score_threshold']:
                signal = 'SELL'
                signal_cn = '卖出'
                reasons.append(f"综合评分{comp_score:.1f}<{self.params['sell_score_threshold']}")
                
                if tech_score < 45:
                    reasons.append(f"技术面疲弱({tech_score:.1f})")
                if fund_score < 45:
                    reasons.append(f"资金流出({fund_score:.1f})")
            
            else:
                reasons.append(f"综合评分{comp_score:.1f}处于中性区间")
            
            # 6. 获取股票名称
            name = quote.get('name', symbol)
            change_pct = quote.get('change_pct', 0)
            
            return {
                'symbol': symbol,
                'name': name,
                'price': current_price,
                'change_pct': change_pct,
                'signal': signal,
                'signal_cn': signal_cn,
                'reason': '；'.join(reasons),
                'scores': {
                    'comprehensive': round(comp_score, 1),
                    'technical': round(tech_score, 1),
                    'fund_flow': round(fund_score, 1),
                    'sentiment': round(sent_score, 1),
                    'macro_cycle': round(macro_score, 1),
                    'fundamental': round(funda_score, 1),
                },
                'strategy': self.preset,
                'cap_style': cap_style,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            
        except Exception as e:
            logger.error(f"分析{symbol}出错: {e}")
            return None
    
    def build_signal_email(self, signals: List[Dict]) -> tuple:
        """
        构建买卖信号邮件内容
        
        Returns:
            (subject, html_body)
        """
        buy_signals = [s for s in signals if s['signal'] == 'BUY']
        sell_signals = [s for s in signals if s['signal'] == 'SELL']
        
        # 邮件主题
        parts = []
        if buy_signals:
            codes = ','.join(s['symbol'] for s in buy_signals)
            parts.append(f"🟢买入{codes}")
        if sell_signals:
            codes = ','.join(s['symbol'] for s in sell_signals)
            parts.append(f"🔴卖出{codes}")
        
        if parts:
            subject = f"📊 交易信号 {'|'.join(parts)} - {datetime.now().strftime('%H:%M')}"
        else:
            subject = f"📊 监控日报 - 暂无交易信号 - {datetime.now().strftime('%m/%d')}"
        
        # HTML正文
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; background: #f5f5f5; padding: 20px; }}
                .container {{ max-width: 700px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #1a73e8, #0d47a1); color: white; padding: 20px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 22px; }}
                .header p {{ margin: 5px 0 0; opacity: 0.9; font-size: 14px; }}
                .section {{ padding: 15px 20px; }}
                .signal-card {{ border: 2px solid #e0e0e0; border-radius: 8px; padding: 15px; margin: 10px 0; }}
                .signal-buy {{ border-color: #28a745; background: #f0fff4; }}
                .signal-sell {{ border-color: #dc3545; background: #fff5f5; }}
                .signal-hold {{ border-color: #ffc107; background: #fffdf0; }}
                .signal-badge {{ display: inline-block; padding: 3px 12px; border-radius: 15px; color: white; font-weight: bold; font-size: 14px; }}
                .badge-buy {{ background: #28a745; }}
                .badge-sell {{ background: #dc3545; }}
                .badge-hold {{ background: #ffc107; color: #333; }}
                .stock-name {{ font-size: 18px; font-weight: bold; color: #333; }}
                .stock-price {{ font-size: 24px; font-weight: bold; }}
                .price-up {{ color: #dc3545; }}
                .price-down {{ color: #28a745; }}
                .scores {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
                .score-item {{ background: #f8f9fa; padding: 5px 10px; border-radius: 5px; font-size: 13px; }}
                .reason {{ color: #555; font-size: 14px; margin-top: 8px; padding: 8px; background: #f8f9fa; border-radius: 5px; }}
                .footer {{ background: #f8f9fa; padding: 15px 20px; text-align: center; color: #888; font-size: 12px; border-top: 1px solid #eee; }}
                .summary {{ background: #e8f4fd; padding: 15px 20px; border-bottom: 1px solid #d0e8f7; }}
                .summary-item {{ display: inline-block; margin-right: 20px; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 AI量化交易信号</h1>
                    <p>{datetime.now().strftime('%Y年%m月%d日 %H:%M')} | 策略: {self.params['name']}</p>
                </div>
                
                <div class="summary">
                    <span class="summary-item">📈 监控: <strong>{len(signals)}只</strong></span>
                    <span class="summary-item">🟢 买入: <strong>{len(buy_signals)}只</strong></span>
                    <span class="summary-item">🔴 卖出: <strong>{len(sell_signals)}只</strong></span>
                    <span class="summary-item">⏱️ 间隔: <strong>{self.check_interval}秒</strong></span>
                </div>
                
                <div class="section">
        """
        
        # 按信号类型排序：买入 > 卖出 > 持有
        sorted_signals = sorted(signals, key=lambda x: {'BUY': 0, 'SELL': 1, 'HOLD': 2}.get(x['signal'], 3))
        
        for s in sorted_signals:
            signal_class = f"signal-{s['signal'].lower()}"
            badge_class = f"badge-{s['signal'].lower()}"
            
            change_emoji = '📈' if s['change_pct'] >= 0 else '📉'
            price_class = 'price-up' if s['change_pct'] >= 0 else 'price-down'
            change_sign = '+' if s['change_pct'] >= 0 else ''
            
            scores = s['scores']
            
            html += f"""
                    <div class="signal-card {signal_class}">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span class="stock-name">{s['symbol']} {s['name']}</span>
                                <span class="signal-badge {badge_class}" style="margin-left:10px;">{s['signal_cn']}</span>
                            </div>
                            <div style="text-align:right;">
                                <span class="stock-price {price_class}">¥{s['price']:.2f}</span>
                                <span style="margin-left:8px;">{change_emoji} {change_sign}{s['change_pct']:.2f}%</span>
                            </div>
                        </div>
                        
                        <div class="scores">
                            <span class="score-item">综合 <strong>{scores['comprehensive']}</strong></span>
                            <span class="score-item">技术 <strong>{scores['technical']}</strong></span>
                            <span class="score-item">资金 <strong>{scores['fund_flow']}</strong></span>
                            <span class="score-item">情绪 <strong>{scores['sentiment']}</strong></span>
                            <span class="score-item">宏观 <strong>{scores['macro_cycle']}</strong></span>
                            <span class="score-item">基本面 <strong>{scores['fundamental']}</strong></span>
                        </div>
                        
                        <div class="reason">💡 {s['reason']}</div>
                    </div>
            """
        
        # 添加无信号的股票
        hold_signals = [s for s in sorted_signals if s['signal'] == 'HOLD']
        if not buy_signals and not sell_signals and hold_signals:
            html += """
                    <div style="text-align:center; padding:20px; color:#888;">
                        <p style="font-size:36px; margin:10px;">😴</p>
                        <p style="font-size:16px;">本轮监控未发现交易信号，继续观察中...</p>
                    </div>
            """
        
        html += f"""
                </div>
                
                <div class="footer">
                    <p>🤖 AI股票实时监控系统 | 综合量化因子引擎 | 仅供参考，不构成投资建议</p>
                    <p>累计检查: {self.stats['total_checks']}次 | 已发送信号: {self.stats['signals_sent']}次</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return subject, html
    
    def check_all_stocks(self) -> List[Dict]:
        """检查所有监控股票"""
        results = []
        
        for symbol in self.stocks:
            try:
                result = self.analyze_stock(symbol)
                if result:
                    results.append(result)
                    
                    # 打印分析结果
                    emoji = {'BUY': '🟢', 'SELL': '🔴', 'HOLD': '⚪'}.get(result['signal'], '⚪')
                    logger.info(
                        f"{emoji} {result['symbol']} {result['name']} "
                        f"¥{result['price']:.2f}({result['change_pct']:+.2f}%) "
                        f"综合{result['scores']['comprehensive']} "
                        f"→ {result['signal_cn']} "
                        f"| {result['reason']}"
                    )
            except Exception as e:
                logger.error(f"分析{symbol}异常: {e}")
        
        return results
    
    def run_once(self) -> List[Dict]:
        """执行一次完整检查"""
        self.stats['total_checks'] += 1
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 第{self.stats['total_checks']}轮检查 | 监控{len(self.stocks)}只股票 | {datetime.now().strftime('%H:%M:%S')}")
        logger.info(f"{'='*60}")
        
        # 分析所有股票
        results = self.check_all_stocks()
        
        if not results:
            logger.warning("本轮无有效分析结果")
            return []
        
        # 筛选出有信号的股票（买入或卖出）
        signal_stocks = [r for r in results if r['signal'] in ('BUY', 'SELL')]
        
        # 检查是否有新信号需要通知
        new_signals = []
        for s in signal_stocks:
            if self._should_notify(s['symbol'], s['signal']):
                new_signals.append(s)
        
        if new_signals:
            logger.info(f"\n🔔 发现{len(new_signals)}个新交易信号!")
            for s in new_signals:
                emoji = '🟢' if s['signal'] == 'BUY' else '🔴'
                logger.info(f"  {emoji} {s['symbol']} {s['name']} → {s['signal_cn']}")
            
            # 发送邮件
            subject, html = self.build_signal_email(results)
            if self.email.send(subject, html):
                self.stats['emails_sent'] += 1
                self.stats['signals_sent'] += len(new_signals)
                logger.info(f"📧 信号邮件已发送")
            else:
                logger.warning(f"📧 邮件发送失败，但信号已记录到日志")
        else:
            if signal_stocks:
                logger.info(f"有{len(signal_stocks)}个信号但已通知过，跳过邮件")
            else:
                logger.info("本轮无交易信号")
        
        # 打印汇总
        buy_count = len([r for r in results if r['signal'] == 'BUY'])
        sell_count = len([r for r in results if r['signal'] == 'SELL'])
        hold_count = len([r for r in results if r['signal'] == 'HOLD'])
        logger.info(f"📈 汇总: 🟢买入{buy_count} | 🔴卖出{sell_count} | ⚪持有{hold_count}")
        
        return results
    
    def run(self):
        """持续运行监控"""
        print("\n" + "=" * 60)
        print("🤖 AI股票实时监控系统启动")
        print("=" * 60)
        print(f"  📊 监控股票: {', '.join(self.stocks)}")
        print(f"  📋 策略风格: {self.params['name']}")
        print(f"  ⏱️  检查间隔: {self.check_interval}秒")
        print(f"  📧 邮件通知: {'✅ 已启用' if self.email.enabled and self.email.is_configured() else '❌ 未启用'}")
        print(f"  📬 收件邮箱: {self.email.email_to or '未配置'}")
        print("=" * 60)
        
        if not self.email.enabled or not self.email.is_configured():
            print("\n⚠️  警告: 邮件未配置，信号将只记录到日志文件(stock_monitor.log)")
            print("   请在 .env 文件中配置 EMAIL_ENABLED=true 和相关邮箱参数\n")
        
        # 启动时发送一封测试邮件
        if self.email.enabled and self.email.is_configured():
            print("\n📧 发送启动测试邮件...")
            if self.email.send_test():
                print("✅ 测试邮件发送成功，请检查收件箱")
            else:
                print("❌ 测试邮件发送失败，请检查邮件配置")
        
        print(f"\n🚀 开始监控... (按 Ctrl+C 停止)\n")
        
        while True:
            try:
                if self.is_trading_time():
                    # 交易时间内，执行检查
                    self.run_once()
                    
                    # 等待下一次检查
                    logger.info(f"⏳ 下次检查: {self.check_interval}秒后")
                    time.sleep(self.check_interval)
                    
                else:
                    # 非交易时间
                    next_time = self.get_next_trading_time()
                    logger.info(f"💤 非交易时间，下一交易时段: {next_time}")
                    
                    # 非交易时间每10分钟检查一次是否到了交易时间
                    time.sleep(600)
                    
            except KeyboardInterrupt:
                print("\n\n🛑 监控已停止")
                print(f"  累计检查: {self.stats['total_checks']}次")
                print(f"  发送信号: {self.stats['signals_sent']}次")
                print(f"  发送邮件: {self.stats['emails_sent']}封")
                break
            except Exception as e:
                logger.error(f"监控异常: {e}")
                time.sleep(60)


def main():
    parser = argparse.ArgumentParser(description='AI股票实时监控 - 买卖信号 + 邮件通知')
    parser.add_argument('--stocks', type=str, default='',
                        help='监控股票代码，逗号分隔 (如: 600519,000858,600036)')
    parser.add_argument('--preset', type=str, default='balanced',
                        choices=['aggressive', 'balanced', 'conservative'],
                        help='策略风格: aggressive(激进) / balanced(稳健) / conservative(保守)')
    parser.add_argument('--interval', type=int, default=300,
                        help='检查间隔秒数 (默认300秒=5分钟)')
    parser.add_argument('--test-email', action='store_true',
                        help='仅发送测试邮件后退出')
    parser.add_argument('--once', action='store_true',
                        help='仅执行一次检查后退出')
    
    args = parser.parse_args()
    
    # 解析股票列表
    stocks = []
    if args.stocks:
        stocks = [s.strip() for s in args.stocks.split(',') if s.strip()]
    
    monitor = StockSignalMonitor(
        stocks=stocks or None,
        preset=args.preset,
        check_interval=args.interval
    )
    
    # 测试邮件模式
    if args.test_email:
        print("📧 发送测试邮件...")
        if monitor.email.send_test():
            print("✅ 测试邮件发送成功！请检查收件箱（包括垃圾邮件箱）")
        else:
            print("❌ 测试邮件发送失败，请检查 .env 中的邮件配置")
        return
    
    # 单次检查模式
    if args.once:
        results = monitor.run_once()
        if results:
            print(f"\n📊 分析完成，共{len(results)}只股票")
        return
    
    # 持续监控模式
    monitor.run()


if __name__ == '__main__':
    main()