"""
趋势选股盯盘系统
1. 大盘行情判断（上证/深证/创业板/科创板指数）-> 进攻/防守
2. 板块轮动分析 -> 强势板块 -> 龙头标的
3. 新闻扫描 -> 利好标的
4. 每10分钟推送TOP10股票（含买卖点）
"""

import os
import sys
import time
import json
import logging
import smtplib
import schedule
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
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


# ============================================================
# PART 1: 大盘行情分析器
# ============================================================

class MarketIndexAnalyzer:
    """大盘指数分析器"""
    
    # 核心指数配置
    INDICES = {
        '000001': {'name': '上证指数', 'symbol': 'sh000001', 'weight': 0.30},
        '399001': {'name': '深证成指', 'symbol': 'sz399001', 'weight': 0.25},
        '399006': {'name': '创业板指', 'symbol': 'sz399006', 'weight': 0.25},
        '000688': {'name': '科创50', 'symbol': 'sh000688', 'weight': 0.20},
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False
    
    def get_index_realtime(self, symbol: str) -> Optional[Dict]:
        """获取指数实时行情"""
        try:
            url = f"https://hq.sinajs.cn/list={symbol}"
            headers = {'Referer': 'https://finance.sina.com.cn'}
            
            r = self.session.get(url, headers=headers, timeout=10)
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
    
    def get_index_history(self, symbol: str, days: int = 20) -> pd.DataFrame:
        """获取指数历史数据"""
        try:
            # 使用新浪API获取历史数据
            market = symbol[:2]
            code = symbol[2:]
            url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {
                'symbol': f"{market}{code}",
                'scale': '240',
                'ma': 'no',
                'datalen': str(days)
            }
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
            logger.error(f"获取指数历史数据失败: {e}")
        return pd.DataFrame()
    
    def calculate_index_score(self, realtime: Dict, history: pd.DataFrame) -> float:
        """计算指数得分 (0-100)"""
        score = 50
        
        if realtime:
            # 当日涨跌
            prev_close = realtime.get('prev_close', 0)
            latest = realtime.get('latest', 0)
            if prev_close > 0:
                change_pct = (latest - prev_close) / prev_close * 100
                if change_pct > 2:
                    score += 20
                elif change_pct > 1:
                    score += 15
                elif change_pct > 0:
                    score += 10
                elif change_pct > -1:
                    score -= 5
                elif change_pct > -2:
                    score -= 10
                else:
                    score -= 20
        
        if not history.empty and len(history) >= 5:
            close = history['close'].values
            
            # 5日趋势
            ma5 = np.mean(close[-5:])
            if close[-1] > ma5:
                score += 10
            else:
                score -= 10
            
            # 20日趋势
            if len(history) >= 20:
                ma20 = np.mean(close[-20:])
                if close[-1] > ma20:
                    score += 10
                else:
                    score -= 10
                
                # 均线多头排列
                if ma5 > ma20:
                    score += 10
            
            # RSI
            if len(close) >= 15:
                rsi = self._calculate_rsi(close, 14)
                if rsi:
                    if rsi > 70:
                        score -= 10  # 超买
                    elif rsi < 30:
                        score += 10  # 超卖反弹机会
                    elif rsi > 50:
                        score += 5
        
        return max(0, min(100, score))
    
    def _calculate_rsi(self, data: np.ndarray, period: int = 14) -> Optional[float]:
        """计算RSI"""
        if len(data) < period + 1:
            return None
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
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
            realtime = self.get_index_realtime(config['symbol'])
            history = self.get_index_history(code, 20)
            
            score = 50
            if realtime:
                score = self.calculate_index_score(realtime, history)
                
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


# ============================================================
# PART 2: 板块轮动分析器
# ============================================================

class SectorRotationAnalyzer:
    """板块轮动分析器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False
    
    def get_sector_data(self) -> pd.DataFrame:
        """获取板块数据（使用新浪API）"""
        try:
            # 获取行业板块
            url = "https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"
            headers = {'Referer': 'https://finance.sina.com.cn'}
            
            r = self.session.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                # 解析板块数据
                content = r.text
                # 简化处理：返回空DataFrame，使用备用方案
                pass
        except Exception as e:
            logger.error(f"获取板块数据失败: {e}")
        
        return pd.DataFrame()
    
    def get_sector_stocks(self, sector_name: str) -> List[Dict]:
        """获取板块内的股票"""
        stocks = []
        try:
            import akshare as ak
            
            # 绕过代理
            old_get = requests.get
            def patched_get(*args, **kwargs):
                kwargs.setdefault('proxies', {'http': None, 'https': None})
                return old_get(*args, **kwargs)
            requests.get = patched_get
            
            try:
                df = ak.stock_board_industry_cons_em(symbol=sector_name)
                if df is not None and not df.empty:
                    for _, row in df.head(20).iterrows():
                        stocks.append({
                            'code': row.get('代码', ''),
                            'name': row.get('名称', ''),
                            'price': row.get('最新价', 0),
                            'change_pct': row.get('涨跌幅', 0),
                            'amount': row.get('成交额', 0),
                            'market_cap': row.get('总市值', 0),
                        })
            finally:
                requests.get = old_get
                
        except Exception as e:
            logger.error(f"获取板块{sector_name}股票失败: {e}")
        
        return stocks
    
    def find_leading_stocks(self, stocks: List[Dict], target_cap: float = 200e8) -> List[Dict]:
        """找出龙头标的（市值约200亿，有带动性）"""
        if not stocks:
            return []
        
        df = pd.DataFrame(stocks)
        
        # 过滤条件
        df = df[df['price'].notna() & (df['price'] > 0)]
        
        if df.empty:
            return []
        
        # 计算综合得分
        df['score'] = 0
        
        # 涨幅得分（适度上涨，避免追高）
        if 'change_pct' in df.columns:
            df['score'] += np.where(
                (df['change_pct'] > 2) & (df['change_pct'] < 8), 30,
                np.where(
                    (df['change_pct'] >= 0) & (df['change_pct'] <= 2), 20,
                    np.where(df['change_pct'] >= 8, 10, 0)
                )
            )
        
        # 市值得分（接近200亿得分高）
        if 'market_cap' in df.columns:
            df['score'] += np.where(
                (df['market_cap'] > 100e8) & (df['market_cap'] < 500e8), 40,
                np.where(
                    (df['market_cap'] >= 500e8) & (df['market_cap'] < 1000e8), 30,
                    np.where(df['market_cap'] >= 1000e8, 20, 10)
                )
            )
        
        # 成交额得分
        if 'amount' in df.columns:
            df['score'] += np.where(
                df['amount'] > 1e9, 30,
                np.where(df['amount'] > 5e8, 20, 10)
            )
        
        # 返回TOP股票
        df = df.sort_values('score', ascending=False)
        return df.head(5).to_dict('records')


# ============================================================
# PART 3: 新闻扫描器
# ============================================================

class NewsScanner:
    """新闻扫描器 - 监测重要信息来源"""
    
    # 关键人物和事件
    KEY_FIGURES = ['马斯克', 'Musk', '黄仁勋', 'Jensen', '特朗普', 'Trump', '美联储', 'Fed', '鲍威尔', 'Powell']
    KEY_EVENTS = ['降息', '加息', '关税', '制裁', '芯片', 'AI', '人工智能', '新能源', '半导体', '量子计算']
    
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False
    
    def scan_news(self) -> List[Dict]:
        """扫描最新新闻"""
        all_news = []
        
        # 1. 东方财富新闻
        eastmoney_news = self._scan_eastmoney_news()
        all_news.extend(eastmoney_news)
        
        # 2. 新浪财经新闻
        sina_news = self._scan_sina_news()
        all_news.extend(sina_news)
        
        # 3. 财联社快讯
        cls_news = self._scan_cls_news()
        all_news.extend(cls_news)
        
        return all_news
    
    def _scan_eastmoney_news(self) -> List[Dict]:
        """扫描东方财富新闻"""
        news_list = []
        try:
            url = "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"
            params = {
                'columns': '245,250,251',
                'pageSize': '20',
                'pageIndex': '1',
                'sortEnd': '',
                'client': 'web'
            }
            
            r = self.session.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if 'data' in data and 'list' in data['data']:
                    for item in data['data']['list']:
                        news_list.append({
                            'title': item.get('title', ''),
                            'content': item.get('digest', ''),
                            'time': item.get('showtime', ''),
                            'source': '东方财富',
                        })
        except Exception as e:
            logger.error(f"扫描东方财富新闻失败: {e}")
        return news_list
    
    def _scan_sina_news(self) -> List[Dict]:
        """扫描新浪财经新闻"""
        news_list = []
        try:
            url = "https://feed.mix.sina.com.cn/api/roll/get"
            params = {
                'pageid': '153',
                'lid': '2516',
                'num': '20',
                'page': '1'
            }
            
            r = self.session.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if 'result' in data and 'data' in data['result']:
                    for item in data['result']['data']:
                        news_list.append({
                            'title': item.get('title', ''),
                            'content': item.get('intro', ''),
                            'time': datetime.fromtimestamp(int(item.get('ctime', 0))).strftime('%Y-%m-%d %H:%M') if item.get('ctime') else '',
                            'source': '新浪财经',
                        })
        except Exception as e:
            logger.error(f"扫描新浪财经新闻失败: {e}")
        return news_list
    
    def _scan_cls_news(self) -> List[Dict]:
        """扫描财联社快讯"""
        news_list = []
        try:
            url = "https://www.cls.cn/nodeapi/updateTelegraphList"
            params = {
                'app': 'CailianpressWeb',
                'os': 'web',
                'sv': '7.7.5',
                'rn': '20'
            }
            
            r = self.session.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if 'data' in data and 'roll_data' in data['data']:
                    for item in data['data']['roll_data']:
                        news_list.append({
                            'title': item.get('title', '') or item.get('content', '')[:50],
                            'content': item.get('content', ''),
                            'time': datetime.fromtimestamp(item.get('ctime', 0)).strftime('%Y-%m-%d %H:%M') if item.get('ctime') else '',
                            'source': '财联社',
                        })
        except Exception as e:
            logger.error(f"扫描财联社新闻失败: {e}")
        return news_list
    
    def analyze_news_impact(self, news_list: List[Dict]) -> Dict:
        """分析新闻影响，找出利好标的"""
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
            '医药生物': ['医药', '生物', '疫苗', '创新药', '医疗器械'],
            '军工': ['军工', '国防', '导弹', '战斗机', '航母'],
            '消费': ['消费', '白酒', '食品', '家电', '旅游'],
            '金融': ['银行', '券商', '保险', '降息', '利率'],
            '房地产': ['房地产', '楼市', '房价', '地产'],
        }
        
        # 股票关键词映射
        stock_keywords = {
            '宁德时代': ['宁德', '锂电池', '储能'],
            '比亚迪': ['比亚迪', '电动车', '新能源车'],
            '贵州茅台': ['茅台', '白酒'],
            '中芯国际': ['中芯', '芯片制造'],
            '华为': ['华为', '鸿蒙', '昇腾'],
            '特斯拉': ['特斯拉', '马斯克', 'Musk'],
            '英伟达': ['英伟达', 'NVIDIA', '黄仁勋', 'GPU'],
        }
        
        positive_words = ['利好', '上涨', '突破', '创新', '增长', '合作', '签约', '发布']
        negative_words = ['利空', '下跌', '制裁', '限制', '减持', '亏损', '风险']
        
        pos_count = 0
        neg_count = 0
        
        for news in news_list:
            title = news.get('title', '')
            content = news.get('content', '')
            text = title + ' ' + content
            
            # 检测关键人物
            for figure in self.KEY_FIGURES:
                if figure in text:
                    impact['key_events'].append(f"{figure}: {title[:30]}")
            
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
                if word in text:
                    pos_count += 1
            for word in negative_words:
                if word in text:
                    neg_count += 1
        
        if pos_count > neg_count * 1.5:
            impact['sentiment'] = 'positive'
        elif neg_count > pos_count * 1.5:
            impact['sentiment'] = 'negative'
        
        return impact


# ============================================================
# PART 4: 买卖点信号生成器
# ============================================================

class SignalGenerator:
    """买卖点信号生成器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False
    
    def get_stock_history(self, code: str, days: int = 60) -> pd.DataFrame:
        """获取股票历史数据"""
        try:
            market = "sh" if code.startswith("6") else "sz"
            url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {
                'symbol': f"{market}{code}",
                'scale': '240',
                'ma': 'no',
                'datalen': str(days)
            }
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
    
    def calculate_indicators(self, df: pd.DataFrame) -> Dict:
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
        indicators['rsi14'] = self._calculate_rsi(close, 14)
        indicators['rsi6'] = self._calculate_rsi(close, 6)
        
        # MACD
        macd, signal, hist = self._calculate_macd(close)
        indicators['macd'] = macd
        indicators['macd_signal'] = signal
        indicators['macd_hist'] = hist
        
        # KDJ
        k, d, j = self._calculate_kdj(high, low, close)
        indicators['kdj_k'] = k
        indicators['kdj_d'] = d
        indicators['kdj_j'] = j
        
        # 布林带
        upper, middle, lower = self._calculate_bollinger(close)
        indicators['bb_upper'] = upper
        indicators['bb_middle'] = middle
        indicators['bb_lower'] = lower
        
        # 量比
        if len(volume) >= 5:
            avg_vol = np.mean(volume[-5:])
            indicators['volume_ratio'] = volume[-1] / avg_vol if avg_vol > 0 else 1
        
        # 当前价格
        indicators['current_price'] = close[-1]
        indicators['prev_close'] = close[-2] if len(close) > 1 else close[-1]
        
        return indicators
    
    def _calculate_rsi(self, data: np.ndarray, period: int = 14) -> Optional[float]:
        if len(data) < period + 1:
            return None
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100
        return 100 - (100 / (1 + avg_gain / avg_loss))
    
    def _calculate_macd(self, data: np.ndarray, fast=12, slow=26, signal=9):
        if len(data) < slow + signal:
            return None, None, None
        ema_fast = self._ema(data, fast)
        ema_slow = self._ema(data, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(macd_line[~np.isnan(macd_line)], signal)
        full_signal = np.full_like(data, np.nan, dtype=float)
        start_idx = len(data) - len(signal_line)
        full_signal[start_idx:] = signal_line
        histogram = macd_line - full_signal
        return macd_line[-1], full_signal[-1], histogram[-1]
    
    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        multiplier = 2 / (period + 1)
        ema = np.zeros_like(data, dtype=float)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]
        return ema
    
    def _calculate_kdj(self, high, low, close, n=9, m1=3, m2=3):
        if len(close) < n:
            return None, None, None
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
    
    def _calculate_bollinger(self, data, period=20, std_dev=2):
        if len(data) < period:
            return None, None, None
        middle = np.mean(data[-period:])
        std = np.std(data[-period:])
        return middle + std_dev*std, middle, middle - std_dev*std
    
    def generate_signals(self, code: str, name: str, current_price: float) -> Dict:
        """生成买卖点信号"""
        df = self.get_stock_history(code)
        indicators = self.calculate_indicators(df)
        
        if not indicators:
            return {'code': code, 'name': name, 'price': current_price, 'signal': 'hold', 'buy_point': None, 'sell_point': None, 'reason': '数据不足'}
        
        signal = 'hold'
        buy_point = None
        sell_point = None
        reason = ''
        strength = 0
        
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
        
        # === 买入信号 ===
        buy_signals = []
        
        # RSI超卖反弹
        if rsi < 30:
            buy_signals.append(('RSI超卖反弹', 20))
        elif rsi < 40 and rsi > 30:
            buy_signals.append(('RSI接近超卖', 10))
        
        # MACD金叉
        if macd is not None and macd_signal is not None:
            if macd > macd_signal and macd_hist > 0:
                buy_signals.append(('MACD金叉', 25))
        
        # KDJ金叉
        if kdj_j is not None and kdj_j < 20:
            buy_signals.append(('KDJ超卖', 15))
        
        # 均线支撑
        if ma20 > 0 and current_price > ma20 * 0.98 and current_price < ma20 * 1.02:
            buy_signals.append(('均线支撑', 15))
        
        # 布林带下轨支撑
        if bb_lower > 0 and current_price < bb_lower * 1.02:
            buy_signals.append(('布林带下轨支撑', 20))
        
        # 温和放量
        if 1.2 < volume_ratio < 3:
            buy_signals.append(('温和放量', 10))
        
        # === 卖出信号 ===
        sell_signals = []
        
        # RSI超买
        if rsi > 70:
            sell_signals.append(('RSI超买', 25))
        elif rsi > 60:
            sell_signals.append(('RSI偏高', 10))
        
        # MACD死叉
        if macd is not None and macd_signal is not None:
            if macd < macd_signal and macd_hist < 0:
                sell_signals.append(('MACD死叉', 25))
        
        # KDJ超买
        if kdj_j is not None and kdj_j > 80:
            sell_signals.append(('KDJ超买', 15))
        
        # 布林带上轨压力
        if bb_upper > 0 and current_price > bb_upper * 0.98:
            sell_signals.append(('布林带上轨压力', 20))
        
        # 均线压力
        if ma5 > 0 and ma10 > 0 and ma5 < ma10:
            sell_signals.append(('均线空头', 15))
        
        # 计算买卖点
        buy_score = sum([s[1] for s in buy_signals])
        sell_score = sum([s[1] for s in sell_signals])
        
        if buy_score >= 30:
            signal = 'buy'
            # 买入点：布林带下轨或均线支撑
            if bb_lower > 0:
                buy_point = round(bb_lower * 1.01, 2)
            elif ma20 > 0:
                buy_point = round(ma20 * 0.99, 2)
            else:
                buy_point = round(current_price * 0.97, 2)
            
            # 止损点
            stop_loss = round(buy_point * 0.95, 2)
            # 止盈点
            take_profit = round(buy_point * 1.10, 2)
            
            reason = ' | '.join([s[0] for s in buy_signals])
            
        elif sell_score >= 30:
            signal = 'sell'
            # 卖出点：布林带上轨或当前价格
            if bb_upper > 0:
                sell_point = round(bb_upper * 0.99, 2)
            else:
                sell_point = round(current_price * 1.02, 2)
            
            reason = ' | '.join([s[0] for s in sell_signals])
            stop_loss = None
            take_profit = None
        else:
            signal = 'hold'
            reason = '无明确信号'
            stop_loss = None
            take_profit = None
        
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


# ============================================================
# PART 5: 邮件发送器
# ============================================================

class EmailSender:
    """邮件发送器"""
    
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.qq.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '465'))
        self.email_from = os.getenv('EMAIL_FROM', 'az5753@foxmail.com')
        self.email_password = os.getenv('EMAIL_PASSWORD', 'rnsywdxffkpmddjj')
        self.email_to = os.getenv('EMAIL_TO', '3102189887@qq.com')
    
    def send_report(self, market: Dict, stocks: List[Dict], news_impact: Dict) -> bool:
        """发送选股报告"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = f"趋势选股报告 - {datetime.now().strftime('%H:%M')} ({market.get('strategy', '')})"
            
            html = self._build_html(market, stocks, news_impact)
            msg.attach(MIMEText(html, 'html'))
            
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
                server.starttls()
            
            server.login(self.email_from, self.email_password)
            server.send_message(msg)
            server.quit()
            
            logger.info("[EMAIL] Report sent successfully!")
            return True
        except Exception as e:
            logger.error(f"[EMAIL] Failed: {e}")
            return False
    
    def _build_html(self, market: Dict, stocks: List[Dict], news_impact: Dict) -> str:
        """构建HTML报告"""
        strategy = market.get('strategy', 'balanced')
        strategy_colors = {
            'aggressive': '#ff4444',
            'offensive': '#ff8800',
            'balanced': '#ffbb33',
            'defensive': '#00c853',
            'conservative': '#0066cc',
        }
        color = strategy_colors.get(strategy, '#ffbb33')
        
        # 大盘指数HTML
        indices_html = ""
        for code, idx in market.get('indices', {}).items():
            change = idx.get('change_pct', 0)
            change_color = '#ff4444' if change > 0 else '#00c853' if change < 0 else '#666'
            indices_html += f"""
            <div style="display: inline-block; margin: 10px; padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                <div style="font-weight: bold;">{idx.get('name', '')}</div>
                <div style="font-size: 24px; font-weight: bold;">{idx.get('latest', 0):.2f}</div>
                <div style="color: {change_color};">{change:+.2f}%</div>
            </div>
            """
        
        # 新闻HTML
        news_html = ""
        if news_impact.get('key_events'):
            news_html += "<h4>重要新闻人物</h4><ul>"
            for event in news_impact['key_events'][:5]:
                news_html += f"<li>{event}</li>"
            news_html += "</ul>"
        
        if news_impact.get('related_sectors'):
            news_html += f"<h4>利好板块</h4><p>{', '.join(news_impact['related_sectors'])}</p>"
        
        if news_impact.get('related_stocks'):
            news_html += f"<4>利好标的</h4><p>{', '.join(news_impact['related_stocks'])}</p>"
        
        # 股票HTML
        stocks_html = ""
        for i, stock in enumerate(stocks, 1):
            signal = stock.get('signal', 'hold')
            signal_color = '#ff4444' if signal == 'buy' else '#00c853' if signal == 'sell' else '#666'
            signal_text = '买入' if signal == 'buy' else '卖出' if signal == 'sell' else '持有'
            
            buy_point = stock.get('buy_point', '-')
            sell_point = stock.get('sell_point', '-')
            stop_loss = stock.get('stop_loss', '-')
            take_profit = stock.get('take_profit', '-')
            
            stocks_html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{i}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{stock.get('code', '')}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{stock.get('name', '')}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{stock.get('price', 0):.2f}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: {signal_color}; font-weight: bold;">{signal_text}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{buy_point}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{sell_point}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{stop_loss}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{take_profit}</td>
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
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, {color} 0%, {color}88 100%); 
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
            <h1>趋势选股报告</h1>
            <p>扫描时间: {market.get('timestamp', '')}</p>
            <p>攻防策略: {market.get('description', '')}</p>
            <p>建议仓位: {market.get('position', 0.5)*100:.0f}%</p>
        </div>
        
        <div class="section">
            <h2>大盘行情</h2>
            <div style="text-align: center;">
                {indices_html}
            </div>
            <p style="text-align: center; margin-top: 10px;">
                综合得分: <strong>{market.get('total_score', 0):.1f}</strong>/100
            </p>
        </div>
        
        <div class="section">
            <h2>新闻分析</h2>
            {news_html if news_html else '<p>暂无重要新闻</p>'}
            <p>新闻情绪: <strong>{news_impact.get('sentiment', 'neutral')}</strong></p>
        </div>
        
        <div class="section">
            <h2>TOP 10 趋势股票（含买卖点）</h2>
            <table class="stock-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>代码</th>
                        <th>名称</th>
                        <th>现价</th>
                        <th>信号</th>
                        <th>买入点</th>
                        <th>卖出点</th>
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
        
        <div class="footer">
            <p>免责声明：本报告由AI趋势选股系统自动生成，仅供参考，不构成投资建议</p>
            <p>投资有风险，入市需谨慎</p>
        </div>
    </div>
</body>
</html>
"""
        return html


# ============================================================
# PART 6: 主扫描器
# ============================================================

class TrendStockScanner:
    """趋势选股扫描器"""
    
    def __init__(self):
        self.market_analyzer = MarketIndexAnalyzer()
        self.sector_analyzer = SectorRotationAnalyzer()
        self.news_scanner = NewsScanner()
        self.signal_generator = SignalGenerator()
        self.email_sender = EmailSender()
        
        self.last_news_scan = None
        self.news_impact = {}
        self.scan_count = 0
    
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
    
    def scan_news_if_needed(self):
        """每小时扫描新闻"""
        now = datetime.now()
        if self.last_news_scan is None or (now - self.last_news_scan).seconds >= 3600:
            logger.info("[NEWS] Scanning news...")
            news_list = self.news_scanner.scan_news()
            self.news_impact = self.news_scanner.analyze_news_impact(news_list)
            self.last_news_scan = now
            logger.info(f"[NEWS] Found {len(news_list)} news, sentiment: {self.news_impact.get('sentiment')}")
    
    def find_trend_stocks(self, market: Dict) -> List[Dict]:
        """找出趋势股票"""
        stocks = []
        
        # 策略：根据大盘决定选股激进程度
        strategy = market.get('strategy', 'balanced')
        
        # 获取热门板块股票（使用预设的热门板块）
        hot_sectors = ['半导体', '人工智能', '新能源汽车', '医药生物', '军工']
        
        # 如果有新闻利好板块，优先使用
        if self.news_impact.get('related_sectors'):
            hot_sectors = self.news_impact['related_sectors'] + hot_sectors
        
        # 去重
        hot_sectors = list(dict.fromkeys(hot_sectors))[:5]
        
        for sector in hot_sectors[:3]:  # 只取前3个板块
            try:
                sector_stocks = self.sector_analyzer.get_sector_stocks(sector)
                if sector_stocks:
                    # 找龙头标的
                    leaders = self.sector_analyzer.find_leading_stocks(sector_stocks)
                    for leader in leaders[:2]:  # 每个板块取2只
                        stocks.append({
                            'code': leader.get('code', ''),
                            'name': leader.get('name', ''),
                            'price': leader.get('price', 0),
                            'sector': sector,
                        })
            except Exception as e:
                logger.error(f"Failed to get {sector} stocks: {e}")
        
        # 如果股票不足10只，补充热门股票
        if len(stocks) < 10:
            try:
                import akshare as ak
                old_get = requests.get
                def patched_get(*args, **kwargs):
                    kwargs.setdefault('proxies', {'http': None, 'https': None})
                    return old_get(*args, **kwargs)
                requests.get = patched_get
                
                try:
                    df = ak.stock_zh_a_spot_em()
                    if df is not None and not df.empty:
                        # 按成交额排序，取热门股票
                        df = df.sort_values('成交额', ascending=False)
                        for _, row in df.head(20).iterrows():
                            if len(stocks) >= 10:
                                break
                            code = row.get('代码', '')
                            if not any(s['code'] == code for s in stocks):
                                stocks.append({
                                    'code': code,
                                    'name': row.get('名称', ''),
                                    'price': row.get('最新价', 0),
                                    'sector': '热门',
                                })
                finally:
                    requests.get = old_get
            except Exception as e:
                logger.error(f"Failed to get hot stocks: {e}")
        
        return stocks[:10]
    
    def generate_signals_for_stocks(self, stocks: List[Dict]) -> List[Dict]:
        """为每只股票生成买卖信号"""
        results = []
        
        for stock in stocks:
            code = stock.get('code', '')
            name = stock.get('name', '')
            price = stock.get('price', 0)
            
            if not code or not price:
                continue
            
            try:
                signal = self.signal_generator.generate_signals(code, name, price)
                signal['sector'] = stock.get('sector', '')
                results.append(signal)
            except Exception as e:
                logger.error(f"Failed to generate signal for {code}: {e}")
        
        return results
    
    def run_scan(self):
        """执行一次扫描"""
        if not self.is_trading_time():
            logger.info("[SCAN] Not trading time, skipping...")
            return
        
        self.scan_count += 1
        scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"[SCAN] Starting scan #{self.scan_count} at {scan_time}")
        
        # 1. 分析大盘
        logger.info("[SCAN] Step 1: Analyzing market...")
        market = self.market_analyzer.analyze_market()
        logger.info(f"[SCAN] Market strategy: {market.get('strategy')}, score: {market.get('total_score', 0):.1f}")
        
        # 2. 扫描新闻（每小时）
        self.scan_news_if_needed()
        
        # 3. 找趋势股票
        logger.info("[SCAN] Step 2: Finding trend stocks...")
        trend_stocks = self.find_trend_stocks(market)
        logger.info(f"[SCAN] Found {len(trend_stocks)} trend stocks")
        
        # 4. 生成买卖信号
        logger.info("[SCAN] Step 3: Generating signals...")
        stock_signals = self.generate_signals_for_stocks(trend_stocks)
        
        # 5. 发送邮件
        logger.info("[SCAN] Step 4: Sending email...")
        success = self.email_sender.send_report(market, stock_signals, self.news_impact)
        
        if success:
            logger.info(f"[SCAN] Scan #{self.scan_count} completed successfully!")
            
            # 打印结果
            for i, stock in enumerate(stock_signals, 1):
                signal = stock.get('signal', 'hold')
                logger.info(f"  {i}. {stock['code']} {stock['name']} "
                          f"Price:{stock['price']:.2f} "
                          f"Signal:{signal} "
                          f"Reason:{stock.get('reason', '')[:30]}")
        else:
            logger.error("[SCAN] Failed to send email")
    
    def run(self):
        """运行扫描器"""
        logger.info("=" * 60)
        logger.info("Trend Stock Scanner Started")
        logger.info("=" * 60)
        logger.info("Strategy: 大盘判断 + 板块轮动 + 新闻扫描")
        logger.info("Trading Hours: 09:30-11:30, 13:00-15:00")
        logger.info("Scan Interval: 10 minutes")
        logger.info("News Scan: Every 1 hour")
        logger.info(f"Email: {self.email_sender.email_to}")
        logger.info("=" * 60)
        
        # 立即执行一次
        self.run_scan()
        
        # 设置定时任务
        schedule.every(10).minutes.do(self.run_scan)
        
        # 持续运行
        while True:
            schedule.run_pending()
            time.sleep(1)


def main():
    """主函数"""
    scanner = TrendStockScanner()
    scanner.run()


if __name__ == '__main__':
    main()
