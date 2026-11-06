#!/usr/bin/env python3
"""Verify the pill chart-icon redesign (branch pepper-pill-chart-icon).

- Pill renders with the new chip (SVG icon + "Chart", no ↗ / ▾ glyphs)
  at desktop width and 390px phone width.
- Clicking the pill opens the chart dialog; closing it works.
- Screenshots: ~/workspace/your_files/pill-icon-shots/
"""
import http.server, os, socketserver, threading
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = '/usr/bin/google-chrome'
if not os.path.exists(CHROME):
    CHROME = os.path.expanduser('~/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome')
SHOTS = os.path.expanduser('~/workspace/your_files/pill-icon-shots')
os.makedirs(SHOTS, exist_ok=True)
fails = []

def ok(name, cond, detail=''):
    if cond:
        print('ok', name)
    else:
        print('FAIL', name, detail)
        fails.append(name)

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)
    def log_message(self, *a):
        pass

httpd = socketserver.TCPServer(('127.0.0.1', 0), Handler)
port = httpd.server_address[1]
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{port}/'

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME,
                                    args=['--no-sandbox', '--disable-gpu'])
        for name, w, h in [('desktop', 1280, 900), ('phone 390', 390, 844)]:
            page = browser.new_page(viewport={'width': w, 'height': h})
            page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_selector('#hdrTick', timeout=30000)
            page.wait_for_timeout(2500)
            chip = page.locator('#hdrTick .lp-cv')
            ok(name + ' chip present', chip.count() == 1, str(chip.count()))
            text = chip.inner_text() if chip.count() else ''
            ok(name + ' chip reads "Chart" (no ↗ / ▾ glyphs)',
               text.strip() == 'Chart' and '↗' not in text and '▾' not in text, repr(text))
            ok(name + ' chip has an inline SVG icon',
               chip.locator('svg').count() == 1, str(chip.locator('svg').count()))
            # No hard outline: background tint, border 0.
            style = chip.evaluate(
                "el => {const s = getComputedStyle(el); return {bg: s.backgroundColor, bw: s.borderWidth, bs: s.borderStyle};}")
            ok(name + ' chip has soft fill, no border',
               style['bs'] == 'none' or style['bw'] == '0px', str(style))
            # Pill fits: no horizontal overflow at this width.
            overflow = page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
            ok(name + ' no horizontal overflow', not overflow, '')
            page.locator('#hdrTick').screenshot(path=f'{SHOTS}/pill-{name.replace(" ", "-")}.png')
            # Open the dialog by clicking the pill, then close it.
            page.locator('#hdrTick').click(timeout=5000)
            page.wait_for_selector('.bc-w:not([hidden])', timeout=10000)
            ok(name + ' clicking the pill opens the chart dialog', True, '')
            page.locator('.bc-w:not([hidden])').screenshot(
                path=f'{SHOTS}/dialog-{name.replace(" ", "-")}.png')
            page.locator('#bcX').click(timeout=5000)
            page.wait_for_timeout(800)
            hidden = page.evaluate("()=>{const d=document.querySelector('.bc-w');return !d||d.hidden;}")
            ok(name + ' closing the dialog works (✕)', hidden, '')
            page.close()
        browser.close()
    httpd.shutdown()
    print('PILL ICON CHECKS', 'PASS' if not fails else 'FAIL: ' + ', '.join(fails))
    raise SystemExit(1 if fails else 0)

if __name__ == '__main__':
    main()
