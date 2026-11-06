#!/usr/bin/env python3
"""Regression: YTD chart must not trap phone/iPad page scroll or inflate .chart-wrap.

Speed Option 2 (c9f4cf6) set canvas style.touchAction='none' and used
setPointerCapture on pointerdown, so a finger starting on the graph could not
scroll the page — felt like needless/broken scroll on iPhone and iPad.
Also guards .chart-wrap staying 220px with canvas clientHeight not exceeding it.
"""
import os, sys
from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get('PS_BASE', 'https://paperstreetbtc.com')).rstrip('/') + '/'
CHROME = '/usr/bin/google-chrome'
VIEWS = [
    ('iphone_390', 390, 844),
    ('ipad_820', 820, 1180),
    ('ipad_1024', 1024, 1366),
]
fails = []

def ok(name, cond, detail=''):
    if cond:
        print('ok', name)
    else:
        print('FAIL', name, detail)
        fails.append(name)

def main():
    # Source contract when native s2 is present in the served tree (local path optional)
    import pathlib, re
    root = pathlib.Path(__file__).resolve().parents[1]
    s2 = (root / 'assets/js/s2.js').read_text()
    if 'drawNative' in s2 or 'touchAction' in s2 or 'touch-action' in s2:
        # Native path must allow vertical panning
        bad_none = re.search(r"touchAction\s*=\s*['\"]none['\"]", s2) or "touch-action: none" in s2 or "touchAction = 'none'" in s2 or 'touchAction="none"' in s2 or "style.touchAction = 'none'" in s2 or 'style.touchAction="none"' in s2
        # also catch canvas.style.touchAction = 'none'
        bad_none = bool(re.search(r"touchAction\s*=\s*['\"]none['\"]", s2))
        ok('s2.js must not set touch-action/none on YTD canvas', not bad_none)
        if 'setPointerCapture' in s2:
            ok('s2.js setPointerCapture requires pan-y touch-action (no none)', not bad_none)

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, args=['--no-sandbox', '--disable-gpu'])
        for name, w, h in VIEWS:
            page = browser.new_page(viewport={'width': w, 'height': h}, has_touch=True, is_mobile=True)
            page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_selector('#ytdChart', timeout=45000)
            page.wait_for_timeout(2000)
            page.locator('#ytdChart').scroll_into_view_if_needed()
            info = page.evaluate("""() => {
              const c = document.getElementById('ytdChart');
              const w = document.querySelector('.chart-wrap');
              return {
                touchAction: c ? getComputedStyle(c).touchAction : null,
                wrapH: w ? w.clientHeight : null,
                wrapScrollH: w ? w.scrollHeight : null,
                canvasH: c ? c.clientHeight : null,
              };
            }""")
            ta = (info['touchAction'] or '').lower()
            ok(f'{name} touch-action allows vertical scroll',
               ta in ('auto', 'manipulation', 'pan-y', 'pan-x pan-y', '') or 'pan-y' in ta,
               f'touchAction={info["touchAction"]!r}')
            ok(f'{name} touch-action is not none', ta != 'none', f'touchAction={info["touchAction"]!r}')
            ok(f'{name} chart-wrap height is 220', info['wrapH'] == 220, str(info))
            ok(f'{name} canvas height <= chart-wrap',
               info['canvasH'] is not None and info['wrapH'] is not None and info['canvasH'] <= info['wrapH'] + 1,
               str(info))
            ok(f'{name} chart-wrap scrollHeight not inflated',
               info['wrapScrollH'] is not None and info['wrapScrollH'] <= info['wrapH'] + 2,
               str(info))
            page.close()
        browser.close()

    print('YTD CHART SCROLL TESTS', len(fails) == 0 and 'PASS' or 'FAIL', 'fails', fails)
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
