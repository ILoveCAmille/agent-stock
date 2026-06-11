"""
绩效报告生成器
生成HTML格式的回测报告
"""

import numpy as np
import pandas as pd
from typing import Dict, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PerformanceReportGenerator:
    """绩效报告生成器"""
    
    def __init__(self):
        pass
    
    def generate_html_report(self, backtest_results: Dict, factor_analyses: Dict = None) -> str:
        """生成HTML报告"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   color: white; padding: 30px; border-radius: 15px; margin-bottom: 20px; }}
        .section {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;
                   box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }}
        .metric-card {{ background: #f9f9f9; padding: 15px; border-radius: 10px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #667eea; }}
        .metric-label {{ font-size: 12px; color: #666; margin-top: 5px; }}
        .positive {{ color: #ff4444; }}
        .negative {{ color: #00c853; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f5f5f5; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>量化策略回测报告</h1>
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="section">
            <h2>收益概览</h2>
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-value">{backtest_results.get('total_return', 0)*100:.2f}%</div>
                    <div class="metric-label">总收益率</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{backtest_results.get('annual_return', 0)*100:.2f}%</div>
                    <div class="metric-label">年化收益率</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{backtest_results.get('sharpe_ratio', 0):.2f}</div>
                    <div class="metric-label">夏普比率</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{backtest_results.get('max_drawdown', 0)*100:.2f}%</div>
                    <div class="metric-label">最大回撤</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>风险指标</h2>
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-value">{backtest_results.get('annual_volatility', 0)*100:.2f}%</div>
                    <div class="metric-label">年化波动率</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{backtest_results.get('calmar_ratio', 0):.2f}</div>
                    <div class="metric-label">卡尔玛比率</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{backtest_results.get('win_rate', 0)*100:.2f}%</div>
                    <div class="metric-label">日胜率</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{backtest_results.get('monthly_win_rate', 0)*100:.2f}%</div>
                    <div class="metric-label">月胜率</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>交易统计</h2>
            <table>
                <tr>
                    <th>指标</th>
                    <th>数值</th>
                </tr>
                <tr>
                    <td>总交易次数</td>
                    <td>{backtest_results.get('total_trades', 0)}</td>
                </tr>
                <tr>
                    <td>买入次数</td>
                    <td>{backtest_results.get('buy_trades', 0)}</td>
                </tr>
                <tr>
                    <td>卖出次数</td>
                    <td>{backtest_results.get('sell_trades', 0)}</td>
                </tr>
                <tr>
                    <td>盈利交易</td>
                    <td>{backtest_results.get('profitable_trades', 0)}</td>
                </tr>
                <tr>
                    <td>亏损交易</td>
                    <td>{backtest_results.get('losing_trades', 0)}</td>
                </tr>
                <tr>
                    <td>交易胜率</td>
                    <td>{backtest_results.get('win_rate_trades', 0)*100:.2f}%</td>
                </tr>
                <tr>
                    <td>盈亏比</td>
                    <td>{backtest_results.get('profit_loss_ratio', 0):.2f}</td>
                </tr>
                <tr>
                    <td>平均持仓天数</td>
                    <td>{backtest_results.get('avg_holding_days', 0):.0f}</td>
                </tr>
            </table>
        </div>
"""
        
        # 因子分析部分
        if factor_analyses:
            html += """
        <div class="section">
            <h2>因子分析</h2>
            <table>
                <tr>
                    <th>排名</th>
                    <th>因子</th>
                    <th>IC均值</th>
                    <th>ICIR</th>
                    <th>多空收益</th>
                    <th>最大回撤</th>
                    <th>综合得分</th>
                </tr>
"""
            
            ranked = factor_analyses.get('ranked_factors', pd.DataFrame())
            if not ranked.empty:
                for _, row in ranked.head(20).iterrows():
                    html += f"""
                <tr>
                    <td>{row.get('rank', '')}</td>
                    <td>{row.get('factor', '')}</td>
                    <td>{row.get('ic_mean', 0):.4f}</td>
                    <td>{row.get('icir', 0):.4f}</td>
                    <td>{row.get('long_short_return', 0)*100:.2f}%</td>
                    <td>{row.get('max_drawdown', 0)*100:.2f}%</td>
                    <td>{row.get('composite_score', 0):.4f}</td>
                </tr>
"""
            
            html += """
            </table>
        </div>
"""
        
        html += """
        <div class="section">
            <h2>免责声明</h2>
            <p>本报告由AI量化系统自动生成，仅供参考，不构成投资建议。</p>
            <p>投资有风险，入市需谨慎。</p>
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def generate_summary(self, backtest_results: Dict) -> str:
        """生成摘要"""
        summary = []
        summary.append("=" * 50)
        summary.append("回测结果摘要")
        summary.append("=" * 50)
        summary.append(f"总收益率: {backtest_results.get('total_return', 0)*100:.2f}%")
        summary.append(f"年化收益率: {backtest_results.get('annual_return', 0)*100:.2f}%")
        summary.append(f"夏普比率: {backtest_results.get('sharpe_ratio', 0):.2f}")
        summary.append(f"最大回撤: {backtest_results.get('max_drawdown', 0)*100:.2f}%")
        summary.append(f"卡尔玛比率: {backtest_results.get('calmar_ratio', 0):.2f}")
        summary.append(f"月胜率: {backtest_results.get('monthly_win_rate', 0)*100:.2f}%")
        summary.append("=" * 50)
        
        return "\n".join(summary)


# 创建全局实例
report_generator = PerformanceReportGenerator()
