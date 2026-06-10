"""
进攻/防守策略引擎
基于市场指数和板块指数制定动态策略
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import json

logger = logging.getLogger(__name__)


class OffensiveDefensiveStrategy:
    """进攻/防守策略引擎"""
    
    # 策略配置
    STRATEGIES = {
        'aggressive_offensive': {
            'name': '激进进攻',
            'description': '市场强势向上，积极参与成长股',
            'position_range': (0.7, 0.9),
            'sector_focus': ['科技', '半导体', '新能源', '军工'],
            'stop_loss': 0.08,
            'take_profit': 0.20,
            'holding_period': 'short_term',
        },
        'moderate_offensive': {
            'name': '稳健进攻',
            'description': '市场偏强，均衡配置成长与价值',
            'position_range': (0.5, 0.7),
            'sector_focus': ['消费', '医药', '科技', '金融'],
            'stop_loss': 0.06,
            'take_profit': 0.15,
            'holding_period': 'medium_term',
        },
        'balanced': {
            'name': '攻守平衡',
            'description': '市场震荡，精选个股，控制仓位',
            'position_range': (0.4, 0.6),
            'sector_focus': ['消费', '医药', '公用事业'],
            'stop_loss': 0.05,
            'take_profit': 0.12,
            'holding_period': 'medium_term',
        },
        'moderate_defensive': {
            'name': '稳健防守',
            'description': '市场偏弱，减仓防御，配置高股息',
            'position_range': (0.2, 0.4),
            'sector_focus': ['银行', '公用事业', '高股息'],
            'stop_loss': 0.04,
            'take_profit': 0.08,
            'holding_period': 'long_term',
        },
        'strong_defensive': {
            'name': '强势防守',
            'description': '市场弱势，轻仓或空仓等待',
            'position_range': (0.0, 0.2),
            'sector_focus': ['现金', '国债'],
            'stop_loss': 0.03,
            'take_profit': 0.05,
            'holding_period': 'cash',
        },
    }
    
    # 板块分类
    SECTOR_CATEGORY = {
        'offensive': ['科技', '半导体', '新能源', '军工', '计算机', '传媒'],
        'defensive': ['银行', '公用事业', '医药', '食品饮料', '白酒'],
        'cyclical': ['煤炭', '有色金属', '房地产', '证券', '汽车'],
        'growth': ['新能源', '半导体', '计算机', '生物医药'],
    }
    
    def __init__(self):
        self.market_analyzer = None
        self._init_analyzer()
    
    def _init_analyzer(self):
        """初始化市场分析器"""
        try:
            from market_index_analyzer import market_analyzer
            self.market_analyzer = market_analyzer
        except ImportError:
            logger.error("无法导入市场分析器")
    
    def analyze_and_recommend(self) -> Dict:
        """分析市场并给出策略建议"""
        result = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'market_analysis': None,
            'strategy': None,
            'position_advice': None,
            'sector_advice': None,
            'stock_suggestions': [],
            'risk_management': None,
            'action_items': [],
        }
        
        if not self.market_analyzer:
            result['error'] = '市场分析器未初始化'
            return result
        
        try:
            # 1. 获取市场分析
            strategy_result = self.market_analyzer.get_offensive_defensive_strategy()
            result['market_analysis'] = strategy_result
            
            # 2. 确定策略
            overall_strategy = strategy_result.get('overall_strategy', {})
            strategy_type = overall_strategy.get('type', 'balanced')
            result['strategy'] = self.STRATEGIES.get(strategy_type, self.STRATEGIES['balanced'])
            result['strategy']['type'] = strategy_type
            
            # 3. 仓位建议
            result['position_advice'] = strategy_result.get('position_advice', {})
            
            # 4. 板块建议
            result['sector_advice'] = self._generate_sector_advice(strategy_result)
            
            # 5. 选股建议
            result['stock_suggestions'] = self._generate_stock_suggestions(strategy_result)
            
            # 6. 风险管理
            result['risk_management'] = self._generate_risk_management(strategy_result)
            
            # 7. 行动项
            result['action_items'] = self._generate_action_items(strategy_result)
            
        except Exception as e:
            logger.error(f"策略分析失败: {e}")
            result['error'] = str(e)
        
        return result
    
    def _generate_sector_advice(self, strategy_result: Dict) -> Dict:
        """生成板块建议"""
        market_state = strategy_result.get('market_state', {})
        sector_rotation = strategy_result.get('sector_rotation', {})
        strategy_type = strategy_result.get('overall_strategy', {}).get('type', 'balanced')
        
        strategy_config = self.STRATEGIES.get(strategy_type, self.STRATEGIES['balanced'])
        
        advice = {
            'focus_sectors': strategy_config['sector_focus'],
            'strong_sectors': [],
            'weak_sectors': [],
            'rotation_advice': [],
        }
        
        # 强势板块
        strong = sector_rotation.get('strong_sectors', [])
        if strong:
            advice['strong_sectors'] = [
                {
                    'name': s['name'],
                    'score': s['score'],
                    'trend': s['trend'],
                    'pct_5d': f"{s['pct_5d']:.2f}%",
                }
                for s in strong[:5]
            ]
        
        # 弱势板块
        weak = sector_rotation.get('weak_sectors', [])
        if weak:
            advice['weak_sectors'] = [
                {
                    'name': s['name'],
                    'score': s['score'],
                    'trend': s['trend'],
                    'pct_5d': f"{s['pct_5d']:.2f}%",
                }
                for s in weak[:5]
            ]
        
        # 轮动建议
        rotation_signal = sector_rotation.get('rotation_signal', 'neutral')
        if rotation_signal == 'active':
            advice['rotation_advice'].append('板块轮动活跃，可跟随强势板块轮动操作')
        elif rotation_signal == 'weak':
            advice['rotation_advice'].append('板块普跌，建议减少操作，等待企稳')
        
        return advice
    
    def _generate_stock_suggestions(self, strategy_result: Dict) -> List[Dict]:
        """生成选股建议"""
        suggestions = []
        
        overall_strategy = strategy_result.get('overall_strategy', {})
        strategy_type = overall_strategy.get('type', 'balanced')
        strategy_config = self.STRATEGIES.get(strategy_type, self.STRATEGIES['balanced'])
        
        # 基于策略类型生成选股建议
        focus_sectors = strategy_config['sector_focus']
        
        for sector in focus_sectors[:3]:  # 只取前3个板块
            suggestions.append({
                'sector': sector,
                'strategy': strategy_config['name'],
                'criteria': self._get_stock_criteria(strategy_type, sector),
                'examples': self._get_example_stocks(sector),
            })
        
        return suggestions
    
    def _get_stock_criteria(self, strategy_type: str, sector: str) -> Dict:
        """获取选股标准"""
        if strategy_type in ['aggressive_offensive', 'moderate_offensive']:
            return {
                'pe_range': (10, 40),
                'pb_range': (1, 5),
                'roe_min': 10,
                'revenue_growth_min': 15,
                'profit_growth_min': 20,
                'focus': '成长性',
            }
        elif strategy_type == 'balanced':
            return {
                'pe_range': (8, 30),
                'pb_range': (1, 4),
                'roe_min': 12,
                'revenue_growth_min': 10,
                'profit_growth_min': 15,
                'focus': '均衡',
            }
        else:  # defensive
            return {
                'pe_range': (5, 15),
                'pb_range': (0.5, 2),
                'roe_min': 8,
                'dividend_yield_min': 3,
                'focus': '高股息低估值',
            }
    
    def _get_example_stocks(self, sector: str) -> List[str]:
        """获取示例股票（仅供参考）"""
        examples = {
            '科技': ['立讯精密', '海康威视', '中兴通讯'],
            '半导体': ['韦尔股份', '北方华创', '中芯国际'],
            '新能源': ['宁德时代', '比亚迪', '隆基绿能'],
            '军工': ['中航沈飞', '航发动力', '紫光国微'],
            '消费': ['贵州茅台', '五粮液', '海天味业'],
            '医药': ['恒瑞医药', '迈瑞医疗', '药明康德'],
            '银行': ['招商银行', '工商银行', '建设银行'],
            '公用事业': ['长江电力', '华能国际', '国投电力'],
            '高股息': ['中国神华', '格力电器', '双汇发展'],
            '白酒': ['贵州茅台', '五粮液', '泸州老窖'],
            '计算机': ['用友网络', '金山办公', '广联达'],
            '汽车': ['比亚迪', '长城汽车', '长安汽车'],
            '证券': ['中信证券', '东方财富', '华泰证券'],
        }
        return examples.get(sector, [])
    
    def _generate_risk_management(self, strategy_result: Dict) -> Dict:
        """生成风险管理建议"""
        overall_strategy = strategy_result.get('overall_strategy', {})
        strategy_type = overall_strategy.get('type', 'balanced')
        strategy_config = self.STRATEGIES.get(strategy_type, self.STRATEGIES['balanced'])
        
        market_state = strategy_result.get('market_state', {})
        market_score = market_state.get('market_score', 50)
        
        risk_management = {
            'stop_loss': strategy_config['stop_loss'],
            'take_profit': strategy_config['take_profit'],
            'max_position_per_stock': 0.2 if strategy_type != 'strong_defensive' else 0.1,
            'holding_period': strategy_config['holding_period'],
            'risk_level': overall_strategy.get('risk_level', 'medium'),
            'warnings': [],
        }
        
        # 风险提示
        if market_score > 75:
            risk_management['warnings'].append('市场过热，注意控制追高风险')
        elif market_score < 35:
            risk_management['warnings'].append('市场弱势，注意止损纪律')
        
        # 板块风险
        sector_rotation = strategy_result.get('sector_rotation', {})
        weak_sectors = sector_rotation.get('weak_sectors', [])
        if len(weak_sectors) > 3:
            risk_management['warnings'].append('多数板块弱势，注意系统性风险')
        
        return risk_management
    
    def _generate_action_items(self, strategy_result: Dict) -> List[Dict]:
        """生成行动项"""
        items = []
        
        overall_strategy = strategy_result.get('overall_strategy', {})
        strategy_type = overall_strategy.get('type', 'balanced')
        market_state = strategy_result.get('market_state', {})
        position_advice = strategy_result.get('position_advice', {})
        
        # 仓位调整
        suggested_position = position_advice.get('suggested_position', 0.5)
        items.append({
            'priority': 'high',
            'action': '调整仓位',
            'description': f'建议总仓位调整至{suggested_position*100:.0f}%',
            'details': position_advice,
        })
        
        # 板块调整
        sector_rotation = strategy_result.get('sector_rotation', {})
        strong = sector_rotation.get('strong_sectors', [])
        weak = sector_rotation.get('weak_sectors', [])
        
        if strong:
            items.append({
                'priority': 'medium',
                'action': '增配板块',
                'description': f'关注强势板块：{", ".join([s["name"] for s in strong[:3]])}',
                'details': strong[:3],
            })
        
        if weak:
            items.append({
                'priority': 'medium',
                'action': '减配板块',
                'description': f'规避弱势板块：{", ".join([s["name"] for s in weak[:3]])}',
                'details': weak[:3],
            })
        
        # 风险管理
        risk_management = self._generate_risk_management(strategy_result)
        if risk_management.get('warnings'):
            for warning in risk_management['warnings']:
                items.append({
                    'priority': 'high',
                    'action': '风险提示',
                    'description': warning,
                })
        
        return items
    
    def format_strategy_report(self, strategy_result: Dict) -> str:
        """格式化策略报告"""
        if not strategy_result:
            return "策略分析失败"
        
        report = []
        report.append("=" * 60)
        report.append("📊 市场策略分析报告")
        report.append("=" * 60)
        report.append(f"分析时间: {strategy_result.get('timestamp', '')}")
        report.append("")
        
        # 市场状态
        market_analysis = strategy_result.get('market_analysis', {})
        market_state = market_analysis.get('market_state', {})
        market_score = market_analysis.get('market_score', 50)
        
        report.append("📈 市场状态")
        report.append("-" * 40)
        report.append(f"市场得分: {market_score:.1f}/100")
        report.append(f"市场状态: {market_state.get('name', '未知')}")
        report.append("")
        
        # 策略建议
        strategy = strategy_result.get('strategy', {})
        report.append("🎯 策略建议")
        report.append("-" * 40)
        report.append(f"策略类型: {strategy.get('name', '未知')}")
        report.append(f"策略描述: {strategy.get('description', '')}")
        report.append("")
        
        # 仓位建议
        position_advice = strategy_result.get('position_advice', {})
        report.append("💰 仓位建议")
        report.append("-" * 40)
        report.append(f"建议仓位: {position_advice.get('suggested_position', 0.5)*100:.0f}%")
        details = position_advice.get('details', {})
        report.append(f"核心仓位: {details.get('core_position', 0)*100:.0f}%")
        report.append(f"卫星仓位: {details.get('satellite_position', 0)*100:.0f}%")
        report.append(f"现金储备: {details.get('cash_reserve', 0)*100:.0f}%")
        report.append("")
        
        # 板块建议
        sector_advice = strategy_result.get('sector_advice', {})
        report.append("📊 板块建议")
        report.append("-" * 40)
        report.append(f"关注板块: {', '.join(sector_advice.get('focus_sectors', []))}")
        
        strong = sector_advice.get('strong_sectors', [])
        if strong:
            report.append("\n强势板块:")
            for s in strong[:3]:
                report.append(f"  • {s['name']}: 得分{s['score']}, 5日涨幅{s['pct_5d']}")
        
        weak = sector_advice.get('weak_sectors', [])
        if weak:
            report.append("\n弱势板块:")
            for s in weak[:3]:
                report.append(f"  • {s['name']}: 得分{s['score']}, 5日涨幅{s['pct_5d']}")
        report.append("")
        
        # 风险管理
        risk_management = strategy_result.get('risk_management', {})
        report.append("⚠️ 风险管理")
        report.append("-" * 40)
        report.append(f"止损线: {risk_management.get('stop_loss', 0)*100:.1f}%")
        report.append(f"止盈线: {risk_management.get('take_profit', 0)*100:.1f}%")
        report.append(f"单股最大仓位: {risk_management.get('max_position_per_stock', 0.2)*100:.0f}%")
        
        warnings = risk_management.get('warnings', [])
        if warnings:
            report.append("\n风险提示:")
            for w in warnings:
                report.append(f"  ⚠️ {w}")
        report.append("")
        
        # 行动项
        action_items = strategy_result.get('action_items', [])
        if action_items:
            report.append("📋 行动项")
            report.append("-" * 40)
            for item in action_items:
                priority = "🔴" if item.get('priority') == 'high' else "🟡"
                report.append(f"{priority} {item['action']}: {item['description']}")
        
        report.append("")
        report.append("=" * 60)
        report.append("⚠️ 免责声明: 以上分析仅供参考，不构成投资建议")
        report.append("=" * 60)
        
        return "\n".join(report)


# 创建全局实例
strategy_engine = OffensiveDefensiveStrategy()
