"""
市场情绪指标模块
计算和分析A股市场情绪
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class MarketSentimentIndicator:
    """市场情绪指标分析器"""
    
    def __init__(self):
        self._cache = {}
        self._cache_time = None
    
    def get_market_overview(self) -> Dict:
        """获取市场概览数据"""
        result = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'indices': {},
            'advance_decline': {},
            'limit_stats': {},
            'volume_stats': {},
            'sentiment_score': 50,
            'sentiment_level': 'neutral',
            'signals': [],
        }
        
        try:
            # 1. 获取主要指数
            result['indices'] = self._get_main_indices()
            
            # 2. 获取涨跌统计
            result['advance_decline'] = self._get_advance_decline()
            
            # 3. 获取涨跌停统计
            result['limit_stats'] = self._get_limit_stats()
            
            # 4. 计算情绪得分
            result['sentiment_score'] = self._calculate_sentiment_score(result)
            
            # 5. 判断情绪水平
            result['sentiment_level'] = self._determine_sentiment_level(result['sentiment_score'])
            
            # 6. 生成信号
            result['signals'] = self._generate_signals(result)
            
        except Exception as e:
            logger.error(f"获取市场概览失败: {e}")
        
        return result
    
    def _get_main_indices(self) -> Dict:
        """获取主要指数"""
        indices = {}
        
        try:
            df = ak.stock_zh_index_spot_em(symbol="沪深重要指数")
            if df is not None and not df.empty:
                # 提取关键指数
                key_indices = ['上证指数', '深证成指', '创业板指', '沪深300', '中证500']
                
                for name in key_indices:
                    row = df[df['名称'] == name]
                    if not row.empty:
                        row = row.iloc[0]
                        indices[name] = {
                            'price': float(row.get('最新价', 0)),
                            'change': float(row.get('涨跌幅', 0)),
                            'volume': float(row.get('成交额', 0)),
                        }
        except Exception as e:
            logger.error(f"获取指数数据失败: {e}")
        
        return indices
    
    def _get_advance_decline(self) -> Dict:
        """获取涨跌统计"""
        result = {
            'advance': 0,
            'decline': 0,
            'flat': 0,
            'ratio': 1,
        }
        
        try:
            # 获取A股实时行情
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                # 统计涨跌
                pct_change = df['涨跌幅'].dropna()
                result['advance'] = len(pct_change[pct_change > 0])
                result['decline'] = len(pct_change[pct_change < 0])
                result['flat'] = len(pct_change[pct_change == 0])
                
                # 计算涨跌比
                if result['decline'] > 0:
                    result['ratio'] = result['advance'] / result['decline']
                else:
                    result['ratio'] = result['advance'] if result['advance'] > 0 else 1
                    
        except Exception as e:
            logger.error(f"获取涨跌统计失败: {e}")
        
        return result
    
    def _get_limit_stats(self) -> Dict:
        """获取涨跌停统计"""
        result = {
            'limit_up': 0,
            'limit_down': 0,
            'ratio': 1,
        }
        
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                pct_change = df['涨跌幅'].dropna()
                
                # 涨停（涨幅>=9.8%）
                result['limit_up'] = len(pct_change[pct_change >= 9.8])
                
                # 跌停（跌幅<=-9.8%）
                result['limit_down'] = len(pct_change[pct_change <= -9.8])
                
                # 涨跌停比
                if result['limit_down'] > 0:
                    result['ratio'] = result['limit_up'] / result['limit_down']
                else:
                    result['ratio'] = result['limit_up'] if result['limit_up'] > 0 else 1
                    
        except Exception as e:
            logger.error(f"获取涨跌停统计失败: {e}")
        
        return result
    
    def _calculate_sentiment_score(self, data: Dict) -> float:
        """计算情绪得分 (0-100)"""
        score = 50  # 基础分
        
        # 1. 指数涨跌得分
        indices = data.get('indices', {})
        if indices:
            avg_change = np.mean([v['change'] for v in indices.values()])
            if avg_change > 2:
                score += 20
            elif avg_change > 1:
                score += 10
            elif avg_change > 0:
                score += 5
            elif avg_change < -2:
                score -= 20
            elif avg_change < -1:
                score -= 10
            elif avg_change < 0:
                score -= 5
        
        # 2. 涨跌比得分
        ad = data.get('advance_decline', {})
        ratio = ad.get('ratio', 1)
        if ratio > 2:
            score += 15
        elif ratio > 1.5:
            score += 10
        elif ratio > 1:
            score += 5
        elif ratio < 0.5:
            score -= 15
        elif ratio < 0.67:
            score -= 10
        elif ratio < 1:
            score -= 5
        
        # 3. 涨跌停得分
        limits = data.get('limit_stats', {})
        limit_ratio = limits.get('ratio', 1)
        if limit_ratio > 3:
            score += 10
        elif limit_ratio > 2:
            score += 5
        elif limit_ratio < 0.33:
            score -= 10
        elif limit_ratio < 0.5:
            score -= 5
        
        return max(0, min(100, score))
    
    def _determine_sentiment_level(self, score: float) -> str:
        """判断情绪水平"""
        if score >= 80:
            return 'extreme_greed'
        elif score >= 65:
            return 'greed'
        elif score >= 45:
            return 'neutral'
        elif score >= 30:
            return 'fear'
        else:
            return 'extreme_fear'
    
    def _generate_signals(self, data: Dict) -> List[Dict]:
        """生成情绪信号"""
        signals = []
        
        score = data.get('sentiment_score', 50)
        level = data.get('sentiment_level', 'neutral')
        
        # 情绪极端信号
        if level == 'extreme_greed':
            signals.append({
                'type': 'warning',
                'signal': 'extreme_greed',
                'description': '市场极度贪婪，注意回调风险',
                'action': 'consider_profit_taking',
            })
        elif level == 'extreme_fear':
            signals.append({
                'type': 'opportunity',
                'signal': 'extreme_fear',
                'description': '市场极度恐慌，可能存在超跌反弹机会',
                'action': 'watch_for_bottom',
            })
        
        # 涨跌比信号
        ad = data.get('advance_decline', {})
        ratio = ad.get('ratio', 1)
        if ratio > 3:
            signals.append({
                'type': 'bullish',
                'signal': 'strong_advance',
                'description': f'涨跌比{ratio:.1f}，市场强势上涨',
                'action': 'trend_following',
            })
        elif ratio < 0.33:
            signals.append({
                'type': 'bearish',
                'signal': 'strong_decline',
                'description': f'涨跌比{ratio:.1f}，市场普跌',
                'action': 'defensive',
            })
        
        # 涨跌停信号
        limits = data.get('limit_stats', {})
        limit_up = limits.get('limit_up', 0)
        limit_down = limits.get('limit_down', 0)
        
        if limit_up > 50:
            signals.append({
                'type': 'bullish',
                'signal': 'limit_up_surge',
                'description': f'涨停{limit_up}家，市场活跃',
                'action': 'participate',
            })
        
        if limit_down > 50:
            signals.append({
                'type': 'bearish',
                'signal': 'limit_down_surge',
                'description': f'跌停{limit_down}家，市场恐慌',
                'action': 'avoid',
            })
        
        return signals
    
    def get_sentiment_history(self, days: int = 30) -> pd.DataFrame:
        """获取情绪历史数据（简化版）"""
        # 这里返回模拟数据，实际应用中应该从数据库获取
        dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
        np.random.seed(42)
        scores = np.random.normal(50, 15, days).clip(0, 100)
        
        df = pd.DataFrame({
            'date': dates,
            'sentiment_score': scores,
        })
        df['sentiment_level'] = df['sentiment_score'].apply(self._determine_sentiment_level)
        
        return df
    
    def format_sentiment_report(self, data: Dict) -> str:
        """格式化情绪报告"""
        report = []
        report.append("=" * 50)
        report.append("📊 市场情绪分析报告")
        report.append("=" * 50)
        report.append(f"分析时间: {data.get('timestamp', '')}")
        report.append("")
        
        # 情绪得分
        score = data.get('sentiment_score', 50)
        level = data.get('sentiment_level', 'neutral')
        
        level_names = {
            'extreme_greed': '极度贪婪',
            'greed': '贪婪',
            'neutral': '中性',
            'fear': '恐惧',
            'extreme_fear': '极度恐慌',
        }
        
        report.append("📈 情绪状态")
        report.append("-" * 30)
        report.append(f"情绪得分: {score:.1f}/100")
        report.append(f"情绪水平: {level_names.get(level, level)}")
        report.append("")
        
        # 指数概览
        indices = data.get('indices', {})
        if indices:
            report.append("📊 主要指数")
            report.append("-" * 30)
            for name, info in indices.items():
                change = info['change']
                direction = "↑" if change > 0 else "↓" if change < 0 else "→"
                report.append(f"{name}: {info['price']:.2f} ({direction}{abs(change):.2f}%)")
            report.append("")
        
        # 涨跌统计
        ad = data.get('advance_decline', {})
        if ad:
            report.append("📈 涨跌统计")
            report.append("-" * 30)
            report.append(f"上涨: {ad.get('advance', 0)}家")
            report.append(f"下跌: {ad.get('decline', 0)}家")
            report.append(f"平盘: {ad.get('flat', 0)}家")
            report.append(f"涨跌比: {ad.get('ratio', 1):.2f}")
            report.append("")
        
        # 涨跌停统计
        limits = data.get('limit_stats', {})
        if limits:
            report.append("🔒 涨跌停统计")
            report.append("-" * 30)
            report.append(f"涨停: {limits.get('limit_up', 0)}家")
            report.append(f"跌停: {limits.get('limit_down', 0)}家")
            report.append(f"涨跌停比: {limits.get('ratio', 1):.2f}")
            report.append("")
        
        # 信号
        signals = data.get('signals', [])
        if signals:
            report.append("⚡ 交易信号")
            report.append("-" * 30)
            for signal in signals:
                icon = "🔴" if signal['type'] == 'bearish' else "🟢" if signal['type'] == 'bullish' else "⚠️"
                report.append(f"{icon} {signal['description']}")
        
        report.append("")
        report.append("=" * 50)
        
        return "\n".join(report)


# 创建全局实例
sentiment_indicator = MarketSentimentIndicator()
