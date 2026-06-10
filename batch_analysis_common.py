"""
公共批量分析模块
提取自 longhubang_ui.py / main_force_ui.py 的重复代码
提供统一的批量股票分析UI和执行逻辑
"""

import time
import concurrent.futures
import streamlit as st
import config


def clear_batch_state(prefix: str):
    """清除批量分析相关的 session_state 键"""
    keys = [f'{prefix}_batch_trigger', f'{prefix}_batch_codes', f'{prefix}_batch_results']
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]


def render_batch_results_display(
    batch_results: dict,
    prefix: str,
    display_results_fn,
    back_label: str
):
    """
    显示批量分析结果页面（含返回/重新分析按钮）
    
    Args:
        batch_results: 批量分析结果字典
        prefix: session_state 键前缀（如 'longhubang', 'main_force'）
        display_results_fn: 显示结果的回调函数
        back_label: 返回按钮的标签文字
    """
    display_results_fn(batch_results)

    col_back, col_clear = st.columns(2)
    with col_back:
        if st.button(f"🔙 {back_label}", width='stretch'):
            clear_batch_state(prefix)
            st.rerun()

    with col_clear:
        if st.button("🔄 重新分析", width='stretch'):
            if f'{prefix}_batch_results' in st.session_state:
                del st.session_state[f'{prefix}_batch_results']
            st.rerun()


def render_batch_analysis_page(
    prefix: str,
    title: str,
    display_results_fn,
    back_label: str,
    enabled_analysts_config: dict = None,
    extra_debug_info: dict = None
):
    """
    渲染通用的批量分析页面，包含：
    - 结果展示（如果已有结果）
    - 股票代码检查
    - 分析模式选择（顺序/并行）
    - 进度条
    - 结果保存

    Args:
        prefix: session_state 键前缀（如 'longhubang', 'main_force'）
        title: 页面标题
        display_results_fn: 显示结果的回调函数
        back_label: 返回按钮标签
        enabled_analysts_config: 分析师配置，默认启用技术面/基本面/资金流/风控
        extra_debug_info: 额外调试信息（可选）
    """
    st.markdown(f"## 🚀 {title}")
    st.markdown("---")

    # 默认分析师配置
    if enabled_analysts_config is None:
        enabled_analysts_config = {
            'technical': True,
            'fundamental': True,
            'fund_flow': True,
            'risk': True,
            'sentiment': False,
            'news': False
        }

    # 检查是否已有分析结果
    if st.session_state.get(f'{prefix}_batch_results'):
        render_batch_results_display(
            st.session_state[f'{prefix}_batch_results'],
            prefix,
            display_results_fn,
            back_label
        )
        return

    # 获取股票代码列表
    stock_codes = st.session_state.get(f'{prefix}_batch_codes', [])

    if not stock_codes:
        st.error("未找到股票代码列表")
        if f'{prefix}_batch_trigger' in st.session_state:
            del st.session_state[f'{prefix}_batch_trigger']
        return

    # 显示股票信息（最多显示10个）
    display_codes = ', '.join(stock_codes[:10])
    suffix = '...' if len(stock_codes) > 10 else ''
    st.info(f"即将分析 {len(stock_codes)} 只股票：{display_codes}{suffix}")

    # 返回按钮
    if st.button("🔙 取消返回", type="secondary"):
        clear_batch_state(prefix)
        st.rerun()

    st.markdown("---")

    # 分析选项
    col1, col2 = st.columns(2)

    with col1:
        analysis_mode = st.selectbox(
            "分析模式",
            options=["sequential", "parallel"],
            format_func=lambda x: "顺序分析（稳定）" if x == "sequential" else "并行分析（快速）",
            help="顺序分析较慢但稳定，并行分析更快但消耗更多资源",
            key=f"{prefix}_analysis_mode"
        )

    with col2:
        if analysis_mode == "parallel":
            max_workers = st.number_input(
                "并行线程数",
                min_value=2,
                max_value=5,
                value=3,
                help="同时分析的股票数量",
                key=f"{prefix}_max_workers"
            )
        else:
            max_workers = 1

    st.markdown("---")

    # 开始分析按钮
    col_confirm, col_cancel = st.columns(2)

    start_analysis = False
    with col_confirm:
        if st.button("🚀 确认开始分析", type="primary", width='stretch', key=f"{prefix}_start_btn"):
            start_analysis = True

    with col_cancel:
        if st.button("❌ 取消", type="secondary", width='stretch', key=f"{prefix}_cancel_btn"):
            clear_batch_state(prefix)
            st.rerun()

    if not start_analysis:
        return

    # 执行分析
    from app import analyze_single_stock_for_batch
    selected_model = config.DEFAULT_MODEL_NAME
    period = '1y'

    st.markdown("---")
    st.info("⏳ 正在执行批量分析，请稍候...")

    # 调试信息（可选）
    if extra_debug_info:
        with st.expander("🔍 调试信息", expanded=False):
            for key, value in extra_debug_info.items():
                st.write(f"**{key}**: {value}")

    # 进度显示
    progress_bar = st.progress(0)
    status_text = st.empty()

    results = []
    start_time = time.time()

    if analysis_mode == "sequential":
        # 顺序分析
        for i, code in enumerate(stock_codes):
            status_text.text(f"正在分析 {code} ({i+1}/{len(stock_codes)})")
            progress_bar.progress((i + 1) / len(stock_codes))

            try:
                result = analyze_single_stock_for_batch(
                    symbol=code,
                    period=period,
                    enabled_analysts_config=enabled_analysts_config,
                    selected_model=selected_model
                )
                results.append({
                    "code": code,
                    "result": result
                })
            except Exception as e:
                results.append({
                    "code": code,
                    "result": {"success": False, "error": str(e)}
                })
    else:
        # 并行分析
        status_text.text(f"并行分析 {len(stock_codes)} 只股票（{max_workers}线程）...")

        def analyze_one(code):
            try:
                result = analyze_single_stock_for_batch(
                    symbol=code,
                    period=period,
                    enabled_analysts_config=enabled_analysts_config,
                    selected_model=selected_model
                )
                return {"code": code, "result": result}
            except Exception as e:
                return {"code": code, "result": {"success": False, "error": str(e)}}

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(analyze_one, code): code for code in stock_codes}

            completed = 0
            for future in concurrent.futures.as_completed(futures):
                completed += 1
                code = futures[future]
                progress_bar.progress(completed / len(stock_codes))
                status_text.text(f"已完成 {completed}/{len(stock_codes)} ({code})")
                try:
                    results.append(future.result())
                except Exception as e:
                    results.append({
                        "code": code,
                        "result": {"success": False, "error": str(e)}
                    })

    # 清除进度
    progress_bar.empty()
    status_text.empty()

    # 计算统计
    elapsed_time = time.time() - start_time
    success_count = sum(1 for r in results if r.get("result", {}).get("success"))
    failed_count = len(results) - success_count

    st.success(f"✅ 批量分析完成！成功 {success_count} 只，失败 {failed_count} 只，耗时 {elapsed_time:.1f}秒")

    # 保存结果到 session_state
    st.session_state[f'{prefix}_batch_results'] = {
        "results": results,
        "total": len(results),
        "success": success_count,
        "failed": failed_count,
        "elapsed_time": elapsed_time
    }

    time.sleep(0.5)
    st.rerun()


def render_batch_results_table(batch_results: dict, get_result_detail_fn=None):
    """
    通用的批量分析结果表格展示

    Args:
        batch_results: 批量结果字典
        get_result_detail_fn: 可选的详情提取函数，默认从 result 中提取
    """
    st.markdown("### 📊 批量分析结果")

    results = batch_results.get("results", [])
    total = batch_results.get("total", 0)
    success = batch_results.get("success", 0)
    failed = batch_results.get("failed", 0)
    elapsed = batch_results.get("elapsed_time", 0)

    # 统计概览
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总计", total)
    with col2:
        st.metric("成功", success)
    with col3:
        st.metric("失败", failed)
    with col4:
        st.metric("耗时", f"{elapsed:.1f}秒")

    st.markdown("---")

    # 逐个显示结果
    for i, item in enumerate(results):
        code = item.get("code", "未知")
        result = item.get("result", {})
        is_success = result.get("success", False)

        icon = "✅" if is_success else "❌"
        with st.expander(f"{icon} {code} - {'分析成功' if is_success else '分析失败'}", expanded=False):
            if is_success:
                if get_result_detail_fn:
                    get_result_detail_fn(result)
                else:
                    # 默认展示
                    analysis = result.get("analysis", {})
                    if isinstance(analysis, dict):
                        for key, value in analysis.items():
                            if isinstance(value, str) and len(value) > 0:
                                st.markdown(f"**{key}**: {value}")
                    else:
                        st.markdown(str(analysis))
            else:
                error = result.get("error", "未知错误")
                st.error(f"错误: {error}")