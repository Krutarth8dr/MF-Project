import os
import re
import sys
import calendar
from datetime import datetime
from pathlib import Path
import openpyxl
import pandas as pd

# ==============================================================================
# SETTINGS & PATHS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "UNION"
OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "UNION"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_FOLDER / "Union_All_Funds_Cleaned.xlsx"

AMC_NAME = "Union MF"
START_DATE = pd.Timestamp(year=2024, month=10, day=1)
END_DATE = pd.Timestamp(year=2026, month=8, day=31)

STANDARD_COLUMNS = [
    "AMC",
    "Fund_Name",
    "Portfolio_Date",
    "Month",
    "Security_Name",
    "ISIN",
    "Industry_Rating",
    "Quantity",
]

TARGET_FUNDS = [
    "Union Equity Savings Fund",
    "Union Active Momentum Fund",
    "Union Balanced Advantage Fund",
    "Union ELSS Tax Saver Fund",
    "Union Childrens Fund",
    "Union Midcap Fund",
    "Union Focused Fund",
    "Union Multi Asset Allocation Fund",
    "Union Value Fund",
    "Union Consumption Fund",
    "Union Multicap Fund",
    "Union Flexi Cap Fund",
    "Union Small Cap Fund",
    "Union Large & Midcap Fund",
    "Union Aggressive Hybrid Fund",
    "Union Innovation & Opportunities Fund",
    "Union Largecap Fund",
    "Union Business Cycle Fund",
]

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def normalize_text(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


TARGET_NORM_MAP = {normalize_text(f): f for f in TARGET_FUNDS}


def clean_text(val):
    if val is None:
        return ""
    text = str(val).strip()
    return re.sub(r"\s+", " ", text)


def match_canonical_fund_name(filename_or_title):
    norm = normalize_text(filename_or_title)
    for norm_name, original_name in TARGET_NORM_MAP.items():
        if norm_name in norm:
            return original_name
    return None


def parse_portfolio_date_from_file(ws, file_path):
    # 1. Search first 15 rows for 'as on ...'
    for r in range(1, 15):
        for c in range(1, 10):
            val = ws.cell(r, c).value
            if val and "as on" in str(val).lower():
                text = str(val)
                m = re.search(r"as\s+on\s+([a-zA-Z]+)\s+(\d{1,2}),?\s+(\d{4})", text, re.I)
                if m:
                    mo_str, day_str, yr_str = m.groups()
                    mo_num = MONTH_MAP.get(mo_str.lower().strip())
                    if mo_num:
                        return datetime(int(yr_str), mo_num, int(day_str))

                m2 = re.search(r"as\s+on\s+(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", text, re.I)
                if m2:
                    d, m_num, y = m2.groups()
                    return datetime(int(y), int(m_num), int(d))

                m3 = re.search(r"as\s+on\s+(\d{1,2})(?:st|nd|rd|th)?\s+([a-zA-Z]+),?\s+(\d{4})", text, re.I)
                if m3:
                    day_str, mo_str, yr_str = m3.groups()
                    mo_num = MONTH_MAP.get(mo_str.lower().strip())
                    if mo_num:
                        return datetime(int(yr_str), mo_num, int(day_str))

    # Fallback to directory structure: 01_raw_files/UNION/<YYYY>/<MM>/...
    parts = file_path.parts
    try:
        y = int(parts[-3])
        m = int(parts[-2])
        last_day = calendar.monthrange(y, m)[1]
        return datetime(y, m, last_day)
    except Exception:
        return datetime(2026, 8, 31)


def clean_union_data():
    print("=" * 75)
    print("UNION MUTUAL FUND - CLEANING PIPELINE")
    print(f"Raw Folder:   {RAW_FOLDER}")
    print(f"Output File:  {OUTPUT_FILE}")
    print(f"Target Date Range: {START_DATE.strftime('%b %Y')} to {END_DATE.strftime('%b %Y')}")
    print("=" * 75)

    excel_files = sorted(list(RAW_FOLDER.rglob("*.xlsx")) + list(RAW_FOLDER.rglob("*.xls")))
    if not excel_files:
        print(f"ERROR: No monthly files found in {RAW_FOLDER}")
        sys.exit(1)

    print(f"\n[Step 1/3] Found {len(excel_files)} monthly fund workbooks to process.")

    all_rows = []
    skipped_files = 0

    for file_idx, file_path in enumerate(excel_files, 1):
        fund_name = match_canonical_fund_name(file_path.name)
        if not fund_name:
            print(f"  [WARN] Unmatched file: {file_path.name}")
            skipped_files += 1
            continue

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active
        except Exception as e:
            print(f"  [ERROR] Failed to load {file_path.name}: {e}")
            skipped_files += 1
            continue

        portfolio_dt = parse_portfolio_date_from_file(ws, file_path)
        portfolio_ts = pd.Timestamp(portfolio_dt)

        if not (START_DATE <= portfolio_ts <= END_DATE):
            skipped_files += 1
            continue

        month_str = portfolio_dt.strftime("%b-%Y")

        # Find header columns
        header_row = None
        col_instrument = None
        col_isin = None
        col_industry = None
        col_qty = None

        for r in range(1, 25):
            row_vals = [ws.cell(r, c).value for c in range(1, 15)]
            for c_idx, val in enumerate(row_vals, 1):
                if val is None:
                    continue
                v_lower = str(val).strip().lower()
                if "name of the instrument" in v_lower:
                    header_row = r
                    col_instrument = c_idx
                elif v_lower == "isin":
                    col_isin = c_idx
                elif any(k in v_lower for k in ["rating / industry", "industry / rating", "industry /rating", "rating/industry", "industry"]):
                    col_industry = c_idx
                elif "quantity" in v_lower:
                    col_qty = c_idx

            if header_row and col_instrument and col_isin and col_qty:
                break

        if not (header_row and col_instrument and col_isin and col_qty):
            print(f"  [WARN] Header not detected in {file_path.name}")
            skipped_files += 1
            continue

        # Extract holdings until 'Total' in col_instrument
        file_holdings = 0
        for r in range(header_row + 1, ws.max_row + 1):
            inst_raw = ws.cell(r, col_instrument).value
            inst_name = clean_text(inst_raw)

            # Stop scanning immediately when Total / Sub Total is detected
            if inst_name.lower() in ["total", "sub total", "sub-total", "grand total"]:
                break

            isin_raw = ws.cell(r, col_isin).value
            isin = clean_text(isin_raw)

            # Filter only ISINs starting with INE
            if not isin.startswith("INE"):
                continue

            industry = clean_text(ws.cell(r, col_industry).value) if col_industry else ""

            qty_raw = ws.cell(r, col_qty).value
            try:
                if qty_raw is None or str(qty_raw).strip() == "":
                    continue
                qty = float(str(qty_raw).replace(",", "").strip())
                if qty <= 0:
                    continue
            except (ValueError, TypeError):
                continue

            all_rows.append({
                "AMC": AMC_NAME,
                "Fund_Name": fund_name,
                "Portfolio_Date": portfolio_ts.strftime("%Y-%m-%d"),
                "Month": month_str,
                "Security_Name": inst_name,
                "ISIN": isin,
                "Industry_Rating": industry,
                "Quantity": int(round(qty)),
            })
            file_holdings += 1

    print("\n[Step 2/3] Compiling cleaned dataset...")
    if not all_rows:
        print("ERROR: No valid equity holdings extracted!")
        sys.exit(1)

    df = pd.DataFrame(all_rows, columns=STANDARD_COLUMNS)

    # Convert types
    df["Portfolio_Date"] = pd.to_datetime(df["Portfolio_Date"])
    df["Quantity"] = df["Quantity"].astype("int64")

    # Sort dataset cleanly
    df = df.sort_values(["Portfolio_Date", "Fund_Name", "Security_Name"]).reset_index(drop=True)

    print(f"Total rows extracted: {len(df):,}")
    print(f"Unique funds:         {df['Fund_Name'].nunique()}")
    print(f"Unique ISINs:         {df['ISIN'].nunique()}")
    print(f"Unique months:        {df['Month'].nunique()}")
    print(f"Date range:           {df['Portfolio_Date'].min().strftime('%d-%b-%Y')} to {df['Portfolio_Date'].max().strftime('%d-%b-%Y')}")

    print("\n[Step 3/3] Saving cleaned data to Excel...")
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"Saved successfully: {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size:,} bytes)")
    print("=" * 75)


if __name__ == "__main__":
    clean_union_data()
