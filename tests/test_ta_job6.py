#!/usr/bin/env python3
"""TA Drawing Fixes Job 6 checks (22 Nov 2026): comparison note + TA pill badge.
The scan saw two things:
 (1) The comparison-hiding works, but the note "TA shows on BTC alone.
     Turn off comparisons to see it." lives ONLY inside the TA panel — a
     user with a comparison on sees no TA and no explanation. Fix: the
     same note as a line under the pills row (outside the panel), visible
     when a comparison is hiding something that WOULD draw.
 (2) The TA pill badge was stuck on the toggle count: syncPill only ran
     on TA toggle clicks, never on a draw, and nOn() counts toggles, not
     drawings. Fix: the badge shows nDrawing() (comparison on -> 0,
     gated MAs excluded — none left on 1W after Job 12 ungated them
     there — trendlines with no lines on this view excluded) and
     syncPill runs in afterDraw, so a comparison toggle or a range
     change re-counts at once.
Serves this checkout on localhost, stubs the price/candle feeds and a
fresh ta-lines.json fixture, and drives the real TA panel + comparison
toggles + range row on the clock page (desktop dark, phone 390 dark, and
a light-theme colour check).
"""
import json, math, os, sys, threading, functools, http.server, socketserver, urllib.parse, datetime as dt
from pathlib import Path

R = Path(__file__).resolve().parents[1]  # the checkout under test

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
    print('ok' if ok else 'FAIL', name, '' if ok else str(detail)[:400], flush=True)
    if not ok:
        fails.append(name)

def iso(d):
    return d.strftime('%Y-%m-%dT%H:%M:%SZ')

def lvl(price, kind, brk=False, ext=False):
    return {'price': price, 'kind': kind, 'score': 5.0, 'rawScore': 6.0, 'distAtr': 1.0,
            'touches': 5, 'lastTouch': iso(FIXED), 'ageCandles': 3, 'broken': brk, 'held': False, 'extreme': ext}

def slp(kind, slope, anchor, anchor_price):
    return {'kind': kind, 'slope': slope, 'anchor': {'t': iso(anchor), 'price': anchor_price},
            'touches': 5, 'score': 5.0, 'rawScore': 6.0, 'distAtr': 1.0, 'priceNow': anchor_price,
            'broken': False, 'held': False}

def tf(asOf, levels, sloped):
    return {'asOf': iso(asOf), 'atr': 700, 'lastClose': 77500, 'levels': levels, 'sloped': sloped,
            'missingSupport': False, 'missingResistance': False}

def fixture():
    h1, h4, d1 = FIXED - dt.timedelta(minutes=10), FIXED - dt.timedelta(hours=1), FIXED - dt.timedelta(hours=5)
    t1h = tf(h1, [lvl(79500, 'resistance'), lvl(76000, 'support')], [slp('support', 30, FIXED - dt.timedelta(hours=12), 75500)])
    t4h = tf(h4, [lvl(79500, 'resistance')], [slp('support', 120, FIXED - dt.timedelta(hours=20), 74000)])
    t1d = tf(d1, [lvl(81000, 'resistance'), lvl(75000, 'support')], [slp('support', -30, dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc), 76000)])
    return {'v': 1, 'kind': 'ta-lines', 'asOf': iso(FIXED), 'timeframes': {'1h': t1h, '4h': t4h, '1d': t1d}}

FIXTURE = fixture()

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
        return route.fulfill(status=200, content_type='application/json', body=json.dumps(FIXTURE))
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

BADGE_JS = """() => {
  const pill = document.getElementById('taPill');
  const b = pill ? pill.querySelector('.ta-n') : null;
  const out = document.querySelector('.ta-cmp-out');
  const inPanel = document.querySelector('.ta-panel .ta-cmp');
  const st = window.__BCTA ? window.__BCTA.state() : null;
  const tl = window.__TA_TL_DEBUG ? window.__TA_TL_DEBUG() : null;
  let noteBox = null;
  if (out && !out.hidden) { const r = out.getBoundingClientRect(); noteBox = {x: r.left, y: r.top, w: r.width, h: r.height, right: r.right}; }
  return {
    badge: b ? b.textContent : null,
    pillText: pill ? pill.textContent.replace(/\\s+/g, ' ').trim() : null,
    cmp: window.__BCTA && window.__BCTA.cmp ? !!window.__BCTA.cmp() : null,
    rng: st ? st.rng : null,
    tlStatus: tl ? tl.status : null,
    tlLines: tl && tl.last && tl.last.lines ? tl.last.lines.length : null,
    noteOut: out ? {hidden: out.hidden, text: out.textContent.trim()} : null,
    noteBox,
    noteInPanel: inPanel ? {hidden: inPanel.hidden, text: inPanel.textContent.trim()} : null,
    overflowX: document.documentElement.scrollWidth > window.innerWidth,
  };
}"""

NOTE_TEXT = 'TA shows on BTC alone. Turn off comparisons to see it.'

def open_panel(pg):
    pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
    pg.wait_for_timeout(400)

def close_panel(pg):
    pg.keyboard.press('Escape'); pg.wait_for_timeout(300)

def all_on(pg):
    open_panel(pg)
    pg.click('.ta-panel [data-ta-key="ma"]'); pg.wait_for_timeout(500)
    for k in ['sma20', 'sma50', 'sma200', 'ema20', 'ema50', 'ema200']:
        pg.click('.ta-panel [data-ta-ma="%s"]' % k); pg.wait_for_timeout(200)
    pg.click('.ta-panel [data-ta-key="bb"]'); pg.wait_for_timeout(500)
    pg.click('.ta-panel [data-ta-key="rsi"]'); pg.wait_for_timeout(500)
    pg.click('.ta-panel [data-ta-key="tl"]'); pg.wait_for_timeout(2000)
    close_panel(pg)

def clear_all(pg):
    open_panel(pg)
    pg.click('.ta-panel [data-ta-clear]'); pg.wait_for_timeout(500)
    close_panel(pg)

def load_clock_page(b, width=1440, height=900):
    ctx = b.new_context(viewport={'width': width, 'height': height})
    pg = ctx.new_page()
    pg.clock.set_fixed_time(FIXED)
    pg.route('**/*', handler)
    pg.goto(U + 'clock/', wait_until='domcontentloaded')
    pg.wait_for_selector('#bcC', timeout=10000)
    pg.wait_for_selector('#taTyp', timeout=10000)
    pg.wait_for_timeout(3000)
    return ctx, pg

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
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        launch = {'executable_path': CHROME} if CHROME else {}
        b = p.chromium.launch(**launch)
        ctx, pg = load_clock_page(b)

        # ---- Badge counts drawings: all 9 on, 1D Line ----
        print('--- Badge: all on, 1D Line ---')
        all_on(pg)
        s = pg.evaluate(BADGE_JS)
        print('  all on 1D: %s' % s)
        chk('Badge: all 9 on (6 MAs + BB + RSI + TL) read 9 on 1D Line',
            s['badge'] == '9' and s['tlStatus'] == 'live' and s['tlLines'] == 8, s)
        chk('Note: external note exists with the panel wording, hidden with no comparison',
            s['noteOut'] and s['noteOut']['text'] == NOTE_TEXT and s['noteOut']['hidden'] is True, s['noteOut'])

        # ---- 1W: all 9 draw now (Job 12 ungated the 3 MAs there) ----
        print('--- Badge: 1W, all on (Job 12) ---')
        pg.click('#bcRgs button[data-r="1W"]'); pg.wait_for_timeout(2000)
        s = pg.evaluate(BADGE_JS)
        print('  all on 1W: %s' % s)
        chk('Badge: all on reads 9 on 1W (6 MAs + BB + RSI + TL, Job 12)',
            s['badge'] == '9' and s['tlLines'] == 3, s)
        chk('Note: still hidden on 1W with no comparison',
            s['noteOut'] and s['noteOut']['hidden'] is True, s['noteOut'])

        # ---- Comparison on: badge 0, note visible outside the panel ----
        print('--- Comparison on: badge 0, note visible ---')
        pg.click('#bcSpx'); pg.wait_for_timeout(1500)
        s = pg.evaluate(BADGE_JS)
        print('  cmp on: %s' % s)
        chk('Badge: comparison on reads no badge (0 drawing) though 9 toggles are on',
            s['badge'] is None and s['pillText'] == 'TA' and s['cmp'] is True, s)
        chk('Note: external note visible while the comparison hides TA',
            s['noteOut'] and s['noteOut']['hidden'] is False and s['noteOut']['text'] == NOTE_TEXT, s['noteOut'])
        chk('Note: external note sits under the pills row, inside the viewport',
            s['noteBox'] and s['noteBox']['right'] <= 1440 and s['noteBox']['h'] > 0, s['noteBox'])
        chk('Note: panel note still shows too (unchanged behaviour)',
            s['noteInPanel'] and s['noteInPanel']['hidden'] is False, s['noteInPanel'])

        # ---- Comparison off: badge and note return ----
        print('--- Comparison off: badge and note return ---')
        pg.click('#bcSpx'); pg.wait_for_timeout(1500)
        s = pg.evaluate(BADGE_JS)
        print('  cmp off: %s' % s)
        chk('Badge: comparison off reads 9 again on 1W (Job 12)',
            s['badge'] == '9' and s['cmp'] is False, s)
        chk('Note: external note hides again with the comparison off',
            s['noteOut'] and s['noteOut']['hidden'] is True, s['noteOut'])

        # ---- TA off + comparison on: no note (nothing to explain) ----
        print('--- TA off + comparison on: no note ---')
        clear_all(pg)
        pg.click('#bcSpx'); pg.wait_for_timeout(1500)
        s = pg.evaluate(BADGE_JS)
        print('  TA off, cmp on: %s' % s)
        chk('Badge: TA off + comparison on reads no badge',
            s['badge'] is None and s['cmp'] is True, s)
        chk('Note: external note stays hidden when TA is off (nothing hidden)',
            s['noteOut'] and s['noteOut']['hidden'] is True, s['noteOut'])
        pg.click('#bcSpx'); pg.wait_for_timeout(1200)

        # ---- 1W, only sma20/sma50/ema50 on: badge 3 (Job 12 ungated
        # them there, so they draw now — the badge counts what draws) ----
        print('--- 1W, only sma20/sma50/ema50 on: badge 3 ---')
        pg.click('#bcRgs button[data-r="1D"]'); pg.wait_for_timeout(1500)
        open_panel(pg)
        pg.click('.ta-panel [data-ta-key="ma"]'); pg.wait_for_timeout(500)
        for k in ['sma20', 'sma50', 'ema50']:
            pg.click('.ta-panel [data-ta-ma="%s"]' % k); pg.wait_for_timeout(200)
        close_panel(pg)
        pg.click('#bcRgs button[data-r="1W"]'); pg.wait_for_timeout(2000)
        s = pg.evaluate(BADGE_JS)
        print('  1W sma20/sma50/ema50 only: %s' % s)
        chk('Badge: only sma20/sma50/ema50 on reads 3 on 1W (they draw now, Job 12)',
            s['badge'] == '3' and s['rng'] == '1W', s)

        # ---- 5Y, TL only: badge 0 (trendlines off by design there) ----
        print('--- 5Y, TL only: badge 0 ---')
        clear_all(pg)
        open_panel(pg)
        pg.click('.ta-panel [data-ta-key="tl"]'); pg.wait_for_timeout(1000)
        close_panel(pg)
        pg.click('#bcRgs button[data-r="5Y"]'); pg.wait_for_timeout(2000)
        s = pg.evaluate(BADGE_JS)
        print('  5Y TL only: %s' % s)
        chk('Badge: TL only reads no badge on 5Y (no lines on this range)',
            s['badge'] is None and s['tlStatus'] == 'unavailable' and s['tlLines'] == 0, s)
        pg.close(); ctx.close()

        # ---- Phone 390 dark: note visible, no overflow ----
        print('--- Phone 390 dark: comparison note ---')
        ctx2, pg2 = load_clock_page(b, 390, 844)
        open_panel(pg2)
        pg2.click('.ta-panel [data-ta-key="bb"]'); pg2.wait_for_timeout(800)
        close_panel(pg2)
        pg2.click('#bcRgs button[data-r="1W"]'); pg2.wait_for_timeout(1500)
        pg2.click('#bcSpx'); pg2.wait_for_timeout(1500)
        s = pg2.evaluate(BADGE_JS)
        print('  phone cmp on: %s' % s)
        chk('Phone: external note visible with a comparison on',
            s['noteOut'] and s['noteOut']['hidden'] is False, s['noteOut'])
        chk('Phone: badge reads no badge with the comparison on',
            s['badge'] is None and s['cmp'] is True, s)
        chk('Phone: note fits the 390px viewport, no horizontal overflow',
            s['noteBox'] and s['noteBox']['right'] <= 390 and s['overflowX'] is False, (s['noteBox'], s['overflowX']))
        # Light theme: the note takes the light muted colour.
        pg2.evaluate("() => document.documentElement.setAttribute('data-theme','light')")
        pg2.wait_for_timeout(300)
        col = pg2.evaluate("() => { const el = document.querySelector('.ta-cmp-out'); return el ? getComputedStyle(el).color : null; }")
        print('  phone light note colour: %s' % col)
        chk('Phone light: note reads the light muted colour (#64748b)',
            col == 'rgb(100, 116, 139)', col)
        pg2.close(); ctx2.close()
        b.close()
    print('JOB6 %d checks, %d FAIL' % (n, len(fails)))
    for f in fails:
        print('  FAIL:', f)
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
