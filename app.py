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

    def get_week_compare_date(target_date):
        exact_week_date = target_date - timedelta(days=7)
        normalized_dates = [pd.Timestamp(d).normalize() for d in all_dates]

        if exact_week_date in normalized_dates:
            return exact_week_date

        available = [d for d in normalized_dates if d < exact_week_date]
        if not available:
            return None
        return available[-1]

    lw_date = get_week_compare_date(selected_date)

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

    def get_weekly_sum_by_date(target_date, dim=None):
        """
        Get the sum of revenue for the given week, optionally grouped by a specific dimension (budget/channel).
        """
        if target_date is None:
            if dim:
                return pd.DataFrame(columns=[dim, "收入"])
            return 0

        # Calculate the start of the week for the target date
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        # Filter data for the given week
        week_df = df[(df["日期"] >= start_of_week) & (df["日期"] <= end_of_week)]

        if dim:
            return week_df.groupby(dim)["收入"].sum().reset_index()
        return week_df["收入"].sum()

    def get_weekly_comp(dim=None):
        """
        Compare weekly revenue for the selected date and the previous week.
        """
        if dim:
            t = get_weekly_sum_by_date(selected_date, dim)
            l = get_weekly_sum_by_date(lw_date, dim)

            res = (
                t.merge(l, on=dim, how="left", suffixes=("", "_上周"))
            )
            res.columns = [dim, "本周", "上周"]
            res = res.fillna(0)
        else:
            t_val = get_weekly_sum_by_date(selected_date)
            l_val = get_weekly_sum_by_date(lw_date)

            res = pd.DataFrame(
                [["总计", t_val, l_val]],
                columns=["维度", "本周", "上周"]
            )

        res["WoW涨跌"] = res["本周"] - res["上周"]
        return res

    weekly_total_row = get_weekly_comp()
    st.dataframe(weekly_total_row, width="stretch")

    # Display weekly comparison by budget and channel
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