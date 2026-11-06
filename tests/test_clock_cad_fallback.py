#!/usr/bin/env python3
"""Targeted test: clock CAD fallback must keep the last valid exchange rate.

Bug (Grok live review, 6 Nov 2026): when CoinGecko failed and the page fell
back to the Coinbase USD-only price, the clock kept the older CAD price but
recomputed the exchange rate as oldCAD / newUSD — a rate from mismatched
timestamps. The fix: fxRate only recomputes when the SAME response supplies
both a valid USD and a valid CAD value; otherwise the last valid rate is
kept, and the footer shows that stored rate.

Test: stub CoinGecko to USD 80000 / CAD 112000 (rate 1.40), let the page
load, then make CoinGecko fail so the Coinbase USD-only fallback (USD 76000)
is used. The footer must still read 1.40, NOT 112000/76000 = 1.47, and the
chart's CAD rate (window.BC_CUR.rate) must be 1.40.

Runs against a local HTTP server serving this repo tree (self-contained).
Usage: python3 tests/test_clock_cad_fallback.py
"""
import http.server, json, os, socketserver, threading, functools
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Chromium: prefer the system google-chrome symlink when present, else the
# Playwright-bundled build.
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

# --- local server serving the repo tree ---
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)
    def log_message(self, *a):
        pass

httpd = socketserver.TCPServer(('127.0.0.1', 0), Handler)
port = httpd.server_address[1]
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{port}/'

# --- price-feed stubs ---
# Phase 1: CoinGecko answers with both USD and CAD (rate 1.40).
# Phase 2: CoinGecko fails; Coinbase answers USD-only (76000).
state = {'phase': 1}

def coingecko(route):
    if state['phase'] == 1:
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'bitcoin': {'usd': 80000, 'cad': 112000,
                                                   'usd_24h_change': 1.0,
                                                   'cad_24h_change': 1.0}}))
    else:
        route.abort()

def coinbase(route):
    route.fulfill(status=200, content_type='application/json',
                  body=json.dumps({'data': {'amount': '76000'}}))

def mempool_blocks(route):
    route.fulfill(status=200, content_type='application/json',
                  body=json.dumps([{'height': 974900, 'timestamp': 1790000000}]))

def mempool_fees(route):
    route.fulfill(status=200, content_type='application/json',
                  body=json.dumps({'fastestFee': 5, 'economyFee': 2}))

def mempool_mempool(route):
    route.fulfill(status=200, content_type='application/json',
                  body=json.dumps({'count': 50000}))

def mempool_diff(route):
    route.fulfill(status=200, content_type='application/json',
                  body=json.dumps({'progressPercent': 50.0, 'difficultyChange': 1.5}))

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME,
                                    args=['--no-sandbox', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        page.route('**/api.coingecko.com/api/v3/simple/price*', coingecko)
        page.route('**/api.coinbase.com/v2/prices/BTC-USD/spot', coinbase)
        page.route('**/mempool.space/api/blocks', mempool_blocks)
        page.route('**/mempool.space/api/v1/fees/recommended', mempool_fees)
        page.route('**/mempool.space/api/mempool', mempool_mempool)
        page.route('**/mempool.space/api/v1/difficulty-adjustment', mempool_diff)

        page.goto(BASE + 'clock/index.html', wait_until='domcontentloaded', timeout=60000)
        # First update: CoinGecko USD 80000 / CAD 112000 -> rate 1.40
        page.wait_for_function(
            "document.getElementById('fxRate').textContent.includes('1.40')",
            timeout=30000)
        fx1 = page.locator('#fxRate').text_content()
        ok('footer rate is 1.40 after CoinGecko USD+CAD', '1.40' in fx1, fx1)

        # Phase 2: CoinGecko fails, Coinbase USD-only (76000) takes over.
        state['phase'] = 2
        page.click('#refreshBtn')
        page.wait_for_timeout(3000)
        fx2 = page.locator('#fxRate').text_content()
        # Old code would recompute 112000/76000 = 1.47. Fixed code keeps 1.40.
        ok('footer rate STAYS 1.40 after USD-only fallback (not 1.47)', '1.40' in fx2, fx2)
        ok('footer rate is not the mismatched 1.47', '1.47' not in fx2, fx2)

        # The chart's CAD conversion must use the same kept rate.
        page.click('.cur-toggle button[data-cur="CAD"]')
        page.wait_for_timeout(2000)
        rate = page.evaluate("window.BC_CUR ? window.BC_CUR.rate : null")
        ok('chart CAD rate (BC_CUR.rate) is 1.40, not 1.47',
           rate is not None and abs(rate - 1.40) < 0.005, str(rate))
        # Hero in CAD shows the last good CAD price (112000) — that is the
        # last-good rule, not the bug; only the RATE must not be recomputed.
        hero = page.locator('#price').text_content()
        ok('CAD hero shows the last good CAD price (C$112,000)', '112,000' in hero, hero)

        browser.close()
    httpd.shutdown()
    print('PASS' if not fails else 'FAIL: ' + ', '.join(fails))
    raise SystemExit(1 if fails else 0)

if __name__ == '__main__':
    main()
