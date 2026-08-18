import re
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "INVESCO"
OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "INVESCO"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_FOLDER / "INVESCO_All_Funds_Cleaned.xlsx"
AMC_NAME = "Invesco Mutual Fund"
START_DATE = pd.Timestamp(year=2024, month=10, day=1)
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


def is_valid_isin(value):
    if pd.isna(value):
        return False

    value = str(value).strip().upper()

    return bool(re.fullmatch(r"INE[A-Z0-9]{9}", value))


def extract_portfolio_date_from_filename(workbook_path):
    file_name = Path(workbook_path).stem
    match = re.search(r"(\d{4})-(\d{2})$", file_name)

    if not match:
        raise ValueError(f"Unable to extract date from filename: {file_name}")

    year, month = match.groups()

    return pd.Timestamp(year=int(year), month=int(month), day=1)


def extract_fund_name_from_filename(workbook_path):
    file_name = Path(workbook_path).stem
    fund_name = re.sub(r"\s*-\s*\d{4}-\d{2}$", "", file_name)
    return fund_name.strip()


def find_header_row(excel):
    preview = pd.read_excel(
        excel,
        sheet_name=excel.sheet_names[0],
        header=None,
        nrows=12,
    )

    for row_index in range(len(preview)):
        row_values = preview.iloc[row_index].astype(str).fillna("")
        if any(
            "name of the instrument" in str(value).strip().lower()
            for value in row_values
        ):
            return row_index

    raise ValueError("Could not locate header row containing 'Name of the Instrument'.")


def find_main_sheet(excel):
    return excel.sheet_names[0]


def clean_single_workbook(workbook_path):
    portfolio_date = extract_portfolio_date_from_filename(workbook_path)

    if portfolio_date < START_DATE:
        raise ValueError(
            f"Skipping workbook before start date: {workbook_path.name}"
        )

    fund_name = extract_fund_name_from_filename(workbook_path)
    month_label = portfolio_date.strftime("%b-%Y")

    excel = pd.ExcelFile(workbook_path)
    sheet_name = find_main_sheet(excel)
    header_row = find_header_row(excel)

    df = pd.read_excel(
        excel,
        sheet_name=sheet_name,
        header=header_row,
    )

    df.columns = [
        str(col).replace("\n", " ").replace("\r", " ").strip()
        for col in df.columns
    ]

    rename_map = {}

    for column_name in df.columns:
        normalized = str(column_name).strip().lower()

        if normalized == "name of the instrument":
            rename_map[column_name] = "Security_Name"
        elif normalized == "isin":
            rename_map[column_name] = "ISIN"
        elif normalized.startswith("industry"):
            rename_map[column_name] = "Industry_Rating"
        elif normalized == "quantity":
            rename_map[column_name] = "Quantity"

    df = df.rename(columns=rename_map)

    required_columns = [
        "Security_Name",
        "ISIN",
        "Industry_Rating",
        "Quantity",
    ]

    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise ValueError(
            f"Missing required columns in {workbook_path.name}: {missing}"
        )

    df = df[required_columns].copy()
    df = df.reset_index(drop=True)

    subtotal_rows = df["Security_Name"].fillna("").astype(str).str.strip().str.lower().str.contains(
        r"^sub total$|sub total", regex=True
    )

    if subtotal_rows.any():
        df = df.iloc[: subtotal_rows.idxmax()]

    df["ISIN"] = df["ISIN"].fillna("").astype(str).str.strip()
    df["Security_Name"] = df["Security_Name"].fillna("").astype(str).str.strip()
    df["Industry_Rating"] = df["Industry_Rating"].fillna("").astype(str).str.strip()
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")

    df = df[df["ISIN"].apply(is_valid_isin)]
    df = df[df["Quantity"].notna()]

    df.insert(0, "AMC", AMC_NAME)
    df.insert(1, "Fund_Name", fund_name)
    df.insert(2, "Portfolio_Date", portfolio_date)
    df.insert(3, "Month", month_label)

    df = df[STANDARD_COLUMNS]
    return df


def get_processed_keys(existing_df):
    existing_df = existing_df.copy()
    existing_df["Portfolio_Date"] = pd.to_datetime(
        existing_df["Portfolio_Date"],
        errors="coerce",
    )

    existing_df["Portfolio_Date"] = existing_df["Portfolio_Date"].apply(
        lambda value: pd.Timestamp(
            year=value.year,
            month=value.month,
            day=1,
        )
        if pd.notna(value)
        else pd.NaT
    )

    existing_df["Month_Key"] = existing_df["Portfolio_Date"].dt.strftime("%Y-%m")
    existing_df = existing_df[existing_df["Fund_Name"].notna() & existing_df["Month_Key"].notna()]

    return set(zip(existing_df["Fund_Name"], existing_df["Month_Key"]))


def process_workbook(workbook_path, processed_keys):
    portfolio_date = extract_portfolio_date_from_filename(workbook_path)
    month_key = portfolio_date.strftime("%Y-%m")
    fund_name = extract_fund_name_from_filename(workbook_path)

    if (fund_name, month_key) in processed_keys:
        print(f"Skipping already processed: {workbook_path.name}")
        return pd.DataFrame()

    cleaned = clean_single_workbook(workbook_path)
    print(f"Processed {workbook_path.name} -> rows: {len(cleaned)}")
    return cleaned


def main():
    print("=" * 100)
    print("Cleaning Invesco Monthly Portfolio Files")
    print("=" * 100)

    if not RAW_FOLDER.exists():
        raise FileNotFoundError(f"Raw folder not found: {RAW_FOLDER}")

    workbooks = sorted(RAW_FOLDER.rglob("*.xlsx"))

    if not workbooks:
        raise FileNotFoundError(f"No Invesco workbooks found under: {RAW_FOLDER}")

    existing_df = None
    processed_keys = set()

    if OUTPUT_FILE.exists():
        try:
            existing_df = pd.read_excel(OUTPUT_FILE)
            processed_keys = get_processed_keys(existing_df)
            print(f"Existing output found: {len(processed_keys)} fund-month combinations")
        except Exception as error:
            print("Could not read existing output.")
            print(error)
            existing_df = None
            processed_keys = set()

    all_data = []

    for workbook_path in workbooks:
        try:
            cleaned = process_workbook(workbook_path, processed_keys)
            if not cleaned.empty:
                all_data.append(cleaned)
                processed_keys.add(
                    (
                        extract_fund_name_from_filename(workbook_path),
                        extract_portfolio_date_from_filename(workbook_path).strftime("%Y-%m"),
                    )
                )
        except ValueError as error:
            print(f"Skipping {workbook_path.name}: {error}")
        except Exception as error:
            print(f"ERROR processing {workbook_path.name}")
            print(error)

    if not all_data:
        print("\nNo new Invesco data found.")
        return

    new_df = pd.concat(all_data, ignore_index=True)

    if existing_df is not None and not existing_df.empty:
        final_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        final_df = new_df

    final_df.to_excel(OUTPUT_FILE, index=False)
    print(f"\nWrote cleaned Invesco data to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
