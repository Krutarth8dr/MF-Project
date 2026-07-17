"""
Enumerate BOI monthly portfolio files by constructing likely filenames for end-of-month dates.
Attempts to download files from Oct-2024 up to current month.
"""
import requests
from datetime import date, datetime
import calendar
import os
from urllib.parse import urljoin

BASE_DIR = r"D:\MF Project\MF Analysis\01_raw_files\BOI"
BASE_DOCS = 'https://www.boimf.in/docs/default-source/investorcorner/monthly-portfolio/'
START = date(2024, 10, 1)
TODAY = date.today()

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
})


def last_day_of_month(yr, m):
    return calendar.monthrange(yr, m)[1]


def sanitize_filename(name):
    return name.replace(' ', '_')


def ensure_dir(p):
    if not os.path.exists(p):
        os.makedirs(p, exist_ok=True)


def try_download(year, month):
    day = last_day_of_month(year, month)
    month_name = datetime(year, month, day).strftime('%B').lower()
    # try both .xlsx and .xls
    exts = ['.xlsx', '.xls']
    for ext in exts:
        filename = f"monthly-portfolio---{day}-{month_name}-{year}{ext}"
        url = urljoin(BASE_DOCS, filename)
        try:
            r = session.head(url, allow_redirects=True, timeout=20)
            if r.status_code == 200:
                # download
                dest_dir = os.path.join(BASE_DIR, str(year), f"{month:02d}")
                ensure_dir(dest_dir)
                print(f"Downloading {url} -> {dest_dir}")
                r2 = session.get(url, stream=True, timeout=60)
                if r2.status_code == 200:
                    path = os.path.join(dest_dir, sanitize_filename(filename))
                    with open(path, 'wb') as fh:
                        for chunk in r2.iter_content(1024*64):
                            fh.write(chunk)
                    print('Saved ->', path)
                    return True
                else:
                    print('GET failed', r2.status_code)
            else:
                print('Not found:', url, r.status_code)
        except Exception as e:
            print('Error requesting', url, e)
    return False


def main():
    y = START.year
    m = START.month
    while (y, m) <= (TODAY.year, TODAY.month):
        try_download(y, m)
        # increment month
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1

if __name__ == '__main__':
    main()
