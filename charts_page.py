"""
charts_page.py — render 3 charts trong tab Charts của app.
Gọi từ app.py: from charts_page import render_charts
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from chart_engine import ChartEngine
from sheets_manager import SheetsManager

# Màu theo tài khoản (tự động gán)
ACCOUNT_COLORS = [
    "#2e75b6", "#ed7d31", "#a9d18e", "#ffc000",
    "#5b9bd5", "#70ad47", "#ff6b6b", "#845ec2",
]


def render_charts(sm: SheetsManager, selected_account: str, accounts: list):
    engine = ChartEngine(sm)
    years  = engine.get_available_years()

    # ── Bộ lọc năm ───────────────────────────────────────────────────────────
    col_yr, col_spacer = st.columns([1, 3])
    with col_yr:
        selected_year = st.selectbox("📅 Năm", years, index=0, key="chart_year")

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════
    # CHART 1 — Hành trình đầu tư
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("### 📈 Chart 1 — Hành trình đầu tư")
    st.caption("Cột 1: Số tiền đầu tư | Cột 2: Giá trị thị trường (chồng thêm lợi nhuận đã ghi nhận)")

    with st.spinner("Đang tính dữ liệu Chart 1..."):
        c1_df = engine.get_chart1_data(selected_account, selected_year)

    if c1_df.empty or c1_df["invested"].sum() == 0:
        st.info("Chưa có dữ liệu giao dịch cho năm này.")
    else:
        fig1 = _build_chart1(c1_df)
        st.plotly_chart(fig1, use_container_width=True)

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════
    # CHART 2 — Lợi nhuận ghi nhận hàng tháng
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("### 💰 Chart 2 — Lợi nhuận ghi nhận hàng tháng")
    st.caption("Cột chồng theo tài khoản | Line = lợi nhuận cộng dồn từng tài khoản")

    with st.spinner("Đang tính dữ liệu Chart 2..."):
        c2_df = engine.get_chart2_data(selected_year)

    if c2_df.empty or c2_df["monthly_pnl"].abs().sum() == 0:
        st.info("Chưa có lợi nhuận ghi nhận trong năm này.")
    else:
        fig2 = _build_chart2(c2_df, accounts)
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════
    # CHART 3 — Tiền mặt
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("### 🏦 Chart 3 — Tiền mặt hiện tại theo tài khoản")
    st.caption("Giá trị tiền mặt và % so với tổng tài sản")

    with st.spinner("Đang tính dữ liệu Chart 3..."):
        c3_df = engine.get_chart3_data()

    if c3_df.empty:
        st.info("Chưa có dữ liệu tài khoản.")
    else:
        _render_chart3_metrics(c3_df)
        fig3 = _build_chart3(c3_df)
        st.plotly_chart(fig3, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# Build functions
# ─────────────────────────────────────────────────────────────────────────────

def _build_chart1(df: pd.DataFrame) -> go.Figure:
    """
    Bar kép:
      Bar 1 (xanh đậm): Số tiền đầu tư
      Bar 2 (xanh nhạt): Giá trị thị trường
      Bar 2 chồng thêm lớp cam: Lợi nhuận đã ghi nhận
    Line: Lợi nhuận cộng dồn
    """
    months      = df["month"].tolist()
    month_labels = [m[5:] + "/" + m[:4] for m in months]  # "01/2024"

    # Phần market_value = base (không tính realized) + realized
    market_base = (df["market_value"] - df["realized_pnl"]).clip(lower=0)

    fig = make_subplots(specs=[[{"secondary_y": False}]])

    # Bar 1: Tiền đầu tư
    fig.add_trace(go.Bar(
        x=month_labels, y=df["invested"],
        name="Tiền đầu tư",
        marker_color="#2e75b6",
        offsetgroup=0,
        width=0.35,
    ))

    # Bar 2a: Giá trị TT (phần base)
    fig.add_trace(go.Bar(
        x=month_labels, y=market_base,
        name="Giá trị thị trường",
        marker_color="#9dc3e6",
        offsetgroup=1,
        width=0.35,
    ))

    # Bar 2b: Lợi nhuận ghi nhận (chồng lên bar 2)
    fig.add_trace(go.Bar(
        x=month_labels, y=df["realized_pnl"].clip(lower=0),
        name="Lợi nhuận đã ghi nhận",
        marker_color="#ed7d31",
        offsetgroup=1,
        base=market_base,
        width=0.35,
    ))

    # Line: lợi nhuận cộng dồn
    fig.add_trace(go.Scatter(
        x=month_labels, y=df["realized_pnl"],
        name="LN cộng dồn (line)",
        mode="lines+markers",
        line=dict(color="#ed7d31", width=2, dash="dot"),
        marker=dict(size=6),
        yaxis="y",
    ))

    fig.update_layout(
        barmode="overlay",
        bargroupgap=0.1,
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=20, r=20, t=60, b=20),
        yaxis=dict(tickformat=",.0f", title="VNĐ"),
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#e8e8e8")
    return fig


def _build_chart2(df: pd.DataFrame, accounts: list) -> go.Figure:
    """Stacked bar theo tài khoản + line cộng dồn từng tài khoản."""
    acc_names   = df["account"].unique().tolist()
    all_months  = sorted(df["month"].unique().tolist())
    month_labels = [m[5:] + "/" + m[:4] for m in all_months]

    fig = go.Figure()
    color_map = {acc: ACCOUNT_COLORS[i % len(ACCOUNT_COLORS)]
                 for i, acc in enumerate(acc_names)}

    # Stacked bars
    for acc in acc_names:
        sub = df[df["account"] == acc].set_index("month").reindex(all_months, fill_value=0)
        fig.add_trace(go.Bar(
            x=month_labels,
            y=sub["monthly_pnl"].values,
            name=acc,
            marker_color=color_map[acc],
            opacity=0.85,
        ))

    # Cumulative lines
    for acc in acc_names:
        sub = df[df["account"] == acc].set_index("month").reindex(all_months, fill_value=0)
        fig.add_trace(go.Scatter(
            x=month_labels,
            y=sub["cumulative"].values,
            name=f"{acc} (cộng dồn)",
            mode="lines+markers",
            line=dict(color=color_map[acc], width=2),
            marker=dict(size=5, symbol="circle"),
            opacity=0.9,
        ))

    fig.update_layout(
        barmode="relative",   # stacked, hỗ trợ âm
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=20, r=20, t=60, b=20),
        yaxis=dict(tickformat=",.0f", title="VNĐ"),
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#e8e8e8", zeroline=True, zerolinecolor="#aaa")
    return fig


def _render_chart3_metrics(df: pd.DataFrame):
    """Hiển thị metric cards cho từng tài khoản."""
    cols = st.columns(len(df))
    for i, (_, row) in enumerate(df.iterrows()):
        with cols[i]:
            pct = row["cash_pct"]
            color = "🟢" if pct >= 20 else ("🟡" if pct >= 10 else "🔴")
            st.metric(
                label=f"{color} {row['account']}",
                value=f"{row['cash']:,.0f} đ",
                delta=f"{pct:.1f}% tiền mặt",
                delta_color="off",
            )


def _build_chart3(df: pd.DataFrame) -> go.Figure:
    """Grouped bar: tiền mặt vs giá trị CK + line % tiền mặt."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    accounts = df["account"].tolist()

    # Bar: tiền mặt
    fig.add_trace(go.Bar(
        x=accounts, y=df["cash"],
        name="Tiền mặt",
        marker_color="#2e75b6",
        offsetgroup=0, width=0.3,
    ), secondary_y=False)

    # Bar: giá trị CK
    fig.add_trace(go.Bar(
        x=accounts, y=df["market_value"],
        name="Giá trị CK",
        marker_color="#9dc3e6",
        offsetgroup=1, width=0.3,
    ), secondary_y=False)

    # Line: % tiền mặt (trục phụ)
    fig.add_trace(go.Scatter(
        x=accounts, y=df["cash_pct"],
        name="% Tiền mặt",
        mode="lines+markers+text",
        text=[f"{v:.1f}%" for v in df["cash_pct"]],
        textposition="top center",
        line=dict(color="#ed7d31", width=2),
        marker=dict(size=8),
    ), secondary_y=True)

    fig.update_layout(
        barmode="group",
        bargroupgap=0.2,
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=20, r=20, t=60, b=20),
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_yaxes(title_text="VNĐ",  tickformat=",.0f",  showgrid=True,
                     gridcolor="#e8e8e8", secondary_y=False)
    fig.update_yaxes(title_text="% Tiền mặt", ticksuffix="%",
                     showgrid=False, secondary_y=True,
                     range=[0, max(100, df["cash_pct"].max() * 1.3)])
    fig.update_xaxes(showgrid=False)
    return fig
