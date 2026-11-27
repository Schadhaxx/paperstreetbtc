#!/usr/bin/env python3
"""TA rotate hint checks (21 Nov 2026, final TA job): a small pill
"Rotate for full screen" at the bottom-left of the clock-page chart,
portrait only. Tap enters full-screen chart mode and shows a "rotate
your phone" prompt while still portrait; the prompt fades after ~5s,
hides on landscape rotation, on exit, or on tap. iOS cannot force
landscape — the hint only suggests, never locks orientation. Verifies at
phone 390 dark + light: the hint is visible in portrait and hidden in
landscape; it sits inside the chart box at the bottom-left; it overlaps
nothing it must never cover (TA pill, RSI strip, price pill, Keep
screen on, Exit, Light pill); tap enters full-screen chart mode with
the prompt; the prompt clears the fs bar, price pill and Exit. Serves
this checkout on localhost (or takes a base URL argv[1] and a shots dir
argv[2], as run_all.sh does), stubs the live-price and candle feeds
with deterministic data. Screenshots: portrait with the hint + landscape
without it, dark + light (4 images).
"""
import json, math, os, sys, threading, functools, http.server, socketserver, urllib.parse, datetime as dt
from pathlib import Path

R = Path(__file__).resolve().parents[1]

def _find_chrome():
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
    if 'ta-lines.json' in url:
        return route.fulfill(status=404, content_type='application/json', body='{}')
    if 'coinbase.com' in url: return coinbase(route)
    if 'paperstreet-quotes' in url:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'btc': {'usd': 77500, 'chg24h': 1.2}}))
    if 'coingecko.com' in url:
        if 'simple/price' in url:
            return route.fulfill(status=200, content_type='application/json', body=json.dumps({'bitcoin': {'usd': 77500, 'usd_24h_change': 1.2}}))
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'prices': [[int(FIXED.timestamp() * 1000) - i * 900000, 77500 + i] for i in range(96, 0, -1)]}))
    if not url.startswith(U): return route.abort()
    route.continue_()

def inked(pg, sel='#bcC'):
    return pg.evaluate("""(s) => { const c = document.querySelector(s); if (!c || !c.width || !c.height) return false;
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let ink = 0;
      for (let i = 0; i < d.length; i += 16) { if (d[i+3] > 0) ink++; }
      return ink > 50; }""", sel)

def rects(pg):
    """Hint/prompt/box/protected rects; null when the element is absent or
    not displayed. __taRects (btcchart-ta.js) supplies the TA pill, RSI
    strip, chart box and the protected controls."""
    return pg.evaluate("""() => {
      const vis = el => { if (!el) return false; const b = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        return cs.display !== 'none' && cs.visibility !== 'hidden' && b.width > 0 && b.height > 0; };
      const r = el => { if (!vis(el)) return null; const b = el.getBoundingClientRect();
        return {x: b.left, y: b.top, r: b.right, b: b.bottom, w: b.width, h: b.height}; };
      const t = window.__taRects ? window.__taRects() : {};
      const prot = t.prot || {};
      const keep = (k, el) => { const q = prot[k]; return (q && q.w > 0 && q.h > 0) ? q : null; };
      return {hint: r(document.querySelector('#rotateHint')),
        prompt: r(document.querySelector('#rotatePrompt')),
        box: (t.box && t.box.w > 0) ? t.box : null,
        taPill: (t.pill && t.pill.w > 0) ? t.pill : null,
        rsi: (t.rsi && t.rsi.w > 0) ? t.rsi : null,
        keep: keep('Keep screen on'),
        light: keep('Light/Dark pill'),
        exit: keep('Exit full screen'),
        pricePill: keep('Price pill'),
        fsbar: r(document.querySelector('.v4-fs-bar')),
        fs: document.documentElement.classList.contains('v4-fs-chart')};
    }""")

def ov(a, b):
    return bool(a and b and a['x'] < b['r'] and b['x'] < a['r'] and a['y'] < b['b'] and b['y'] < a['b'])

def inside(a, b):
    return bool(a and b and a['x'] >= b['x'] and a['r'] <= b['r'] and a['y'] >= b['y'] and a['b'] <= b['b'])

def open_page(p, width, height, light=False):
    ctx = p.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce',
                        color_scheme='light' if light else 'dark')
    ctx.route('**/*', handler)
    # Must-fix (27 Nov 2026): seed RSI on, so the strip-shows check in
    # Phase A is meaningful (shows because RSI is on, not merely because
    # the gate is gone — the gate is gone, so on means visible).
    ctx.add_init_script("localStorage.setItem('ps-ta-v1', JSON.stringify({rsi:true}));")
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
    pg.clock.set_fixed_time(FIXED)
    pg.goto(U + 'clock/index.html', wait_until='networkidle')
    if light:
        pg.evaluate("document.documentElement.setAttribute('data-theme','light')")
    pg.wait_for_selector('#bcC', timeout=8000)
    # The hint is display:none in landscape, so wait for attached, not visible.
    pg.wait_for_selector('#rotateHint', state='attached', timeout=8000)
    pg.wait_for_timeout(1500)
    return ctx, pg, errs

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
    with sync_playwright() as p:
        launch = {'executable_path': CHROME} if CHROME else {}
        b = p.chromium.launch(**launch)
        # ---- Phase A: portrait 390 dark ----
        ctx, pg, errs = open_page(b, 390, 844)
        try:
            chk('A portrait 390 dark: chart paints', inked(pg))
            chk('A portrait 390 dark: hint present', pg.evaluate("!!document.querySelector('#rotateHint')"))
            chk('A hint text is "Rotate for full screen"', pg.inner_text('#rotateHint').strip() == '\u21bb Rotate for full screen', pg.inner_text('#rotateHint'))
            q = rects(pg)
            chk('A hint sits inside the chart box', inside(q['hint'], q['box']), str(q['hint']) + ' vs ' + str(q['box']))
            chk('A hint is bottom-left of the box (<=16px from left + bottom edges)',
                q['hint'] and q['box'] and q['hint']['x'] - q['box']['x'] <= 16 and q['box']['b'] - q['hint']['b'] <= 16,
                str(q['hint']) + ' vs ' + str(q['box']))
            chk('A hint does not cover the TA pill', not ov(q['hint'], q['taPill']), str(q['taPill']))
            chk('A hint does not cover Keep screen on', not ov(q['hint'], q['keep']), str(q['keep']))
            chk('A hint does not cover the Light pill', not ov(q['hint'], q['light']), str(q['light']))
            chk('A hint does not cover Exit (hidden in normal mode)', not ov(q['hint'], q['exit']), str(q['exit']))
            # Must-fix (27 Nov 2026): RSI is ungated now, so the strip
            # shows with RSI seeded on — the hint must not cover it
            # (it sits inside the chart box; the strip is the grid row
            # below the box).
            chk('A RSI strip shows with RSI on (must-fix)', q['rsi'] is not None)
            chk('A hint does not cover the RSI strip', not ov(q['hint'], q['rsi']), str(q['rsi']))
            pg.screenshot(path=str(shots / 'rotate-hint-390-dark-portrait.png'), animations='disabled')
            # ---- Phase B: tap the hint ----
            pg.click('#rotateHint'); pg.wait_for_timeout(800)
            q = rects(pg)
            chk('B tap hint: full-screen chart mode on', q['fs'], str(q))
            chk('B tap hint: rotate prompt visible', q['prompt'] is not None, str(q['prompt']))
            chk('B prompt text asks to rotate the phone',
                'Rotate your phone' in pg.inner_text('#rotatePrompt'), pg.inner_text('#rotatePrompt'))
            pg.screenshot(path=str(shots / 'rotate-hint-390-dark-fs-prompt.png'), animations='disabled')
            chk('B prompt does not cover the fs bar (Exit / Keep screen on)',
                not ov(q['prompt'], q['fsbar']), str(q['fsbar']))
            chk('B prompt does not cover the price pill', not ov(q['prompt'], q['pricePill']), str(q['pricePill']))
            chk('B prompt does not cover Exit', not ov(q['prompt'], q['exit']), str(q['exit']))
            pg.clock.run_for(6000); pg.wait_for_timeout(300)
            q = rects(pg)
            chk('B prompt fades after ~5s', q['prompt'] is None, str(q['prompt']))
            chk('B still full-screen chart after the prompt fades', q['fs'])
            pg.keyboard.press('Escape'); pg.wait_for_timeout(600)
            q = rects(pg)
            chk('B Escape exits full screen, hint visible again', not q['fs'] and q['hint'] is not None, str(q))
            # Tap again, then rotate to landscape: hint + prompt both hide.
            pg.click('#rotateHint'); pg.wait_for_timeout(800)
            q = rects(pg)
            chk('B second tap: full-screen chart + prompt again', q['fs'] and q['prompt'] is not None, str(q))
            pg.set_viewport_size({'width': 844, 'height': 390}); pg.wait_for_timeout(800)
            q = rects(pg)
            chk('B landscape: prompt hidden on rotate', q['prompt'] is None, str(q['prompt']))
            chk('B landscape: hint hidden (chart already wide)', q['hint'] is None, str(q['hint']))
            chk('B landscape: still full-screen chart after rotate', q['fs'])
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            chk('A portrait 390 dark: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('A/B portrait 390 dark', False, str(e)[:200])
        ctx.close()
        # ---- Phase C: landscape 390 dark (fresh page) ----
        ctx, pg, errs = open_page(b, 844, 390)
        try:
            chk('C landscape 844x390 dark: chart paints', inked(pg))
            q = rects(pg)
            chk('C landscape dark: hint hidden', q['hint'] is None, str(q['hint']))
            chk('C landscape dark: prompt hidden', q['prompt'] is None, str(q['prompt']))
            pg.screenshot(path=str(shots / 'rotate-hint-390-dark-landscape.png'), animations='disabled')
            chk('C landscape dark: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('C landscape 390 dark', False, str(e)[:200])
        ctx.close()
        # ---- Phase D: portrait 390 light ----
        ctx, pg, errs = open_page(b, 390, 844, light=True)
        try:
            chk('D portrait 390 light: chart paints', inked(pg))
            q = rects(pg)
            chk('D portrait light: hint visible', q['hint'] is not None, str(q['hint']))
            chk('D portrait light: hint inside the box, bottom-left',
                inside(q['hint'], q['box']) and q['hint']['x'] - q['box']['x'] <= 16 and q['box']['b'] - q['hint']['b'] <= 16,
                str(q['hint']))
            chk('D portrait light: hint does not cover the TA pill', not ov(q['hint'], q['taPill']))
            chk('D portrait light: hint does not cover the Light pill', not ov(q['hint'], q['light']))
            pg.screenshot(path=str(shots / 'rotate-hint-390-light-portrait.png'), animations='disabled')
            pg.click('#rotateHint'); pg.wait_for_timeout(800)
            q = rects(pg)
            chk('D portrait light: tap enters full-screen chart + prompt',
                q['fs'] and q['prompt'] is not None, str(q))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            chk('D portrait light: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('D portrait 390 light', False, str(e)[:200])
        ctx.close()
        # ---- Phase E: landscape 390 light ----
        ctx, pg, errs = open_page(b, 844, 390, light=True)
        try:
            q = rects(pg)
            chk('E landscape light: hint hidden', q['hint'] is None, str(q['hint']))
            chk('E landscape light: prompt hidden', q['prompt'] is None, str(q['prompt']))
            pg.screenshot(path=str(shots / 'rotate-hint-390-light-landscape.png'), animations='disabled')
            chk('E landscape light: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('E landscape 390 light', False, str(e)[:200])
        ctx.close()
        b.close()
    print('TA ROTATE HINT:', 'PASS (%d checks)' % n if not fails else 'FAIL (%d/%d)' % (len(fails), n))
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
