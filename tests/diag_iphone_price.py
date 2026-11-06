#!/usr/bin/env python3
"""Reproduce the iPhone launch shift: stub a REAL BTC price so the pill
grows from '—' to a full price + change + Chart chip, and sample
scrollWidth + header geometry over the first seconds of load.
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

MEASURE = """() => {
  const vw = window.innerWidth;
  const pill = document.getElementById('hdrTick');
  const brand = document.querySelector('.brand');
  const btn = document.getElementById('mnavBtn');
  const inner = document.querySelector('.header-inner');
  const r = el => { if (!el) return null; const b = el.getBoundingClientRect();
    return {left: Math.round(b.left), right: Math.round(b.right), w: Math.round(b.width)}; };
  return {
    vw, scrollW: document.documentElement.scrollWidth,
    pill: r(pill), pillText: pill ? pill.textContent.trim().slice(0, 60) : null,
    brand: r(brand), btn: r(btn), inner: r(inner),
  };
}"""

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME,
                                    args=['--no-sandbox', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 390, 'height': 844},
                                has_touch=True, is_mobile=True,
                                device_scale_factor=2)
        # Realistic live price so the pill fills in like on a real phone.
        page.route('**/api.coingecko.com/api/v3/simple/price*',
                   lambda r: r.fulfill(status=200, content_type='application/json',
                                       body=json.dumps({'bitcoin': {'usd': 75792,
                                                                    'usd_24h_change': 1.24}})))
        page.goto(BASE, wait_until='commit', timeout=60000)
        for i in range(12):
            m = page.evaluate(MEASURE)
            print(f"t={i*0.5:4.1f}s scrollW={m['scrollW']} vw={m['vw']} "
                  f"pill={m['pill']} brand={m['brand']} btn={m['btn']} "
                  f"pillText={m['pillText']!r}")
            if i == 0:
                page.screenshot(path=os.path.join(OUT, '10-price-early.png'),
                                clip={'x': 0, 'y': 0, 'width': 390, 'height': 200})
            page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(OUT, '11-price-settled.png'),
                        clip={'x': 0, 'y': 0, 'width': 390, 'height': 200})
        # What is the pill's intrinsic (min-content) width? And does the
        # header-inner overflow its own box?
        extra = page.evaluate("""() => {
          const pill = document.getElementById('hdrTick');
          const inner = document.querySelector('.header-inner');
          const cs = getComputedStyle(pill);
          return {
            pillMinContent: pill.scrollWidth,
            pillClientW: pill.clientWidth,
            innerScrollW: inner.scrollWidth,
            innerClientW: inner.clientWidth,
            pillFlexShrink: cs.flexShrink, pillMinWidth: cs.minWidth,
            pillWhiteSpace: cs.whiteSpace,
            bodyOverflowX: getComputedStyle(document.body).overflowX,
            htmlOverflowX: getComputedStyle(document.documentElement).overflowX,
          };
        }""")
        print('=== PILL SIZING ===')
        for k, v in extra.items():
            print('  ', k, '=', v)
        # Full DOM overflow walk with the price loaded.
        ov = page.evaluate("""() => {
          const vw = window.innerWidth; const bad = [];
          document.querySelectorAll('*').forEach(el => {
            const r = el.getBoundingClientRect();
            if ((r.width === 0 && r.height === 0)) return;
            if (r.right > vw + 0.5 || r.left < -0.5) {
              bad.push({tag: el.tagName.toLowerCase(), id: el.id || '',
                cls: (el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className || '').toString().slice(0, 60),
                left: Math.round(r.left), right: Math.round(r.right)});
            }
          });
          return {vw, scrollW: document.documentElement.scrollWidth, count: bad.length, bad: bad.slice(0, 25)};
        }""")
        print('=== OVERFLOW WITH PRICE LOADED ===')
        print('scrollW:', ov['scrollW'], 'count:', ov['count'])
        for b in ov['bad']:
            print('  ', b)
        browser.close()
    httpd.shutdown()

if __name__ == '__main__':
    main()
