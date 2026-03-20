import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, date
import uuid

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_HEADERS = {
    "Accounts": ["id", "name", "broker", "buy_fee_rate", "sell_fee_rate", "note", "created_at"],
    "Transactions": [
        "txn_id", "account", "type", "date", "symbol", "quantity",
        "price", "fee", "tax", "amount", "note", "buy_lot_id", "created_at"
    ],
    "BuyLots": [
        "lot_id", "account", "symbol", "buy_date", "quantity_original",
        "quantity_remaining", "buy_price", "buy_fee", "note", "created_at"
    ],
    "SellMatches": [
        "match_id", "sell_txn_id", "lot_id", "account", "symbol",
        "sell_date", "quantity", "buy_price", "sell_price",
        "buy_fee_alloc", "sell_fee_alloc", "sell_tax_alloc",
        "realized_pnl", "created_at"
    ],
    "CashLedger": [
        "entry_id", "account", "date", "type", "amount", "note", "created_at"
    ]
}


class SheetsManager:
    def __init__(self, key_path: str, data_sheet_id: str, price_sheet_id: str):
        creds = Credentials.from_service_account_file(key_path, scopes=SCOPES)
        self.gc = gspread.authorize(creds)
        self.data_wb = self.gc.open_by_key(data_sheet_id)
        self.price_sheet_id = price_sheet_id
        self._price_cache = None
        self._price_cache_time = None

    def init_sheets(self):
        """Create required sheets/tabs if they don't exist."""
        existing = [ws.title for ws in self.data_wb.worksheets()]
        for sheet_name, headers in SHEET_HEADERS.items():
            if sheet_name not in existing:
                ws = self.data_wb.add_worksheet(title=sheet_name, rows=1000, cols=len(headers))
                ws.append_row(headers)
            else:
                ws = self.data_wb.worksheet(sheet_name)
                # Check headers
                existing_headers = ws.row_values(1)
                if not existing_headers:
                    ws.append_row(SHEET_HEADERS[sheet_name])

    def _get_ws(self, name: str):
        return self.data_wb.worksheet(name)

    def _ws_to_df(self, name: str) -> pd.DataFrame:
        ws = self._get_ws(name)
        data = ws.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame(columns=SHEET_HEADERS[name])

    def _append_row(self, sheet_name: str, row_dict: dict):
        ws = self._get_ws(sheet_name)
        headers = SHEET_HEADERS[sheet_name]
        row = [row_dict.get(h, "") for h in headers]
        ws.append_row(row, value_input_option="USER_ENTERED")

    def _update_cell(self, sheet_name: str, row_idx: int, col_name: str, value):
        ws = self._get_ws(sheet_name)
        headers = SHEET_HEADERS[sheet_name]
        col_idx = headers.index(col_name) + 1
        ws.update_cell(row_idx + 2, col_idx, value)  # +2: 1 for header, 1 for 0-index

    # ---- Accounts ----
    def get_accounts(self) -> list:
        df = self._ws_to_df("Accounts")
        if df.empty:
            return []
        return df.to_dict(orient="records")

    def add_account(self, data: dict):
        data["id"] = str(uuid.uuid4())[:8]
        data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row("Accounts", data)

    # ---- Transactions ----
    def get_transactions(self) -> pd.DataFrame:
        return self._ws_to_df("Transactions")

    def add_transaction(self, data: dict) -> str:
        data["txn_id"] = "T" + str(uuid.uuid4())[:8].upper()
        data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row("Transactions", data)
        return data["txn_id"]

    # ---- BuyLots ----
    def get_buy_lots(self, account: str = None, symbol: str = None) -> pd.DataFrame:
        df = self._ws_to_df("BuyLots")
        if df.empty:
            return df
        if account and account != "Tất cả":
            df = df[df["account"] == account]
        if symbol:
            df = df[df["symbol"] == symbol]
        return df

    def add_buy_lot(self, data: dict) -> str:
        lot_id = "L" + str(uuid.uuid4())[:8].upper()
        data["lot_id"] = lot_id
        data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row("BuyLots", data)
        return lot_id

    def update_lot_remaining(self, lot_id: str, new_remaining: int):
        df = self._ws_to_df("BuyLots")
        if df.empty:
            return
        idx = df[df["lot_id"] == lot_id].index
        if len(idx) == 0:
            return
        row_idx = idx[0]
        self._update_cell("BuyLots", row_idx, "quantity_remaining", new_remaining)

    def get_lots_for_fifo(self, account: str, symbol: str) -> pd.DataFrame:
        """Get open buy lots sorted by date (FIFO)."""
        df = self.get_buy_lots(account, symbol)
        if df.empty:
            return df
        df = df[df["quantity_remaining"].astype(int) > 0]
        df["buy_date"] = pd.to_datetime(df["buy_date"])
        return df.sort_values("buy_date")

    # ---- SellMatches ----
    def add_sell_match(self, data: dict):
        data["match_id"] = "M" + str(uuid.uuid4())[:8].upper()
        data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row("SellMatches", data)

    def get_sell_matches(self, account: str = None) -> pd.DataFrame:
        df = self._ws_to_df("SellMatches")
        if df.empty:
            return df
        if account and account != "Tất cả":
            df = df[df["account"] == account]
        return df

    # ---- CashLedger ----
    def add_cash_entry(self, data: dict):
        data["entry_id"] = "C" + str(uuid.uuid4())[:8].upper()
        data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row("CashLedger", data)

    def get_cash_balance(self, account: str) -> float:
        df = self._ws_to_df("CashLedger")
        if df.empty:
            return 0.0
        if account != "Tất cả":
            df = df[df["account"] == account]
        if df.empty:
            return 0.0
        return float(df["amount"].astype(float).sum())

    # ---- Price Data ----
    def get_latest_price(self, symbol: str) -> float:
        """Get the most recent price for a symbol from the price sheet."""
        try:
            if self._price_cache is None:
                self._load_price_cache()
            return self._price_cache.get(symbol.upper(), 0.0)
        except Exception:
            return 0.0

    def _load_price_cache(self):
        """Load and cache prices from the price sheet."""
        try:
            price_wb = self.gc.open_by_key(self.price_sheet_id)
            ws = price_wb.worksheet("Giá")
            
            # Row 3 = date headers (C3 onwards), Col B = symbols
            # Read enough data
            all_values = ws.get_all_values()
            
            if len(all_values) < 4:
                self._price_cache = {}
                return
            
            # Row index 2 (0-based) = row 3 = dates
            date_row = all_values[2]  # dates in C3 onwards -> index 2 onwards
            
            # Find the most recent non-empty date column
            # Columns: A=0, B=1, C=2 onwards
            latest_col_idx = None
            for i in range(2, len(date_row)):
                if date_row[i].strip():
                    latest_col_idx = i
                    break  # First non-empty after C is most recent (leftmost = newest based on image)
            
            if latest_col_idx is None:
                self._price_cache = {}
                return
            
            price_cache = {}
            for row in all_values[3:]:  # Data starts at row 4 (index 3)
                if len(row) > 1 and row[1].strip():  # Col B = symbol
                    symbol = row[1].strip().upper()
                    if len(row) > latest_col_idx and row[latest_col_idx].strip():
                        try:
                            price = float(str(row[latest_col_idx]).replace(",", "").replace(".", ""))
                            price_cache[symbol] = price
                        except ValueError:
                            pass
            
            self._price_cache = price_cache
            self._price_cache_time = datetime.now()
        except Exception as e:
            self._price_cache = {}

    def get_all_symbols(self) -> list:
        """Get all symbols from buy lots."""
        df = self._ws_to_df("BuyLots")
        if df.empty:
            return []
        return sorted(df["symbol"].dropna().unique().tolist())
