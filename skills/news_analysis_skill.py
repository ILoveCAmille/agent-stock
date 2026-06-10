"""
新闻分析技能
提供新闻搜索和分析能力
"""

import requests
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class NewsAnalysisSkill(BaseSkill):
    """新闻分析技能"""
    
    def __init__(self):
        super().__init__()
    
    def get_stock_news(self, stock_code: str) -> List[Dict]:
        """获取股票新闻"""
        news_list = []
        
        # 1. 东方财富新闻
        eastmoney_news = self._get_eastmoney_news(stock_code)
        news_list.extend(eastmoney_news)
        
        # 2. 新浪财经新闻
        sina_news = self._get_sina_news(stock_code)
        news_list.extend(sina_news)
        
        return news_list[:15]
    
    def _get_eastmoney_news(self, stock_code: str) -> List[Dict]:
        """获取东方财富新闻"""
        news_list = []
        try:
            url = "https://search-api-web.eastmoney.com/search/jsonp"
            params = {
                'cb': 'jQuery',
                'param': json.dumps({
                    "uid": "",
                    "keyword": stock_code,
                    "type": ["cmsArticleWebOld"],
                    "client": "web",
                    "clientType": "web",
                    "clientVersion": "curr",
                    "param": {
                        "cmsArticleWebOld": {
                            "searchScope": "default",
                            "sort": "default",
                            "pageIndex": 1,
                            "pageSize": 10,
                            "preTag": "",
                            "postTag": ""
                        }
                    }
                })
            }
            
            response = self._safe_get(url, params=params, timeout=15)
            if response:
                text = response.text
                json_str = text[text.index('(') + 1:text.rindex(')')]
                data = json.loads(json_str)
                
                if 'result' in data and 'cmsArticleWebOld' in data['result']:
                    articles = data['result']['cmsArticleWebOld']
                    for article in articles[:10]:
                        news_list.append({
                            'title': article.get('title', '').replace('<em>', '').replace('</em>', ''),
                            'source': '东方财富',
                            'date': article.get('date', ''),
                            'content': article.get('content', '')[:200]
                        })
        except Exception as e:
            logger.error(f"获取东方财富新闻失败: {e}")
        return news_list
    
    def _get_sina_news(self, stock_code: str) -> List[Dict]:
        """获取新浪财经新闻"""
        news_list = []
        try:
            url = "https://feed.mix.sina.com.cn/api/roll/get"
            params = {
                'pageid': '153',
                'lid': '2516',
                'k': stock_code,
                'num': '10',
                'page': '1'
            }
            
            response = self._safe_get(url, params=params, timeout=15)
            if response:
                data = response.json()
                if 'result' in data and 'data' in data['result']:
                    for item in data['result']['data'][:5]:
                        news_list.append({
                            'title': item.get('title', ''),
                            'source': '新浪财经',
                            'date': datetime.fromtimestamp(int(item.get('ctime', 0))).strftime('%Y-%m-%d %H:%M') if item.get('ctime') else '',
                            'content': item.get('intro', '')[:200]
                        })
        except Exception as e:
            logger.error(f"获取新浪财经新闻失败: {e}")
        return news_list
    
    def get_market_news(self) -> List[Dict]:
        """获取市场新闻"""
        news_list = []
        try:
            url = "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"
            params = {
                'columns': '245,250',
                'pageSize': '10',
                'pageIndex': '1',
                'sortEnd': '',
                'client': 'web'
            }
            
            response = self._safe_get(url, params=params, timeout=15)
            if response:
                data = response.json()
                if 'data' in data and 'list' in data['data']:
                    for item in data['data']['list'][:10]:
                        news_list.append({
                            'title': item.get('title', ''),
                            'source': '东方财富',
                            'date': item.get('showtime', ''),
                            'content': item.get('digest', '')[:200]
                        })
        except Exception as e:
            logger.error(f"获取市场新闻失败: {e}")
        return news_list
    
    def analyze_news_sentiment(self, news_list: List[Dict]) -> Dict:
        """分析新闻情绪"""
        sentiment = {
            'positive_count': 0,
            'negative_count': 0,
            'neutral_count': 0,
            'overall': 'neutral',
            'keywords': []
        }
        
        positive_words = ['利好', '上涨', '增长', '突破', '新高', '买入', '推荐', '看好']
        negative_words = ['利空', '下跌', '亏损', '风险', '减持', '卖出', '警示', '下滑']
        
        for news in news_list:
            title = news.get('title', '')
            
            pos_count = sum(1 for w in positive_words if w in title)
            neg_count = sum(1 for w in negative_words if w in title)
            
            if pos_count > neg_count:
                sentiment['positive_count'] += 1
            elif neg_count > pos_count:
                sentiment['negative_count'] += 1
            else:
                sentiment['neutral_count'] += 1
        
        total = len(news_list)
        if total > 0:
            if sentiment['positive_count'] > total * 0.6:
                sentiment['overall'] = 'positive'
            elif sentiment['negative_count'] > total * 0.6:
                sentiment['overall'] = 'negative'
        
        return sentiment
    
    def get_skill_description(self) -> str:
        """获取技能描述"""
        return """
【新闻分析技能】
- 获取个股新闻（东方财富、新浪财经）
- 获取市场新闻
- 分析新闻情绪（利好/利空/中性）
- 识别重大事件和热点
"""
