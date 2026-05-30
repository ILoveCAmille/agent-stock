#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合量化交易策略
整合五维度评分系统的买卖决策策略
支持多种交易模式：激进型、稳健型、保守型
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging
from quant_factors import QuantFactors


class ComprehensiveStrategy:
    """综合量化交易策略"""
    
    # 策略预设配置
    PRESETS = {
        'aggressive': {
            'name': '激进型策略',
            'description': '追求高收益，容忍较高回撤',
            'buy_score_threshold': 55,
            'sell_score_threshold': 42,
            'tech_min': 48,
            'fund_min': 45,
            'sent_min': 42,
            'atr_stop_mult': 2.5,
            'trailing_stop': True,
            'trailing_atr_mult': 2.0,
            'max_holding_days': 20,
            'take_profit_pct': 15.0,
            'stop_loss_pct': 8.0,
            'weights': {
                'technical': 0.35,
                'fund_flow': 0.25,
                'sentiment': 0.15,
                'macro_cycle': 0.10,
                'fundamental': 0.15,
            }
        },
        'balanced': {
            'name': '稳健型策略',
            'description': '收益与风险平衡',
            'buy_score_threshold': 57,
            'sell_score_threshold': 40,
            'tech_min': 50,
            'fund_min': 47,
            'sent_min': 44,
            'atr_stop_mult': 2.0,
            'trailing_stop': True,
            'trailing_atr_mult': 1.5,
            'max_holding_days': 15,
            'take_profit_pct': 12.0,
            'stop_loss_pct': 6.0,
            'weights': {
                'technical': 0.30,
                'fund_flow': 0.25,
                'sentiment': 0.15,
                'macro_cycle': 0.15,
                'fundamental': 0.15,
            }
        },
        'conservative': {
            'name': '保守型策略',
            'description': '优先控制风险，追求稳健收益',
            'buy_score_threshold': 60,
            'sell_score_threshold': 38,
            'tech_min': 53,
            'fund_min': 50,
            'sent_min': 46,
            'atr_stop_mult': 1.5,
            'trailing_stop': True,
            'trailing_atr_mult': 1.2,
            'max_holding_days': 10,
            'take_profit_pct': 8.0,
            'stop_loss_pct': 5.0,
            'weights': {
                'technical': 0.25,
                'fund_flow': 0.20,
                'sentiment': 0.15,
                'macro_cycle': 0.20,
                'fundamental': 0.20,
            }
        },
        # 市值风格策略
        'small_cap_momentum': {
            'name': '小市值动量策略',
            'description': '针对小市值/妖股：技术指标和情绪驱动，快进快出',
            'buy_score_threshold': 55,
            'sell_score_threshold': 43,
            'tech_min': 45,
            'fund_min': 42,
            'sent_min': 40,
            'atr_stop_mult': 3.0,
            'trailing_stop': True,
            'trailing_atr_mult': 2.5,
            'max_holding_days': 8,
            'take_profit_pct': 20.0,
            'stop_loss_pct': 10.0,
            'weights': {
                'technical': 0.40,
                'fund_flow': 0.20,
                'sentiment': 0.25,
                'macro_cycle': 0.05,
                'fundamental': 0.10,
            }
        },
        'large_cap_value': {
            'name': '大市值价值策略',
            'description': '针对大市值/蓝筹：基本面和宏观驱动，中长线持有',
            'buy_score_threshold': 58,
            'sell_score_threshold': 38,
            'tech_min': 48,
            'fund_min': 48,
            'sent_min': 38,
            'atr_stop_mult': 1.5,
            'trailing_stop': True,
            'trailing_atr_mult': 1.2,
            'max_holding_days': 30,
            'take_profit_pct': 10.0,
            'stop_loss_pct': 5.0,
            'weights': {
                'technical': 0.15,
                'fund_flow': 0.20,
                'sentiment': 0.05,
                'macro_cycle': 0.25,
                'fundamental': 0.35,
            }
        },
    }
    
    def __init__(self, preset: str = 'balanced', custom_params: Dict = None):
        """
        初始化策略
        
        Args:
            preset: 策略预设 ('aggressive', 'balanced', 'conservative')
            custom_params: 自定义参数覆盖
        """
        self.logger = logging.getLogger(__name__)
        
        if preset not in self.PRESETS:
            self.logger.warning(f"未知预设 '{preset}'，使用默认 'balanced'")
            preset = 'balanced'
        
        self.params = self.PRESETS[preset].copy()
        self.preset_name = preset
        
        # 应用自定义参数
        if custom_params:
            self.params.update(custom_params)
        
        # 内部状态
        self.holding_days = 0
        self.entry_price = 0
        self.max_price_since_entry = 0
    
    @staticmethod
    def comprehensive_strategy_fn(df: pd.DataFrame, i: int, position: int, params: Dict) -> int:
        """
        综合策略函数（用于回测引擎接口）
        
        Args:
            df: 包含五维度评分的DataFrame
            i: 当前索引
            position: 当前持仓
            params: 策略参数
        
        Returns:
            信号: 1=买入, -1=卖出, 0=持有
        """
        # 需要至少120天数据来计算指标
        if i < 120:
            return 0
        
        row = df.iloc[i]
        
        # 获取策略参数
        buy_threshold = params.get('buy_score_threshold', 65)
        sell_threshold = params.get('sell_score_threshold', 35)
        tech_min = params.get('tech_min', 55)
        fund_min = params.get('fund_min', 50)
        sent_min = params.get('sent_min', 40)
        max_holding = params.get('max_holding_days', 15)
        take_profit = params.get('take_profit_pct', 12.0)
        stop_loss = params.get('stop_loss_pct', 6.0)
        trailing_stop = params.get('trailing_stop', True)
        trailing_atr_mult = params.get('trailing_atr_mult', 1.5)
        
        # 获取评分
        comp_score = row.get('Score_Comprehensive', 50)
        tech_score = row.get('Score_Technical', 50)
        fund_score = row.get('Score_FundFlow', 50)
        sent_score = row.get('Score_Sentiment', 50)
        macro_score = row.get('Score_MacroCycle', 50)
        
        close = row['Close']
        atr = row.get('ATR', 0)
        
        # 管理持仓天数
        if 'holding_counter' not in params:
            params['holding_counter'] = 0
        if 'entry_price' not in params:
            params['entry_price'] = 0
        if 'max_price' not in params:
            params['max_price'] = 0
        
        if position > 0:
            params['holding_counter'] += 1
            if close > params['max_price']:
                params['max_price'] = close
        
        if position == 0:
            # ========== 买入条件 ==========
            # 条件1: 综合评分超过买入阈值
            # 条件2: 技术指标评分不低于最低要求
            # 条件3: 资金流向评分不低于最低要求
            # 条件4: 散户情绪评分不低于最低要求
            # 条件5: MACD金叉或RSI从超卖区回升（技术确认）
            
            score_ok = comp_score > buy_threshold
            tech_ok = tech_score > tech_min
            fund_ok = fund_score > fund_min
            sent_ok = sent_score > sent_min
            
            # 技术确认信号
            rsi = row.get('RSI_14', 50)
            macd = row.get('MACD', 0)
            macd_signal = row.get('MACD_signal', 0)
            
            # MACD金叉 或 RSI从超卖区回升
            if i > 0:
                prev_macd = df.iloc[i-1].get('MACD', 0)
                prev_macd_signal = df.iloc[i-1].get('MACD_signal', 0)
                prev_rsi = df.iloc[i-1].get('RSI_14', 50)
                
                macd_golden_cross = (prev_macd <= prev_macd_signal) and (macd > macd_signal)
                rsi_recovery = (prev_rsi < 35) and (rsi > prev_rsi)
                tech_confirm = macd_golden_cross or rsi_recovery or (rsi < 60 and rsi > 30)
            else:
                tech_confirm = True
            
            # 均线多头排列确认
            ma5 = row.get('MA5', 0) or df['Close'].rolling(5).mean().iloc[i]
            ma20 = row.get('MA20', 0) or df['Close'].rolling(20).mean().iloc[i]
            ma_trend = ma5 > ma20 if (ma5 and ma20) else True
            
            if score_ok and tech_ok and fund_ok and sent_ok and tech_confirm and ma_trend:
                params['holding_counter'] = 0
                params['entry_price'] = close
                params['max_price'] = close
                return 1
        
        else:
            # ========== 卖出条件 ==========
            entry_price = params['entry_price']
            max_price = params['max_price']
            holding_days = params['holding_counter']
            
            if entry_price <= 0:
                return 0
            
            profit_pct = (close - entry_price) / entry_price * 100
            
            # 条件1: 止盈
            if profit_pct >= take_profit:
                params['holding_counter'] = 0
                return -1
            
            # 条件2: 止损
            if profit_pct <= -stop_loss:
                params['holding_counter'] = 0
                return -1
            
            # 条件3: 追踪止损（从最高价回落超过ATR倍数）
            if trailing_stop and max_price > entry_price and atr > 0:
                trailing_stop_price = max_price - atr * trailing_atr_mult
                if close < trailing_stop_price and profit_pct > 0:
                    params['holding_counter'] = 0
                    return -1
            
            # 条件4: 最大持仓天数
            if holding_days >= max_holding:
                params['holding_counter'] = 0
                return -1
            
            # 条件5: 综合评分恶化
            if comp_score < sell_threshold:
                params['holding_counter'] = 0
                return -1
            
            # 条件6: 技术指标恶化（趋势反转）
            if tech_score < 30 and fund_score < 35:
                params['holding_counter'] = 0
                return -1
            
            # 条件7: RSI超买 + MACD死叉（强烈卖出信号）
            rsi = row.get('RSI_14', 50)
            macd = row.get('MACD', 0)
            macd_signal_val = row.get('MACD_signal', 0)
            if i > 0:
                prev_macd = df.iloc[i-1].get('MACD', 0)
                prev_macd_signal = df.iloc[i-1].get('MACD_signal', 0)
                macd_death_cross = (prev_macd >= prev_macd_signal) and (macd < macd_signal_val)
                
                if rsi > 75 and macd_death_cross:
                    params['holding_counter'] = 0
                    return -1
        
        return 0


class MultiStrategyComparator:
    """多策略对比器"""
    
    def __init__(self):
        self.strategies = {}
        self.results = {}
    
    def add_strategy(self, name: str, strategy_fn, params: Dict):
        """添加策略"""
        self.strategies[name] = {
            'fn': strategy_fn,
            'params': params
        }
    
    def add_all_presets(self):
        """添加所有预设策略"""
        for preset_name, config in ComprehensiveStrategy.PRESETS.items():
            params = {
                'buy_score_threshold': config['buy_score_threshold'],
                'sell_score_threshold': config['sell_score_threshold'],
                'tech_min': config['tech_min'],
                'fund_min': config['fund_min'],
                'sent_min': config['sent_min'],
                'atr_stop_mult': config['atr_stop_mult'],
                'trailing_stop': config['trailing_stop'],
                'trailing_atr_mult': config['trailing_atr_mult'],
                'max_holding_days': config['max_holding_days'],
                'take_profit_pct': config['take_profit_pct'],
                'stop_loss_pct': config['stop_loss_pct'],
            }
            self.add_strategy(
                config['name'],
                ComprehensiveStrategy.comprehensive_strategy_fn,
                params
            )
        
        # 添加原有的策略作为对比基准
        from strategy_optimizer import StrategyOptimizer
        self.add_strategy(
            '多因子复合(原)',
            StrategyOptimizer.multi_factor_strategy,
            {'buy_threshold': 70, 'sell_threshold': 30, 'rsi_upper': 70, 'rsi_lower': 30}
        )
        self.add_strategy(
            'MA均线交叉(原)',
            StrategyOptimizer.ma_cross_atr_strategy,
            {'fast_period': 5, 'slow_period': 20, 'atr_stop_mult': 2.0, 'holding_days': 5}
        )
    
    def run_comparison(self, df: pd.DataFrame, backtest_engine, params_override: Dict = None) -> Dict:
        """运行所有策略的对比"""
        from backtest_engine import BacktestEngine
        
        results = {}
        
        for name, strategy_info in self.strategies.items():
            fn = strategy_info['fn']
            params = strategy_info['params'].copy()
            if params_override:
                params.update(params_override)
            
            try:
                result = backtest_engine.run(df, fn, params)
                results[name] = result
            except Exception as e:
                logging.getLogger(__name__).error(f"策略 {name} 运行失败: {e}")
                continue
        
        return results


# 全局实例
comprehensive_strategy = ComprehensiveStrategy('balanced')