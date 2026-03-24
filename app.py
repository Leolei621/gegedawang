import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta

st.set_page_config(page_title="收益对比深度看板", layout="wide")

password = st.sidebar.text_input("请输入访问密码", type="password")

if password == "123456":
    st.title("📊 高清收益分析看板")
    uploaded_file = st.file_uploader("上传数据文件", type=["csv", "xlsx"])

    if uploaded_file:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        df.columns = [c.strip() for c in df.columns]

        required_cols = ["日期", "收入", "预算", "渠道"]
        missing_cols = [c for c in required_cols if c not in df.columns]

        if missing_cols:
            st.error(f"文件缺少必要列：{', '.join(missing_cols)}")
            st.stop()

        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        df["收入"] = pd.to_numeric(df["收入"], errors="coerce").fillna(0)

        df = df.dropna(subset=["日期"])

        if df.empty:
            st.error("可用数据为空，请检查上传文件。")
            st.stop()

        latest_date = df["日期"].max()
        prev_date = latest_date - timedelta(days=1)
        lw_date = latest_date - timedelta(days=7)

        st.sidebar.header("图表筛选设置")
        view_mode = st.sidebar.radio("1. 选择分析维度：", ["总收益", "预算维度", "渠道维度"])

        all_budgets = sorted(df["预算"].dropna().astype(str).unique().tolist())
        all_channels = sorted(df["渠道"].dropna().astype(str).unique().tolist())

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

        def get_comp(dim=None):
            if dim:
                t = df[df["日期"] == latest_date].groupby(dim)["收入"].sum().reset_index()
                p = df[df["日期"] == prev_date].groupby(dim)["收入"].sum().reset_index()
                l = df[df["日期"] == lw_date].groupby(dim)["收入"].sum().reset_index()

                res = (
                    t.merge(p, on=dim, how="left", suffixes=("", "_昨日"))
                     .merge(l, on=dim, how="left", suffixes=("", "_上周"))
                )
                res.columns = [dim, "今日", "昨日", "上周同日"]
            else:
                t_val = df[df["日期"] == latest_date]["收入"].sum()
                p_val = df[df["日期"] == prev_date]["收入"].sum()
                l_val = df[df["日期"] == lw_date]["收入"].sum()
                res = pd.DataFrame(
                    [["总计", t_val, p_val, l_val]],
                    columns=["维度", "今日", "昨日", "上周同日"]
                )

            res = res.fillna(0)
            res["DoD涨跌"] = res["今日"] - res["昨日"]
            res["WoW涨跌"] = res["今日"] - res["上周同日"]
            return res

        total_row = get_comp()

        st.subheader(f"📍 实时概览 ({latest_date.date()})")
        m1, m2, m3 = st.columns(3)
        m1.metric("今日总额", f"¥{total_row['今日'][0]:,.2f}")
        m2.metric("较昨日", f"¥{total_row['今日'][0]:,.2f}", delta=f"{total_row['DoD涨跌'][0]:,.2f}")
        m3.metric("较上周同日", f"¥{total_row['今日'][0]:,.2f}", delta=f"{total_row['WoW涨跌'][0]:,.2f}")

        st.markdown("---")
        st.subheader(f"📈 {view_mode} 趋势追踪")

        if view_mode == "总收益":
            plot_df = df.groupby("日期")["收入"].sum().reset_index()
            fig = px.line(plot_df, x="日期", y="收入", title="总收益日趋势", markers=True, height=500)

        elif view_mode == "预算维度":
            if not selected_budgets:
                st.info("请先在左侧选择预算。")
                st.stop()
            plot_df = (
                df[df["预算"].astype(str).isin(selected_budgets)]
                .groupby(["日期", "预算"])["收入"]
                .sum()
                .reset_index()
            )
            fig = px.line(plot_df, x="日期", y="收入", color="预算", title="选定预算趋势对比", markers=True, height=600)

        else:
            if not selected_channels:
                st.info("请先在左侧选择渠道。")
                st.stop()
            plot_df = (
                df[df["渠道"].astype(str).isin(selected_channels)]
                .groupby(["日期", "渠道"])["收入"]
                .sum()
                .reset_index()
            )
            fig = px.line(plot_df, x="日期", y="收入", color="渠道", title="选定渠道趋势对比", markers=True, height=600)

        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, width="stretch")

        st.markdown("---")
        t1, t2 = st.tabs(["🍱 预算明细对比", "🚀 渠道明细对比"])

        with t1:
            budget_df = get_comp("预算")
            st.dataframe(budget_df, width="stretch")

        with t2:
            channel_df = get_comp("渠道")
            st.dataframe(channel_df, width="stretch")
    else:
        st.info("请先上传 CSV 或 Excel 文件。")
else:
    st.warning("👈 请在左侧输入密码解锁看板")