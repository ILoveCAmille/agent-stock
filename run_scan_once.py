"""
运行一次完整扫描并发送邮件
"""

import os
import sys

# Clear proxy
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)
os.environ['NO_PROXY'] = '*'

sys.path.insert(0, '.')

import requests
import logging
from datetime import datetime
from trend_stock_scanner import MarketIndexAnalyzer, NewsScanner, EmailSender, SignalGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

print('=' * 60)
print('Running Full Trend Stock Scan')
print('=' * 60)

# 1. 大盘分析
print('\n[Step 1] Analyzing market...')
market_analyzer = MarketIndexAnalyzer()
market = market_analyzer.analyze_market()
print(f'Strategy: {market.get("strategy")}')
print(f'Score: {round(market.get("total_score", 0), 1)}')

# 2. 新闻扫描
print('\n[Step 2] Scanning news...')
news_scanner = NewsScanner()
news_list = news_scanner.scan_news()
news_impact = news_scanner.analyze_news_impact(news_list)
print(f'Found {len(news_list)} news')
print(f'Related sectors: {news_impact.get("related_sectors")}')
print(f'Key events: {news_impact.get("key_events", [])[:3]}')

# 3. 获取热门股票
print('\n[Step 3] Getting hot stocks...')

session = requests.Session()
session.trust_env = False

# 使用新浪API获取热门股票
hot_stocks = []

# 方法1: 从新浪获取涨幅榜
try:
    # 获取沪市涨幅榜
    url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    params = {
        'page': '1',
        'num': '20',
        'sort': 'changepercent',
        'asc': '0',
        'node': 'hs_a',
        'symbol': '',
        '_s_r_a': 'init'
    }
    headers = {'Referer': 'https://finance.sina.com.cn'}
    
    r = session.get(url, params=params, headers=headers, timeout=15)
    if r.status_code == 200:
        data = r.json()
        if isinstance(data, list):
            for item in data[:20]:
                code = item.get('code', '')
                name = item.get('name', '')
                price = float(item.get('trade', 0))
                change = float(item.get('changepercent', 0))
                amount = float(item.get('amount', 0))
                mktcap = float(item.get('mktcap', 0))
                
                # 过滤条件
                if price > 5 and amount > 1e8 and mktcap > 50e8:
                    hot_stocks.append({
                        'code': code,
                        'name': name,
                        'price': price,
                        'change_pct': change,
                        'amount': amount,
                        'market_cap': mktcap,
                    })
            print(f'Got {len(hot_stocks)} stocks from Sina API')
except Exception as e:
    print(f'Sina API failed: {e}')

# 方法2: 如果新浪失败，使用预设的热门股票
if len(hot_stocks) < 10:
    print('Using preset hot stocks...')
    preset_stocks = [
        ('600519', '贵州茅台', 1800.0),
        ('000858', '五粮液', 150.0),
        ('300750', '宁德时代', 200.0),
        ('002594', '比亚迪', 280.0),
        ('601318', '中国平安', 50.0),
        ('600036', '招商银行', 35.0),
        ('000333', '美的集团', 60.0),
        ('600900', '长江电力', 28.0),
        ('601899', '紫金矿业', 15.0),
        ('002475', '立讯精密', 35.0),
        ('300059', '东方财富', 18.0),
        ('601012', '隆基绿能', 25.0),
        ('002371', '北方华创', 300.0),
        ('688981', '中芯国际', 50.0),
        ('002230', '科大讯飞', 55.0),
    ]
    
    for code, name, price in preset_stocks:
        if not any(s['code'] == code for s in hot_stocks):
            hot_stocks.append({
                'code': code,
                'name': name,
                'price': price,
                'change_pct': 0,
                'amount': 1e9,
                'market_cap': 200e8,
            })

print(f'Total stocks to analyze: {len(hot_stocks)}')

# 4. 生成买卖信号
print('\n[Step 4] Generating signals...')
signal_gen = SignalGenerator()

stock_signals = []
for stock in hot_stocks[:15]:  # 分析前15只
    code = stock.get('code', '')
    name = stock.get('name', '')
    price = stock.get('price', 0)
    
    if not code or not price:
        continue
    
    try:
        signal = signal_gen.generate_signals(code, name, price)
        signal['sector'] = stock.get('sector', '热门')
        stock_signals.append(signal)
        print(f'  {code} {name}: {signal.get("signal")} - {signal.get("reason", "")[:30]}')
    except Exception as e:
        print(f'  {code} {name}: Error - {e}')

# 按信号排序：买入信号优先
stock_signals.sort(key=lambda x: (0 if x.get('signal') == 'buy' else 1 if x.get('signal') == 'sell' else 2))

# 取TOP10
top_stocks = stock_signals[:10]
print(f'\nTOP {len(top_stocks)} stocks selected')

# 5. 发送邮件
print('\n[Step 5] Sending email...')
email_sender = EmailSender()
success = email_sender.send_report(market, top_stocks, news_impact)
print(f'Email sent: {success}')

# 打印结果
print('\n' + '=' * 60)
print('TOP 10 Stocks:')
print('=' * 60)
for i, stock in enumerate(top_stocks, 1):
    signal = stock.get('signal', 'hold')
    print(f"{i}. {stock['code']} {stock['name']} | Price:{stock['price']:.2f} | Signal:{signal} | Buy:{stock.get('buy_point', '-')} | Sell:{stock.get('sell_point', '-')}")

print('\nDone!')
