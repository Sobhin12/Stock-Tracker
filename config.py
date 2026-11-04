import os
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# On Vercel only /tmp is writable; the durable copy lives in Vercel Blob (see storage.py).
DATA_DIR = Path("/tmp") if os.environ.get("VERCEL") else BASE_DIR / "data"
XLSX_PATH = DATA_DIR / "Stock_Trading_Snapshot.xlsx"

# First date to backfill when a company has no data in the workbook yet.
START_DATE = date(2024, 11, 1)

# NSE symbol -> display name and BSE scrip code
COMPANIES = {
    "NIVABUPA": {"name": "Niva Bupa", "bse_code": "544286"},
    "STARHEALTH": {"name": "Star Health", "bse_code": "543412"},
    "ICICIGI": {"name": "ICICI Lombard", "bse_code": "540716"},
    "GODIGIT": {"name": "Go Digit", "bse_code": "544179"},
}

NSE_URL = "https://www.nseindia.com/report-detail/eq_security"
BSE_URL = "https://www.bseindia.com/markets/equity/EQReports/StockPrcHistori.html?flag=0"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
