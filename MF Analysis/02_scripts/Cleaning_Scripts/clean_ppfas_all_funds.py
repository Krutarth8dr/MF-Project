import re
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "PPFAS"
OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "PPFAS"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_FOLDER / "PPFAS_All_Funds_Cleaned.xlsx"
AMC_NAME = "PPFAS Mutual Fund"
START_DATE = pd.Timestamp(year=2024, month=10, day=1)

TARGET_SHEETS = [
    "PPLCF",
    "PPTSF",
    "PPFCF",
]

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
    return bool(re.fullmatch(r"IN[A-Z0-9]{10}", value))


def reduce_fund_name(name: str) -> str:
    """Reduce a fund display name by removing any parenthetical text and trimming whitespace.
    Example: 'Parag Parikh Flexi Cap Fund (An open-ended ...)' -> 'Parag Parikh Flexi Cap Fund'
    """
    if not name:
        return name
    s = str(name).strip()
    # Remove anything from the first '('
    idx = s.find('(')
    if idx != -1:
        s = s[:idx]
    return s.strip()


def extract_portfolio_date_from_filename(workbook_path):
    file_name = Path(workbook_path).stem
    # Handle filenames like ..._June_30_2026 or ..._October_31_2024 or ..._February_28_2025
    m = re.search(r"_([A-Za-z]+)_(?:28|30|31)_(\d{4})", file_name)
    if not m:
        # try other common pattern without underscores
        m2 = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", file_name)
        if m2:
            month_name = m2.group(1).lower()
            year = int(m2.group(3))
        else:
            raise ValueError(f"Unable to extract date from filename: {file_name}")
    else:
        month_name = m.group(1).lower()
        year = int(m.group(2))

    month_map = {
        'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
        'july':7,'august':8,'september':9,'october':10,'november':11,'december':12
    }
    month = month_map.get(month_name)
    if not month:
        raise ValueError(f"Unknown month name in filename: {file_name}")
    return pd.Timestamp(year=year, month=month, day=1)


def find_header_row_and_fundname(excel, sheet_name):
    preview = pd.read_excel(
        excel,
        sheet_name=sheet_name,
        header=None,
        nrows=8,
    )

    # Try to get fund display name from preview cell [0,1] if present
    fund_name = None
    try:
        candidate = str(preview.iloc[0, 1])
        if candidate and candidate.strip() and 'monthly portfolio' not in candidate.lower():
            fund_name = candidate.strip()
    except Exception:
        fund_name = None

    # locate header row containing 'Name of the Instrument'
    header_row = None
    for i in range(len(preview)):
        row = preview.iloc[i].astype(str).fillna("")
        if any('name of the instrument' in str(x).lower() for x in row):
            header_row = i
            break

    return header_row, fund_name


def load_canonical_fund_names():
    """
    Loads canonical fund display names from the June-2026 consolidated workbook.
    Returns a mapping of sheet_code -> display name (e.g., 'PPFCF' -> 'Parag Parikh Flexi Cap Fund ...').
    """
    mapping = {}
    canonical_folder = RAW_FOLDER / '2026' / '06'
    if not canonical_folder.exists():
        print(f'Canonical folder not found: {canonical_folder} - falling back to sheet codes')
        return mapping

    candidates = list(canonical_folder.glob('PPFAS_Monthly_Portfolio_Report_June_30_2026.*'))
    if not candidates:
        print(f'No canonical June-2026 workbook found in {canonical_folder} - falling back to sheet codes')
        return mapping

    excel = pd.ExcelFile(candidates[0])
    for sheet in TARGET_SHEETS:
        if sheet in excel.sheet_names:
            try:
                preview = pd.read_excel(excel, sheet_name=sheet, header=None, nrows=1)
                candidate = str(preview.iloc[0, 1]).strip()
                mapping[sheet] = reduce_fund_name(candidate) if candidate else sheet
                print(f'Canonical: {sheet} -> {mapping[sheet]}')
            except Exception as e:
                print(f'Could not read canonical name for sheet {sheet}: {e}')
                mapping[sheet] = sheet
        else:
            print(f'Canonical workbook missing sheet {sheet} - will use sheet code as name')
            mapping[sheet] = sheet

    return mapping


def clean_single_sheet(excel, sheet_name, workbook_path):
    header_row, fund_name = find_header_row_and_fundname(excel, sheet_name)
    if header_row is None:
        raise ValueError(f"Could not find header row in sheet {sheet_name} of {workbook_path.name}")

    df = pd.read_excel(
        excel,
        sheet_name=sheet_name,
        header=header_row,
    )

    # Standardize columns
    df.columns = [str(col).replace('\n', ' ').replace('\r', ' ').strip() for col in df.columns]

    rename_map = {}
    for col in df.columns:
        n = str(col).strip().lower()
        if n == 'name of the instrument':
            rename_map[col] = 'Security_Name'
        elif n == 'isin':
            rename_map[col] = 'ISIN'
        elif n.startswith('industry') or 'industry' in n or 'rating' in n:
            rename_map[col] = 'Industry_Rating'
        elif n == 'quantity':
            rename_map[col] = 'Quantity'

    df = df.rename(columns=rename_map)

    required = ['Security_Name','ISIN','Industry_Rating','Quantity']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns {missing} in {workbook_path.name} sheet {sheet_name}")

    df = df[required].copy().reset_index(drop=True)

    # Stop scanning when 'Arbitrage' or 'Sub Total' appears in Security_Name
    stop_mask = df['Security_Name'].fillna('').astype(str).str.strip().str.lower().str.contains(r'arbitrage|sub total')
    if stop_mask.any():
        first_idx = stop_mask.idxmax()
        df = df.iloc[:first_idx]

    # Cleanup fields
    df['ISIN'] = df['ISIN'].fillna('').astype(str).str.strip()
    df['Security_Name'] = df['Security_Name'].fillna('').astype(str).str.strip()
    df['Industry_Rating'] = df['Industry_Rating'].fillna('').astype(str).str.strip()
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')

    # Keep only valid ISINs and numeric quantities
    df = df[df['ISIN'].apply(is_valid_isin)]
    df = df[df['Quantity'].notna()]

    # Attempt to extract portfolio date from filename
    portfolio_date = extract_portfolio_date_from_filename(workbook_path.name)
    month_label = portfolio_date.strftime('%b-%Y')

    # If fund_name not found earlier, try to extract from sheet top cell
    if not fund_name or not fund_name.strip():
        # try reading first few rows from sheet
        preview2 = pd.read_excel(excel, sheet_name=sheet_name, header=None, nrows=2)
        try:
            candidate = str(preview2.iloc[0,1])
            fund_name = candidate.strip() if candidate and candidate.strip() else sheet_name
        except Exception:
            fund_name = sheet_name

    # Reduce fund name to text before any parenthesis
    fund_name = reduce_fund_name(fund_name)

    df.insert(0, 'AMC', AMC_NAME)
    df.insert(1, 'Fund_Name', fund_name)
    df.insert(2, 'Portfolio_Date', portfolio_date)
    df.insert(3, 'Month', month_label)

    df = df[STANDARD_COLUMNS]
    return df


def get_processed_keys(existing_df):
    existing_df = existing_df.copy()
    existing_df['Portfolio_Date'] = pd.to_datetime(existing_df['Portfolio_Date'], errors='coerce')
    existing_df['Portfolio_Date'] = existing_df['Portfolio_Date'].apply(lambda x: pd.Timestamp(year=x.year, month=x.month, day=1) if pd.notna(x) else pd.NaT)
    existing_df['Month_Key'] = existing_df['Portfolio_Date'].dt.strftime('%Y-%m')
    existing_df = existing_df[existing_df['Fund_Name'].notna() & existing_df['Month_Key'].notna()]
    return set(zip(existing_df['Fund_Name'], existing_df['Month_Key']))


def process_workbook(workbook_path, processed_keys, fund_name_mapping):
    excel = pd.ExcelFile(workbook_path)
    # Try to extract portfolio date for processed key
    try:
        portfolio_date = extract_portfolio_date_from_filename(workbook_path.name)
        month_key = portfolio_date.strftime('%Y-%m')
    except Exception:
        month_key = None

    cleaned_all = []
    for sheet in TARGET_SHEETS:
        if sheet not in excel.sheet_names:
            print(f"Sheet {sheet} not found in {workbook_path.name}")
            continue
        try:
            # Determine fund_name from canonical mapping first
            fund_name = fund_name_mapping.get(sheet) if fund_name_mapping else None

            # If not available, preview to get fund name
            if not fund_name:
                header_row, fund_name_preview = find_header_row_and_fundname(excel, sheet)
                if fund_name_preview:
                    fund_name = reduce_fund_name(fund_name_preview)

            if not fund_name:
                # attempt to pull fund name from cell [0,1]
                preview = pd.read_excel(excel, sheet_name=sheet, header=None, nrows=1)
                try:
                    fund_name = reduce_fund_name(str(preview.iloc[0,1]).strip())
                except Exception:
                    fund_name = sheet

            if month_key and (fund_name, month_key) in processed_keys:
                print(f"Skipping already processed: {fund_name} {month_key}")
                continue

            cleaned = clean_single_sheet(excel, sheet, workbook_path)
            cleaned_all.append(cleaned)
            if month_key:
                processed_keys.add((fund_name, month_key))
            print(f"Processed {workbook_path.name} | {sheet} | rows: {len(cleaned)}")
        except Exception as e:
            print(f"ERROR processing {workbook_path.name} sheet {sheet}: {e}")

    if cleaned_all:
        return pd.concat(cleaned_all, ignore_index=True)
    return pd.DataFrame()


def main():
    print('='*100)
    print('Cleaning PPFAS Monthly Portfolio Files')
    print('='*100)

    if not RAW_FOLDER.exists():
        raise FileNotFoundError(f'Raw folder not found: {RAW_FOLDER}')

    workbooks = sorted(RAW_FOLDER.rglob('PPFAS_Monthly_Portfolio_Report_*'))
    if not workbooks:
        raise FileNotFoundError(f'No PPFAS workbooks found under: {RAW_FOLDER}')

    existing_df = None
    processed_keys = set()
    if OUTPUT_FILE.exists():
        try:
            existing_df = pd.read_excel(OUTPUT_FILE)
            processed_keys = get_processed_keys(existing_df)
            print(f'Existing output found: {len(processed_keys)} fund-month combinations')
        except Exception as e:
            print('Could not read existing output:', e)
            existing_df = None
            processed_keys = set()

    all_data = []
    # Load canonical fund names from June-2026 workbook (used as canonical mapping)
    fund_name_mapping = load_canonical_fund_names()

    for wb in workbooks:
        try:
            # filter by start date using filename
            try:
                pd_date = extract_portfolio_date_from_filename(wb.name)
                if pd_date < START_DATE:
                    print(f"Skipping {wb.name} before start date")
                    continue
            except Exception:
                # If unable to parse date from filename, process anyway
                pass

            cleaned = process_workbook(wb, processed_keys, fund_name_mapping)
            if not cleaned.empty:
                all_data.append(cleaned)
        except Exception as e:
            print(f"ERROR processing workbook {wb.name}: {e}")

    if not all_data:
        print('\nNo new PPFAS data found.')
        return

    new_df = pd.concat(all_data, ignore_index=True)
    if existing_df is not None and not existing_df.empty:
        final_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        final_df = new_df

    final_df.to_excel(OUTPUT_FILE, index=False)
    print(f'Wrote cleaned PPFAS data to: {OUTPUT_FILE}')


if __name__ == '__main__':
    main()
