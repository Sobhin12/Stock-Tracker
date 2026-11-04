"""FastAPI app: refresh data from NSE/BSE into the workbook, serve charts and the file."""
import threading
from datetime import date, datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import excel_store as store
import storage
from config import BASE_DIR, COMPANIES, START_DATE, XLSX_PATH
from fetchers.bse import fetch_bse
from fetchers.nse import fetch_nse

IST = timezone(timedelta(hours=5, minutes=30))
app = FastAPI(title="Stock Trading Snapshot")
_lock = threading.Lock()


def today_ist() -> date:
    return datetime.now(IST).date()


def refresh() -> dict:
    """Fetch everything after the workbook's latest date up to today and rebuild it."""
    today = today_ist()
    data = store.load_data()
    last = store.last_dates(data)
    result = {sym: {"nse": {}, "bse": {}} for sym in COMPANIES}
    changed = False

    for sym in COMPANIES:
        start = last[sym]["nse"] + timedelta(days=1) if last[sym]["nse"] else START_DATE
        if start > today:
            result[sym]["nse"] = {"status": "up to date", "added": 0}
            continue
        try:
            rows = fetch_nse(sym, start, today)
            data[sym]["nse"] = store.merge(data[sym]["nse"], rows, 2)
            result[sym]["nse"] = {"status": "ok", "added": len(rows)}
            changed |= bool(rows)
        except Exception as e:  # one failure shouldn't stop the others
            result[sym]["nse"] = {"status": "error", "error": str(e), "added": 0}

    bse_starts = {}
    for sym, info in COMPANIES.items():
        start = last[sym]["bse"] + timedelta(days=1) if last[sym]["bse"] else START_DATE
        if start > today:
            result[sym]["bse"] = {"status": "up to date", "added": 0}
        else:
            bse_starts[info["bse_code"]] = start
    if bse_starts:
        try:
            by_code = fetch_bse(bse_starts, today)
            for sym, info in COMPANIES.items():
                if info["bse_code"] in by_code:
                    rows = by_code[info["bse_code"]]
                    data[sym]["bse"] = store.merge(data[sym]["bse"], rows, 0)
                    result[sym]["bse"] = {"status": "ok", "added": len(rows)}
                    changed |= bool(rows)
        except Exception as e:
            for sym, info in COMPANIES.items():
                if info["bse_code"] in bse_starts:
                    result[sym]["bse"] = {"status": "error", "error": str(e), "added": 0}

    if changed or not XLSX_PATH.exists():
        store.save(data)
    return {"today": today.isoformat(), "updated": changed, "companies": result,
            "last_dates": _iso(store.last_dates(data))}


def _iso(last):
    return {s: {k: v.isoformat() if v else None for k, v in d.items()} for s, d in last.items()}


@app.get("/api/companies")
def companies():
    data = store.load_data()
    last = store.last_dates(data)
    out = []
    for sym, info in COMPANIES.items():
        nse_rows = data[sym]["nse"]
        out.append({
            "symbol": sym, "name": info["name"], "bse_code": info["bse_code"],
            "last_nse": last[sym]["nse"].isoformat() if last[sym]["nse"] else None,
            "last_bse": last[sym]["bse"].isoformat() if last[sym]["bse"] else None,
            "last_close": nse_rows[-1][8] if nse_rows else None,
            "prev_close": nse_rows[-1][3] if nse_rows else None,
        })
    return {"companies": out, "today": today_ist().isoformat(), "has_file": XLSX_PATH.exists()}


@app.get("/api/chart/{sym}")
def chart(sym: str, exchange: str = "nse", month: str | None = None):
    sym = sym.upper()
    if sym not in COMPANIES or exchange not in ("nse", "bse"):
        raise HTTPException(404, "Unknown company or exchange")
    rows = store.load_data()[sym][exchange]
    # Column indexes of date, high, low, close, average in each sheet layout
    di, hi, li, ci, ai = (2, 5, 6, 8, 9) if exchange == "nse" else (0, 2, 3, 4, 5)
    months = sorted({r[di].strftime("%Y-%m") for r in rows})
    if not months:
        return {"months": [], "month": None, "labels": [], "high": [], "low": [], "close": [], "avg": []}
    month = month if month in months else months[-1]
    sel = [r for r in rows if r[di].strftime("%Y-%m") == month]
    rnd = lambda v: round(v, 2) if isinstance(v, (int, float)) else None
    return {
        "months": months, "month": month,
        "labels": [r[di].strftime("%d-%b") for r in sel],
        "high": [rnd(r[hi]) for r in sel], "low": [rnd(r[li]) for r in sel],
        "close": [rnd(r[ci]) for r in sel], "avg": [rnd(r[ai]) for r in sel],
        "avg_label": "Average Price" if exchange == "nse" else "WAP",
    }


@app.post("/api/refresh")
def do_refresh():
    if not _lock.acquire(blocking=False):
        raise HTTPException(409, "A refresh is already running")
    try:
        return refresh()
    finally:
        _lock.release()


@app.get("/api/download")
def download():
    storage.pull(XLSX_PATH)
    if not XLSX_PATH.exists():
        raise HTTPException(404, "Workbook not created yet - click Refresh first")
    return FileResponse(
        XLSX_PATH, filename=f"Stock_Trading_Snapshot_{today_ist():%d.%m.%Y}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# Local dev serves the page; on Vercel the CDN serves public/ before reaching the app.
app.mount("/", StaticFiles(directory=BASE_DIR / "public", html=True), name="static")
