import re
from datetime import datetime
from pathlib import Path
import requests
from urllib.parse import urljoin, unquote

# ============================================================================
# CONFIGURATION
# ============================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "PPFAS"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)
BASE_URL = "https://amc.ppfas.com"
PAGE_URL = BASE_URL + "/downloads/portfolio-disclosure/"
START_YEAR = 2024
START_MONTH = 10
END_YEAR = datetime.now().year
TIMEOUT = 60
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    )
}

MONTHS = {
    'january': 1,
    'february': 2,
    'march': 3,
    'april': 4,
    'may': 5,
    'june': 6,
    'july': 7,
    'august': 8,
    'september': 9,
    'october': 10,
    'november': 11,
    'december': 12,
}


def print_sep(char='=', width=100):
    print(char * width)


def sanitize_filename(value: str) -> str:
    value = unquote(value)
    for invalid in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
        value = value.replace(invalid, "-")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def fetch_page(url: str) -> str:
    print(f"Fetching PPFAS portfolio page: {url}")
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def find_consolidated_links(html: str):
    # Matches relative links for consolidated monthly files like:
    # /downloads/portfolio-disclosure/2026/PPFAS_Monthly_Portfolio_Report_June_30_2026.xls?08072026_1
    pattern = re.compile(r'href="(?P<href>/downloads/portfolio-disclosure/(?P<year>\d{4})/(?P<fname>PPFAS_Monthly_Portfolio_Report_[^\"]+?\.(?:xls|xlsx)(?:\?[^\"]*)?))"', re.IGNORECASE)
    matches = pattern.finditer(html)
    results = []
    for m in matches:
        href = m.group('href')
        year = int(m.group('year'))
        fname = m.group('fname')
        # Try to extract month name from filename
        month_match = re.search(r'PPFAS_Monthly_Portfolio_Report_([A-Za-z]+)_30_(' + str(year) + r')', fname, re.IGNORECASE)
        month_num = None
        if month_match:
            month_name = month_match.group(1).lower()
            month_num = MONTHS.get(month_name)
        # fallback: try to find any month name
        if month_num is None:
            for name, num in MONTHS.items():
                if name[:3] in fname.lower():
                    month_num = num
                    break
        results.append((year, month_num, href))
    # deduplicate by href
    unique = []
    seen = set()
    for item in results:
        if item[2] not in seen:
            unique.append(item)
            seen.add(item[2])
    return unique


def build_save_path(year: int, month: int, href: str) -> Path:
    folder = RAW_FOLDER / str(year) / f"{month:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    # Remove any URL query parameters so extension remains correct
    parsed = href.split('/')[-1].split('?')[0]
    filename = sanitize_filename(parsed)

    save_path = folder / filename

    # If the cleaned filename already exists, append a numeric suffix before the extension
    if save_path.exists():
        stem = save_path.stem
        suffix = save_path.suffix
        counter = 1
        while True:
            candidate = folder / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                save_path = candidate
                break
            counter += 1

    return save_path


def download_file(url: str, save_path: Path) -> bool:
    if save_path.exists():
        print(f"Skipping existing: {save_path}")
        return False
    full_url = urljoin(BASE_URL, url)
    print(f"Downloading {full_url} -> {save_path}")
    r = requests.get(full_url, headers=HEADERS, timeout=TIMEOUT, stream=True)
    r.raise_for_status()
    with open(save_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return True


def main():
    print_sep()
    print("Downloading PPFAS consolidated monthly portfolio files (from Oct 2024)")
    print_sep()

    html = fetch_page(PAGE_URL)
    links = find_consolidated_links(html)

    total = 0
    downloaded = 0
    skipped = 0

    for year, month, href in sorted(links):
        # if month could not be determined, skip with a warning
        if month is None:
            print(f"Could not determine month for link: {href} (year {year}) - skipping")
            continue
        if year < START_YEAR or (year == START_YEAR and month < START_MONTH):
            continue
        total += 1
        save_path = build_save_path(year, month, href)
        try:
            if download_file(href, save_path):
                downloaded += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"ERROR downloading {href}: {e}")

    print_sep()
    print(f"Total candidates found: {total}")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped existing: {skipped}")
    print(f"Output root: {RAW_FOLDER}")
    print_sep()


if __name__ == '__main__':
    main()
