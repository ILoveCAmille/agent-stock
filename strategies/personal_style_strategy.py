"""
个人投资风格选择法
核心逻辑：
1. 大盘判断 -> 进攻/防守
2. 板块轮动 -> 强势板块 -> 龙头标的（市值200亿左右，有带动性）
3. 新闻扫描 -> 利好标的
4. 技术指标 -> 买卖点信号
"""

import os
import sys
import requests
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Clear proxy
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

logger = logging.getLogger(__name__)


class PersonalStyleStrategy:
    """个人投资风格选择法"""
    
    # 策略配置
    STRATEGY_NAME = "个人投资风格选择法"
    VERSION = "1.0.0"
    
    # 目标市值范围（元）
    TARGET_MARKET_CAP_MIN = 100e8   # 100亿
    TARGET_MARKET_CAP_MAX = 500e8   # 500亿
    TARGET_MARKET_CAP_IDEAL = 200e8 # 200亿理想
    
    # 核心指数配置
    INDICES = {
        '000001': {'name': '上证指数', 'symbol': 'sh000001', 'weight': 0.30},
        '399001': {'name': '深证成指', 'symbol': 'sz399001', 'weight': 0.25},
        '399006': {'name': '创业板指', 'symbol': 'sz399006', 'weight': 0.25},
        '000688': {'name': '科创50', 'symbol': 'sh000688', 'weight': 0.20},
    }
    
    # 热门板块（按优先级排序）
    HOT_SECTORS = [
        '半导体', '人工智能', '新能源汽车', '医药生物', '军工',
        '消费电子', '光伏', '锂电池', '机器人', '量子计算',
    ]
    
    # 关键人物和事件
    KEY_FIGURES = ['马斯克', 'Musk', '黄仁勋', 'Jensen', '特朗普', 'Trump', '美联储', 'Fed', '鲍威尔', 'Powell']
    KEY_EVENTS = ['降息', '加息', '关税', '制裁', '芯片', 'AI', '人工智能', '新能源', '半导体']
    
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn'
        })
    
    # ============================================================
    # Part 1: 大盘行情判断
    # ============================================================
    
    def analyze_market(self) -> Dict:
        """分析大盘行情，决定攻防策略"""
        result = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'indices': {},
            'total_score': 0,
            'strategy': 'balanced',
            'position': 0.5,
            'description': '',
        }
        
        total_weight = 0
        weighted_score = 0
        
        for code, config in self.INDICES.items():
            realtime = self._get_index_realtime(config['symbol'])
            history = self._get_index_history(code, 20)
            
            score = 50
            if realtime:
                score = self._calculate_index_score(realtime, history)
                
                prev_close = realtime.get('prev_close', 0)
                latest = realtime.get('latest', 0)
                change_pct = ((latest - prev_close) / prev_close * 100) if prev_close > 0 else 0
                
                result['indices'][code] = {
                    'name': config['name'],
                    'latest': latest,
                    'change_pct': change_pct,
                    'score': score,
                }
                
                weighted_score += score * config['weight']
                total_weight += config['weight']
        
        if total_weight > 0:
            result['total_score'] = weighted_score / total_weight
        
        # 根据得分决定策略
        score = result['total_score']
        if score >= 75:
            result['strategy'] = 'aggressive'
            result['position'] = 0.8
            result['description'] = '强势进攻：大盘全面走强，积极参与'
        elif score >= 60:
            result['strategy'] = 'offensive'
            result['position'] = 0.6
            result['description'] = '温和进攻：大盘偏强，适度加仓'
        elif score >= 45:
            result['strategy'] = 'balanced'
            result['position'] = 0.5
            result['description'] = '攻守平衡：大盘震荡，精选个股'
        elif score >= 30:
            result['strategy'] = 'defensive'
            result['position'] = 0.3
            result['description'] = '防守为主：大盘偏弱，控制仓位'
        else:
            result['strategy'] = 'conservative'
            result['position'] = 0.1
            result['description'] = '极度防守：大盘弱势，轻仓观望'
        
        return result
    
    def _get_index_realtime(self, symbol: str) -> Optional[Dict]:
        """获取指数实时行情"""
        try:
            url = f"https://hq.sinajs.cn/list={symbol}"
            r = self.session.get(url, timeout=10)
            if r.status_code == 200:
                content = r.text
                if '="' in content:
                    data = content.split('"')[1].split(',')
                    if len(data) > 30:
                        return {
                            'name': data[0],
                            'open': float(data[1]) if data[1] else 0,
                            'prev_close': float(data[2]) if data[2] else 0,
                            'latest': float(data[3]) if data[3] else 0,
                            'high': float(data[4]) if data[4] else 0,
                            'low': float(data[5]) if data[5] else 0,
                            'volume': float(data[8]) if data[8] else 0,
                            'amount': float(data[9]) if data[9] else 0,
                        }
        except Exception as e:
            logger.error(f"获取指数{symbol}失败: {e}")
        return None
    
    def _get_index_history(self, symbol: str, days: int = 20) -> pd.DataFrame:
        """获取指数历史数据"""
        try:
            market = symbol[:2]
            code = symbol[2:]
            url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {'symbol': f"{market}{code}", 'scale': '240', 'ma': 'no', 'datalen': str(days)}
            
            r = self.session.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data:
                    df = pd.DataFrame(data)
                    df['day'] = pd.to_datetime(df['day'])
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    return df
        except Exception as e:
            logger.error(f"获取指数历史数据失败: {e}")
        return pd.DataFrame()
    
    def _calculate_index_score(self, realtime: Dict, history: pd.DataFrame) -> float:
        """计算指数得分 (0-100)"""
        score = 50
        
        if realtime:
            prev_close = realtime.get('prev_close', 0)
            latest = realtime.get('latest', 0)
            if prev_close > 0:
                change_pct = (latest - prev_close) / prev_close * 100
                if change_pct > 2: score += 20
                elif change_pct > 1: score += 15
                elif change_pct > 0: score += 10
                elif change_pct > -1: score -= 5
                elif change_pct > -2: score -= 10
                else: score -= 20
        
        if not history.empty and len(history) >= 5:
            close = history['close'].values
            ma5 = np.mean(close[-5:])
            if close[-1] > ma5: score += 10
            else: score -= 10
            
            if len(history) >= 20:
                ma20 = np.mean(close[-20:])
                if close[-1] > ma20: score += 10
                else: score -= 10
                if ma5 > ma20: score += 10
        
        return max(0, min(100, score))
    
    # ============================================================
    # Part 2: 板块轮动分析
    # ============================================================
    
    def find_strong_sectors(self) -> List[Dict]:
        """找出强势板块"""
        strong_sectors = []
        
        try:
            # 使用新浪API获取板块数据
            url = "https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"
            r = self.session.get(url, timeout=10)
            if r.status_code == 200:
                # 解析板块数据
                content = r.text
                # 备用：使用预设板块
                pass
        except Exception as e:
            logger.error(f"获取板块数据失败: {e}")
        
        # 使用预设热门板块
        for sector in self.HOT_SECTORS:
            strong_sectors.append({
                'name': sector,
                'score': 70,  # 默认分数
            })
        
        return strong_sectors[:5]
    
    def get_sector_stocks(self, sector_name: str) -> List[Dict]:
        """获取板块内的股票"""
        stocks = []
        try:
            # 使用新浪API获取板块股票
            url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
            
            # 板块代码映射
            sector_nodes = {
                '半导体': 'semiconductor',
                '人工智能': 'ai',
                '新能源汽车': 'nevehicle',
                '医药生物': 'pharma',
                '军工': 'military',
                '消费电子': 'consumerelectronics',
                '光伏': 'solar',
                '锂电池': 'lithium',
                '机器人': 'robot',
                '量子计算': 'quantum',
            }
            
            node = sector_nodes.get(sector_name, '')
            if node:
                params = {
                    'page': '1',
                    'num': '30',
                    'sort': 'changepercent',
                    'asc': '0',
                    'node': node,
                }
                
                r = self.session.get(url, params=params, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        for item in data:
                            stocks.append({
                                'code': item.get('code', ''),
                                'name': item.get('name', ''),
                                'price': float(item.get('trade', 0)),
                                'change_pct': float(item.get('changepercent', 0)),
                                'amount': float(item.get('amount', 0)),
                                'market_cap': float(item.get('mktcap', 0)),
                            })
        except Exception as e:
            logger.error(f"获取板块{sector_name}股票失败: {e}")
        
        # 如果API失败，使用预设的龙头股票
        if not stocks:
            stocks = self._get_preset_sector_stocks(sector_name)
        
        return stocks
    
    def _get_preset_sector_stocks(self, sector_name: str) -> List[Dict]:
        """获取预设的板块龙头股票"""
        preset_stocks = {
            '半导体': [
                {'code': '002371', 'name': '北方华创', 'price': 300.0, 'change_pct': 0, 'amount': 2e9, 'market_cap': 300e8},
                {'code': '688981', 'name': '中芯国际', 'price': 50.0, 'change_pct': 0, 'amount': 1.5e9, 'market_cap': 400e8},
                {'code': '603986', 'name': '兆易创新', 'price': 100.0, 'change_pct': 0, 'amount': 1e9, 'market_cap': 200e8},
            ],
            '人工智能': [
                {'code': '002230', 'name': '科大讯飞', 'price': 55.0, 'change_pct': 0, 'amount': 1.5e9, 'market_cap': 250e8},
                {'code': '688787', 'name': '海天瑞声', 'price': 80.0, 'change_pct': 0, 'amount': 5e8, 'market_cap': 100e8},
                {'code': '300496', 'name': '中科创达', 'price': 80.0, 'change_pct': 0, 'amount': 8e8, 'market_cap': 150e8},
            ],
            '新能源汽车': [
                {'code': '300750', 'name': '宁德时代', 'price': 200.0, 'change_pct': 0, 'amount': 3e9, 'market_cap': 800e8},
                {'code': '002594', 'name': '比亚迪', 'price': 280.0, 'change_pct': 0, 'amount': 2.5e9, 'market_cap': 700e8},
                {'code': '002460', 'name': '赣锋锂业', 'price': 50.0, 'change_pct': 0, 'amount': 1e9, 'market_cap': 200e8},
            ],
            '医药生物': [
                {'code': '600276', 'name': '恒瑞医药', 'price': 45.0, 'change_pct': 0, 'amount': 1e9, 'market_cap': 300e8},
                {'code': '300760', 'name': '迈瑞医疗', 'price': 300.0, 'change_pct': 0, 'amount': 8e8, 'market_cap': 400e8},
                {'code': '000538', 'name': '云南白药', 'price': 55.0, 'change_pct': 0, 'amount': 5e8, 'market_cap': 200e8},
            ],
            '军工': [
                {'code': '600760', 'name': '中航沈飞', 'price': 50.0, 'change_pct': 0, 'amount': 8e8, 'market_cap': 200e8},
                {'code': '600893', 'name': '航发动力', 'price': 40.0, 'change_pct': 0, 'amount': 6e8, 'market_cap': 180e8},
                {'code': '002049', 'name': '紫光国微', 'price': 150.0, 'change_pct': 0, 'amount': 1e9, 'market_cap': 250e8},
            ],
            '消费': [
                {'code': '600519', 'name': '贵州茅台', 'price': 1800.0, 'change_pct': 0, 'amount': 3e9, 'market_cap': 2000e8},
                {'code': '000858', 'name': '五粮液', 'price': 150.0, 'change_pct': 0, 'amount': 2e9, 'market_cap': 500e8},
                {'code': '000568', 'name': '泸州老窖', 'price': 180.0, 'change_pct': 0, 'amount': 1e9, 'market_cap': 300e8},
            ],
            '金融': [
                {'code': '601318', 'name': '中国平安', 'price': 50.0, 'change_pct': 0, 'amount': 2e9, 'market_cap': 800e8},
                {'code': '600036', 'name': '招商银行', 'price': 35.0, 'change_pct': 0, 'amount': 1.5e9, 'market_cap': 600e8},
                {'code': '601166', 'name': '兴业银行', 'price': 18.0, 'change_pct': 0, 'amount': 8e8, 'market_cap': 400e8},
            ],
        }
        
        # 返回预设股票，如果没有则返回热门股票
        stocks = preset_stocks.get(sector_name, [])
        
        if not stocks:
            # 返回一些热门股票
            stocks = [
                {'code': '600519', 'name': '贵州茅台', 'price': 1800.0, 'change_pct': 0, 'amount': 3e9, 'market_cap': 2000e8},
                {'code': '000858', 'name': '五粮液', 'price': 150.0, 'change_pct': 0, 'amount': 2e9, 'market_cap': 500e8},
                {'code': '300750', 'name': '宁德时代', 'price': 200.0, 'change_pct': 0, 'amount': 3e9, 'market_cap': 800e8},
                {'code': '002594', 'name': '比亚迪', 'price': 280.0, 'change_pct': 0, 'amount': 2.5e9, 'market_cap': 700e8},
                {'code': '601318', 'name': '中国平安', 'price': 50.0, 'change_pct': 0, 'amount': 2e9, 'market_cap': 800e8},
                {'code': '600036', 'name': '招商银行', 'price': 35.0, 'change_pct': 0, 'amount': 1.5e9, 'market_cap': 600e8},
                {'code': '000333', 'name': '美的集团', 'price': 60.0, 'change_pct': 0, 'amount': 1e9, 'market_cap': 400e8},
                {'code': '600900', 'name': '长江电力', 'price': 28.0, 'change_pct': 0, 'amount': 8e8, 'market_cap': 600e8},
                {'code': '601899', 'name': '紫金矿业', 'price': 15.0, 'change_pct': 0, 'amount': 1.2e9, 'market_cap': 300e8},
                {'code': '002475', 'name': '立讯精密', 'price': 35.0, 'change_pct': 0, 'amount': 1e9, 'market_cap': 250e8},
                {'code': '300059', 'name': '东方财富', 'price': 18.0, 'change_pct': 0, 'amount': 1.5e9, 'market_cap': 200e8},
                {'code': '601012', 'name': '隆基绿能', 'price': 25.0, 'change_pct': 0, 'amount': 1.2e9, 'market_cap': 300e8},
            ]
        
        return stocks
    
    def find_leading_stocks(self, stocks: List[Dict], count: int = 3) -> List[Dict]:
        """找出龙头标的（市值约200亿，有带动性）"""
        if not stocks:
            return []
        
        df = pd.DataFrame(stocks)
        
        # 过滤条件
        df = df[df['price'].notna() & (df['price'] > 0)]
        df = df[df['market_cap'].notna() & (df['market_cap'] > 0)]
        
        if df.empty:
            return []
        
        # 计算综合得分
        df['score'] = 0
        
        # 1. 市值得分（接近200亿得分最高）
        df['cap_diff'] = abs(df['market_cap'] - self.TARGET_MARKET_CAP_IDEAL)
        df['cap_score'] = np.where(
            (df['market_cap'] >= self.TARGET_MARKET_CAP_MIN) & (df['market_cap'] <= self.TARGET_MARKET_CAP_MAX),
            100 - (df['cap_diff'] / self.TARGET_MARKET_CAP_IDEAL * 50),
            30
        )
        df['score'] += df['cap_score'] * 0.4  # 市值权重40%
        
        # 2. 涨幅得分（适度上涨，带动性强）
        df['change_score'] = np.where(
            (df['change_pct'] > 2) & (df['change_pct'] < 8), 90,  # 适度上涨
            np.where(
                (df['change_pct'] >= 0) & (df['change_pct'] <= 2), 70,  # 平稳
                np.where(
                    (df['change_pct'] >= 8) & (df['change_pct'] < 15), 50,  # 涨幅较大
                    np.where(df['change_pct'] < 0, 30, 20)  # 下跌或涨幅过大
                )
            )
        )
        df['score'] += df['change_score'] * 0.35  # 涨幅权重35%
        
        # 3. 成交额得分（流动性好）
        df['amount_score'] = np.where(
            df['amount'] > 1e9, 100,
            np.where(df['amount'] > 5e8, 80, np.where(df['amount'] > 1e8, 60, 30))
        )
        df['score'] += df['amount_score'] * 0.25  # 成交额权重25%
        
        # 按得分排序，返回TOP
        df = df.sort_values('score', ascending=False)
        
        results = []
        for _, row in df.head(count).iterrows():
            results.append({
                'code': row['code'],
                'name': row['name'],
                'price': row['price'],
                'change_pct': row['change_pct'],
                'market_cap': row['market_cap'],
                'amount': row['amount'],
                'score': row['score'],
            })
        
        return results
    
    # ============================================================
    # Part 3: 新闻扫描
    # ============================================================
    
    def scan_news(self) -> List[Dict]:
        """扫描最新新闻"""
        all_news = []
        
        # 东方财富新闻
        try:
            url = "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"
            params = {'columns': '245,250,251', 'pageSize': '20', 'pageIndex': '1', 'client': 'web'}
            r = self.session.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if 'data' in data and 'list' in data['data']:
                    for item in data['data']['list']:
                        all_news.append({
                            'title': item.get('title', ''),
                            'content': item.get('digest', ''),
                            'time': item.get('showtime', ''),
                            'source': '东方财富',
                        })
        except Exception as e:
            logger.error(f"扫描东方财富新闻失败: {e}")
        
        # 新浪财经新闻
        try:
            url = "https://feed.mix.sina.com.cn/api/roll/get"
            params = {'pageid': '153', 'lid': '2516', 'num': '20', 'page': '1'}
            r = self.session.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if 'result' in data and 'data' in data['result']:
                    for item in data['result']['data']:
                        all_news.append({
                            'title': item.get('title', ''),
                            'content': item.get('intro', ''),
                            'time': datetime.fromtimestamp(int(item.get('ctime', 0))).strftime('%Y-%m-%d %H:%M') if item.get('ctime') else '',
                            'source': '新浪财经',
                        })
        except Exception as e:
            logger.error(f"扫描新浪财经新闻失败: {e}")
        
        return all_news
    
    def analyze_news_impact(self, news_list: List[Dict]) -> Dict:
        """分析新闻影响"""
        impact = {
            'related_sectors': [],
            'related_stocks': [],
            'key_events': [],
            'sentiment': 'neutral',
        }
        
        # 板块关键词映射
        sector_keywords = {
            '半导体': ['芯片', '半导体', '光刻机', 'EDA', 'GPU', '英伟达', 'NVIDIA'],
            '人工智能': ['AI', '人工智能', '大模型', 'ChatGPT', '算力', '机器人'],
            '新能源': ['新能源', '光伏', '风电', '储能', '锂电池', '电动车'],
            '医药生物': ['医药', '生物', '疫苗', '创新药'],
            '军工': ['军工', '国防', '导弹'],
            '消费': ['消费', '白酒', '食品', '家电'],
            '金融': ['银行', '券商', '保险', '降息', '利率'],
        }
        
        # 股票关键词映射
        stock_keywords = {
            '宁德时代': ['宁德', '锂电池'],
            '比亚迪': ['比亚迪', '电动车'],
            '贵州茅台': ['茅台', '白酒'],
            '中芯国际': ['中芯', '芯片制造'],
            '英伟达': ['英伟达', 'NVIDIA', '黄仁勋'],
            '特斯拉': ['特斯拉', '马斯克', 'Musk'],
        }
        
        positive_words = ['利好', '上涨', '突破', '创新', '增长', '合作', '签约', '发布']
        negative_words = ['利空', '下跌', '制裁', '限制', '减持', '亏损', '风险']
        
        pos_count = 0
        neg_count = 0
        
        for news in news_list:
            text = news.get('title', '') + ' ' + news.get('content', '')
            
            # 检测关键人物
            for figure in self.KEY_FIGURES:
                if figure in text:
                    impact['key_events'].append(f"{figure}: {news.get('title', '')[:30]}")
            
            # 检测相关板块
            for sector, keywords in sector_keywords.items():
                for kw in keywords:
                    if kw in text:
                        if sector not in impact['related_sectors']:
                            impact['related_sectors'].append(sector)
                        break
            
            # 检测相关股票
            for stock, keywords in stock_keywords.items():
                for kw in keywords:
                    if kw in text:
                        if stock not in impact['related_stocks']:
                            impact['related_stocks'].append(stock)
                        break
            
            # 情绪分析
            for word in positive_words:
                if word in text: pos_count += 1
            for word in negative_words:
                if word in text: neg_count += 1
        
        if pos_count > neg_count * 1.5:
            impact['sentiment'] = 'positive'
        elif neg_count > pos_count * 1.5:
            impact['sentiment'] = 'negative'
        
        return impact
    
    # ============================================================
    # Part 4: 买卖点信号生成
    # ============================================================
    
    def generate_signal(self, code: str, name: str, current_price: float) -> Dict:
        """生成买卖点信号"""
        # 获取历史数据
        history = self._get_stock_history(code, 60)
        if history.empty:
            return self._empty_signal(code, name, current_price)
        
        # 计算技术指标
        indicators = self._calculate_indicators(history)
        if not indicators:
            return self._empty_signal(code, name, current_price)
        
        # 生成信号
        signal = 'hold'
        buy_point = None
        sell_point = None
        stop_loss = None
        take_profit = None
        reason = ''
        
        rsi = indicators.get('rsi14', 50)
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 0)
        macd_hist = indicators.get('macd_hist', 0)
        ma5 = indicators.get('ma5', 0)
        ma10 = indicators.get('ma10', 0)
        ma20 = indicators.get('ma20', 0)
        bb_lower = indicators.get('bb_lower', 0)
        bb_upper = indicators.get('bb_upper', 0)
        kdj_j = indicators.get('kdj_j', 50)
        volume_ratio = indicators.get('volume_ratio', 1)
        
        # 买入信号评分
        buy_score = 0
        buy_reasons = []
        
        if rsi < 30:
            buy_score += 25
            buy_reasons.append('RSI超卖反弹')
        elif rsi < 40:
            buy_score += 15
            buy_reasons.append('RSI接近超卖')
        
        if macd is not None and macd_signal is not None:
            if macd > macd_signal and macd_hist > 0:
                buy_score += 25
                buy_reasons.append('MACD金叉')
        
        if kdj_j is not None and kdj_j < 20:
            buy_score += 20
            buy_reasons.append('KDJ超卖')
        
        if ma20 > 0 and current_price > ma20 * 0.98 and current_price < ma20 * 1.02:
            buy_score += 15
            buy_reasons.append('均线支撑')
        
        if bb_lower > 0 and current_price < bb_lower * 1.02:
            buy_score += 20
            buy_reasons.append('布林带下轨支撑')
        
        if 1.2 < volume_ratio < 3:
            buy_score += 10
            buy_reasons.append('温和放量')
        
        # 卖出信号评分
        sell_score = 0
        sell_reasons = []
        
        if rsi > 70:
            sell_score += 25
            sell_reasons.append('RSI超买')
        elif rsi > 60:
            sell_score += 10
            sell_reasons.append('RSI偏高')
        
        if macd is not None and macd_signal is not None:
            if macd < macd_signal and macd_hist < 0:
                sell_score += 25
                sell_reasons.append('MACD死叉')
        
        if kdj_j is not None and kdj_j > 80:
            sell_score += 20
            sell_reasons.append('KDJ超买')
        
        if bb_upper > 0 and current_price > bb_upper * 0.98:
            sell_score += 20
            sell_reasons.append('布林带上轨压力')
        
        if ma5 > 0 and ma10 > 0 and ma5 < ma10:
            sell_score += 15
            sell_reasons.append('均线空头')
        
        # 判断信号
        if buy_score >= 30:
            signal = 'buy'
            if bb_lower > 0:
                buy_point = round(bb_lower * 1.01, 2)
            elif ma20 > 0:
                buy_point = round(ma20 * 0.99, 2)
            else:
                buy_point = round(current_price * 0.97, 2)
            stop_loss = round(buy_point * 0.95, 2)
            take_profit = round(buy_point * 1.10, 2)
            reason = ' | '.join(buy_reasons)
        elif sell_score >= 30:
            signal = 'sell'
            if bb_upper > 0:
                sell_point = round(bb_upper * 0.99, 2)
            else:
                sell_point = round(current_price * 1.02, 2)
            reason = ' | '.join(sell_reasons)
        else:
            signal = 'hold'
            reason = '无明确信号'
        
        return {
            'code': code,
            'name': name,
            'price': current_price,
            'signal': signal,
            'buy_point': buy_point,
            'sell_point': sell_point,
            'stop_loss': stop_loss if signal == 'buy' else None,
            'take_profit': take_profit if signal == 'buy' else None,
            'reason': reason,
            'rsi': round(rsi, 1) if rsi else None,
            'macd_hist': round(macd_hist, 3) if macd_hist else None,
            'volume_ratio': round(volume_ratio, 2) if volume_ratio else None,
            'buy_score': buy_score,
            'sell_score': sell_score,
        }
    
    def _empty_signal(self, code: str, name: str, price: float) -> Dict:
        """空信号"""
        return {
            'code': code, 'name': name, 'price': price,
            'signal': 'hold', 'buy_point': None, 'sell_point': None,
            'stop_loss': None, 'take_profit': None, 'reason': '数据不足',
            'rsi': None, 'macd_hist': None, 'volume_ratio': None,
            'buy_score': 0, 'sell_score': 0,
        }
    
    def _get_stock_history(self, code: str, days: int = 60) -> pd.DataFrame:
        """获取股票历史数据"""
        try:
            market = "sh" if code.startswith("6") else "sz"
            url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {'symbol': f"{market}{code}", 'scale': '240', 'ma': 'no', 'datalen': str(days)}
            
            r = self.session.get(url, params=params, timeout=10)
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
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """计算技术指标"""
        indicators = {}
        
        if df.empty or len(df) < 20:
            return indicators
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values
        
        # 均线
        indicators['ma5'] = np.mean(close[-5:])
        indicators['ma10'] = np.mean(close[-10:])
        indicators['ma20'] = np.mean(close[-20:])
        if len(close) >= 60:
            indicators['ma60'] = np.mean(close[-60:])
        
        # RSI
        indicators['rsi14'] = self._rsi(close, 14)
        indicators['rsi6'] = self._rsi(close, 6)
        
        # MACD
        macd, signal, hist = self._macd(close)
        indicators['macd'] = macd
        indicators['macd_signal'] = signal
        indicators['macd_hist'] = hist
        
        # KDJ
        k, d, j = self._kdj(high, low, close)
        indicators['kdj_k'] = k
        indicators['kdj_d'] = d
        indicators['kdj_j'] = j
        
        # 布林带
        upper, middle, lower = self._bollinger(close)
        indicators['bb_upper'] = upper
        indicators['bb_middle'] = middle
        indicators['bb_lower'] = lower
        
        # 量比
        if len(volume) >= 5:
            avg_vol = np.mean(volume[-5:])
            indicators['volume_ratio'] = volume[-1] / avg_vol if avg_vol > 0 else 1
        
        return indicators
    
    def _rsi(self, data: np.ndarray, period: int = 14) -> Optional[float]:
        if len(data) < period + 1: return None
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0: return 100
        return 100 - (100 / (1 + avg_gain / avg_loss))
    
    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        multiplier = 2 / (period + 1)
        ema = np.zeros_like(data, dtype=float)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]
        return ema
    
    def _macd(self, data: np.ndarray, fast=12, slow=26, signal=9):
        if len(data) < slow + signal: return None, None, None
        ema_fast = self._ema(data, fast)
        ema_slow = self._ema(data, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(macd_line[~np.isnan(macd_line)], signal)
        full_signal = np.full_like(data, np.nan, dtype=float)
        start_idx = len(data) - len(signal_line)
        full_signal[start_idx:] = signal_line
        histogram = macd_line - full_signal
        return macd_line[-1], full_signal[-1], histogram[-1]
    
    def _kdj(self, high, low, close, n=9, m1=3, m2=3):
        if len(close) < n: return None, None, None
        rsv = np.full_like(close, np.nan, dtype=float)
        for i in range(n-1, len(close)):
            h = np.max(high[i-n+1:i+1])
            l = np.min(low[i-n+1:i+1])
            rsv[i] = (close[i] - l) / (h - l) * 100 if h != l else 50
        k = np.full_like(close, np.nan, dtype=float)
        d = np.full_like(close, np.nan, dtype=float)
        j = np.full_like(close, np.nan, dtype=float)
        k[n-1] = 50
        d[n-1] = 50
        for i in range(n, len(close)):
            if not np.isnan(rsv[i]):
                k[i] = (2/3)*k[i-1] + (1/3)*rsv[i]
                d[i] = (2/3)*d[i-1] + (1/3)*k[i]
                j[i] = 3*k[i] - 2*d[i]
        return k[-1], d[-1], j[-1]
    
    def _bollinger(self, data, period=20, std_dev=2):
        if len(data) < period: return None, None, None
        middle = np.mean(data[-period:])
        std = np.std(data[-period:])
        return middle + std_dev*std, middle, middle - std_dev*std
    
    # ============================================================
    # Part 5: 完整选股流程
    # ============================================================
    
    def select_stocks(self, top_n: int = 10) -> Dict:
        """完整的选股流程"""
        result = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'strategy': self.STRATEGY_NAME,
            'version': self.VERSION,
            'market': None,
            'news_impact': None,
            'stocks': [],
        }
        
        # 1. 大盘判断
        logger.info("[Step 1] 分析大盘行情...")
        market = self.analyze_market()
        result['market'] = market
        logger.info(f"  策略: {market['strategy']}, 得分: {market['total_score']:.1f}")
        
        # 2. 新闻扫描
        logger.info("[Step 2] 扫描新闻...")
        news_list = self.scan_news()
        news_impact = self.analyze_news_impact(news_list)
        result['news_impact'] = news_impact
        logger.info(f"  情绪: {news_impact['sentiment']}, 利好板块: {news_impact['related_sectors']}")
        
        # 3. 找强势板块和龙头标的
        logger.info("[Step 3] 找强势板块和龙头标的...")
        all_candidates = []
        
        # 从新闻利好板块开始
        target_sectors = news_impact.get('related_sectors', [])[:2]
        
        # 补充热门板块
        for sector in self.HOT_SECTORS:
            if sector not in target_sectors:
                target_sectors.append(sector)
            if len(target_sectors) >= 5:
                break
        
        for sector in target_sectors[:3]:
            try:
                stocks = self.get_sector_stocks(sector)
                if stocks:
                    leaders = self.find_leading_stocks(stocks, count=3)
                    for leader in leaders:
                        leader['sector'] = sector
                        all_candidates.append(leader)
                    logger.info(f"  {sector}: 找到 {len(leaders)} 只龙头标的")
            except Exception as e:
                logger.error(f"  {sector}: 失败 - {e}")
        
        # 4. 生成买卖信号
        logger.info("[Step 4] 生成买卖信号...")
        stock_signals = []
        
        for candidate in all_candidates[:15]:  # 最多分析15只
            code = candidate.get('code', '')
            name = candidate.get('name', '')
            price = candidate.get('price', 0)
            
            if not code or not price:
                continue
            
            try:
                signal = self.generate_signal(code, name, price)
                signal['sector'] = candidate.get('sector', '')
                signal['market_cap'] = candidate.get('market_cap', 0)
                stock_signals.append(signal)
            except Exception as e:
                logger.error(f"  {code} {name}: 信号生成失败 - {e}")
        
        # 排序：买入信号优先，然后按得分
        stock_signals.sort(key=lambda x: (
            0 if x.get('signal') == 'buy' else 1 if x.get('signal') == 'sell' else 2,
            -x.get('buy_score', 0)
        ))
        
        result['stocks'] = stock_signals[:top_n]
        
        logger.info(f"[完成] 选出 {len(result['stocks'])} 只股票")
        
        return result


# 创建全局实例
personal_strategy = PersonalStyleStrategy()
