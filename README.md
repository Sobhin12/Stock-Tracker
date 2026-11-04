# Stock Trading Snapshot

Pulls daily trading data for NIVABUPA, STARHEALTH, ICICIGI and GODIGIT from NSE and BSE,
appends it to `Stock_Trading_Snapshot.xlsx` (Summary / NSE / BSE sheets per company with
charts, laid out like the original Niva Bupa snapshot) and shows NSE and BSE charts in a web page.

## Run locally

```bash
venv/Scripts/python.exe -m pip install -r requirements.txt
venv/Scripts/python.exe -m uvicorn app:app --port 8000
```

Open http://localhost:8000. The workbook is kept at `data/Stock_Trading_Snapshot.xlsx`.

- **Refresh** – if the latest date in the Excel is before today, fetches the missing days
  (first run backfills from 1 Nov 2024, ~10 minutes), updates the Excel and the charts.
- **Download Excel** – downloads the workbook.

## Deploy to Vercel

Vercel functions have no permanent disk, so the workbook is stored in **Vercel Blob**
(`storage.py`); the app copies it to `/tmp` to read and uploads it after each refresh.

1. Push this folder to a Git repo and import it in Vercel (or run `vercel link` here).
2. In the project: **Storage → Create → Blob**, connect it to the project. This adds
   `BLOB_READ_WRITE_TOKEN` to the environment variables.
3. Upload the locally built workbook once, so the site starts with full history
   (the 10-minute backfill is too long for a serverless request):
   ```bash
   BLOB_READ_WRITE_TOKEN=<token> venv/Scripts/python.exe scripts/upload_seed.py
   ```
4. Deploy: `vercel --prod` (or push to the connected branch).
5. Open the site and click **Refresh** – it only fetches the days since the last date.

`vercel.json` runs the function in Mumbai (`bom1`) with a 300 s limit; static files in `public/`
are served by Vercel's CDN and `/api/*` goes to `api/index.py`.

**Caveat:** NSE and BSE sit behind Akamai, which can block requests from cloud servers.
If Refresh on Vercel reports NSE/BSE errors, run the refresh from a machine in India
(locally, or a scheduled job) with `BLOB_READ_WRITE_TOKEN` set — it uploads to the same
Blob — and use the Vercel site for viewing and downloading.

## Sources

- NSE: Security-wise Archives report (`report-detail/eq_security`) – price, volume & deliverable data.
- BSE: the exchange's public daily Bhavcopy (OHLC, shares, trades, turnover) and delivery files
  (`BSEDATA/gross`) – the same figures the Historical Stock Price page shows; WAP = turnover / shares.
  The Historical Stock Price page's own API rejects non-browser clients, so it isn't called directly.

Companies, BSE scrip codes and the backfill start date are in `config.py`.
