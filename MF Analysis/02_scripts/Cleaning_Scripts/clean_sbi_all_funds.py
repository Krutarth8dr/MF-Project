import re
import pandas as pd
from pathlib import Path

# ==============================================================================
# SETTINGS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "SBI"

OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "SBI"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_FOLDER / "SBI_All_Funds_Cleaned.xlsx"

TARGET_SHEETS = [
    "SLMF",
    "SMGLF",
    "SFEF",
    "SFLEXI",
    "SMIDCAP",
    "SBLUECHIP",
    "SSCF",
    "SMCF",
]

AMC_NAME = "SBI Mutual Fund"

FUND_NAME_REPLACEMENTS = {
    "SBI Blue Chip Fund": "SBI Large Cap Fund",
    "SBI Focused Equity Fund": "SBI Focused Fund",
    "SBI Magnum Global Fund": "SBI MNC Fund",
    "SBI Magnum Midcap Fund": "SBI Midcap Fund",
}

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def extract_fund_name(df):
    """
    Row 2
    Column D contains the actual fund name.
    """

    value = df.iloc[2, 3]

    if pd.isna(value):
        return ""

    return str(value).strip()


def extract_portfolio_date(df):
    """
    Row 3
    Column D contains the portfolio date.
    """

    value = df.iloc[3, 3]

    return pd.to_datetime(value, errors="coerce")


def normalize_fund_name(fund_name):
    fund_name = str(fund_name).strip()
    return FUND_NAME_REPLACEMENTS.get(fund_name, fund_name)


def get_month_key(portfolio_date):
    portfolio_date = pd.to_datetime(portfolio_date, errors="coerce")

    if pd.isna(portfolio_date):
        return None

    return portfolio_date.to_period("M").to_timestamp()


def get_processed_keys(existing_df):
    existing_df = existing_df.copy()
    existing_df["FundName"] = existing_df["FundName"].apply(normalize_fund_name)
    existing_df["Portfolio_Date"] = pd.to_datetime(
        existing_df["Portfolio_Date"],
        errors="coerce",
    )
    existing_df["Month_Key"] = existing_df["Portfolio_Date"].apply(get_month_key)

    existing_df = existing_df[
        existing_df["FundName"].notna() & existing_df["Month_Key"].notna()
    ]

    return set(zip(existing_df["FundName"], existing_df["Month_Key"]))


def is_valid_isin(isin):
    """
    Keep only Indian equity ISINs.
    """

    if pd.isna(isin):
        return False

    isin = str(isin).strip().upper()

    return isin.startswith("INE")


# ==============================================================================
# CLEAN A SINGLE SHEET
# ==============================================================================


def clean_sheet(df, sheet_name):

    fund_name = normalize_fund_name(extract_fund_name(df))
    portfolio_date = extract_portfolio_date(df)
    header_row = None

    for i in range(len(df)):

        row_values = df.iloc[i].astype(str).str.strip().tolist()

        if "Name of the Instrument / Issuer" in row_values:
            header_row = i
            break

    if header_row is None:
        raise ValueError("Header row not found.")

    headers = df.iloc[header_row].tolist()

    data = df.iloc[header_row + 1 :].copy()

    data.columns = headers

    # Drop completely empty rows
    data = data.dropna(how="all")

    # Rename columns
    rename_map = {
        "Name of the Instrument / Issuer": "Security_Name",
        "Rating / Industry^": "Industry_Rating",
    }

    data = data.rename(columns=rename_map)

    required_columns = [
        "Security_Name",
        "ISIN",
        "Industry_Rating",
        "Quantity",
    ]

    for col in required_columns:
        if col not in data.columns:
            raise ValueError(f"{sheet_name}: Missing required column '{col}'")

    # Keep only valid ISIN rows
    data = data[data["ISIN"].apply(is_valid_isin)]

    # Quantity must be numeric
    data["Quantity"] = pd.to_numeric(data["Quantity"], errors="coerce")

    data = data[data["Quantity"].notna()]

    # Clean text
    data["Security_Name"] = data["Security_Name"].astype(str).str.strip()

    data["Industry_Rating"] = data["Industry_Rating"].fillna("").astype(str).str.strip()

    data.insert(0, "AMC", AMC_NAME)
    data.insert(1, "FundName", fund_name)
    data.insert(2, "Portfolio_Date", portfolio_date)
    data.insert(
        3, "Month", portfolio_date.strftime("%b-%Y") if pd.notna(portfolio_date) else ""
    )

    final_columns = [
        "AMC",
        "FundName",
        "Portfolio_Date",
        "Month",
        "Security_Name",
        "ISIN",
        "Industry_Rating",
        "Quantity",
    ]

    return data[final_columns]

# ==============================================================================
# PROCESS A SINGLE WORKBOOK
# ==============================================================================


def process_workbook(workbook_path, processed_keys):

    print("\n" + "=" * 90)
    print(f"Workbook: {workbook_path.name}")
    print("=" * 90)

    xls = pd.ExcelFile(workbook_path)

    cleaned_data = []

    for sheet in TARGET_SHEETS:

        if sheet not in xls.sheet_names:
            print(f"Skipping {sheet} (sheet not found)")
            continue

        try:

            df = pd.read_excel(workbook_path, sheet_name=sheet, header=None)

            fund_name = normalize_fund_name(extract_fund_name(df))
            portfolio_date = extract_portfolio_date(df)
            month_key = get_month_key(portfolio_date)

            if (fund_name, month_key) in processed_keys:
                print(f"{sheet:<12} | {fund_name:<35} | Already processed")
                continue

            cleaned_df = clean_sheet(df, sheet)

            cleaned_data.append(cleaned_df)
            processed_keys.add((fund_name, month_key))

            print(
                f"{sheet:<12}"
                f" | {cleaned_df['FundName'].iloc[0]:<35}"
                f" | Rows: {len(cleaned_df)}"
            )

        except Exception as e:

            print(f"{sheet:<12} | ERROR -> {e}")

    if cleaned_data:
        return pd.concat(cleaned_data, ignore_index=True)

    return pd.DataFrame()


# ==============================================================================
# MAIN
# ==============================================================================


def main():

    workbook_files = sorted(RAW_FOLDER.glob("*.xlsx"))

    if not workbook_files:
        raise FileNotFoundError(f"No SBI workbook found in:\n{RAW_FOLDER}")

    all_data = []
    existing_df = None
    processed_keys = set()

    print("=" * 90)
    print("Cleaning SBI Monthly Portfolio Files")
    print("=" * 90)

    if OUTPUT_FILE.exists():
        try:
            existing_df = pd.read_excel(OUTPUT_FILE)
            require_columns = ["FundName", "Portfolio_Date"]
            missing = [col for col in require_columns if col not in existing_df.columns]

            if missing:
                print(
                    "Existing output is missing required columns. Reprocessing all SBI files."
                )
                existing_df = None
            else:
                processed_keys = get_processed_keys(existing_df)
                print(
                    f"Existing output found: {len(processed_keys)} fund-month "
                    "combinations already processed"
                )

        except Exception as e:
            print("Could not read existing output. Reprocessing all SBI files.")
            print("Reason:", e)
            existing_df = None
            processed_keys = set()

    for workbook in workbook_files:

        cleaned = process_workbook(workbook, processed_keys)

        if not cleaned.empty:
            all_data.append(cleaned)

    if not all_data:
        if existing_df is not None:
            print("\nNo new SBI data found. Existing cleaned file preserved.")
            print("Output:", OUTPUT_FILE)
            return

        raise ValueError("No cleaned data produced.")

    new_df = pd.concat(all_data, ignore_index=True)

    if existing_df is not None and not existing_df.empty:
        final_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        final_df = new_df

    final_df["Portfolio_Date"] = pd.to_datetime(
        final_df["Portfolio_Date"], errors="coerce"
    )
    final_df["FundName"] = final_df["FundName"].apply(normalize_fund_name)
    final_df = final_df.drop_duplicates()

    final_df = final_df.sort_values(by=["Portfolio_Date", "FundName", "Security_Name"])

    final_df.reset_index(drop=True, inplace=True)

    if OUTPUT_FILE.exists():
        try:
            OUTPUT_FILE.unlink()
        except PermissionError:
            print("\nERROR")
            print("Please close:")
            print(OUTPUT_FILE)
            return

    final_df.to_excel(OUTPUT_FILE, index=False)

    print("\n" + "=" * 90)
    print("SBI Cleaning Complete")
    print("=" * 90)
    print(f"Workbooks Processed : {len(workbook_files)}")
    print(f"New rows added     : {len(new_df)}")
    print(f"Total rows         : {len(final_df)}")
    print(f"Funds              : {final_df['FundName'].nunique()}")
    print(f"Output             : {OUTPUT_FILE}")


# ==============================================================================
# RUN
# ==============================================================================

if __name__ == "__main__":
    main()
