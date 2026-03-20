import pandas as pd
import numpy as np
from datetime import datetime
from sheets_manager import SheetsManager


class PortfolioLogic:
    def __init__(self, sm: SheetsManager):
        self.sm = sm

    # =========================================================
    # ADD TRANSACTION - Main entry point
    # =========================================================
    def add_transaction(self, data: dict) -> str:
        """Process and save a transaction. Returns status message."""
        txn_type = data["type"]
        account = data["account"]

        if txn_type == "Mua":
            return self._process_buy(data)
        elif txn_type == "Bán":
            return self._process_sell(data)
        elif txn_type == "Cổ tức tiền mặt":
            return self._process_cash_dividend(data)
        elif txn_type == "Cổ tức cổ phiếu":
            return self._process_stock_dividend(data)
        elif txn_type in ["Phí quản lý TK", "Phí lưu ký", "Phí margin", "Phí ứng trước", "Phí khác"]:
            return self._process_fee(data)
        elif txn_type == "Nộp tiền":
            return self._process_deposit(data)
        elif txn_type == "Rút tiền":
            return self._process_withdrawal(data)
        else:
            raise ValueError(f"Loại giao dịch không hợp lệ: {txn_type}")

    def _process_buy(self, data: dict) -> str:
        symbol = data["symbol"].upper()
        qty = int(data["quantity"])
        price = float(data["price"])
        fee = float(data.get("fee", 0))
        total_cost = qty * price + fee

        # Save transaction
        txn_id = self.sm.add_transaction({
            **data,
            "symbol": symbol,
            "amount": qty * price,
        })

        # Create buy lot
        lot_id = self.sm.add_buy_lot({
            "account": data["account"],
            "symbol": symbol,
            "buy_date": data["date"],
            "quantity_original": qty,
            "quantity_remaining": qty,
            "buy_price": price,
            "buy_fee": fee,
            "note": data.get("note", ""),
            "txn_id": txn_id
        })

        # Deduct cash
        self.sm.add_cash_entry({
            "account": data["account"],
            "date": data["date"],
            "type": "Mua CP",
            "amount": -total_cost,
            "note": f"Mua {qty} {symbol} @ {price:,.0f} | Lot: {lot_id}"
        })

        return f"✅ Mua {qty} {symbol} @ {price:,.0f} đ | Lô: {lot_id}"

    def _process_sell(self, data: dict) -> str:
        symbol = data["symbol"].upper()
        sell_qty = int(data["quantity"])
        sell_price = float(data["price"])
        sell_fee = float(data.get("fee", 0))
        sell_tax = float(data.get("tax", 0))
        sell_value = sell_qty * sell_price - sell_fee - sell_tax

        # Get FIFO lots
        lots_df = self.sm.get_lots_for_fifo(data["account"], symbol)
        total_available = lots_df["quantity_remaining"].astype(int).sum() if not lots_df.empty else 0

        if total_available < sell_qty:
            raise ValueError(f"Không đủ số lượng {symbol}! Có: {total_available}, Bán: {sell_qty}")

        # Save sell transaction
        txn_id = self.sm.add_transaction({
            **data,
            "symbol": symbol,
            "amount": sell_qty * sell_price,
        })

        # FIFO matching
        remaining_to_sell = sell_qty
        total_buy_cost = 0
        matched_lots = []

        for _, lot in lots_df.iterrows():
            if remaining_to_sell <= 0:
                break
            
            lot_remaining = int(lot["quantity_remaining"])
            matched_qty = min(remaining_to_sell, lot_remaining)
            buy_price = float(lot["buy_price"])
            buy_fee = float(lot["buy_fee"])
            buy_fee_per_share = buy_fee / int(lot["quantity_original"]) if int(lot["quantity_original"]) > 0 else 0

            # Proportional fee allocation
            sell_fee_alloc = sell_fee * (matched_qty / sell_qty)
            sell_tax_alloc = sell_tax * (matched_qty / sell_qty)
            buy_fee_alloc = buy_fee_per_share * matched_qty

            buy_cost = matched_qty * buy_price + buy_fee_alloc
            sell_proceeds = matched_qty * sell_price - sell_fee_alloc - sell_tax_alloc
            pnl = sell_proceeds - buy_cost

            # Record match
            self.sm.add_sell_match({
                "sell_txn_id": txn_id,
                "lot_id": lot["lot_id"],
                "account": data["account"],
                "symbol": symbol,
                "sell_date": data["date"],
                "quantity": matched_qty,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "buy_fee_alloc": round(buy_fee_alloc, 0),
                "sell_fee_alloc": round(sell_fee_alloc, 0),
                "sell_tax_alloc": round(sell_tax_alloc, 0),
                "realized_pnl": round(pnl, 0)
            })

            # Update lot remaining
            new_remaining = lot_remaining - matched_qty
            self.sm.update_lot_remaining(lot["lot_id"], new_remaining)

            total_buy_cost += buy_cost
            remaining_to_sell -= matched_qty
            matched_lots.append(lot["lot_id"])

        total_pnl = sell_qty * sell_price - total_buy_cost - sell_fee - sell_tax

        # Add cash
        self.sm.add_cash_entry({
            "account": data["account"],
            "date": data["date"],
            "type": "Bán CP",
            "amount": sell_value,
            "note": f"Bán {sell_qty} {symbol} @ {sell_price:,.0f}"
        })

        return (f"✅ Bán {sell_qty} {symbol} @ {sell_price:,.0f} đ | "
                f"Lãi/Lỗ: {total_pnl:+,.0f} đ | Khớp {len(matched_lots)} lô")

    def _process_cash_dividend(self, data: dict) -> str:
        amount = float(data.get("amount", 0))
        tax = float(data.get("tax", 0))
        net = amount - tax
        self.sm.add_transaction(data)
        self.sm.add_cash_entry({
            "account": data["account"],
            "date": data["date"],
            "type": "Cổ tức",
            "amount": net,
            "note": f"Cổ tức {data.get('symbol','')} | Thuế: {tax:,.0f}"
        })
        return f"✅ Cổ tức {data.get('symbol','')} | Net: {net:,.0f} đ"

    def _process_stock_dividend(self, data: dict) -> str:
        symbol = data["symbol"].upper()
        qty = int(data["quantity"])
        # Add as buy lot at price 0
        self.sm.add_transaction(data)
        self.sm.add_buy_lot({
            "account": data["account"],
            "symbol": symbol,
            "buy_date": data["date"],
            "quantity_original": qty,
            "quantity_remaining": qty,
            "buy_price": 0,
            "buy_fee": 0,
            "note": f"Cổ tức cổ phiếu"
        })
        return f"✅ Nhận {qty} cổ phiếu {symbol} từ cổ tức"

    def _process_fee(self, data: dict) -> str:
        amount = float(data.get("amount", 0))
        self.sm.add_transaction(data)
        self.sm.add_cash_entry({
            "account": data["account"],
            "date": data["date"],
            "type": data["type"],
            "amount": -amount,
            "note": data.get("note", "")
        })
        return f"✅ Ghi nhận {data['type']}: {amount:,.0f} đ"

    def _process_deposit(self, data: dict) -> str:
        amount = float(data.get("amount", 0))
        self.sm.add_transaction(data)
        self.sm.add_cash_entry({
            "account": data["account"],
            "date": data["date"],
            "type": "Nộp tiền",
            "amount": amount,
            "note": data.get("note", "")
        })
        return f"✅ Nộp tiền: {amount:,.0f} đ"

    def _process_withdrawal(self, data: dict) -> str:
        amount = float(data.get("amount", 0))
        self.sm.add_transaction(data)
        self.sm.add_cash_entry({
            "account": data["account"],
            "date": data["date"],
            "type": "Rút tiền",
            "amount": -amount,
            "note": data.get("note", "")
        })
        return f"✅ Rút tiền: {amount:,.0f} đ"

    # =========================================================
    # PORTFOLIO VIEW
    # =========================================================
    def get_portfolio(self, account: str) -> pd.DataFrame:
        """Get current holdings with market values."""
        lots_df = self.sm.get_buy_lots(account if account != "Tất cả" else None)
        if lots_df.empty:
            return pd.DataFrame()

        # Only open lots
        lots_df["quantity_remaining"] = lots_df["quantity_remaining"].astype(int)
        open_lots = lots_df[lots_df["quantity_remaining"] > 0].copy()
        if open_lots.empty:
            return pd.DataFrame()

        # Aggregate by symbol (and account for "all accounts")
        open_lots["buy_price"] = open_lots["buy_price"].astype(float)
        open_lots["buy_fee"] = open_lots["buy_fee"].astype(float)
        open_lots["quantity_original"] = open_lots["quantity_original"].astype(int)
        open_lots["fee_per_share"] = open_lots.apply(
            lambda r: r["buy_fee"] / r["quantity_original"] if r["quantity_original"] > 0 else 0, axis=1
        )
        open_lots["total_cost"] = open_lots["quantity_remaining"] * (open_lots["buy_price"] + open_lots["fee_per_share"])

        grouped = open_lots.groupby("symbol").agg(
            quantity=("quantity_remaining", "sum"),
            total_cost=("total_cost", "sum")
        ).reset_index()

        grouped["avg_buy_price"] = grouped["total_cost"] / grouped["quantity"]
        grouped["buy_value"] = grouped["total_cost"]

        # Get market prices
        grouped["current_price"] = grouped["symbol"].apply(self.sm.get_latest_price)
        grouped["market_value"] = grouped["quantity"] * grouped["current_price"]
        grouped["unrealized_pnl"] = grouped["market_value"] - grouped["buy_value"]
        grouped["unrealized_pnl_pct"] = (grouped["unrealized_pnl"] / grouped["buy_value"] * 100).round(2)

        # Format prices
        grouped["avg_buy_price"] = grouped["avg_buy_price"].round(0)
        grouped["current_price"] = grouped["current_price"].round(0)

        return grouped[["symbol", "quantity", "avg_buy_price", "current_price",
                         "buy_value", "market_value", "unrealized_pnl", "unrealized_pnl_pct"]]

    def get_summary(self, account: str) -> dict:
        portfolio = self.get_portfolio(account)
        cash = self.sm.get_cash_balance(account)

        if portfolio.empty:
            return {
                "market_value": 0, "total_invested": 0,
                "unrealized_pnl": 0, "unrealized_pnl_pct": 0,
                "cash": cash
            }

        market_value = portfolio["market_value"].sum()
        total_invested = portfolio["buy_value"].sum()
        unrealized_pnl = portfolio["unrealized_pnl"].sum()
        unrealized_pnl_pct = (unrealized_pnl / total_invested * 100) if total_invested > 0 else 0

        return {
            "market_value": market_value,
            "total_invested": total_invested,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
            "cash": cash
        }

    def get_realized_pnl(self, account: str) -> pd.DataFrame:
        df = self.sm.get_sell_matches(account if account != "Tất cả" else None)
        if df.empty:
            return pd.DataFrame()

        df["realized_pnl"] = df["realized_pnl"].astype(float)
        df["quantity"] = df["quantity"].astype(int)
        df["buy_price"] = df["buy_price"].astype(float)
        df["sell_price"] = df["sell_price"].astype(float)

        result = df.rename(columns={
            "symbol": "Mã CP",
            "sell_date": "Ngày bán",
            "quantity": "Số lượng",
            "buy_price": "Giá mua",
            "sell_price": "Giá bán",
            "realized_pnl": "Lợi nhuận",
            "lot_id": "Lô mua"
        })

        cols = ["Mã CP", "Ngày bán", "Số lượng", "Giá mua", "Giá bán", "Lợi nhuận", "Lô mua"]
        cols = [c for c in cols if c in result.columns]
        result = result[cols].sort_values("Ngày bán", ascending=False)
        
        result["Giá mua"] = result["Giá mua"].apply(lambda x: f"{x:,.0f}")
        result["Giá bán"] = result["Giá bán"].apply(lambda x: f"{x:,.0f}")
        result["Lợi nhuận"] = result["Lợi nhuận"].apply(lambda x: f"{x:+,.0f}")

        return result

    def get_transactions(self, account: str, filter_types: list, 
                         filter_symbol: str, date_range) -> pd.DataFrame:
        df = self.sm.get_transactions()
        if df.empty:
            return pd.DataFrame()

        if account != "Tất cả":
            df = df[df["account"] == account]
        if filter_types:
            df = df[df["type"].isin(filter_types)]
        if filter_symbol:
            df = df[df["symbol"].str.upper() == filter_symbol]
        if len(date_range) == 2:
            start, end = date_range
            df["date"] = pd.to_datetime(df["date"])
            df = df[(df["date"].dt.date >= start) & (df["date"].dt.date <= end)]
            df["date"] = df["date"].dt.strftime("%d/%m/%Y")

        df = df.rename(columns={
            "account": "Tài khoản",
            "type": "Loại",
            "date": "Ngày",
            "symbol": "Mã CP",
            "quantity": "Số lượng",
            "price": "Giá",
            "fee": "Phí",
            "tax": "Thuế",
            "amount": "Giá trị",
            "note": "Ghi chú"
        })

        display_cols = ["Ngày", "Tài khoản", "Loại", "Mã CP", "Số lượng", "Giá", "Phí", "Thuế", "Giá trị", "Ghi chú"]
        display_cols = [c for c in display_cols if c in df.columns]
        return df[display_cols].sort_values("Ngày", ascending=False)
