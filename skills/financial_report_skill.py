"""
财报分析技能
提供财报搜索、解析和分析能力
"""

import requests
import json
import logging
import pandas as pd
from typing import Dict, List, Optional
from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class FinancialReportSkill(BaseSkill):
    """财报分析技能"""
    
    def __init__(self):
        super().__init__()
    
    def search_financial_reports(self, stock_code: str) -> List[Dict]:
        """搜索财报信息"""
        reports = []
        
        # 1. 搜索东方财富财报
        eastmoney_reports = self._search_eastmoney_reports(stock_code)
        reports.extend(eastmoney_reports)
        
        # 2. 搜索巨潮资讯财报
        cninfo_reports = self._search_cninfo_reports(stock_code)
        reports.extend(cninfo_reports)
        
        return reports
    
    def _search_eastmoney_reports(self, stock_code: str) -> List[Dict]:
        """搜索东方财富财报"""
        reports = []
        try:
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'sortColumns': 'REPORT_DATE',
                'sortTypes': '-1',
                'pageSize': '10',
                'pageNumber': '1',
                'reportName': 'RPT_LICO_FN_CPD',
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                'filter': f'(SECURITY_CODE="{stock_code}")'
            }
            
            response = self._safe_get(url, params=params, timeout=15)
            if response:
                data = response.json()
                if data.get('result') and data['result'].get('data'):
                    for item in data['result']['data'][:5]:
                        reports.append({
                            'title': f"{item.get('REPORT_DATE_NAME', '')}报告",
                            'date': item.get('REPORT_DATE', '')[:10],
                            'type': '东方财富',
                            'eps': item.get('BASIC_EPS', ''),
                            'revenue': item.get('TOTAL_OPERATE_INCOME', ''),
                            'profit': item.get('PARENT_NETPROFIT', '')
                        })
        except Exception as e:
            logger.error(f"搜索东方财富财报失败: {e}")
        
        return reports
    
    def _search_cninfo_reports(self, stock_code: str) -> List[Dict]:
        """搜索巨潮资讯财报"""
        reports = []
        try:
            url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
            data = {
                'stock': stock_code,
                'tabName': 'fulltext',
                'pageSize': '10',
                'pageNum': '1',
                'column': 'szse' if stock_code.startswith('0') or stock_code.startswith('3') else 'sse',
                'category': 'category_ndbg_szsh',
                'plate': '',
                'seDate': ''
            }
            
            response = self._safe_post(url, json_data=data, timeout=15)
            if response:
                result = response.json()
                if result.get('announcements'):
                    for item in result['announcements'][:5]:
                        reports.append({
                            'title': item.get('announcementTitle', ''),
                            'date': item.get('announcementTime', ''),
                            'type': '巨潮资讯',
                            'url': f"https://www.cninfo.com.cn/new/disclosure/detail?announcementId={item.get('announcementId', '')}"
                        })
        except Exception as e:
            logger.error(f"搜索巨潮资讯财报失败: {e}")
        
        return reports
    
    def get_financial_indicators(self, stock_code: str) -> Dict:
        """获取财务指标"""
        indicators = {}
        
        try:
            import akshare as ak
            
            # 获取财务指标
            df = ak.stock_financial_analysis_indicator(symbol=stock_code)
            if df is not None and not df.empty:
                latest = df.iloc[0]
                indicators = {
                    'roe': latest.get('净资产收益率(%)', ''),
                    'roa': latest.get('总资产收益率(%)', ''),
                    'gross_margin': latest.get('销售毛利率(%)', ''),
                    'net_margin': latest.get('销售净利率(%)', ''),
                    'debt_ratio': latest.get('资产负债率(%)', ''),
                    'current_ratio': latest.get('流动比率', ''),
                    'quick_ratio': latest.get('速动比率', ''),
                    'inventory_turnover': latest.get('存货周转率(次)', ''),
                    'receivable_turnover': latest.get('应收账款周转率(次)', ''),
                    'total_asset_turnover': latest.get('总资产周转率(次)', ''),
                    'revenue_growth': latest.get('主营业务收入增长率(%)', ''),
                    'profit_growth': latest.get('净利润增长率(%)', ''),
                    'eps': latest.get('基本每股收益(元)', ''),
                    'bvps': latest.get('每股净资产(元)', '')
                }
        except Exception as e:
            logger.error(f"获取财务指标失败: {e}")
        
        return indicators
    
    def get_quarterly_reports(self, stock_code: str) -> Dict:
        """获取季报数据"""
        quarterly_data = {
            'income_statement': [],
            'balance_sheet': [],
            'cash_flow': []
        }
        
        try:
            import akshare as ak
            
            # 获取利润表
            income = ak.stock_profit_sheet_by_report_em(symbol=stock_code)
            if income is not None and not income.empty:
                quarterly_data['income_statement'] = income.head(8).to_dict('records')
            
            # 获取资产负债表
            balance = ak.stock_balance_sheet_by_report_em(symbol=stock_code)
            if balance is not None and not balance.empty:
                quarterly_data['balance_sheet'] = balance.head(8).to_dict('records')
            
            # 获取现金流量表
            cashflow = ak.stock_cash_flow_sheet_by_report_em(symbol=stock_code)
            if cashflow is not None and not cashflow.empty:
                quarterly_data['cash_flow'] = cashflow.head(8).to_dict('records')
                
        except Exception as e:
            logger.error(f"获取季报数据失败: {e}")
        
        return quarterly_data
    
    def analyze_financial_health(self, indicators: Dict) -> Dict:
        """分析财务健康状况"""
        analysis = {
            'profitability': 'unknown',
            'solvency': 'unknown',
            'growth': 'unknown',
            'overall': 'unknown',
            'details': []
        }
        
        try:
            # 盈利能力分析
            roe = float(indicators.get('roe', 0) or 0)
            net_margin = float(indicators.get('net_margin', 0) or 0)
            
            if roe > 15 and net_margin > 10:
                analysis['profitability'] = 'excellent'
                analysis['details'].append('盈利能力优秀')
            elif roe > 10 and net_margin > 5:
                analysis['profitability'] = 'good'
                analysis['details'].append('盈利能力良好')
            elif roe > 5:
                analysis['profitability'] = 'average'
                analysis['details'].append('盈利能力一般')
            else:
                analysis['profitability'] = 'poor'
                analysis['details'].append('盈利能力较弱')
            
            # 偿债能力分析
            debt_ratio = float(indicators.get('debt_ratio', 0) or 0)
            current_ratio = float(indicators.get('current_ratio', 0) or 0)
            
            if debt_ratio < 40 and current_ratio > 1.5:
                analysis['solvency'] = 'excellent'
                analysis['details'].append('偿债能力优秀')
            elif debt_ratio < 60 and current_ratio > 1:
                analysis['solvency'] = 'good'
                analysis['details'].append('偿债能力良好')
            elif debt_ratio < 70:
                analysis['solvency'] = 'average'
                analysis['details'].append('偿债能力一般')
            else:
                analysis['solvency'] = 'poor'
                analysis['details'].append('偿债能力较弱')
            
            # 成长性分析
            revenue_growth = float(indicators.get('revenue_growth', 0) or 0)
            profit_growth = float(indicators.get('profit_growth', 0) or 0)
            
            if revenue_growth > 20 and profit_growth > 20:
                analysis['growth'] = 'excellent'
                analysis['details'].append('成长性优秀')
            elif revenue_growth > 10 and profit_growth > 10:
                analysis['growth'] = 'good'
                analysis['details'].append('成长性良好')
            elif revenue_growth > 0:
                analysis['growth'] = 'average'
                analysis['details'].append('成长性一般')
            else:
                analysis['growth'] = 'poor'
                analysis['details'].append('成长性较弱')
            
            # 综合评估
            scores = {
                'excellent': 4,
                'good': 3,
                'average': 2,
                'poor': 1,
                'unknown': 0
            }
            
            total_score = (
                scores.get(analysis['profitability'], 0) +
                scores.get(analysis['solvency'], 0) +
                scores.get(analysis['growth'], 0)
            )
            
            if total_score >= 10:
                analysis['overall'] = 'excellent'
            elif total_score >= 7:
                analysis['overall'] = 'good'
            elif total_score >= 4:
                analysis['overall'] = 'average'
            else:
                analysis['overall'] = 'poor'
                
        except Exception as e:
            logger.error(f"分析财务健康状况失败: {e}")
        
        return analysis
    
    def get_skill_description(self) -> str:
        """获取技能描述"""
        return """
【财报分析技能】
- 搜索财报（东方财富、巨潮资讯）
- 获取财务指标（ROE、毛利率、负债率等）
- 获取季报数据（利润表、资产负债表、现金流量表）
- 分析财务健康状况（盈利能力、偿债能力、成长性）
"""
