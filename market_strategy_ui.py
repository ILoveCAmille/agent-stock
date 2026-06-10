"""
市场策略分析UI模块
展示市场指数分析和进攻/防守策略
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime
import json


def display_market_strategy():
    """显示市场策略分析页面"""
    
    st.markdown("""
    <style>
        .strategy-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1.5rem;
            border-radius: 15px;
            color: white;
            margin-bottom: 1rem;
        }
        .metric-card {
            background: white;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }
        .bullish { color: #ff4444; }
        .bearish { color: #00c853; }
        .neutral { color: #ffbb33; }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("📊 市场策略分析")
    st.markdown("---")
    
    # 侧边栏控制
    with st.sidebar:
        st.subheader("⚙️ 分析设置")
        auto_refresh = st.checkbox("自动刷新", value=False)
        analysis_depth = st.selectbox("分析深度", ["快速", "标准", "深度"], index=1)
        
        if st.button("🔄 刷新分析", use_container_width=True):
            st.session_state.market_analysis = None
    
    # 主要内容区
    tab1, tab2, tab3 = st.tabs(["📈 市场概览", "🎯 策略建议", "📊 板块分析"])
    
    with tab1:
        display_market_overview()
    
    with tab2:
        display_strategy_advice()
    
    with tab3:
        display_sector_analysis()


def display_market_overview():
    """显示市场概览"""
    st.subheader("核心指数监控")
    
    # 使用缓存或实时获取
    if 'market_analysis' not in st.session_state or st.session_state.market_analysis is None:
        with st.spinner("正在分析市场..."):
            try:
                from offensive_defensive_strategy import strategy_engine
                st.session_state.market_analysis = strategy_engine.analyze_and_recommend()
            except Exception as e:
                st.error(f"分析失败: {e}")
                return
    
    analysis = st.session_state.market_analysis
    market_analysis = analysis.get('market_analysis', {})
    market_state = market_analysis.get('market_state', {})
    market_score = market_analysis.get('market_score', 50)
    
    # 市场得分仪表盘
    col1, col2, col3 = st.columns(3)
    
    with col1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=market_score,
            title={'text': "市场得分"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 30], 'color': "red"},
                    {'range': [30, 50], 'color': "orange"},
                    {'range': [50, 70], 'color': "yellow"},
                    {'range': [70, 100], 'color': "green"},
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 4},
                    'thickness': 0.75,
                    'value': market_score
                }
            }
        ))
        fig.update_layout(height=250)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.metric("市场状态", market_state.get('name', '未知'))
        strategy = analysis.get('strategy', {})
        st.metric("策略类型", strategy.get('name', '未知'))
    
    with col3:
        position_advice = analysis.get('position_advice', {})
        st.metric("建议仓位", f"{position_advice.get('suggested_position', 0.5)*100:.0f}%")
        risk_management = analysis.get('risk_management', {})
        st.metric("风险等级", risk_management.get('risk_level', 'medium'))
    
    # 核心指数表格
    st.subheader("核心指数详情")
    indices = market_analysis.get('indices', {})
    
    if indices:
        index_data = []
        for code, data in indices.items():
            indicators = data.get('indicators', {})
            index_data.append({
                '指数': data['name'],
                '当前价': f"{indicators.get('current_price', 0):.2f}",
                '涨跌幅': f"{indicators.get('daily_change', 0):.2f}%",
                'RSI': f"{indicators.get('rsi14', 50):.1f}",
                '趋势': indicators.get('trend', 'sideways'),
                '得分': data.get('score', 50),
            })
        
        df = pd.DataFrame(index_data)
        st.dataframe(df, use_container_width=True)
    
    # 信号列表
    st.subheader("交易信号")
    signals = market_analysis.get('signals', [])
    
    if signals:
        for signal in signals:
            priority_icon = "🔴" if signal.get('priority') == 'high' else "🟡"
            signal_type = signal.get('type', '')
            
            if signal_type == 'position':
                st.info(f"{priority_icon} **仓位信号**: {signal['description']}")
            elif signal_type == 'sector':
                st.warning(f"{priority_icon} **板块信号**: {signal['description']}")
            elif signal_type == 'index_oversold':
                st.success(f"{priority_icon} **超卖信号**: {signal['description']}")
            elif signal_type == 'index_overbought':
                st.error(f"{priority_icon} **超买信号**: {signal['description']}")
            else:
                st.info(f"{priority_icon} {signal['description']}")
    else:
        st.info("暂无交易信号")


def display_strategy_advice():
    """显示策略建议"""
    st.subheader("进攻/防守策略")
    
    if 'market_analysis' not in st.session_state:
        st.warning("请先在市场概览中进行分析")
        return
    
    analysis = st.session_state.market_analysis
    strategy = analysis.get('strategy', {})
    position_advice = analysis.get('position_advice', {})
    risk_management = analysis.get('risk_management', {})
    
    # 策略卡片
    strategy_type = strategy.get('type', 'balanced')
    
    strategy_colors = {
        'aggressive_offensive': '#ff4444',
        'moderate_offensive': '#ff8800',
        'balanced': '#ffbb33',
        'moderate_defensive': '#00c853',
        'strong_defensive': '#0066cc',
    }
    
    color = strategy_colors.get(strategy_type, '#ffbb33')
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {color} 0%, {color}88 100%); 
                padding: 2rem; border-radius: 15px; color: white; margin-bottom: 1rem;">
        <h2 style="margin:0;">{strategy.get('name', '未知')}</h2>
        <p style="margin:0.5rem 0 0 0;">{strategy.get('description', '')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 仓位配置图
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("仓位配置")
        details = position_advice.get('details', {})
        
        labels = ['核心仓位', '卫星仓位', '现金储备']
        values = [
            details.get('core_position', 0.3) * 100,
            details.get('satellite_position', 0.15) * 100,
            details.get('cash_reserve', 0.55) * 100,
        ]
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=.3,
            marker_colors=['#ff4444', '#ffbb33', '#00c853']
        )])
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("风险参数")
        st.metric("止损线", f"{risk_management.get('stop_loss', 0)*100:.1f}%")
        st.metric("止盈线", f"{risk_management.get('take_profit', 0)*100:.1f}%")
        st.metric("单股最大仓位", f"{risk_management.get('max_position_per_stock', 0.2)*100:.0f}%")
    
    # 板块建议
    st.subheader("板块配置建议")
    sector_advice = analysis.get('sector_advice', {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**关注板块**")
        focus_sectors = sector_advice.get('focus_sectors', [])
        for sector in focus_sectors:
            st.success(f"✅ {sector}")
    
    with col2:
        st.markdown("**强势板块**")
        strong = sector_advice.get('strong_sectors', [])
        if strong:
            for s in strong[:3]:
                st.info(f"📈 {s['name']}: 得分 {s['score']}")
    
    # 选股建议
    st.subheader("选股建议")
    stock_suggestions = analysis.get('stock_suggestions', [])
    
    if stock_suggestions:
        for suggestion in stock_suggestions:
            with st.expander(f"📊 {suggestion['sector']}板块"):
                st.write(f"**策略**: {suggestion['strategy']}")
                criteria = suggestion.get('criteria', {})
                st.write(f"**选股重点**: {criteria.get('focus', '')}")
                st.write(f"**PE范围**: {criteria.get('pe_range', '')}")
                st.write(f"**示例股票**: {', '.join(suggestion.get('examples', []))}")
    
    # 行动项
    st.subheader("行动项")
    action_items = analysis.get('action_items', [])
    
    if action_items:
        for item in action_items:
            priority = item.get('priority', 'medium')
            if priority == 'high':
                st.error(f"🔴 **{item['action']}**: {item['description']}")
            else:
                st.warning(f"🟡 **{item['action']}**: {item['description']}")
    
    # 风险提示
    warnings = risk_management.get('warnings', [])
    if warnings:
        st.subheader("⚠️ 风险提示")
        for warning in warnings:
            st.warning(warning)


def display_sector_analysis():
    """显示板块分析"""
    st.subheader("板块轮动分析")
    
    if 'market_analysis' not in st.session_state:
        st.warning("请先在市场概览中进行分析")
        return
    
    analysis = st.session_state.market_analysis
    market_analysis = analysis.get('market_analysis', {})
    sector_rotation = market_analysis.get('sector_rotation', {})
    
    # 板块得分图
    strong = sector_rotation.get('strong_sectors', [])
    weak = sector_rotation.get('weak_sectors', [])
    
    if strong or weak:
        all_sectors = strong + weak
        
        fig = go.Figure()
        
        # 强势板块
        if strong:
            fig.add_trace(go.Bar(
                x=[s['name'] for s in strong],
                y=[s['score'] for s in strong],
                name='强势板块',
                marker_color='#ff4444'
            ))
        
        # 弱势板块
        if weak:
            fig.add_trace(go.Bar(
                x=[s['name'] for s in weak],
                y=[s['score'] for s in weak],
                name='弱势板块',
                marker_color='#00c853'
            ))
        
        fig.update_layout(
            title='板块得分对比',
            xaxis_title='板块',
            yaxis_title='得分',
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # 板块详情表格
    if strong:
        st.subheader("📈 强势板块详情")
        df_strong = pd.DataFrame(strong)
        df_strong = df_strong.rename(columns={
            'name': '板块名称',
            'score': '得分',
            'trend': '趋势',
            'pct_5d': '5日涨幅',
            'pct_10d': '10日涨幅',
        })
        st.dataframe(df_strong[['板块名称', '得分', '趋势', '5日涨幅', '10日涨幅']], 
                     use_container_width=True)
    
    if weak:
        st.subheader("📉 弱势板块详情")
        df_weak = pd.DataFrame(weak)
        df_weak = df_weak.rename(columns={
            'name': '板块名称',
            'score': '得分',
            'trend': '趋势',
            'pct_5d': '5日涨幅',
            'pct_10d': '10日涨幅',
        })
        st.dataframe(df_weak[['板块名称', '得分', '趋势', '5日涨幅', '10日涨幅']], 
                     use_container_width=True)
    
    # 轮动建议
    st.subheader("轮动建议")
    rotation_signal = sector_rotation.get('rotation_signal', 'neutral')
    
    if rotation_signal == 'active':
        st.success("🟢 板块轮动活跃，可跟随强势板块轮动操作")
    elif rotation_signal == 'weak':
        st.warning("🟡 板块普跌，建议减少操作，等待企稳")
    else:
        st.info("🔵 板块分化，精选个股为主")
    
    recommendations = sector_rotation.get('recommendations', [])
    for rec in recommendations:
        st.info(f"💡 {rec}")


if __name__ == "__main__":
    display_market_strategy()
