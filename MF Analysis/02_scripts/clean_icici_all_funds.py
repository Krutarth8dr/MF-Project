import os
import re
import pandas as pd
from datetime import datetime
from pathlib import Path
import traceback

# =========================
# SETTINGS
# =========================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ICICI_RAW_FOLDER = str(PROJECT_ROOT / "01_raw_files" / "ICICI")
OUTPUT_FOLDER = str(PROJECT_ROOT / "03_clean_data" / "ICICI")
OUTPUT_FILE = os.path.join(OUTPUT_FOLDER, "ICICI_All_Funds_Cleaned.xlsx")

AMC_NAME = "ICICI Prudential Mutual Fund"

ICICI_FUNDS = {
    "ICICI Prudential Flexicap Fund": {
        "search": "ICICI Prudential Flexicap Fund",
        "sheet": "FLEXCAP"
    },
    "ICICI Prudential Large Cap Fund": {
        "search": "ICICI Prudential Large Cap Fund",
        "sheet": "BLUECHIP"
    },
    "ICICI Prudential Midcap Fund": {
        "search": "ICICI Prudential Midcap Fund",
        "sheet": "MIDCAP"
    },
    "ICICI Prudential Multicap Fund": {
        "search": "ICICI Prudential Multicap Fund",
        "sheet": "MULTICAP"
    },
    "ICICI Prudential Equity Savings Fund": {
        "search": "ICICI Prudential Equity Savings Fund",
        "sheet": "ESF"
    },
}

MONTH_MAP = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


# =========================
# HELPER FUNCTIONS
# =========================

def parse_icici_month_folder(folder_name):
    """
    Reads folder names like:
    Monthly-Portfolio-Disclosure-April-2025
    Monthly-Portfolio-Disclosure-January-2026
    """

    match = re.search(
        r"Monthly-Portfolio-Disclosure-([A-Za-z]+)-(\d{4})",
        folder_name,
        re.IGNORECASE
    )

    if not match:
        return None

    month_text = match.group(1).lower()
    year = int(match.group(2))

    month = MONTH_MAP.get(month_text)

    if not month:
        return None

    return datetime(year, month, 1)


def normalize_text(text):
    return str(text).lower().replace("-", " ").replace("_", " ").strip()


def find_fund_file(month_folder_path, fund_search_name):
    matches = []

    search_text = normalize_text(fund_search_name)

    for file in os.listdir(month_folder_path):
        file_path = os.path.join(month_folder_path, file)

        if not os.path.isfile(file_path):
            continue

        if not file.lower().endswith((".xlsx", ".xls")):
            continue

        file_text = normalize_text(file)

        if search_text in file_text:
            matches.append(file_path)

    return matches


def find_header_row(file_path, sheet_name):
    """
    Finds the row containing:
    Company/Issuer/Instrument Name
    """

    preview_df = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        header=None,
        nrows=30
    )

    for i in range(len(preview_df)):
        row_values = [
            str(value).strip().lower()
            if pd.notna(value)
            else ""
            for value in preview_df.iloc[i]
        ]

        if any(
            "company/issuer/instrument name" in value
            for value in row_values
        ):
            return i

    return None


def clean_icici_file(file_path, fund_name, sheet_name, portfolio_date):
    """
    Cleans one ICICI fund file for one month.
    """

    header_row_index = find_header_row(file_path, sheet_name)

    if header_row_index is None:
        raise Exception(f"Header row not found in file: {file_path}, sheet: {sheet_name}")

    df = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        header=header_row_index
    )

    df = df.dropna(how="all")
    df.columns = [str(col).strip() for col in df.columns]

    required_columns = {
        "Company/Issuer/Instrument Name": "Security_Name",
        "ISIN": "ISIN",
        "Coupon": "Coupon",
        "Industry/Rating": "Industry_Rating",
        "Quantity": "Quantity",
        "Exposure/Market Value(Rs.Lakh)": "Market_Value_Rs_Lakh",
        "% to Nav": "Percent_To_NAV",
    }

    available_columns = {}

    for original_col, new_col in required_columns.items():
        for col in df.columns:
            if str(col).strip().lower() == original_col.lower():
                available_columns[col] = new_col
                break

    missing_columns = [
        original_col
        for original_col, new_col in required_columns.items()
        if new_col not in available_columns.values()
    ]

    if missing_columns:
        raise Exception(
            f"Missing columns in file: {file_path}, sheet: {sheet_name}, columns: {missing_columns}"
        )

    df = df[list(available_columns.keys())].rename(columns=available_columns)

    # Basic cleanup
    df["Security_Name"] = df["Security_Name"].astype(str).str.strip()

    df = df[
        (df["Security_Name"].notna()) &
        (df["Security_Name"] != "") &
        (df["Security_Name"].str.lower() != "nan")
    ]

    # Remove section headers / totals / non-holding rows
    remove_keywords = [
        "equity & equity related instruments",
        "listed / awaiting listing",
        "unlisted",
        "awaiting listing",
        "total",
        "grand total",
        "cash & cash equivalent",
        "cash and cash equivalent",
        "net current assets",
        "margin fixed deposit",
        "treps",
        "repo",
        "reverse repo",
        "commercial paper",
        "certificate of deposit",
        "money market instruments",
        "debt instruments",
        "government securities",
        "sovereign",
        "mutual fund units",
        "investment in mutual fund",
        "alternative investment fund",
        "rights",
        "warrants",
        "preference shares",
    ]

    pattern = "|".join(remove_keywords)

    df = df[~df["Security_Name"].str.lower().str.contains(pattern, na=False)]

    # Keep only rows that look like actual holdings
    # Usually actual holdings have ISIN and/or Quantity/Market Value
    df = df[
        df["ISIN"].notna() |
        df["Quantity"].notna() |
        df["Market_Value_Rs_Lakh"].notna()
    ]

    # Numeric cleanup
    numeric_cols = [
        "Coupon",
        "Quantity",
        "Market_Value_Rs_Lakh",
        "Percent_To_NAV",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Metadata columns
    df.insert(0, "AMC", AMC_NAME)
    df.insert(1, "Fund_Name", fund_name)
    df.insert(2, "Portfolio_Date", portfolio_date)
    df.insert(3, "Month", portfolio_date.strftime("%b-%Y"))
    df.insert(4, "Source_File", os.path.basename(file_path))
    df.insert(5, "Source_Sheet", sheet_name)

    return df


# =========================
# MAIN PROCESS
# =========================

def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    month_folders = []

    for item in os.listdir(ICICI_RAW_FOLDER):
        item_path = os.path.join(ICICI_RAW_FOLDER, item)

        if os.path.isdir(item_path):
            month_date = parse_icici_month_folder(item)

            if month_date:
                month_folders.append({
                    "folder_name": item,
                    "folder_path": item_path,
                    "month_date": month_date
                })

    month_folders.sort(key=lambda x: x["month_date"])

    if not month_folders:
        print("No ICICI month folders found.")
        return

    print("Cleaning ICICI all funds")
    print("=" * 100)

    # Load existing cleaned data if available
    existing_df = None
    already_processed_fund_months = set()

    if os.path.exists(OUTPUT_FILE):
        try:
            existing_df = pd.read_excel(OUTPUT_FILE)
            existing_df["Portfolio_Date"] = pd.to_datetime(existing_df["Portfolio_Date"], errors="coerce")
            # Track (Fund_Name, Portfolio_Date) tuples instead of just months
            already_processed_fund_months = set(
                zip(existing_df["Fund_Name"].dropna(), existing_df["Portfolio_Date"].dropna())
            )
            print(f"Existing output found: {len(already_processed_fund_months)} fund-month combinations already processed")
        except Exception:
            print("Could not read existing output. Will reprocess all months.")
            existing_df = None

    # Don't filter months - we'll filter at the fund level instead
    print(f"Total months to check: {len(month_folders)}")

    # Clean all months (will check fund-level granularity)
    new_cleaned = []

    for month_info in month_folders:
        folder_name = month_info["folder_name"]
        folder_path = month_info["folder_path"]
        month_date = month_info["month_date"]

        print()
        print("#" * 100)
        print(f"Month: {month_date.strftime('%b-%Y')}")
        print(f"Folder: {folder_name}")
        print("#" * 100)

        for fund_name, fund_info in ICICI_FUNDS.items():
            # Check if THIS fund+month combination already exists
            if (fund_name, month_date) in already_processed_fund_months:
                print()
                print(f"Fund: {fund_name}")
                print("Status: Already processed (skipping)")
                continue

            fund_search_name = fund_info["search"]
            sheet_name = fund_info["sheet"]

            print()
            print(f"Fund: {fund_name}")

            matches = find_fund_file(folder_path, fund_search_name)

            if len(matches) == 0:
                print("Status: Missing fund file")
                continue

            if len(matches) > 1:
                print("Status: Multiple matching files found. Skipping.")
                for m in matches:
                    print("  ", m)
                continue

            file_path = matches[0]
            print("File:", file_path)
            print("Sheet:", sheet_name)

            try:
                clean_df = clean_icici_file(
                    file_path=file_path,
                    fund_name=fund_name,
                    sheet_name=sheet_name,
                    portfolio_date=month_date
                )

                new_cleaned.append(clean_df)
                print(f"Status: Cleaned successfully | Rows: {len(clean_df)}")

            except Exception as e:
                print("Status: Error")
                print("Error:", e)
                traceback.print_exc()

    if not new_cleaned:
        print()
        print("No new cleaned data generated.")
        return

    new_df = pd.concat(new_cleaned, ignore_index=True)

    # Combine with existing data
    if existing_df is not None and len(existing_df) > 0:
        final_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        final_df = new_df

    final_df = final_df.sort_values(
        by=["AMC", "Fund_Name", "Portfolio_Date", "Security_Name"],
        ascending=[True, True, True, True]
    )

    if os.path.exists(OUTPUT_FILE):
        try:
            os.remove(OUTPUT_FILE)
        except PermissionError:
            print("ERROR: Output file is open in Excel.")
            print("Please close this file and run again:")
            print(OUTPUT_FILE)
            return

    final_df.to_excel(OUTPUT_FILE, index=False)

    print()
    print("=" * 100)
    print("ICICI all funds cleaned file updated successfully")
    print("=" * 100)
    print("Output:", OUTPUT_FILE)
    print(f"New rows added: {len(new_df)}")
    print(f"Total rows: {len(final_df)}")
    print("Funds processed:", final_df["Fund_Name"].nunique())
    print("Months processed:", final_df["Month"].nunique())


if __name__ == "__main__":
    main()