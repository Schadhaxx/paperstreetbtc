#!/usr/bin/env python3
"""TA Stage 1 checks (20 Nov 2026): chart-type pill + menu, TA pill, floating
panel, RSI strip container. Serves this checkout on localhost (or takes a base
URL argv[1] and a shots dir argv[2], as run_all.sh does), stubs the live-price
and candle feeds with deterministic data, and at phone 390 dark + desktop 1440
light verifies: the pill labels, every range x type combination through the new
menu (behaviour identical to the old buttons), the TA panel open/close, the RSI
strip, and the overlap check (target 0 hits) on the clock page and the popover.
Writes screenshots + overlap-check.json to the shots dir (default
handback/ta/). Nothing is drawn by TA in Stage 1; this test checks chrome only.
"""
import json, math, os, subprocess, sys, threading, functools, http.server, socketserver, urllib.parse, datetime as dt
from pathlib import Path

R = Path(__file__).resolve().parents[1]

def _find_chrome():
    # System Chrome first, then the Playwright browser cache. Default
    # Playwright launch needs the exact cached revision (installed 1.65.2
    # wants r1255, this cache has r1248), so use the cached executable
    # directly instead of relying on default discovery.
    for p in ['/usr/bin/google-chrome', '/usr/bin/chromium']:
        if os.path.exists(p):
            return p
    cache = Path.home() / '.cache' / 'ms-playwright'
    for pat in ('chromium-*/chrome-linux*/chrome',
                'chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell'):
        hits = sorted(cache.glob(pat))
        if hits:
            return str(hits[0])
    return None

CHROME = os.environ.get('CHROME_PATH') or _find_chrome()
FIXED = dt.datetime(2026, 10, 30, 20, tzinfo=dt.timezone.utc)
fails, n = [], 0

def chk(name, ok, detail=''):
    global n
    n += 1
    print('ok' if ok else 'FAIL', name, '' if ok else str(detail)[:200], flush=True)
    if not ok:
        fails.append(name)

def coinbase(route):
    u = urllib.parse.urlparse(route.request.url); q = urllib.parse.parse_qs(u.query)
    if 'spot' in u.path:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'data': {'amount': '77500.00', 'currency': 'USD'}}))
    g = int(q.get('granularity', ['86400'])[0]); end = int(FIXED.timestamp())
    rows, t = [], end - end % g
    while len(rows) < 300:
        o = 77500 + 900 * math.sin(t / g / 5.0); c = o + 350 * math.cos(t / g / 3.0)
        rows.append([t, min(o, c) - 120, max(o, c) + 120, o, c, 10]); t -= g
    route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))

def handler(route):
    url = route.request.url
    if 'coinbase.com' in url: return coinbase(route)
    if 'paperstreet-quotes' in url:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'btc': {'usd': 77500, 'chg24h': 1.2}}))
    if 'coingecko.com' in url:
        if 'simple/price' in url:
            return route.fulfill(status=200, content_type='application/json', body=json.dumps({'bitcoin': {'usd': 77500, 'usd_24h_change': 1.2}}))
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'prices': [[int(FIXED.timestamp() * 1000) - i * 900000, 77500 + i] for i in range(96, 0, -1)]}))
    if 'raw.githubusercontent.com' in url or 'history.json' in url:
        return route.abort()
    if not url.startswith(U): return route.abort()
    route.continue_()

def inked(pg, sel='#bcC'):
    return pg.evaluate("""(s) => { const c = document.querySelector(s); if (!c || !c.width || !c.height) return false;
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let ink = 0;
      for (let i = 0; i < d.length; i += 16) { if (d[i+3] > 0) ink++; }
      return ink > 50; }""", sel)

def main():
    global U
    srv = None
    if len(sys.argv) > 1:
        base = sys.argv[1].rstrip('/')
        U = base + '/'
    else:
        class Q(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a): pass
        srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=str(R))); srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        U = 'http://127.0.0.1:%d/' % srv.server_address[1]
    shots = Path(sys.argv[2]) if len(sys.argv) > 2 else R / 'handback' / 'ta'
    shots.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    overlap = {}
    with sync_playwright() as p:
        launch = {'executable_path': CHROME} if CHROME else {}
        b = p.chromium.launch(**launch)
        # ---- clock page, phone 390 dark ----
        ctx = b.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce'); ctx.route('**/*', handler)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'clock/index.html', wait_until='networkidle')
            pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            chk('clock 390 dark: chart paints', inked(pg))
            chk('clock 390 dark: TA module loaded', pg.evaluate("!!window.__BTTA && !!window.__BCTA"))
            chk('clock 390 dark: type pill says Line', pg.inner_text('#taTyp').strip().startswith('Line'))
            chk('clock 390 dark: TA pill present', pg.locator('#taPill').is_visible())
            chk('clock 390 dark: RSI strip hidden when off', pg.evaluate("document.getElementById('taRsi').hidden"))
            # menu: 1D 1H candles through the new menu
            pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
            chk('clock 390 dark: menu lists 1H + 4H on 1D', pg.evaluate("!!document.querySelector('.ta-menu [data-ta-size=\"1h\"]') && !!document.querySelector('.ta-menu [data-ta-size=\"4h\"]')"))
            pg.click('.ta-menu [data-ta-size="1h"]'); pg.wait_for_timeout(1200)
            chk('clock 390 dark: pill says 1H candles', pg.inner_text('#taTyp').strip().startswith('1H candles'))
            chk('clock 390 dark: 1H candles paint', inked(pg))
            chk('clock 390 dark: note says 1h candles', '1h candles' in pg.inner_text('#bcNt'))
            pg.screenshot(path=str(shots / 'clock-390-dark-1h-candles.png'), animations='disabled')
            # back to Line, then TA panel + RSI
            pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
            pg.click('.ta-menu [data-ta-pick="line"]'); pg.wait_for_timeout(900)
            chk('clock 390 dark: pill back to Line', pg.inner_text('#taTyp').strip().startswith('Line'))
            pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
            chk('clock 390 dark: TA panel opens with 4 toggles', pg.locator('.ta-panel .ta-sw').count() == 4)
            # Gating on 1D Line: RSI is ENABLED (Job 3 ungreyed it — the
            # strip now has a scale, bands and a live value), and the
            # RSI strip stays hidden here only because RSI is off by
            # default in this test (no seed). Bollinger and SMA 200 are
            # ENABLED on 1D Line (Job 2 ungreyed them — the pre-warm
            # makes them valid from index 0 there now), and SMA 20
            # stays live. Trends is ENABLED on 1D Line (Job 1 ungreyed
            # it — the lines draw there now).
            chk('clock 390 dark: Trends toggle enabled on 1D (Job 1)', not pg.is_disabled('.ta-panel [data-ta-key="tl"]'))
            chk('clock 390 dark: Bollinger toggle enabled on 1D (Job 2)', not pg.is_disabled('.ta-panel [data-ta-key="bb"]'))
            chk('clock 390 dark: RSI toggle enabled on 1D (Job 3)', not pg.is_disabled('.ta-panel [data-ta-key="rsi"]'))
            chk('clock 390 dark: SMA 200 chip enabled on 1D (Job 2)', not pg.is_disabled('.ta-panel [data-ta-ma="sma200"]'))
            chk('clock 390 dark: SMA 20 chip enabled on 1D', not pg.is_disabled('.ta-panel [data-ta-ma="sma20"]'))
            chk('clock 390 dark: RSI strip stays hidden (RSI off)', pg.evaluate("document.getElementById('taRsi').hidden"))
            # The MA group switch is live on 1D. Job 5 removed the SMA 50
            # auto-select, so turning the group on with nothing selected
            # shows no badge (nothing draws); selecting a chip shows
            # badge 1, and turning the group off clears it.
            pg.click('.ta-panel [data-ta-key="ma"]'); pg.wait_for_timeout(600)
            chk('clock 390 dark: MA group on with nothing selected shows no badge (Job 5)', '1' not in pg.inner_text('#taPill'))
            pg.click('.ta-panel [data-ta-ma="sma50"]'); pg.wait_for_timeout(600)
            chk('clock 390 dark: pill count badge 1', pg.inner_text('#taPill').strip().startswith('TA1') or '1' in pg.inner_text('#taPill'))
            pg.click('.ta-panel [data-ta-key="ma"]'); pg.wait_for_timeout(400)
            pg.screenshot(path=str(shots / 'clock-390-dark-ta-panel.png'), animations='disabled')
            r = pg.evaluate("window.__taRects()")
            overlap['clock-390-dark-panel'] = r
            chk('clock 390 dark: overlap 0 with panel open', r['overlaps'] == [], r['overlaps'])
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            chk('clock 390 dark: Esc closes panel', pg.evaluate("document.querySelector('.ta-panel').hidden"))
            # range x type: 1W candles Daily, 1M candles Weekly, 5Y candles
            # Daily (Job 9: 5Y has candles now — the pill is enabled and the
            # 1M candles carry over, reset to the 5Y Daily default), then
            # back to 1D 1H candles (Job 5 carry through the 5Y candle view;
            # before Job 9, 5Y was Line-only so the carry did not apply and
            # the pill came back Line).
            pg.click('#bcRgs button[data-r="1W"]'); pg.wait_for_timeout(900)
            pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
            pg.click('.ta-menu [data-ta-size="daily"]'); pg.wait_for_timeout(1200)
            chk('clock 390 dark: 1W pill says Candles \u00b7 Daily', 'Candles' in pg.inner_text('#taTyp') and 'Daily' in pg.inner_text('#taTyp'))
            pg.click('#bcRgs button[data-r="1M"]'); pg.wait_for_timeout(900)
            pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
            pg.click('.ta-menu [data-ta-size="weekly"]'); pg.wait_for_timeout(1200)
            chk('clock 390 dark: 1M pill says Candles \u00b7 Weekly', 'Candles' in pg.inner_text('#taTyp') and 'Weekly' in pg.inner_text('#taTyp'))
            pg.click('#bcRgs button[data-r="5Y"]'); pg.wait_for_timeout(900)
            chk('clock 390 dark: 5Y pill enabled, says Candles \u00b7 Daily (Job 9)', pg.evaluate("!document.getElementById('taTyp').disabled && document.getElementById('taTyp').textContent.includes('Candles') && document.getElementById('taTyp').textContent.includes('Daily')"))
            pg.click('#bcRgs button[data-r="1D"]'); pg.wait_for_timeout(1200)
            chk('clock 390 dark: back to 1D 1H candles (Job 5 carry, Job 9)', '1H candles' in pg.inner_text('#taTyp'))
            chk('clock 390 dark: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('clock 390 dark', False, str(e)[:200])
        ctx.close()
        # ---- clock page, desktop 1440 light ----
        ctx = b.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce', color_scheme='light'); ctx.route('**/*', handler)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'clock/index.html', wait_until='networkidle')
            pg.evaluate("document.documentElement.setAttribute('data-theme','light')")
            pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            chk('clock 1440 light: chart paints', inked(pg))
            pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
            r = pg.evaluate("window.__taRects()")
            overlap['clock-1440-light-panel'] = r
            chk('clock 1440 light: overlap 0 with panel open', r['overlaps'] == [], r['overlaps'])
            pg.screenshot(path=str(shots / 'clock-1440-light-ta-panel.png'), animations='disabled')
            pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
            chk('clock 1440 light: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('clock 1440 light', False, str(e)[:200])
        ctx.close()
        # ---- popover on the homepage, phone 390 dark ----
        ctx = b.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce'); ctx.route('**/*', handler)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'index.html', wait_until='networkidle')
            pg.evaluate("document.getElementById('hdrTick').click()"); pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            chk('popover 390 dark: chart paints', inked(pg))
            chk('popover 390 dark: pills present', pg.locator('#taTyp').is_visible() and pg.locator('#taPill').is_visible())
            pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
            r = pg.evaluate("window.__taRects()")
            overlap['popover-390-dark-panel'] = r
            chk('popover 390 dark: overlap 0 with panel open', r['overlaps'] == [], r['overlaps'])
            pg.screenshot(path=str(shots / 'popover-390-dark-ta-panel.png'), animations='disabled')
            pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
            pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
            r2 = pg.evaluate("window.__taRects()")
            overlap['popover-390-dark-menu'] = r2
            chk('popover 390 dark: overlap 0 with menu open', r2['overlaps'] == [], r2['overlaps'])
            pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
            chk('popover 390 dark: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('popover 390 dark', False, str(e)[:200])
        ctx.close()
        b.close()
    (shots / 'overlap-check.json').write_text(json.dumps(overlap, indent=1))
    print('TA STAGE 1:', 'PASS (%d checks)' % n if not fails else 'FAIL (%d/%d)' % (len(fails), n))
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
