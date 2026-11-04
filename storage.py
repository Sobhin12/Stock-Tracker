"""Where the workbook lives.

Locally it is just a file on disk. On Vercel the filesystem is temporary, so when
BLOB_READ_WRITE_TOKEN is set the workbook is kept in Vercel Blob: pull() copies the
latest version to the local path before reading, push() uploads it after a save.
"""
import os
from pathlib import Path

import requests

BLOB_API = os.environ.get("BLOB_API_URL", "https://blob.vercel-storage.com")
BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN")
ACCESS = os.environ.get("BLOB_ACCESS", "private")  # must match the store's setting
PATHNAME ="Stock_Trading_Snapshot.xlsx"
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_pulled_version: str | None = None  # uploadedAt of the copy currently on disk


def enabled() -> bool:
    return bool(BLOB_TOKEN)


def _headers(**extra) -> dict:
    return {"authorization": f"Bearer {BLOB_TOKEN}", "x-api-version": "7", **extra}


def _find() -> dict | None:
    r = requests.get(BLOB_API, params={"prefix": PATHNAME, "limit": 10}, headers=_headers(), timeout=30)
    r.raise_for_status()
    blobs = [b for b in r.json().get("blobs", []) if b["pathname"] == PATHNAME]
    return max(blobs, key=lambda b: b["uploadedAt"]) if blobs else None


def pull(path: Path) -> None:
    """Make path hold the latest stored workbook (no-op without Blob)."""
    global _pulled_version
    if not enabled():
        return
    blob = _find()
    if blob is None:
        return
    if blob["uploadedAt"] == _pulled_version and path.exists():
        return
    # The version in the query string keeps the CDN from serving an older copy.
    r = requests.get(blob["url"], params={"v": blob["uploadedAt"]}, headers=_headers(), timeout=60)
    r.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    _pulled_version = blob["uploadedAt"]


def push(path: Path) -> None:
    """Upload path as the stored workbook (no-op without Blob)."""
    global _pulled_version
    if not enabled():
        return
    r = requests.put(
        f"{BLOB_API}/{PATHNAME}", data=path.read_bytes(), timeout=120,
        headers=_headers(**{
            "x-vercel-blob-access": ACCESS,
            "x-content-type": XLSX_TYPE, "x-add-random-suffix": "0",
            "x-allow-overwrite": "1", "x-cache-control-max-age": "60",
        }),
    )
    if not r.ok:
        raise RuntimeError(f"Blob upload failed: {r.status_code} {r.text}")
    _pulled_version = None  # re-check uploadedAt on the next pull
