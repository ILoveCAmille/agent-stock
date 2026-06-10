"""
联网搜索技能
提供实时网络搜索能力
"""

import requests
import json
import logging
from typing import Dict, List, Optional
from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class WebSearchSkill(BaseSkill):
    """联网搜索技能"""
    
    def __init__(self):
        super().__init__()
        self.search_engines = {
            'bing': 'https://api.bing.microsoft.com/v7.0/search',
            'baidu': 'https://www.baidu.com/s',
            'sogou': 'https://www.sogou.com/web',
        }
    
    def search_stock_news(self, stock_name: str, stock_code: str) -> List[Dict]:
        """搜索股票相关新闻"""
        results = []
        
        # 1. 搜索东方财富新闻
        eastmoney_news = self._search_eastmoney_news(stock_code)
        results.extend(eastmoney_news)
        
        # 2. 搜索新浪财经新闻
        sina_news = self._search_sina_news(stock_code)
        results.extend(sina_news)
        
        # 3. 搜索百度新闻
        baidu_news = self._search_baidu_news(stock_name)
        results.extend(baidu_news)
        
        return results[:20]  # 返回前20条
    
    def _search_eastmoney_news(self, stock_code: str) -> List[Dict]:
        """搜索东方财富新闻"""
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
                # 解析JSONP响应
                json_str = text[text.index('(') + 1:text.rindex(')')]
                data = json.loads(json_str)
                
                if 'result' in data and 'cmsArticleWebOld' in data['result']:
                    articles = data['result']['cmsArticleWebOld']
                    for article in articles[:10]:
                        news_list.append({
                            'title': article.get('title', '').replace('<em>', '').replace('</em>', ''),
                            'source': '东方财富',
                            'date': article.get('date', ''),
                            'url': article.get('url', ''),
                            'content': article.get('content', '')[:200]
                        })
        except Exception as e:
            logger.error(f"东方财富新闻搜索失败: {e}")
        
        return news_list
    
    def _search_sina_news(self, stock_code: str) -> List[Dict]:
        """搜索新浪财经新闻"""
        news_list = []
        try:
            url = "https://search.sina.com.cn/news"
            params = {
                'q': stock_code,
                'range': 'all',
                'c': 'news',
                'sort': 'time',
                'num': '10'
            }
            
            response = self._safe_get(url, params=params, timeout=15)
            if response:
                # 简单解析HTML获取标题
                from html.parser import HTMLParser
                import re
                
                # 提取标题和链接
                titles = re.findall(r'<h2><a[^>]*>(.*?)</a></h2>', response.text)
                for title in titles[:5]:
                    clean_title = re.sub(r'<[^>]+>', '', title)
                    news_list.append({
                        'title': clean_title,
                        'source': '新浪财经',
                        'date': '',
                        'url': '',
                        'content': ''
                    })
        except Exception as e:
            logger.error(f"新浪财经新闻搜索失败: {e}")
        
        return news_list
    
    def _search_baidu_news(self, keyword: str) -> List[Dict]:
        """搜索百度新闻"""
        news_list = []
        try:
            url = "https://www.baidu.com/s"
            params = {
                'wd': f'{keyword} 股票',
                'tn': 'news',
                'rtt': '1',
                'bsst': '1'
            }
            
            response = self._safe_get(url, params=params, timeout=15)
            if response:
                import re
                # 提取标题
                titles = re.findall(r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>', response.text, re.DOTALL)
                for title in titles[:5]:
                    clean_title = re.sub(r'<[^>]+>', '', title).strip()
                    if clean_title:
                        news_list.append({
                            'title': clean_title,
                            'source': '百度',
                            'date': '',
                            'url': '',
                            'content': ''
                        })
        except Exception as e:
            logger.error(f"百度新闻搜索失败: {e}")
        
        return news_list
    
    def search_market_overview(self) -> Dict:
        """搜索市场概况"""
        overview = {
            'hot_sectors': [],
            'market_news': [],
            'policy_news': []
        }
        
        try:
            # 搜索热门板块
            url = "https://push2.eastmoney.com/api/qt/clist/get"
            params = {
                'pn': '1',
                'pz': '10',
                'po': '1',
                'np': '1',
                'fltt': '2',
                'invt': '2',
                'fid': 'f3',
                'fs': 'm:90+t:2',
                'fields': 'f2,f3,f4,f12,f14'
            }
            
            response = self._safe_get(url, params=params, timeout=10)
            if response:
                data = response.json()
                if 'data' in data and 'diff' in data['data']:
                    for item in data['data']['diff'][:10]:
                        overview['hot_sectors'].append({
                            'name': item.get('f14', ''),
                            'code': item.get('f12', ''),
                            'change': item.get('f3', 0)
                        })
        except Exception as e:
            logger.error(f"搜索市场概况失败: {e}")
        
        return overview
    
    def search_company_announcements(self, stock_code: str) -> List[Dict]:
        """搜索公司公告"""
        announcements = []
        try:
            url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
            params = {
                'sr': '-1',
                'page_size': '10',
                'page_index': '1',
                'ann_type': 'SHA,SZA,SZA_BJ',
                'client_source': 'web',
                'stock_list': stock_code,
                'f_node': '0',
                's_node': '0'
            }
            
            response = self._safe_get(url, params=params, timeout=15)
            if response:
                data = response.json()
                if 'data' in data and 'list' in data['data']:
                    for item in data['data']['list'][:10]:
                        announcements.append({
                            'title': item.get('title', ''),
                            'date': item.get('notice_date', ''),
                            'type': item.get('ann_type', ''),
                            'url': item.get('url', '')
                        })
        except Exception as e:
            logger.error(f"搜索公司公告失败: {e}")
        
        return announcements
    
    def get_skill_description(self) -> str:
        """获取技能描述"""
        return """
【联网搜索技能】
- 实时搜索股票相关新闻（东方财富、新浪财经、百度）
- 搜索市场概况和热门板块
- 搜索公司公告和信息披露
- 提供最新市场信息支持分析
"""
