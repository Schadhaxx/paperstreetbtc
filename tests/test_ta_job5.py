#!/usr/bin/env python3
"""TA Drawing Fixes Job 5 checks (22 Nov 2026): panel state bugs. The scan
saw four panel/UI state bugs:
 (1) batch-click leaves SMA 50 unselected — setToggle('ma', true)
     auto-selected SMA 50, so a user batch-clicking the chips toggled it
     OFF again. Fix: no auto-select; the set is exactly what was clicked.
 (2) master off / Clear all leave pills selected — syncPanel read
     S.maSet alone, so chips showed on with the group off; Clear all
     never emptied maSet. Fix: chip on = group on AND chip selected;
     Clear all empties maSet; a chip click with the group off selects it
     and turns the group on.
 (3) chart-type ticks unreliable — candle-load fallbacks drew Line while
     CT/RGCT still said candles, so the menu/pill ticks lied. Fix: the
     fallbacks reset the type state to Line (range fallback, intraday
     catch, too-few-candles fall-through), so ticks always match the
     drawing.
 (4) switching range 1D->1W resets the chart type to Line — CT (1D) and
     RGCT (ranges) are separate state and the range-click handler never
     carried the type over. Fix: the range click carries the type (1D
     candles stay candles on 1W at the 4H default; back to 1D the
     original 1D size is restored, or the 4H size if it was picked on a
     range; Line carries over the same way).
Serves this checkout on localhost, stubs the price/candle feeds, drives
the real TA panel + type menu + range row on the clock page, and checks
each behaviour — including failure injection (a 4h load failure and an
intraday failure must both land on Line with Line ticks).
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
# Failure-injection flags, set per page-context below. FAIL_4H makes the
# Coinbase 4h candle load fail (range fallback); FAIL_INTRA makes both
# intraday sources fail (Coinbase 15-min + CoinGecko chart).
FAIL_4H = False
FAIL_INTRA = False
fails, n = [], 0

def chk(name, ok, detail=''):
    global n
    n += 1
    print('ok' if ok else 'FAIL', name, '' if ok else str(detail)[:400], flush=True)
    if not ok:
        fails.append(name)

def coinbase(route):
    u = urllib.parse.urlparse(route.request.url); q = urllib.parse.parse_qs(u.query)
    if 'spot' in u.path:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'data': {'amount': '77500.00', 'currency': 'USD'}}))
    g = int(q.get('granularity', ['86400'])[0]); end = int(FIXED.timestamp())
    if FAIL_4H and g == 3600:
        return route.fulfill(status=500, content_type='application/json', body='{"error":"4h unavailable"}')
    if FAIL_INTRA and g == 900:
        return route.fulfill(status=500, content_type='application/json', body='{"error":"intraday unavailable"}')
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
        if FAIL_INTRA:
            return route.fulfill(status=500, content_type='application/json', body='{"error":"intraday unavailable"}')
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'prices': [[int(FIXED.timestamp() * 1000) - i * 900000, 77500 + i] for i in range(96, 0, -1)]}))
    if 'raw.githubusercontent.com' in url or 'history.json' in url:
        return route.abort()
    if not url.startswith(U): return route.abort()
    route.continue_()

STATE_JS = """() => {
  const ls = JSON.parse(localStorage.getItem('ps-ta-v1') || 'null');
  const st = window.__BCTA ? window.__BCTA.state() : null;
  const sw = {}; document.querySelectorAll('.ta-panel [data-ta-key]').forEach(b => sw[b.getAttribute('data-ta-key')] = b.classList.contains('on'));
  const chips = {}; document.querySelectorAll('.ta-panel [data-ta-ma]').forEach(b => chips[b.getAttribute('data-ta-ma')] = {on: b.classList.contains('on'), disabled: b.disabled});
  return {ls, st, sw, chips};
}"""

MENU_JS = """() => {
  const m = document.querySelector('.ta-menu');
  if (!m || m.hidden) return null;
  /* innerText carries the tick as a trailing line ('\\n\\u2713'); strip it
     so the label is just the type/size name. */
  return [...m.querySelectorAll('.ta-mo')].map(b => ({t: b.innerText.split('\\n')[0].trim(), on: b.classList.contains('on')}));
}"""

PILL_JS = """() => {
  const el = document.getElementById('taTyp');
  return el ? el.textContent.replace(/\\s+/g, ' ').trim() : null;
}"""

CG_JS = """() => {
  const out = {};
  ['bcCt','bcCg'].forEach(id => { const el = document.getElementById(id); if (!el) { out[id]=null; return; }
    out[id] = {btns: [...el.querySelectorAll('button')].map(b => ({k: b.getAttribute('data-ct')||b.getAttribute('data-cg')||b.getAttribute('data-cggran'), on: b.classList.contains('on'), shown: b.style.display !== 'none'}))}; });
  return out;
}"""

def state(pg):
    return pg.evaluate(STATE_JS)

def menu_ticks(pg):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    t = pg.evaluate(MENU_JS)
    pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
    return t

def menu_pick(pg, attr, val):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [%s="%s"]' % (attr, val)); pg.wait_for_timeout(1200)

def load_clock_page(b):
    """Fresh browser context (clean localStorage) on the clock page."""
    ctx = b.new_context(viewport={'width': 1440, 'height': 900})
    pg = ctx.new_page()
    pg.clock.set_fixed_time(FIXED)
    pg.route('**/*', handler)
    pg.goto(U + 'clock/', wait_until='domcontentloaded')
    pg.wait_for_selector('#bcC', timeout=10000)
    pg.wait_for_selector('#taTyp', timeout=10000)
    pg.wait_for_timeout(3000)
    return ctx, pg

def main():
    global U, FAIL_4H, FAIL_INTRA
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
        pg = b.new_page(viewport={'width': 1440, 'height': 900})
        pg.clock.set_fixed_time(FIXED)
        pg.route('**/*', handler)
        pg.goto(U + 'clock/', wait_until='domcontentloaded')
        pg.wait_for_selector('#bcC', timeout=10000)
        pg.wait_for_timeout(3000)
        pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
        pg.wait_for_timeout(500)

        # ---- Bug 1: batch-click the MA chips ----
        print('--- Bug 1: batch-click MA chips on 1D Line ---')
        pg.click('.ta-panel [data-ta-key="ma"]'); pg.wait_for_timeout(800)
        order = ['sma20', 'sma50', 'sma200', 'ema20', 'ema50', 'ema200']
        for k in order:
            pg.click('.ta-panel [data-ta-ma="%s"]' % k)
            s = state(pg)
            print('  after clicking %s: maSet=%s' % (k, sorted((s['ls'] or {}).get('maSet', {}).keys()) if s['ls'] else None))
        s = state(pg)
        chk('Bug1: batch-click selects all 6 MA chips (SMA 50 included)',
            s['ls'] and set(s['ls'].get('maSet', {}).keys()) == set(order), s['ls'])
        chk('Bug1: all 6 chips show on in the panel',
            all(s['chips'][k]['on'] for k in order), s['chips'])

        # ---- Bug 2a: master off ----
        print('--- Bug 2a: MA master switch off ---')
        pg.click('.ta-panel [data-ta-key="ma"]'); pg.wait_for_timeout(800)
        s = state(pg)
        print('  after master off: sw.ma=%s chips=%s maSet=%s' % (s['sw'].get('ma'), {k: v['on'] for k, v in s['chips'].items()}, (s['ls'] or {}).get('maSet')))
        chk('Bug2a: master off shows all MA chips off',
            all(not v['on'] for v in s['chips'].values()), s['chips'])

        # ---- Bug 2b: Clear all ----
        print('--- Bug 2b: Clear all ---')
        pg.click('.ta-panel [data-ta-key="ma"]'); pg.wait_for_timeout(500)
        pg.click('.ta-panel [data-ta-ma="sma20"]'); pg.wait_for_timeout(300)
        pg.click('.ta-panel [data-ta-ma="sma50"]'); pg.wait_for_timeout(300)
        pg.click('.ta-panel [data-ta-key="bb"]'); pg.wait_for_timeout(500)
        pg.click('.ta-panel [data-ta-clear]'); pg.wait_for_timeout(800)
        s = state(pg)
        print('  after Clear all: sw=%s chips=%s maSet=%s' % (s['sw'], {k: v['on'] for k, v in s['chips'].items()}, (s['ls'] or {}).get('maSet')))
        chk('Bug2b: Clear all turns every switch off',
            all(not v for v in s['sw'].values()), s['sw'])
        chk('Bug2b: Clear all shows every MA chip off',
            all(not v['on'] for v in s['chips'].values()), s['chips'])
        chk('Bug2b: Clear all empties the saved MA set',
            not (s['ls'] or {}).get('maSet'), (s['ls'] or {}).get('maSet'))

        # ---- Bug 3: chart-type ticks ----
        print('--- Bug 3: type-menu ticks ---')
        t = menu_ticks(pg)
        print('  1D Line menu: %s' % t)
        chk('Bug3: 1D Line menu ticks Line on, nothing else',
            t and [x['t'] for x in t if x['on']] == ['Line'], t)
        menu_pick(pg, 'data-ta-pick', 'candles')
        s = state(pg)
        print('  after picking Candles on 1D: CT=%s' % (s['st'] or {}).get('CT'))
        t = menu_ticks(pg)
        print('  1D Candles menu: %s' % t)
        chk('Bug3: 1D Candles menu ticks Candles + 1H on',
            t and sorted(x['t'] for x in t if x['on']) == sorted(['Candles', '1H candles']), t)
        menu_pick(pg, 'data-ta-size', '4h')
        s = state(pg)
        print('  after picking 4H on 1D: CT=%s' % (s['st'] or {}).get('CT'))
        t = menu_ticks(pg)
        print('  1D 4H menu: %s' % t)
        chk('Bug3: 1D 4H menu ticks Candles + 4H on',
            t and sorted(x['t'] for x in t if x['on']) == sorted(['Candles', '4H candles']), t)
        # Range switch: ticks must follow the new range's state. With the
        # Job 5 carry-over, 1D 4H -> 1W stays on candles (4H), so the menu
        # must tick Candles + 4H — not Line.
        pg.click('#bcRgs button[data-r="1W"]'); pg.wait_for_timeout(1500)
        s = state(pg)
        t = menu_ticks(pg)
        print('  1W (after 1D 4H) menu: %s state=%s' % (t, {k: (s['st'] or {}).get(k) for k in ('rng', 'RGCT', 'RGGRAN')}))
        chk('Bug3: 1W menu ticks Candles + 4H on after 1D 4H -> 1W (type carried over)',
            t and sorted(x['t'] for x in t if x['on']) == sorted(['Candles', '4H candles']), t)
        s = state(pg)
        print('  on 1W Candles: RGCT=%s RGGRAN=%s' % ((s['st'] or {}).get('RGCT'), (s['st'] or {}).get('RGGRAN')))
        cg = pg.evaluate(CG_JS)
        print('  1W Candles bcCg/bcCt: %s' % cg)
        chk('Bug3: bcCg ticks show Candles + 4H on for 1W Candles',
            cg['bcCg'] and [x['k'] for x in cg['bcCg']['btns'] if x['on']] == ['candles', '4h'], cg)
        chk('Bug3: type pill reads 4H candles on 1W Candles',
            (pg.evaluate(PILL_JS) or '').strip() == '4H candles', pg.evaluate(PILL_JS))

        # ---- Bug 4: fresh page, 1D -> 1W keeps Candles (and back) ----
        # A fresh context: no carried state from the bugs 1-3 page.
        print('--- Bug 4: fresh page, 1D Candles -> 1W -> 1D ---')
        pg.close()
        ctx2, pg = load_clock_page(b)
        s = state(pg)
        chk('Bug4 setup: fresh page opens on 1D Line',
            (s['st'] or {}).get('rng') == '1D' and (s['st'] or {}).get('CT') == 'line', s['st'])
        menu_pick(pg, 'data-ta-pick', 'candles')
        s = state(pg)
        print('  on 1D Candles: CT=%s candViewActive=%s' % ((s['st'] or {}).get('CT'), (s['st'] or {}).get('candViewActive')))
        chk('Bug4 setup: 1D is on candles (1H) before the switch',
            (s['st'] or {}).get('CT') == '1h' and (s['st'] or {}).get('candViewActive') is True, s['st'])
        pg.click('#bcRgs button[data-r="1W"]'); pg.wait_for_timeout(1500)
        s = state(pg)
        print('  after switching to 1W: RGCT=%s RGGRAN=%s candViewActive=%s' % ((s['st'] or {}).get('RGCT'), (s['st'] or {}).get('RGGRAN'), (s['st'] or {}).get('candViewActive')))
        chk('Bug4: 1D Candles -> 1W keeps Candles (RGCT=candles)',
            (s['st'] or {}).get('RGCT') == 'candles', s['st'])
        chk('Bug4: 1D Candles -> 1W still shows candles',
            (s['st'] or {}).get('candViewActive') is True, s['st'])
        chk('Bug4: 1D Candles -> 1W uses the 4H size (1W default)',
            (s['st'] or {}).get('RGGRAN') == '4h', s['st'])
        t = menu_ticks(pg)
        print('  1W menu: %s' % t)
        chk('Bug4: 1W menu ticks Candles + 4H on',
            t and sorted(x['t'] for x in t if x['on']) == sorted(['Candles', '4H candles']), t)
        # Reverse: 1W Candles -> 1D comes back on candles — the ORIGINAL
        # 1D size (1H) is preserved, because CT was never reset.
        pg.click('#bcRgs button[data-r="1D"]'); pg.wait_for_timeout(1500)
        s = state(pg)
        print('  after switching back to 1D: CT=%s candViewActive=%s' % ((s['st'] or {}).get('CT'), (s['st'] or {}).get('candViewActive')))
        chk('Bug4: 1W Candles -> 1D comes back on candles (1H, the original 1D size)',
            (s['st'] or {}).get('CT') == '1h' and (s['st'] or {}).get('candViewActive') is True, s['st'])
        t = menu_ticks(pg)
        print('  1D menu after the return: %s' % t)
        chk('Bug4: 1D menu ticks Candles + 1H on after the return',
            t and sorted(x['t'] for x in t if x['on']) == sorted(['Candles', '1H candles']), t)
        chk('Bug4: type pill reads 1H candles after the return to 1D',
            (pg.evaluate(PILL_JS) or '').strip() == '1H candles', pg.evaluate(PILL_JS))
        # Line carries over too: pick Line on 1D, then 1W must be Line.
        menu_pick(pg, 'data-ta-pick', 'line')
        s = state(pg)
        chk('Bug4 setup: 1D is on Line before the Line-carry check',
            (s['st'] or {}).get('CT') == 'line', s['st'])
        pg.click('#bcRgs button[data-r="1W"]'); pg.wait_for_timeout(1500)
        s = state(pg)
        print('  after 1D Line -> 1W: RGCT=%s candViewActive=%s' % ((s['st'] or {}).get('RGCT'), (s['st'] or {}).get('candViewActive')))
        chk('Bug4: 1D Line -> 1W stays Line (RGCT=line)',
            (s['st'] or {}).get('RGCT') == 'line' and (s['st'] or {}).get('candViewActive') is False, s['st'])
        t = menu_ticks(pg)
        chk('Bug4: 1W menu ticks Line only after the Line carry',
            t and [x['t'] for x in t if x['on']] == ['Line'], t)
        # The other return path: 1D Line -> 1W Candles -> 1D. CT was
        # 'line', so the 1W 4H size carries back as 1D 4H (wasGran branch).
        menu_pick(pg, 'data-ta-pick', 'candles')
        s = state(pg)
        chk('Bug4 setup: 1W is on candles (4H) before the 4H-carry check',
            (s['st'] or {}).get('RGCT') == 'candles' and (s['st'] or {}).get('RGGRAN') == '4h', s['st'])
        pg.click('#bcRgs button[data-r="1D"]'); pg.wait_for_timeout(1500)
        s = state(pg)
        print('  after 1W Candles -> 1D (from 1D Line): CT=%s candViewActive=%s' % ((s['st'] or {}).get('CT'), (s['st'] or {}).get('candViewActive')))
        chk('Bug4: 1D Line -> 1W Candles -> 1D comes back on candles (4H)',
            (s['st'] or {}).get('CT') == '4h' and (s['st'] or {}).get('candViewActive') is True, s['st'])
        t = menu_ticks(pg)
        chk('Bug4: 1D menu ticks Candles + 4H on after the 4H carry',
            t and sorted(x['t'] for x in t if x['on']) == sorted(['Candles', '4H candles']), t)
        pg.close(); ctx2.close()

        # ---- Bug 3 fallbacks: a failed candle load must show Line ticks ----
        print('--- Bug 3 fallback: 4h load fails on 1W ---')
        FAIL_4H = True
        ctx3, pg3 = load_clock_page(b)
        menu_pick(pg3, 'data-ta-pick', 'candles')  # 1D 1H candles (intraday OK)
        pg3.click('#bcRgs button[data-r="1W"]'); pg3.wait_for_timeout(2000)
        s = state(pg3)
        print('  1W with 4h failed: RGCT=%s candViewActive=%s' % ((s['st'] or {}).get('RGCT'), (s['st'] or {}).get('candViewActive')))
        chk('Bug3-fallback: failed 4h load resets RGCT to line',
            (s['st'] or {}).get('RGCT') == 'line', s['st'])
        chk('Bug3-fallback: failed 4h load shows Line, not candles',
            (s['st'] or {}).get('candViewActive') is False, s['st'])
        t = menu_ticks(pg3)
        print('  1W menu after failed 4h: %s' % t)
        chk('Bug3-fallback: menu ticks Line only after the failed 4h load',
            t and [x['t'] for x in t if x['on']] == ['Line'], t)
        pill3 = pg3.evaluate(PILL_JS)
        chk('Bug3-fallback: pill reads Line after the failed 4h load',
            pill3 and 'Line' in pill3 and 'Candles' not in pill3, pill3)
        pg3.close(); ctx3.close()
        FAIL_4H = False

        print('--- Bug 3 fallback: intraday fails on 1D ---')
        FAIL_INTRA = True
        ctx4, pg4 = load_clock_page(b)
        menu_pick(pg4, 'data-ta-pick', 'candles')
        pg4.wait_for_timeout(1000)
        s = state(pg4)
        print('  1D with intraday failed: CT=%s candViewActive=%s' % ((s['st'] or {}).get('CT'), (s['st'] or {}).get('candViewActive')))
        chk('Bug3-fallback: failed intraday load resets CT to line',
            (s['st'] or {}).get('CT') == 'line', s['st'])
        chk('Bug3-fallback: failed intraday load shows Line, not candles',
            (s['st'] or {}).get('candViewActive') is False, s['st'])
        t = menu_ticks(pg4)
        print('  1D menu after failed intraday: %s' % t)
        chk('Bug3-fallback: menu ticks Line only after the failed intraday load',
            t and [x['t'] for x in t if x['on']] == ['Line'], t)
        pg4.close(); ctx4.close()
        FAIL_INTRA = False
        b.close()
    print('JOB5 %d checks, %d FAIL' % (n, len(fails)))
    for f in fails:
        print('  FAIL:', f)
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
