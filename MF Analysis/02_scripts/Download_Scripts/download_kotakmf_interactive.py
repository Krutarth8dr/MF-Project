"""
Interactive Kotak MF downloader.

Usage (local, interactive):
  - Install dependencies: pip install selenium webdriver-manager requests
  - Run: python download_kotakmf_interactive.py --start-date 2024-10-01

How it works:
  - Launches a visible Chrome browser (not headless).
  - Sets Chrome's download directory to the repository raw folder for KOTAK.
  - Navigates to Kotak's statutory-disclosure page so you can solve any captcha.
  - After solving captcha / ensuring the list is visible, press Enter in the console
    to let the script scan the current page for items containing 'Consolidated' and
    click them.
  - The script watches for the browser to download files and automatically moves
    completed downloads into year/month subfolders under the raw folder.
  - Repeat: navigate pages in the browser and press Enter to process additional pages.

Notes:
  - This is interactive on purpose to avoid bot protection and to let you solve any
    Captcha/Radware challenges.
  - If an automatic click doesn't trigger a download, try clicking the item manually
    in the opened browser; the script will still detect the new file and organize it.
"""

import argparse
import os
import re
import shutil
import sys
import time
import threading
from datetime import datetime, date
from urllib.parse import unquote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

DEFAULT_DOWNLOAD_DIR = r"D:\MF Project\MF Analysis\01_raw_files\KOTAK"
DATE_IN_TITLE_RE = re.compile(
    r"as\s*on\s*([A-Za-z]+)\s*(\d{1,2}),\s*(\d{4})", re.IGNORECASE
)
IS_CONSOLIDATED_RE = re.compile(r"consolidated", re.IGNORECASE)


def sanitize_filename(name: str) -> str:
    if not name:
        return "downloaded_file"
    name = str(name)
    name = name.split("?")[0]
    name = unquote(name)
    name = re.sub(r"[<>:\\\"/\\|?*]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        return "downloaded_file"
    return name


def parse_date_from_text(text: str):
    if not text:
        return None
    m = DATE_IN_TITLE_RE.search(text)
    if m:
        mon = m.group(1)
        day = int(m.group(2))
        yr = int(m.group(3))
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                dt = datetime.strptime(f"{day} {mon} {yr}", fmt).date()
                return dt
            except Exception:
                pass
    # fallback: find 4-digit year
    m2 = re.search(r"(\d{4})", text)
    if m2:
        try:
            y = int(m2.group(1))
            return date(y, 1, 1)
        except Exception:
            return None
    return None


def list_current_files(download_dir):
    """Return a set of filenames currently in the download directory (non-recursive)."""
    try:
        return {f for f in os.listdir(download_dir)}
    except Exception:
        return set()


def wait_for_new_file(download_dir, before_set, timeout=90):
    """Wait for a new, fully-written file to appear in the download dir.

    Returns:
      - the full path to the new file, once its size has stabilized, OR
      - the string 'MOVED_ELSEWHERE' if the file appeared but then disappeared
        before we finished checking it (almost always means the background
        DownloadWatcher thread already grabbed and moved it — that's fine,
        just means the download DID succeed), OR
      - None if no new file ever appeared within `timeout`.
    """
    end = time.time() + timeout
    while time.time() < end:
        cur = set(os.listdir(download_dir))
        added = cur - before_set
        if added:
            # check for a file that's not partial (.crdownload / .tmp)
            for name in sorted(added):
                if name.endswith(".crdownload") or name.endswith(".tmp"):
                    continue
                full = os.path.join(download_dir, name)
                # wait until file size stabilizes (download finished).
                # IMPORTANT: this inner loop must never run unbounded — if the
                # background watcher moves the file out from under us,
                # os.path.getsize() will keep failing forever otherwise.
                last_size = -1
                stable_checks = 0
                missing_checks = 0
                while stable_checks < 6 and time.time() < end:
                    try:
                        size = os.path.getsize(full)
                    except Exception:
                        missing_checks += 1
                        if missing_checks >= 3:
                            # File vanished — something else (the watcher)
                            # already picked it up and moved it. Treat as success.
                            return "MOVED_ELSEWHERE"
                        time.sleep(0.5)
                        continue
                    missing_checks = 0
                    if size == last_size and size > 0:
                        stable_checks += 1
                    else:
                        stable_checks = 0
                    last_size = size
                    time.sleep(0.5)
                if stable_checks >= 6:
                    return full
                # Timed out waiting for stability within the overall window
                return "MOVED_ELSEWHERE" if last_size == -1 else None
        time.sleep(0.5)
    return None


def move_file_to_year_month(file_path, base_root, item_date=None):
    """Move a downloaded file into a YYYY/MM subfolder."""
    if not os.path.exists(file_path):
        return None
    if item_date:
        year = item_date.year
        month = item_date.month
    else:
        st = os.path.getmtime(file_path)
        dt = datetime.fromtimestamp(st)
        year = dt.year
        month = dt.month
    dest_dir = os.path.join(base_root, str(year), f"{month:02d}")
    os.makedirs(dest_dir, exist_ok=True)
    fname = os.path.basename(file_path)
    dest = os.path.join(dest_dir, fname)
    base, ext = os.path.splitext(dest)
    i = 1
    while os.path.exists(dest):
        dest = f"{base}_{i}{ext}"
        i += 1
    shutil.move(file_path, dest)
    return dest


# ---------------------------------------------------------------------------
# Background download watcher – runs in a daemon thread and moves any new
# files that appear in the download directory (e.g. when you click manually).
# ---------------------------------------------------------------------------
class DownloadWatcher:
    """Watches the download directory in a background thread and auto-organizes
    any new files that appear (from manual clicks or any other source)."""

    def __init__(self, download_dir):
        self.download_dir = download_dir
        self._known = list_current_files(download_dir)
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._lock = threading.Lock()
        self.moved_count = 0
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def pause(self):
        """Pause background moving. Call this while the main loop is actively
        clicking + watching for a download itself, to avoid both the watcher
        and the main loop racing to move the same file."""
        self._paused.set()

    def resume(self):
        self._paused.clear()
        self.refresh_known()

    def refresh_known(self):
        """Refresh the known file set (call after an explicit scan/download)."""
        with self._lock:
            self._known = list_current_files(self.download_dir)

    def _run(self):
        while not self._stop.is_set():
            time.sleep(3)
            if self._paused.is_set():
                continue
            current = list_current_files(self.download_dir)
            with self._lock:
                new_files = sorted(current - self._known)
            if not new_files:
                continue
            for name in new_files:
                if name.endswith(".crdownload") or name.endswith(".tmp"):
                    continue
                full = os.path.join(self.download_dir, name)
                # wait briefly for file size to stabilize
                last_size = -1
                for _ in range(6):
                    try:
                        size = os.path.getsize(full)
                    except Exception:
                        size = -1
                    if size == last_size and size > 0:
                        break
                    last_size = size
                    time.sleep(0.5)
                try:
                    # try to parse a date from the filename itself
                    item_date = parse_date_from_text(name)
                    moved = move_file_to_year_month(
                        full, self.download_dir, item_date=item_date
                    )
                    if moved:
                        print(f"  [watcher] Detected and moved: {moved}")
                        self.moved_count += 1
                except Exception as exc:
                    print(f"  [watcher] Failed to move {full}: {exc}")
            self.refresh_known()


# ---------------------------------------------------------------------------
# Dropdown selection – selects "Consolidated & Fortnightly Portfolio"
# ---------------------------------------------------------------------------
def select_consolidated_dropdown(driver):
    """Find and select 'Consolidated & Fortnightly Portfolio' from the
    Portfolios dropdown on the Kotak statutory-disclosure page."""
    try:
        selects = driver.find_elements(By.TAG_NAME, "select")
        for sel in selects:
            opts = sel.find_elements(By.TAG_NAME, "option")
            for o in opts:
                if "consolidated" in o.text.lower():
                    print(f'  Selecting dropdown option: "{o.text.strip()}"')
                    driver.execute_script(
                        "arguments[0].value = arguments[1]; "
                        'arguments[0].dispatchEvent(new Event("change", {bubbles: true}));',
                        sel,
                        o.get_attribute("value"),
                    )
                    time.sleep(2)  # wait for the page to load items
                    return True
    except Exception as exc:
        print(f"  Warning: could not auto-select dropdown: {exc}")
    return False


# ---------------------------------------------------------------------------
# Pagination – Kotak renders pagination as:
#   <li class="pagination-next"><a aria-label=" page">...</a></li>
#   <li class="pagination-next disabled">...</li>   (when on the last page)
# Searching for //a[@aria-label=' page'] and grabbing the LAST match is
# unreliable because the previous button and numbered page links can carry a
# similar aria-label. Targeting the <li class="pagination-next"> wrapper
# directly is unambiguous and also lets us detect the "disabled" (last page)
# state.
# ---------------------------------------------------------------------------
def _page_signature(driver):
    """A cheap fingerprint of the currently-listed items, used to detect when
    Kotak's Angular app has actually finished swapping in the next page's
    content (vs. just having started the transition)."""
    try:
        return driver.execute_script(
            "var els = document.querySelectorAll('*');"
            "var txt = '';"
            "for (var i = 0; i < els.length; i++) {"
            "  var t = els[i].textContent || '';"
            "  if (t.toLowerCase().indexOf('consolidated') !== -1) { txt += t.slice(0,60); }"
            "}"
            "return txt.length + ':' + txt.slice(0,300);"
        )
    except Exception:
        return None


def go_to_next_page(driver):
    """Click Kotak's pagination 'Next' control. Returns True once the page's
    content has actually refreshed (not just after the click), False if no
    next page / no button could be found."""
    before_sig = _page_signature(driver)

    def _wait_for_refresh():
        # Poll for up to ~10s for the visible "consolidated" items to change,
        # since Angular re-renders asynchronously and click handlers on the
        # new rows aren't reliably bound the instant the DOM node appears.
        end = time.time() + 10
        while time.time() < end:
            time.sleep(0.5)
            sig = _page_signature(driver)
            if sig is not None and sig != before_sig:
                # give Angular a little extra time to finish binding events
                time.sleep(1.5)
                return
        # Fall back to a flat wait if we couldn't detect a change
        time.sleep(2)

    li = None
    try:
        li = driver.find_element(By.CSS_SELECTOR, "li.pagination-next")
    except Exception:
        li = None

    if li is not None:
        li_class = li.get_attribute("class") or ""
        if "disabled" in li_class.split():
            print("  Already on the last page (Next button is disabled).")
            return False
        try:
            btn = li.find_element(By.TAG_NAME, "a")
        except Exception:
            btn = li
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({behavior:'auto', block:'center'});", btn
            )
            time.sleep(0.3)
            try:
                btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn)
            print("Navigated to next page. Waiting for page to load...")
            _wait_for_refresh()
            return True
        except Exception as exc:
            print(f"  Warning: found Next button but click failed: {exc}")

    # Generic fallback selectors, in case the markup differs from what we expect
    for xpath in [
        "//li[contains(@class,'pagination-next')]//a",
        "//a[contains(@class,'next')]",
        "//a[normalize-space(.)='>']",
        "//a[normalize-space(.)='>>']",
    ]:
        try:
            btn = driver.find_element(By.XPATH, xpath)
            driver.execute_script(
                "arguments[0].scrollIntoView({behavior:'auto', block:'center'});", btn
            )
            time.sleep(0.3)
            try:
                btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn)
            print("Navigated to next page. Waiting for page to load...")
            _wait_for_refresh()
            return True
        except Exception:
            continue

    return False


# ---------------------------------------------------------------------------
# Page scanning – finds "Consolidated" items and clicks them for download
# ---------------------------------------------------------------------------
def scan_and_click_consolidated(driver, download_dir, start_date):
    """Scan the current browser page for items containing 'Consolidated',
    click each one that matches the date filter, and organize the download."""
    # IMPORTANT: On the current Kotak markup, the row title (e.g. "Consolidated
    # Portfolio as on February 28, 2026") is plain, non-interactive text. The
    # actual clickable control is a separate sibling element:
    #   <span class="... cursor-pointer ...">Download <img .../></span>
    # Clicking the title text does nothing. We find the "Download" trigger
    # elements directly, then walk up to the nearest ancestor whose text
    # contains "consolidated" (the row/card wrapping both the title and the
    # Download control) to get the item's title/date for filtering/logging.
    download_xpath = (
        "//*[contains(translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
        "'abcdefghijklmnopqrstuvwxyz'), 'cursor-pointer') and "
        "contains(normalize-space(.), 'Download')]"
    )
    ancestor_xpath = (
        "ancestor::*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
        "'abcdefghijklmnopqrstuvwxyz'), 'consolidated')][1]"
    )

    download_elems = driver.find_elements(By.XPATH, download_xpath)

    seen_texts = set()
    candidates = []

    if download_elems:
        for dl in download_elems:
            try:
                container = dl.find_element(By.XPATH, ancestor_xpath)
                row_text = container.text.strip()
            except Exception:
                continue
            if not row_text or not IS_CONSOLIDATED_RE.search(row_text):
                continue
            clean_text = re.sub(
                r"\bDownload\b", "", row_text, flags=re.IGNORECASE
            ).strip()
            clean_text = re.sub(r"\s+", " ", clean_text)
            if not clean_text or clean_text in seen_texts or len(clean_text) > 200:
                continue
            seen_texts.add(clean_text)
            candidates.append({"element": dl, "text": clean_text})
    else:
        # Fallback to older markup where the title itself was a directly
        # clickable <a href="javascript://"> anchor.
        print(
            '  No "Download" trigger elements found, falling back to older anchor-based markup...'
        )
        xpath_primary = (
            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'consolidated') and "
            "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'portfolio as on')]"
        )
        xpath_fallback = (
            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'consolidated')]"
        )
        elems = driver.find_elements(By.XPATH, xpath_primary)
        if not elems:
            elems = driver.find_elements(By.XPATH, xpath_fallback)
        for e in elems:
            try:
                txt = e.text.strip()
            except Exception:
                continue
            if not txt or txt in seen_texts or len(txt) > 200:
                continue
            if not IS_CONSOLIDATED_RE.search(txt):
                continue
            seen_texts.add(txt)
            candidates.append({"element": e, "text": txt})

    # Filter by date
    filtered = []
    for item in candidates:
        pdate = parse_date_from_text(item["text"])
        if pdate and pdate < start_date:
            print(f'  Skipping (before {start_date}): {item["text"][:80]}')
            continue
        item["date"] = pdate
        filtered.append(item)

    if not filtered:
        print("No matching Consolidated items found on this page.")
        return 0

    print(f"\nFound {len(filtered)} Consolidated item(s) on this page:")
    for i, item in enumerate(filtered, 1):
        date_str = str(item.get("date", "?"))
        print(f'  {i}. [{date_str}] {item["text"][:100]}')

    # Build a set of existing files (recursively) so we can skip items that
    # were already downloaded in a previous run.
    existing_files = []
    for root, _dirs, files in os.walk(download_dir):
        existing_files.extend(files)

    def already_downloaded(item_text, item_date):
        if not item_date:
            return False
        month = item_date.strftime("%B").lower()
        year = str(item_date.year)
        is_sebi = "sebi" in item_text.lower()
        for fname in existing_files:
            fl = fname.lower()
            if month in fl and year in fl and (("sebi" in fl) == is_sebi):
                return fname
        return None

    before = list_current_files(download_dir)
    downloaded = 0

    def _relocate_by_text(target_text):
        """Re-find a fresh Download element for a row whose text we already
        know, in case the original element reference is stale/unresponsive
        (common right after an Angular page transition)."""
        try:
            fresh_elems = driver.find_elements(By.XPATH, download_xpath)
        except Exception:
            return None
        target_key = target_text[:40].lower()
        for dl in fresh_elems:
            try:
                container = dl.find_element(By.XPATH, ancestor_xpath)
                row_text = container.text.strip().lower()
            except Exception:
                continue
            if target_key in row_text:
                return dl
        return None

    def _click_and_wait(elem):
        """Click a Download element, handle new-tab/alert cases, and wait for
        the resulting file. Returns the wait_for_new_file() result."""
        original_window = driver.current_window_handle
        original_handles = set(driver.window_handles)

        clicked = False
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({behavior:'auto', block:'center'});", elem
            )
            time.sleep(0.3)
            elem.click()
            clicked = True
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", elem)
                clicked = True
            except Exception:
                pass

        if not clicked:
            return None

        time.sleep(1.0)
        try:
            new_handles = set(driver.window_handles) - original_handles
        except Exception:
            new_handles = set()

        opened_extra_tab = False
        if new_handles:
            opened_extra_tab = True
            new_handle = next(iter(new_handles))
            try:
                driver.switch_to.window(new_handle)
                time.sleep(2)
            except Exception as exc:
                print(f"  Warning: could not switch to new tab: {exc}")

        try:
            alert = driver.switch_to.alert
            alert_text = alert.text
            print(f'  A browser dialog appeared ("{alert_text[:80]}"), accepting it...')
            alert.accept()
            time.sleep(1)
        except Exception:
            pass

        result = wait_for_new_file(download_dir, before, timeout=45)

        if result is None and opened_extra_tab:
            print("  A new tab opened but no download was detected automatically.")
            print(
                "  If a PDF is showing in that tab, please save it manually "
                "(Ctrl+S) into the download folder, then press Enter."
            )
            input("  Press Enter once handled (or if nothing to do)...")
            result = wait_for_new_file(download_dir, before, timeout=15)

        if opened_extra_tab:
            try:
                if driver.current_window_handle != original_window:
                    driver.close()
            except Exception:
                pass
            try:
                driver.switch_to.window(original_window)
            except Exception:
                pass

        return result

    for idx, item in enumerate(filtered, 1):
        e = item["element"]
        txt = item["text"]
        pdate = item.get("date")

        existing = already_downloaded(txt, pdate)
        if existing:
            print(
                f'\n[{idx}/{len(filtered)}] Skipping (already downloaded as "{existing}"): {txt[:80]}'
            )
            continue

        print(f"\n[{idx}/{len(filtered)}] Clicking: {txt[:90]}")
        print("  Waiting for download...")
        new_file = _click_and_wait(e)

        if new_file is None:
            # First attempt produced nothing — very likely the row's click
            # handler wasn't fully bound yet (e.g. right after a page-2+
            # transition). Re-locate a fresh element for this same row and
            # try once more before giving up.
            print("  No file detected yet — re-locating this item and retrying once...")
            fresh = _relocate_by_text(txt)
            if fresh is not None:
                time.sleep(1)
                new_file = _click_and_wait(fresh)
            else:
                print("  Could not re-locate the item on the page for a retry.")

        if new_file == "MOVED_ELSEWHERE":
            # The background watcher already picked up and moved this file.
            print("  [OK] Download detected and organized by background watcher.")
            downloaded += 1
            before = list_current_files(download_dir)
        elif new_file:
            dest = move_file_to_year_month(new_file, download_dir, item_date=pdate)
            if dest:
                print(f"  [OK] Downloaded and moved to: {dest}")
                downloaded += 1
            before = list_current_files(download_dir)
        else:
            print(
                "  [SKIP] No new file detected. It may have already been downloaded, "
                "or you can try clicking manually."
            )

        # Small pause between clicks to avoid triggering rate limits
        time.sleep(1)

    return downloaded


# ---------------------------------------------------------------------------
# Main interactive loop
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Interactive Kotak MF downloader – opens a browser for you to "
        "solve captchas, then auto-clicks Consolidated items."
    )
    parser.add_argument(
        "--start-date",
        default="2024-10-01",
        help="YYYY-MM-DD earliest date to download (inclusive). Default: 2024-10-01",
    )
    parser.add_argument(
        "--download-dir",
        default=DEFAULT_DOWNLOAD_DIR,
        help="Base download directory (absolute Windows path)",
    )
    args = parser.parse_args()

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    download_dir = os.path.abspath(args.download_dir)
    os.makedirs(download_dir, exist_ok=True)

    print("=" * 65)
    print("  Kotak MF Interactive Downloader")
    print("=" * 65)
    print(f"  Download dir : {download_dir}")
    print(f"  Start date   : {start_date}")
    print("=" * 65)
    print()

    # -- Launch Chrome --
    print("Launching Chrome (visible)...")
    chrome_opts = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
        "profile.default_content_settings.popups": 0,
    }
    chrome_opts.add_experimental_option("prefs", prefs)
    chrome_opts.add_argument("--disable-blink-features=AutomationControlled")
    # suppress "Chrome is being controlled by automated software" bar
    chrome_opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_opts.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_opts)

    # Start the background download watcher
    watcher = DownloadWatcher(download_dir)
    watcher.start()

    total_downloaded = 0

    try:
        driver.get("https://www.kotakmf.com/Information/statutory-disclosure")
        print()
        print(
            "Browser opened at: https://www.kotakmf.com/Information/statutory-disclosure"
        )
        print()
        print("-" * 65)
        print("  STEP 1: Solve any captcha / Radware challenge in the browser.")
        print("  STEP 2: Come back here and press Enter when the page has loaded.")
        print("          The script will auto-select the Consolidated dropdown.")
        print("-" * 65)
        print()

        try:
            input("Press Enter when the page has loaded (captcha solved if any)...")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            return

        # Auto-select the Consolidated dropdown
        print('\nAuto-selecting "Consolidated & Fortnightly Portfolio" dropdown...')
        if select_consolidated_dropdown(driver):
            print("  Dropdown selected. Waiting for items to load...")
            time.sleep(2)
        else:
            print(
                "  Could not auto-select dropdown. Please select it manually in the browser."
            )
            input("  Press Enter after selecting the dropdown...")

        # -- Interactive loop --
        while True:
            print()
            print("Options:")
            print("  [Enter]  Scan current page for Consolidated items and download")
            print("  [n]      Navigate to next page (if pagination exists), then scan")
            print("  [q]      Quit")
            print()

            try:
                choice = input("Your choice: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                break

            if choice == "q":
                break

            if choice == "n":
                next_clicked = go_to_next_page(driver)

                if not next_clicked:
                    print(
                        "Could not find a Next button. Please navigate manually in "
                        "the browser, then press Enter here to scan."
                    )
                    input("Press Enter when ready...")

            # Scan and click
            print()
            watcher.pause()
            watcher.refresh_known()
            count = scan_and_click_consolidated(driver, download_dir, start_date)
            watcher.resume()
            total_downloaded += count
            print(
                f"\nPage done -- downloaded {count} file(s) this round "
                f"({total_downloaded} total).\n"
            )

    except KeyboardInterrupt:
        print("\nInterrupted by user.")

    finally:
        watcher.stop()
        print()
        print("=" * 65)
        print(f"  Session complete. Downloaded {total_downloaded} file(s).")
        if watcher.moved_count:
            print(
                f"  Background watcher also moved {watcher.moved_count} manually-downloaded file(s)."
            )
        print("=" * 65)
        print("Closing browser...")
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
