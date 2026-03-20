"""
chart_engine.py — tính toán dữ liệu cho 3 charts:
  Chart 1: Hành trình đầu tư theo tháng (bar + line)
  Chart 2: Lợi nhuận ghi nhận hàng tháng theo tài khoản (stacked bar + line cộng dồn)
  Chart 3: Tiền mặt theo tài khoản (bar + % line)
"""

import pandas as pd
import numpy as np
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from sheets_manager import SheetsManager


class ChartEngine:
    def __init__(self, sm: SheetsManager):
        self.sm = sm

    # ─────────────────────────────────────────────────────────────────────────
    # CHART 1: Hành trình đầu tư
    # ─────────────────────────────────────────────────────────────────────────
    def get_chart1_data(self, account: str, year: int) -> pd.DataFrame:
        """
        Trả về DataFrame theo tháng trong năm `year` với các cột:
          month        : "YYYY-MM"
          invested     : Tổng giá trị mua của các lô CÒN nắm giữ tại cuối tháng đó
          market_value : Giá trị thị trường tại cuối tháng (dùng giá hiện tại gần nhất)
          realized_pnl : Lợi nhuận đã ghi nhận TRONG năm đó (cộng dồn đến tháng)
          dividend     : Cổ tức đã nhận trong năm (cộng dồn đến tháng)
        Logic reset đầu năm:
          - realized_pnl: reset về 0 mỗi đầu năm, chỉ tính giao dịch bán trong năm
          - invested: = tổng giá trị mua của lô còn nắm giữ tại thời điểm cuối tháng
        """
        lots_df    = self.sm.get_buy_lots(account if account != "Tất cả" else None)
        matches_df = self.sm.get_sell_matches(account if account != "Tất cả" else None)
        cash_df    = self.sm._ws_to_df("CashLedger")

        months = self._months_of_year(year)
        rows = []

        for month_str in months:
            month_end = self._month_end(month_str)
            if month_end > date.today():
                break

            # ── Tiền đầu tư: tổng cost của lô còn mở tại cuối tháng ──────────
            invested = self._invested_at(lots_df, matches_df, account, month_end)

            # ── Giá trị thị trường tại cuối tháng ────────────────────────────
            # Dùng giá hiện tại (snapshot tốt nhất có thể)
            open_lots = self._open_lots_at(lots_df, matches_df, account, month_end)
            market_val = 0.0
            if not open_lots.empty:
                for sym, grp in open_lots.groupby("symbol"):
                    price = self.sm.get_latest_price(sym)
                    market_val += grp["quantity_remaining"].astype(float).sum() * price

            # ── Cổ tức tích lũy trong năm đến cuối tháng ─────────────────────
            dividend = self._dividend_ytd(cash_df, account, year, month_end)

            # ── Lợi nhuận ghi nhận trong năm đến cuối tháng ──────────────────
            realized = self._realized_pnl_ytd(matches_df, account, year, month_end)

            rows.append({
                "month":        month_str,
                "invested":     invested,
                "market_value": market_val + dividend,
                "realized_pnl": realized,
            })

        return pd.DataFrame(rows)

    # ─────────────────────────────────────────────────────────────────────────
    # CHART 2: Lợi nhuận hàng tháng theo tài khoản
    # ─────────────────────────────────────────────────────────────────────────
    def get_chart2_data(self, year: int) -> pd.DataFrame:
        """
        Trả về DataFrame với:
          month        : "YYYY-MM"
          account      : tên tài khoản
          monthly_pnl  : lợi nhuận ghi nhận trong tháng đó (bán + cổ tức)
          cumulative   : cộng dồn từ đầu năm đến tháng (reset đầu năm)
        """
        matches_df = self.sm.get_sell_matches()
        cash_df    = self.sm._ws_to_df("CashLedger")
        accounts   = [a["name"] for a in self.sm.get_accounts()]

        if not accounts:
            return pd.DataFrame()

        months = self._months_of_year(year)
        rows = []

        for acc in accounts:
            cum = 0.0
            for month_str in months:
                m_start = datetime.strptime(month_str, "%Y-%m").date().replace(day=1)
                m_end   = self._month_end(month_str)
                if m_end > date.today():
                    break

                # Lợi nhuận bán trong tháng
                pnl = self._realized_pnl_in_range(matches_df, acc, m_start, m_end)
                # Cổ tức trong tháng
                div = self._dividend_in_range(cash_df, acc, m_start, m_end)
                monthly = pnl + div

                cum += monthly
                rows.append({
                    "month":       month_str,
                    "account":     acc,
                    "monthly_pnl": monthly,
                    "cumulative":  cum,
                })

        return pd.DataFrame(rows)

    # ─────────────────────────────────────────────────────────────────────────
    # CHART 3: Tiền mặt theo tài khoản
    # ─────────────────────────────────────────────────────────────────────────
    def get_chart3_data(self) -> pd.DataFrame:
        """
        Trả về DataFrame với:
          account       : tên tài khoản
          cash          : số dư tiền mặt hiện tại
          market_value  : giá trị CK đang nắm giữ
          total_value   : cash + market_value
          cash_pct      : % tiền mặt / tổng
        """
        accounts = self.sm.get_accounts()
        if not accounts:
            return pd.DataFrame()

        rows = []
        for acc in accounts:
            acc_name = acc["name"]

            # Tiền mặt
            cash = self.sm.get_cash_balance(acc_name)

            # Giá trị danh mục
            lots_df    = self.sm.get_buy_lots(acc_name)
            matches_df = self.sm.get_sell_matches(acc_name)
            open_lots  = self._open_lots_at(lots_df, matches_df, acc_name, date.today())
            market_val = 0.0
            if not open_lots.empty:
                for sym, grp in open_lots.groupby("symbol"):
                    price = self.sm.get_latest_price(sym)
                    market_val += grp["quantity_remaining"].astype(float).sum() * price

            total = cash + market_val
            rows.append({
                "account":      acc_name,
                "cash":         cash,
                "market_value": market_val,
                "total_value":  total,
                "cash_pct":     (cash / total * 100) if total > 0 else 0,
            })

        return pd.DataFrame(rows)

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
    def _months_of_year(self, year: int) -> list:
        return [f"{year}-{m:02d}" for m in range(1, 13)]

    def _month_end(self, month_str: str) -> date:
        d = datetime.strptime(month_str, "%Y-%m").date()
        next_m = d + relativedelta(months=1)
        return next_m - relativedelta(days=1)

    def _open_lots_at(self, lots_df: pd.DataFrame, matches_df: pd.DataFrame,
                      account: str, as_of: date) -> pd.DataFrame:
        """Các lô mua còn mở tại ngày as_of."""
        if lots_df.empty:
            return pd.DataFrame()

        df = lots_df.copy()
        if account and account != "Tất cả":
            df = df[df["account"] == account]

        df["buy_date"] = pd.to_datetime(df["buy_date"], errors="coerce").dt.date
        df = df[df["buy_date"] <= as_of].copy()
        if df.empty:
            return df

        df["quantity_original"]  = pd.to_numeric(df["quantity_original"],  errors="coerce").fillna(0)
        df["quantity_remaining"] = df["quantity_original"].copy()

        # Trừ đi các lượng đã bán trước as_of
        if not matches_df.empty:
            m = matches_df.copy()
            m["sell_date"] = pd.to_datetime(m["sell_date"], errors="coerce").dt.date
            m = m[m["sell_date"] <= as_of]
            for _, row in m.iterrows():
                mask = df["lot_id"] == row["lot_id"]
                if mask.any():
                    sold = pd.to_numeric(row["quantity"], errors="coerce") or 0
                    df.loc[mask, "quantity_remaining"] -= sold

        df["quantity_remaining"] = df["quantity_remaining"].clip(lower=0)
        return df[df["quantity_remaining"] > 0]

    def _invested_at(self, lots_df, matches_df, account, as_of: date) -> float:
        """Tổng chi phí (giá mua + phí phân bổ) của các lô còn mở tại as_of."""
        open_lots = self._open_lots_at(lots_df, matches_df, account, as_of)
        if open_lots.empty:
            return 0.0
        open_lots["buy_price"] = pd.to_numeric(open_lots["buy_price"], errors="coerce").fillna(0)
        open_lots["buy_fee"]   = pd.to_numeric(open_lots["buy_fee"],   errors="coerce").fillna(0)
        open_lots["qty_orig"]  = pd.to_numeric(open_lots["quantity_original"], errors="coerce").fillna(1)
        open_lots["fee_ps"]    = open_lots["buy_fee"] / open_lots["qty_orig"]
        open_lots["cost"]      = open_lots["quantity_remaining"] * (open_lots["buy_price"] + open_lots["fee_ps"])
        return float(open_lots["cost"].sum())

    def _realized_pnl_ytd(self, matches_df, account, year, as_of: date) -> float:
        if matches_df.empty:
            return 0.0
        m = matches_df.copy()
        if account and account != "Tất cả":
            m = m[m["account"] == account]
        m["sell_date"] = pd.to_datetime(m["sell_date"], errors="coerce").dt.date
        year_start = date(year, 1, 1)
        m = m[(m["sell_date"] >= year_start) & (m["sell_date"] <= as_of)]
        if m.empty:
            return 0.0
        return float(pd.to_numeric(m["realized_pnl"], errors="coerce").fillna(0).sum())

    def _realized_pnl_in_range(self, matches_df, account, start: date, end: date) -> float:
        if matches_df.empty:
            return 0.0
        m = matches_df.copy()
        if account:
            m = m[m["account"] == account]
        m["sell_date"] = pd.to_datetime(m["sell_date"], errors="coerce").dt.date
        m = m[(m["sell_date"] >= start) & (m["sell_date"] <= end)]
        return float(pd.to_numeric(m["realized_pnl"], errors="coerce").fillna(0).sum())

    def _dividend_ytd(self, cash_df, account, year, as_of: date) -> float:
        if cash_df.empty:
            return 0.0
        df = cash_df.copy()
        if account and account != "Tất cả":
            df = df[df["account"] == account]
        df = df[df["type"] == "Cổ tức"]
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        year_start = date(year, 1, 1)
        df = df[(df["date"] >= year_start) & (df["date"] <= as_of)]
        return float(pd.to_numeric(df["amount"], errors="coerce").fillna(0).sum())

    def _dividend_in_range(self, cash_df, account, start: date, end: date) -> float:
        if cash_df.empty:
            return 0.0
        df = cash_df.copy()
        if account:
            df = df[df["account"] == account]
        df = df[df["type"] == "Cổ tức"]
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        return float(pd.to_numeric(df["amount"], errors="coerce").fillna(0).sum())

    def get_available_years(self) -> list:
        """Lấy danh sách năm có giao dịch."""
        txn_df = self.sm.get_transactions()
        if txn_df.empty:
            return [date.today().year]
        txn_df["date"] = pd.to_datetime(txn_df["date"], errors="coerce")
        years = sorted(txn_df["date"].dt.year.dropna().unique().astype(int).tolist(), reverse=True)
        if not years:
            return [date.today().year]
        return years
