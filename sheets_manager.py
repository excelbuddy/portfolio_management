import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import uuid
import time

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_HEADERS = {
    "Accounts":     ["id", "name", "broker", "buy_fee_rate", "sell_fee_rate", "note", "created_at"],
    "Transactions": ["txn_id", "account", "type", "date", "symbol", "quantity",
                     "price", "fee", "tax", "amount", "note", "buy_lot_id", "created_at"],
    "BuyLots":      ["lot_id", "account", "symbol", "buy_date", "quantity_original",
                     "quantity_remaining", "buy_price", "buy_fee", "note", "created_at"],
    "SellMatches":  ["match_id", "sell_txn_id", "lot_id", "account", "symbol",
                     "sell_date", "quantity", "buy_price", "sell_price",
                     "buy_fee_alloc", "sell_fee_alloc", "sell_tax_alloc",
                     "realized_pnl", "created_at"],
    "CashLedger":   ["entry_id", "account", "date", "type", "amount", "note", "created_at"]
}

CACHE_TTL = 30  # seconds


class SheetsManager:
    def __init__(self, key_path: str, data_sheet_id: str, price_sheet_id: str):
        creds = Credentials.from_service_account_file(key_path, scopes=SCOPES)
        self.gc = gspread.authorize(creds)
        self.data_wb = self.gc.open_by_key(data_sheet_id)
        self.price_sheet_id = price_sheet_id
        self._cache: dict = {}
        self._price_cache: dict = {}
        self._price_cache_ts: float = 0

    # ------------------------------------------------------------------ helpers
    def _get_ws(self, name: str):
        return self.data_wb.worksheet(name)

    def _ws_to_df(self, name: str, force_refresh: bool = False) -> pd.DataFrame:
        now = time.time()
        cached = self._cache.get(name)
        if not force_refresh and cached and (now - cached["ts"]) < CACHE_TTL:
            return cached["df"].copy()
        ws = self._get_ws(name)
        data = ws.get_all_records(default_blank="")
        df = pd.DataFrame(data) if data else pd.DataFrame(columns=SHEET_HEADERS[name])
        self._cache[name] = {"df": df, "ts": now}
        return df.copy()

    def invalidate(self, *sheet_names):
        for name in sheet_names:
            self._cache.pop(name, None)

    def _append_row(self, sheet_name: str, row_dict: dict):
        ws = self._get_ws(sheet_name)
        headers = SHEET_HEADERS[sheet_name]
        row = [str(row_dict.get(h, "")) for h in headers]
        ws.append_row(row, value_input_option="USER_ENTERED")
        self.invalidate(sheet_name)

    def _update_cell_by_key(self, sheet_name: str, key_col: str, key_val: str,
                             target_col: str, new_value):
        ws = self._get_ws(sheet_name)
        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return
        header_row = all_values[0]
        try:
            key_idx   = header_row.index(key_col)
            value_idx = header_row.index(target_col)
        except ValueError:
            return
        for i, row in enumerate(all_values[1:], start=2):
            if len(row) > key_idx and row[key_idx] == str(key_val):
                ws.update_cell(i, value_idx + 1, str(new_value))
                self.invalidate(sheet_name)
                return

    # ------------------------------------------------------------------ init
    def init_sheets(self):
        existing = {ws.title for ws in self.data_wb.worksheets()}
        for sheet_name, headers in SHEET_HEADERS.items():
            if sheet_name not in existing:
                ws = self.data_wb.add_worksheet(title=sheet_name, rows=2000, cols=len(headers) + 2)
                ws.append_row(headers)
            else:
                ws = self.data_wb.worksheet(sheet_name)
                if not ws.row_values(1):
                    ws.append_row(headers)

    # ------------------------------------------------------------------ accounts
    def get_accounts(self) -> list:
        df = self._ws_to_df("Accounts")
        return df.to_dict(orient="records") if not df.empty else []

    def add_account(self, data: dict):
        data["id"] = str(uuid.uuid4())[:8]
        data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row("Accounts", data)

    # ------------------------------------------------------------------ transactions
    def get_transactions(self) -> pd.DataFrame:
        return self._ws_to_df("Transactions")

    def add_transaction(self, data: dict) -> str:
        data["txn_id"] = "T" + str(uuid.uuid4())[:8].upper()
        data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row("Transactions", data)
        return data["txn_id"]

    # ------------------------------------------------------------------ buy lots
    def get_buy_lots(self, account: str = None, symbol: str = None) -> pd.DataFrame:
        df = self._ws_to_df("BuyLots")
        if df.empty:
            return df
        if account and account != "Tất cả":
            df = df[df["account"] == account]
        if symbol:
            df = df[df["symbol"] == symbol.upper()]
        return df

    def add_buy_lot(self, data: dict) -> str:
        lot_id = "L" + str(uuid.uuid4())[:8].upper()
        data["lot_id"] = lot_id
        data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row("BuyLots", data)
        return lot_id

    def update_lot_remaining(self, lot_id: str, new_remaining: int):
        self._update_cell_by_key("BuyLots", "lot_id", lot_id, "quantity_remaining", new_remaining)

    def get_lots_for_fifo(self, account: str, symbol: str) -> pd.DataFrame:
        df = self.get_buy_lots(account, symbol)
        if df.empty:
            return df
        df["quantity_remaining"] = pd.to_numeric(df["quantity_remaining"], errors="coerce").fillna(0).astype(int)
        df = df[df["quantity_remaining"] > 0].copy()
        df["buy_date"] = pd.to_datetime(df["buy_date"], errors="coerce")
        return df.sort_values("buy_date")

    # ------------------------------------------------------------------ sell matches
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

    # ------------------------------------------------------------------ cash ledger
    def add_cash_entry(self, data: dict):
        data["entry_id"] = "C" + str(uuid.uuid4())[:8].upper()
        data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row("CashLedger", data)

    def get_cash_balance(self, account: str) -> float:
        df = self._ws_to_df("CashLedger")
        if df.empty:
            return 0.0
        if account and account != "Tất cả":
            df = df[df["account"] == account]
        if df.empty:
            return 0.0
        return float(pd.to_numeric(df["amount"], errors="coerce").fillna(0).sum())

    # ------------------------------------------------------------------ prices
    def get_latest_price(self, symbol: str) -> float:
        if not self._price_cache or (time.time() - self._price_cache_ts) > 3600:
            self._load_price_cache()
        return self._price_cache.get(symbol.upper(), 0.0)

    def _load_price_cache(self):
        try:
            price_wb = self.gc.open_by_key(self.price_sheet_id)
            ws = price_wb.worksheet("Giá")
            all_values = ws.get_all_values()
            if len(all_values) < 4:
                self._price_cache = {}
                return
            date_row = all_values[2]
            latest_col_idx = None
            for i in range(2, len(date_row)):
                if date_row[i].strip():
                    latest_col_idx = i
                    break
            if latest_col_idx is None:
                self._price_cache = {}
                return
            cache = {}
            for row in all_values[3:]:
                if len(row) > 1 and row[1].strip():
                    sym = row[1].strip().upper()
                    if len(row) > latest_col_idx and row[latest_col_idx].strip():
                        try:
                            raw = row[latest_col_idx].replace(",", "").replace(".", "").replace(" ", "")
                            cache[sym] = float(raw)
                        except ValueError:
                            pass
            self._price_cache = cache
            self._price_cache_ts = time.time()
        except Exception:
            self._price_cache = {}

    def get_all_symbols(self) -> list:
        df = self._ws_to_df("BuyLots")
        if df.empty:
            return []
        return sorted(df["symbol"].dropna().unique().tolist())
