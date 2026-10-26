"""
Clean all downloaded monthly portfolio files for Samco Mutual Fund (Samco MF).

Process:
    - Reads all files in 01_raw_files/Samco_MF/<YYYY>/<MM>/
    - Parses target files for the 4 target funds:
        1. SAMCO_MULTICAP    -> Samco Multi Cap Fund
        2. SAMCO_SPECIAL_OPP -> Samco Special Opportunities Fund
        3. SAMCO_FLEXICAP    -> Samco Flexi Cap Fund
        4. SAMCO_SMALLCAP    -> Samco Small Cap Fund
    - Dynamic header detection for Name, ISIN, Industry, and Quantity
    - Stops immediately upon encountering 'Sub Total', 'Total', '(b) Unlisted', etc.
    - Filters for valid listed Indian equities (ISIN starts with INE, length 12, quantity > 0)
    - Generates 03_clean_data/Samco_MF/Samco_MF_All_Funds_Cleaned.xlsx
"""

import sys
import os
import calendar
import warnings
from datetime import datetime
from pathlib import Path
import openpyxl
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# Force UTF-8 output
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "Samco_MF"
CLEAN_DIR = PROJECT_ROOT / "03_clean_data" / "Samco_MF"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = CLEAN_DIR / "Samco_MF_All_Funds_Cleaned.xlsx"

CODE_TO_FUND = {
    "SAMCO_LARGE_MIDCAP": "Samco Large & Mid Cap Fund",
    "SAMCO_LARGECAP": "Samco Large Cap Fund",
    "SAMCO_DYNAMIC_ASSET": "Samco Dynamic Asset Allocation Fund",
    "SAMCO_MULTI_ASSET": "Samco Multi Asset Allocation Fund",
    "SAMCO_MULTICAP": "Samco Multi Cap Fund",
    "SAMCO_MIDCAP": "Samco Mid Cap Fund",
    "SAMCO_ELSS": "Samco ELSS Tax Saver Fund",
    "SAMCO_SPECIAL_OPP": "Samco Special Opportunities Fund",
    "SAMCO_SMALLCAP": "Samco Small Cap Fund",
    "SAMCO_FLEXICAP": "Samco Flexi Cap Fund",
}

STOP_TERMS = [
    "sub total",
    "subtotal",
    "(b) unlisted",
    "(b)unlisted",
    "total",
    "reverse repo",
    "treps",
    "net receivables",
    "grand total",
    "notes",
]


def identify_columns(worksheet):
    """Dynamically find header row and column indices."""
    for r_idx in range(1, 15):
        row_vals = [worksheet.cell(r_idx, c).value for c in range(1, 15)]
        str_vals = [str(v).strip().lower() if v is not None else "" for v in row_vals]

        # Look for ISIN header
        if any("isin" == s or "isin code" in s for s in str_vals):
            header_row = r_idx
            isin_col = None
            name_col = None
            ind_col = None
            qty_col = None

            for c_idx, s in enumerate(str_vals, start=1):
                if not s:
                    continue
                if "isin" in s and isin_col is None:
                    isin_col = c_idx
                elif ("instrument" in s or "name" in s or "security" in s) and name_col is None:
                    name_col = c_idx
                elif ("industry" in s or "rating" in s or "sector" in s) and ind_col is None:
                    ind_col = c_idx
                elif ("quantity" in s or "shares" in s or "qty" in s) and qty_col is None:
                    qty_col = c_idx

            if isin_col and name_col and qty_col:
                return header_row, name_col, isin_col, ind_col, qty_col

    return None, None, None, None, None


def clean_quantity(raw_val):
    """Convert quantity cell to clean positive integer or None."""
    if raw_val is None:
        return None
    try:
        val_str = str(raw_val).replace(",", "").strip()
        val_float = float(val_str)
        if val_float > 0 and not pd.isna(val_float):
            return int(round(val_float))
    except (ValueError, TypeError):
        pass
    return None


def clean_isin(raw_val):
    """Validate and clean ISIN string."""
    if raw_val is None:
        return None
    s = str(raw_val).strip().upper()
    if s.startswith("INE") and len(s) == 12 and s.isalnum():
        return s
    return None


def parse_samco_file(filepath: Path):
    """Parse a single Samco MF Excel portfolio file."""
    # File naming: <FUND_CODE>_<YYYY>_<MM>.xlsx
    parts = filepath.stem.split("_")
    # Identify fund code
    matched_code = None
    for code in sorted(CODE_TO_FUND.keys(), key=lambda c: -len(c)):
        if filepath.stem.startswith(code):
            matched_code = code
            break

    if not matched_code:
        return []

    fund_name = CODE_TO_FUND[matched_code]

    # Extract year and month from stem
    year_str = parts[-2]
    month_str = parts[-1]
    try:
        year = int(year_str)
        month = int(month_str)
    except ValueError:
        # Fallback to parent directories
        try:
            month = int(filepath.parent.name)
            year = int(filepath.parent.parent.name)
        except ValueError:
            return []

    # Calculate portfolio date (last calendar day of month)
    last_day = calendar.monthrange(year, month)[1]
    portfolio_date = f"{year:04d}-{month:02d}-{last_day:02d}"
    month_display = datetime(year, month, 1).strftime("%b-%Y")

    records = []

    try:
        wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
    except Exception as exc:
        print(f"❌ Error opening {filepath.name}: {exc}")
        return []

    ws = wb.active
    header_row, name_col, isin_col, ind_col, qty_col = identify_columns(ws)

    if not header_row:
        wb.close()
        print(f"⚠️ Header row not found in {filepath.name}")
        return []

    for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
        if not row:
            continue

        # Check for stop keywords across first few cells
        lead_cells = [str(c).strip().lower() for c in row[:3] if c is not None]
        lead_text = " ".join(lead_cells)
        if any(term in lead_text for term in STOP_TERMS):
            break

        # Extract values
        raw_name = row[name_col - 1] if len(row) >= name_col else None
        raw_isin = row[isin_col - 1] if len(row) >= isin_col else None
        raw_ind = row[ind_col - 1] if (ind_col and len(row) >= ind_col) else ""
        raw_qty = row[qty_col - 1] if len(row) >= qty_col else None

        isin = clean_isin(raw_isin)
        qty = clean_quantity(raw_qty)

        # Skip non-equity or invalid rows
        if not isin or not qty:
            continue

        sec_name = str(raw_name).strip() if raw_name is not None else ""
        ind_rating = str(raw_ind).strip() if raw_ind is not None else ""

        records.append({
            "AMC": "Samco MF",
            "Fund_Name": fund_name,
            "Portfolio_Date": portfolio_date,
            "Month": month_display,
            "Security_Name": sec_name,
            "ISIN": isin,
            "Industry_Rating": ind_rating,
            "Quantity": qty,
        })

    wb.close()
    return records


def main():
    print("=" * 80)
    print("🧹 Cleaning Samco MF Portfolio Files")
    print(f"Raw Directory: {RAW_DIR}")
    print("=" * 80)

    files = sorted(RAW_DIR.rglob("*.xlsx"))
    print(f"Found {len(files)} files to clean.")

    all_records = []
    file_count = 0

    for fpath in files:
        records = parse_samco_file(fpath)
        if records:
            all_records.extend(records)
            file_count += 1

    print(f"\nExtracted {len(all_records):,} records from {file_count} files.")

    if not all_records:
        print("❌ No records extracted. Aborting.")
        sys.exit(1)

    df = pd.DataFrame(all_records)

    # Standard columns
    cols = [
        "AMC",
        "Fund_Name",
        "Portfolio_Date",
        "Month",
        "Security_Name",
        "ISIN",
        "Industry_Rating",
        "Quantity",
    ]
    df = df[cols]

    # Deduplicate in case of duplicate entries
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["AMC", "Fund_Name", "Portfolio_Date", "ISIN", "Security_Name"])
    if len(df) < before_dedup:
        print(f"Removed {before_dedup - len(df)} duplicate records.")

    # Sort
    df = df.sort_values(by=["Fund_Name", "Portfolio_Date", "Security_Name"]).reset_index(drop=True)

    # Save to Excel
    print(f"\nWriting clean dataset to: {OUTPUT_FILE}")
    df.to_excel(OUTPUT_FILE, index=False)

    print("\n" + "=" * 80)
    print("SUMMARY BY FUND")
    print("=" * 80)
    summary = df.groupby("Fund_Name").agg(
        Total_Rows=("Quantity", "count"),
        Unique_ISINs=("ISIN", "nunique"),
        Min_Date=("Portfolio_Date", "min"),
        Max_Date=("Portfolio_Date", "max"),
        Months=("Month", "nunique"),
    )
    print(summary.to_string())

    print("\n" + "=" * 80)
    print("OVERALL SUMMARY")
    print("=" * 80)
    print(f"Total Rows:     {len(df):,}")
    print(f"Total Funds:    {df['Fund_Name'].nunique()}")
    print(f"Total ISINs:    {df['ISIN'].nunique()}")
    print(f"Date Range:     {df['Portfolio_Date'].min()} to {df['Portfolio_Date'].max()}")
    print(f"File Saved:     {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size / 1024:.1f} KB)")
    print("=" * 80)


if __name__ == "__main__":
    main()
