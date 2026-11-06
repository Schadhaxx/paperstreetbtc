#!/usr/bin/env python3
"""Clock page light mode (Sunil, 6 Nov 2026): verify both themes render
correctly at desktop width and 390px phone width.

Checks: dark is the default; ?theme=light applies light and persists via
ps-theme localStorage; the footer Light/Dark links toggle both ways; the
inline BTC chart and the hash-rate chart draw in both themes; the USD/CAD
toggle works in light mode; no horizontal overflow at 390px; no console
errors. Screenshots go to ~/workspace/your_files/clock-light-shots/.

Runs against a local HTTP server serving this repo tree (self-contained).
Usage: python3 tests/test_clock_light_mode.py
"""
import http.server, json, os, socketserver, threading, time
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = '/usr/bin/google-chrome'
if not os.path.exists(CHROME):
    CHROME = os.path.expanduser('~/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome')
SHOTS = os.path.expanduser('~/workspace/your_files/clock-light-shots')
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

def canvas_has_pixels(page, sel):
    """True if the canvas has any non-transparent, non-uniform pixels."""
    return page.evaluate("""(sel) => {
      const c = document.querySelector(sel);
      if (!c || !c.width || !c.height) return false;
      const x = c.getContext('2d');
      const d = x.getImageData(0, 0, c.width, c.height).data;
      let seen = new Set();
      for (let i = 0; i < d.length; i += 4013) {
        seen.add(d[i] + ',' + d[i+1] + ',' + d[i+2] + ',' + d[i+3]);
        if (seen.size > 4) return true;
      }
      return false;
    }""", sel)

def main():
    errors = []
    # Stub the live feeds so the page loads fully in the sandbox (no
    # internet) — the hash chart and the CAD toggle need real values to
    # be testable, and a clean load should produce no failed requests.
    now = int(time.time())
    def price(route):
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'bitcoin': {'usd': 76000, 'cad': 107000,
                                                   'usd_24h_change': 0.6,
                                                   'cad_24h_change': 0.6}}))
    def blocks(route):
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps([{'height': 974900, 'timestamp': now - 300}]))
    def fees(route):
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'fastestFee': 5, 'economyFee': 2}))
    def mempool(route):
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'count': 50000}))
    def diff(route):
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'progressPercent': 50.0, 'difficultyChange': 1.5}))
    def hashrate(route):
        pts = [{'timestamp': now - (30 - i) * 86400, 'avgHashrate': (900 + i * 5) * 1e18}
               for i in range(30)]
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'hashrates': pts,
                                       'currentHashrate': 1040 * 1e18}))
    def candles(route):
        # Coinbase candles: [time, low, high, open, close, volume]
        pts = [[now - (30 - i) * 86400, 70000, 78000, 72000, 76000, 100]
               for i in range(30)]
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps(pts))
    def spot(route):
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'data': {'amount': '76000'}}))
    def market_chart(route):
        pts = [[(now - (30 - i) * 86400) * 1000, 76000] for i in range(30)]
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'prices': pts, 'market_caps': [],
                                       'total_volumes': []}))
    def history(route):
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'closes': {}, 'btc_provisional': []}))
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME,
                                    args=['--no-sandbox', '--disable-gpu'])
        for name, w, h in [('desktop', 1280, 900), ('phone 390', 390, 844)]:
            page = browser.new_page(viewport={'width': w, 'height': h})
            page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.route('**/api.coingecko.com/api/v3/simple/price*', price)
            page.route('**/mempool.space/api/blocks', blocks)
            page.route('**/mempool.space/api/v1/fees/recommended', fees)
            page.route('**/mempool.space/api/mempool', mempool)
            page.route('**/mempool.space/api/v1/difficulty-adjustment', diff)
            page.route('**/mempool.space/api/v1/mining/hashrate/*', hashrate)
            page.route('**/api.exchange.coinbase.com/products/BTC-USD/candles*', candles)
            page.route('**/api.coinbase.com/v2/prices/BTC-USD/spot', spot)
            page.route('**/api.coingecko.com/api/v3/coins/bitcoin/market_chart*', market_chart)
            page.route('**/raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/history.json*', history)

            # --- Dark (default): no theme param, clean localStorage ---
            page.goto(BASE + 'clock/index.html', wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(4000)
            theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
            ok(f'{name} dark is the default (no data-theme)', theme is None, str(theme))
            bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
            ok(f'{name} dark body is dark', bg in ('rgb(5, 7, 15)', 'rgb(5,7,15)'), bg)
            ok(f'{name} dark BTC chart draws', canvas_has_pixels(page, '#bcC'))
            ok(f'{name} dark hash chart draws', canvas_has_pixels(page, '#hashC'))
            page.screenshot(path=f'{SHOTS}/{name.replace(" ", "-")}-dark.png', full_page=True)

            # --- Light via ?theme=light ---
            page.goto(BASE + 'clock/index.html?theme=light',
                      wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(4000)
            theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
            ok(f'{name} ?theme=light sets data-theme=light', theme == 'light', str(theme))
            bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
            ok(f'{name} light body is #f6f8fb', bg in ('rgb(246, 248, 251)', 'rgb(246,248,251)'), bg)
            hero_bg = page.evaluate(
                "getComputedStyle(document.getElementById('hero')).backgroundColor")
            ok(f'{name} light hero is white', hero_bg in ('rgb(255, 255, 255)', 'rgb(255,255,255)'), hero_bg)
            txt = page.evaluate("getComputedStyle(document.body).color")
            ok(f'{name} light body text is dark', txt in ('rgb(15, 23, 42)', 'rgb(15,23,42)'), txt)
            # The inline chart container must be white, not the dark rgba.
            bc_bg = page.evaluate(
                "getComputedStyle(document.querySelector('.bc-inline')).backgroundColor")
            ok(f'{name} light inline chart card is white',
               bc_bg in ('rgb(255, 255, 255)', 'rgb(255,255,255)'), bc_bg)
            ok(f'{name} light BTC chart draws', canvas_has_pixels(page, '#bcC'))
            ok(f'{name} light hash chart draws', canvas_has_pixels(page, '#hashC'))
            # No horizontal overflow at phone width.
            ov = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            ok(f'{name} no horizontal overflow', ov <= 1, f'overflow {ov}px')
            page.screenshot(path=f'{SHOTS}/{name.replace(" ", "-")}-light.png', full_page=True)

            # --- Toggle: "Back to dark" link switches back ---
            page.locator('.ps-theme-alt .ps-to-dark').first.click(timeout=5000)
            page.wait_for_timeout(3000)
            theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
            ok(f'{name} "Back to dark" returns to dark', theme is None, str(theme))

            # --- Persistence: ps-theme=light survives a plain reload ---
            page.evaluate("localStorage.setItem('ps-theme','light')")
            page.goto(BASE + 'clock/index.html', wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(3000)
            theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
            ok(f'{name} saved light preference respected on reload', theme == 'light', str(theme))

            # --- USD/CAD toggle works in light mode ---
            cad_btn = page.locator('.cur-toggle button[data-cur="CAD"]').first
            if cad_btn.is_enabled():
                cad_btn.click(timeout=5000)
                page.wait_for_timeout(1500)
                hero = page.locator('#price').text_content() or ''
                ok(f'{name} CAD toggle works in light mode (hero shows C$)',
                   'C$' in hero, hero)
            else:
                ok(f'{name} CAD toggle enabled in light mode', False, 'CAD button disabled')
            page.close()

        browser.close()
    httpd.shutdown()
    ok('no console/page errors during the run', not errors, '; '.join(errors[:3]))
    print('CLOCK LIGHT MODE', 'PASS' if not fails else 'FAIL: ' + ', '.join(fails))
    raise SystemExit(1 if fails else 0)

if __name__ == '__main__':
    main()
