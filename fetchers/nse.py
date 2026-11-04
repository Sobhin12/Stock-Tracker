"""NSE Security-wise Archives (price, volume & deliverable data)."""
import time
from datetime import date, datetime, timedelta

import requests

from config import NSE_URL, USER_AGENT

API = "https://www.nseindia.com/api/historicalOR/generateSecurityWiseHistoricalData"
CHUNK_DAYS = 60

# Column order matches the "NSE Data" sheet of the sample workbook.
COLUMNS = [
    "Symbol", "Series", "Date", "Prev Close", "Open Price", "High Price", "Low Price",
    "Last Price", "Close Price", "Average Price", "Total Traded Quantity", "Turnover ₹",
    "No. of Trades", "Deliverable Qty", "% Dly Qt to Traded Qty",
]
_KEYS = [
    "CH_SYMBOL", "CH_SERIES", "mTIMESTAMP", "CH_PREVIOUS_CLS_PRICE", "CH_OPENING_PRICE",
    "CH_TRADE_HIGH_PRICE", "CH_TRADE_LOW_PRICE", "CH_LAST_TRADED_PRICE", "CH_CLOSING_PRICE",
    "VWAP", "CH_TOT_TRADED_QTY", "CH_TOT_TRADED_VAL", "CH_TOTAL_TRADES", "COP_DELIV_QTY",
    "COP_DELIV_PERC",
]


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    # The API only answers once the report page has set its cookies.
    s.get(NSE_URL, timeout=30).raise_for_status()
    s.headers.update({"Referer": NSE_URL, "Accept": "application/json"})
    return s


def _row(rec: dict) -> list:
    row = [rec.get(k) for k in _KEYS]
    row[2] = datetime.strptime(rec["mTIMESTAMP"], "%d-%b-%Y").date()
    return row


def fetch_nse(symbol: str, start: date, end: date) -> list[list]:
    """Return EQ-series rows for symbol between start and end (inclusive), oldest first."""
    s = _session()
    rows: dict[date, list] = {}
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
        params = {
            "from": cur.strftime("%d-%m-%Y"), "to": chunk_end.strftime("%d-%m-%Y"),
            "symbol": symbol, "type": "priceVolumeDeliverable", "series": "ALL",
        }
        for attempt in range(3):
            r = s.get(API, params=params, timeout=30)
            if r.status_code == 200:
                break
            time.sleep(2 * (attempt + 1))
            s = _session()
        r.raise_for_status()
        for rec in r.json().get("data", []):
            if rec.get("CH_SERIES") == "EQ":
                row = _row(rec)
                rows[row[2]] = row
        cur = chunk_end + timedelta(days=1)
        time.sleep(0.5)
    return [rows[d] for d in sorted(rows)]
