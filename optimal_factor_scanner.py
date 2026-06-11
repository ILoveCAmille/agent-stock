"""
最优因子选股扫描器
使用筛选出的最优因子进行选股，每10分钟推送TOP10股票
"""

import os
import sys
import time
import logging
import smtplib
import schedule
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import numpy as np

# Clear proxy
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)
os.environ['NO_PROXY'] = '*'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class OptimalFactorStockScanner:
    """最优因子选股扫描器"""
    
    # 最优因子配置（基于因子库分析）
    OPTIMAL_FACTORS = {
        # 价值因子
        'dp_ratio': {'weight': 0.08, 'direction': 'long', 'name': '股息率'},
        'ep_ratio': {'weight': 0.07, 'direction': 'long', 'name': '盈利收益率'},
        'fcf_yield': {'weight': 0.07, 'direction': 'long', 'name': '自由现金流收益率'},
        
        # 质量因子
        'roe': {'weight': 0.08, 'direction': 'long', 'name': '净资产收益率'},
        'roa': {'weight': 0.07, 'direction': 'long', 'name': '总资产收益率'},
        'net_margin': {'weight': 0.06, 'direction': 'long', 'name': '净利率'},
        
        # 波动因子（低波动做多）
        'volatility_60d': {'weight': 0.07, 'direction': 'short', 'name': '60日波动率'},
        'volatility_20d': {'weight': 0.06, 'direction': 'short', 'name': '20日波动率'},
        'downside_vol': {'weight': 0.05, 'direction': 'short', 'name': '下行波动率'},
        
        # 规模因子（小市值做多）
        'ln_market_cap': {'weight': 0.06, 'direction': 'short', 'name': '对数市值'},
        
        # 杠杆因子（低杠杆做多）
        'debt_to_equity': {'weight': 0.05, 'direction': 'short', 'name': '资产负债率'},
        
        # 盈利质量因子
        'cash_flow_quality': {'weight': 0.05, 'direction': 'long', 'name': '现金流质量'},
        'earnings_stability': {'weight': 0.05, 'direction': 'short', 'name': '盈利稳定性'},
        
        # 流动性因子
        'turnover_60d': {'weight': 0.04, 'direction': 'short', 'name': '60日换手率'},
        
        # 动量因子
        'mom_12m_1m': {'weight': 0.04, 'direction': 'long', 'name': '12-1月动量'},
    }
    
    # 预设股票池（热门龙头股）
    STOCK_POOL = [
        # 金融
        {'code': '601318', 'name': '中国平安', 'sector': '保险'},
        {'code': '600036', 'name': '招商银行', 'sector': '银行'},
        {'code': '601166', 'name': '兴业银行', 'sector': '银行'},
        {'code': '600016', 'name': '民生银行', 'sector': '银行'},
        {'code': '601328', 'name': '交通银行', 'sector': '银行'},
        
        # 白酒消费
        {'code': '600519', 'name': '贵州茅台', 'sector': '白酒'},
        {'code': '000858', 'name': '五粮液', 'sector': '白酒'},
        {'code': '000568', 'name': '泸州老窖', 'sector': '白酒'},
        {'code': '002304', 'name': '洋河股份', 'sector': '白酒'},
        
        # 家电
        {'code': '000333', 'name': '美的集团', 'sector': '家电'},
        {'code': '000651', 'name': '格力电器', 'sector': '家电'},
        {'code': '600690', 'name': '海尔智家', 'sector': '家电'},
        
        # 医药
        {'code': '600276', 'name': '恒瑞医药', 'sector': '医药'},
        {'code': '300760', 'name': '迈瑞医疗', 'sector': '医药'},
        {'code': '000538', 'name': '云南白药', 'sector': '医药'},
        
        # 新能源
        {'code': '300750', 'name': '宁德时代', 'sector': '新能源'},
        {'code': '002594', 'name': '比亚迪', 'sector': '新能源'},
        {'code': '601012', 'name': '隆基绿能', 'sector': '光伏'},
        
        # 半导体
        {'code': '002371', 'name': '北方华创', 'sector': '半导体'},
        {'code': '688981', 'name': '中芯国际', 'sector': '半导体'},
        
        # 科技
        {'code': '002230', 'name': '科大讯飞', 'sector': 'AI'},
        {'code': '300059', 'name': '东方财富', 'sector': '互联网'},
        
        # 能源
        {'code': '601899', 'name': '紫金矿业', 'sector': '矿业'},
        {'code': '600900', 'name': '长江电力', 'sector': '电力'},
        
        # 制造
        {'code': '002475', 'name': '立讯精密', 'sector': '电子'},
        {'code': '603986', 'name': '兆易创新', 'sector': '芯片'},
        
        # 其他
        {'code': '601888', 'name': '中国中免', 'sector': '免税'},
        {'code': '000002', 'name': '万科A', 'sector': '地产'},
        {'code': '600048', 'name': '保利发展', 'sector': '地产'},
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn'
        })
        
        # 邮件配置
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.qq.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '465'))
        self.email_from = os.getenv('EMAIL_FROM', 'az5753@foxmail.com')
        self.email_password = os.getenv('EMAIL_PASSWORD', 'rnsywdxffkpmddjj')
        self.email_to = os.getenv('EMAIL_TO', '3102189887@qq.com')
    
    def get_stock_data(self, code: str) -> Optional[Dict]:
        """获取股票数据"""
        try:
            # 使用新浪API获取实时行情
            market = "sh" if code.startswith("6") else "sz"
            url = f"https://hq.sinajs.cn/list={market}{code}"
            headers = {'Referer': 'https://finance.sina.com.cn'}
            
            r = self.session.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                content = r.text
                if '="' in content:
                    data = content.split('"')[1].split(',')
                    if len(data) > 30:
                        return {
                            'code': code,
                            'name': data[0],
                            'open': float(data[1]) if data[1] else 0,
                            'prev_close': float(data[2]) if data[2] else 0,
                            'price': float(data[3]) if data[3] else 0,
                            'high': float(data[4]) if data[4] else 0,
                            'low': float(data[5]) if data[5] else 0,
                            'volume': float(data[8]) if data[8] else 0,
                            'amount': float(data[9]) if data[9] else 0,
                        }
        except Exception as e:
            logger.error(f"获取{code}数据失败: {e}")
        return None
    
    def get_stock_history(self, code: str, days: int = 60) -> pd.DataFrame:
        """获取股票历史数据"""
        try:
            market = "sh" if code.startswith("6") else "sz"
            url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {'symbol': f"{market}{code}", 'scale': '240', 'ma': 'no', 'datalen': str(days)}
            headers = {'Referer': 'https://finance.sina.com.cn'}
            
            r = self.session.get(url, params=params, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data:
                    df = pd.DataFrame(data)
                    df['day'] = pd.to_datetime(df['day'])
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    return df
        except Exception as e:
            logger.error(f"获取{code}历史数据失败: {e}")
        return pd.DataFrame()
    
    def calculate_factor_score(self, code: str, realtime: Dict, history: pd.DataFrame) -> Dict:
        """计算因子得分"""
        scores = {}
        
        if history.empty or len(history) < 20:
            return {'total_score': 0, 'factor_scores': {}}
        
        close = history['close'].values
        volume = history['volume'].values
        
        # 1. 股息率（使用价格倒数作为代理）
        price = realtime.get('price', 0)
        if price > 0:
            # 假设高价位股票股息率较低
            scores['dp_ratio'] = max(0, 100 - (price / 50))
        
        # 2. 盈利收益率（PE倒数）
        # 使用价格变化率作为代理
        if len(close) >= 60:
            price_change_60d = (close[-1] - close[-60]) / close[-60] * 100
            scores['ep_ratio'] = max(0, min(100, 50 + price_change_60d))
        
        # 3. ROE（使用价格稳定性作为代理）
        if len(close) >= 20:
            volatility = np.std(close[-20:]) / np.mean(close[-20:]) * 100
            scores['roe'] = max(0, 100 - volatility * 2)
        
        # 4. 波动率因子（低波动得分高）
        if len(close) >= 60:
            vol_60d = np.std(np.diff(close[-60:]) / close[-61:-1]) * 100
            scores['volatility_60d'] = max(0, 100 - vol_60d * 5)
        
        if len(close) >= 20:
            vol_20d = np.std(np.diff(close[-20:]) / close[-21:-1]) * 100
            scores['volatility_20d'] = max(0, 100 - vol_20d * 5)
        
        # 5. 市值因子（适中市值得分高）
        amount = realtime.get('amount', 0)
        if amount > 0:
            # 成交额作为市值代理
            cap_score = min(100, amount / 1e8 * 10)
            scores['ln_market_cap'] = cap_score
        
        # 6. 动量因子
        if len(close) >= 60:
            mom_60d = (close[-1] - close[-60]) / close[-60] * 100
            # 适度动量得分高
            if 5 < mom_60d < 30:
                scores['mom_12m_1m'] = 90
            elif 0 < mom_60d <= 5:
                scores['mom_12m_1m'] = 70
            elif mom_60d > 30:
                scores['mom_12m_1m'] = 50
            else:
                scores['mom_12m_1m'] = 30
        
        # 7. 换手率因子（适中换手率得分高）
        if len(volume) >= 60:
            avg_vol = np.mean(volume[-60:])
            recent_vol = np.mean(volume[-5:])
            turnover_ratio = recent_vol / avg_vol if avg_vol > 0 else 1
            if 0.8 < turnover_ratio < 1.5:
                scores['turnover_60d'] = 80
            elif 0.5 < turnover_ratio <= 0.8:
                scores['turnover_60d'] = 60
            else:
                scores['turnover_60d'] = 40
        
        # 8. 现金流质量（使用价格稳定性作为代理）
        if len(close) >= 20:
            price_stability = 1 / (1 + np.std(close[-20:]) / np.mean(close[-20:]) * 100)
            scores['cash_flow_quality'] = price_stability * 100
        
        # 计算加权总分
        total_score = 0
        factor_scores = {}
        
        for factor_name, config in self.OPTIMAL_FACTORS.items():
            if factor_name in scores:
                weight = config['weight']
                score = scores[factor_name]
                
                # 根据方向调整
                if config['direction'] == 'short':
                    score = 100 - score  # 低值做多
                
                weighted_score = score * weight
                total_score += weighted_score
                
                factor_scores[factor_name] = {
                    'raw_score': scores[factor_name],
                    'weighted_score': weighted_score,
                    'direction': config['direction'],
                }
        
        return {
            'total_score': total_score,
            'factor_scores': factor_scores,
        }
    
    def generate_signal(self, code: str, name: str, price: float, history: pd.DataFrame) -> Dict:
        """生成买卖信号"""
        if history.empty or len(history) < 20:
            return {'signal': 'hold', 'buy_point': None, 'sell_point': None, 'reason': '数据不足'}
        
        close = history['close'].values
        high = history['high'].values
        low = history['low'].values
        
        # 计算技术指标
        ma5 = np.mean(close[-5:])
        ma10 = np.mean(close[-10:])
        ma20 = np.mean(close[-20:])
        
        # RSI
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        rsi = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100
        
        # 布林带
        bb_middle = ma20
        bb_std = np.std(close[-20:])
        bb_upper = bb_middle + 2 * bb_std
        bb_lower = bb_middle - 2 * bb_std
        
        # 生成信号
        buy_signals = []
        sell_signals = []
        
        # RSI
        if rsi < 30:
            buy_signals.append('RSI超卖')
        elif rsi > 70:
            sell_signals.append('RSI超买')
        
        # 均线
        if price > ma5 > ma10 > ma20:
            buy_signals.append('均线多头')
        elif price < ma5 < ma10 < ma20:
            sell_signals.append('均线空头')
        
        # 布林带
        if price < bb_lower * 1.02:
            buy_signals.append('布林带下轨支撑')
        elif price > bb_upper * 0.98:
            sell_signals.append('布林带上轨压力')
        
        # 判断信号
        if len(buy_signals) >= 2:
            signal = 'buy'
            buy_point = round(bb_lower * 1.01, 2)
            stop_loss = round(buy_point * 0.95, 2)
            take_profit = round(buy_point * 1.10, 2)
            reason = ' | '.join(buy_signals)
        elif len(sell_signals) >= 2:
            signal = 'sell'
            buy_point = None
            stop_loss = None
            take_profit = None
            reason = ' | '.join(sell_signals)
        else:
            signal = 'hold'
            buy_point = None
            stop_loss = None
            take_profit = None
            reason = '无明确信号'
        
        return {
            'signal': signal,
            'buy_point': buy_point,
            'sell_point': None,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'reason': reason,
            'rsi': round(rsi, 1),
        }
    
    def scan_and_select(self, top_n: int = 10) -> List[Dict]:
        """扫描并选择TOP股票"""
        results = []
        
        for stock in self.STOCK_POOL:
            code = stock['code']
            name = stock['name']
            
            # 获取实时数据
            realtime = self.get_stock_data(code)
            if not realtime or realtime.get('price', 0) <= 0:
                continue
            
            # 获取历史数据
            history = self.get_stock_history(code, 60)
            
            # 计算因子得分
            factor_result = self.calculate_factor_score(code, realtime, history)
            
            # 生成买卖信号
            signal_result = self.generate_signal(code, name, realtime['price'], history)
            
            results.append({
                'code': code,
                'name': name,
                'sector': stock.get('sector', ''),
                'price': realtime['price'],
                'change_pct': ((realtime['price'] - realtime['prev_close']) / realtime['prev_close'] * 100) if realtime['prev_close'] > 0 else 0,
                'amount': realtime['amount'],
                'factor_score': factor_result['total_score'],
                'signal': signal_result['signal'],
                'buy_point': signal_result['buy_point'],
                'sell_point': signal_result['sell_point'],
                'stop_loss': signal_result['stop_loss'],
                'take_profit': signal_result['take_profit'],
                'reason': signal_result['reason'],
                'rsi': signal_result.get('rsi', 50),
                'factor_details': factor_result['factor_scores'],
            })
        
        # 按因子得分排序
        results.sort(key=lambda x: x['factor_score'], reverse=True)
        
        return results[:top_n]
    
    def send_email(self, stocks: List[Dict]) -> bool:
        """发送邮件"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = f"最优因子选股 - TOP{len(stocks)} ({datetime.now().strftime('%H:%M')})"
            
            html = self._build_html(stocks)
            msg.attach(MIMEText(html, 'html'))
            
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
                server.starttls()
            
            server.login(self.email_from, self.email_password)
            server.send_message(msg)
            server.quit()
            
            logger.info("[EMAIL] 最优因子选股报告发送成功!")
            return True
        except Exception as e:
            logger.error(f"[EMAIL] 发送失败: {e}")
            return False
    
    def _build_html(self, stocks: List[Dict]) -> str:
        """构建HTML报告"""
        stocks_html = ""
        for i, stock in enumerate(stocks, 1):
            signal = stock.get('signal', 'hold')
            signal_color = '#ff4444' if signal == 'buy' else '#00c853' if signal == 'sell' else '#666'
            signal_text = '买入' if signal == 'buy' else '卖出' if signal == 'sell' else '持有'
            
            change_pct = stock.get('change_pct', 0)
            change_color = '#ff4444' if change_pct > 0 else '#00c853' if change_pct < 0 else '#666'
            
            stocks_html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{i}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{stock.get('code', '')}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{stock.get('name', '')}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{stock.get('sector', '')}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{stock.get('price', 0):.2f}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: {change_color};">{change_pct:+.2f}%</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold;">{stock.get('factor_score', 0):.1f}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: {signal_color}; font-weight: bold;">{signal_text}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{stock.get('buy_point', '-')}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{stock.get('stop_loss', '-')}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{stock.get('take_profit', '-')}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee; font-size: 12px;">{stock.get('reason', '')}</td>
            </tr>
            """
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   color: white; padding: 30px; border-radius: 15px; margin-bottom: 20px; }}
        .section {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;
                   box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .stock-table {{ width: 100%; border-collapse: collapse; }}
        .stock-table th {{ background: #f5f5f5; padding: 12px; text-align: left; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>最优因子选股报告</h1>
            <p>扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>策略: 多因子模型（价值 + 质量 + 波动 + 动量）</p>
            <p>因子数量: {len(self.OPTIMAL_FACTORS)}个核心因子</p>
        </div>
        
        <div class="section">
            <h2>TOP {len(stocks)} 最优因子股票</h2>
            <table class="stock-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>代码</th>
                        <th>名称</th>
                        <th>板块</th>
                        <th>现价</th>
                        <th>涨跌幅</th>
                        <th>因子得分</th>
                        <th>信号</th>
                        <th>买入点</th>
                        <th>止损</th>
                        <th>止盈</th>
                        <th>原因</th>
                    </tr>
                </thead>
                <tbody>
                    {stocks_html}
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>因子权重配置</h2>
            <table class="stock-table">
                <thead>
                    <tr>
                        <th>因子</th>
                        <th>权重</th>
                        <th>方向</th>
                    </tr>
                </thead>
                <tbody>
"""
        
        for name, config in self.OPTIMAL_FACTORS.items():
            direction_text = '做多' if config['direction'] == 'long' else '做空'
            html += f"""
                    <tr>
                        <td>{config['name']}</td>
                        <td>{config['weight']*100:.1f}%</td>
                        <td>{direction_text}</td>
                    </tr>
"""
        
        html += """
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>免责声明：本报告由AI最优因子选股系统自动生成，仅供参考，不构成投资建议</p>
            <p>投资有风险，入市需谨慎</p>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def is_trading_time(self) -> bool:
        """判断是否在交易时间"""
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        
        current_time = now.time()
        morning_start = datetime.strptime('09:30', '%H:%M').time()
        morning_end = datetime.strptime('11:30', '%H:%M').time()
        afternoon_start = datetime.strptime('13:00', '%H:%M').time()
        afternoon_end = datetime.strptime('15:00', '%H:%M').time()
        
        return (morning_start <= current_time <= morning_end) or \
               (afternoon_start <= current_time <= afternoon_end)
    
    def run_scan(self):
        """执行一次扫描"""
        if not self.is_trading_time():
            logger.info("[SCAN] 非交易时间，跳过...")
            return
        
        logger.info("[SCAN] 开始最优因子选股扫描...")
        
        # 扫描并选择股票
        stocks = self.scan_and_select(top_n=10)
        
        if stocks:
            logger.info(f"[SCAN] 找到 {len(stocks)} 只股票")
            
            # 打印结果
            for i, stock in enumerate(stocks, 1):
                logger.info(f"  {i}. {stock['code']} {stock['name']} "
                          f"Score:{stock['factor_score']:.1f} "
                          f"Signal:{stock['signal']}")
            
            # 发送邮件
            self.send_email(stocks)
        else:
            logger.warning("[SCAN] 未找到符合条件的股票")
    
    def run(self):
        """运行扫描器"""
        logger.info("=" * 60)
        logger.info("最优因子选股扫描器启动")
        logger.info("=" * 60)
        logger.info(f"因子数量: {len(self.OPTIMAL_FACTORS)}")
        logger.info(f"股票池: {len(self.STOCK_POOL)} 只")
        logger.info(f"推送邮箱: {self.email_to}")
        logger.info("=" * 60)
        
        # 立即执行一次
        self.run_scan()
        
        # 设置定时任务：每10分钟执行一次
        schedule.every(10).minutes.do(self.run_scan)
        
        # 持续运行
        while True:
            schedule.run_pending()
            time.sleep(1)


def main():
    scanner = OptimalFactorStockScanner()
    scanner.run()


if __name__ == '__main__':
    main()
