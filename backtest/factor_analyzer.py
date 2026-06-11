"""
因子绩效分析器
分析因子的收益、稳定性、回撤等指标
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class FactorPerformanceAnalyzer:
    """因子绩效分析器"""
    
    def __init__(self):
        pass
    
    def analyze_factor(self, factor_values: pd.Series, returns: pd.Series) -> Dict:
        """分析单个因子的绩效"""
        if factor_values.empty or returns.empty:
            return self._empty_analysis()
        
        # 对齐数据
        aligned = pd.DataFrame({
            'factor': factor_values,
            'return': returns
        }).dropna()
        
        if len(aligned) < 30:
            return self._empty_analysis()
        
        # 计算IC
        ic_mean, ic_std, icir = self._calculate_ic(aligned)
        
        # 计算分组收益
        quintile_returns = self._calculate_quintile_returns(aligned)
        
        # 计算多空收益
        long_short_return = self._calculate_long_short_return(quintile_returns)
        
        # 计算稳定性指标
        stability_metrics = self._calculate_stability_metrics(aligned)
        
        # 计算风险指标
        risk_metrics = self._calculate_risk_metrics(aligned)
        
        return {
            'ic_mean': ic_mean,
            'ic_std': ic_std,
            'icir': icir,
            'quintile_returns': quintile_returns,
            'long_short_return': long_short_return,
            'stability': stability_metrics,
            'risk': risk_metrics,
            'data_points': len(aligned),
        }
    
    def _calculate_ic(self, data: pd.DataFrame) -> Tuple[float, float, float]:
        """计算信息系数"""
        # 计算每日IC
        daily_ic = []
        
        # 使用滚动窗口计算IC
        window = 20
        for i in range(window, len(data)):
            window_data = data.iloc[i-window:i]
            if len(window_data) >= 10:
                ic = window_data['factor'].corr(window_data['return'])
                daily_ic.append(ic)
        
        if not daily_ic:
            return 0, 0, 0
        
        ic_series = pd.Series(daily_ic)
        ic_mean = ic_series.mean()
        ic_std = ic_series.std()
        icir = ic_mean / ic_std if ic_std > 0 else 0
        
        return ic_mean, ic_std, icir
    
    def _calculate_quintile_returns(self, data: pd.DataFrame) -> Dict:
        """计算分组收益"""
        try:
            # 按因子值分5组
            data['quintile'] = pd.qcut(data['factor'], 5, labels=['Q1', 'Q2', 'Q3', 'Q4', 'Q5'], duplicates='drop')
            
            # 计算每组平均收益
            quintile_returns = data.groupby('quintile', observed=False)['return'].mean().to_dict()
            
            return quintile_returns
            
        except Exception as e:
            logger.error(f"计算分组收益失败: {e}")
            return {}
    
    def _calculate_long_short_return(self, quintile_returns: Dict) -> float:
        """计算多空收益"""
        if not quintile_returns:
            return 0
        
        q5_return = quintile_returns.get('Q5', 0)
        q1_return = quintile_returns.get('Q1', 0)
        
        return q5_return - q1_return
    
    def _calculate_stability_metrics(self, data: pd.DataFrame) -> Dict:
        """计算稳定性指标"""
        returns = data['return']
        
        # 收益稳定性（滚动20日收益的标准差的倒数）
        rolling_returns = returns.rolling(20).mean()
        return_stability = 1 / (1 + rolling_returns.std()) if not rolling_returns.empty else 0
        
        # 月度稳定性
        monthly_returns = returns.resample('ME').sum() if isinstance(returns.index, pd.DatetimeIndex) else returns
        monthly_positive_rate = (monthly_returns > 0).mean() if not monthly_returns.empty else 0
        
        # 趋势稳定性
        cumsum = returns.cumsum()
        trend_stability = 1 / (1 + cumsum.diff().std()) if not cumsum.empty else 0
        
        return {
            'return_stability': return_stability,
            'monthly_positive_rate': monthly_positive_rate,
            'trend_stability': trend_stability,
        }
    
    def _calculate_risk_metrics(self, data: pd.DataFrame) -> Dict:
        """计算风险指标"""
        returns = data['return']
        
        # 波动率
        volatility = returns.std() * np.sqrt(252)
        
        # 最大回撤
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdown.min())
        
        # 下行风险
        downside_returns = returns[returns < 0]
        downside_risk = downside_returns.std() * np.sqrt(252) if not downside_returns.empty else 0
        
        # VaR
        var_95 = returns.quantile(0.05)
        var_99 = returns.quantile(0.01)
        
        return {
            'volatility': volatility,
            'max_drawdown': max_drawdown,
            'downside_risk': downside_risk,
            'var_95': var_95,
            'var_99': var_99,
        }
    
    def rank_factors(self, factor_analyses: Dict[str, Dict]) -> pd.DataFrame:
        """对因子进行排名"""
        data = []
        
        for factor_name, analysis in factor_analyses.items():
            if analysis.get('data_points', 0) > 0:
                # 计算综合得分
                score = self._calculate_composite_score(analysis)
                
                data.append({
                    'factor': factor_name,
                    'ic_mean': analysis.get('ic_mean', 0),
                    'ic_std': analysis.get('ic_std', 0),
                    'icir': analysis.get('icir', 0),
                    'long_short_return': analysis.get('long_short_return', 0),
                    'return_stability': analysis.get('stability', {}).get('return_stability', 0),
                    'monthly_positive_rate': analysis.get('stability', {}).get('monthly_positive_rate', 0),
                    'max_drawdown': analysis.get('risk', {}).get('max_drawdown', 0),
                    'composite_score': score,
                })
        
        df = pd.DataFrame(data)
        
        if not df.empty:
            df = df.sort_values('composite_score', ascending=False)
            df['rank'] = range(1, len(df) + 1)
        
        return df
    
    def _calculate_composite_score(self, analysis: Dict) -> float:
        """计算综合得分"""
        # 权重配置
        weights = {
            'icir': 0.25,
            'long_short_return': 0.20,
            'return_stability': 0.20,
            'monthly_positive_rate': 0.15,
            'max_drawdown': 0.20,
        }
        
        score = 0
        
        # ICIR（标准化到0-1）
        icir = min(max(analysis.get('icir', 0), 0), 2) / 2
        score += icir * weights['icir']
        
        # 多空收益（标准化到0-1）
        ls_return = min(max(analysis.get('long_short_return', 0), 0), 0.1) / 0.1
        score += ls_return * weights['long_short_return']
        
        # 收益稳定性
        stability = analysis.get('stability', {}).get('return_stability', 0)
        score += stability * weights['return_stability']
        
        # 月度正收益比例
        monthly_rate = analysis.get('stability', {}).get('monthly_positive_rate', 0)
        score += monthly_rate * weights['monthly_positive_rate']
        
        # 最大回撤（越小越好）
        max_dd = analysis.get('risk', {}).get('max_drawdown', 1)
        dd_score = 1 - min(max_dd, 1)
        score += dd_score * weights['max_drawdown']
        
        return score
    
    def generate_report(self, factor_name: str, analysis: Dict) -> str:
        """生成因子分析报告"""
        report = []
        report.append("=" * 60)
        report.append(f"因子分析报告: {factor_name}")
        report.append("=" * 60)
        report.append(f"数据点: {analysis.get('data_points', 0)}")
        report.append("")
        
        report.append("-" * 60)
        report.append("IC分析:")
        report.append("-" * 60)
        report.append(f"IC均值: {analysis.get('ic_mean', 0):.4f}")
        report.append(f"IC标准差: {analysis.get('ic_std', 0):.4f}")
        report.append(f"ICIR: {analysis.get('icir', 0):.4f}")
        report.append("")
        
        report.append("-" * 60)
        report.append("分组收益:")
        report.append("-" * 60)
        quintile_returns = analysis.get('quintile_returns', {})
        for q, ret in quintile_returns.items():
            report.append(f"  {q}: {ret*100:.2f}%")
        report.append(f"多空收益: {analysis.get('long_short_return', 0)*100:.2f}%")
        report.append("")
        
        report.append("-" * 60)
        report.append("稳定性指标:")
        report.append("-" * 60)
        stability = analysis.get('stability', {})
        report.append(f"收益稳定性: {stability.get('return_stability', 0):.4f}")
        report.append(f"月度正收益比例: {stability.get('monthly_positive_rate', 0)*100:.2f}%")
        report.append(f"趋势稳定性: {stability.get('trend_stability', 0):.4f}")
        report.append("")
        
        report.append("-" * 60)
        report.append("风险指标:")
        report.append("-" * 60)
        risk = analysis.get('risk', {})
        report.append(f"年化波动率: {risk.get('volatility', 0)*100:.2f}%")
        report.append(f"最大回撤: {risk.get('max_drawdown', 0)*100:.2f}%")
        report.append(f"下行风险: {risk.get('downside_risk', 0)*100:.2f}%")
        report.append(f"95% VaR: {risk.get('var_95', 0)*100:.2f}%")
        report.append(f"99% VaR: {risk.get('var_99', 0)*100:.2f}%")
        report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def _empty_analysis(self) -> Dict:
        """空分析结果"""
        return {
            'ic_mean': 0,
            'ic_std': 0,
            'icir': 0,
            'quintile_returns': {},
            'long_short_return': 0,
            'stability': {
                'return_stability': 0,
                'monthly_positive_rate': 0,
                'trend_stability': 0,
            },
            'risk': {
                'volatility': 0,
                'max_drawdown': 0,
                'downside_risk': 0,
                'var_95': 0,
                'var_99': 0,
            },
            'data_points': 0,
        }


# 创建全局实例
factor_analyzer = FactorPerformanceAnalyzer()
