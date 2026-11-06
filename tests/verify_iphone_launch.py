#!/usr/bin/env python3
"""Verify the iPhone launch fix: with a real price loaded, at 390px the
page must not scroll horizontally (scrollWidth == innerWidth), the header
must fit, and the pill + hamburger must be usable. Spot-check 820px too.
Screenshots before/after are taken by the caller comparing branches; here
we capture the AFTER shots.
"""
import http.server, json, os, socketserver, threading
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, '..', 'iphone-diag')
os.makedirs(OUT, exist_ok=True)
CHROME = '/usr/bin/google-chrome'
if not os.path.exists(CHROME):
    CHROME = os.path.expanduser('~/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome')

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)
    def log_message(self, *a):
        pass

httpd = socketserver.TCPServer(('127.0.0.1', 0), Handler)
port = httpd.server_address[1]
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{port}/'
fails = []

def ok(name, cond, detail=''):
    if cond:
        print('ok', name)
    else:
        print('FAIL', name, detail)
        fails.append(name)

def measure(page):
    return page.evaluate("""() => {
      const pill = document.getElementById('hdrTick');
      const btn = document.getElementById('mnavBtn');
      const inner = document.querySelector('.header-inner');
      const r = el => { if (!el) return null; const b = el.getBoundingClientRect();
        return {left: Math.round(b.left), right: Math.round(b.right), w: Math.round(b.width)}; };
      // Any element sticking out past the viewport?
      const vw = window.innerWidth; const bad = [];
      document.querySelectorAll('header *, body > *').forEach(el => {
        const b = el.getBoundingClientRect();
        if (b.width && (b.right > vw + 0.5 || b.left < -0.5))
          bad.push((el.tagName + '#' + (el.id || '') + '.' + (el.className || '')).slice(0, 70) + ' L' + Math.round(b.left) + ' R' + Math.round(b.right));
      });
      return {vw, scrollW: document.documentElement.scrollWidth,
              pill: r(pill), btn: r(btn), innerScrollW: inner.scrollWidth,
              innerClientW: inner.clientWidth, pillText: pill ? pill.textContent.trim() : '',
              chipVisible: !!document.querySelector('.hdr-tick .lp-cv') &&
                getComputedStyle(document.querySelector('.hdr-tick .lp-cv')).display !== 'none',
              bad: bad.slice(0, 10)};
    }""")

def run_case(browser, label, w, h, price):
    page = browser.new_page(viewport={'width': w, 'height': h},
                            has_touch=True, is_mobile=True, device_scale_factor=2)
    page.route('**/api.coingecko.com/api/v3/simple/price*',
               lambda r: r.fulfill(status=200, content_type='application/json',
                                   body=json.dumps({'bitcoin': {'usd': price,
                                                                'usd_24h_change': 1.24}})))
    page.goto(BASE, wait_until='commit', timeout=60000)
    page.wait_for_timeout(2500)
    m = measure(page)
    print(f'--- {label} (price ${price:,}) ---')
    print(f"  scrollW={m['scrollW']} vw={m['vw']} pill={m['pill']} btn={m['btn']} "
          f"innerScrollW={m['innerScrollW']} chipVisible={m['chipVisible']}")
    print(f"  pillText={m['pillText']!r} overflowers={m['bad']}")
    ok(f'{label}: scrollWidth == innerWidth ({m["scrollW"]} == {m["vw"]})',
       m['scrollW'] == m['vw'], f"scrollW={m['scrollW']} vw={m['vw']}")
    ok(f'{label}: hamburger fully inside viewport (right {m["btn"]["right"]} <= {m["vw"]})',
       m['btn']['right'] <= m['vw'], str(m['btn']))
    ok(f'{label}: header-inner does not overflow ({m["innerScrollW"]} <= {m["innerClientW"]})',
       m['innerScrollW'] <= m['innerClientW'], f"{m['innerScrollW']} vs {m['innerClientW']}")
    ok(f'{label}: no element sticks out past the viewport', len(m['bad']) == 0, str(m['bad']))
    # Pill still opens the chart.
    page.locator('#hdrTick').click(timeout=5000)
    page.wait_for_timeout(1200)
    dlg = page.evaluate("!!document.querySelector('.bc-w:not([hidden])') || !!document.querySelector('.bc-w')")
    ok(f'{label}: tapping the pill still opens the chart', dlg, 'no dialog')
    page.keyboard.press('Escape')
    page.wait_for_timeout(400)
    # Reload: still fits.
    page.evaluate('location.reload()')
    page.wait_for_timeout(2500)
    m2 = measure(page)
    ok(f'{label}: after reload scrollWidth == innerWidth ({m2["scrollW"]} == {m2["vw"]})',
       m2['scrollW'] == m2['vw'], f"scrollW={m2['scrollW']} vw={m2['vw']}")
    page.screenshot(path=os.path.join(OUT, f'after-{label.replace(" ", "-")}.png'),
                    clip={'x': 0, 'y': 0, 'width': w, 'height': 300})
    page.close()

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME,
                                    args=['--no-sandbox', '--disable-gpu'])
        run_case(browser, '390px', 390, 844, 75792)
        run_case(browser, '390px-6digit', 390, 844, 104250)
        run_case(browser, '820px', 820, 1180, 75792)
        browser.close()
    httpd.shutdown()
    print('VERIFY', 'PASS' if not fails else 'FAIL: ' + ', '.join(fails))
    raise SystemExit(1 if fails else 0)

if __name__ == '__main__':
    main()
