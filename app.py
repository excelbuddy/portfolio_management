import streamlit as st
import pandas as pd
from datetime import date, datetime
import sys
import os

sys.path.append(os.path.dirname(__file__))

from sheets_manager import SheetsManager
from portfolio_logic import PortfolioLogic

st.set_page_config(
    page_title="📈 Stock Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    .main-header {font-size: 1.8rem; font-weight: 700; color: #1f4e79; margin-bottom: 0.5rem;}
    .section-header {font-size: 1.1rem; font-weight: 600; color: #2e75b6; border-bottom: 2px solid #2e75b6; padding-bottom: 4px; margin-top: 1rem;}
    .metric-card {background: #f0f4ff; border-radius: 10px; padding: 12px 16px; border-left: 4px solid #2e75b6;}
    .profit-positive {color: #0a7c42; font-weight: 600;}
    .profit-negative {color: #c0392b; font-weight: 600;}
    .stDataFrame {font-size: 0.85rem;}
</style>
""", unsafe_allow_html=True)

# --- Init session ---
if "sm" not in st.session_state:
    st.session_state.sm = None
if "connected" not in st.session_state:
    st.session_state.connected = False

# --- Sidebar: connection ---
with st.sidebar:
    st.markdown("## ⚙️ Cấu hình kết nối")
    
    uploaded_key = st.file_uploader("Upload Service Account JSON", type=["json"])
    data_sheet_id = st.text_input(
        "Sheet ID lưu data của bạn",
        placeholder="Paste Sheet ID tại đây",
        help="Tạo 1 Google Sheet mới, lấy ID từ URL: .../spreadsheets/d/[ID]/edit"
    )
    price_sheet_id = st.text_input(
        "Sheet ID bảng giá",
        value="13M1MGQvmJR4VMiPVMTpti2Yxmk46hpncVTNN_cKWw3Y",
        help="Sheet chứa dữ liệu giá thị trường hàng ngày"
    )

    if st.button("🔌 Kết nối", type="primary", use_container_width=True):
        if uploaded_key and data_sheet_id:
            try:
                import json, tempfile
                key_data = json.loads(uploaded_key.read())
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(key_data, f)
                    tmp_path = f.name
                sm = SheetsManager(tmp_path, data_sheet_id, price_sheet_id)
                sm.init_sheets()
                st.session_state.sm = sm
                st.session_state.connected = True
                st.success("✅ Kết nối thành công!")
            except Exception as e:
                st.error(f"❌ Lỗi: {e}")
        else:
            st.warning("Vui lòng upload JSON key và nhập Sheet ID")

    if st.session_state.connected:
        st.success("🟢 Đã kết nối")
        st.divider()
        # Account selector
        sm: SheetsManager = st.session_state.sm
        accounts = sm.get_accounts()
        account_names = ["Tất cả"] + [a["name"] for a in accounts]
        selected_account = st.selectbox("📂 Tài khoản", account_names)
        st.session_state.selected_account = selected_account
        st.session_state.accounts = accounts

# --- Main content ---
if not st.session_state.connected:
    st.markdown('<div class="main-header">📈 Stock Tracker - Quản lý đầu tư chứng khoán</div>', unsafe_allow_html=True)
    st.info("👈 Vui lòng kết nối Google Sheets ở thanh bên trái để bắt đầu.")
    
    with st.expander("📖 Hướng dẫn setup lần đầu"):
        st.markdown("""
**Bước 1:** Tạo Google Cloud Project và bật Google Sheets API + Google Drive API  
**Bước 2:** Tạo Service Account → Tải file JSON key  
**Bước 3:** Tạo Google Sheet mới để lưu data, copy Sheet ID từ URL  
**Bước 4:** Share cả 2 Google Sheet cho email trong file JSON (role: Editor)  
**Bước 5:** Upload JSON key và nhập Sheet IDs ở thanh bên trái → Kết nối  

App sẽ tự động tạo các tab cần thiết trong Sheet của bạn.
        """)
    st.stop()

sm: SheetsManager = st.session_state.sm
logic = PortfolioLogic(sm)
selected_account = st.session_state.get("selected_account", "Tất cả")
accounts = st.session_state.get("accounts", [])

tab1, tab2, tab3, tab4 = st.tabs(["📋 Danh mục", "➕ Ghi giao dịch", "🏦 Quản lý tài khoản", "📜 Lịch sử GD"])

# ===================== TAB 1: PORTFOLIO =====================
with tab1:
    st.markdown('<div class="section-header">📊 Danh mục đang nắm giữ</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    portfolio_df = logic.get_portfolio(selected_account)
    summary = logic.get_summary(selected_account)
    
    with col1:
        st.metric("💰 Tổng giá trị thị trường", 
                  f"{summary['market_value']:,.0f} đ",
                  delta=f"{summary['unrealized_pnl']:+,.0f} đ")
    with col2:
        st.metric("📥 Tổng tiền đã đầu tư", f"{summary['total_invested']:,.0f} đ")
    with col3:
        pnl_pct = summary['unrealized_pnl_pct']
        st.metric("📈 Lãi dự kiến", 
                  f"{summary['unrealized_pnl']:,.0f} đ",
                  delta=f"{pnl_pct:.1f}%")
    with col4:
        st.metric("🏦 Tiền mặt", f"{summary['cash']:,.0f} đ")

    st.divider()
    
    if not portfolio_df.empty:
        # Format for display
        display_df = portfolio_df.copy()
        for col in ["buy_value", "market_value", "unrealized_pnl"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"{x:,.0f}")
        if "unrealized_pnl_pct" in display_df.columns:
            display_df["unrealized_pnl_pct"] = display_df["unrealized_pnl_pct"].apply(lambda x: f"{x:.1f}%")
        
        display_df = display_df.rename(columns={
            "symbol": "Mã CP",
            "quantity": "Số lượng",
            "avg_buy_price": "Giá mua TB",
            "current_price": "Giá thị trường",
            "buy_value": "Giá trị mua",
            "market_value": "Giá trị TT",
            "unrealized_pnl": "Lãi dự kiến",
            "unrealized_pnl_pct": "% Lãi"
        })
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có cổ phiếu nào trong danh mục.")

    # Realized PnL section
    st.markdown('<div class="section-header">✅ Lợi nhuận đã ghi nhận</div>', unsafe_allow_html=True)
    realized_df = logic.get_realized_pnl(selected_account)
    if not realized_df.empty:
        st.dataframe(realized_df, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có giao dịch bán nào.")

# ===================== TAB 2: ADD TRANSACTION =====================
with tab2:
    st.markdown('<div class="section-header">➕ Ghi giao dịch mới</div>', unsafe_allow_html=True)
    
    if not accounts:
        st.warning("⚠️ Chưa có tài khoản nào. Vui lòng tạo tài khoản ở tab 'Quản lý tài khoản'.")
    else:
        account_options = [a["name"] for a in accounts]
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            txn_account = st.selectbox("Tài khoản *", account_options, key="txn_account")
            txn_type = st.selectbox("Loại giao dịch *", [
                "Mua", "Bán", 
                "Cổ tức tiền mặt", "Cổ tức cổ phiếu",
                "Phí quản lý TK", "Phí lưu ký", "Phí margin", 
                "Phí ứng trước", "Phí khác",
                "Nộp tiền", "Rút tiền"
            ], key="txn_type")
            txn_date = st.date_input("Ngày GD *", value=date.today(), key="txn_date")
        
        with col2:
            needs_symbol = txn_type in ["Mua", "Bán", "Cổ tức cổ phiếu", "Cổ tức tiền mặt"]
            needs_qty = txn_type in ["Mua", "Bán", "Cổ tức cổ phiếu"]
            needs_price = txn_type in ["Mua", "Bán"]
            
            if needs_symbol:
                # Try to get symbols from portfolio
                all_symbols = sm.get_all_symbols()
                txn_symbol = st.text_input("Mã cổ phiếu *", key="txn_symbol").upper()
            
            if needs_qty:
                txn_qty = st.number_input("Số lượng *", min_value=1, step=100, key="txn_qty")
            
            if needs_price:
                txn_price = st.number_input("Giá *", min_value=0, step=100, key="txn_price")
                
                # Auto-fill fee/tax from account settings
                acc_info = next((a for a in accounts if a["name"] == txn_account), None)
                if acc_info:
                    if txn_type == "Mua":
                        auto_fee_rate = float(acc_info.get("buy_fee_rate", 0.15)) / 100
                        fee_amount = int(txn_qty * txn_price * auto_fee_rate) if needs_qty else 0
                        txn_fee = st.number_input("Phí giao dịch", value=fee_amount, step=1000, key="txn_fee",
                                                   help=f"Tự động tính theo phí mua {acc_info.get('buy_fee_rate','0.15')}%")
                        txn_tax = st.number_input("Thuế", value=0, step=1000, key="txn_tax", disabled=True)
                    else:  # Bán
                        auto_fee_rate = float(acc_info.get("sell_fee_rate", 0.15)) / 100
                        tax_rate = 0.001  # 0.1% thuế TNCN
                        fee_amount = int(txn_qty * txn_price * auto_fee_rate) if needs_qty else 0
                        tax_amount = int(txn_qty * txn_price * tax_rate) if needs_qty else 0
                        txn_fee = st.number_input("Phí giao dịch", value=fee_amount, step=1000, key="txn_fee")
                        txn_tax = st.number_input("Thuế TNCN (0.1%)", value=tax_amount, step=1000, key="txn_tax")
                else:
                    txn_fee = st.number_input("Phí giao dịch", value=0, step=1000, key="txn_fee")
                    txn_tax = st.number_input("Thuế", value=0, step=1000, key="txn_tax")
            
            # Cash amount for non-buy/sell
            if txn_type in ["Cổ tức tiền mặt", "Phí quản lý TK", "Phí lưu ký", 
                            "Phí margin", "Phí ứng trước", "Phí khác", "Nộp tiền", "Rút tiền"]:
                txn_amount = st.number_input("Số tiền *", min_value=0, step=10000, key="txn_amount")
                if txn_type == "Cổ tức tiền mặt":
                    txn_tax_div = st.number_input("Thuế cổ tức (5%)", 
                                                   value=int(txn_amount * 0.05) if 'txn_amount' in st.session_state else 0,
                                                   step=1000, key="txn_tax_div")
            
            txn_note = st.text_input("Ghi chú", key="txn_note")
        
        st.divider()
        
        if st.button("💾 Lưu giao dịch", type="primary", use_container_width=False):
            try:
                txn_data = {
                    "account": txn_account,
                    "type": txn_type,
                    "date": str(txn_date),
                    "symbol": txn_symbol if needs_symbol and 'txn_symbol' in dir() else "",
                    "quantity": txn_qty if needs_qty else 0,
                    "price": txn_price if needs_price else 0,
                    "fee": txn_fee if needs_price else (txn_amount if txn_type not in ["Nộp tiền", "Rút tiền", "Cổ tức tiền mặt"] else 0),
                    "tax": txn_tax if needs_price else (txn_tax_div if txn_type == "Cổ tức tiền mặt" else 0),
                    "amount": (txn_qty * txn_price) if needs_price else txn_amount if 'txn_amount' in dir() else 0,
                    "note": txn_note
                }
                
                result = logic.add_transaction(txn_data)
                st.success(f"✅ {result}")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Lỗi khi lưu: {e}")

# ===================== TAB 3: ACCOUNT MANAGEMENT =====================
with tab3:
    st.markdown('<div class="section-header">🏦 Danh sách tài khoản</div>', unsafe_allow_html=True)
    
    if accounts:
        acc_df = pd.DataFrame(accounts)
        display_cols = {
            "name": "Tên tài khoản",
            "broker": "Công ty CK",
            "buy_fee_rate": "Phí mua (%)",
            "sell_fee_rate": "Phí bán (%)",
            "note": "Ghi chú"
        }
        acc_display = acc_df[[c for c in display_cols if c in acc_df.columns]].rename(columns=display_cols)
        st.dataframe(acc_display, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có tài khoản nào.")
    
    st.divider()
    st.markdown('<div class="section-header">➕ Thêm tài khoản mới</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        new_acc_name = st.text_input("Tên tài khoản *", placeholder="VD: SSI - Tài khoản chính")
        new_broker = st.text_input("Công ty chứng khoán", placeholder="VD: SSI, VPS, VCSC...")
    with col2:
        new_buy_fee = st.number_input("Phí mua (%)", min_value=0.0, max_value=1.0, value=0.15, step=0.01, format="%.3f")
        new_sell_fee = st.number_input("Phí bán (%)", min_value=0.0, max_value=1.0, value=0.15, step=0.01, format="%.3f")
    with col3:
        new_acc_note = st.text_input("Ghi chú", key="new_acc_note")
        st.write("")
        if st.button("➕ Thêm tài khoản", type="primary"):
            if new_acc_name:
                sm.add_account({
                    "name": new_acc_name,
                    "broker": new_broker,
                    "buy_fee_rate": new_buy_fee,
                    "sell_fee_rate": new_sell_fee,
                    "note": new_acc_note
                })
                st.success(f"✅ Đã thêm tài khoản '{new_acc_name}'")
                st.rerun()
            else:
                st.error("Vui lòng nhập tên tài khoản")

# ===================== TAB 4: TRANSACTION HISTORY =====================
with tab4:
    st.markdown('<div class="section-header">📜 Lịch sử giao dịch</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_type = st.multiselect("Loại GD", ["Mua", "Bán", "Cổ tức tiền mặt", "Cổ tức cổ phiếu",
                                                    "Phí quản lý TK", "Phí lưu ký", "Phí margin",
                                                    "Phí ứng trước", "Phí khác", "Nộp tiền", "Rút tiền"])
    with col2:
        filter_symbol = st.text_input("Mã CP", placeholder="VD: VCB").upper()
    with col3:
        date_range = st.date_input("Khoảng thời gian", value=(date(date.today().year, 1, 1), date.today()))
    
    txn_df = logic.get_transactions(selected_account, filter_type, filter_symbol, date_range)
    
    if not txn_df.empty:
        st.dataframe(txn_df, use_container_width=True, hide_index=True)
        
        # Summary
        total_buy = txn_df[txn_df["Loại"] == "Mua"]["Giá trị"].sum() if "Giá trị" in txn_df.columns else 0
        total_sell = txn_df[txn_df["Loại"] == "Bán"]["Giá trị"].sum() if "Giá trị" in txn_df.columns else 0
        st.caption(f"Tổng mua: {total_buy:,.0f} đ | Tổng bán: {total_sell:,.0f} đ")
    else:
        st.info("Không có giao dịch nào trong điều kiện lọc.")
