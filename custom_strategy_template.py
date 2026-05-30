#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自定义股票策略模板
复制此文件并修改为你自己的策略

使用方法:
1. 复制此文件为: your_strategy_name_selector.py
2. 修改 CustomStrategySelector 类名为你的策略名
3. 实现你的选股逻辑在 get_stocks() 方法中
4. 参考 low_price_bull_ui.py 创建对应的UI界面文件
5. 在 app.py 中注册你的策略
"""

import pandas as pd
import pywencai
from datetime import datetime
from typing import Tuple, Optional
import time
import akshare as ak


class CustomStrategySelector:
    """
    自定义选股策略类
    请修改此类实现你自己的选股逻辑
    """
    
    def __init__(self):
        self.raw_data = None
        self.selected_stocks = None
        
        # ==================== 策略配置 - 在这里定义你的参数 ====================
        self.STRATEGY_NAME = "我的自定义策略"
        self.STRATEGY_DESC = "在这里描述你的策略逻辑"
        
        # 选股条件示例 - 请修改为你自己的条件
        self.CONDITIONS = {
            # 基本面条件
            'pe_ratio': 20,                    # PE小于
            'pb_ratio': 1.5,                   # PB小于
            'dividend_yield': 2,               # 股息率大于(%)
            'debt_ratio': 40,                  # 资产负债率小于(%)
            'net_profit_growth': 10,           # 净利润增长率大于(%)
            
            # 技术面条件
            'price_min': 3,                    # 最低价
            'price_max': 30,                   # 最高价
            'turnover_min': 5000,              # 最低成交额(万元)
            'rsi_max': 50,                     # RSI最大值
            
            # 过滤条件
            'exclude_st': True,                # 排除ST
            'exclude_star_st': True,           # 排除*ST
            'exclude_kcb': True,               # 排除科创板
            'exclude_cyb': True,               # 排除创业板
            'exclude_bj': True,                # 排除北交所
            
            # 排序方式
            'sort_by': '流通市值',              # 排序字段
            'sort_order': 'asc',               # 排序方式 asc/desc
            
            # 返回数量
            'return_count': 10                 # 返回前N只股票
        }
        # ===================================================================

    def get_stocks(self) -> Tuple[bool, Optional[pd.DataFrame], str]:
        """
        执行选股逻辑
        返回: (成功状态, 股票DataFrame, 消息)
        """
        try:
            print(f"\n{'='*60}")
            print(f"🚀 {self.STRATEGY_NAME} - 选股开始")
            print(f"{'='*60}")
            print(f"策略说明: {self.STRATEGY_DESC}")
            
            # ============== 方法1: 使用问财接口选股(推荐) ==============
            # 优点: 简单强大，支持几乎所有财务、技术、行情指标
            return self._get_stocks_by_wencai()
            
            # ============== 方法2: 使用AKShare自己计算 ==============
            # 优点: 完全可控，不需要依赖问财
            # return self._get_stocks_by_akshare()

        except Exception as e:
            error_msg = f"选股失败: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return False, None, error_msg

    def _get_stocks_by_wencai(self) -> Tuple[bool, Optional[pd.DataFrame], str]:
        """使用问财接口选股"""
        
        # 构建问财查询语句
        # 问财支持自然语言查询，非常强大
        query_parts = []
        
        # 价格条件
        if self.CONDITIONS['price_min'] > 0:
            query_parts.append(f"股价>{self.CONDITIONS['price_min']}元")
        if self.CONDITIONS['price_max'] > 0:
            query_parts.append(f"股价<{self.CONDITIONS['price_max']}元")
            
        # 基本面条件
        if self.CONDITIONS['pe_ratio'] > 0:
            query_parts.append(f"市盈率(动)<{self.CONDITIONS['pe_ratio']}")
        if self.CONDITIONS['pb_ratio'] > 0:
            query_parts.append(f"市净率<{self.CONDITIONS['pb_ratio']}")
        if self.CONDITIONS['dividend_yield'] > 0:
            query_parts.append(f"股息率>{self.CONDITIONS['dividend_yield']}%")
        if self.CONDITIONS['net_profit_growth'] > 0:
            query_parts.append(f"净利润同比增长率>{self.CONDITIONS['net_profit_growth']}%")
            
        # 过滤条件
        if self.CONDITIONS['exclude_st']:
            query_parts.append("非ST")
        if self.CONDITIONS['exclude_star_st']:
            query_parts.append("非*ST")
        if self.CONDITIONS['exclude_kcb']:
            query_parts.append("非科创板")
        if self.CONDITIONS['exclude_cyb']:
            query_parts.append("非创业板")
        if self.CONDITIONS['exclude_bj']:
            query_parts.append("非北交所")
            
        # 排序
        sort_dir = "从小到大排名" if self.CONDITIONS['sort_order'] == 'asc' else "从大到小排名"
        query_parts.append(f"{self.CONDITIONS['sort_by']}{sort_dir}")
        
        # 合并查询语句
        query = "，".join(query_parts)
        
        print(f"\n📝 问财查询语句:")
        print(query)
        print(f"\n⏳ 正在查询数据...")
        
        # 调用问财接口
        result = pywencai.get(query=query, loop=True)
        
        if result is None:
            return False, None, "问财接口无返回，请检查网络或稍后重试"
            
        # 转换格式
        df = self._convert_to_dataframe(result)
        
        if df is None or df.empty:
            return False, None, "没有找到符合条件的股票"
            
        self.raw_data = df
        
        # 取前N只
        count = min(len(df), self.CONDITIONS['return_count'])
        selected = df.head(count)
        self.selected_stocks = selected
        
        # 输出结果
        print(f"\n✅ 选股完成，共找到 {len(df)} 只符合条件的股票，返回前 {count} 只")
        print(f"\n📋 筛选结果:")
        for idx, row in selected.iterrows():
            code = row.get('股票代码', 'N/A')
            name = row.get('股票简称', 'N/A')
            price = row.get('最新价', row.get('股价', 'N/A'))
            print(f"  {idx+1:2d}. {code} {name} - 价格: {price}")
            
        print(f"\n{'='*60}\n")
        
        return True, selected, f"成功筛选出 {count} 只股票"

    def _get_stocks_by_akshare(self) -> Tuple[bool, Optional[pd.DataFrame], str]:
        """使用AKShare获取数据并自己实现筛选逻辑"""
        print("\n📊 使用AKShare获取全市场数据...")
        
        # 获取A股列表
        stock_df = ak.stock_zh_a_spot_em()
        
        # 在这里添加你的筛选逻辑
        # 示例: 
        # filtered = stock_df[
        #     (stock_df['最新价'] < 20) &
        #     (stock_df['涨跌幅'] > 0) &
        #     (stock_df['成交额'] > 100000000)
        # ]
        
        return True, stock_df.head(10), "测试返回"

    def _convert_to_dataframe(self, result) -> Optional[pd.DataFrame]:
        """统一格式转换"""
        try:
            if isinstance(result, pd.DataFrame):
                return result
            elif isinstance(result, dict):
                if 'data' in result:
                    return pd.DataFrame(result['data'])
                elif 'result' in result:
                    return pd.DataFrame(result['result'])
                else:
                    return pd.DataFrame(result)
            elif isinstance(result, list):
                return pd.DataFrame(result)
            else:
                return None
        except Exception as e:
            print(f"数据转换失败: {e}")
            return None

    def get_clean_codes(self) -> list:
        """返回纯净的股票代码列表(去掉后缀)"""
        if self.selected_stocks is None or self.selected_stocks.empty:
            return []
        
        codes = []
        for code in self.selected_stocks['股票代码'].tolist():
            if isinstance(code, str):
                clean_code = code.split('.')[0] if '.' in code else code
                codes.append(clean_code)
            else:
                codes.append(str(code))
        return codes


if __name__ == "__main__":
    # 测试选股
    selector = CustomStrategySelector()
    success, df, msg = selector.get_stocks()
    
    if success:
        print(f"\n✅ 测试成功: {msg}")
        print(f"股票代码列表: {selector.get_clean_codes()}")
    else:
        print(f"\n❌ 测试失败: {msg}")