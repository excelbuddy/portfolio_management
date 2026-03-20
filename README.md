# 📈 Stock Tracker - Quản lý đầu tư chứng khoán

Webapp theo dõi mua/bán và ghi nhận lãi/lỗ đầu tư chứng khoán Việt Nam.
Dữ liệu lưu trên Google Sheets, deploy qua Streamlit.

---

## 🚀 Hướng dẫn setup từ đầu

### Bước 1: Tạo Google Cloud Project & Service Account

1. Vào https://console.cloud.google.com
2. Tạo project mới (VD: `stock-tracker`)
3. Vào **APIs & Services → Library**, bật 2 API:
   - `Google Sheets API`
   - `Google Drive API`
4. Vào **APIs & Services → Credentials**
5. Click **Create Credentials → Service Account**
   - Đặt tên: `stock-tracker-sa`
   - Click **Create and Continue → Done**
6. Click vào service account vừa tạo
7. Tab **Keys → Add Key → Create new key → JSON → Create**
8. File JSON sẽ tự tải về máy (giữ file này bí mật!)

### Bước 2: Tạo Google Sheet để lưu data

1. Vào https://sheets.google.com, tạo Sheet mới, đặt tên `Stock Tracker Data`
2. Copy Sheet ID từ URL: `https://docs.google.com/spreadsheets/d/[SHEET_ID]/edit`
3. Click **Share** → paste email từ file JSON (dạng `xxx@yyy.iam.gserviceaccount.com`) → **Editor**

### Bước 3: Share Sheet giá thị trường

Sheet ID: `13M1MGQvmJR4VMiPVMTpti2Yxmk46hpncVTNN_cKWw3Y`

1. Mở sheet giá → Share → paste email service account → **Viewer** (chỉ cần đọc)

### Bước 4: Chạy app local

```bash
# Clone/tải code về
git clone <your-repo>
cd stock_tracker

# Tạo virtual env
python -m venv venv
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Cài dependencies
pip install -r requirements.txt

# Chạy app
streamlit run app.py
```

### Bước 5: Deploy lên Streamlit Cloud (miễn phí)

1. Đẩy code lên GitHub (không đẩy file JSON key lên!)
2. Vào https://share.streamlit.io → New app → chọn repo
3. Vào **Settings → Secrets**, thêm nội dung file JSON:

```toml
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = "-----BEGIN RSA PRIVATE KEY-----\n..."
client_email = "..."
# ... (copy toàn bộ nội dung JSON vào đây theo format TOML)
```

4. Sửa `sheets_manager.py` để đọc từ `st.secrets` thay vì file JSON:

```python
# Thêm vào đầu sheets_manager.py khi deploy
import streamlit as st
from google.oauth2.service_account import Credentials

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=SCOPES
)
```

---

## 📊 Cấu trúc dữ liệu trong Google Sheets

| Sheet | Mô tả |
|-------|-------|
| `Accounts` | Danh sách tài khoản, phí giao dịch |
| `Transactions` | Toàn bộ lịch sử giao dịch |
| `BuyLots` | Từng lô mua (FIFO tracking) |
| `SellMatches` | Khớp lệnh bán với lô mua, lãi/lỗ từng lô |
| `CashLedger` | Sổ tiền mặt (nộp/rút/cổ tức/phí) |

---

## 💡 Logic nghiệp vụ

- **FIFO**: Khi bán, tự động ghép với các lô mua từ cũ đến mới
- **Avg Buy Price**: Tính theo số lượng còn lại × (giá mua + phí/cổ phiếu)
- **Unrealized PnL**: (Giá TT - Giá mua TB) × Số lượng
- **Realized PnL**: Sau khi khớp lô bán = Doanh thu bán - Chi phí mua (đã phân bổ phí)
- **Cash Balance**: Nộp tiền - Rút tiền - Tiền mua CP + Tiền bán CP + Cổ tức - Phí

---

## 🗺️ Roadmap

- [x] Ghi chép giao dịch mua/bán/phí/cổ tức
- [x] Quản lý nhiều tài khoản
- [x] FIFO matching khi bán
- [x] Danh mục + unrealized PnL
- [x] Lịch sử giao dịch có filter
- [ ] Charts: Hành trình đầu tư, Lợi nhuận hàng tháng, Tiền mặt
- [ ] Export báo cáo Excel/PDF
- [ ] Cảnh báo giá mục tiêu
