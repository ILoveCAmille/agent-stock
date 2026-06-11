"""
量化选股盯盘系统
每10分钟扫描A股，使用多因子模型选出TOP10股票，推送到邮箱
"""

import os
import sys
import time
import logging
import smtplib
import schedule
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np

# Clear proxy
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

# Disable proxy for requests
os.environ['NO_PROXY'] = '*'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class MultiFactorStockSelector:
    """多因子选股器"""
    
    # 因子权重配置
    FACTOR_WEIGHTS = {
        'momentum': 0.15,      # 动量因子
        'value': 0.20,         # 价值因子
        'quality': 0.20,       # 质量因子
        'growth': 0.15,        # 成长因子
        'liquidity': 0.10,     # 流动性因子
        'volatility': 0.10,    # 波动因子
        'fund_flow': 0.10,     # 资金流向因子
    }
    
    def __init__(self):
        self._cache = {}
        self._cache_time = None
        self._cache_ttl = 300  # 5分钟缓存
        self.session = requests.Session()
        self.session.trust_env = False
    
    def get_all_stocks(self) -> pd.DataFrame:
        """获取所有A股实时数据（使用新浪API）"""
        try:
            # 使用新浪API获取实时行情
            url = "https://hq.sinajs.cn/list=sh000001"
            headers = {'Referer': 'https://finance.sina.com.cn'}
            
            # 先测试连接
            r = self.session.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                logger.error("无法连接到新浪API")
                return pd.DataFrame()
            
            # 获取沪深A股列表
            import akshare as ak
            
            # 尝试使用akshare但添加代理绕过
            old_get = requests.get
            def patched_get(*args, **kwargs):
                kwargs.setdefault('proxies', {'http': None, 'https': None})
                return old_get(*args, **kwargs)
            requests.get = patched_get
            
            try:
                df = ak.stock_zh_a_spot_em()
            finally:
                requests.get = old_get
            
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取股票数据失败: {e}")
        
        # 备用方案：使用新浪批量接口
        return self._get_stocks_from_sina()
    
    def _get_stocks_from_sina(self) -> pd.DataFrame:
        """使用新浪API获取股票数据（备用方案）"""
        try:
            # 获取股票代码列表
            codes = []
            
            # 沪市主板
            for i in range(600000, 604000):
                codes.append(f"sh{i}")
            
            # 深市主板
            for i in range(0, 3000):
                codes.append(f"sz{i:06d}")
            
            # 批量获取（每次50只）
            all_data = []
            batch_size = 50
            
            for i in range(0, min(len(codes), 500), batch_size):  # 只测试前500只
                batch = codes[i:i+batch_size]
                url = f"https://hq.sinajs.cn/list={','.join(batch)}"
                headers = {'Referer': 'https://finance.sina.com.cn'}
                
                try:
                    r = self.session.get(url, headers=headers, timeout=10)
                    if r.status_code == 200:
                        for line in r.text.strip().split('\n'):
                            if '="' in line:
                                parts = line.split('=')
                                code_part = parts[0].split('_')[-1]
                                code = code_part[2:]
                                
                                data = parts[1].strip('"').split(',')
                                if len(data) > 30 and data[0]:
                                    try:
                                        all_data.append({
                                            '代码': code,
                                            '名称': data[0],
                                            '最新价': float(data[3]) if data[3] else 0,
                                            '涨跌幅': ((float(data[3]) - float(data[2])) / float(data[2]) * 100) if float(data[2]) > 0 else 0,
                                            '成交量': float(data[8]) if data[8] else 0,
                                            '成交额': float(data[9]) if data[9] else 0,
                                        })
                                    except:
                                        pass
                except:
                    pass
            
            if all_data:
                df = pd.DataFrame(all_data)
                df = df[df['最新价'] > 0]
                return df
                
        except Exception as e:
            logger.error(f"新浪备用方案失败: {e}")
        
        return pd.DataFrame()
    
    def calculate_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算所有因子得分"""
        if df.empty:
            return df
        
        try:
            # 过滤条件
            df = df[df['最新价'].notna() & (df['最新价'] > 0)]
            df = df[df['成交额'].notna() & (df['成交额'] > 1e7)]  # 成交额大于1000万
            df = df[df['涨跌幅'].notna()]
            
            # 过滤ST和退市股
            df = df[~df['名称'].str.contains('ST|退', na=False)]
            
            # 过滤科创板和北交所（可选）
            df = df[~df['代码'].str.startswith('688')]  # 科创板
            df = df[~df['代码'].str.startswith('8')]    # 北交所
            
            if df.empty:
                return df
            
            # 1. 动量因子：60日涨跌幅（适中动量，避免追高）
            df['momentum_score'] = self._calculate_momentum_score(df)
            
            # 2. 价值因子：低PE、低PB
            df['value_score'] = self._calculate_value_score(df)
            
            # 3. 质量因子：高ROE（从市盈率和市净率推算）
            df['quality_score'] = self._calculate_quality_score(df)
            
            # 4. 成长因子：年初至今涨跌幅
            df['growth_score'] = self._calculate_growth_score(df)
            
            # 5. 流动性因子：换手率适中
            df['liquidity_score'] = self._calculate_liquidity_score(df)
            
            # 6. 波动因子：低波动
            df['volatility_score'] = self._calculate_volatility_score(df)
            
            # 7. 资金流向因子：量比
            df['fund_flow_score'] = self._calculate_fund_flow_score(df)
            
            # 计算综合得分
            df['total_score'] = (
                df['momentum_score'] * self.FACTOR_WEIGHTS['momentum'] +
                df['value_score'] * self.FACTOR_WEIGHTS['value'] +
                df['quality_score'] * self.FACTOR_WEIGHTS['quality'] +
                df['growth_score'] * self.FACTOR_WEIGHTS['growth'] +
                df['liquidity_score'] * self.FACTOR_WEIGHTS['liquidity'] +
                df['volatility_score'] * self.FACTOR_WEIGHTS['volatility'] +
                df['fund_flow_score'] * self.FACTOR_WEIGHTS['fund_flow']
            )
            
            return df
            
        except Exception as e:
            logger.error(f"计算因子失败: {e}")
            return df
    
    def _calculate_momentum_score(self, df: pd.DataFrame) -> pd.Series:
        """动量因子：60日涨跌幅，适度动量（避免极端）"""
        score = pd.Series(0.0, index=df.index)
        
        if '60日涨跌幅' in df.columns:
            pct = df['60日涨跌幅'].fillna(0)
            # 适度动量：10-30%涨幅得分最高
            score = np.where(
                (pct > 10) & (pct < 30), 100,
                np.where(
                    (pct >= 30) & (pct < 50), 80,
                    np.where(
                        (pct > 0) & (pct <= 10), 60,
                        np.where(pct < -10, 20, 40)
                    )
                )
            )
        
        return pd.Series(score, index=df.index)
    
    def _calculate_value_score(self, df: pd.DataFrame) -> pd.Series:
        """价值因子：低PE、低PB"""
        score = pd.Series(0.0, index=df.index)
        
        # PE得分
        pe_score = pd.Series(50.0, index=df.index)
        if '市盈率-动态' in df.columns:
            pe = df['市盈率-动态'].fillna(0)
            pe_score = np.where(
                (pe > 0) & (pe < 15), 100,
                np.where(
                    (pe >= 15) & (pe < 25), 80,
                    np.where(
                        (pe >= 25) & (pe < 40), 60,
                        np.where(
                            (pe >= 40) & (pe < 60), 40,
                            np.where(pe >= 60, 20, 50)
                        )
                    )
                )
            )
        
        # PB得分
        pb_score = pd.Series(50.0, index=df.index)
        if '市净率' in df.columns:
            pb = df['市净率'].fillna(0)
            pb_score = np.where(
                (pb > 0) & (pb < 1), 100,
                np.where(
                    (pb >= 1) & (pb < 2), 80,
                    np.where(
                        (pb >= 2) & (pb < 3), 60,
                        np.where(
                            (pb >= 3) & (pb < 5), 40,
                            np.where(pb >= 5, 20, 50)
                        )
                    )
                )
            )
        
        score = (pe_score + pb_score) / 2
        return pd.Series(score, index=df.index)
    
    def _calculate_quality_score(self, df: pd.DataFrame) -> pd.Series:
        """质量因子：从PE和PB推算ROE"""
        score = pd.Series(50.0, index=df.index)
        
        if '市盈率-动态' in df.columns and '市净率' in df.columns:
            pe = df['市盈率-动态'].fillna(0)
            pb = df['市净率'].fillna(0)
            
            # ROE ≈ PB / PE
            roe = np.where((pe > 0) & (pb > 0), (pb / pe) * 100, 0)
            
            score = np.where(
                roe > 15, 100,
                np.where(
                    roe > 10, 80,
                    np.where(
                        roe > 5, 60,
                        np.where(roe > 0, 40, 20)
                    )
                )
            )
        
        return pd.Series(score, index=df.index)
    
    def _calculate_growth_score(self, df: pd.DataFrame) -> pd.Series:
        """成长因子：年初至今涨跌幅"""
        score = pd.Series(50.0, index=df.index)
        
        if '年初至今涨跌幅' in df.columns:
            ytd = df['年初至今涨跌幅'].fillna(0)
            score = np.where(
                (ytd > 20) & (ytd < 80), 100,
                np.where(
                    (ytd >= 0) & (ytd <= 20), 80,
                    np.where(
                        (ytd >= -10) & (ytd < 0), 60,
                        np.where(
                            (ytd >= -30) & (ytd < -10), 40,
                            np.where(ytd < -30, 20, 50)
                        )
                    )
                )
            )
        
        return pd.Series(score, index=df.index)
    
    def _calculate_liquidity_score(self, df: pd.DataFrame) -> pd.Series:
        """流动性因子：换手率适中"""
        score = pd.Series(50.0, index=df.index)
        
        if '换手率' in df.columns:
            turnover = df['换手率'].fillna(0)
            # 适度换手率（2-8%）得分最高
            score = np.where(
                (turnover >= 2) & (turnover <= 8), 100,
                np.where(
                    (turnover > 8) & (turnover <= 15), 70,
                    np.where(
                        (turnover >= 1) & (turnover < 2), 60,
                        np.where(turnover > 15, 30, 40)
                    )
                )
            )
        
        return pd.Series(score, index=df.index)
    
    def _calculate_volatility_score(self, df: pd.DataFrame) -> pd.Series:
        """波动因子：低波动得分高"""
        score = pd.Series(50.0, index=df.index)
        
        if '振幅' in df.columns:
            amplitude = df['振幅'].fillna(0)
            # 低振幅得分高
            score = np.where(
                amplitude < 3, 100,
                np.where(
                    (amplitude >= 3) & (amplitude < 5), 80,
                    np.where(
                        (amplitude >= 5) & (amplitude < 8), 60,
                        np.where(amplitude >= 8, 40, 50)
                    )
                )
            )
        
        return pd.Series(score, index=df.index)
    
    def _calculate_fund_flow_score(self, df: pd.DataFrame) -> pd.Series:
        """资金流向因子：量比"""
        score = pd.Series(50.0, index=df.index)
        
        if '量比' in df.columns:
            volume_ratio = df['量比'].fillna(1)
            # 量比1.5-3得分最高（放量但不过度）
            score = np.where(
                (volume_ratio >= 1.5) & (volume_ratio <= 3), 100,
                np.where(
                    (volume_ratio > 3) & (volume_ratio <= 5), 70,
                    np.where(
                        (volume_ratio >= 1) & (volume_ratio < 1.5), 60,
                        np.where(volume_ratio > 5, 30, 40)
                    )
                )
            )
        
        return pd.Series(score, index=df.index)
    
    def get_top_stocks(self, top_n: int = 10) -> List[Dict]:
        """获取TOP N股票"""
        # 获取所有股票
        df = self.get_all_stocks()
        if df.empty:
            return []
        
        # 计算因子
        df = self.calculate_factors(df)
        if df.empty:
            return []
        
        # 按综合得分排序
        df = df.sort_values('total_score', ascending=False)
        
        # 取TOP N
        top_stocks = []
        for _, row in df.head(top_n).iterrows():
            stock = {
                'code': row.get('代码', ''),
                'name': row.get('名称', ''),
                'price': row.get('最新价', 0),
                'change_pct': row.get('涨跌幅', 0),
                'pe': row.get('市盈率-动态', 0),
                'pb': row.get('市净率', 0),
                'turnover': row.get('换手率', 0),
                'volume_ratio': row.get('量比', 0),
                'amount': row.get('成交额', 0),
                'ytd_return': row.get('年初至今涨跌幅', 0),
                'd60_return': row.get('60日涨跌幅', 0),
                'total_score': row.get('total_score', 0),
                'momentum_score': row.get('momentum_score', 0),
                'value_score': row.get('value_score', 0),
                'quality_score': row.get('quality_score', 0),
                'growth_score': row.get('growth_score', 0),
                'liquidity_score': row.get('liquidity_score', 0),
                'volatility_score': row.get('volatility_score', 0),
                'fund_flow_score': row.get('fund_flow_score', 0),
            }
            top_stocks.append(stock)
        
        return top_stocks


class EmailNotifier:
    """邮件通知器"""
    
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.qq.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '465'))
        self.email_from = os.getenv('EMAIL_FROM', 'az5753@foxmail.com')
        self.email_password = os.getenv('EMAIL_PASSWORD', 'rnsywdxffkpmddjj')
        self.email_to = os.getenv('EMAIL_TO', '3102189887@qq.com')
    
    def send_top_stocks_email(self, stocks: List[Dict], scan_time: str) -> bool:
        """发送TOP股票邮件"""
        if not stocks:
            return False
        
        try:
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = f"AI量化选股 - TOP{len(stocks)}股票推荐 ({scan_time})"
            
            # 构建HTML内容
            html = self._build_html(stocks, scan_time)
            msg.attach(MIMEText(html, 'html'))
            
            # 发送邮件
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
                server.starttls()
            
            server.login(self.email_from, self.email_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"[EMAIL] Sent TOP{len(stocks)} stocks email successfully")
            return True
            
        except Exception as e:
            logger.error(f"[EMAIL] Failed to send email: {e}")
            return False
    
    def _build_html(self, stocks: List[Dict], scan_time: str) -> str:
        """构建HTML邮件内容"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   color: white; padding: 20px; border-radius: 10px; }}
        .stock-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        .stock-table th {{ background: #f5f5f5; padding: 12px; text-align: left; 
                          border-bottom: 2px solid #ddd; }}
        .stock-table td {{ padding: 10px; border-bottom: 1px solid #eee; }}
        .stock-table tr:hover {{ background: #f9f9f9; }}
        .up {{ color: #ff4444; }}
        .down {{ color: #00c853; }}
        .score {{ font-weight: bold; color: #667eea; }}
        .factor-bar {{ display: inline-block; height: 10px; background: #667eea; 
                      border-radius: 5px; margin-right: 5px; }}
        .footer {{ margin-top: 20px; padding: 15px; background: #f5f5f5; 
                  border-radius: 10px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>AI量化选股系统</h1>
        <p>扫描时间: {scan_time}</p>
        <p>选股策略: 多因子模型（动量+价值+质量+成长+流动性+波动+资金流向）</p>
    </div>
    
    <h2>TOP {len(stocks)} 推荐股票</h2>
    
    <table class="stock-table">
        <thead>
            <tr>
                <th>排名</th>
                <th>代码</th>
                <th>名称</th>
                <th>现价</th>
                <th>涨跌幅</th>
                <th>PE</th>
                <th>PB</th>
                <th>换手率</th>
                <th>量比</th>
                <th>综合得分</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for i, stock in enumerate(stocks, 1):
            change_pct = stock.get('change_pct', 0)
            change_class = 'up' if change_pct > 0 else 'down' if change_pct < 0 else ''
            change_sign = '+' if change_pct > 0 else ''
            
            html += f"""
            <tr>
                <td><strong>{i}</strong></td>
                <td>{stock.get('code', '')}</td>
                <td>{stock.get('name', '')}</td>
                <td>{stock.get('price', 0):.2f}</td>
                <td class="{change_class}">{change_sign}{change_pct:.2f}%</td>
                <td>{stock.get('pe', 0):.1f}</td>
                <td>{stock.get('pb', 0):.2f}</td>
                <td>{stock.get('turnover', 0):.2f}%</td>
                <td>{stock.get('volume_ratio', 0):.2f}</td>
                <td class="score">{stock.get('total_score', 0):.1f}</td>
            </tr>
"""
        
        html += """
        </tbody>
    </table>
    
    <h3>因子得分详情</h3>
    <table class="stock-table">
        <thead>
            <tr>
                <th>代码</th>
                <th>名称</th>
                <th>动量</th>
                <th>价值</th>
                <th>质量</th>
                <th>成长</th>
                <th>流动性</th>
                <th>波动</th>
                <th>资金流</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for stock in stocks:
            html += f"""
            <tr>
                <td>{stock.get('code', '')}</td>
                <td>{stock.get('name', '')}</td>
                <td>{stock.get('momentum_score', 0):.0f}</td>
                <td>{stock.get('value_score', 0):.0f}</td>
                <td>{stock.get('quality_score', 0):.0f}</td>
                <td>{stock.get('growth_score', 0):.0f}</td>
                <td>{stock.get('liquidity_score', 0):.0f}</td>
                <td>{stock.get('volatility_score', 0):.0f}</td>
                <td>{stock.get('fund_flow_score', 0):.0f}</td>
            </tr>
"""
        
        html += """
        </tbody>
    </table>
    
    <div class="footer">
        <p><strong>免责声明：</strong>本报告由AI量化系统自动生成，仅供参考，不构成投资建议。</p>
        <p>投资有风险，入市需谨慎。请根据自身风险承受能力做出投资决策。</p>
        <p>因子权重：动量15% | 价值20% | 质量20% | 成长15% | 流动性10% | 波动10% | 资金流10%</p>
    </div>
</body>
</html>
"""
        return html


class StockScanner:
    """股票扫描器 - 定时执行"""
    
    def __init__(self):
        self.selector = MultiFactorStockSelector()
        self.notifier = EmailNotifier()
        self.last_scan_time = None
        self.scan_count = 0
    
    def is_trading_time(self) -> bool:
        """判断是否在交易时间"""
        now = datetime.now()
        
        # 周末不交易
        if now.weekday() >= 5:
            return False
        
        # 交易时间：9:30-11:30, 13:00-15:00
        current_time = now.time()
        morning_start = datetime.strptime('09:30', '%H:%M').time()
        morning_end = datetime.strptime('11:30', '%H:%M').time()
        afternoon_start = datetime.strptime('13:00', '%H:%M').time()
        afternoon_end = datetime.strptime('15:00', '%H:%M').time()
        
        return (morning_start <= current_time <= morning_end) or \
               (afternoon_start <= current_time <= afternoon_end)
    
    def scan_and_notify(self):
        """扫描并通知"""
        if not self.is_trading_time():
            logger.info("[SCAN] Not trading time, skipping...")
            return
        
        scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"[SCAN] Starting scan #{self.scan_count + 1} at {scan_time}")
        
        try:
            # 获取TOP股票
            top_stocks = self.selector.get_top_stocks(top_n=10)
            
            if not top_stocks:
                logger.warning("[SCAN] No stocks found")
                return
            
            logger.info(f"[SCAN] Found TOP{len(top_stocks)} stocks")
            
            # 发送邮件
            success = self.notifier.send_top_stocks_email(top_stocks, scan_time)
            
            if success:
                self.last_scan_time = scan_time
                self.scan_count += 1
                logger.info(f"[SCAN] Scan #{self.scan_count} completed successfully")
                
                # 打印TOP股票
                for i, stock in enumerate(top_stocks, 1):
                    logger.info(f"  {i}. {stock['code']} {stock['name']} "
                              f"Price:{stock['price']:.2f} "
                              f"Change:{stock['change_pct']:+.2f}% "
                              f"Score:{stock['total_score']:.1f}")
            else:
                logger.error("[SCAN] Failed to send email")
                
        except Exception as e:
            logger.error(f"[SCAN] Error during scan: {e}")
            import traceback
            traceback.print_exc()
    
    def run(self):
        """运行扫描器"""
        logger.info("=" * 60)
        logger.info("Stock Scanner Started")
        logger.info("=" * 60)
        logger.info(f"Trading Hours: 09:30-11:30, 13:00-15:00")
        logger.info(f"Scan Interval: 10 minutes")
        logger.info(f"Email: {self.notifier.email_to}")
        logger.info("=" * 60)
        
        # 立即执行一次
        self.scan_and_notify()
        
        # 设置定时任务：每10分钟执行一次
        schedule.every(10).minutes.do(self.scan_and_notify)
        
        # 持续运行
        while True:
            schedule.run_pending()
            time.sleep(1)


def main():
    """主函数"""
    scanner = StockScanner()
    scanner.run()


if __name__ == '__main__':
    main()
