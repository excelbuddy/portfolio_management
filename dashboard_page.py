"""
dashboard_page.py — Bloomberg/trading terminal style dashboard
Sections: KPI bar, Portfolio top, Mini journey chart, Recent transactions
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import date, datetime
from chart_engine import ChartEngine
from sheets_manager import SheetsManager
from portfolio_logic import PortfolioLogic

# ── Bloomberg color palette ───────────────────────────────────────────────────
BG_CARD     = "#0d1117"
BG_PANEL    = "#161b22"
BG_ROW_ALT  = "#1c2128"
BORDER      = "#30363d"
TEXT_MAIN   = "#e6edf3"
TEXT_DIM    = "#8b949e"
GREEN       = "#3fb950"
RED         = "#f85149"
ORANGE      = "#d29922"
BLUE        = "#58a6ff"
PURPLE      = "#bc8cff"
YELLOW      = "#e3b341"
TEAL        = "#39d353"

ACCOUNT_COLORS = [BLUE, ORANGE, GREEN, PURPLE, YELLOW, TEAL, RED]

CSS = f"""
<style>
/* ── global dark bg ── */
.stApp, [data-testid="stAppViewContainer"] {{
    background-color: {BG_CARD} !important;
}}
[data-testid="stSidebar"] {{
    background-color: #0d1117 !important;
    border-right: 1px solid {BORDER};
}}
/* ── KPI cards ── */
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 10px;
    margin-bottom: 16px;
}}
.kpi-card {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 14px 16px;
    position: relative;
}}
.kpi-label {{
    font-size: 0.68rem;
    color: {TEXT_DIM};
    text-transform: uppercase;
    letter-spacing: .06em;
    margin-bottom: 6px;
}}
.kpi-value {{
    font-size: 1.35rem;
    font-weight: 700;
    color: {TEXT_MAIN};
    font-family: 'Roboto Mono', monospace;
    line-height: 1.1;
}}
.kpi-delta {{
    font-size: 0.75rem;
    font-weight: 600;
    margin-top: 4px;
}}
.kpi-delta.up   {{ color: {GREEN}; }}
.kpi-delta.down {{ color: {RED};   }}
.kpi-delta.flat {{ color: {TEXT_DIM}; }}
.kpi-accent {{ border-top: 3px solid; }}
.kpi-accent.blue   {{ border-color: {BLUE};   }}
.kpi-accent.green  {{ border-color: {GREEN};  }}
.kpi-accent.orange {{ border-color: {ORANGE}; }}
.kpi-accent.red    {{ border-color: {RED};    }}
.kpi-accent.purple {{ border-color: {PURPLE}; }}
/* ── section headers ── */
.section-hdr {{
    font-size: 0.72rem;
    font-weight: 700;
    color: {TEXT_DIM};
    text-transform: uppercase;
    letter-spacing: .1em;
    padding: 8px 0 6px 0;
    border-bottom: 1px solid {BORDER};
    margin-bottom: 10px;
}}
/* ── portfolio mini table ── */
.port-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
    font-family: 'Roboto Mono', monospace;
}}
.port-table th {{
    color: {TEXT_DIM};
    text-align: right;
    padding: 5px 8px;
    font-weight: 600;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: .05em;
    border-bottom: 1px solid {BORDER};
}}
.port-table th:first-child {{ text-align: left; }}
.port-table td {{
    padding: 7px 8px;
    color: {TEXT_MAIN};
    text-align: right;
    border-bottom: 1px solid {BG_ROW_ALT};
}}
.port-table td:first-child {{ text-align: left; font-weight: 700; color: {BLUE}; }}
.port-table tr:hover td {{ background: {BG_ROW_ALT}; }}
.up   {{ color: {GREEN} !important; }}
.down {{ color: {RED}   !important; }}
.flat {{ color: {TEXT_DIM} !important; }}
/* ── recent transactions ── */
.txn-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 6px;
    margin-bottom: 4px;
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    font-size: 0.8rem;
}}
.txn-badge {{
    font-size: 0.65rem;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 4px;
    min-width: 36px;
    text-align: center;
}}
.txn-buy  {{ background: rgba(63,185,80,.2);  color: {GREEN};  border: 1px solid {GREEN}; }}
.txn-sell {{ background: rgba(248,81,73,.2);  color: {RED};    border: 1px solid {RED};   }}
.txn-div  {{ background: rgba(88,166,255,.2); color: {BLUE};   border: 1px solid {BLUE};  }}
.txn-fee  {{ background: rgba(210,153,34,.2); color: {ORANGE}; border: 1px solid {ORANGE};}}
.txn-sym  {{ color: {TEXT_MAIN}; font-weight: 700; min-width: 44px; }}
.txn-amt  {{ color: {TEXT_MAIN}; font-family: 'Roboto Mono',monospace; margin-left: auto; }}
.txn-date {{ color: {TEXT_DIM}; font-size: 0.72rem; }}
/* ── account tabs ── */
.acc-pill {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.72rem;
    font-weight: 600;
    margin-right: 6px;
    border: 1px solid {BORDER};
    color: {TEXT_DIM};
}}
/* ── Streamlit overrides ── */
div[data-testid="metric-container"] {{ display: none; }}
.stTabs [data-baseweb="tab-list"]   {{ background: {BG_CARD} !important; gap: 4px; }}
.stTabs [data-baseweb="tab"]        {{ background: {BG_PANEL} !important; color: {TEXT_DIM} !important;
                                       border: 1px solid {BORDER} !important; border-radius: 6px !important; }}
.stTabs [aria-selected="true"]      {{ background: #1f3a5f !important; color: {BLUE} !important; }}
h1,h2,h3,h4 {{ color: {TEXT_MAIN} !important; }}
p, li        {{ color: {TEXT_MAIN} !important; }}
.stDataFrame {{ display: none; }}
</style>
"""


def render_dashboard(sm: SheetsManager, selected_account: str, accounts: list):
    st.markdown(CSS, unsafe_allow_html=True)

    logic  = PortfolioLogic(sm)
    engine = ChartEngine(sm)
    year   = date.today().year

    # ── Load data ─────────────────────────────────────────────────────────────
    portfolio = logic.get_portfolio(selected_account)
    summary   = logic.get_summary(selected_account)
    txn_df    = sm.get_transactions()

    # ── Header bar ────────────────────────────────────────────────────────────
    now_str = datetime.now().strftime("%d/%m/%Y  %H:%M")
    acc_label = selected_account if selected_account != "Tất cả" else "All Accounts"

    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;
                padding:10px 0 4px 0;border-bottom:1px solid {BORDER};margin-bottom:14px;">
      <div>
        <span style="font-size:1.3rem;font-weight:800;color:{TEXT_MAIN};">
          📈 STOCK TRACKER
        </span>
        <span style="font-size:0.8rem;color:{TEXT_DIM};margin-left:12px;">
          {acc_label}
        </span>
      </div>
      <div style="font-size:0.75rem;color:{TEXT_DIM};font-family:monospace;">
        🕐 {now_str}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── KPI CARDS ─────────────────────────────────────────────────────────────
    mv      = summary["market_value"]
    inv     = summary["total_invested"]
    upnl    = summary["unrealized_pnl"]
    upnl_p  = summary["unrealized_pnl_pct"]
    cash    = summary["cash"]
    total   = mv + cash

    # Realized PnL năm nay
    matches = sm.get_sell_matches(selected_account if selected_account != "Tất cả" else None)
    rpnl = 0.0
    if not matches.empty:
        matches["sell_date"] = pd.to_datetime(matches["sell_date"], errors="coerce")
        yr_matches = matches[matches["sell_date"].dt.year == year]
        rpnl = pd.to_numeric(yr_matches["realized_pnl"], errors="coerce").fillna(0).sum()

    cash_pct = (cash / total * 100) if total > 0 else 0

    def _fmt(v):
        if abs(v) >= 1e9:  return f"{v/1e9:.2f}B"
        if abs(v) >= 1e6:  return f"{v/1e6:.1f}M"
        return f"{v:,.0f}"

    def _delta_cls(v): return "up" if v > 0 else ("down" if v < 0 else "flat")
    def _arrow(v):     return "▲" if v > 0 else ("▼" if v < 0 else "—")

    st.markdown(f"""
    <div class="kpi-grid">
      <div class="kpi-card kpi-accent blue">
        <div class="kpi-label">Tổng tài sản</div>
        <div class="kpi-value">{_fmt(total)}</div>
        <div class="kpi-delta flat">VNĐ</div>
      </div>
      <div class="kpi-card kpi-accent green">
        <div class="kpi-label">Giá trị thị trường</div>
        <div class="kpi-value">{_fmt(mv)}</div>
        <div class="kpi-delta {_delta_cls(upnl)}">
          {_arrow(upnl)} {_fmt(abs(upnl))} ({upnl_p:+.1f}%)
        </div>
      </div>
      <div class="kpi-card kpi-accent {'green' if rpnl >= 0 else 'red'}">
        <div class="kpi-label">LN đã ghi nhận {year}</div>
        <div class="kpi-value" style="color:{'#3fb950' if rpnl>=0 else '#f85149'}">{_fmt(rpnl)}</div>
        <div class="kpi-delta {_delta_cls(rpnl)}">{_arrow(rpnl)} YTD</div>
      </div>
      <div class="kpi-card kpi-accent orange">
        <div class="kpi-label">Tiền mặt</div>
        <div class="kpi-value">{_fmt(cash)}</div>
        <div class="kpi-delta flat">{cash_pct:.1f}% tổng tài sản</div>
      </div>
      <div class="kpi-card kpi-accent purple">
        <div class="kpi-label">Tiền đã đầu tư</div>
        <div class="kpi-value">{_fmt(inv)}</div>
        <div class="kpi-delta flat">{len(portfolio)} mã CK</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── TWO COLUMN LAYOUT ─────────────────────────────────────────────────────
    left, right = st.columns([3, 2], gap="medium")

    # ── LEFT: Mini journey chart + Portfolio table ────────────────────────────
    with left:
        # Mini chart
        st.markdown(f'<div class="section-hdr">Hành trình đầu tư — {year}</div>',
                    unsafe_allow_html=True)
        with st.spinner(""):
            c1_df = engine.get_chart1_data(selected_account, year)
        if not c1_df.empty and c1_df["invested"].sum() > 0:
            fig_mini = _mini_journey_chart(c1_df)
            st.plotly_chart(fig_mini, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown(f'<p style="color:{TEXT_DIM};font-size:.8rem;padding:20px 0;">Chưa có dữ liệu</p>',
                        unsafe_allow_html=True)

        # Portfolio table
        st.markdown('<div class="section-hdr">Danh mục hiện tại</div>', unsafe_allow_html=True)
        if not portfolio.empty:
            st.markdown(_portfolio_table_html(portfolio), unsafe_allow_html=True)
        else:
            st.markdown(f'<p style="color:{TEXT_DIM};font-size:.8rem;">Chưa có cổ phiếu nào.</p>',
                        unsafe_allow_html=True)

    # ── RIGHT: Account breakdown + Recent transactions ────────────────────────
    with right:
        # Account breakdown bars
        if len(accounts) > 1:
            st.markdown('<div class="section-hdr">Tài sản theo tài khoản</div>',
                        unsafe_allow_html=True)
            fig_acc = _account_breakdown_chart(sm, accounts, logic)
            st.plotly_chart(fig_acc, use_container_width=True,
                            config={"displayModeBar": False})

        # Recent transactions
        st.markdown('<div class="section-hdr">Giao dịch gần đây</div>', unsafe_allow_html=True)
        if not txn_df.empty:
            filt = txn_df
            if selected_account != "Tất cả":
                filt = txn_df[txn_df["account"] == selected_account]
            filt = filt.copy()
            filt["date"] = pd.to_datetime(filt["date"], errors="coerce")
            filt = filt.sort_values("date", ascending=False).head(10)
            st.markdown(_recent_txn_html(filt), unsafe_allow_html=True)
        else:
            st.markdown(f'<p style="color:{TEXT_DIM};font-size:.8rem;">Chưa có giao dịch.</p>',
                        unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Chart builders
# ─────────────────────────────────────────────────────────────────────────────

def _mini_journey_chart(df: pd.DataFrame) -> go.Figure:
    month_labels = [m[5:] + "/" + m[2:4] for m in df["month"]]
    market_base  = (df["market_value"] - df["realized_pnl"]).clip(lower=0)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=month_labels, y=df["invested"],
        name="Đầu tư", marker_color=BLUE, opacity=0.8,
        offsetgroup=0, width=0.35,
    ))
    fig.add_trace(go.Bar(
        x=month_labels, y=market_base,
        name="Giá trị TT", marker_color="#1f4e79", opacity=0.9,
        offsetgroup=1, width=0.35,
    ))
    fig.add_trace(go.Bar(
        x=month_labels, y=df["realized_pnl"].clip(lower=0),
        name="LN ghi nhận", marker_color=GREEN, opacity=0.9,
        offsetgroup=1, base=market_base, width=0.35,
    ))
    fig.add_trace(go.Scatter(
        x=month_labels, y=df["realized_pnl"],
        name="LN cộng dồn", mode="lines+markers",
        line=dict(color=ORANGE, width=1.5, dash="dot"),
        marker=dict(size=4),
    ))
    fig.update_layout(
        barmode="overlay", height=220,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", y=1.15, x=0, font=dict(size=10, color=TEXT_DIM)),
        yaxis=dict(tickformat=".2s", color=TEXT_DIM, gridcolor=BORDER, showgrid=True),
        xaxis=dict(color=TEXT_DIM, showgrid=False),
        plot_bgcolor=BG_PANEL, paper_bgcolor=BG_PANEL,
        font=dict(color=TEXT_DIM, size=10),
        hovermode="x unified",
    )
    return fig


def _account_breakdown_chart(sm, accounts, logic) -> go.Figure:
    labels, mv_vals, cash_vals = [], [], []
    colors = ACCOUNT_COLORS

    for acc in accounts:
        acc_name = acc["name"]
        s = logic.get_summary(acc_name)
        labels.append(acc_name)
        mv_vals.append(s["market_value"])
        cash_vals.append(max(s["cash"], 0))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=mv_vals, name="CK",
        orientation="h", marker_color=BLUE, opacity=0.85,
    ))
    fig.add_trace(go.Bar(
        y=labels, x=cash_vals, name="Tiền mặt",
        orientation="h", marker_color=GREEN, opacity=0.7,
    ))
    fig.update_layout(
        barmode="stack", height=max(120, len(accounts) * 48),
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", y=1.15, x=0, font=dict(size=10, color=TEXT_DIM)),
        xaxis=dict(tickformat=".2s", color=TEXT_DIM, showgrid=True, gridcolor=BORDER),
        yaxis=dict(color=TEXT_DIM, showgrid=False),
        plot_bgcolor=BG_PANEL, paper_bgcolor=BG_PANEL,
        font=dict(color=TEXT_DIM, size=10),
        hovermode="y unified",
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# HTML builders
# ─────────────────────────────────────────────────────────────────────────────

def _portfolio_table_html(df: pd.DataFrame) -> str:
    rows_html = ""
    for _, r in df.iterrows():
        pnl      = float(r["unrealized_pnl"])
        pnl_pct  = float(r["unrealized_pnl_pct"])
        cls      = "up" if pnl > 0 else ("down" if pnl < 0 else "flat")
        arrow    = "▲" if pnl > 0 else ("▼" if pnl < 0 else "—")
        cur_price = float(r.get("current_price", 0))
        avg_price = float(r.get("avg_buy_price",  0))
        qty       = int(r["quantity"])
        mv        = float(r["market_value"])

        def _f(v): return f"{v:,.0f}" if abs(v) < 1e6 else f"{v/1e6:.2f}M"

        rows_html += f"""
        <tr>
          <td>{r['symbol']}</td>
          <td>{qty:,}</td>
          <td>{_f(avg_price)}</td>
          <td>{_f(cur_price)}</td>
          <td>{_f(mv)}</td>
          <td class="{cls}">{arrow} {_f(abs(pnl))}<br>
            <span style="font-size:.7rem">{pnl_pct:+.1f}%</span>
          </td>
        </tr>"""

    return f"""
    <table class="port-table">
      <thead>
        <tr>
          <th>Mã</th><th>SL</th><th>Giá mua</th><th>Giá TT</th>
          <th>GT thị trường</th><th>Lãi/Lỗ</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>"""


def _recent_txn_html(df: pd.DataFrame) -> str:
    type_cfg = {
        "Mua":              ("MUA",  "txn-buy"),
        "Bán":              ("BÁN",  "txn-sell"),
        "Cổ tức tiền mặt":  ("DIV",  "txn-div"),
        "Cổ tức cổ phiếu":  ("DIV",  "txn-div"),
        "Nộp tiền":         ("NẠP",  "txn-div"),
        "Rút tiền":         ("RÚT",  "txn-sell"),
    }

    html = ""
    for _, r in df.iterrows():
        t       = str(r.get("type", ""))
        sym     = str(r.get("symbol", "")).strip()
        amt     = float(str(r.get("amount", 0)).replace(",","") or 0)
        qty     = str(r.get("quantity","")).strip()
        price   = str(r.get("price","")).strip()
        dt_raw  = r.get("date")
        dt_str  = pd.to_datetime(dt_raw).strftime("%d/%m") if pd.notna(dt_raw) else ""
        acc     = str(r.get("account",""))

        lbl, badge_cls = type_cfg.get(t, (t[:3].upper(), "txn-fee"))

        sym_part  = f'<span class="txn-sym">{sym}</span>' if sym else ""
        qty_part  = f'<span style="color:{TEXT_DIM};font-size:.72rem">{qty} @ {price}</span>' if qty and qty != "0" else ""
        amt_str   = f"{amt/1e6:.2f}M" if abs(amt) >= 1e6 else f"{amt:,.0f}"
        amt_color = RED if t in ["Bán","Rút tiền"] else (GREEN if t in ["Mua","Nộp tiền","Cổ tức tiền mặt"] else TEXT_DIM)

        html += f"""
        <div class="txn-row">
          <span class="txn-badge {badge_cls}">{lbl}</span>
          {sym_part}
          {qty_part}
          <span class="txn-date" style="margin-left:4px">{dt_str}</span>
          <span class="txn-amt" style="color:{amt_color}">{amt_str}</span>
        </div>"""

    return html if html else f'<p style="color:{TEXT_DIM};font-size:.8rem">Không có giao dịch.</p>'
