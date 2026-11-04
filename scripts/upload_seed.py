"""Upload the locally built workbook to Vercel Blob so the deployment starts with full history.

    BLOB_READ_WRITE_TOKEN=... venv/Scripts/python.exe scripts/upload_seed.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import storage  # noqa: E402
from config import XLSX_PATH  # noqa: E402

if not storage.enabled():
    sys.exit("Set BLOB_READ_WRITE_TOKEN first (Vercel dashboard > Storage > your Blob store).")
if not XLSX_PATH.exists():
    sys.exit(f"{XLSX_PATH} not found - run a refresh locally first.")
storage.push(XLSX_PATH)
print(f"Uploaded {XLSX_PATH.name} ({XLSX_PATH.stat().st_size:,} bytes) to Vercel Blob.")
