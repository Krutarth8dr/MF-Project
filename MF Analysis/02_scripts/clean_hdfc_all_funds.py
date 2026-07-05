import argparse
import pandas as pd
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_HDFC_FOLDER = PROJECT_ROOT / "01_raw_files" / "HDFC"
CLEAN_FOLDER = PROJECT_ROOT / "03_clean_data" / "HDFC"
CLEAN_FOLDER.mkdir(parents=True, exist_ok=True)

AMC_NAME = "HDFC"

# Add all HDFC fund folder names here
FUNDS = [
    "HDFC Flexi Cap",
    "HDFC Multi Cap",
    "HDFC Large Cap",
    "HDFC Balanced Advantage Fund",
    "HDFC Focused Fund",
]


def get_month_from_filename(file_name):
    """
    Example:
    Monthly HDFC Flexi Cap Fund - 31 January 2026.xlsx

    Output:
    Month = Jan-2026
    MonthDate = 2026-01-01
    """
    match = re.search(
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
        file_name
    )

    if not match:
        raise ValueError(f"Month not found in filename: {file_name}")

    day, month_name, year = match.groups()
    date_value = pd.to_datetime(f"{day} {month_name} {year}")

    month_text = date_value.strftime("%b-%Y")
    month_date = date_value.replace(day=1)

    return month_text, month_date


def clean_single_hdfc_fund(fund_name, incremental=False):
    raw_folder = RAW_HDFC_FOLDER / fund_name

    if not raw_folder.exists():
        print(f"Skipping. Folder not found: {raw_folder}")
        return None

    files = sorted(raw_folder.glob("*.xlsx"))

    if not files:
        print(f"Skipping. No Excel files found for: {fund_name}")
        return None

    clean_output = CLEAN_FOLDER / f"clean_{fund_name.lower().replace(' ', '_')}_all_months.xlsx"
    existing_df = None
    existing_source_files = set()

    if incremental and clean_output.exists():
        existing_df = pd.read_excel(clean_output, parse_dates=["MonthDate"])
        existing_df["SourceFile"] = existing_df["SourceFile"].astype(str).str.strip()
        existing_source_files = set(existing_df["SourceFile"].tolist())

    print()
    print("=" * 80)
    print(f"Cleaning fund: {fund_name}")
    print(f"Files found: {len(files)}")
    if incremental and existing_source_files:
        print(f"Skipping {len(existing_source_files)} already cleaned files.")
    print("=" * 80)

    new_data = []

    for file_path in files:
        if incremental and file_path.name in existing_source_files:
            print("Skipping already cleaned file:", file_path.name)
            continue

        print("Processing:", file_path.name)

        month, month_date = get_month_from_filename(file_path.name)

        # HDFC format header row is 4
        df = pd.read_excel(file_path, header=4)

        clean_df = pd.DataFrame(index=df.index)

        clean_df["AMC"] = AMC_NAME
        clean_df["FundName"] = fund_name
        clean_df["Month"] = month
        clean_df["MonthDate"] = month_date
        clean_df["ISIN"] = df.iloc[:, 1]
        clean_df["EquityName"] = df.iloc[:, 3]
        clean_df["Industry"] = df.iloc[:, 4]
        clean_df["Quantity"] = df.iloc[:, 5]
        clean_df["MarketValue"] = df.iloc[:, 6]
        clean_df["PercentageToNAV"] = df.iloc[:, 7]
        clean_df["SourceFile"] = file_path.name

        # Text cleaning
        clean_df["ISIN"] = clean_df["ISIN"].astype(str).str.strip()
        clean_df["EquityName"] = clean_df["EquityName"].astype(str).str.strip()
        clean_df["Industry"] = clean_df["Industry"].astype(str).str.strip()

        # Number cleaning
        for col in ["Quantity", "MarketValue", "PercentageToNAV"]:
            clean_df[col] = (
                clean_df[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("-", "0", regex=False)
                .str.strip()
            )
            clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce")

        # Keep only valid Indian equity rows
        clean_df = clean_df[clean_df["ISIN"].str.startswith("INE", na=False)]
        clean_df = clean_df[clean_df["Quantity"].notna()]

        new_data.append(clean_df)

    if not new_data:
        if existing_df is not None:
            print("No new raw files found for fund; existing cleaned file preserved.")
            return clean_output

        print(f"Skipping. No new Excel files cleaned for: {fund_name}")
        return None

    new_df = pd.concat(new_data, ignore_index=True)

    if existing_df is not None:
        final_df = pd.concat([existing_df, new_df], ignore_index=True)
        final_df = final_df.drop_duplicates(
            subset=["SourceFile", "FundName", "MonthDate", "ISIN"],
            keep="last"
        )
    else:
        final_df = new_df

    final_df = final_df.sort_values(
        by=["MonthDate", "EquityName"],
        ascending=[True, True]
    )

    final_df.to_excel(clean_output, index=False)

    print(f"Saved: {clean_output}")
    print(f"Rows: {len(final_df)}")

    return clean_output


created_files = []

for fund in FUNDS:
    output_file = clean_single_hdfc_fund(fund, incremental=True)
    if output_file:
        created_files.append(output_file)

print()
print("Cleaning completed.")
print("Files created:")

for file in created_files:
    print(file)
