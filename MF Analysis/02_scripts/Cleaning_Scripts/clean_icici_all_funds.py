import os
import re
import pandas as pd
from datetime import datetime
from pathlib import Path
import traceback

# ==============================================================================
# SETTINGS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ICICI_RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "ICICI"

OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "ICICI"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_FOLDER / "ICICI_All_Funds_Cleaned.xlsx"

AMC_NAME = "ICICI Prudential Mutual Fund"

ICICI_FUNDS = {
    "ICICI Prudential Flexicap Fund": {
        "search": "ICICI Prudential Flexicap Fund",
        "sheet": "FLEXCAP",
    },
    "ICICI Prudential Large Cap Fund": {
        "search": "ICICI Prudential Large Cap Fund",
        "sheet": "BLUECHIP",
    },
    "ICICI Prudential Midcap Fund": {
        "search": "ICICI Prudential Midcap Fund",
        "sheet": "MIDCAP",
    },
    "ICICI Prudential Multicap Fund": {
        "search": "ICICI Prudential Multicap Fund",
        "sheet": "MULTICAP",
    },
    "ICICI Prudential Equity Savings Fund": {
        "search": "ICICI Prudential Equity Savings Fund",
        "sheet": "ESF",
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
# HELPER FUNCTIONS
# ==============================================================================


def parse_icici_month_folder(folder_name):
    """
    Reads folder names like:

    Monthly-Portfolio-Disclosure-April-2025

    Returns:
        2025-04-01
    """

    match = re.search(
        r"Monthly-Portfolio-Disclosure-([A-Za-z]+)-(\d{4})",
        folder_name,
        re.IGNORECASE,
    )

    if not match:
        return None

    month_name = match.group(1).lower()
    year = int(match.group(2))

    month = MONTH_MAP.get(month_name)

    if month is None:
        return None

    return datetime(year, month, 1)


def normalize_text(text):
    return str(text).lower().replace("-", " ").replace("_", " ").strip()


def find_fund_file(month_folder_path, fund_search_name):

    matches = []

    search_text = normalize_text(fund_search_name)

    for file in os.listdir(month_folder_path):

        file_path = os.path.join(
            month_folder_path,
            file,
        )

        if not os.path.isfile(file_path):
            continue

        if not file.lower().endswith(
            (
                ".xlsx",
                ".xls",
            )
        ):
            continue

        file_text = normalize_text(file)

        if search_text in file_text:
            matches.append(file_path)

    return matches


def find_header_row(file_path, sheet_name):

    preview_df = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        header=None,
        nrows=30,
    )

    for i in range(len(preview_df)):

        row_values = [
            str(value).strip().lower() for value in preview_df.iloc[i].tolist()
        ]

        if any("company/issuer/instrument name" in value for value in row_values):
            return i

    return None


# ==============================================================================
# CLEAN A SINGLE ICICI FUND FILE
# ==============================================================================


def clean_icici_file(file_path, fund_name, sheet_name, portfolio_date):
    """
    Cleans one ICICI fund file for one month.
    Returns a standardized dataframe.
    """

    header_row = find_header_row(file_path, sheet_name)

    if header_row is None:
        raise ValueError(
            f"Header row not found.\n" f"File : {file_path}\n" f"Sheet: {sheet_name}"
        )

    df = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        header=header_row,
    )

    df = df.dropna(how="all")
    df.columns = [str(col).strip() for col in df.columns]

    for i in range(len(df)):

        row = df.iloc[i]

        if row.fillna("").astype(str).str.strip().eq("").all():
            df = df.iloc[:i]
            break

    # --------------------------------------------------------------------------
    # Column Mapping
    # --------------------------------------------------------------------------

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

    for original_col, renamed_col in required_columns.items():

        for column in df.columns:

            if str(column).strip().lower() == original_col.lower():

                available_columns[column] = renamed_col
                break

    missing_columns = [
        original_col
        for original_col, renamed_col in required_columns.items()
        if renamed_col not in available_columns.values()
    ]

    if missing_columns:

        raise ValueError(
            f"Missing columns:\n{missing_columns}\n\n"
            f"File : {file_path}\n"
            f"Sheet: {sheet_name}"
        )

    df = df[list(available_columns.keys())].rename(columns=available_columns)

    # --------------------------------------------------------------------------
    # Basic Cleanup
    # --------------------------------------------------------------------------

    df["Security_Name"] = df["Security_Name"].astype(str).str.strip()

    df = df[df["Security_Name"].notna()]

    df = df[df["Security_Name"] != ""]

    df = df[df["Security_Name"].str.lower() != "nan"]

    # --------------------------------------------------------------------------
    # Numeric cleanup
    # --------------------------------------------------------------------------

    numeric_columns = [
        "Coupon",
        "Quantity",
        "Market_Value_Rs_Lakh",
        "Percent_To_NAV",
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    # --------------------------------------------------------------------------
    # Keep only genuine holdings
    # --------------------------------------------------------------------------

    df = df[
        (df["ISIN"].notna())
        | (df["Quantity"].notna())
        | (df["Market_Value_Rs_Lakh"].notna())
    ]

    # Keep only Indian equity ISINs

    df["ISIN"] = df["ISIN"].astype(str).str.strip().str.upper()

    df = df[df["ISIN"].str.startswith("INE")]

    # --------------------------------------------------------------------------
    # Metadata
    # --------------------------------------------------------------------------

    df.insert(0, "AMC", AMC_NAME)
    df.insert(1, "Fund_Name", fund_name)
    df.insert(2, "Portfolio_Date", portfolio_date)
    df.insert(3, "Month", portfolio_date.strftime("%b-%Y"))

    # --------------------------------------------------------------------------
    # Final standardization
    # --------------------------------------------------------------------------

    df["Industry_Rating"] = df["Industry_Rating"].fillna("").astype(str).str.strip()

    df["Quantity"] = pd.to_numeric(
        df["Quantity"],
        errors="coerce",
    )

    df = df[df["Quantity"].notna()]

    df = df[STANDARD_COLUMNS]

    return df
# ==============================================================================
# MAIN
# ==============================================================================


def main():

    print("=" * 100)
    print("Cleaning ICICI Monthly Portfolio Files")
    print("=" * 100)

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # --------------------------------------------------------------------------
    # Find all month folders
    # --------------------------------------------------------------------------

    month_folders = []

    for item in os.listdir(ICICI_RAW_FOLDER):

        item_path = os.path.join(
            ICICI_RAW_FOLDER,
            item,
        )

        if not os.path.isdir(item_path):
            continue

        month_date = parse_icici_month_folder(item)

        if month_date is None:
            continue

        month_folders.append(
            {
                "folder_name": item,
                "folder_path": item_path,
                "month_date": month_date,
            }
        )

    month_folders.sort(key=lambda x: x["month_date"])

    if not month_folders:
        raise FileNotFoundError("No ICICI month folders found.")

    # --------------------------------------------------------------------------
    # Existing cleaned data
    # --------------------------------------------------------------------------

    existing_df = None
    processed_keys = set()

    if os.path.exists(OUTPUT_FILE):

        try:

            existing_df = pd.read_excel(OUTPUT_FILE)

            existing_df = existing_df[STANDARD_COLUMNS]

            existing_df["Portfolio_Date"] = pd.to_datetime(
                existing_df["Portfolio_Date"],
                errors="coerce",
            )

            required_columns = [
                "Fund_Name",
                "Portfolio_Date",
            ]

            missing = [
                col for col in required_columns if col not in existing_df.columns
            ]

            if missing:

                print("Existing cleaned file is incompatible.")
                print("Reprocessing all ICICI files.")

                existing_df = None

            else:

                existing_df["Portfolio_Date"] = pd.to_datetime(
                    existing_df["Portfolio_Date"],
                    errors="coerce",
                )

                processed_keys = set(
                    zip(
                        existing_df["Fund_Name"],
                        existing_df["Portfolio_Date"],
                    )
                )

                print(
                    f"Existing cleaned file found "
                    f"({len(processed_keys)} fund-month combinations)."
                )

        except Exception as e:

            print("Could not read existing cleaned file.")

            print(e)

            existing_df = None

    # --------------------------------------------------------------------------
    # Clean new data
    # --------------------------------------------------------------------------

    all_data = []

    for month_info in month_folders:

        folder_name = month_info["folder_name"]
        folder_path = month_info["folder_path"]
        month_date = month_info["month_date"]

        print()
        print("#" * 100)
        print(month_date.strftime("%b-%Y"))
        print("#" * 100)

        for fund_name, fund_info in ICICI_FUNDS.items():

            if (fund_name, month_date) in processed_keys:

                print(f"{fund_name:<45} Already processed")

                continue

            print(fund_name)

            matches = find_fund_file(
                folder_path,
                fund_info["search"],
            )

            if len(matches) == 0:

                print("Missing file")
                continue

            if len(matches) > 1:

                print("Multiple matching files found")

                for file in matches:
                    print(file)

                continue

            try:

                cleaned = clean_icici_file(
                    file_path=matches[0],
                    fund_name=fund_name,
                    sheet_name=fund_info["sheet"],
                    portfolio_date=month_date,
                )

                all_data.append(cleaned)

                processed_keys.add(
                    (
                        fund_name,
                        month_date,
                    )
                )

                print(f"Rows : {len(cleaned)}")

            except Exception:
                print("ERROR")
                traceback.print_exc()

    # --------------------------------------------------------------------------
    # Nothing new
    # --------------------------------------------------------------------------

    if not all_data:

        if existing_df is not None:

            print()
            print("No new ICICI data found.")
            print("Existing cleaned file preserved.")
            print("Output:")
            print(OUTPUT_FILE)

            return

        raise ValueError("No cleaned ICICI data produced.")

    # --------------------------------------------------------------------------
    # Combine
    # --------------------------------------------------------------------------

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

    # --------------------------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------------------------

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

    # --------------------------------------------------------------------------
    # Save
    # --------------------------------------------------------------------------

    if os.path.exists(OUTPUT_FILE):

        try:

            os.remove(OUTPUT_FILE)

        except PermissionError:

            print("ERROR")
            print("Please close:")
            print(OUTPUT_FILE)

            return
    final_df = final_df[STANDARD_COLUMNS]
    final_df.to_excel(
        OUTPUT_FILE,
        index=False,
    )

    print()
    print("=" * 100)
    print("ICICI Cleaning Complete")
    print("=" * 100)
    print(f"Months Processed : {len(month_folders)}")
    print(f"New rows added   : {len(new_df)}")
    print(f"Total rows       : {len(final_df)}")
    print(f"Funds            : {final_df['Fund_Name'].nunique()}")
    print(f"Output           : {OUTPUT_FILE}")


# ==============================================================================
# RUN
# ==============================================================================

if __name__ == "__main__":
    main()
