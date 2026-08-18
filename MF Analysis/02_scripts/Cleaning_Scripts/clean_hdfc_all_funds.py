import re
import traceback
from pathlib import Path

import pandas as pd

# ==============================================================================
# SETTINGS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "HDFC"

OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "HDFC"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_FOLDER / "HDFC_All_Funds_Cleaned.xlsx"

AMC_NAME = "HDFC Mutual Fund"

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


# ==============================================================================
# HELPERS
# ==============================================================================


def normalize_header(value):
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())


def parse_date_text(value):
    if pd.isna(value):
        return pd.NaT

    text = str(value).strip()

    match = re.search(r"portfolio\s+as\s+on\s+(.+)$", text, re.IGNORECASE)
    if match:
        text = match.group(1).strip()

    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)

    if pd.isna(parsed):
        return pd.NaT

    return parsed.replace(day=1)


def extract_portfolio_date_from_file_name(workbook_path):
    match = re.search(
        r"-\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
        workbook_path.stem,
        re.IGNORECASE,
    )

    if not match:
        return pd.NaT

    return parse_date_text(match.group(1))


def extract_portfolio_date(df):
    for row_idx in range(min(len(df), 10)):
        for value in df.iloc[row_idx].tolist():
            parsed = parse_date_text(value)
            if pd.notna(parsed):
                return parsed

    return pd.NaT


def get_month_key(portfolio_date):
    portfolio_date = pd.to_datetime(portfolio_date, errors="coerce")

    if pd.isna(portfolio_date):
        return None

    return portfolio_date.to_period("M").to_timestamp()


def get_processed_keys(existing_df):
    existing_df = existing_df.copy()

    existing_df["Portfolio_Date"] = pd.to_datetime(
        existing_df["Portfolio_Date"],
        errors="coerce",
    )

    existing_df["Month_Key"] = existing_df["Portfolio_Date"].apply(get_month_key)

    existing_df = existing_df[
        existing_df["Fund_Name"].notna() & existing_df["Month_Key"].notna()
    ]

    return set(
        zip(
            existing_df["Fund_Name"],
            existing_df["Month_Key"],
        )
    )


def is_valid_isin(isin):
    if pd.isna(isin):
        return False

    isin = str(isin).strip().upper()

    return isin.startswith("INE")


def find_header_row(df):
    for row_idx in range(len(df)):
        row_values = [normalize_header(value) for value in df.iloc[row_idx].tolist()]

        if "isin" in row_values and "nameoftheinstrument" in row_values:
            return row_idx

    return None


def find_required_columns(columns):
    normalized_columns = {normalize_header(column): column for column in columns}

    expected = {
        "isin": "ISIN",
        "nameoftheinstrument": "Security_Name",
        "industryrating": "Industry_Rating",
        "quantity": "Quantity",
    }

    rename_map = {}
    missing = []

    for normalized_name, standard_name in expected.items():
        original_column = normalized_columns.get(normalized_name)

        if original_column is None:
            missing.append(standard_name)
            continue

        rename_map[original_column] = standard_name

    return rename_map, missing


def clean_quantity(series):
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


# ==============================================================================
# CLEAN A SINGLE HDFC WORKBOOK
# ==============================================================================


def clean_hdfc_file(workbook_path, fund_name):
    preview_df = pd.read_excel(
        workbook_path,
        sheet_name=0,
        header=None,
        nrows=30,
    )

    portfolio_date = extract_portfolio_date(preview_df)

    if pd.isna(portfolio_date):
        portfolio_date = extract_portfolio_date_from_file_name(workbook_path)

    if pd.isna(portfolio_date):
        raise ValueError(f"Portfolio date not found: {workbook_path}")

    header_row = find_header_row(preview_df)

    if header_row is None:
        raise ValueError(f"Header row not found: {workbook_path}")

    df = pd.read_excel(
        workbook_path,
        sheet_name=0,
        header=header_row,
    )

    df = df.dropna(how="all")
    df.columns = [str(column).strip() for column in df.columns]

    rename_map, missing_columns = find_required_columns(df.columns)

    if missing_columns:
        raise ValueError(f"Missing columns {missing_columns} in file:\n{workbook_path}")

    df = df[list(rename_map.keys())].rename(columns=rename_map)

    # HDFC files end the equity section with "Sub Total" in the ISIN column.
    # Keep only rows above that marker before applying ISIN filters.
    sub_total_mask = (
        df["ISIN"]
        .astype(str)
        .str.strip()
        .str.contains(r"^sub\s*total$", case=False, na=False, regex=True)
    )

    if sub_total_mask.any():
        first_sub_total_position = sub_total_mask[sub_total_mask].index[0]
        df = df.loc[:first_sub_total_position].iloc[:-1].copy()

    df["ISIN"] = df["ISIN"].astype(str).str.strip().str.upper()
    df = df[df["ISIN"].apply(is_valid_isin)]

    df["Security_Name"] = df["Security_Name"].astype(str).str.strip()
    df = df[df["Security_Name"].notna()]
    df = df[df["Security_Name"] != ""]
    df = df[df["Security_Name"].str.lower() != "nan"]

    df["Industry_Rating"] = df["Industry_Rating"].fillna("").astype(str).str.strip()

    df["Quantity"] = clean_quantity(df["Quantity"])
    df = df[df["Quantity"].notna()]

    df.insert(0, "AMC", AMC_NAME)
    df.insert(1, "Fund_Name", fund_name)
    df.insert(2, "Portfolio_Date", portfolio_date)
    df.insert(3, "Month", portfolio_date.strftime("%b-%Y"))

    return df[STANDARD_COLUMNS]


# ==============================================================================
# MAIN
# ==============================================================================


def main():
    print("=" * 100)
    print("Cleaning HDFC Monthly Portfolio Files")
    print("=" * 100)

    if not RAW_FOLDER.exists():
        raise FileNotFoundError(f"HDFC raw folder not found:\n{RAW_FOLDER}")

    existing_df = None
    processed_keys = set()

    if OUTPUT_FILE.exists():
        try:
            existing_df = pd.read_excel(OUTPUT_FILE)

            missing = [
                col for col in STANDARD_COLUMNS if col not in existing_df.columns
            ]

            if missing:
                print("Existing cleaned file is incompatible.")
                print("Reprocessing all HDFC files.")
                existing_df = None
            else:
                existing_df = existing_df[STANDARD_COLUMNS]
                processed_keys = get_processed_keys(existing_df)
                print(
                    f"Existing cleaned file found "
                    f"({len(processed_keys)} fund-month combinations)."
                )

        except Exception as e:
            print("Could not read existing cleaned file.")
            print(e)
            existing_df = None
            processed_keys = set()

    all_data = []
    workbook_count = 0
    skipped_count = 0
    error_count = 0

    fund_folders = sorted(folder for folder in RAW_FOLDER.iterdir() if folder.is_dir())

    if not fund_folders:
        raise FileNotFoundError(f"No HDFC fund folders found in:\n{RAW_FOLDER}")

    for fund_folder in fund_folders:
        fund_name = fund_folder.name
        workbook_files = sorted(
            file
            for file in fund_folder.glob("*.xlsx")
            if not file.name.startswith("~$")
        )

        if not workbook_files:
            print(f"\n{fund_name}")
            print("No workbook files found")
            continue

        print()
        print("#" * 100)
        print(fund_name)
        print("#" * 100)

        for workbook_path in workbook_files:
            workbook_count += 1

            portfolio_date = extract_portfolio_date_from_file_name(workbook_path)
            month_key = get_month_key(portfolio_date)

            if month_key is not None and (fund_name, month_key) in processed_keys:
                skipped_count += 1
                print(f"{workbook_path.name:<75} Already processed")
                continue

            try:
                cleaned = clean_hdfc_file(workbook_path, fund_name)

                if cleaned.empty:
                    print(f"{workbook_path.name:<75} No valid rows")
                    continue

                all_data.append(cleaned)

                month_key = get_month_key(cleaned["Portfolio_Date"].iloc[0])
                processed_keys.add((fund_name, month_key))

                print(f"{workbook_path.name:<75} Rows: {len(cleaned)}")

            except Exception:
                error_count += 1
                print(f"{workbook_path.name:<75} ERROR")
                traceback.print_exc()

    if not all_data:
        if existing_df is not None:
            print()
            print("No new HDFC data found.")
            print("Existing cleaned file preserved.")
            print("Output:")
            print(OUTPUT_FILE)
            return

        raise ValueError("No cleaned HDFC data produced.")

    new_df = pd.concat(all_data, ignore_index=True)

    if existing_df is not None and not existing_df.empty:
        final_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        final_df = new_df

    final_df["Portfolio_Date"] = pd.to_datetime(
        final_df["Portfolio_Date"],
        errors="coerce",
    )

    final_df = final_df[STANDARD_COLUMNS]
    final_df = final_df.drop_duplicates()
    final_df = final_df.sort_values(
        by=["Portfolio_Date", "Fund_Name", "Security_Name"],
        ascending=[True, True, True],
    )
    final_df.reset_index(drop=True, inplace=True)

    if OUTPUT_FILE.exists():
        try:
            OUTPUT_FILE.unlink()
        except PermissionError:
            print("ERROR")
            print("Please close:")
            print(OUTPUT_FILE)
            return

    final_df.to_excel(OUTPUT_FILE, index=False)

    print()
    print("=" * 100)
    print("HDFC Cleaning Complete")
    print("=" * 100)
    print(f"Workbooks Checked : {workbook_count}")
    print(f"Already Processed : {skipped_count}")
    print(f"Errors            : {error_count}")
    print(f"New rows added    : {len(new_df)}")
    print(f"Total rows        : {len(final_df)}")
    print(f"Funds             : {final_df['Fund_Name'].nunique()}")
    print(f"Output            : {OUTPUT_FILE}")


# ==============================================================================
# RUN
# ==============================================================================

if __name__ == "__main__":
    main()
