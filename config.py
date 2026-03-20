"""
config.py — đọc credentials từ nhiều nguồn theo thứ tự ưu tiên:
  1. Streamlit secrets (st.secrets)  → dùng khi deploy Streamlit Cloud
  2. File .env local                 → dùng khi chạy local (python-dotenv)
  3. Fallback: trả về None           → app sẽ hiển thị form nhập thủ công
"""
import os
import json
import tempfile

def get_config() -> dict:
    """
    Returns:
        {
          "key_path":        str | None,  # path tới file JSON tạm
          "data_sheet_id":   str | None,
          "price_sheet_id":  str | None,
          "source":          str           # "secrets" | "env" | "manual"
        }
    """
    # ── 1. Thử Streamlit secrets ──────────────────────────────────────────────
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            key_path = _write_temp_json(dict(st.secrets["gcp_service_account"]))
            return {
                "key_path":       key_path,
                "data_sheet_id":  st.secrets.get("DATA_SHEET_ID",  ""),
                "price_sheet_id": st.secrets.get("PRICE_SHEET_ID", ""),
                "source":         "secrets"
            }
    except Exception:
        pass

    # ── 2. Thử .env file ─────────────────────────────────────────────────────
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # python-dotenv không bắt buộc

    key_path_env  = os.environ.get("GCP_KEY_PATH", "")
    data_sheet    = os.environ.get("DATA_SHEET_ID", "")
    price_sheet   = os.environ.get("PRICE_SHEET_ID", "")
    gcp_json_str  = os.environ.get("GCP_SERVICE_ACCOUNT_JSON", "")

    if gcp_json_str:
        try:
            key_path = _write_temp_json(json.loads(gcp_json_str))
            return {
                "key_path":       key_path,
                "data_sheet_id":  data_sheet,
                "price_sheet_id": price_sheet,
                "source":         "env"
            }
        except Exception:
            pass

    if key_path_env and os.path.exists(key_path_env):
        return {
            "key_path":       key_path_env,
            "data_sheet_id":  data_sheet,
            "price_sheet_id": price_sheet,
            "source":         "env"
        }

    # ── 3. Không tìm thấy → dùng manual form ─────────────────────────────────
    return {
        "key_path":       None,
        "data_sheet_id":  None,
        "price_sheet_id": None,
        "source":         "manual"
    }


def _write_temp_json(data: dict) -> str:
    """Ghi dict ra file JSON tạm, trả về đường dẫn."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(data, f)
        return f.name
