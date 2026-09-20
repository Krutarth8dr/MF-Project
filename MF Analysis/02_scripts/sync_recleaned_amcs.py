"""
Synchronize freshly re-cleaned AMCs to Supabase fund_holdings table.
For each updated AMC:
1. Deletes existing rows from Supabase
2. Uploads the cleaned records in batches of 2,500
3. Verifies exact row count parity

Finally, audits all 26 AMCs to confirm 100.00% parity across the entire database.
"""

import sys
import os
import time
import math
from pathlib import Path
import pandas as pd
import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

# Ensure UTF-8 output
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent

for env_path in [PROJECT_ROOT / ".env", WORKSPACE_ROOT / ".env", Path(".env")]:
    if env_path.exists():
        load_dotenv(env_path)
        break

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERROR: Missing SUPABASE_URL or SUPABASE_KEY in .env")
    sys.exit(1)

SUPABASE_HOST = SUPABASE_URL.replace("https://", "").replace("http://", "").strip("/")
API_URL = f"https://{SUPABASE_HOST}/rest/v1"

MATRIX_FILE = PROJECT_ROOT / "05_matrix" / "MASTER" / "matrix_all_amc_funds_quantity_long.xlsx"

# The 8 AMCs that were re-cleaned and need resync
TARGET_AMCS = [
    "ABSL",
    "AXIS",
    "BAJAJ Finserv MF",
    "Bandhan MF",
    "DSP Mutual Fund",
    "Edelweiss Mutual Fund",
    "Sundaram MF",
    "WhiteOak MF"
]

FUND_HOLDINGS_VALID_COLUMNS = [
    "amc",
    "security_name",
    "isin",
    "portfolio_date",
    "month",
    "industry_rating",
    "fund_name",
    "quantity"
]

def create_http_session() -> requests.Session:
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST", "GET", "DELETE"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def get_amc_count(session: requests.Session, amc: str) -> int:
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "count=exact"
    }
    encoded_amc = requests.utils.quote(amc)
    url = f"{API_URL}/fund_holdings?select=id&amc=eq.{encoded_amc}&limit=1"
    r = session.get(url, headers=headers, timeout=30)
    cr = r.headers.get("content-range", "*/0")
    if "/" in cr:
        return int(cr.split("/")[-1])
    return 0

def delete_amc_records(session: requests.Session, amc: str) -> bool:
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "count=exact"
    }
    encoded_amc = requests.utils.quote(amc)
    url = f"{API_URL}/fund_holdings?amc=eq.{encoded_amc}"
    print(f"   🗑️ Deleting existing records for '{amc}' from Supabase...")
    r = session.delete(url, headers=headers, timeout=60)
    if r.status_code in [200, 204]:
        count = get_amc_count(session, amc)
        print(f"      Deleted. Remaining count: {count}")
        return count == 0
    else:
        print(f"      ❌ DELETE failed with status {r.status_code}: {r.text[:200]}")
        return False

def upload_records(session: requests.Session, records: list, amc: str, batch_size: int = 2500) -> bool:
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    url = f"{API_URL}/fund_holdings?on_conflict=amc,fund_name,isin,portfolio_date,security_name"
    total_records = len(records)
    total_batches = math.ceil(total_records / batch_size)
    print(f"   📤 Uploading {total_records:,} records in {total_batches} batch(es)...")
    start_t = time.time()
    uploaded = 0

    for i in range(0, total_records, batch_size):
        batch = records[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        b_start = time.time()
        r = session.post(url, headers=headers, json=batch, timeout=60)
        if r.status_code in [200, 201]:
            uploaded += len(batch)
            pct = (uploaded / total_records) * 100
            print(f"      Batch {batch_num:>2}/{total_batches} | {uploaded:>6,}/{total_records:,} ({pct:5.1f}%) | in {time.time() - b_start:.2f}s")
        else:
            print(f"      ❌ Batch {batch_num} failed ({r.status_code}): {r.text[:200]}")
            return False

    print(f"   ✅ Finished '{amc}' in {time.time() - start_t:.1f}s")
    return True

def main():
    print("=" * 70)
    print("🔄 SYNC RE-CLEANED AMCS TO SUPABASE")
    print("=" * 70)

    # 1. Load local matrix once
    print(f"\n📂 Loading local master matrix: {MATRIX_FILE.name} ...")
    t0 = time.time()
    df = pd.read_excel(MATRIX_FILE)
    print(f"   Loaded {len(df):,} rows in {time.time() - t0:.1f}s")

    # Standardize columns
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    existing_cols = [c for c in FUND_HOLDINGS_VALID_COLUMNS if c in df.columns]
    df = df[existing_cols].copy()

    if "quantity" in df.columns:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype("int64")
    if "portfolio_date" in df.columns:
        df["portfolio_date"] = df["portfolio_date"].astype(str).str.strip()
    for str_col in ["amc", "security_name", "isin", "month", "industry_rating", "fund_name"]:
        if str_col in df.columns:
            df[str_col] = df[str_col].astype(str).str.strip()
            df[str_col] = df[str_col].replace({"nan": None, "None": None, "": None, "NaT": None})
    df = df.replace({np.nan: None})

    session = create_http_session()

    # 2. Process each target AMC
    for amc in TARGET_AMCS:
        print(f"\n[{amc}]")
        amc_df = df[df["amc"] == amc]
        local_count = len(amc_df)
        supa_count_before = get_amc_count(session, amc)
        print(f"   Local rows: {local_count:,} | Supabase rows: {supa_count_before:,}")

        # Delete existing in Supabase
        if not delete_amc_records(session, amc):
            print(f"   ❌ Aborting sync for {amc} due to delete failure")
            continue

        # Upload clean records
        records = amc_df.to_dict("records")
        if not upload_records(session, records, amc, batch_size=2500):
            print(f"   ❌ Upload failed for {amc}")
            continue

        # Verify
        supa_count_after = get_amc_count(session, amc)
        if supa_count_after == local_count:
            print(f"   🎯 VERIFIED: Exact parity achieved for {amc}! ({supa_count_after:,} rows)")
        else:
            print(f"   ⚠️ MISMATCH for {amc}: Local={local_count:,}, Supabase={supa_count_after:,} (Diff: {supa_count_after - local_count})")

    # 3. Final Audit across all 26 AMCs
    print("\n" + "=" * 70)
    print("📊 FINAL AUDIT ACROSS ALL 26 AMCS")
    print("=" * 70)
    all_local_counts = df["amc"].value_counts().to_dict()
    total_local = len(df)
    total_supa = 0
    all_match = True

    for amc_name in sorted(all_local_counts.keys()):
        loc = all_local_counts[amc_name]
        supa = get_amc_count(session, amc_name)
        total_supa += supa
        diff = supa - loc
        if diff == 0:
            status = "✅ MATCH"
        else:
            status = f"❌ DIFF ({diff:+d})"
            all_match = False
        print(f"   {amc_name:<28}: Local = {loc:>6,} | Supabase = {supa:>6,} | {status}")

    print("=" * 70)
    print(f"   TOTAL ROWS: Local = {total_local:,} | Supabase = {total_supa:,} | Diff = {total_supa - total_local}")
    if all_match and total_supa == total_local:
        print("🎉 100.00% EXACT PARITY CONFIRMED ACROSS ALL 26 AMCS!")
    else:
        print("⚠️ SOME DISCREPANCIES REMAIN.")
    print("=" * 70)

if __name__ == "__main__":
    main()
