#!/usr/bin/env python3
"""Verify the menu button move: at 390px the hamburger must sit UNDER the
Paperstreet logo (below the header, top-left) instead of in the header row,
must not overlap the header/pill/hero, must still open the mobile nav menu
(panel drops below the floater), and the page must not scroll sideways.
Desktop (1280px) must be unchanged: button in the header row.
"""
import http.server, json, os, socketserver, threading
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.expanduser('~'), 'workspace', 'your_files', 'menu-button-shots')
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
      const btn = document.getElementById('mnavBtn');
      const menu = document.getElementById('mnavMenu');
      const header = document.querySelector('.header');
      const inner = document.querySelector('.header-inner');
      const pill = document.getElementById('hdrTick');
      const brand = document.querySelector('.brand');
      const hero = document.querySelector('.hero');
      const r = el => { if (!el) return null; const b = el.getBoundingClientRect();
        return {left: Math.round(b.left), top: Math.round(b.top),
                right: Math.round(b.right), bottom: Math.round(b.bottom),
                w: Math.round(b.width), h: Math.round(b.height)}; };
      const cs = getComputedStyle(btn);
      // Does the button overlap the pill or the hero heading?
      const eyebrow = document.querySelector('.hero .eyebrow');
      const h1 = document.querySelector('.hero h1');
      const overlap = (a, b) => a && b && a.left < b.right && a.right > b.left &&
        a.top < b.bottom && a.bottom > b.top;
      return {vw: window.innerWidth, scrollW: document.documentElement.scrollWidth,
              btn: r(btn), menu: r(menu), header: r(header), inner: r(inner),
              pill: r(pill), brand: r(brand), hero: r(hero),
              btnPosition: cs.position, btnDisplay: cs.display,
              menuHidden: menu.hidden,
              overlapsPill: overlap(r(btn), r(pill)),
              overlapsEyebrow: overlap(r(btn), r(eyebrow)),
              overlapsH1: overlap(r(btn), r(h1)),
              overlapsMenu: !menu.hidden && overlap(r(btn), r(menu))};
    }""")

def run_phone(browser, label, price):
    page = browser.new_page(viewport={'width': 390, 'height': 844},
                            has_touch=True, is_mobile=True, device_scale_factor=2)
    page.route('**/api.coingecko.com/api/v3/simple/price*',
               lambda r: r.fulfill(status=200, content_type='application/json',
                                   body=json.dumps({'bitcoin': {'usd': price,
                                                                'usd_24h_change': 1.24}})))
    page.goto(BASE, wait_until='commit', timeout=60000)
    page.wait_for_timeout(2500)
    m = measure(page)
    print(f'--- {label} (price ${price:,}) ---')
    print(f"  scrollW={m['scrollW']} vw={m['vw']} btn={m['btn']} header={m['header']}")
    print(f"  brand={m['brand']} pill={m['pill']} position={m['btnPosition']}")
    ok(f'{label}: scrollWidth == innerWidth', m['scrollW'] == m['vw'],
       f"scrollW={m['scrollW']} vw={m['vw']}")
    ok(f'{label}: button is a floater (position absolute)', m['btnPosition'] == 'absolute',
       m['btnPosition'])
    ok(f'{label}: button sits BELOW the header (top {m["btn"]["top"]} >= header bottom {m["header"]["bottom"]})',
       m['btn']['top'] >= m['header']['bottom'] - 1,
       f"btn top={m['btn']['top']} header bottom={m['header']['bottom']}")
    ok(f'{label}: button is under the logo (left {m["btn"]["left"]} == brand left {m["brand"]["left"]})',
       abs(m['btn']['left'] - m['brand']['left']) <= 2,
       f"btn left={m['btn']['left']} brand left={m['brand']['left']}")
    ok(f'{label}: button fully inside viewport', m['btn']['right'] <= m['vw'] and m['btn']['left'] >= 0,
       str(m['btn']))
    ok(f'{label}: button does not overlap the BTC pill', not m['overlapsPill'])
    ok(f'{label}: button does not overlap hero eyebrow/heading',
       not m['overlapsEyebrow'] and not m['overlapsH1'],
       f"eyebrow={m['overlapsEyebrow']} h1={m['overlapsH1']}")
    ok(f'{label}: header-inner does not overflow',
       m['inner']['right'] <= m['vw'] and m['pill']['right'] <= m['vw'],
       f"pill right={m['pill']['right']}")
    # Tap the button: menu opens, panel drops BELOW the floater.
    page.locator('#mnavBtn').click(timeout=5000)
    page.wait_for_timeout(600)
    m2 = measure(page)
    print(f"  after tap: menuHidden={m2['menuHidden']} menu={m2['menu']} btn={m2['btn']}")
    ok(f'{label}: tapping the button opens the menu', not m2['menuHidden'])
    ok(f'{label}: menu panel starts below the floater (menu top {m2["menu"]["top"]} >= btn bottom {m2["btn"]["bottom"]})',
       m2['menu']['top'] >= m2['btn']['bottom'] - 1,
       f"menu top={m2['menu']['top']} btn bottom={m2['btn']['bottom']}")
    ok(f'{label}: floater does not overlap the open panel', not m2['overlapsMenu'])
    ok(f'{label}: menu links are visible', page.locator('#mnavMenu a').first.is_visible())
    page.screenshot(path=os.path.join(OUT, f'after-{label}-menu-open.png'),
                    clip={'x': 0, 'y': 0, 'width': 390, 'height': 500})
    # Tap again: menu closes.
    page.locator('#mnavBtn').click(timeout=5000)
    page.wait_for_timeout(400)
    m3 = measure(page)
    ok(f'{label}: tapping again closes the menu', m3['menuHidden'])
    # Scroll down: floater stays under the (sticky) header.
    page.evaluate('window.scrollTo(0, 800)')
    page.wait_for_timeout(600)
    m4 = measure(page)
    ok(f'{label}: after scrolling, floater still sits below the header',
       m4['btn']['top'] >= m4['header']['bottom'] - 1,
       f"btn top={m4['btn']['top']} header bottom={m4['header']['bottom']}")
    page.screenshot(path=os.path.join(OUT, f'after-{label}.png'),
                    clip={'x': 0, 'y': 0, 'width': 390, 'height': 300})
    page.close()

def run_tablet(browser):
    page = browser.new_page(viewport={'width': 820, 'height': 1180},
                            has_touch=True, is_mobile=True, device_scale_factor=2)
    page.goto(BASE, wait_until='commit', timeout=60000)
    page.wait_for_timeout(2000)
    m = measure(page)
    print(f'--- tablet 820px ---')
    print(f"  btn={m['btn']} inner={m['inner']} position={m['btnPosition']}")
    ok('tablet: button is in the header row (not a floater)',
       m['btnPosition'] != 'absolute' and
       m['btn']['top'] >= m['inner']['top'] and
       m['btn']['bottom'] <= m['inner']['bottom'] + 1,
       f"position={m['btnPosition']} btn={m['btn']} inner={m['inner']}")
    ok('tablet: button at the right end of the header',
       m['btn']['right'] <= m['vw'] and m['btn']['right'] > m['vw'] - 60,
       str(m['btn']))
    page.close()

def run_desktop(browser):
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    page.goto(BASE, wait_until='commit', timeout=60000)
    page.wait_for_timeout(2000)
    m = measure(page)
    print(f'--- desktop 1280px ---')
    print(f"  btn display={m['btnDisplay']} position={m['btnPosition']}")
    # At desktop width the hamburger is hidden by design and the full nav
    # links show instead — the move must not leak into desktop.
    ok('desktop: hamburger hidden (display none)', m['btnDisplay'] == 'none',
       m['btnDisplay'])
    ok('desktop: hamburger NOT absolutely positioned', m['btnPosition'] != 'absolute',
       m['btnPosition'])
    nav_visible = page.evaluate(
        "getComputedStyle(document.querySelector('.header nav')).display !== 'none' && "
        "document.querySelector('.header nav').getBoundingClientRect().width > 100")
    ok('desktop: full nav links visible instead', nav_visible)
    page.close()

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME,
                                    args=['--no-sandbox', '--disable-gpu'])
        run_phone(browser, '390px', 75792)
        run_phone(browser, '390px-6digit', 104250)
        run_tablet(browser)
        run_desktop(browser)
        browser.close()
    httpd.shutdown()
    print('VERIFY', 'PASS' if not fails else 'FAIL: ' + ', '.join(fails))
    raise SystemExit(1 if fails else 0)

if __name__ == '__main__':
    main()
