"""
因子评估器
评估因子的：回撤、收益率稳定性、月度收益稳定性
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class FactorEvaluator:
    """因子评估器"""
    
    def __init__(self):
        pass
    
    def evaluate_factor(self, factor_values: pd.Series, returns: pd.Series, 
                        periods: int = 252) -> Dict:
        """评估单个因子的表现"""
        if factor_values.empty or returns.empty:
            return self._empty_evaluation()
        
        try:
            # 对齐数据
            aligned_data = pd.DataFrame({
                'factor': factor_values,
                'return': returns
            }).dropna()
            
            if len(aligned_data) < 60:  # 至少需要60天数据
                return self._empty_evaluation()
            
            # 1. 计算因子收益率
            factor_returns = self._calculate_factor_returns(aligned_data)
            
            # 2. 计算各项指标
            annual_return = self._calculate_annual_return(factor_returns)
            annual_vol = self._calculate_annual_volatility(factor_returns)
            sharpe_ratio = self._calculate_sharpe_ratio(annual_return, annual_vol)
            max_drawdown = self._calculate_max_drawdown(factor_returns)
            calmar_ratio = self._calculate_calmar_ratio(annual_return, max_drawdown)
            
            # 3. 稳定性指标
            return_stability = self._calculate_return_stability(factor_returns)
            monthly_stability = self._calculate_monthly_stability(factor_returns)
            win_rate = self._calculate_win_rate(factor_returns)
            
            # 4. 信息系数
            ic_mean, ic_std, icir = self._calculate_ic(aligned_data)
            
            # 5. 分组收益
            quintile_returns = self._calculate_quintile_returns(aligned_data)
            
            return {
                'annual_return': annual_return,
                'annual_vol': annual_vol,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'calmar_ratio': calmar_ratio,
                'return_stability': return_stability,
                'monthly_stability': monthly_stability,
                'win_rate': win_rate,
                'ic_mean': ic_mean,
                'ic_std': ic_std,
                'icir': icir,
                'quintile_returns': quintile_returns,
                'data_points': len(aligned_data),
            }
            
        except Exception as e:
            logger.error(f"因子评估失败: {e}")
            return self._empty_evaluation()
    
    def _empty_evaluation(self) -> Dict:
        """空评估结果"""
        return {
            'annual_return': 0,
            'annual_vol': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'calmar_ratio': 0,
            'return_stability': 0,
            'monthly_stability': 0,
            'win_rate': 0,
            'ic_mean': 0,
            'ic_std': 0,
            'icir': 0,
            'quintile_returns': {},
            'data_points': 0,
        }
    
    def _calculate_factor_returns(self, data: pd.DataFrame) -> pd.Series:
        """计算因子收益率（多空组合）"""
        # 按因子值分组
        data['factor_group'] = pd.qcut(data['factor'], 5, labels=False, duplicates='drop')
        
        # 计算每组平均收益
        group_returns = data.groupby('factor_group')['return'].mean()
        
        # 多空收益 = 最高组 - 最低组
        if len(group_returns) >= 2:
            long_short_return = group_returns.iloc[-1] - group_returns.iloc[0]
        else:
            long_short_return = data['return'].mean()
        
        # 返回每日因子收益序列
        data['factor_return'] = data['return'] * (data['factor'] - data['factor'].mean()) / data['factor'].std()
        
        return data['factor_return'].dropna()
    
    def _calculate_annual_return(self, returns: pd.Series) -> float:
        """计算年化收益率"""
        if returns.empty:
            return 0
        cumulative = (1 + returns).prod()
        n_years = len(returns) / 252
        if n_years <= 0:
            return 0
        return cumulative ** (1 / n_years) - 1
    
    def _calculate_annual_volatility(self, returns: pd.Series) -> float:
        """计算年化波动率"""
        if returns.empty:
            return 0
        return returns.std() * np.sqrt(252)
    
    def _calculate_sharpe_ratio(self, annual_return: float, annual_vol: float, 
                                 rf: float = 0.03) -> float:
        """计算夏普比率"""
        if annual_vol == 0:
            return 0
        return (annual_return - rf) / annual_vol
    
    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """计算最大回撤"""
        if returns.empty:
            return 0
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return abs(drawdown.min())
    
    def _calculate_calmar_ratio(self, annual_return: float, max_drawdown: float) -> float:
        """计算卡尔玛比率"""
        if max_drawdown == 0:
            return 0
        return annual_return / max_drawdown
    
    def _calculate_return_stability(self, returns: pd.Series) -> float:
        """计算收益稳定性（滚动20日收益的标准差的倒数）"""
        if returns.empty or len(returns) < 20:
            return 0
        
        rolling_returns = returns.rolling(20).mean()
        stability = 1 / (1 + rolling_returns.std())
        
        return stability
    
    def _calculate_monthly_stability(self, returns: pd.Series) -> float:
        """计算月度收益稳定性"""
        if returns.empty or len(returns) < 60:
            return 0
        
        # 按月分组
        returns.index = pd.to_datetime(returns.index)
        monthly_returns = returns.resample('M').sum()
        
        if len(monthly_returns) < 3:
            return 0
        
        # 月度收益为正的比例
        positive_months = (monthly_returns > 0).sum()
        total_months = len(monthly_returns)
        
        # 月度收益的变异系数
        cv = monthly_returns.std() / abs(monthly_returns.mean()) if monthly_returns.mean() != 0 else 1
        
        # 稳定性 = 正收益月比例 / (1 + 变异系数)
        stability = (positive_months / total_months) / (1 + cv)
        
        return stability
    
    def _calculate_win_rate(self, returns: pd.Series) -> float:
        """计算胜率"""
        if returns.empty:
            return 0
        return (returns > 0).mean()
    
    def _calculate_ic(self, data: pd.DataFrame) -> Tuple[float, float, float]:
        """计算信息系数 (IC)"""
        try:
            # 计算每日IC
            daily_ic = []
            
            # 按日期分组计算IC
            if 'date' in data.columns:
                for date, group in data.groupby('date'):
                    if len(group) >= 10:
                        ic = group['factor'].corr(group['return'])
                        daily_ic.append(ic)
            else:
                # 如果没有日期列，使用滚动IC
                for i in range(0, len(data) - 20, 5):
                    window = data.iloc[i:i+20]
                    if len(window) >= 10:
                        ic = window['factor'].corr(window['return'])
                        daily_ic.append(ic)
            
            if not daily_ic:
                return 0, 0, 0
            
            ic_series = pd.Series(daily_ic)
            ic_mean = ic_series.mean()
            ic_std = ic_series.std()
            icir = ic_mean / ic_std if ic_std > 0 else 0
            
            return ic_mean, ic_std, icir
            
        except Exception as e:
            logger.error(f"计算IC失败: {e}")
            return 0, 0, 0
    
    def _calculate_quintile_returns(self, data: pd.DataFrame) -> Dict:
        """计算分组收益"""
        try:
            data['factor_group'] = pd.qcut(data['factor'], 5, labels=False, duplicates='drop')
            group_returns = data.groupby('factor_group')['return'].mean()
            
            quintile_names = ['Q1 (Low)', 'Q2', 'Q3', 'Q4', 'Q5 (High)']
            result = {}
            
            for i, (group, ret) in enumerate(group_returns.items()):
                if i < len(quintile_names):
                    result[quintile_names[i]] = ret
            
            return result
            
        except Exception as e:
            logger.error(f"计算分组收益失败: {e}")
            return {}
    
    def rank_factors(self, evaluations: Dict[str, Dict]) -> pd.DataFrame:
        """对因子进行排名"""
        data = []
        
        for factor_name, eval_result in evaluations.items():
            if eval_result['data_points'] > 0:
                # 计算综合得分
                score = self._calculate_composite_score(eval_result)
                
                data.append({
                    'factor': factor_name,
                    'annual_return': eval_result['annual_return'],
                    'sharpe_ratio': eval_result['sharpe_ratio'],
                    'max_drawdown': eval_result['max_drawdown'],
                    'calmar_ratio': eval_result['calmar_ratio'],
                    'return_stability': eval_result['return_stability'],
                    'monthly_stability': eval_result['monthly_stability'],
                    'win_rate': eval_result['win_rate'],
                    'ic_mean': eval_result['ic_mean'],
                    'icir': eval_result['icir'],
                    'composite_score': score,
                })
        
        df = pd.DataFrame(data)
        
        if not df.empty:
            df = df.sort_values('composite_score', ascending=False)
            df['rank'] = range(1, len(df) + 1)
        
        return df
    
    def _calculate_composite_score(self, eval_result: Dict) -> float:
        """计算综合得分"""
        # 权重配置
        weights = {
            'sharpe_ratio': 0.20,
            'calmar_ratio': 0.15,
            'return_stability': 0.20,
            'monthly_stability': 0.20,
            'win_rate': 0.10,
            'icir': 0.15,
        }
        
        score = 0
        
        # 夏普比率（标准化到0-1）
        sharpe = min(max(eval_result['sharpe_ratio'], 0), 3) / 3
        score += sharpe * weights['sharpe_ratio']
        
        # 卡尔玛比率（标准化到0-1）
        calmar = min(max(eval_result['calmar_ratio'], 0), 5) / 5
        score += calmar * weights['calmar_ratio']
        
        # 收益稳定性
        score += eval_result['return_stability'] * weights['return_stability']
        
        # 月度稳定性
        score += eval_result['monthly_stability'] * weights['monthly_stability']
        
        # 胜率
        score += eval_result['win_rate'] * weights['win_rate']
        
        # ICIR（标准化到0-1）
        icir = min(max(eval_result['icir'], 0), 2) / 2
        score += icir * weights['icir']
        
        return score


# 创建全局实例
factor_evaluator = FactorEvaluator()
