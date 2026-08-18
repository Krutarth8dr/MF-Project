import re
import pandas as pd
from pathlib import Path

# ==============================================================================
# SETTINGS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "Aditya Birla"
OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "Aditya Birla"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_FOLDER / "ABSL_All_Funds_Cleaned.xlsx"

# JUNE 2026 IS THE ONLY CANONICAL SOURCE FOR FUND NAMES.
CANONICAL_FILENAME_HINTS = ["june", "2026"]

TARGET_SHEETS = [
    "ABSLMCF",
    "ABSLBCF",
    "ABSLCONF",
    "ABSLESG",
    "ABSLMAAF",
    "ABSLQF",
    "ABSLSO",
    "ABSLTNLF",
    "ADVG",
    "BINFRA",
    "BSLBKFS",
    "BSLDAAF",
    "BSLEQTY",
    "BSLFEF",
    "BSLMFG",
    "BSLNMF",
    "BSLPHF",
    "BSLR96",
    "BSLTA1",
    "BTOP100",
    "GENNEXT",
    "MIDCAP",
    "MNC",
    "PSUEQ",
    "PURE",
]

TARGET_SHEETS = list(dict.fromkeys(TARGET_SHEETS))

AMC_NAME = "ABSL"


# ==============================================================================
# FILE HELPERS
# ==============================================================================


def find_all_workbooks():
    patterns = ("*.xlsx", "*.xls", "*.xlsm")
    files = []

    for pattern in patterns:
        files.extend(RAW_FOLDER.rglob(pattern))

    return sorted(set(files))


def excel_engine_for(path: Path) -> str:
    if path.suffix.lower() == ".xls":
        return "xlrd"
    return "openpyxl"


def find_canonical_workbook():
    """June 2026 remains the permanent canonical Fund_Name source."""

    candidates = [
        p
        for p in find_all_workbooks()
        if all(hint.lower() in p.name.lower() for hint in CANONICAL_FILENAME_HINTS)
    ]

    if not candidates:
        raise FileNotFoundError(
            "Could not find the June 2026 ABSL canonical workbook "
            f"matching {CANONICAL_FILENAME_HINTS} under {RAW_FOLDER}."
        )

    chosen = sorted(candidates)[0]

    if len(candidates) > 1:
        print(f"Note: multiple June 2026 candidates found, using: {chosen.name}")

    return chosen


# ==============================================================================
# GENERAL HELPERS
# ==============================================================================


def normalize_text(value):
    if pd.isna(value):
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).replace("\n", " ").strip().lower(),
    )


def extract_portfolio_date(df):
    """
    Find 'Portfolio Statement as on ...' anywhere in the first 10 rows.
    This handles the July layout where the title shifted columns.
    """

    for i in range(min(10, len(df))):
        for cell in df.iloc[i].tolist():
            if pd.isna(cell):
                continue

            cell_str = str(cell).strip()

            match = re.search(
                r"as on\s+(.+)$",
                cell_str,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            date_str = match.group(1).strip()
            date_str = re.sub(r",(\S)", r", \1", date_str)

            parsed = pd.to_datetime(date_str, errors="coerce")

            if pd.isna(parsed):
                return pd.NaT

            return parsed.replace(day=1)

    return pd.NaT


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
# JUNE CANONICAL FUND-NAME MAPPING
# ==============================================================================


def find_index_header_row(index_df):
    """
    Detect a modern Index layout by header names.

    July's Index has:
        Scheme Code
        Scheme Short Code
        Scheme Name

    The function is also capable of reading this format if it ever appears
    in the canonical workbook.
    """

    for row_idx in range(min(25, len(index_df))):
        normalized = {
            normalize_text(value): col_idx
            for col_idx, value in enumerate(index_df.iloc[row_idx].tolist())
            if normalize_text(value)
        }

        if "scheme short code" in normalized and "scheme name" in normalized:
            return row_idx, normalized

        if "scheme code" in normalized and "scheme name" in normalized:
            return row_idx, normalized

    return None, {}


def load_canonical_fund_names(canonical_workbook):
    """
    Build the canonical mapping ONLY from June.

    For the original June structure:
        column 1 = code
        column 2 = Fund Name

    If June has a header-based structure:
        Scheme Short Code -> Scheme Name

    July's Scheme Name is never used.
    """
    print("=" * 90)
    print("Loading Canonical Fund Names from JUNE 2026")
    print("=" * 90)
    print(f"Canonical source: {canonical_workbook}")

    index_df = pd.read_excel(
        canonical_workbook,
        sheet_name="Index",
        header=None,
        engine=excel_engine_for(canonical_workbook),
    )

    fund_name_mapping = {}

    # Try header-based mapping first.
    header_row, headers = find_index_header_row(index_df)

    if header_row is not None:
        name_col = headers.get("scheme name")

        if "scheme short code" in headers:
            code_col = headers["scheme short code"]
        else:
            code_col = headers.get("scheme code")

        if code_col is not None and name_col is not None:
            for _, row in index_df.iloc[header_row + 1 :].iterrows():
                code = row.iloc[code_col]
                fund_name = row.iloc[name_col]

                if pd.isna(code) or pd.isna(fund_name):
                    continue

                code = str(code).strip().upper()
                fund_name = str(fund_name).strip()

                if code in TARGET_SHEETS and fund_name:
                    fund_name_mapping[code] = fund_name

    # Original ABSL June structure fallback.
    if not fund_name_mapping:
        if index_df.shape[1] < 3:
            raise ValueError(
                "June Index does not contain the expected code/name columns."
            )

        for sheet in TARGET_SHEETS:
            code_values = index_df.iloc[:, 1].astype(str).str.strip().str.upper()

            match = index_df[code_values == sheet.upper()]

            if match.empty:
                print(f"{sheet:<12} -> NOT FOUND in June Index")
                continue

            fund_name = str(match.iloc[0, 2]).strip()

            if fund_name and fund_name.lower() != "nan":
                fund_name_mapping[sheet] = fund_name

    print()
    print("June canonical mapping:")
    print("-" * 90)

    for sheet in TARGET_SHEETS:
        if sheet in fund_name_mapping:
            print(f"{sheet:<12} -> {fund_name_mapping[sheet]}")
        else:
            print(f"{sheet:<12} -> NOT FOUND")

    print(
        f"\nCanonical fund mappings loaded: "
        f"{len(fund_name_mapping)} / {len(TARGET_SHEETS)}"
    )
    print()

    if not fund_name_mapping:
        raise ValueError("No Fund_Name mappings could be loaded from June.")

    return fund_name_mapping


# ==============================================================================
# MONTHLY SHEET HEADER DETECTION
# ==============================================================================


def find_portfolio_header(df):
    """
    Dynamically locate the holdings header.

    Old files can have:
        Name of the Instrument
        ISIN
        Industry / Rating
        Quantity

    July 2026 can have:
        Name of the Instrument / Issuer
        ISIN
        Industry^ / Rating
        Quantity

    No fixed column numbers are assumed.
    """

    for row_idx in range(len(df)):
        row = df.iloc[row_idx].tolist()

        normalized = {
            col_idx: normalize_text(value) for col_idx, value in enumerate(row)
        }

        security_col = None
        isin_col = None
        industry_col = None
        quantity_col = None

        for col_idx, value in normalized.items():
            if value.startswith("name of the instrument"):
                security_col = col_idx
                break

        for col_idx, value in normalized.items():
            if value == "isin":
                isin_col = col_idx
                break

        for col_idx, value in normalized.items():
            if value.startswith("industry"):
                industry_col = col_idx
                break

        for col_idx, value in normalized.items():
            if value == "quantity":
                quantity_col = col_idx
                break

        if (
            security_col is not None
            and isin_col is not None
            and industry_col is not None
            and quantity_col is not None
        ):
            return row_idx, {
                "security_name": security_col,
                "isin": isin_col,
                "industry_rating": industry_col,
                "quantity": quantity_col,
            }

    return None, {}


# ==============================================================================
# SHEET CLEANING
# ==============================================================================


def clean_sheet(df, sheet_name, fund_name):

    portfolio_date = extract_portfolio_date(df)

    header_row, columns = find_portfolio_header(df)

    if header_row is None:
        raise ValueError(
            "Header row not found. Expected a holdings header containing "
            "'Name of the Instrument', 'ISIN', 'Industry', and 'Quantity'."
        )

    data = df.iloc[header_row + 1 :].reset_index(drop=True)

    data = data.dropna(how="all")

    security_col = columns["security_name"]
    isin_col = columns["isin"]
    industry_col = columns["industry_rating"]
    quantity_col = columns["quantity"]

    # --------------------------------------------------------------------------
    # ORIGINAL ABSL STOP RULE:
    #
    # Scan the Name of Instrument / Issuer column and STOP at the first row
    # containing the word "Total".
    #
    # This is deliberately retained from the original ABSL script.
    # --------------------------------------------------------------------------
    name_col = data[security_col].astype(str).str.strip()

    stop_mask = name_col.str.upper().str.contains(
        r"\bTOTAL\b",
        regex=True,
        na=False,
    )

    if stop_mask.any():
        stop_index = stop_mask.idxmax()
        data = data.loc[: stop_index - 1]

    # --------------------------------------------------------------------------
    # Extract required portfolio fields.
    # --------------------------------------------------------------------------
    sub = data[
        [
            security_col,
            isin_col,
            industry_col,
            quantity_col,
        ]
    ].copy()

    sub.columns = [
        "Security_Name",
        "ISIN",
        "Industry_Rating",
        "Quantity",
    ]

    # Keep only valid ISIN rows.
    sub = sub[sub["ISIN"].apply(is_valid_isin)]

    # Quantity must be numeric.
    sub["Quantity"] = pd.to_numeric(
        sub["Quantity"],
        errors="coerce",
    )

    sub = sub[sub["Quantity"].notna()]

    # Clean text.
    sub["Security_Name"] = sub["Security_Name"].astype(str).str.strip()

    sub["Industry_Rating"] = sub["Industry_Rating"].fillna("").astype(str).str.strip()

    # --------------------------------------------------------------------------
    # IMPORTANT:
    # Fund_Name comes ONLY from the June canonical mapping.
    # --------------------------------------------------------------------------
    sub.insert(0, "AMC", AMC_NAME)
    sub.insert(1, "Fund_Name", fund_name)
    sub.insert(2, "Portfolio_Date", portfolio_date)
    sub.insert(
        3,
        "Month",
        (portfolio_date.strftime("%b-%Y") if pd.notna(portfolio_date) else ""),
    )

    final_columns = [
        "AMC",
        "Fund_Name",
        "Portfolio_Date",
        "Month",
        "Security_Name",
        "ISIN",
        "Industry_Rating",
        "Quantity",
    ]

    return sub[final_columns]


# ==============================================================================
# MONTHLY WORKBOOK PROCESSING
# ==============================================================================


def process_workbook(
    workbook_path,
    processed_keys,
    fund_name_mapping,
):
    """
    Current workbook supplies:
        sheet/code + holdings

    June canonical workbook supplies:
        Fund_Name
    """

    print("\n" + "=" * 90)
    print(f"Workbook: {workbook_path.name}")
    print("=" * 90)

    xls = pd.ExcelFile(
        workbook_path,
        engine=excel_engine_for(workbook_path),
    )

    cleaned_data = []

    for sheet in TARGET_SHEETS:

        if sheet not in xls.sheet_names:
            print(f"{sheet:<12} | Sheet not found")
            continue

        if sheet not in fund_name_mapping:
            print(f"{sheet:<12} | No June canonical fund name")
            continue

        try:
            df = pd.read_excel(
                xls,
                sheet_name=sheet,
                header=None,
            )

            # The code/sheet is from the CURRENT monthly workbook.
            # The name is from JUNE.
            fund_name = fund_name_mapping[sheet]

            portfolio_date = extract_portfolio_date(df)
            month_key = get_month_key(portfolio_date)

            if (fund_name, month_key) in processed_keys:
                print(f"{sheet:<12} | " f"{fund_name:<45} | Already processed")
                continue

            cleaned_df = clean_sheet(
                df,
                sheet,
                fund_name,
            )

            if cleaned_df.empty:
                print(f"{sheet:<12} | " f"{fund_name:<45} | 0 valid rows")
                continue

            cleaned_data.append(cleaned_df)

            processed_keys.add((fund_name, month_key))

            date_text = (
                portfolio_date.strftime("%b-%Y") if pd.notna(portfolio_date) else "N/A"
            )

            print(
                f"{sheet:<12}"
                f" | {fund_name:<45}"
                f" | Rows: {len(cleaned_df)}"
                f" | Date: {date_text}"
            )

        except Exception as e:
            print(f"{sheet:<12} | ERROR -> {e}")

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
    print("Cleaning ABSL Monthly Portfolio Files")
    print("=" * 90)

    # --------------------------------------------------------------------------
    # 1. June = canonical Fund_Name source.
    # --------------------------------------------------------------------------
    canonical_workbook = find_canonical_workbook()

    fund_name_mapping = load_canonical_fund_names(canonical_workbook)

    # --------------------------------------------------------------------------
    # 2. Find all monthly workbooks.
    # --------------------------------------------------------------------------
    workbook_files = find_all_workbooks()

    if not workbook_files:
        raise FileNotFoundError(f"No ABSL workbooks found in:\n{RAW_FOLDER}")

    print(f"Canonical Fund_Name source: {canonical_workbook.name}")
    print(f"Monthly workbooks found: {len(workbook_files)}")

    all_data = []
    existing_df = None
    processed_keys = set()

    # --------------------------------------------------------------------------
    # 3. Existing cleaned output.
    # --------------------------------------------------------------------------
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
                print(
                    "Existing output is missing required columns. "
                    "Reprocessing all ABSL files."
                )
                existing_df = None
            else:
                processed_keys = get_processed_keys(existing_df)

                print(
                    f"Existing output found: "
                    f"{len(processed_keys)} fund-month combinations "
                    "already processed"
                )

        except Exception as e:
            print("Could not read existing output. " "Reprocessing all ABSL files.")
            print("Reason:", e)

            existing_df = None
            processed_keys = set()

    # --------------------------------------------------------------------------
    # 4. Process all monthly workbooks.
    # --------------------------------------------------------------------------
    for workbook in workbook_files:

        cleaned = process_workbook(
            workbook,
            processed_keys,
            fund_name_mapping,
        )

        if not cleaned.empty:
            all_data.append(cleaned)

    # --------------------------------------------------------------------------
    # 5. Nothing new.
    # --------------------------------------------------------------------------
    if not all_data:
        if existing_df is not None:
            print("\nNo new ABSL data found. Existing cleaned file preserved.")
            print("Output:", OUTPUT_FILE)
            return

        raise ValueError("No cleaned data produced.")

    # --------------------------------------------------------------------------
    # 6. Combine.
    # --------------------------------------------------------------------------
    new_df = pd.concat(
        all_data,
        ignore_index=True,
    )

    if existing_df is not None and not existing_df.empty:
        final_df = pd.concat(
            [existing_df, new_df],
            ignore_index=True,
        )
    else:
        final_df = new_df

    # --------------------------------------------------------------------------
    # 7. Final cleanup.
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
        ]
    )

    final_df.reset_index(
        drop=True,
        inplace=True,
    )

    # --------------------------------------------------------------------------
    # 8. Write output.
    # --------------------------------------------------------------------------
    if OUTPUT_FILE.exists():
        try:
            OUTPUT_FILE.unlink()
        except PermissionError:
            print("\nERROR")
            print("Please close:")
            print(OUTPUT_FILE)
            return

    final_df.to_excel(
        OUTPUT_FILE,
        index=False,
    )

    print("\n" + "=" * 90)
    print("ABSL Cleaning Complete")
    print("=" * 90)
    print(f"Workbooks Processed : {len(workbook_files)}")
    print(f"New rows added      : {len(new_df)}")
    print(f"Total rows          : {len(final_df)}")
    print(f"Funds               : {final_df['Fund_Name'].nunique()}")
    print(f"Output              : {OUTPUT_FILE}")


# ==============================================================================
# RUN
# ==============================================================================

if __name__ == "__main__":
    main()
