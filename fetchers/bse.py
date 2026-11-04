"""BSE daily data from the exchange's public Bhavcopy and delivery files.

These are the same figures the Historical Stock Price page shows (OHLC, shares,
trades, turnover, delivery); WAP is turnover / shares, as on the page.
"""
import csv
import io
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import requests

from config import USER_AGENT

BHAV_URL = "https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{d:%Y%m%d}_F_0000.CSV"
DELIV_URL = "https://www.bseindia.com/BSEDATA/gross/{d:%Y}/SCBSEALL{d:%d%m}.zip"
HEADERS = {"User-Agent": USER_AGENT, "Referer": "https://www.bseindia.com/"}

# Column order matches the "BSE Data" sheet of the sample workbook.
COLUMNS = [
    "Date", "Open Price", "High Price", "Low Price", "Close Price", "WAP", "No.of Shares",
    "No. of Trades", "Total Turnover (Rs.)", "Deliverable Quantity",
    "% Deli. Qty to Traded Qty", "Spread High-Low", "Spread Close-Open",
]


def _get(url: str) -> requests.Response | None:
    for _ in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
        except requests.RequestException:
            continue
        # Non-trading days return the site's HTML page with status 200.
        if r.status_code == 200 and not r.content.lstrip().startswith(b"<"):
            return r
        if r.status_code in (200, 404):
            return None
    raise RuntimeError(f"BSE download failed: {url}")


def _fetch_day(d: date, codes: set[str]) -> dict[str, list]:
    bhav = _get(BHAV_URL.format(d=d))
    if bhav is None:
        return {}
    deliv: dict[str, tuple[float, float]] = {}
    z = _get(DELIV_URL.format(d=d))
    if z is not None:
        with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
            for line in zf.read(zf.namelist()[0]).decode().splitlines()[1:]:
                p = line.split("|")
                if len(p) >= 7 and p[1] in codes:
                    deliv[p[1]] = (int(p[2]), float(p[6]))
    out = {}
    for rec in csv.DictReader(io.StringIO(bhav.text)):
        code = rec["FinInstrmId"]
        if code not in codes:
            continue
        o, h, l, c = (float(rec[k]) for k in ("OpnPric", "HghPric", "LwPric", "ClsPric"))
        qty, turnover = int(rec["TtlTradgVol"]), float(rec["TtlTrfVal"])
        dq, dp = deliv.get(code, (None, None))
        out[code] = [
            d, o, h, l, c, turnover / qty if qty else None, qty, int(rec["TtlNbOfTxsExctd"]),
            turnover, dq, dp, round(h - l, 2), round(c - o, 2),
        ]
    return out


def fetch_bse(starts: dict[str, date], end: date) -> dict[str, list[list]]:
    """starts: {bse_code: first date needed}. Returns {bse_code: rows oldest first}."""
    if not starts:
        return {}
    days = []
    d = min(starts.values())
    # Weekends included: exchanges occasionally trade on a Saturday (e.g. Budget day).
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    codes = set(starts)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda day: (day, _fetch_day(day, codes)), days))
    out: dict[str, list[list]] = {c: [] for c in codes}
    for day, by_code in sorted(results, key=lambda x: x[0]):
        for code, row in by_code.items():
            if day >= starts[code]:
                out[code].append(row)
    return out
