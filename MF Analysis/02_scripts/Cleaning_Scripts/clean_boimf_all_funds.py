"""
Cleaning script for Bank Of India monthly consolidated workbooks.

Behavior:
- Target sheets: provided list
- Use the June-2026 workbook as canonical source for Fund_Name per sheet
- For each sheet in each monthly workbook (Oct-2024 onward):
  - Find header row by scanning for "Name of the Instrument" in the first 12 rows
  - Read data with that header, find the column for Security name / Instrument and ISIN and Quantity
  - Take all rows above the row where Security Name contains "Sub Total" (case-insensitive)
  - Validate ISINs using regex r"IN[A-Z0-9]{10}" and ensure numeric Quantity
  - Produce cleaned output with columns: [AMC, Fund_Name, Portfolio_Date, Month, Security_Name, ISIN, Industry_Rating, Quantity]

Saves output to: D:\MF Project\MF Analysis\03_clean_data\BOI\BOI_All_Funds_Cleaned.xlsx
"""

import pandas as pd
import re
import os
from datetime import datetime, date
from glob import glob

ROOT_RAW = r"D:\MF Project\MF Analysis\01_raw_files\BOI"
ROOT_CLEAN = r"D:\MF Project\MF Analysis\03_clean_data\BOI"
CANONICAL_JUNE = os.path.join(ROOT_RAW, '2026', '06', 'monthly-portfolio---30-june-2026.xlsx')
TARGET_SHEETS = ["YB04","YB07","YB08","YB09","YB21","YB30","YB31","YB33","YB34","YB36","YB37","YB38","YB39","YB40","YB41","YB43","YB44"]
START_DATE = date(2024, 10, 1)
AMC_NAME = "Bank Of India"
ISIN_RE = re.compile(r"IN[A-Z0-9]{10}")

STANDARD_COLUMNS = ["AMC","Fund_Name","Portfolio_Date","Month","Security_Name","ISIN","Industry_Rating","Quantity"]


def find_header_row(sheet_df_preview):
    # sheet_df_preview: DataFrame read with header=None for first ~12 rows
    for idx in range(min(12, len(sheet_df_preview))):
        row = sheet_df_preview.iloc[idx].astype(str).str.lower()
        if row.str.contains('name of the instrument').any() or row.str.contains('name of the instrument / issuer').any():
            return idx
    # fallback: search for 'isin' header
    for idx in range(min(12, len(sheet_df_preview))):
        row = sheet_df_preview.iloc[idx].astype(str).str.lower()
        if row.str.contains('isin').any():
            return idx
    return 0


def reduce_fund_name(s: str) -> str:
    if not isinstance(s, str):
        return s
    # remove everything from first '(' onward
    i = s.find('(')
    if i != -1:
        s = s[:i]
    s = s.strip()
    # remove common prefixes like 'Name of Mutual Fund :' and similar
    s = re.sub(r'(?i)name of mutual fund\s*:\s*', '', s).strip()
    s = re.sub(r'(?i)name of the mutual fund\s*:\s*', '', s).strip()
    s = re.sub(r'(?i)fund name\s*:\s*', '', s).strip()
    return s


def load_canonical_fund_names(june_path, sheets):
    """
    Preferentially load canonical fund names from an 'Index' sheet in the June workbook.
    The Index sheet should contain 'Scheme Code' and 'Scheme Names' columns. Use that mapping
    for sheet codes (e.g., 'YB04' -> 'Bank of India XYZ Fund'). Trim at '('.
    If Index sheet or columns are not present, fall back to the previous heuristic search.
    """
    mapping = {}
    if not os.path.exists(june_path):
        print(f"June canonical workbook not found at {june_path}. Falling back to sheet codes as fund names.")
        for sh in sheets:
            mapping[sh] = sh
        return mapping

    try:
        xls = pd.ExcelFile(june_path)
    except Exception:
        print(f"Cannot open June workbook {june_path}; falling back to sheet codes")
        for sh in sheets:
            mapping[sh] = sh
        return mapping

    # Try Index sheet
    index_sheet_name = None
    for candidate in ['Index', 'INDEX', 'index']:
        if candidate in xls.sheet_names:
            index_sheet_name = candidate
            break
    if index_sheet_name:
        try:
            idx_df = pd.read_excel(june_path, sheet_name=index_sheet_name)
            # find columns case-insensitively
            cols = {c.lower(): c for c in idx_df.columns}
            code_col = None
            name_col = None
            for k in cols:
                if 'scheme code' == k or k.endswith('scheme code') or ('code' in k and 'scheme' in k):
                    code_col = cols[k]
                if 'scheme names' == k or 'scheme name' == k or ('scheme' in k and 'name' in k) or ('scheme' in k and 'names' in k):
                    name_col = cols[k]
            # if ambiguous detection, try to find columns by heuristics
            if not code_col or not name_col:
                # look for any column that contains any of the TARGET_SHEETS codes in its values
                for c in idx_df.columns:
                    sample_vals = idx_df[c].dropna().astype(str).str.strip().head(20).tolist()
                    if any(str(s) in sheets for s in sample_vals):
                        code_col = c
                        break
                # find name column as the other text column
                if code_col:
                    for c in idx_df.columns:
                        if c == code_col:
                            continue
                        # choose col with 'Fund' or long text
                        sample_vals = idx_df[c].dropna().astype(str).str.strip().head(20).tolist()
                        if any('fund' in str(s).lower() or 'bank' in str(s).lower() or len(str(s))>20 for s in sample_vals):
                            name_col = c
                            break
            if code_col and name_col:
                # ensure code_col contains actual codes and name_col contains names; if reversed, swap
                sample_codes = idx_df[code_col].dropna().astype(str).str.strip().head(20).tolist()
                sample_names = idx_df[name_col].dropna().astype(str).str.strip().head(20).tolist()
                code_like = sum(1 for v in sample_codes if re.match(r'^[A-Za-z0-9\-\s]+$', v) and len(v)<=20)
                name_like = sum(1 for v in sample_names if any(x in str(v).lower() for x in ['fund','bank','scheme']))
                # if samples suggest they are swapped, swap them
                if name_like < code_like and any(re.match(r'^[A-Za-z]{1,3}\d{1,3}$', str(v)) for v in sample_names):
                    # likely swapped
                    code_col, name_col = name_col, code_col
                for _, r in idx_df.iterrows():
                    code = str(r.get(code_col, '')).strip()
                    name = r.get(name_col, '')
                    if pd.isna(name):
                        name = ''
                    name = str(name).strip()
                    if not code or not name:
                        continue
                    # sanity: ensure code contains letters and digits (avoid stray text rows)
                    if not (re.search('[A-Za-z]', code) and re.search('\d', code)):
                        continue
                    # reduce up to first '('
                    i = name.find('(')
                    if i != -1:
                        name = name[:i].strip()
                    mapping[code] = name
                # now ensure all target sheets are present in mapping, else fallback for missing
                for sh in sheets:
                    if sh not in mapping:
                        mapping[sh] = sh
                return mapping
            else:
                print('Index sheet found but could not locate Scheme Code/Names columns; falling back to heuristic')
        except Exception as e:
            print('Failed to read Index sheet:', e)

    # Fallback: previous heuristic
    for sh in sheets:
        if sh not in xls.sheet_names:
            mapping[sh] = sh
            continue
        # read a larger preview area to robustly find title/fund name
        try:
            preview = pd.read_excel(june_path, sheet_name=sh, header=None, nrows=20)
        except Exception:
            mapping[sh] = sh
            continue
        header_row = find_header_row(preview)
        # search for candidate strings in first 10 rows and columns
        candidate = None
        max_len = 0
        rows_to_search = min(preview.shape[0], max(12, header_row))
        cols_to_search = min(preview.shape[1], 8)
        for r in range(0, rows_to_search):
            for c in range(0, cols_to_search):
                try:
                    val = preview.iat[r, c]
                except Exception:
                    continue
                if isinstance(val, str):
                    txt = val.strip()
                    if not txt:
                        continue
                    low = txt.lower()
                    # skip generic labels
                    if any(x in low for x in ['name of mutual fund', 'name of the mutual fund', 'portfolio', 'name of the instrument']):
                        continue
                    # prefer longer descriptive strings
                    if len(txt) > max_len and len(txt) > 5:
                        candidate = txt
                        max_len = len(txt)
        if not candidate:
            # fallback: try to find any cell containing 'Fund' or 'Scheme' that is longer
            for r in range(0, rows_to_search):
                for c in range(0, cols_to_search):
                    try:
                        val = preview.iat[r, c]
                    except Exception:
                        continue
                    if isinstance(val, str) and ('fund' in val.lower() or 'scheme' in val.lower()):
                        txt = val.strip()
                        if len(txt) > max_len:
                            candidate = txt
                            max_len = len(txt)
        if not candidate:
            mapping[sh] = sh
        else:
            mapping[sh] = reduce_fund_name(candidate)
    return mapping

def parse_portfolio_date_from_filename(fname: str):
    # expect patterns like monthly-portfolio---30-june-2026.xlsx
    m = re.search(r'monthly-portfolio---(\d{1,2})-([a-zA-Z]+)-(\d{4})', fname, re.IGNORECASE)
    if m:
        day = int(m.group(1))
        mon_str = m.group(2)
        year = int(m.group(3))
        try:
            dt = datetime.strptime(f"{day}-{mon_str}-{year}", "%d-%B-%Y").date()
            return dt
        except Exception:
            try:
                dt = datetime.strptime(f"{day}-{mon_str}-{year}", "%d-%b-%Y").date()
                return dt
            except Exception:
                return None
    return None


def find_column_by_keywords(cols, keywords):
    cols_l = [str(c).lower() for c in cols]
    for kw in keywords:
        for i, c in enumerate(cols_l):
            if kw in c:
                return cols[i]
    return None


def clean_single_sheet(df, security_col, isin_col, qty_col, rating_col=None):
    out = []
    stop_idx = None
    # find first row where security contains 'sub total'
    sec_series = df[security_col].astype(str).fillna('').str.strip()
    mask = sec_series.str.lower().str.contains('sub total') | sec_series.str.lower().str.contains('subtotal')
    if mask.any():
        stop_idx = mask.idxmax()
    # take rows up to stop_idx - 1 (if stop_idx found), else all
    if stop_idx is not None:
        df_proc = df.loc[:stop_idx-1]
    else:
        df_proc = df
    for _, r in df_proc.iterrows():
        sec = str(r.get(security_col, '')).strip()
        isin = str(r.get(isin_col, '')).strip() if isin_col in df_proc.columns else ''
        qty = r.get(qty_col, None) if qty_col in df_proc.columns else None
        rating = r.get(rating_col, None) if rating_col and rating_col in df_proc.columns else None
        # validate isin
        isin_match = ISIN_RE.search(isin)
        if not isin_match:
            continue
        # validate qty numeric
        try:
            qty_val = float(qty)
        except Exception:
            # try removing commas
            try:
                qty_val = float(str(qty).replace(',', ''))
            except Exception:
                continue
        out.append({'sec': sec, 'isin': isin_match.group(0), 'qty': qty_val, 'rating': rating})
    return out


def main():
    ensure_clean_dir = lambda: os.makedirs(ROOT_CLEAN, exist_ok=True)
    ensure_clean_dir()

    fund_name_map = load_canonical_fund_names(CANONICAL_JUNE, TARGET_SHEETS)
    print('Canonical fund name mapping loaded for sheets:')
    for k, v in fund_name_map.items():
        print(k, '->', v)

    cleaned_rows = []

    # find all monthly files
    files = sorted(glob(os.path.join(ROOT_RAW, '**', 'monthly-portfolio-*.xlsx'), recursive=True)) + sorted(glob(os.path.join(ROOT_RAW, '**', 'monthly-portfolio-*.xls'), recursive=True))
    for fpath in files:
        fname = os.path.basename(fpath)
        pdate = parse_portfolio_date_from_filename(fname)
        if not pdate:
            print('Skipping file (cannot parse date):', fpath)
            continue
        if pdate < START_DATE:
            print('Skipping file (before start):', fpath)
            continue
        portfolio_date = date(pdate.year, pdate.month, 1)
        month_str = pdate.strftime('%b-%Y')
        print('Processing', fpath, 'as', portfolio_date)
        try:
            xls = pd.ExcelFile(fpath)
        except Exception as e:
            print('Failed to open', fpath, e)
            continue
        for sh in TARGET_SHEETS:
            if sh not in xls.sheet_names:
                continue
            try:
                preview = pd.read_excel(fpath, sheet_name=sh, header=None, nrows=12)
            except Exception as e:
                print('Failed preview read for', fpath, sh, e)
                continue
            header_row = find_header_row(preview)
            try:
                df = pd.read_excel(fpath, sheet_name=sh, header=header_row, engine='openpyxl' if fpath.lower().endswith('.xlsx') else None)
            except Exception:
                try:
                    df = pd.read_excel(fpath, sheet_name=sh, header=header_row)
                except Exception as e:
                    print('Failed read with header for', fpath, sh, e)
                    continue
            # normalize column names stripping whitespace
            df.columns = [str(c).strip() for c in df.columns]
            # find columns (broaden rating keywords)
            security_col = find_column_by_keywords(df.columns, ['name of the instrument','name of the instrument / issuer','instrument','security name','security'])
            isin_col = find_column_by_keywords(df.columns, ['isin'])
            qty_col = find_column_by_keywords(df.columns, ['quantity','no. of units','no.of units','units','no. of units (nos)','no of units','holding'])
            rating_col = find_column_by_keywords(df.columns, ['industry','rating','sector','industry / rating','industry/rating','industry and rating','sector / industry'])
            if not rating_col:
                # try alternative names
                rating_col = find_column_by_keywords(df.columns, ['category','classification'])
            if not rating_col:
                # debug: list columns so it's easier to see why rating missing
                print('Rating column not found for', fpath, sh, 'available cols:', df.columns.tolist())
            if not security_col or not isin_col:
                print('Could not find security/isin columns for', fpath, sh, 'cols:', df.columns.tolist())
                continue
            entries = clean_single_sheet(df, security_col, isin_col, qty_col, rating_col)
            fund_name = fund_name_map.get(sh, sh)
            for ent in entries:
                cleaned_rows.append({
                    'AMC': AMC_NAME,
                    'Fund_Name': fund_name,
                    'Portfolio_Date': portfolio_date,
                    'Month': month_str,
                    'Security_Name': ent.get('sec'),
                    'ISIN': ent.get('isin'),
                    'Industry_Rating': ent.get('rating'),
                    'Quantity': ent.get('qty')
                })

    if not cleaned_rows:
        print('No cleaned rows produced')
        return
    out_df = pd.DataFrame(cleaned_rows)
    out_path = os.path.join(ROOT_CLEAN, 'BOI_All_Funds_Cleaned.xlsx')
    # write excel
    try:
        out_df.to_excel(out_path, index=False)
        print('Saved cleaned file to', out_path)
    except Exception as e:
        print('Failed to save cleaned file', e)


if __name__ == '__main__':
    main()
