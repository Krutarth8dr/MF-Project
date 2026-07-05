"""
Upload the master long-format quantity matrix to the Supabase fund_holdings table.

Uses the Supabase REST API directly (HTTP requests) rather than supabase-py,
which is more robust to transient network issues.

Requires SUPABASE_URL and SUPABASE_KEY in .env. SUPABASE_KEY must be the
SERVICE_ROLE key: the fund_holdings RLS policy only allows writes via
service_role, so the anon key cannot insert/upsert here.
"""

import sys
import pandas as pd
import requests
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Windows consoles default to cp1252, which cannot encode the status symbols
# (✓/✗/❌) used below and crashes on print. Force UTF-8 output.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# Load environment
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MATRIX_FILE = PROJECT_ROOT / "05_matrix" / "MASTER" / "matrix_all_amc_funds_quantity_long.xlsx"

# Get credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERROR: Missing SUPABASE_URL or SUPABASE_KEY in .env")
    exit(1)

# Remove https:// if present
if SUPABASE_URL.startswith("https://"):
    SUPABASE_URL = SUPABASE_URL.replace("https://", "")

API_URL = f"https://{SUPABASE_URL}/rest/v1"

def upload_data():
    print("=" * 80)
    print("SUPABASE DATA UPLOAD (Direct HTTP API)")
    print("=" * 80)
    
    # Load data
    print("\nLoading matrix file...")
    df = pd.read_excel(MATRIX_FILE)
    print(f"Loaded {len(df)} rows")
    
    # Clean data
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
    
    # Convert Quantity to int
    if "quantity" in df.columns:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype('int64')
    
    # Convert dates to string
    if "portfolio_date" in df.columns:
        df["portfolio_date"] = df["portfolio_date"].astype(str)
    
    # Remove duplicates
    df = df.drop_duplicates()
    print(f"After dedup: {len(df)} rows")
    
    # Replace NaN with None
    df = df.where(pd.notna(df), None)
    
    # Convert to records
    records = df.to_dict("records")
    
    # Clean each record - convert None/NaN to null
    import json
    import numpy as np
    clean_records = []
    for record in records:
        clean_record = {}
        for key, value in record.items():
            if pd.isna(value) or value is None:
                clean_record[key] = None
            elif isinstance(value, (pd.Timestamp, np.datetime64)):
                clean_record[key] = str(value)
            elif isinstance(value, np.integer):
                clean_record[key] = int(value)
            elif isinstance(value, np.floating):
                clean_record[key] = float(value)
            else:
                clean_record[key] = value
        clean_records.append(clean_record)
    
    records = clean_records
    
    # Upload in batches
    batch_size = 100
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    
    print(f"\nUploading {len(records)} records in batches of {batch_size}...")
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(records) + batch_size - 1) // batch_size
        
        try:
            # POST to insert endpoint
            url = f"{API_URL}/fund_holdings"
            response = requests.post(
                url,
                headers=headers,
                json=batch,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                print(f"✓ Batch {batch_num}/{total_batches} uploaded")
            else:
                print(f"✗ Batch {batch_num}: Status {response.status_code}")
                print(f"  Response: {response.text[:200]}")
        
        except Exception as e:
            print(f"✗ Batch {batch_num}: {e}")
            if "Connection refused" in str(e) or "getaddrinfo" in str(e):
                print("  Network error - check your internet connection")
            return False
    
    print()
    print("=" * 80)
    print("✓ Upload completed!")
    print("=" * 80)
    return True

if __name__ == "__main__":
    upload_data()
