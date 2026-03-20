import streamlit as st
import pandas as pd
from datetime import date
import json, tempfile, sys, os

sys.path.append(os.path.dirname(__file__))
from sheets_manager import SheetsManager
from portfolio_logic import PortfolioLogic
from config import get_config

st.set_page_config(page_title="📈 Stock Tracker", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
  .section-header{font-size:1.1rem;font-weight:600;color:#2e75b6;
    border-bottom:2px solid #2e75b6;padding-bottom:4px;margin-top:1rem;}
  .stDataFrame{font-size:.85rem;}
  .source-badge{font-size:.75rem;padding:2px 8px;border-radius:10px;
    background:#e8f4ea;color:#2d6a2d;font-weight:600;}
</style>
""", unsafe_allow_html=True)

# ── session defaults ──────────────────────────────────────────────────────────
for k, v in [("sm", None), ("connected", False),
              ("selected_account", "Tất cả"), ("accounts", []),
              ("auto_connect_tried", False)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Auto-connect on first load if config is preset ───────────────────────────
if not st.session_state.connected and not st.session_state.auto_connect_tried:
    st.session_state.auto_connect_tried = True
    cfg = get_config()
    if cfg["source"] in ("secrets", "env") and cfg["key_path"] and cfg["data_sheet_id"]:
        try:
            sm = SheetsManager(cfg["key_path"], cfg["data_sheet_id"], cfg["price_sheet_id"])
            sm.init_sheets()
            st.session_state.sm        = sm
            st.session_state.accounts  = sm.get_accounts()
            st.session_state.connected = True
            st.session_state.cfg_source = cfg["source"]
        except Exception as e:
            st.session_state.auto_connect_error = str(e)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📈 Stock Tracker")

    if st.session_state.connected:
        source = st.session_state.get("cfg_source", "manual")
        badge_label = {"secrets": "☁️ Streamlit Secrets", "env": "🖥️ Local .env",
                       "manual": "🔧 Manual"}.get(source, source)
        st.markdown(f'<span class="source-badge">{badge_label}</span>', unsafe_allow_html=True)
        st.success("🟢 Đã kết nối")
        st.divider()

        account_names = ["Tất cả"] + [a["name"] for a in st.session_state.accounts]
        st.session_state.selected_account = st.selectbox("📂 Tài khoản", account_names)

        if st.button("🔄 Làm mới dữ liệu", use_container_width=True):
            st.session_state.sm.invalidate(
                "Accounts","Transactions","BuyLots","SellMatches","CashLedger")
            st.session_state.accounts = st.session_state.sm.get_accounts()
            st.rerun()

    else:
        # Show error if auto-connect failed
        if err := st.session_state.get("auto_connect_error"):
            st.error(f"Auto-connect lỗi: {err}")

        st.markdown("### 🔌 Kết nối thủ công")
        st.caption("(Hoặc setup secrets/env để tự động kết nối)")

        uploaded_key   = st.file_uploader("Service Account JSON", type=["json"])
        data_sheet_id  = st.text_input("Sheet ID data",
                                        value="16gIB0warr2vScFaNUGex3ZVrgRZ88cDmSv17uLydFc8",
                                        placeholder="Paste Sheet ID")
        price_sheet_id = st.text_input("Sheet ID bảng giá",
                                        value="13M1MGQvmJR4VMiPVMTpti2Yxmk46hpncVTNN_cKWw3Y")

        if st.button("🔌 Kết nối", type="primary", use_container_width=True):
            if uploaded_key and data_sheet_id:
                try:
                    key_data = json.loads(uploaded_key.read())
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                        json.dump(key_data, f)
                        tmp_path = f.name
                    sm = SheetsManager(tmp_path, data_sheet_id, price_sheet_id)
                    sm.init_sheets()
                    st.session_state.sm         = sm
                    st.session_state.accounts   = sm.get_accounts()
                    st.session_state.connected  = True
                    st.session_state.cfg_source = "manual"
                    st.success("✅ Kết nối thành công!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Lỗi: {e}")
            else:
                st.warning("Vui lòng upload JSON key")

        with st.expander("📖 Hướng dẫn setup tự động"):
            st.markdown("""
**Để không phải upload JSON mỗi lần:**

**Local:** Đổi tên `.env.example` → `.env`, điền thông tin vào.

**Streamlit Cloud:** Vào app Settings → Secrets, điền:
```toml
DATA_SHEET_ID  = "16gIB0war..."
PRICE_SHEET_ID = "13M1MGQvm..."

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key = "-----BEGIN RSA PRIVATE KEY-----\\n..."
client_email = "...@....iam.gserviceaccount.com"
# copy toàn bộ các field từ file JSON
```
            """)

# ── Guard ─────────────────────────────────────────────────────────────────────
if not st.session_state.connected:
    st.markdown("## 📈 Stock Tracker")
    st.info("👈 Kết nối Google Sheets ở thanh bên trái để bắt đầu.")
    st.stop()

sm: SheetsManager = st.session_state.sm
logic             = PortfolioLogic(sm)
selected_account  = st.session_state.selected_account
accounts          = st.session_state.accounts

# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs(["📋 Danh mục", "➕ Ghi giao dịch",
                                   "🏦 Quản lý tài khoản", "📜 Lịch sử GD"])

# ──────────────────────────────────────────── TAB 1: DANH MỤC ────────────────
with tab1:
    st.markdown('<div class="section-header">📊 Danh mục đang nắm giữ</div>', unsafe_allow_html=True)

    portfolio_df = logic.get_portfolio(selected_account)
    summary      = logic.get_summary(selected_account)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Giá trị thị trường", f"{summary['market_value']:,.0f} đ")
    c2.metric("📥 Tổng tiền đầu tư",   f"{summary['total_invested']:,.0f} đ")
    c3.metric("📈 Lãi dự kiến",
              f"{summary['unrealized_pnl']:,.0f} đ",
              delta=f"{summary['unrealized_pnl_pct']:+.1f}%")
    c4.metric("🏦 Tiền mặt", f"{summary['cash']:,.0f} đ")

    st.divider()
    if not portfolio_df.empty:
        disp = portfolio_df.copy()
        for col in ["buy_value","market_value","unrealized_pnl"]:
            if col in disp.columns:
                disp[col] = disp[col].apply(lambda x: f"{x:,.0f}")
        if "unrealized_pnl_pct" in disp.columns:
            disp["unrealized_pnl_pct"] = disp["unrealized_pnl_pct"].apply(lambda x: f"{x:.1f}%")
        for col in ["avg_buy_price","current_price"]:
            if col in disp.columns:
                disp[col] = disp[col].apply(lambda x: f"{x:,.0f}")
        disp = disp.rename(columns={
            "symbol":"Mã CP","quantity":"SL","avg_buy_price":"Giá mua TB",
            "current_price":"Giá TT","buy_value":"Giá trị mua",
            "market_value":"Giá trị TT","unrealized_pnl":"Lãi DK","unrealized_pnl_pct":"% Lãi"
        })
        st.dataframe(disp, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có cổ phiếu nào trong danh mục.")

    st.markdown('<div class="section-header">✅ Lợi nhuận đã ghi nhận</div>', unsafe_allow_html=True)
    realized_df = logic.get_realized_pnl(selected_account)
    if not realized_df.empty:
        st.dataframe(realized_df, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có giao dịch bán nào.")

# ──────────────────────────────────────────── TAB 2: GHI GIAO DỊCH ───────────
with tab2:
    st.markdown('<div class="section-header">➕ Ghi giao dịch mới</div>', unsafe_allow_html=True)

    if not accounts:
        st.warning("⚠️ Chưa có tài khoản. Tạo tài khoản ở tab 'Quản lý tài khoản' trước.")
    else:
        account_options = [a["name"] for a in accounts]
        col1, col2 = st.columns([1, 2])

        with col1:
            txn_account = st.selectbox("Tài khoản *", account_options, key="txn_acct")
            txn_type    = st.selectbox("Loại giao dịch *", [
                "Mua","Bán","Cổ tức tiền mặt","Cổ tức cổ phiếu",
                "Phí quản lý TK","Phí lưu ký","Phí margin","Phí ứng trước","Phí khác",
                "Nộp tiền","Rút tiền"
            ], key="txn_type_sel")
            txn_date = st.date_input("Ngày GD *", value=date.today(), key="txn_dt")

        needs_symbol = txn_type in ["Mua","Bán","Cổ tức cổ phiếu","Cổ tức tiền mặt"]
        needs_qty    = txn_type in ["Mua","Bán","Cổ tức cổ phiếu"]
        needs_price  = txn_type in ["Mua","Bán"]
        needs_amount = txn_type in ["Cổ tức tiền mặt","Phí quản lý TK","Phí lưu ký",
                                    "Phí margin","Phí ứng trước","Phí khác","Nộp tiền","Rút tiền"]

        acc_info      = next((a for a in accounts if a["name"] == txn_account), {})
        buy_fee_rate  = float(acc_info.get("buy_fee_rate",  0.15)) / 100
        sell_fee_rate = float(acc_info.get("sell_fee_rate", 0.15)) / 100

        with col2:
            txn_symbol = ""
            txn_qty = txn_price = txn_amount = 0

            if needs_symbol:
                txn_symbol = st.text_input("Mã cổ phiếu *", key="txn_sym").upper().strip()
            if needs_qty:
                txn_qty = st.number_input("Số lượng *", min_value=0, step=100, value=0, key="txn_qty")
            if needs_price:
                txn_price = st.number_input("Giá *", min_value=0, step=100, value=0, key="txn_price")
                # Chỉ hiển thị thông tin % - không dùng widget để tính fee/tax
                gross = txn_qty * txn_price
                if txn_type == "Mua":
                    fee_rate_pct = acc_info.get("buy_fee_rate", 0.15)
                    st.info(f"💡 Phí mua: **{fee_rate_pct}%** → ~{int(gross * float(fee_rate_pct) / 100):,} đ  |  Thuế: không có")
                else:  # Bán
                    fee_rate_pct = acc_info.get("sell_fee_rate", 0.15)
                    st.info(f"💡 Phí bán: **{fee_rate_pct}%** → ~{int(gross * float(fee_rate_pct) / 100):,} đ  |  Thuế TNCN: **0.1%** → ~{int(gross * 0.001):,} đ")

            if needs_amount:
                txn_amount = st.number_input("Số tiền *", min_value=0, step=10000, key="txn_amt")
                if txn_type == "Cổ tức tiền mặt":
                    st.info(f"💡 Thuế cổ tức: **5%** → ~{int(txn_amount * 0.05):,} đ")

            txn_note = st.text_input("Ghi chú", key="txn_note")

        st.divider()
        if st.button("💾 Lưu giao dịch", type="primary"):
            errors = []
            if needs_symbol and not txn_symbol:  errors.append("Chưa nhập mã cổ phiếu")
            if needs_qty    and txn_qty    <= 0: errors.append("Số lượng phải > 0")
            if needs_price  and txn_price  <= 0: errors.append("Giá phải > 0")
            if needs_amount and txn_amount <= 0: errors.append("Số tiền phải > 0")

            if errors:
                for e in errors: st.error(f"❌ {e}")
            else:
                try:
                    # Tính phí và thuế hoàn toàn trong Python - không phụ thuộc widget
                    _buy_fee_rate  = float(acc_info.get("buy_fee_rate",  0.15)) / 100
                    _sell_fee_rate = float(acc_info.get("sell_fee_rate", 0.15)) / 100
                    _gross = txn_qty * txn_price

                    if txn_type == "Mua":
                        calc_fee = round(_gross * _buy_fee_rate)
                        calc_tax = 0
                    elif txn_type == "Bán":
                        calc_fee = round(_gross * _sell_fee_rate)
                        calc_tax = round(_gross * 0.001)   # TNCN 0.1%
                    elif txn_type == "Cổ tức tiền mặt":
                        calc_fee = 0
                        calc_tax = round(txn_amount * 0.05)  # 5%
                    else:
                        calc_fee = 0
                        calc_tax = 0

                    final_amount = _gross if needs_price else txn_amount

                    msg = logic.add_transaction({
                        "account":  txn_account,
                        "type":     txn_type,
                        "date":     str(txn_date),
                        "symbol":   txn_symbol,
                        "quantity": txn_qty,
                        "price":    txn_price,
                        "fee":      calc_fee,
                        "tax":      calc_tax,
                        "amount":   final_amount,
                        "note":     txn_note
                    })
                    st.success(msg)
                    sm.invalidate("Transactions","BuyLots","SellMatches","CashLedger")
                except Exception as e:
                    st.error(f"❌ Lỗi: {e}")

# ──────────────────────────────────────────── TAB 3: TÀI KHOẢN ───────────────
with tab3:
    st.markdown('<div class="section-header">🏦 Danh sách tài khoản</div>', unsafe_allow_html=True)

    if accounts:
        acc_df    = pd.DataFrame(accounts)
        rename_map = {"name":"Tên TK","broker":"CTCK",
                      "buy_fee_rate":"Phí mua (%)","sell_fee_rate":"Phí bán (%)","note":"Ghi chú"}
        disp_cols = [c for c in rename_map if c in acc_df.columns]
        st.dataframe(acc_df[disp_cols].rename(columns=rename_map),
                     use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có tài khoản nào.")

    st.divider()
    st.markdown('<div class="section-header">➕ Thêm tài khoản mới</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        new_name   = st.text_input("Tên tài khoản *", key="new_acc_name")
        new_broker = st.text_input("Công ty CK",      key="new_broker")
    with c2:
        new_buy_fee  = st.number_input("Phí mua (%)", min_value=0.0, max_value=1.0,
                                       value=0.15, step=0.01, format="%.3f", key="new_buy_fee")
        new_sell_fee = st.number_input("Phí bán (%)", min_value=0.0, max_value=1.0,
                                       value=0.15, step=0.01, format="%.3f", key="new_sell_fee")
    with c3:
        new_note = st.text_input("Ghi chú", key="new_acc_note")
        st.write("")
        if st.button("➕ Thêm tài khoản", type="primary"):
            if new_name:
                sm.add_account({"name":new_name,"broker":new_broker,
                                "buy_fee_rate":new_buy_fee,"sell_fee_rate":new_sell_fee,
                                "note":new_note})
                st.session_state.accounts = sm.get_accounts()
                st.success(f"✅ Đã thêm '{new_name}'")
                st.rerun()
            else:
                st.error("Vui lòng nhập tên tài khoản")

# ──────────────────────────────────────────── TAB 4: LỊCH SỬ ─────────────────
with tab4:
    st.markdown('<div class="section-header">📜 Lịch sử giao dịch</div>', unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        filter_type = st.multiselect("Loại GD", [
            "Mua","Bán","Cổ tức tiền mặt","Cổ tức cổ phiếu",
            "Phí quản lý TK","Phí lưu ký","Phí margin","Phí ứng trước","Phí khác",
            "Nộp tiền","Rút tiền"])
    with fc2:
        filter_symbol = st.text_input("Mã CP", placeholder="VD: VCB").upper()
    with fc3:
        date_range = st.date_input("Khoảng thời gian",
                                   value=(date(date.today().year, 1, 1), date.today()))

    txn_df = logic.get_transactions(selected_account, filter_type, filter_symbol, date_range)
    if not txn_df.empty:
        st.dataframe(txn_df, use_container_width=True, hide_index=True)
        if "Loại" in txn_df.columns and "Giá trị" in txn_df.columns:
            nums = pd.to_numeric(txn_df["Giá trị"], errors="coerce").fillna(0)
            total_buy  = nums[txn_df["Loại"] == "Mua"].sum()
            total_sell = nums[txn_df["Loại"] == "Bán"].sum()
            st.caption(f"Tổng mua: {total_buy:,.0f} đ  |  Tổng bán: {total_sell:,.0f} đ")
    else:
        st.info("Không có giao dịch nào trong điều kiện lọc.")
