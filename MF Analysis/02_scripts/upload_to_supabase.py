"""
Upload the master long-format quantity matrix and security master table to Supabase.

Tables updated:
1. fund_holdings   - Master fund-level monthly quantity holdings
2. security_master - ISIN-to-security names mapping

Uses the Supabase REST API with HTTP connection pooling and batching for high throughput.
Requires SUPABASE_URL and SUPABASE_KEY in .env (or MF Analysis/.env).
SUPABASE_KEY must be the SERVICE_ROLE key (or key with insert/upsert permissions).
"""

import sys
import os
import time
import math
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

# Windows consoles default to cp1252, force UTF-8 output
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# Locate project roots and .env file
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent

# Try loading .env from MF Analysis or workspace root
env_loaded = False
for env_path in [PROJECT_ROOT / ".env", WORKSPACE_ROOT / ".env", Path(".env")]:
    if env_path.exists():
        load_dotenv(env_path)
        env_loaded = True
        break
if not env_loaded:
    load_dotenv()

MATRIX_FILE = PROJECT_ROOT / "05_matrix" / "MASTER" / "matrix_all_amc_funds_quantity_long.xlsx"
SECURITY_MASTER_FILE = PROJECT_ROOT / "05_matrix" / "MASTER" / "security_master.xlsx"

# Get credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERROR: Missing SUPABASE_URL or SUPABASE_KEY in .env")
    print("Please ensure your .env contains:")
    print("  SUPABASE_URL=your-project-id.supabase.co")
    print("  SUPABASE_KEY=your-service-role-key")
    sys.exit(1)

# Normalize URL
SUPABASE_HOST = SUPABASE_URL.replace("https://", "").replace("http://", "").strip("/")
API_URL = f"https://{SUPABASE_HOST}/rest/v1"

# Allowed schema columns for fund_holdings table
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
    """Create a requests session with connection pooling and automatic retries."""
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


def load_and_prepare_fund_holdings(file_path: Path) -> pd.DataFrame:
    """Load matrix Excel file, clean columns and prepare records for fund_holdings table."""
    print(f"\n📂 Loading matrix file: {file_path.name} ...")
    t0 = time.time()
    df = pd.read_excel(file_path)
    print(f"   Loaded {len(df):,} rows in {time.time() - t0:.1f}s")

    # Standardize column names (lowercase, stripped, underscored)
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]

    # Filter to only valid database columns (drops 'month_sort_date' and any other extras)
    existing_valid_cols = [c for c in FUND_HOLDINGS_VALID_COLUMNS if c in df.columns]
    dropped_cols = [c for c in df.columns if c not in FUND_HOLDINGS_VALID_COLUMNS]
    if dropped_cols:
        print(f"   ℹ️ Ignored non-schema columns: {dropped_cols}")
    df = df[existing_valid_cols].copy()

    # Convert and clean data types
    if "quantity" in df.columns:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype("int64")

    if "portfolio_date" in df.columns:
        df["portfolio_date"] = df["portfolio_date"].astype(str).str.strip()

    for str_col in ["amc", "security_name", "isin", "month", "industry_rating", "fund_name"]:
        if str_col in df.columns:
            df[str_col] = df[str_col].astype(str).str.strip()
            df[str_col] = df[str_col].replace({"nan": None, "None": None, "": None})

    # Drop exact duplicates
    initial_len = len(df)
    df = df.drop_duplicates()
    if len(df) < initial_len:
        print(f"   Deduped: removed {initial_len - len(df):,} duplicate rows ({len(df):,} remaining)")

    # Replace pandas NaN with None for valid JSON serialization
    df = df.replace({np.nan: None})
    return df


def load_and_prepare_security_master(file_path: Path) -> pd.DataFrame:
    """Load security master Excel file, clean columns and prepare records for security_master table."""
    print(f"\n📂 Loading security master file: {file_path.name} ...")
    t0 = time.time()
    df = pd.read_excel(file_path)
    print(f"   Loaded {len(df):,} rows in {time.time() - t0:.1f}s")

    # Standardize column names (e.g., ISIN -> isin, Name_1 -> name_1)
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]

    # Keep only isin and name_* columns
    valid_cols = [c for c in df.columns if c == "isin" or c.startswith("name_")]
    dropped_cols = [c for c in df.columns if c not in valid_cols]
    if dropped_cols:
        print(f"   ℹ️ Ignored non-schema columns: {dropped_cols}")
    df = df[valid_cols].copy()

    # Clean string columns and handle nulls
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": None, "None": None, "": None})

    # Drop any records without a valid ISIN
    initial_len = len(df)
    df = df.dropna(subset=["isin"])
    df = df[df["isin"].str.len() > 0]

    # Drop duplicates by ISIN
    df = df.drop_duplicates(subset=["isin"])
    if len(df) < initial_len:
        print(f"   Deduped: removed {initial_len - len(df):,} duplicate/invalid rows ({len(df):,} remaining)")

    # Replace pandas NaN with None for valid JSON serialization
    df = df.replace({np.nan: None})
    return df


def upload_table_records(
    session: requests.Session,
    table_name: str,
    records: list,
    batch_size: int = 2500,
    on_conflict: str = ""
) -> bool:
    """Upload records to a Supabase table in batches via REST API upsert.

    on_conflict: comma-separated column names that define uniqueness.
                 Supabase will UPDATE existing rows instead of inserting
                 duplicates when these columns match.
                 Example: 'amc,fund_name,isin,portfolio_date'
    """
    total_records = len(records)
    total_batches = math.ceil(total_records / batch_size)

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    # Append on_conflict so Supabase performs INSERT ... ON CONFLICT DO UPDATE
    url = f"{API_URL}/{table_name}"
    if on_conflict:
        url = f"{url}?on_conflict={on_conflict}"

    print(f"\n📤 Starting upload of {total_records:,} records to '{table_name}' in {total_batches} batch(es)...")
    if on_conflict:
        print(f"   Conflict key: ({on_conflict}) → existing rows will be updated, not duplicated")
    start_time = time.time()
    uploaded_count = 0

    for i in range(0, total_records, batch_size):
        batch = records[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        batch_records = len(batch)
        batch_t0 = time.time()

        try:
            response = session.post(
                url,
                headers=headers,
                json=batch,
                timeout=45
            )

            if response.status_code in [200, 201]:
                uploaded_count += batch_records
                elapsed = time.time() - start_time
                batch_elapsed = time.time() - batch_t0
                rate = uploaded_count / elapsed if elapsed > 0 else 0
                remaining = (total_records - uploaded_count) / rate if rate > 0 else 0
                pct = (uploaded_count / total_records) * 100

                print(
                    f"✓ [{table_name}] Batch {batch_num:>3}/{total_batches} | "
                    f"{uploaded_count:>6,}/{total_records:,} ({pct:5.1f}%) | "
                    f"{batch_records:,} rows in {batch_elapsed:.2f}s | "
                    f"Speed: {rate:5.0f} rows/s | "
                    f"ETA: {remaining:4.0f}s"
                )
            else:
                print(f"❌ [{table_name}] Batch {batch_num}/{total_batches} Failed with status {response.status_code}:")
                print(f"   {response.text[:300]}")
                if "Could not find the table" in response.text:
                    print(f"\n💡 Hint: Table '{table_name}' does not exist in Supabase.")
                    print("   Please execute the SQL commands in 'SUPABASE_SCHEMA.sql' in your Supabase SQL Editor.")
                return False

        except Exception as e:
            print(f"❌ [{table_name}] Batch {batch_num}/{total_batches} Exception: {e}")
            if "Connection" in str(e) or "getaddrinfo" in str(e):
                print("   Network error - check your internet connection and DNS settings.")
            return False

    total_time = time.time() - start_time
    avg_speed = total_records / total_time if total_time > 0 else 0

    print(f"✅ '{table_name}' upload finished: {total_records:,} records in {total_time:.2f}s ({avg_speed:,.0f} rows/s)")
    return True


def upload_fund_holdings(session: requests.Session, batch_size: int = 2500) -> bool:
    """Upload fund holdings matrix to Supabase fund_holdings table.

    Uses upsert with conflict key (amc, fund_name, isin, portfolio_date).
    Existing rows are updated in place; only genuinely new rows are inserted.
    Requires the UNIQUE constraint on fund_holdings to exist (see REPORT1_DEDUPE.sql).
    """
    if not MATRIX_FILE.exists():
        print(f"❌ ERROR: Matrix file not found at: {MATRIX_FILE}")
        return False

    df = load_and_prepare_fund_holdings(MATRIX_FILE)
    records = df.to_dict("records")
    return upload_table_records(
        session, "fund_holdings", records,
        batch_size=batch_size,
        on_conflict="amc,fund_name,isin,portfolio_date"
    )


def upload_security_master(session: requests.Session, batch_size: int = 1000) -> bool:
    """Upload security master mapping to Supabase security_master table.

    Uses upsert with conflict key (isin).
    Existing ISINs have their name columns updated; new ISINs are inserted.
    """
    if not SECURITY_MASTER_FILE.exists():
        print(f"❌ ERROR: Security Master file not found at: {SECURITY_MASTER_FILE}")
        return False

    df = load_and_prepare_security_master(SECURITY_MASTER_FILE)
    records = df.to_dict("records")
    return upload_table_records(
        session, "security_master", records,
        batch_size=batch_size,
        on_conflict="isin"
    )


def upload_data(table: str = "all", batch_size: int = 2500) -> bool:
    """Upload specified table(s) to Supabase."""
    print("=" * 80)
    print("🚀 SUPABASE DATA UPLOAD (High-Throughput Direct HTTP API)")
    print(f"   Target URL: https://{SUPABASE_HOST}")
    print(f"   Target:     {table.upper()}")
    print("=" * 80)

    session = create_http_session()
    overall_start = time.time()
    success = True

    if table in ["all", "fund_holdings"]:
        print("\n--- 1. FUND HOLDINGS TABLE ---")
        if not upload_fund_holdings(session, batch_size=batch_size):
            success = False

    if table in ["all", "security_master"]:
        print("\n--- 2. SECURITY MASTER TABLE ---")
        if not upload_security_master(session, batch_size=1000):
            success = False

    total_time = time.time() - overall_start
    print()
    print("=" * 80)
    if success:
        print("🎉 ALL REQUESTED UPLOADS COMPLETED SUCCESSFULLY!")
    else:
        print("⚠️ UPLOAD FINISHED WITH ERRORS")
    print(f"   Total Elapsed Time: {total_time:.2f}s ({total_time / 60:.1f} mins)")
    print("=" * 80)
    return success


def main():
    parser = argparse.ArgumentParser(description="Upload mutual fund data and security master to Supabase.")
    parser.add_argument(
        "--table",
        choices=["all", "fund_holdings", "security_master"],
        default="all",
        help="Which table to upload (default: all)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2500,
        help="Batch size for fund_holdings upload (default: 2500)"
    )

    args = parser.parse_args()
    success = upload_data(table=args.table, batch_size=args.batch_size)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
