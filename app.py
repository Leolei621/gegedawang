
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

    csv_url = (
        f"https://docs.google.com/spreadsheets/d/"
        f"{SHEET_ID}/export?format=csv&gid={GID}"
    )

    if st.button("🔄 手动刷新数据"):
        st.cache_data.clear()
        st.success("已刷新数据")

    # =========================
    # 数据加载
    # =========================
    @st.cache_data(ttl=60)
    def load_data():
        data = pd.read_csv(csv_url)
        data.columns = [str(c).strip() for c in data.columns]

        required_cols = ["日期", "收入", "预算", "渠道"]
        missing_cols = [
            c for c in required_cols if c not in data.columns
        ]

        if missing_cols:
            st.error(
                "Google 表格缺少必要列："
                + ", ".join(missing_cols)
            )
            st.stop()

        data["原始日期"] = data["日期"]
        data["原始收入"] = data["收入"]

        data["日期"] = pd.to_datetime(
            data["日期"], errors="coerce"
        )

        data["收入"] = pd.to_numeric(
            data["收入"], errors="coerce"
        )

        invalid_dates = data[
            data["日期"].isna()
            & data["原始日期"].notna()
        ]

        if not invalid_dates.empty:
            st.warning(
                f"⚠️ 检测到 {len(invalid_dates)} 行日期格式错误，"
                "这些数据已被忽略。"
            )
            st.dataframe(
                invalid_dates[
                    ["原始日期", "原始收入", "预算", "渠道"]
                ],
                use_container_width=True
            )

        invalid_incomes = data[
            data["收入"].isna()
            & data["原始收入"].notna()
        ]

        if not invalid_incomes.empty:
            st.warning(
                f"⚠️ 检测到 {len(invalid_incomes)} 行收入格式错误，"
                "这些收入暂按 0 处理。"
            )
            st.dataframe(
                invalid_incomes[
                    ["原始日期", "原始收入", "预算", "渠道"]
                ],
                use_container_width=True
            )

        data["收入"] = data["收入"].fillna(0)

        data["预算"] = (
            data["预算"].fillna("未填写")
            .astype(str).str.strip()
        )

        data["渠道"] = (
            data["渠道"].fillna("未填写")
            .astype(str).str.strip()
        )

        data = data.dropna(subset=["日期"]).copy()

        data["日期"] = data["日期"].dt.normalize()

        data["周开始"] = (
            data["日期"]
            - pd.to_timedelta(
                data["日期"].dt.weekday,
                unit="D"
            )
        )

        data["周结束"] = (
            data["周开始"] + pd.Timedelta(days=6)
        )

        data = data.drop(
            columns=["原始日期", "原始收入"]
        )

        if data.empty:
            st.error("当前表格没有可用数据。")
            st.stop()

        return data

    df = load_data()

    st.info(
        "当前使用 Google 表格中的最新数据"
        "（自动刷新 + 可手动刷新）"
    )

    # =========================
    # 日期及维度
    # =========================
    all_dates = sorted(
        pd.Timestamp(x).normalize()
        for x in df["日期"].unique()
    )

    latest_date = all_dates[-1]

    all_weeks = sorted(
        pd.Timestamp(x).normalize()
        for x in df["周开始"].unique()
    )

    all_budgets = sorted(df["预算"].unique().tolist())
    all_channels = sorted(df["渠道"].unique().tolist())

    # =========================
    # 侧边栏
    # =========================
    st.sidebar.header("分析设置")

    analysis_granularity = st.sidebar.radio(
        "选择时间维度：",
        ["按日分析", "按周分析"]
    )

    view_mode = st.sidebar.radio(
        "选择分析维度：",
        ["总收益", "预算维度", "渠道维度"]
    )

    selected_budgets = []
    selected_channels = []

    if view_mode == "预算维度":
        selected_budgets = st.sidebar.multiselect(
            "选择要查看的预算：",
            all_budgets,
            default=all_budgets[:3]
        )

    elif view_mode == "渠道维度":
        selected_channels = st.sidebar.multiselect(
            "选择要查看的渠道：",
            all_channels,
            default=all_channels[:5]
        )

    st.sidebar.markdown("---")
    st.sidebar.subheader("🚨 预警设置")

    drop_threshold_pct = st.sidebar.slider(
        "收益下滑预警阈值 (%)",
        min_value=5,
        max_value=80,
        value=20,
        step=5
    )

    drop_threshold = drop_threshold_pct / 100

    # =========================
    # 通用函数
    # =========================
    def get_latest_available_before(target_date):
        dates = [
            d for d in all_dates
            if d < target_date
        ]
        return dates[-1] if dates else None

    def get_week_compare_date(target_date):
        exact_date = target_date - timedelta(days=7)

        if exact_date in all_dates:
            return exact_date

        dates = [
            d for d in all_dates
            if d < exact_date
        ]

        return dates[-1] if dates else None

    def get_previous_week(week_start):
        previous = week_start - pd.Timedelta(days=7)

        if previous in all_weeks:
            return previous

        dates = [
            w for w in all_weeks
            if w < week_start
        ]

        return dates[-1] if dates else None

    def get_sum_by_date(target_date, dim=None):
        if target_date is None:
            if dim:
                return pd.DataFrame(
                    columns=[dim, "收入"]
                )
            return 0.0

        day_df = df[df["日期"] == target_date]

        if dim:
            return (
                day_df.groupby(dim, as_index=False)["收入"]
                .sum()
            )

        return day_df["收入"].sum()

    def get_sum_by_week(week_start, dim=None):
        if week_start is None:
            if dim:
                return pd.DataFrame(
                    columns=[dim, "收入"]
                )
            return 0.0

        week_df = df[df["周开始"] == week_start]

        if dim:
            return (
                week_df.groupby(dim, as_index=False)["收入"]
                .sum()
            )

        return week_df["收入"].sum()

    def get_daily_comp(
        selected_date, prev_date, lw_date, dim=None
    ):
        if dim:
            current = get_sum_by_date(
                selected_date, dim
            ).rename(columns={"收入": "今日"})

            previous = get_sum_by_date(
                prev_date, dim
            ).rename(columns={"收入": "前一日"})

            lastweek = get_sum_by_date(
                lw_date, dim
            ).rename(columns={"收入": "上周同日"})

            result = (
                current
                .merge(previous, on=dim, how="outer")
                .merge(lastweek, on=dim, how="outer")
                .fillna(0)
            )

        else:
            result = pd.DataFrame([{
                "维度": "总计",
                "今日": get_sum_by_date(selected_date),
                "前一日": get_sum_by_date(prev_date),
                "上周同日": get_sum_by_date(lw_date)
            }])

        result["DoD涨跌"] = (
            result["今日"] - result["前一日"]
        )

        result["WoW涨跌"] = (
            result["今日"] - result["上周同日"]
        )

        return result

    def get_weekly_comp(
        selected_week, prev_week, dim=None
    ):
        if dim:
            current = get_sum_by_week(
                selected_week, dim
            ).rename(columns={"收入": "本周"})

            previous = get_sum_by_week(
                prev_week, dim
            ).rename(columns={"收入": "上周"})

            result = current.merge(
                previous,
                on=dim,
                how="outer"
            ).fillna(0)

        else:
            result = pd.DataFrame([{
                "维度": "总计",
                "本周": get_sum_by_week(selected_week),
                "上周": get_sum_by_week(prev_week)
            }])

        result["WoW涨跌"] = (
            result["本周"] - result["上周"]
        )

        return result

    # =========================
    # 占比分析
    # =========================
    def build_share_compare(
        current_data,
        previous_data,
        dim_name,
        current_label,
        previous_label
    ):
        current = (
            current_data.groupby(
                dim_name, as_index=False
            )["收入"].sum()
            .rename(columns={"收入": current_label})
        )

        previous = (
            previous_data.groupby(
                dim_name, as_index=False
            )["收入"].sum()
            .rename(columns={"收入": previous_label})
        )

        merged = current.merge(
            previous,
            on=dim_name,
            how="outer"
        ).fillna(0)

        current_total = merged[current_label].sum()
        previous_total = merged[previous_label].sum()

        merged["当前占比"] = (
            merged[current_label] / current_total
            if current_total > 0 else 0
        )

        merged["对比占比"] = (
            merged[previous_label] / previous_total
            if previous_total > 0 else 0
        )

        merged["占比变化"] = (
            merged["当前占比"] - merged["对比占比"]
        )

        merged = merged.sort_values(
            current_label, ascending=False
        )

        return merged

    def render_share_pie(
        current_data,
        previous_data,
        dim_name,
        title,
        current_label,
        previous_label
    ):
        result = build_share_compare(
            current_data,
            previous_data,
            dim_name,
            current_label,
            previous_label
        )

        if result.empty:
            st.info("暂无占比数据")
            return

        c1, c2 = st.columns([1.2, 1])

        with c1:
            pie_data = result[
                result[current_label] > 0
            ]

            if not pie_data.empty:
                fig = px.pie(
                    pie_data,
                    names=dim_name,
                    values=current_label,
                    hole=0.45,
                    title=title
                )

                fig.update_traces(
                    textposition="inside",
                    textinfo="percent+label"
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True
                )

        with c2:
            show = result.copy()

            show["当前占比"] = show[
                "当前占比"
            ].map(lambda x: f"{x:.2%}")

            show["对比占比"] = show[
                "对比占比"
            ].map(lambda x: f"{x:.2%}")

            show["占比变化"] = show[
                "占比变化"
            ].map(lambda x: f"{x:+.2%}")

            st.dataframe(
                show,
                use_container_width=True,
                hide_index=True
            )

    # =================================================
    # 新增模块：渠道收益下滑归因
    # =================================================
    def get_budget_attribution(
        current_data,
        comparison_data,
        current_label,
        comparison_label
    ):
        current = (
            current_data.groupby(
                "预算", as_index=False
            )["收入"].sum()
            .rename(columns={"收入": current_label})
        )

        comparison = (
            comparison_data.groupby(
                "预算", as_index=False
            )["收入"].sum()
            .rename(columns={"收入": comparison_label})
        )

        result = current.merge(
            comparison,
            on="预算",
            how="outer"
        ).fillna(0)

        result["涨跌金额"] = (
            result[current_label]
            - result[comparison_label]
        )

        result["涨跌比例"] = result.apply(
            lambda row: (
                row["涨跌金额"]
                / row[comparison_label]
                if row[comparison_label] > 0
                else None
            ),
            axis=1
        )

        result["变化状态"] = result[
            "涨跌金额"
        ].apply(
            lambda x: (
                "下降" if x < -0.000001
                else "增长" if x > 0.000001
                else "持平"
            )
        )

        result = result.sort_values(
            "涨跌金额",
            ascending=True
        ).reset_index(drop=True)

        return result

    def render_attribution_table(
        result,
        current_label,
        comparison_label,
        chart_title
    ):
        if result.empty:
            st.info("当前渠道暂无预算明细。")
            return

        current_total = result[current_label].sum()
        previous_total = result[comparison_label].sum()

        net_change = current_total - previous_total

        declines = result[
            result["涨跌金额"] < 0
        ]

        increases = result[
            result["涨跌金额"] > 0
        ]

        total_decline = -declines["涨跌金额"].sum()
        total_increase = increases["涨跌金额"].sum()

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            current_label,
            f"${current_total:,.2f}"
        )

        c2.metric(
            comparison_label,
            f"${previous_total:,.2f}"
        )

        c3.metric(
            "净收益变化",
            f"${net_change:,.2f}",
            delta=f"${net_change:,.2f}"
        )

        c4.metric(
            "下降预算数量",
            f"{len(declines)} 个"
        )

        st.caption(
            f"下降预算合计减少 ${total_decline:,.2f}；"
            f"增长预算合计增加 ${total_increase:,.2f}；"
            f"最终净变化 ${net_change:,.2f}。"
        )

        if not declines.empty:
            biggest = declines.iloc[0]

            st.error(
                f"📉 下降最多的预算："
                f"**{biggest['预算']}**，"
                f"减少 **${abs(biggest['涨跌金额']):,.2f}**。"
            )
        else:
            st.success(
                "当前没有预算出现收益下降。"
            )

        only_declines = st.checkbox(
            "只看收益下降的预算",
            value=False,
            key=f"only_declines_{chart_title}"
        )

        display = (
            declines.copy()
            if only_declines
            else result.copy()
        )

        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            column_config={
                current_label: st.column_config.NumberColumn(
                    current_label,
                    format="$%.2f"
                ),
                comparison_label: st.column_config.NumberColumn(
                    comparison_label,
                    format="$%.2f"
                ),
                "涨跌金额": st.column_config.NumberColumn(
                    "涨跌金额",
                    format="$%.2f"
                ),
                "涨跌比例": st.column_config.NumberColumn(
                    "涨跌比例",
                    format="%.2f"
                )
            }
        )

        st.caption(
            "涨跌比例为小数形式："
            "-0.20 代表下降 20%；"
            "上期收入为 0 时不计算比例。"
        )

        if not display.empty:
            fig = px.bar(
                display,
                x="预算",
                y="涨跌金额",
                color="变化状态",
                color_discrete_map={
                    "下降": "#e74c3c",
                    "增长": "#2ecc71",
                    "持平": "#95a5a6"
                },
                title=chart_title,
                text="涨跌金额"
            )

            fig.update_traces(
                texttemplate="%{text:,.2f}",
                textposition="outside"
            )

            fig.update_layout(
                height=420,
                xaxis_title="预算",
                yaxis_title="收益变化（USD）"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        csv_data = result.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "📥 下载预算涨跌明细 CSV",
            data=csv_data,
            file_name="渠道预算收益涨跌明细.csv",
            mime="text/csv",
            key=f"download_{chart_title}"
        )

    def render_channel_attribution(
        selected_day=None,
        selected_week=None
    ):
        st.markdown("---")
        st.subheader("🔍 渠道收益下滑归因分析")

        st.write(
            "选择一个渠道，查看具体哪个预算造成"
            "收益下降，以及下降金额和比例。"
        )

        default_channel = (
            all_channels.index("storyreel")
            if "storyreel" in all_channels
            else 0
        )

        channel = st.selectbox(
            "选择需要排查的渠道",
            all_channels,
            index=default_channel,
            key="attribution_channel"
        )

        channel_df = df[
            df["渠道"] == channel
        ].copy()

        if selected_day is not None:
            compare_mode = st.radio(
                "选择对比方式",
                ["今日 vs 昨日", "今日 vs 上周同日"],
                horizontal=True,
                key="attribution_daily_mode"
            )

            if compare_mode == "今日 vs 昨日":
                comparison_day = (
                    selected_day - pd.Timedelta(days=1)
                )
            else:
                comparison_day = (
                    selected_day - pd.Timedelta(days=7)
                )

            current_data = channel_df[
                channel_df["日期"] == selected_day
            ]

            comparison_data = channel_df[
                channel_df["日期"] == comparison_day
            ]

            if comparison_day not in all_dates:
                st.warning(
                    f"对比日期 "
                    f"{comparison_day.strftime('%Y-%m-%d')} "
                    "没有数据，暂不进行比较。"
                )
                return

            st.caption(
                f"当前日期：{selected_day:%Y-%m-%d} ｜ "
                f"对比日期：{comparison_day:%Y-%m-%d}"
            )

            result = get_budget_attribution(
                current_data,
                comparison_data,
                "当日收益",
                "对比日收益"
            )

            render_attribution_table(
                result,
                "当日收益",
                "对比日收益",
                f"{channel} 各预算日收益涨跌"
            )

        elif selected_week is not None:
            week_end = selected_week + pd.Timedelta(
                days=6
            )

            available_dates = channel_df[
                (channel_df["日期"] >= selected_week)
                & (channel_df["日期"] <= week_end)
            ]["日期"]

            if available_dates.empty:
                st.info("该渠道在选定周暂无数据。")
                return

            actual_end = available_dates.max()

            previous_start = (
                selected_week - pd.Timedelta(days=7)
            )

            previous_end = (
                actual_end - pd.Timedelta(days=7)
            )

            current_data = channel_df[
                (channel_df["日期"] >= selected_week)
                & (channel_df["日期"] <= actual_end)
            ]

            comparison_data = channel_df[
                (channel_df["日期"] >= previous_start)
                & (channel_df["日期"] <= previous_end)
            ]

            # 核查两个时间段的全局数据日期，
            # 避免上周没有数据时误判为增长。
            expected_previous_dates = [
                selected_week
                + pd.Timedelta(days=i)
                - pd.Timedelta(days=7)
                for i in range(
                    (actual_end - selected_week).days + 1
                )
            ]

            missing_previous_dates = [
                d for d in expected_previous_dates
                if d not in all_dates
            ]

            if missing_previous_dates:
                st.warning(
                    "上周同期缺少部分日期的数据，"
                    "暂不计算周度归因。缺失日期："
                    + ", ".join(
                        d.strftime("%m-%d")
                        for d in missing_previous_dates
                    )
                )
                return

            st.caption(
                f"本周：{selected_week:%Y-%m-%d}"
                f" ~ {actual_end:%Y-%m-%d} ｜ "
                f"上周同期：{previous_start:%Y-%m-%d}"
                f" ~ {previous_end:%Y-%m-%d}"
            )

            result = get_budget_attribution(
                current_data,
                comparison_data,
                "本周同期收益",
                "上周同期收益"
            )

            render_attribution_table(
                result,
                "本周同期收益",
                "上周同期收益",
                f"{channel} 各预算周收益涨跌"
            )

    # =========================
    # 按日分析
    # =========================
    if analysis_granularity == "按日分析":

        selected_date = st.sidebar.selectbox(
            "选择查看日期：",
            all_dates,
            index=len(all_dates) - 1,
            format_func=lambda x: x.strftime("%Y-%m-%d")
        )

        prev_date = get_latest_available_before(
            selected_date
        )

        lw_date = get_week_compare_date(
            selected_date
        )

        total_row = get_daily_comp(
            selected_date,
            prev_date,
            lw_date
        )

        st.subheader(
            f"📍 实时概览（按日）"
            f" {selected_date:%Y-%m-%d}"
        )

        prev_label = (
            prev_date.strftime("%Y-%m-%d")
            if prev_date is not None
            else "无可用日期"
        )

        lw_label = (
            lw_date.strftime("%Y-%m-%d")
            if lw_date is not None
            else "无可用日期"
        )

        m1, m2, m3 = st.columns(3)

        m1.metric(
            "当日总收益",
            f"${total_row['今日'].iloc[0]:,.2f}"
        )

        m2.metric(
            f"前一日收益（{prev_label}）",
            f"${total_row['前一日'].iloc[0]:,.2f}",
            delta=(
                f"{total_row['DoD涨跌'].iloc[0]:,.2f}"
            )
        )

        m3.metric(
            f"上周同日收益（{lw_label}）",
            f"${total_row['上周同日'].iloc[0]:,.2f}",
            delta=(
                f"{total_row['WoW涨跌'].iloc[0]:,.2f}"
            )
        )

        today_rev = total_row["今日"].iloc[0]
        prev_rev = total_row["前一日"].iloc[0]

        if prev_rev > 0:
            drop_pct = (
                prev_rev - today_rev
            ) / prev_rev

            if drop_pct >= drop_threshold:
                st.error(
                    f"🚨 总收益较前一日下降 "
                    f"{drop_pct:.1%}，"
                    f"超过 {drop_threshold_pct}% 预警线。"
                )

        # 新增：渠道预算下滑归因
        render_channel_attribution(
            selected_day=selected_date
        )

        st.markdown("---")
        st.subheader(
            f"📈 {view_mode} 趋势追踪（按日）"
        )

        if view_mode == "总收益":
            plot_df = df.groupby(
                "日期", as_index=False
            )["收入"].sum()

            fig = px.line(
                plot_df,
                x="日期",
                y="收入",
                title="总收益日趋势",
                markers=True,
                height=500
            )

        elif view_mode == "预算维度":
            if not selected_budgets:
                st.info("请在左侧选择预算。")
                st.stop()

            plot_df = (
                df[df["预算"].isin(selected_budgets)]
                .groupby(
                    ["日期", "预算"],
                    as_index=False
                )["收入"].sum()
            )

            fig = px.line(
                plot_df,
                x="日期",
                y="收入",
                color="预算",
                title="预算日收益趋势",
                markers=True,
                height=600
            )

        else:
            if not selected_channels:
                st.info("请在左侧选择渠道。")
                st.stop()

            plot_df = (
                df[df["渠道"].isin(selected_channels)]
                .groupby(
                    ["日期", "渠道"],
                    as_index=False
                )["收入"].sum()
            )

            fig = px.line(
                plot_df,
                x="日期",
                y="收入",
                color="渠道",
                title="渠道日收益趋势",
                markers=True,
                height=600
            )

        fig.add_vline(
            x=selected_date,
            line_dash="dash",
            line_color="red"
        )

        fig.update_layout(
            hovermode="x unified"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        st.markdown("---")
        st.subheader(
            "🥧 预算 / 渠道占比对比（按日）"
        )

        current_day_df = df[
            df["日期"] == selected_date
        ]

        previous_day_df = df[
            df["日期"] == lw_date
        ] if lw_date is not None else df.iloc[0:0]

        pie_tab1, pie_tab2 = st.tabs([
            "🍱 预算占比图",
            "🚀 渠道占比图"
        ])

        with pie_tab1:
            render_share_pie(
                current_day_df,
                previous_day_df,
                "预算",
                "当日预算占比图",
                "今日收入",
                "上周同日收入"
            )

        with pie_tab2:
            render_share_pie(
                current_day_df,
                previous_day_df,
                "渠道",
                "当日渠道占比图",
                "今日收入",
                "上周同日收入"
            )

        st.markdown("---")

        detail_tab1, detail_tab2 = st.tabs([
            "🍱 预算明细对比",
            "🚀 渠道明细对比"
        ])

        with detail_tab1:
            st.dataframe(
                get_daily_comp(
                    selected_date,
                    prev_date,
                    lw_date,
                    "预算"
                ),
                use_container_width=True,
                hide_index=True
            )

        with detail_tab2:
            st.dataframe(
                get_daily_comp(
                    selected_date,
                    prev_date,
                    lw_date,
                    "渠道"
                ),
                use_container_width=True,
                hide_index=True
            )

    # =========================
    # 按周分析
    # =========================
    else:
        selected_week = st.sidebar.selectbox(
            "选择查看周（周一）：",
            all_weeks,
            index=len(all_weeks) - 1,
            format_func=lambda x: (
                f"{x:%Y-%m-%d} ~ "
                f"{x + pd.Timedelta(days=6):%Y-%m-%d}"
            )
        )

        selected_week_end = (
            selected_week + pd.Timedelta(days=6)
        )

        prev_week = get_previous_week(
            selected_week
        )

        prev_week_label = (
            f"{prev_week:%Y-%m-%d} ~ "
            f"{prev_week + pd.Timedelta(days=6):%Y-%m-%d}"
            if prev_week is not None
            else "无可用上周"
        )

        weekly_total = get_weekly_comp(
            selected_week,
            prev_week
        )

        st.subheader(
            f"📅 周度概览（按周）"
            f" {selected_week:%Y-%m-%d}"
            f" ~ {selected_week_end:%Y-%m-%d}"
        )

        m1, m2 = st.columns(2)

        m1.metric(
            "本周总收益",
            f"${weekly_total['本周'].iloc[0]:,.2f}"
        )

        m2.metric(
            f"上周收益（{prev_week_label}）",
            f"${weekly_total['上周'].iloc[0]:,.2f}",
            delta=(
                f"{weekly_total['WoW涨跌'].iloc[0]:,.2f}"
            )
        )

        this_week_rev = weekly_total[
            "本周"
        ].iloc[0]

        last_week_rev = weekly_total[
            "上周"
        ].iloc[0]

        if last_week_rev > 0:
            drop_pct = (
                last_week_rev - this_week_rev
            ) / last_week_rev

            if drop_pct >= drop_threshold:
                st.error(
                    f"🚨 周收益较上周下降 "
                    f"{drop_pct:.1%}，"
                    f"超过 {drop_threshold_pct}% 预警线。"
                )

        # 新增：渠道预算周度下滑归因
        render_channel_attribution(
            selected_week=selected_week
        )

        st.markdown("---")
        st.subheader(
            f"📈 {view_mode} 趋势追踪（按周）"
        )

        if view_mode == "总收益":
            plot_df = df.groupby(
                "周开始", as_index=False
            )["收入"].sum()

            fig = px.line(
                plot_df,
                x="周开始",
                y="收入",
                title="总收益周趋势",
                markers=True,
                height=500
            )

        elif view_mode == "预算维度":
            if not selected_budgets:
                st.info("请在左侧选择预算。")
                st.stop()

            plot_df = (
                df[df["预算"].isin(selected_budgets)]
                .groupby(
                    ["周开始", "预算"],
                    as_index=False
                )["收入"].sum()
            )

            fig = px.line(
                plot_df,
                x="周开始",
                y="收入",
                color="预算",
                title="预算周收益趋势",
                markers=True,
                height=600
            )

        else:
            if not selected_channels:
                st.info("请在左侧选择渠道。")
                st.stop()

            plot_df = (
                df[df["渠道"].isin(selected_channels)]
                .groupby(
                    ["周开始", "渠道"],
                    as_index=False
                )["收入"].sum()
            )

            fig = px.line(
                plot_df,
                x="周开始",
                y="收入",
                color="渠道",
                title="渠道周收益趋势",
                markers=True,
                height=600
            )

        fig.add_vline(
            x=selected_week,
            line_dash="dash",
            line_color="red"
        )

        fig.update_layout(
            hovermode="x unified"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        st.markdown("---")
        st.subheader(
            "🥧 预算 / 渠道占比对比（按周）"
        )

        current_week_df = df[
            df["周开始"] == selected_week
        ]

        previous_week_df = (
            df[df["周开始"] == prev_week]
            if prev_week is not None
            else df.iloc[0:0]
        )

        pie_tab1, pie_tab2 = st.tabs([
            "🍱 预算周占比图",
            "🚀 渠道周占比图"
        ])

        with pie_tab1:
            render_share_pie(
                current_week_df,
                previous_week_df,
                "预算",
                "本周预算占比图",
                "本周收入",
                "上周收入"
            )

        with pie_tab2:
            render_share_pie(
                current_week_df,
                previous_week_df,
                "渠道",
                "本周渠道占比图",
                "本周收入",
                "上周收入"
            )

        st.markdown("---")

        detail_tab1, detail_tab2 = st.tabs([
            "🍱 预算周明细对比",
            "🚀 渠道周明细对比"
        ])

        with detail_tab1:
            st.dataframe(
                get_weekly_comp(
                    selected_week,
                    prev_week,
                    "预算"
                ),
                use_container_width=True,
                hide_index=True
            )

        with detail_tab2:
            st.dataframe(
                get_weekly_comp(
                    selected_week,
                    prev_week,
                    "渠道"
                ),
                use_container_width=True,
                hide_index=True
            )

else:
    st.warning("👈 请在左侧输入密码解锁看板")
