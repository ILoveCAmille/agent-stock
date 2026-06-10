"""
市场指数分析模块
分析A股大盘指数和板块指数，制定进攻/防守策略
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MarketIndexAnalyzer:
    """市场指数分析器"""
    
    # 核心指数配置
    CORE_INDICES = {
        '000001': {'name': '上证指数', 'symbol': 'sh000001', 'weight': 0.35},
        '399001': {'name': '深证成指', 'symbol': 'sz399001', 'weight': 0.25},
        '399006': {'name': '创业板指', 'symbol': 'sz399006', 'weight': 0.20},
        '000300': {'name': '沪深300', 'symbol': 'sh000300', 'weight': 0.15},
        '000905': {'name': '中证500', 'symbol': 'sh000905', 'weight': 0.05},
    }
    
    # 板块指数配置
    SECTOR_INDICES = {
        '399967': {'name': '中证军工', 'sector': '军工'},
        '399986': {'name': '中证银行', 'sector': '银行'},
        '399989': {'name': '中证医疗', 'sector': '医疗'},
        '399441': {'name': '生物医药', 'sector': '医药'},
        '399808': {'name': '中证新能', 'sector': '新能源'},
        '399396': {'name': '国证芯片', 'sector': '半导体'},
        '399363': {'name': '计算机指数', 'sector': '计算机'},
        '399417': {'name': '白酒指数', 'sector': '白酒'},
        '399440': {'name': '国证汽车', 'sector': '汽车'},
        '399365': {'name': '中证煤炭', 'sector': '煤炭'},
        '399371': {'name': '国证有色', 'sector': '有色金属'},
        '399373': {'name': '国证地产', 'sector': '房地产'},
        '399374': {'name': '国证传媒', 'sector': '传媒'},
        '399375': {'name': '国证证券', 'sector': '证券'},
        '399376': {'name': '国证食品', 'sector': '食品饮料'},
    }
    
    # 市场状态定义
    MARKET_STATES = {
        'STRONG_BULL': {'name': '强势牛市', 'strategy': 'aggressive', 'position': 0.8},
        'MILD_BULL': {'name': '温和牛市', 'strategy': 'offensive', 'position': 0.6},
        'SIDEWAYS': {'name': '震荡市', 'strategy': 'balanced', 'position': 0.5},
        'MILD_BEAR': {'name': '温和熊市', 'strategy': 'defensive', 'position': 0.3},
        'STRONG_BEAR': {'name': '强势熊市', 'strategy': 'conservative', 'position': 0.1},
    }
    
    def __init__(self):
        self._index_cache = {}
        self._cache_time = None
        self._cache_ttl = 300  # 5分钟缓存
    
    def get_realtime_indices(self, symbol: str = "沪深重要指数") -> Optional[pd.DataFrame]:
        """获取实时指数行情
        
        Args:
            symbol: 指数类别，可选 "沪深重要指数", "上证系列指数", "深证系列指数"
        """
        try:
            df = ak.stock_zh_index_spot_em(symbol=symbol)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取实时指数失败: {e}")
        
        # 备用：新浪数据源
        try:
            df = ak.stock_zh_index_spot_sina()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"新浪指数数据获取失败: {e}")
        
        return None
    
    def get_index_history(self, symbol: str, period: str = "daily", 
                          start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        """获取指数历史数据
        
        Args:
            symbol: 指数代码，如 "000001"
            period: 周期，daily/weekly/monthly
            start_date: 开始日期，格式 YYYYMMDD
            end_date: 结束日期，格式 YYYYMMDD
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        
        try:
            df = ak.index_zh_a_hist(symbol=symbol, period=period, 
                                     start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                # 标准化列名
                df = df.rename(columns={
                    '日期': 'date', '开盘': 'open', '收盘': 'close',
                    '最高': 'high', '最低': 'low', '成交量': 'volume',
                    '成交额': 'amount', '振幅': 'amplitude', '涨跌幅': 'pct_change',
                    '涨跌额': 'change', '换手率': 'turnover'
                })
                df['date'] = pd.to_datetime(df['date'])
                return df
        except Exception as e:
            logger.error(f"获取指数历史数据失败 {symbol}: {e}")
        
        return None
    
    def calculate_index_indicators(self, df: pd.DataFrame) -> Dict:
        """计算指数技术指标"""
        if df is None or df.empty or len(df) < 20:
            return {}
        
        try:
            close = df['close'].values
            volume = df['volume'].values if 'volume' in df.columns else None
            
            indicators = {}
            
            # 均线系统
            indicators['ma5'] = self._calc_ma(close, 5)
            indicators['ma10'] = self._calc_ma(close, 10)
            indicators['ma20'] = self._calc_ma(close, 20)
            indicators['ma60'] = self._calc_ma(close, 60)
            indicators['ma120'] = self._calc_ma(close, 120) if len(close) >= 120 else None
            
            # 当前价格
            indicators['current_price'] = close[-1]
            indicators['prev_close'] = close[-2] if len(close) > 1 else close[-1]
            
            # 涨跌幅
            if len(close) > 1:
                indicators['daily_change'] = ((close[-1] - close[-2]) / close[-2]) * 100
            
            # RSI
            indicators['rsi6'] = self._calc_rsi(close, 6)
            indicators['rsi14'] = self._calc_rsi(close, 14)
            
            # MACD
            macd, signal, hist = self._calc_macd(close)
            indicators['macd'] = macd
            indicators['macd_signal'] = signal
            indicators['macd_hist'] = hist
            
            # 布林带
            upper, middle, lower = self._calc_bollinger(close, 20)
            indicators['bb_upper'] = upper
            indicators['bb_middle'] = middle
            indicators['bb_lower'] = lower
            
            # 量比
            if volume is not None and len(volume) >= 5:
                indicators['volume_ratio'] = volume[-1] / np.mean(volume[-5:]) if np.mean(volume[-5:]) > 0 else 1
            
            # 均线多头/空头排列
            if all([indicators.get(f'ma{n}') for n in [5, 10, 20]]):
                indicators['ma_bullish'] = (indicators['ma5'] > indicators['ma10'] > indicators['ma20'])
                indicators['ma_bearish'] = (indicators['ma5'] < indicators['ma10'] < indicators['ma20'])
            
            # 趋势判断
            indicators['trend'] = self._determine_trend(indicators)
            
            return indicators
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
            return {}
    
    def _calc_ma(self, data: np.ndarray, period: int) -> Optional[float]:
        """计算移动平均线"""
        if len(data) < period:
            return None
        return np.mean(data[-period:])
    
    def _calc_rsi(self, data: np.ndarray, period: int = 14) -> Optional[float]:
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
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calc_macd(self, data: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple:
        """计算MACD"""
        if len(data) < slow + signal:
            return None, None, None
        
        ema_fast = self._ema(data, fast)
        ema_slow = self._ema(data, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return macd_line[-1], signal_line[-1], histogram[-1]
    
    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """计算指数移动平均"""
        multiplier = 2 / (period + 1)
        ema = np.zeros_like(data, dtype=float)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]
        return ema
    
    def _calc_bollinger(self, data: np.ndarray, period: int = 20, std_dev: int = 2) -> Tuple:
        """计算布林带"""
        if len(data) < period:
            return None, None, None
        
        middle = np.mean(data[-period:])
        std = np.std(data[-period:])
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        
        return upper, middle, lower
    
    def _determine_trend(self, indicators: Dict) -> str:
        """判断趋势"""
        ma_bullish = indicators.get('ma_bullish', False)
        ma_bearish = indicators.get('ma_bearish', False)
        rsi = indicators.get('rsi14', 50)
        macd_hist = indicators.get('macd_hist', 0)
        
        if ma_bullish and rsi > 60 and macd_hist > 0:
            return 'strong_up'
        elif ma_bullish or (rsi > 55 and macd_hist > 0):
            return 'up'
        elif ma_bearish and rsi < 40 and macd_hist < 0:
            return 'strong_down'
        elif ma_bearish or (rsi < 45 and macd_hist < 0):
            return 'down'
        else:
            return 'sideways'
    
    def analyze_market_state(self) -> Dict:
        """分析市场整体状态"""
        result = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'indices': {},
            'market_state': None,
            'strategy': None,
            'position_suggestion': 0.5,
            'signals': [],
            'sector_analysis': {},
        }
        
        # 1. 分析核心指数
        total_score = 0
        total_weight = 0
        
        for code, config in self.CORE_INDICES.items():
            df = self.get_index_history(code)
            if df is not None and not df.empty:
                indicators = self.calculate_index_indicators(df)
                if indicators:
                    # 计算指数得分
                    score = self._calculate_index_score(indicators)
                    result['indices'][code] = {
                        'name': config['name'],
                        'indicators': indicators,
                        'score': score,
                        'weight': config['weight'],
                    }
                    total_score += score * config['weight']
                    total_weight += config['weight']
        
        # 2. 计算综合得分
        if total_weight > 0:
            market_score = total_score / total_weight
        else:
            market_score = 50  # 默认中性
        
        # 3. 判断市场状态
        if market_score >= 80:
            state = 'STRONG_BULL'
        elif market_score >= 65:
            state = 'MILD_BULL'
        elif market_score >= 45:
            state = 'SIDEWAYS'
        elif market_score >= 30:
            state = 'MILD_BEAR'
        else:
            state = 'STRONG_BEAR'
        
        result['market_state'] = self.MARKET_STATES[state]
        result['market_score'] = market_score
        result['strategy'] = self.MARKET_STATES[state]['strategy']
        result['position_suggestion'] = self.MARKET_STATES[state]['position']
        
        # 4. 生成交易信号
        result['signals'] = self._generate_signals(result)
        
        return result
    
    def _calculate_index_score(self, indicators: Dict) -> float:
        """计算指数得分 (0-100)"""
        score = 50  # 基础分
        
        # 趋势得分
        trend = indicators.get('trend', 'sideways')
        trend_scores = {
            'strong_up': 20, 'up': 10, 'sideways': 0, 'down': -10, 'strong_down': -20
        }
        score += trend_scores.get(trend, 0)
        
        # RSI得分
        rsi = indicators.get('rsi14', 50)
        if rsi > 70:
            score -= 10  # 超买
        elif rsi > 60:
            score += 5
        elif rsi < 30:
            score += 10  # 超卖可能反弹
        elif rsi < 40:
            score -= 5
        
        # MACD得分
        macd_hist = indicators.get('macd_hist', 0)
        if macd_hist > 0:
            score += 10
        elif macd_hist < 0:
            score -= 10
        
        # 均线得分
        if indicators.get('ma_bullish'):
            score += 10
        elif indicators.get('ma_bearish'):
            score -= 10
        
        # 量比得分
        volume_ratio = indicators.get('volume_ratio', 1)
        if volume_ratio > 1.5:
            score += 5  # 放量
        elif volume_ratio < 0.5:
            score -= 5  # 缩量
        
        return max(0, min(100, score))
    
    def _generate_signals(self, market_result: Dict) -> List[Dict]:
        """生成交易信号"""
        signals = []
        
        strategy = market_result.get('strategy', 'balanced')
        market_score = market_result.get('market_score', 50)
        
        # 基于策略类型生成信号
        if strategy == 'aggressive':
            signals.append({
                'type': 'position',
                'action': 'increase',
                'description': '强势牛市，建议加仓至80%以上',
                'priority': 'high'
            })
            signals.append({
                'type': 'sector',
                'action': 'rotate_to_growth',
                'description': '关注成长股：科技、新能源、半导体',
                'priority': 'medium'
            })
        elif strategy == 'offensive':
            signals.append({
                'type': 'position',
                'action': 'moderate_increase',
                'description': '温和牛市，建议仓位60%左右',
                'priority': 'high'
            })
            signals.append({
                'type': 'sector',
                'action': 'balanced_allocation',
                'description': '均衡配置：成长+价值',
                'priority': 'medium'
            })
        elif strategy == 'balanced':
            signals.append({
                'type': 'position',
                'action': 'maintain',
                'description': '震荡市，建议仓位50%，精选个股',
                'priority': 'high'
            })
            signals.append({
                'type': 'sector',
                'action': 'defensive_growth',
                'description': '关注防御性成长：消费、医药',
                'priority': 'medium'
            })
        elif strategy == 'defensive':
            signals.append({
                'type': 'position',
                'action': 'decrease',
                'description': '温和熊市，建议减仓至30%以下',
                'priority': 'high'
            })
            signals.append({
                'type': 'sector',
                'action': 'defensive',
                'description': '转向防御：银行、公用事业、高股息',
                'priority': 'medium'
            })
        elif strategy == 'conservative':
            signals.append({
                'type': 'position',
                'action': 'minimize',
                'description': '强势熊市，建议仓位10%以下或空仓',
                'priority': 'high'
            })
            signals.append({
                'type': 'sector',
                'action': 'cash_is_king',
                'description': '现金为王，等待市场企稳',
                'priority': 'high'
            })
        
        # 指数信号
        for code, data in market_result.get('indices', {}).items():
            indicators = data.get('indicators', {})
            if indicators.get('rsi14', 50) < 30:
                signals.append({
                    'type': 'index_oversold',
                    'index': data['name'],
                    'action': 'watch_for_bottom',
                    'description': f'{data["name"]} RSI={indicators["rsi14"]:.1f}，超卖区域，关注反弹机会',
                    'priority': 'medium'
                })
            elif indicators.get('rsi14', 50) > 70:
                signals.append({
                    'type': 'index_overbought',
                    'index': data['name'],
                    'action': 'caution',
                    'description': f'{data["name"]} RSI={indicators["rsi14"]:.1f}，超买区域，注意回调风险',
                    'priority': 'medium'
                })
        
        return signals
    
    def analyze_sector_rotation(self) -> Dict:
        """分析板块轮动"""
        result = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'strong_sectors': [],
            'weak_sectors': [],
            'rotation_signal': None,
            'recommendations': [],
        }
        
        sector_scores = []
        
        for code, config in self.SECTOR_INDICES.items():
            df = self.get_index_history(code)
            if df is not None and not df.empty and len(df) >= 20:
                indicators = self.calculate_index_indicators(df)
                if indicators:
                    # 计算近5日、10日、20日涨跌幅
                    close = df['close'].values
                    pct_5d = ((close[-1] - close[-6]) / close[-6] * 100) if len(close) > 5 else 0
                    pct_10d = ((close[-1] - close[-11]) / close[-11] * 100) if len(close) > 10 else 0
                    pct_20d = ((close[-1] - close[-21]) / close[-21] * 100) if len(close) > 20 else 0
                    
                    score = self._calculate_index_score(indicators)
                    
                    sector_scores.append({
                        'code': code,
                        'name': config['name'],
                        'sector': config['sector'],
                        'score': score,
                        'pct_5d': pct_5d,
                        'pct_10d': pct_10d,
                        'pct_20d': pct_20d,
                        'trend': indicators.get('trend', 'sideways'),
                        'rsi': indicators.get('rsi14', 50),
                    })
        
        # 按得分排序
        sector_scores.sort(key=lambda x: x['score'], reverse=True)
        
        # 强势板块（得分>60）
        result['strong_sectors'] = [s for s in sector_scores if s['score'] > 60][:5]
        
        # 弱势板块（得分<40）
        result['weak_sectors'] = [s for s in sector_scores if s['score'] < 40][-5:]
        
        # 板块轮动信号
        if len(result['strong_sectors']) >= 3:
            result['rotation_signal'] = 'active'
            result['recommendations'].append('板块轮动活跃，关注强势板块延续性')
        elif len(result['weak_sectors']) >= 3:
            result['rotation_signal'] = 'weak'
            result['recommendations'].append('多数板块弱势，建议防御为主')
        else:
            result['rotation_signal'] = 'neutral'
            result['recommendations'].append('板块分化，精选个股为主')
        
        return result
    
    def get_offensive_defensive_strategy(self) -> Dict:
        """获取进攻/防守策略建议"""
        # 分析市场状态
        market_state = self.analyze_market_state()
        
        # 分析板块轮动
        sector_rotation = self.analyze_sector_rotation()
        
        # 综合策略
        strategy = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'market_state': market_state,
            'sector_rotation': sector_rotation,
            'overall_strategy': self._determine_overall_strategy(market_state, sector_rotation),
            'position_advice': self._get_position_advice(market_state),
            'sector_advice': self._get_sector_advice(sector_rotation),
            'risk_warnings': self._get_risk_warnings(market_state, sector_rotation),
        }
        
        return strategy
    
    def _determine_overall_strategy(self, market_state: Dict, sector_rotation: Dict) -> Dict:
        """确定整体策略"""
        market_score = market_state.get('market_score', 50)
        rotation_signal = sector_rotation.get('rotation_signal', 'neutral')
        
        # 综合判断
        if market_score >= 70 and rotation_signal == 'active':
            strategy_type = 'aggressive_offensive'
            description = '强势进攻：市场向好，板块轮动活跃，积极参与'
            risk_level = 'high'
        elif market_score >= 60:
            strategy_type = 'moderate_offensive'
            description = '温和进攻：市场偏强，适度加仓，关注主线'
            risk_level = 'medium'
        elif market_score >= 40:
            strategy_type = 'balanced'
            description = '攻守平衡：市场震荡，精选个股，控制仓位'
            risk_level = 'medium'
        elif market_score >= 30:
            strategy_type = 'moderate_defensive'
            description = '温和防守：市场偏弱，减仓为主，配置防御'
            risk_level = 'low'
        else:
            strategy_type = 'strong_defensive'
            description = '强势防守：市场弱势，轻仓或空仓，等待机会'
            risk_level = 'very_low'
        
        return {
            'type': strategy_type,
            'description': description,
            'risk_level': risk_level,
            'market_score': market_score,
        }
    
    def _get_position_advice(self, market_state: Dict) -> Dict:
        """获取仓位建议"""
        position = market_state.get('position_suggestion', 0.5)
        strategy = market_state.get('strategy', 'balanced')
        
        return {
            'suggested_position': position,
            'strategy': strategy,
            'description': f'建议总仓位：{position*100:.0f}%',
            'details': {
                'core_position': position * 0.6,  # 核心仓位
                'satellite_position': position * 0.3,  # 卫星仓位
                'cash_reserve': 1 - position,  # 现金储备
            }
        }
    
    def _get_sector_advice(self, sector_rotation: Dict) -> List[Dict]:
        """获取板块建议"""
        advice = []
        
        strong = sector_rotation.get('strong_sectors', [])
        weak = sector_rotation.get('weak_sectors', [])
        
        if strong:
            advice.append({
                'action': 'increase',
                'sectors': [s['name'] for s in strong[:3]],
                'description': f'建议增配：{", ".join([s["name"] for s in strong[:3]])}'
            })
        
        if weak:
            advice.append({
                'action': 'decrease',
                'sectors': [s['name'] for s in weak[:3]],
                'description': f'建议减配：{", ".join([s["name"] for s in weak[:3]])}'
            })
        
        return advice
    
    def _get_risk_warnings(self, market_state: Dict, sector_rotation: Dict) -> List[str]:
        """获取风险提示"""
        warnings = []
        
        market_score = market_state.get('market_score', 50)
        
        if market_score < 30:
            warnings.append('市场处于弱势区域，注意控制风险')
        
        if market_score > 80:
            warnings.append('市场过热，注意回调风险')
        
        # 检查指数RSI
        for code, data in market_state.get('indices', {}).items():
            rsi = data.get('indicators', {}).get('rsi14')
            if rsi and rsi > 75:
                warnings.append(f'{data["name"]} RI超买({rsi:.1f})，短期注意回调')
        
        return warnings


# 创建全局实例
market_analyzer = MarketIndexAnalyzer()
