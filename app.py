import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta

st.set_page_config(page_title="收益对比深度看板", layout="wide")

password = st.sidebar.text_input("请输入访问密码", type="password")

if password == "123456":
    st.title("📊 高清收益分析看板")

    SHEET_ID = "1FvWeyj2stVsWdgWPQVMoUIMX-4cjT1Lk"
    GID = "444452246"
    csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

    if st.button("🔄 手动刷新数据"):
        st.cache_data.clear()
        st.success("已刷新数据")

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

        df = df.dropna(subset=["日期"])

        if df.empty:
            st.error("当前表格没有可用数据，请检查 Google 表格内容。")
            st.stop()

        return df

    df = load_data()

    st.info("当前使用 Google 表格中的最新数据（自动刷新 + 可手动刷新）")

    all_dates = sorted(df["日期"].dt.normalize().unique().tolist())
    latest_date = all_dates[-1]

    selected_date_input = st.sidebar.selectbox(
        "选择查看日期：",
        all_dates,
        index=len(all_dates) - 1,
        format_func=lambda x: pd.Timestamp(x).strftime("%Y-%m-%d")
    )
    selected_date = pd.Timestamp(selected_date_input).normalize()

    def get_latest_available_before(target_date):
        available = [d for d in all_dates if pd.Timestamp(d).normalize() < target_date]
        if not available:
            return None
        return pd.Timestamp(available[-1]).normalize()

    prev_date = get_latest_available_before(selected_date)

    st.sidebar.header("图表筛选设置")
    view_mode = st.sidebar.radio("1. 选择分析维度：", ["总收益", "预算维度", "渠道维度"])

    all_budgets = sorted(df["预算"].dropna().unique().tolist())
    all_channels = sorted(df["渠道"].dropna().unique().tolist())

    selected_budgets = []
    selected_channels = []

    if view_mode == "预算维度":
        selected_budgets = st.sidebar.multiselect(
            "2. 选择要查看的预算：",
            all_budgets,
            default=all_budgets[:3] if len(all_budgets) >= 3 else all_budgets
        )
    elif view_mode == "渠道维度":
        selected_channels = st.sidebar.multiselect(
            "2. 选择要查看的渠道：",
            all_channels,
            default=all_channels[:5] if len(all_channels) >= 5 else all_channels
        )

    def get_sum_by_date(target_date, dim=None):
        if target_date is None:
            if dim:
                return pd.DataFrame(columns=[dim, "收入"])
            return 0

        day_df = df[df["日期"].dt.normalize() == target_date]

        if dim:
            return day_df.groupby(dim)["收入"].sum().reset_index()
        return day_df["收入"].sum()

    def get_comp(dim=None):
        if dim:
            t = get_sum_by_date(selected_date, dim)
            p = get_sum_by_date(prev_date, dim)

            res = (
                t.merge(p, on=dim, how="left", suffixes=("", "_前一日"))
            )
            res.columns = [dim, "今日", "前一日"]
            res = res.fillna(0)
        else:
            t_val = get_sum_by_date(selected_date)
            p_val = get_sum_by_date(prev_date)

            res = pd.DataFrame(
                [["总计", t_val, p_val]],
                columns=["维度", "今日", "前一日"]
            )

        res["DoD涨跌"] = res["今日"] - res["前一日"]
        return res

    total_row = get_comp()

    st.subheader(f"📍 实时概览 ({selected_date.date()})")

    if prev_date is not None:
        prev_label = prev_date.strftime("%Y-%m-%d")
    else:
        prev_label = "无可用前一日"

    m1, m2 = st.columns(2)
    m1.metric("当日收益", f"¥{total_row['今日'][0]:,.2f}")
    m2.metric(
        f"前一日收益（{prev_label}）",
        f"¥{total_row['前一日'][0]:,.2f}",
        delta=f"{total_row['DoD涨跌'][0]:,.2f}"
    )

    st.markdown("---")
    st.subheader(f"📈 {view_mode} 趋势追踪")

    if view_mode == "总收益":
        plot_df = df.groupby(df["日期"].dt.normalize())["收入"].sum().reset_index()
        plot_df.columns = ["日期", "收入"]
        fig = px.line(plot_df, x="日期", y="收入", title="总收益日趋势", markers=True, height=500)
        fig.add_vline(x=selected_date, line_dash="dash", line_color="red")

    elif view_mode == "预算维度":
        if not selected_budgets:
            st.info("请先在左侧选择预算。")
            st.stop()

        plot_df = (
            df[df["预算"].isin(selected_budgets)]
            .assign(日期=df["日期"].dt.normalize())
            .groupby(["日期", "预算"])["收入"]
            .sum()
            .reset_index()
        )
        fig = px.line(
            plot_df,
            x="日期",
            y="收入",
            color="预算",
            title="选定预算趋势对比",
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
            .assign(日期=df["日期"].dt.normalize())
            .groupby(["日期", "渠道"])["收入"]
            .sum()
            .reset_index()
        )
        fig = px.line(
            plot_df,
            x="日期",
            y="收入",
            color="渠道",
            title="选定渠道趋势对比",
            markers=True,
            height=600
        )
        fig.add_vline(x=selected_date, line_dash="dash", line_color="red")

    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, width="stretch")

    st.markdown("---")
    t1, t2 = st.tabs(["🍱 预算明细对比", "🚀 渠道明细对比"])

    with t1:
        st.dataframe(get_comp("预算"), width="stretch")

    with t2:
        st.dataframe(get_comp("渠道"), width="stretch")

    # 👉 新增：按周收入对比
    st.subheader("📅 实时周收入对比")
    def get_sum_by_week(target_date, dim=None):
        """
        获取指定周的收益总和，按维度（预算/渠道）进行分组
        """
        if target_date is None:
            return 0

        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        week_df = df[(df["日期"] >= start_of_week) & (df["日期"] <= end_of_week)]

        if dim:
            return week_df.groupby(dim)["收入"].sum().reset_index()
        return week_df["收入"].sum()

    def get_weekly_comp(dim=None):
        """
        比较当前周的收益，按预算/渠道维度
        """
        if dim:
            current_week = get_sum_by_week(selected_date, dim)
            prev_week = get_sum_by_week(prev_date, dim)

            res = pd.DataFrame(
                {
                    dim: ["本周", "前一周"],
                    "本周": [current_week, prev_week],
                    "DoW涨跌": [current_week - prev_week, None]
                }
            )

        else:
            current_week_val = get_sum_by_week(selected_date)
            prev_week_val = get_sum_by_week(prev_date)

            res = pd.DataFrame(
                [["总计", current_week_val, prev_week_val]],
                columns=["维度", "本周", "前一周"]
            )
            res["DoW涨跌"] = res["本周"] - res["前一周"]

        return res

    weekly_total_row = get_weekly_comp()
    st.dataframe(weekly_total_row, width="stretch")

    t1, t2 = st.tabs(["🍱 预算周明细对比", "🚀 渠道周明细对比"])

    with t1:
        st.dataframe(get_weekly_comp("预算"), width="stretch")

    with t2:
        st.dataframe(get_weekly_comp("渠道"), width="stretch")

    # Weekly data plot
    weekly_data = df.groupby(df['日期'].dt.to_period('W').dt.start_time)['收入'].sum().reset_index()
    st.dataframe(weekly_data, width="stretch")

    fig_weekly = px.line(
        weekly_data,
        x='日期',
        y='收入',
        title="每周收入对比",
        markers=True,
        height=500
    )
    st.plotly_chart(fig_weekly, width="stretch")

else:
    st.warning("👈 请在左侧输入密码解锁看板")