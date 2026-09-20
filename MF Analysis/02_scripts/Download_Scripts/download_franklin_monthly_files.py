import urllib.request
import json
import re
from pathlib import Path
import time

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

RAW_DIR = Path(__file__).resolve().parents[2] / "01_raw_files" / "FRANKLIN"
RAW_DIR.mkdir(parents=True, exist_ok=True)


# Load the API report JSON
json_path = Path(r'C:\Users\Krutarth\.gemini\antigravity\brain\db78f6aa-4677-4939-948c-dab195a25360\scratch\report_response.json')
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

first_drop = data.get('FirstDropDown', [])
records = []
for item in first_drop:
    if item.get('id') == 'MONTHLY-PORTFOLIO-DSCLR':
        records = item.get('dataRecords', {}).get('linkdata', [])
        break

month_order = {'jan':1, 'feb':2, 'mar':3, 'apr':4, 'may':5, 'jun':6, 'june':6, 'jul':7, 'july':7, 'aug':8, 'sep':9, 'sept':9, 'oct':10, 'nov':11, 'dec':12}

target_files = []
for r in records:
    href = r.get('literatureHref', '')
    fname = href.split('/')[-1] if href else ''
    m = re.search(r'Monthly-Portfolio-ISIN-\d{1,2}-([a-zA-Z]+)-(\d{4})\.xlsx', fname)
    if m:
        mon = m.group(1).lower()
        yr = int(m.group(2))
        m_num = month_order.get(mon[:3], 0)
        if (yr == 2024 and m_num >= 10) or (yr == 2025) or (yr == 2026 and m_num <= 8):
            target_files.append((yr, m_num, fname, href))

target_files.sort(key=lambda x: (x[0], x[1]))
print(f"Total target files to verify/download: {len(target_files)}")

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

for yr, m_num, fname, href in target_files:
    dest = RAW_DIR / fname
    if dest.exists() and dest.stat().st_size > 100000:
        print(f"✓ Already exists: {fname} ({dest.stat().st_size:,} bytes)")
        continue

    full_url = f"https://www.franklintempletonindia.com/download{href}"
    print(f"Downloading {yr}-{m_num:02d} ({fname})...")
    req = urllib.request.Request(full_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp, open(dest, 'wb') as out_f:
            out_f.write(resp.read())
        print(f"   [OK] Saved {dest.name} ({dest.stat().st_size:,} bytes)")
    except Exception as e:
        print(f"   [ERROR] Failed {fname}: {e}")
    time.sleep(0.3)

print("\nAll downloads finished!")
