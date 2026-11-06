#!/usr/bin/env python3
"""Grok live-review missing checks (6 Nov 2026) — the three the browser
harness could not do (no viewport resize, no touch, no request blocking).

1. Real phone/iPad touch scrolling STARTING ON charts (390px, 820px, 1024px):
   a finger drag that begins on a chart must scroll the page, not get
   trapped. Desktop mouse-wheel checks do not establish this.
   Surfaces: homepage YTD chart, homepage BTC popover chart (#bcC),
   screener weekly-candle modal (#ind-canvas).
2. Forced 4H-fetch failure: with the Coinbase 1h-bars request blocked, the
   BTC popover 1W 4H button must fall back to Daily (7 daily candles) with
   the "Coinbase 4-hour candles unavailable" note — no stuck 4H view, no
   blank chart, no error banner.
3. Clock-outage behaviour: with ALL clock feeds blocked, /clock/ must not
   go blank and must not invent numbers (dashes / last-good + stale label).

Runs against a local HTTP server serving this repo tree (self-contained).
Usage: python3 tests/test_grok_missing_checks.py
"""
import http.server, os, socketserver, threading
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = '/usr/bin/google-chrome'
if not os.path.exists(CHROME):
    CHROME = os.path.expanduser('~/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome')
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

def touch_drag_up(page, x, y, distance=300, steps=10):
    """Finger drag starting at (x, y) moving UP by `distance` px (the
    gesture that scrolls a page down). Returns (page scrollY, dialog scrollTop)."""
    cdp = page.context.new_cdp_session(page)
    cdp.send('Input.dispatchTouchEvent',
             {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y, 'id': 1}]})
    for i in range(1, steps + 1):
        yy = y - distance * i / steps
        cdp.send('Input.dispatchTouchEvent',
                 {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': yy, 'id': 1}]})
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    page.wait_for_timeout(600)
    return (page.evaluate('window.scrollY'),
            page.evaluate("(()=>{const d=document.querySelector('.bc-w');"
                          "return d?d.scrollTop:0;})()"))

def drag_on_selector(page, sel, label):
    """Drag starting on the element matched by `sel`; the gesture must not
    be trapped — the page or the containing dialog must scroll."""
    box = page.locator(sel).first.bounding_box()
    if not box:
        ok(label + ' element present', False, 'no ' + sel)
        return
    cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    y0, d0 = page.evaluate('window.scrollY'), page.evaluate(
        "(()=>{const d=document.querySelector('.bc-w');return d?d.scrollTop:0;})()")
    y1, d1 = touch_drag_up(page, cx, cy)
    ok(label + ' touch drag starting on chart is not trapped (page or dialog scrolls)',
       y1 > y0 + 20 or d1 > d0,
       f'page scrollY {y0}->{y1}, dialog scrollTop {d0}->{d1}')

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME,
                                    args=['--no-sandbox', '--disable-gpu'])
        # ---- CHECK 1: touch scroll on charts, phone + iPad ----
        for name, w, h in [('phone 390', 390, 844), ('iPad 820', 820, 1180),
                           ('iPad 1024', 1024, 1366)]:
            page = browser.new_page(viewport={'width': w, 'height': h},
                                    has_touch=True, is_mobile=True)
            page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_selector('#ytdChart', timeout=45000)
            page.wait_for_timeout(2500)
            # (a) Homepage YTD chart.
            drag_on_selector(page, '#ytdChart', name + ' YTD chart')
            # (b) Homepage BTC popover chart.
            try:
                page.evaluate('window.scrollTo(0, 0)')
                page.locator('#hdrTick').first.click(timeout=5000)
                page.wait_for_selector('#bcC', timeout=10000)
                page.wait_for_timeout(1500)
                drag_on_selector(page, '#bcC', name + ' BTC popover chart')
                page.keyboard.press('Escape')
                page.wait_for_timeout(500)
            except Exception as e:
                ok(name + ' BTC popover chart drag', False, str(e)[:140])
            # (c) Screener weekly-candle modal.
            try:
                page.goto(BASE + 'screener.html', wait_until='domcontentloaded', timeout=60000)
                page.wait_for_selector('.card[data-symbol]', timeout=30000)
                page.wait_for_timeout(2000)
                # Open the TSLA weekly candle modal.
                page.locator('.card[data-symbol="TSLA"]').first.click(timeout=8000)
                page.wait_for_selector('#ind-canvas', timeout=10000)
                page.wait_for_timeout(1500)
                drag_on_selector(page, '#ind-canvas', name + ' screener candle modal')
            except Exception as e:
                ok(name + ' screener candle modal drag', False, str(e)[:140])
            page.close()

        # ---- CHECK 2: forced 4H-fetch failure ----
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        page.route('**/api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600*',
                   lambda r: r.abort())
        page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(2500)
        page.locator('#hdrTick').first.click(timeout=5000)
        page.wait_for_selector('#bcC', timeout=10000)
        page.wait_for_timeout(1500)
        dlg = page.locator('.bc-w')
        dlg.locator('button:has-text("1W")').first.click(timeout=5000)
        page.wait_for_timeout(1200)
        dlg.locator('[data-cg="candles"]').first.click(timeout=5000)
        page.wait_for_timeout(1500)
        btn4h = dlg.locator('[data-cggran="4h"]').first
        if btn4h.count() and btn4h.is_visible():
            btn4h.click(timeout=5000)
            page.wait_for_timeout(2500)
            # fallback() appends the message to #bcNt.
            note = page.locator('#bcNt').first.text_content() or ''
            ok('4H failure falls back with the unavailable note',
               'unavailable' in note.lower() and 'daily' in note.lower(), note[:160])
            txt = page.locator('.bc-w').inner_text()
            ok('4H failure shows daily candles, not 42 4H', '42 4-hour' not in txt, '')
            # The size button should now read Daily as active.
            daily_on = dlg.locator('[data-cggran="daily"]').first.get_attribute('aria-pressed')
            ok('4H failure leaves Daily as the active size', daily_on == 'true', str(daily_on))
        else:
            ok('4H size button visible in Candles mode', False, 'not visible')
        page.close()

        # ---- CHECK 3: clock outage (all feeds blocked) ----
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        for pat in ['**/api.coingecko.com/**', '**/api.coinbase.com/**',
                    '**/mempool.space/**']:
            page.route(pat, lambda r: r.abort())
        page.goto(BASE + 'clock/index.html', wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(5000)
        hero = page.locator('#price').text_content() or ''
        status = page.locator('#status').text_content() or ''
        body = page.locator('body').inner_text()
        ok('clock outage: page is not blank (layout present)',
           'Bitcoin' in body and 'sats' in body.lower(), body[:80].replace('\n', ' '))
        ok('clock outage: hero price is a dash, not an invented number',
           hero.strip() in ('—', '-', '') or '—' in hero, repr(hero))
        ok('clock outage: a failed-feed label is shown',
           'fail' in status.lower() or 'fail' in body.lower(), status[:120])
        page.close()
        browser.close()
    httpd.shutdown()
    print('MISSING CHECKS', 'PASS' if not fails else 'FAIL: ' + ', '.join(fails))
    raise SystemExit(1 if fails else 0)

if __name__ == '__main__':
    main()
