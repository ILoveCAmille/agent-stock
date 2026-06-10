"""
基础技能模块
提供所有技能的公共基础功能
"""

import os
import requests
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseSkill:
    """技能基类"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False  # 绕过系统代理
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self._cache = {}
        self._cache_ttl = 300  # 5分钟缓存
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if (datetime.now() - timestamp).seconds < self._cache_ttl:
                return data
            del self._cache[key]
        return None
    
    def _set_cached(self, key: str, data: Any):
        """设置缓存数据"""
        self._cache[key] = (data, datetime.now())
    
    def _safe_get(self, url: str, params: Dict = None, headers: Dict = None, 
                  timeout: int = 10) -> Optional[requests.Response]:
        """安全的HTTP GET请求"""
        try:
            response = self.session.get(
                url, 
                params=params, 
                headers=headers or {},
                timeout=timeout
            )
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(f"HTTP GET failed for {url}: {e}")
            return None
    
    def _safe_post(self, url: str, data: Dict = None, json_data: Dict = None,
                   headers: Dict = None, timeout: int = 10) -> Optional[requests.Response]:
        """安全的HTTP POST请求"""
        try:
            response = self.session.post(
                url,
                data=data,
                json=json_data,
                headers=headers or {},
                timeout=timeout
            )
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(f"HTTP POST failed for {url}: {e}")
            return None
    
    def format_number(self, num: float, precision: int = 2) -> str:
        """格式化数字显示"""
        if abs(num) >= 1e8:
            return f"{num/1e8:.{precision}f}亿"
        elif abs(num) >= 1e4:
            return f"{num/1e4:.{precision}f}万"
        else:
            return f"{num:.{precision}f}"
    
    def format_percent(self, num: float) -> str:
        """格式化百分比"""
        return f"{num:+.2f}%"
    
    def get_skill_info(self) -> Dict:
        """获取技能信息"""
        return {
            'name': self.__class__.__name__,
            'description': self.__doc__ or '',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
