import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta

st.set_page_config(page_title="收益对比深度看板", layout="wide")

# =========================
# 密码区
# =========================
password = st.sidebar.text_input("请输入访问密码", type="password")

if password == "123456":
    st.title("📊 高清收益分析看板")

    SHEET_ID = "1FvWeyj2stVsWdgWPQVMoUIMX-4cjT1Lk"
    GID = "444452246"
    csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

    if st.button("🔄 手动刷新数据"):
        st.cache_data.clear()
        st.success("已刷新数据")

    # =========================
    # 数据加载
    # =========================
    @st.cache_data(ttl=60)
    def load_data():
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]

        required_cols = ["日期", "收入", "预算", "渠道"]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            st.error(f"Google 表格缺少必要列：{', '.join(missing_cols)}")
            st.stop()

        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        df["收入"] = pd.to_numeric(df["收入"], errors="coerce").fillna(0)
        df["预算"] = df["预算"].astype(str)
        df["渠道"] = df["渠道"].astype(str)

        df = df.dropna(subset=["日期"]).copy()
        df["日期"] = df["日期"].dt.normalize()
        df["周开始"] = df["日期"] - pd.to_timedelta(df["日期"].dt.weekday, unit="D")
        df["周结束"] = df["周开始"] + pd.Timedelta(days=6)

        if df.empty:
            st.error("当前表格没有可用数据，请检查 Google 表格内容。")
            st.stop()

        return df

    df = load_data()

    st.info("当前使用 Google 表格中的最新数据（自动刷新 + 可手动刷新）")

    # =========================
    # 基础日期/周列表
    # =========================
    all_dates = sorted(df["日期"].dropna().unique().tolist())
    latest_date = pd.Timestamp(all_dates[-1]).normalize()

    all_weeks = sorted(df["周开始"].dropna().unique().tolist())
    latest_week = pd.Timestamp(all_weeks[-1]).normalize()

    # =========================
    # 顶层分析模式
    # =========================
    st.sidebar.header("分析设置")
    analysis_granularity = st.sidebar.radio("选择时间维度：", ["按日分析", "按周分析"])

    view_mode = st.sidebar.radio("选择分析维度：", ["总收益", "预算维度", "渠道维度"])

    all_budgets = sorted(df["预算"].dropna().unique().tolist())
    all_channels = sorted(df["渠道"].dropna().unique().tolist())

    selected_budgets = []
    selected_channels = []

    if view_mode == "预算维度":
        selected_budgets = st.sidebar.multiselect(
            "选择要查看的预算：",
            all_budgets,
            default=all_budgets[:3] if len(all_budgets) >= 3 else all_budgets
        )
    elif view_mode == "渠道维度":
        selected_channels = st.sidebar.multiselect(
            "选择要查看的渠道：",
            all_channels,
            default=all_channels[:5] if len(all_channels) >= 5 else all_channels
        )

    # =========================
    # 通用函数 - 日维度
    # =========================
    def get_latest_available_before(target_date):
        available = [pd.Timestamp(d).normalize() for d in all_dates if pd.Timestamp(d).normalize() < target_date]
        if not available:
            return None
        return available[-1]

    def get_week_compare_date(target_date):
        exact_week_date = target_date - timedelta(days=7)
        normalized_dates = [pd.Timestamp(d).normalize() for d in all_dates]

        if exact_week_date in normalized_dates:
            return exact_week_date

        available = [d for d in normalized_dates if d < exact_week_date]
        if not available:
            return None
        return available[-1]

    def get_sum_by_date(target_date, dim=None):
        if target_date is None:
            if dim:
                return pd.DataFrame(columns=[dim, "收入"])
            return 0

        day_df = df[df["日期"] == pd.Timestamp(target_date).normalize()]

        if dim:
            return day_df.groupby(dim, as_index=False)["收入"].sum()
        return day_df["收入"].sum()

    def get_daily_comp(selected_date, prev_date, lw_date, dim=None):
        if dim:
            t = get_sum_by_date(selected_date, dim)
            p = get_sum_by_date(prev_date, dim)
            l = get_sum_by_date(lw_date, dim)

            res = (
                t.merge(p, on=dim, how="left", suffixes=("", "_前一日"))
                 .merge(l, on=dim, how="left", suffixes=("", "_上周"))
            )
            res.columns = [dim, "今日", "前一日", "上周同日"]
            res = res.fillna(0)
        else:
            t_val = get_sum_by_date(selected_date)
            p_val = get_sum_by_date(prev_date)
            l_val = get_sum_by_date(lw_date)

            res = pd.DataFrame(
                [["总计", t_val, p_val, l_val]],
                columns=["维度", "今日", "前一日", "上周同日"]
            )

        res["DoD涨跌"] = res["今日"] - res["前一日"]
        res["WoW涨跌"] = res["今日"] - res["上周同日"]
        return res

    def build_daily_share_compare(selected_date, lw_date, dim_name):
        current_df = get_sum_by_date(selected_date, dim_name)
        lastweek_df = get_sum_by_date(lw_date, dim_name)

        if current_df.empty:
            return pd.DataFrame(), pd.DataFrame()

        current_df = current_df.rename(columns={"收入": "今日收入"})
        lastweek_df = lastweek_df.rename(columns={"收入": "上周收入"})

        merged = current_df.merge(lastweek_df, on=dim_name, how="outer").fillna(0)

        current_total = merged["今日收入"].sum()
        lastweek_total = merged["上周收入"].sum()

        merged["今日占比"] = merged["今日收入"] / current_total if current_total > 0 else 0
        merged["上周占比"] = merged["上周收入"] / lastweek_total if lastweek_total > 0 else 0
        merged["占比变化"] = merged["今日占比"] - merged["上周占比"]

        def get_change_label(x):
            if x > 0:
                return f"增加 {x:.2%}"
            elif x < 0:
                return f"降低 {abs(x):.2%}"
            else:
                return "持平"

        merged["变化说明"] = merged["占比变化"].apply(get_change_label)

        display_df = merged.copy()
        display_df["今日占比"] = display_df["今日占比"].map(lambda x: f"{x:.2%}")
        display_df["上周占比"] = display_df["上周占比"].map(lambda x: f"{x:.2%}")
        display_df["占比变化"] = display_df["占比变化"].map(
            lambda x: f"+{x:.2%}" if x > 0 else (f"-{abs(x):.2%}" if x < 0 else "0.00%")
        )

        display_df = display_df.sort_values("今日收入", ascending=False)

        return merged, display_df[[dim_name, "今日收入", "今日占比", "上周占比", "占比变化", "变化说明"]]

    # =========================
    # 通用函数 - 周维度
    # =========================
    def get_previous_week(week_start):
        previous_week = pd.Timestamp(week_start).normalize() - pd.Timedelta(days=7)
        available = [pd.Timestamp(w).normalize() for w in all_weeks]
        if previous_week in available:
            return previous_week

        fallback = [w for w in available if w < pd.Timestamp(week_start).normalize()]
        return fallback[-1] if fallback else None

    def get_sum_by_week(week_start, dim=None):
        if week_start is None:
            if dim:
                return pd.DataFrame(columns=[dim, "收入"])
            return 0

        week_start = pd.Timestamp(week_start).normalize()
        week_df = df[df["周开始"] == week_start]

        if dim:
            return week_df.groupby(dim, as_index=False)["收入"].sum()
        return week_df["收入"].sum()

    def get_weekly_comp(selected_week, prev_week, dim=None):
        if dim:
            t = get_sum_by_week(selected_week, dim)
            p = get_sum_by_week(prev_week, dim)

            res = t.merge(p, on=dim, how="left", suffixes=("", "_上周"))
            res.columns = [dim, "本周", "上周"]
            res = res.fillna(0)
        else:
            t_val = get_sum_by_week(selected_week)
            p_val = get_sum_by_week(prev_week)

            res = pd.DataFrame(
                [["总计", t_val, p_val]],
                columns=["维度", "本周", "上周"]
            )

        res["WoW涨跌"] = res["本周"] - res["上周"]
        return res

    def build_weekly_share_compare(selected_week, prev_week, dim_name):
        current_df = get_sum_by_week(selected_week, dim_name)
        lastweek_df = get_sum_by_week(prev_week, dim_name)

        if current_df.empty:
            return pd.DataFrame(), pd.DataFrame()

        current_df = current_df.rename(columns={"收入": "本周收入"})
        lastweek_df = lastweek_df.rename(columns={"收入": "上周收入"})

        merged = current_df.merge(lastweek_df, on=dim_name, how="outer").fillna(0)

        current_total = merged["本周收入"].sum()
        lastweek_total = merged["上周收入"].sum()

        merged["本周占比"] = merged["本周收入"] / current_total if current_total > 0 else 0
        merged["上周占比"] = merged["上周收入"] / lastweek_total if lastweek_total > 0 else 0
        merged["占比变化"] = merged["本周占比"] - merged["上周占比"]

        def get_change_label(x):
            if x > 0:
                return f"增加 {x:.2%}"
            elif x < 0:
                return f"降低 {abs(x):.2%}"
            else:
                return "持平"

        merged["变化说明"] = merged["占比变化"].apply(get_change_label)

        display_df = merged.copy()
        display_df["本周占比"] = display_df["本周占比"].map(lambda x: f"{x:.2%}")
        display_df["上周占比"] = display_df["上周占比"].map(lambda x: f"{x:.2%}")
        display_df["占比变化"] = display_df["占比变化"].map(
            lambda x: f"+{x:.2%}" if x > 0 else (f"-{abs(x):.2%}" if x < 0 else "0.00%")
        )

        display_df = display_df.sort_values("本周收入", ascending=False)

        return merged, display_df[[dim_name, "本周收入", "本周占比", "上周占比", "占比变化", "变化说明"]]

    # =========================
    # 图表渲染函数
    # =========================
    def render_daily_share_pie(dim_name, title, selected_date, lw_date):
        raw_df, show_df = build_daily_share_compare(selected_date, lw_date, dim_name)

        if raw_df.empty:
            st.info(f"{title} 暂无数据")
            return

        c1, c2 = st.columns([1.2, 1])

        with c1:
            pie_df = raw_df[raw_df["今日收入"] > 0].copy()

            if pie_df.empty:
                st.info(f"{title} 今日无有效收入数据")
            else:
                fig_pie = px.pie(
                    pie_df,
                    names=dim_name,
                    values="今日收入",
                    hole=0.45,
                    title=title
                )
                fig_pie.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig_pie, use_container_width=True)

        with c2:
            st.markdown(f"#### {dim_name}占比 vs 上周同日")
            st.dataframe(show_df, use_container_width=True)

    def render_weekly_share_pie(dim_name, title, selected_week, prev_week):
        raw_df, show_df = build_weekly_share_compare(selected_week, prev_week, dim_name)

        if raw_df.empty:
            st.info(f"{title} 暂无数据")
            return

        c1, c2 = st.columns([1.2, 1])

        with c1:
            pie_df = raw_df[raw_df["本周收入"] > 0].copy()

            if pie_df.empty:
                st.info(f"{title} 本周无有效收入数据")
            else:
                fig_pie = px.pie(
                    pie_df,
                    names=dim_name,
                    values="本周收入",
                    hole=0.45,
                    title=title
                )
                fig_pie.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig_pie, use_container_width=True)

        with c2:
            st.markdown(f"#### {dim_name}占比 vs 上周")
            st.dataframe(show_df, use_container_width=True)

    # =========================
    # 按日分析
    # =========================
    if analysis_granularity == "按日分析":
        selected_date_input = st.sidebar.selectbox(
            "选择查看日期：",
            all_dates,
            index=len(all_dates) - 1,
            format_func=lambda x: pd.Timestamp(x).strftime("%Y-%m-%d")
        )
        selected_date = pd.Timestamp(selected_date_input).normalize()

        prev_date = get_latest_available_before(selected_date)
        lw_date = get_week_compare_date(selected_date)

        total_row = get_daily_comp(selected_date, prev_date, lw_date)

        st.subheader(f"📍 实时概览（按日） {selected_date.strftime('%Y-%m-%d')}")

        prev_label = prev_date.strftime("%Y-%m-%d") if prev_date is not None else "无可用前一日"
        lw_label = lw_date.strftime("%Y-%m-%d") if lw_date is not None else "无可用上周同日"

        m1, m2, m3 = st.columns(3)
        m1.metric("当日收益", f"¥{total_row['今日'][0]:,.2f}")
        m2.metric(
            f"前一日收益（{prev_label}）",
            f"¥{total_row['前一日'][0]:,.2f}",
            delta=f"{total_row['DoD涨跌'][0]:,.2f}"
        )
        m3.metric(
            f"上周同日收益（{lw_label}）",
            f"¥{total_row['上周同日'][0]:,.2f}",
            delta=f"{total_row['WoW涨跌'][0]:,.2f}"
        )

        st.markdown("---")
        st.subheader(f"📈 {view_mode} 趋势追踪（按日）")

        if view_mode == "总收益":
            plot_df = df.groupby("日期", as_index=False)["收入"].sum()
            fig = px.line(
                plot_df,
                x="日期",
                y="收入",
                title="总收益日趋势",
                markers=True,
                height=500
            )
            fig.add_vline(x=selected_date, line_dash="dash", line_color="red")

        elif view_mode == "预算维度":
            if not selected_budgets:
                st.info("请先在左侧选择预算。")
                st.stop()

            plot_df = (
                df[df["预算"].isin(selected_budgets)]
                .groupby(["日期", "预算"], as_index=False)["收入"]
                .sum()
            )
            fig = px.line(
                plot_df,
                x="日期",
                y="收入",
                color="预算",
                title="选定预算趋势对比（按日）",
                markers=True,
                height=600
            )
            fig.add_vline(x=selected_date, line_dash="dash", line_color="red")

        else:
            if not selected_channels:
                st.info("请先在左侧选择渠道。")
                st.stop()

            plot_df = (
                df[df["渠道"].isin(selected_channels)]
                .groupby(["日期", "渠道"], as_index=False)["收入"]
                .sum()
            )
            fig = px.line(
                plot_df,
                x="日期",
                y="收入",
                color="渠道",
                title="选定渠道趋势对比（按日）",
                markers=True,
                height=600
            )
            fig.add_vline(x=selected_date, line_dash="dash", line_color="red")

        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("🥧 预算 / 渠道占比对比（按日）")

        pie_tab1, pie_tab2 = st.tabs(["🍱 预算占比图", "🚀 渠道占比图"])

        with pie_tab1:
            render_daily_share_pie("预算", "当日预算占比图", selected_date, lw_date)

        with pie_tab2:
            render_daily_share_pie("渠道", "当日渠道占比图", selected_date, lw_date)

        st.markdown("---")
        detail_tab1, detail_tab2 = st.tabs(["🍱 预算明细对比", "🚀 渠道明细对比"])

        with detail_tab1:
            st.dataframe(get_daily_comp(selected_date, prev_date, lw_date, "预算"), use_container_width=True)

        with detail_tab2:
            st.dataframe(get_daily_comp(selected_date, prev_date, lw_date, "渠道"), use_container_width=True)

    # =========================
    # 按周分析
    # =========================
    else:
        selected_week_input = st.sidebar.selectbox(
            "选择查看周（周一）：",
            all_weeks,
            index=len(all_weeks) - 1,
            format_func=lambda x: f"{pd.Timestamp(x).strftime('%Y-%m-%d')} ~ {(pd.Timestamp(x) + pd.Timedelta(days=6)).strftime('%Y-%m-%d')}"
        )
        selected_week = pd.Timestamp(selected_week_input).normalize()
        selected_week_end = selected_week + pd.Timedelta(days=6)

        prev_week = get_previous_week(selected_week)
        prev_week_label = (
            f"{prev_week.strftime('%Y-%m-%d')} ~ {(prev_week + pd.Timedelta(days=6)).strftime('%Y-%m-%d')}"
            if prev_week is not None else "无可用上周"
        )

        weekly_total_row = get_weekly_comp(selected_week, prev_week)

        st.subheader(
            f"📅 周度概览（按周） {selected_week.strftime('%Y-%m-%d')} ~ {selected_week_end.strftime('%Y-%m-%d')}"
        )

        m1, m2 = st.columns(2)
        m1.metric("本周收益", f"¥{weekly_total_row['本周'][0]:,.2f}")
        m2.metric(
            f"上周收益（{prev_week_label}）",
            f"¥{weekly_total_row['上周'][0]:,.2f}",
            delta=f"{weekly_total_row['WoW涨跌'][0]:,.2f}"
        )

        st.markdown("---")
        st.subheader(f"📈 {view_mode} 趋势追踪（按周）")

        if view_mode == "总收益":
            weekly_plot_df = df.groupby("周开始", as_index=False)["收入"].sum()
            fig_weekly = px.line(
                weekly_plot_df,
                x="周开始",
                y="收入",
                title="总收益周趋势",
                markers=True,
                height=500
            )
            fig_weekly.add_vline(x=selected_week, line_dash="dash", line_color="red")

        elif view_mode == "预算维度":
            if not selected_budgets:
                st.info("请先在左侧选择预算。")
                st.stop()

            weekly_plot_df = (
                df[df["预算"].isin(selected_budgets)]
                .groupby(["周开始", "预算"], as_index=False)["收入"]
                .sum()
            )
            fig_weekly = px.line(
                weekly_plot_df,
                x="周开始",
                y="收入",
                color="预算",
                title="选定预算趋势对比（按周）",
                markers=True,
                height=600
            )
            fig_weekly.add_vline(x=selected_week, line_dash="dash", line_color="red")

        else:
            if not selected_channels:
                st.info("请先在左侧选择渠道。")
                st.stop()

            weekly_plot_df = (
                df[df["渠道"].isin(selected_channels)]
                .groupby(["周开始", "渠道"], as_index=False)["收入"]
                .sum()
            )
            fig_weekly = px.line(
                weekly_plot_df,
                x="周开始",
                y="收入",
                color="渠道",
                title="选定渠道趋势对比（按周）",
                markers=True,
                height=600
            )
            fig_weekly.add_vline(x=selected_week, line_dash="dash", line_color="red")

        fig_weekly.update_layout(hovermode="x unified")
        st.plotly_chart(fig_weekly, use_container_width=True)

        st.markdown("---")
        st.subheader("🥧 预算 / 渠道占比对比（按周）")

        pie_tab1, pie_tab2 = st.tabs(["🍱 预算周占比图", "🚀 渠道周占比图"])

        with pie_tab1:
            render_weekly_share_pie("预算", "本周预算占比图", selected_week, prev_week)

        with pie_tab2:
            render_weekly_share_pie("渠道", "本周渠道占比图", selected_week, prev_week)

        st.markdown("---")
        detail_tab1, detail_tab2 = st.tabs(["🍱 预算周明细对比", "🚀 渠道周明细对比"])

        with detail_tab1:
            st.dataframe(get_weekly_comp(selected_week, prev_week, "预算"), use_container_width=True)

        with detail_tab2:
            st.dataframe(get_weekly_comp(selected_week, prev_week, "渠道"), use_container_width=True)

else:
    st.warning("👈 请在左侧输入密码解锁看板")