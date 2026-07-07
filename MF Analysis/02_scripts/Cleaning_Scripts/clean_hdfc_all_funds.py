import pandas as pd
from pathlib import Path
import re

# ==============================================================================
# SETTINGS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_HDFC_FOLDER = PROJECT_ROOT / "01_raw_files" / "HDFC"

OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "HDFC"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_FOLDER / "HDFC_All_Funds_Cleaned.xlsx"

AMC_NAME = "HDFC Mutual Fund"

FUNDS = [
    "HDFC Flexi Cap",
    "HDFC Multi Cap",
    "HDFC Large Cap",
    "HDFC Balanced Advantage Fund",
    "HDFC Focused Fund",
]


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def get_month_from_filename(file_name):
    """
    Example

    Monthly HDFC Flexi Cap Fund - 31 January 2026.xlsx

    Returns

    Month = Jan-2026
    Portfolio_Date = 2026-01-01
    """

    match = re.search(
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
        file_name,
    )

    if not match:
        raise ValueError(f"Month not found in filename: {file_name}")

    day, month_name, year = match.groups()

    date_value = pd.to_datetime(f"{day} {month_name} {year}")

    return (
        date_value.strftime("%b-%Y"),
        date_value.replace(day=1),
    )


def get_month_key(portfolio_date):

    portfolio_date = pd.to_datetime(
        portfolio_date,
        errors="coerce",
    )

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


# ==============================================================================
# CLEAN A SINGLE HDFC FUND
# ==============================================================================


def clean_single_hdfc_fund(fund_name, processed_keys):

    raw_folder = RAW_HDFC_FOLDER / fund_name

    if not raw_folder.exists():
        print(f"Skipping. Folder not found: {raw_folder}")
        return pd.DataFrame()

    files = sorted(raw_folder.glob("*.xlsx"))

    if not files:
        print(f"Skipping. No Excel files found for: {fund_name}")
        return pd.DataFrame()

    print()
    print("=" * 90)
    print(f"Cleaning fund : {fund_name}")
    print(f"Files found   : {len(files)}")
    print("=" * 90)

    cleaned_data = []

    for file_path in files:

        month, portfolio_date = get_month_from_filename(file_path.name)
        month_key = get_month_key(portfolio_date)

        if (fund_name, month_key) in processed_keys:
            print(f"Skipping : {file_path.name}")
            continue

        print(f"Processing : {file_path.name}")

        # --------------------------------------------------------
        # Read workbook
        # --------------------------------------------------------

        df = pd.read_excel(
            file_path,
            header=4,
        )

        clean_df = pd.DataFrame(index=df.index)

        clean_df["AMC"] = AMC_NAME
        clean_df["Fund_Name"] = fund_name
        clean_df["Portfolio_Date"] = portfolio_date
        clean_df["Month"] = month

        clean_df["ISIN"] = df.iloc[:, 1]
        clean_df["Security_Name"] = df.iloc[:, 3]
        clean_df["Industry_Rating"] = df.iloc[:, 4]
        clean_df["Quantity"] = df.iloc[:, 5]

        # --------------------------------------------------------
        # Text cleaning
        # --------------------------------------------------------

        clean_df["ISIN"] = clean_df["ISIN"].astype(str).str.strip()

        clean_df["Security_Name"] = clean_df["Security_Name"].astype(str).str.strip()

        clean_df["Industry_Rating"] = (
            clean_df["Industry_Rating"].fillna("").astype(str).str.strip()
        )

        # --------------------------------------------------------
        # Quantity cleaning
        # --------------------------------------------------------

        clean_df["Quantity"] = (
            clean_df["Quantity"]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("-", "0", regex=False)
            .str.strip()
        )

        clean_df["Quantity"] = pd.to_numeric(
            clean_df["Quantity"],
            errors="coerce",
        )

        # --------------------------------------------------------
        # Keep only Indian equities
        # --------------------------------------------------------

        clean_df = clean_df[clean_df["ISIN"].apply(is_valid_isin)]

        clean_df = clean_df[clean_df["Quantity"].notna()]

        cleaned_data.append(clean_df)

        processed_keys.add(
            (
                fund_name,
                month_key,
            )
        )

        print(f"Rows : {len(clean_df)}")

    if cleaned_data:
        return pd.concat(
            cleaned_data,
            ignore_index=True,
        )

    return pd.DataFrame()


# ==============================================================================
# MAIN
# ==============================================================================


def main():

    print("=" * 90)
    print("Cleaning HDFC Monthly Portfolio Files")
    print("=" * 90)

    all_data = []

    existing_df = None
    processed_keys = set()

    if OUTPUT_FILE.exists():

        try:

            existing_df = pd.read_excel(OUTPUT_FILE)

            required_columns = [
                "Fund_Name",
                "Portfolio_Date",
            ]

            missing = [
                col for col in required_columns if col not in existing_df.columns
            ]

            if missing:

                print("Existing cleaned file is incompatible.")
                print("Reprocessing all HDFC files.")

                existing_df = None

            else:

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

    # ----------------------------------------------------------
    # Process every HDFC fund
    # ----------------------------------------------------------

    for fund in FUNDS:

        cleaned = clean_single_hdfc_fund(
            fund,
            processed_keys,
        )

        if not cleaned.empty:
            all_data.append(cleaned)

    # ----------------------------------------------------------
    # Nothing new
    # ----------------------------------------------------------

    if not all_data:

        if existing_df is not None:

            print()
            print("No new HDFC data found.")
            print("Existing cleaned file preserved.")
            print("Output:")
            print(OUTPUT_FILE)

            return

        raise ValueError("No cleaned HDFC data produced.")

    # ----------------------------------------------------------
    # Combine new data
    # ----------------------------------------------------------

    new_df = pd.concat(
        all_data,
        ignore_index=True,
    )

    if existing_df is not None:

        final_df = pd.concat(
            [
                existing_df,
                new_df,
            ],
            ignore_index=True,
        )

    else:

        final_df = new_df

    # ----------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------

    final_df["Portfolio_Date"] = pd.to_datetime(
        final_df["Portfolio_Date"],
        errors="coerce",
    )

    final_df = final_df.drop_duplicates()

    final_df = final_df.sort_values(
        by=[
            "Portfolio_Date",
            "Fund_Name",
            "Security_Name",
        ],
        ascending=[
            True,
            True,
            True,
        ],
    )

    final_df.reset_index(
        drop=True,
        inplace=True,
    )

    # ----------------------------------------------------------
    # Save
    # ----------------------------------------------------------

    if OUTPUT_FILE.exists():

        try:

            OUTPUT_FILE.unlink()

        except PermissionError:

            print()
            print("ERROR")
            print("Please close:")
            print(OUTPUT_FILE)

            return

    final_df.to_excel(
        OUTPUT_FILE,
        index=False,
    )

    print()
    print("=" * 90)
    print("HDFC Cleaning Complete")
    print("=" * 90)
    print(f"Funds Processed : {len(FUNDS)}")
    print(f"New rows added  : {len(new_df)}")
    print(f"Total rows      : {len(final_df)}")
    print(f"Funds           : {final_df['Fund_Name'].nunique()}")
    print(f"Output          : {OUTPUT_FILE}")


# ==============================================================================
# RUN
# ==============================================================================

if __name__ == "__main__":
    main()
