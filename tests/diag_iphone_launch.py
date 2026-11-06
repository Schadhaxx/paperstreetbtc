#!/usr/bin/env python3
"""Diagnose the iPhone launch horizontal shift at 390px.

Loads the homepage from a local server serving the repo tree, at 390x844
(has_touch, is_mobile), and reports:
- documentElement.scrollWidth vs window.innerWidth (at first paint + settled)
- every element whose bounding box extends past the 390px viewport
- screenshots of the top banner at first load and after settle
"""
import http.server, os, socketserver, threading
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

OVERFLOW_JS = """() => {
  const vw = window.innerWidth;
  const bad = [];
  document.querySelectorAll('*').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;
    if (r.right > vw + 0.5 || r.left < -0.5) {
      const cs = getComputedStyle(el);
      bad.push({
        tag: el.tagName.toLowerCase(),
        id: el.id || '',
        cls: (el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className || '').toString().slice(0, 80),
        left: Math.round(r.left * 10) / 10,
        right: Math.round(r.right * 10) / 10,
        width: Math.round(r.width * 10) / 10,
        pos: cs.position,
        overflow: cs.overflow + '/' + cs.overflowX,
      });
    }
  });
  // Keep only the widest/outermost offenders (drop descendants of a listed ancestor).
  const out = [];
  for (const b of bad) {
    out.push(b);
  }
  return {
    vw, scrollW: document.documentElement.scrollWidth,
    bodyScrollW: document.body ? document.body.scrollWidth : null,
    scrollX: window.scrollX,
    offenders: out.slice(0, 60),
    count: out.length,
  };
}"""

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME,
                                    args=['--no-sandbox', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 390, 'height': 844},
                                has_touch=True, is_mobile=True,
                                device_scale_factor=2)
        page.goto(BASE, wait_until='commit', timeout=60000)
        page.wait_for_timeout(400)
        early = page.evaluate(OVERFLOW_JS)
        print('=== AT FIRST PAINT (400ms) ===')
        print('innerWidth:', early['vw'], 'scrollWidth:', early['scrollW'],
              'bodyScrollW:', early['bodyScrollW'], 'scrollX:', early['scrollX'])
        print('offenders:', early['count'])
        page.screenshot(path=os.path.join(OUT, '01-early-top.png'),
                        clip={'x': 0, 'y': 0, 'width': 390, 'height': 400})
        page.wait_for_timeout(4000)
        settled = page.evaluate(OVERFLOW_JS)
        print('=== SETTLED (4.4s) ===')
        print('innerWidth:', settled['vw'], 'scrollWidth:', settled['scrollW'],
              'bodyScrollW:', settled['bodyScrollW'], 'scrollX:', settled['scrollX'])
        print('offenders:', settled['count'])
        for o in settled['offenders'][:30]:
            print('  ', o)
        page.screenshot(path=os.path.join(OUT, '02-settled-top.png'),
                        clip={'x': 0, 'y': 0, 'width': 390, 'height': 400})
        page.screenshot(path=os.path.join(OUT, '03-settled-full.png'), full_page=True)
        # Header geometry specifically.
        hdr = page.evaluate("""() => {
          const h = document.querySelector('header') || document.querySelector('.hdr, .top, #top');
          const els = [];
          ['header', '.brand', '.hdr', 'nav', '#hdrTick', '.btc-pill', '.mnav-btn'].forEach(s => {
            const el = document.querySelector(s);
            if (el) { const r = el.getBoundingClientRect();
              els.push({sel: s, left: Math.round(r.left), right: Math.round(r.right), w: Math.round(r.width)}); }
          });
          return {header: h ? h.outerHTML.slice(0, 200) : null, els};
        }""")
        print('=== HEADER GEOMETRY ===')
        for e in hdr['els']:
            print('  ', e)
        print('viewport meta:', page.evaluate(
            "document.querySelector('meta[name=viewport]') ? "
            "document.querySelector('meta[name=viewport]').content : 'MISSING'"))
        browser.close()
    httpd.shutdown()

if __name__ == '__main__':
    main()
