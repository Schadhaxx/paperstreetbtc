#!/usr/bin/env python3
"""TA Stage 2 checks (20 Nov 2026): browser indicators (SMA/EMA, Bollinger,
RSI) drawn on #bcC after the price series in every native view, with 200+
warm-up closes so the first visible candle already has a valid value; RSI
strip; tooltip values; comparison-on note; perf (<4 ms/frame all-on,
measured); all-off pixel-identical (screenshots for pixel_diff.py).
Serves this checkout on localhost (or takes a base URL argv[1] and a shots
dir argv[2], as run_all.sh does), stubs the live-price and candle feeds with
deterministic data, and verifies at phone 390 dark + desktop 1440 light.
The expected indicator values are computed here in Python (independent
implementation, same conventions as tests/test_ta_indicators.js) from the
exact warm-up + visible closes the browser used (read via
window.__TA_DEBUG), so the comparison is exact, not assumed.
"""
import json, math, os, subprocess, sys, threading, functools, http.server, socketserver, urllib.parse, datetime as dt
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
# Stage 1: seed Bollinger + MA (SMA 50) + RSI on, so the tests observe the
# values instead of clicking the toggles on. last1DSize is the TA default ('1h').
SEED = "localStorage.setItem('ps-ta-v1', JSON.stringify({tl:false,bb:true,ma:true,maSet:{sma50:true},rsi:true,rsiCol:false,last1DSize:'1h'}));"
fails, n = [], 0

def chk(name, ok, detail=''):
    global n
    n += 1
    print('ok' if ok else 'FAIL', name, '' if ok else str(detail)[:200], flush=True)
    if not ok:
        fails.append(name)

# --- independent indicator maths (same conventions as the JS) ---
def sma(c, p):
    out = [None] * len(c)
    for i in range(p - 1, len(c)):
        out[i] = sum(c[i - p + 1:i + 1]) / p
    return out

def ema(c, p):
    out = [None] * len(c)
    k = 2 / (p + 1)
    out[p - 1] = sum(c[:p]) / p
    for i in range(p, len(c)):
        out[i] = c[i] * k + out[i - 1] * (1 - k)
    return out

def boll(c, p=20, m=2):
    mid = sma(c, p)
    up, lo = [None] * len(c), [None] * len(c)
    for i in range(p - 1, len(c)):
        w = c[i - p + 1:i + 1]
        mu = sum(w) / p
        sd = math.sqrt(sum((x - mu) ** 2 for x in w) / p)
        up[i], lo[i] = mu + m * sd, mu - m * sd
    return mid, up, lo

def rsi(c, p=14):
    out = [None] * len(c)
    g = [max(c[i] - c[i - 1], 0) for i in range(1, len(c))]
    l = [max(c[i - 1] - c[i], 0) for i in range(1, len(c))]
    ag, al = sum(g[:p]) / p, sum(l[:p]) / p
    out[p] = 100.0 if al == 0 else (0.0 if ag == 0 else 100 - 100 / (1 + ag / al))
    for i in range(p + 1, len(c)):
        ag = (ag * (p - 1) + g[i - 1]) / p
        al = (al * (p - 1) + l[i - 1]) / p
        out[i] = 100.0 if al == 0 else (0.0 if ag == 0 else 100 - 100 / (1 + ag / al))
    return out

def close(a, b):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= 1e-6 * max(1, abs(b))

def check_values(name, dbg, ma_keys=('sma50',)):
    """Compare the browser's last indicator values with the Python values
    computed from the exact warm-up + visible closes the browser used.
    ma_keys: the enabled moving averages (e.g. ('sma50',) or
    ('sma20', 'sma50', 'sma200')) — each is checked from
    dbg['last']['mas'][key], the per-MA dict (Stage 3 fix, item 6:
    stacking MAs)."""
    if not dbg:
        chk(name, False, 'no __TA_DEBUG'); return
    full = (dbg['warmCloses'] or []) + (dbg['closes'] or [])
    w = dbg['warm']
    mid, up, lo = boll(full, 20, 2)
    mid, up, lo = mid[w:], up[w:], lo[w:]
    rs = rsi(full, 14)[w:]
    last = dbg['last']
    ok = True
    detail = []
    mas = last.get('mas') or {}
    for key in ma_keys:
        kind, per = key[:3], int(key[3:])
        want = (ema if kind == 'ema' else sma)(full, per)[w:][-1]
        got = mas.get(key)
        if not close(got, want):
            ok = False; detail.append('%s got %s want %s' % (key, got, want))
    for key, got, want in (('bbUp', last.get('bbUp'), up[-1]),
                           ('bbLo', last.get('bbLo'), lo[-1]),
                           ('bbMid', last.get('bbMid'), mid[-1]),
                           ('rsi', last.get('rsi'), rs[-1])):
        if not close(got, want):
            ok = False; detail.append('%s got %s want %s' % (key, got, want))
    chk(name, ok, '; '.join(detail))

def ma_colours_present(pg, rgbs):
    """True if every (R,G,B) in rgbs appears on the main chart canvas
    (+/-40 per channel for antialiasing). Used by the stacking test to
    prove each enabled MA line is actually drawn in its own colour."""
    return pg.evaluate("""(rgbs) => { const c = document.querySelector('#bcC'); if (!c) return false;
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      const found = rgbs.map(() => false);
      for (let i = 0; i < d.length; i += 4) {
        const r = d[i], g = d[i+1], b = d[i+2], a = d[i+3];
        if (a < 200) continue;
        rgbs.forEach((rgb, j) => { if (!found[j] && Math.abs(r-rgb[0])<40 && Math.abs(g-rgb[1])<40 && Math.abs(b-rgb[2])<40) found[j] = true; });
      } return found; }""", rgbs)

def coinbase(route):
    u = urllib.parse.urlparse(route.request.url); q = urllib.parse.parse_qs(u.query)
    if 'spot' in u.path:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'data': {'amount': '77500.00', 'currency': 'USD'}}))
    g = int(q.get('granularity', ['86400'])[0]); end = int(FIXED.timestamp())
    # Honour the requested window (like the real API): the warm-up fetches
    # page back in windows, so each must return its own slice, not the
    # same 300 rows ending at FIXED.
    if 'end' in q:
        try: end = min(end, int(dt.datetime.fromisoformat(q['end'][0].replace('Z', '+00:00')).timestamp()))
        except Exception: pass
    start = 0
    if 'start' in q:
        try: start = int(dt.datetime.fromisoformat(q['start'][0].replace('Z', '+00:00')).timestamp())
        except Exception: pass
    rows, t = [], end - end % g
    while len(rows) < 300 and t >= start:
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

def has_overlay(pg):
    """True if an overlay line is present on the main chart canvas: MA pink
    (light #db2777 / dark #f472b6), SMA 50 amber (light #d97706 / dark
    #fbbf24), or Bollinger violet (light #7c3aed / dark #a78bfa), +/-40
    per channel for antialiasing. Either one proves drawOverlays ran —
    the MA alone is not guaranteed visible: on a candle view after a fall
    it can sit entirely above the price y-range (its values are still
    valid, just off-chart). Amber is included because on a 1W view the
    only MA left drawing may be SMA 50 (SMA 20/50 gated there)."""
    return pg.evaluate("""() => { const c = document.querySelector('#bcC'); if (!c) return false;
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      const near = (r,g,b, R,G,B) => Math.abs(r-R)<40 && Math.abs(g-G)<40 && Math.abs(b-B)<40;
      for (let i = 0; i < d.length; i += 4) {
        const r = d[i], g = d[i+1], b = d[i+2], a = d[i+3];
        if (a < 200) continue;
        if (near(r,g,b, 219,39,119) || near(r,g,b, 244,114,182)) return true;
        if (near(r,g,b, 217,119,6) || near(r,g,b, 251,191,36)) return true;
        if (near(r,g,b, 124,58,237) || near(r,g,b, 167,139,250)) return true;
      } return false; }""")

def open_panel(pg):
    """Open the TA panel if it is hidden (the pill toggles it)."""
    if pg.evaluate("document.querySelector('.ta-panel').hidden"):
        pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)

def wait_warm(pg, want=200, timeout=8000):
    """Wait until the intraday warm-up fetch has landed (range views are
    synchronous from DATA, so this returns at once there)."""
    try:
        pg.wait_for_function("""(w) => { const d = window.__TA_DEBUG && window.__TA_DEBUG();
          return d && d.warm >= w; }""", arg=want, timeout=timeout)
        return True
    except Exception:
        return False

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
    perf = {}
    with sync_playwright() as p:
        launch = {'executable_path': CHROME} if CHROME else {}
        b = p.chromium.launch(**launch)
        # ---- clock page, phone 390 dark: 1D line, all overlays on ----
        ctx = b.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce'); ctx.route('**/*', handler)
        ctx.add_init_script(SEED)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'clock/index.html', wait_until='networkidle')
            pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            chk('clock 390 dark: chart paints', inked(pg))
            chk('clock 390 dark: TA module loaded', pg.evaluate("!!window.__BTTA && !!window.__BCTA && !!window.__TA_DEBUG"))
            open_panel(pg)
            # Gating on 1D Line: RSI is ENABLED (Job 3 ungreyed it — the
            # strip now has a scale, bands and a live value, and Job 2's
            # pre-warm makes it valid from index 0 there now). Bollinger
            # and SMA 200 are ENABLED (Job 2 ungreyed them). SMA 20/50
            # and EMA 20 stay live.
            chk('clock 390 dark: Bollinger toggle enabled on 1D (Job 2)', not pg.is_disabled('.ta-panel [data-ta-key="bb"]'))
            chk('clock 390 dark: RSI toggle enabled on 1D (Job 3)', not pg.is_disabled('.ta-panel [data-ta-key="rsi"]'))
            chk('clock 390 dark: SMA 200 chip enabled on 1D (Job 2)', not pg.is_disabled('.ta-panel [data-ta-ma="sma200"]'))
            chk('clock 390 dark: SMA 20/50 + EMA 20 chips enabled on 1D', not pg.is_disabled('.ta-panel [data-ta-ma="sma20"]') and not pg.is_disabled('.ta-panel [data-ta-ma="sma50"]') and not pg.is_disabled('.ta-panel [data-ta-ma="ema20"]'))
            chk('clock 390 dark: warm-up fetch lands (>=200 closes)', wait_warm(pg, 200))
            dbg = pg.evaluate("window.__TA_DEBUG()")
            chk('clock 390 dark: 1D line geometry', dbg and dbg['kind'] == '1d-line', dbg and dbg['kind'])
            chk('clock 390 dark: first visible point valid (MA/BB/RSI)', dbg and dbg['firstValid'] == {'ma': 0, 'bb': 0, 'rsi': 0}, dbg and dbg['firstValid'])
            check_values('clock 390 dark: indicator values match Python', dbg)
            chk('clock 390 dark: RSI strip shows (Job 3)', not pg.evaluate("document.getElementById('taRsi').hidden"))
            tip = pg.evaluate("window.__BCTA.taTip('1d-line', 50)")
            chk('clock 390 dark: tooltip shows SMA 50 + BB + RSI (Job 3)', tip and len(tip) == 3 and 'SMA 50' in tip[0]['t'] and 'BB 20' in tip[1]['t'] and 'RSI' in tip[2]['t'], str(tip)[:160])
            # Stage 3 fix (item 6): stacking MAs — SMA 20 on here; SMA 200
            # is live on 1D now (Job 2), but it is added on 1M Line, where
            # the stacking values are checked against Python for the
            # daily-line geometry; then all three stack and all three
            # colours draw.
            pg.click('.ta-panel [data-ta-ma="sma20"]'); pg.wait_for_timeout(600)
            chk('clock 390 dark: SMA 200 chip enabled on 1D after SMA 20 on (Job 2)', not pg.is_disabled('.ta-panel [data-ta-ma="sma200"]'))
            pg.click('#bcRgs button[data-r="1M"]'); pg.wait_for_timeout(1200)
            open_panel(pg)
            pg.click('.ta-panel [data-ta-ma="sma200"]'); pg.wait_for_timeout(600)
            chk('clock 390 dark: three MA chips on', pg.evaluate("['sma20','sma50','sma200'].every(k => document.querySelector('.ta-panel [data-ta-ma=\"' + k + '\"]').classList.contains('on'))"))
            dbgS = pg.evaluate("window.__TA_DEBUG()")
            chk('clock 390 dark: stacking first valid 0 for all three', dbgS and dbgS['firstValid'] == {'ma': 0, 'bb': 0, 'rsi': 0} and dbgS['firstValidMas'] == {'sma20': 0, 'sma50': 0, 'sma200': 0}, dbgS and (dbgS['firstValid'], dbgS['firstValidMas']))
            check_values('clock 390 dark: stacked SMA 20/50/200 match Python', dbgS, ma_keys=('sma20', 'sma50', 'sma200'))
            tipS = pg.evaluate("window.__BCTA.taTip('daily-line', 20)")
            chk('clock 390 dark: tooltip lists all three MAs + BB + RSI (Job 3)', tipS and len(tipS) == 5 and 'SMA 20' in tipS[0]['t'] and 'SMA 50' in tipS[1]['t'] and 'SMA 200' in tipS[2]['t'] and 'BB 20' in tipS[3]['t'] and 'RSI' in tipS[4]['t'], str(tipS)[:200])
            chk('clock 390 dark: pill count badge 5 (BB + 3 MAs + RSI)', '5' in pg.inner_text('#taPill'))
            # dark theme: SMA 20 pink #f472b6, SMA 50 amber #fbbf24, SMA 200 teal #14b8a6
            cols = ma_colours_present(pg, [[244, 114, 182], [251, 191, 36], [20, 184, 166]])
            chk('clock 390 dark: all three MA colours drawn', cols == [True, True, True], str(cols))
            pg.screenshot(path=str(shots / 'clock-390-dark-ta-all-on.png'), animations='disabled')
            # EMA stacks alongside SMA: add EMA 50, both still match Python
            open_panel(pg)
            pg.click('.ta-panel [data-ta-ma="ema50"]'); pg.wait_for_timeout(600)
            dbg2 = pg.evaluate("window.__TA_DEBUG()")
            check_values('clock 390 dark: EMA 50 stacks with SMA 50', dbg2, ma_keys=('sma50', 'ema50'))
            # all off again (Clear all): strip hides, pill count clears
            open_panel(pg)
            pg.click('.ta-panel [data-ta-clear]'); pg.wait_for_timeout(600)
            chk('clock 390 dark: Clear all hides RSI strip', pg.evaluate("document.getElementById('taRsi').hidden"))
            pg.screenshot(path=str(shots / 'clock-390-dark-ta-all-off.png'), animations='disabled')
            p = pg.evaluate("window.__TA_PERF")
            perf['phone-390-dark'] = p
            chk('clock 390 dark: perf samples taken', p and p['n'] >= 3, str(p))
            chk('clock 390 dark: all-on <4 ms/frame', p and p['avg'] < 4, str(p))
            r = pg.evaluate("window.__taRects()")
            chk('clock 390 dark: overlap 0 with panel open', r['overlaps'] == [], r['overlaps'])
            pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
            chk('clock 390 dark: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('clock 390 dark', False, str(e)[:200])
        ctx.close()
        # ---- clock page, desktop 1440 light: 1Y line + 1W candles + compare ----
        ctx = b.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce', color_scheme='light'); ctx.route('**/*', handler)
        ctx.add_init_script(SEED)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'clock/index.html', wait_until='networkidle')
            pg.evaluate("document.documentElement.setAttribute('data-theme','light')")
            pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            pg.click('#bcRgs button[data-r="1Y"]'); pg.wait_for_timeout(1200)
            open_panel(pg)
            # Gating on 1Y Line: RSI is live (Job 3 ungreyed it);
            # Bollinger and SMA 200 are live (Job 2 ungreyed Bollinger everywhere).
            chk('clock 1440 light: Bollinger toggle enabled on 1Y (Job 2)', not pg.is_disabled('.ta-panel [data-ta-key="bb"]'))
            chk('clock 1440 light: RSI toggle enabled on 1Y (Job 3)', not pg.is_disabled('.ta-panel [data-ta-key="rsi"]'))
            chk('clock 1440 light: SMA 200 chip enabled (kept on 1Y)', not pg.is_disabled('.ta-panel [data-ta-ma="sma200"]'))
            dbg = pg.evaluate("window.__TA_DEBUG()")
            chk('clock 1440 light: 1Y line geometry', dbg and dbg['kind'] == 'daily-line', dbg and dbg['kind'])
            chk('clock 1440 light: DATA warm-up >=200 closes', dbg and dbg['warm'] >= 200, dbg and dbg['warm'])
            chk('clock 1440 light: first visible point valid', dbg and dbg['firstValid'] == {'ma': 0, 'bb': 0, 'rsi': 0}, dbg and dbg['firstValid'])
            check_values('clock 1440 light: 1Y values match Python', dbg)
            pg.screenshot(path=str(shots / 'clock-1440-light-ta-all-on-1y.png'), animations='disabled')
            # comparison on: overlays hide, note shows, strip hides
            pg.click('#bcSpx'); pg.wait_for_timeout(900)
            chk('clock 1440 light: compare note shows in panel', pg.evaluate("!document.querySelector('.ta-panel .ta-cmp').hidden"))
            chk('clock 1440 light: RSI strip hides on compare', pg.evaluate("document.getElementById('taRsi').hidden"))
            pg.click('#bcSpx'); pg.wait_for_timeout(900)
            chk('clock 1440 light: compare note hides again', pg.evaluate("document.querySelector('.ta-panel .ta-cmp').hidden"))
            # must-fix: cmp() must clear when leaving a compare-on range
            # for 1D or a candle view, even though the chip stays on
            pg.click('#bcSpx'); pg.wait_for_timeout(900)
            chk('clock 1440 light: compare note shows at 1Y', pg.evaluate("!document.querySelector('.ta-panel .ta-cmp').hidden"))
            chk('clock 1440 light: RSI strip hides on compare at 1Y', pg.evaluate("document.getElementById('taRsi').hidden"))
            # (a) switch to 1D without turning Spx off
            pg.click('#bcRgs button[data-r="1D"]'); pg.wait_for_timeout(900)
            chk('clock 1440 light: 1D warm-up lands', wait_warm(pg, 200))
            chk('clock 1440 light: 1D cmp() false with Spx still on', pg.evaluate("window.__BCTA.cmp()===false"))
            chk('clock 1440 light: 1D RSI strip shows with Spx still on (Job 3, cmp off on 1D)', not pg.evaluate("document.getElementById('taRsi').hidden"))
            chk('clock 1440 light: 1D compare note hidden with Spx still on', pg.evaluate("document.querySelector('.ta-panel .ta-cmp').hidden"))
            chk('clock 1440 light: 1D overlays drawn with Spx still on', has_overlay(pg))
            # (b) back to 1Y (compare still on), then 1W + daily candles
            pg.click('#bcRgs button[data-r="1Y"]'); pg.wait_for_timeout(1200)
            chk('clock 1440 light: compare note shows again at 1Y', pg.evaluate("!document.querySelector('.ta-panel .ta-cmp').hidden"))
            pg.click('#bcRgs button[data-r="1W"]'); pg.wait_for_timeout(900)
            pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
            pg.click('.ta-menu [data-ta-size="daily"]'); pg.wait_for_timeout(1200)
            chk('clock 1440 light: 1W candles cmp() false with Spx still on', pg.evaluate("window.__BCTA.cmp()===false"))
            chk('clock 1440 light: 1W candles RSI strip shows with Spx still on (Job 3, cmp off on 1W candles)', not pg.evaluate("document.getElementById('taRsi').hidden"))
            chk('clock 1440 light: 1W candles compare note hidden with Spx still on', pg.evaluate("document.querySelector('.ta-panel .ta-cmp').hidden"))
            chk('clock 1440 light: 1W candles overlays draw (BB + SMA 200 ungated, Job 2) with Spx still on', has_overlay(pg))
            # restore: compare off, so the rest of the section runs as before
            pg.click('#bcSpx'); pg.wait_for_timeout(900)
            # 1W daily candles with overlays on
            pg.click('#bcRgs button[data-r="1W"]'); pg.wait_for_timeout(900)
            pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
            pg.click('.ta-menu [data-ta-size="daily"]'); pg.wait_for_timeout(1200)
            dbg3 = pg.evaluate("window.__TA_DEBUG()")
            chk('clock 1440 light: 1W candle geometry', dbg3 and dbg3['kind'] == 'candles-range', dbg3 and dbg3['kind'])
            chk('clock 1440 light: 1W candles first valid', dbg3 and dbg3['firstValid'] == {'ma': 0, 'bb': 0, 'rsi': 0}, dbg3 and dbg3['firstValid'])
            check_values('clock 1440 light: 1W candle values match Python', dbg3)
            # 1D 4h candles with overlays on (warm-up fetch path)
            pg.click('#bcRgs button[data-r="1D"]'); pg.wait_for_timeout(900)
            pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
            pg.click('.ta-menu [data-ta-size="4h"]'); pg.wait_for_timeout(1200)
            chk('clock 1440 light: 1D 4h warm-up lands', wait_warm(pg, 200))
            dbg4 = pg.evaluate("window.__TA_DEBUG()")
            chk('clock 1440 light: 1D 4h geometry', dbg4 and dbg4['kind'] == 'candles-1d', dbg4 and dbg4['kind'])
            chk('clock 1440 light: 1D 4h first valid', dbg4 and dbg4['firstValid'] == {'ma': 0, 'bb': 0, 'rsi': 0}, dbg4 and dbg4['firstValid'])
            check_values('clock 1440 light: 1D 4h values match Python', dbg4)
            pg.screenshot(path=str(shots / 'clock-1440-light-ta-all-on-1d-4h.png'), animations='disabled')
            # 1W 4h candles (second 4h warm-up path, cut at the first visible bucket)
            pg.click('#bcRgs button[data-r="1W"]'); pg.wait_for_timeout(900)
            pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
            pg.click('.ta-menu [data-ta-size="4h"]'); pg.wait_for_timeout(1500)
            chk('clock 1440 light: 1W 4h warm-up lands', wait_warm(pg, 200))
            dbg5 = pg.evaluate("window.__TA_DEBUG()")
            chk('clock 1440 light: 1W 4h geometry', dbg5 and dbg5['kind'] == 'candles-range', dbg5 and dbg5['kind'])
            chk('clock 1440 light: 1W 4h first valid', dbg5 and dbg5['firstValid'] == {'ma': 0, 'bb': 0, 'rsi': 0}, dbg5 and dbg5['firstValid'])
            check_values('clock 1440 light: 1W 4h values match Python', dbg5)
            p = pg.evaluate("window.__TA_PERF")
            perf['desktop-1440-light'] = p
            chk('clock 1440 light: perf samples taken', p and p['n'] >= 3, str(p))
            chk('clock 1440 light: all-on <4 ms/frame', p and p['avg'] < 4, str(p))
            chk('clock 1440 light: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('clock 1440 light', False, str(e)[:200])
        ctx.close()
        # ---- popover on the homepage, phone 390 dark ----
        ctx = b.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce'); ctx.route('**/*', handler)
        ctx.add_init_script(SEED)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'index.html', wait_until='networkidle')
            pg.evaluate("document.getElementById('hdrTick').click()"); pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            open_panel(pg)
            chk('popover 390 dark: Bollinger toggle enabled on 1D (Job 2)', not pg.is_disabled('.ta-panel [data-ta-key="bb"]'))
            chk('popover 390 dark: warm-up fetch lands', wait_warm(pg, 200))
            dbg = pg.evaluate("window.__TA_DEBUG()")
            check_values('popover 390 dark: indicator values match Python', dbg)
            pg.screenshot(path=str(shots / 'popover-390-dark-ta-all-on.png'), animations='disabled')
            r = pg.evaluate("window.__taRects()")
            chk('popover 390 dark: overlap 0 with panel open', r['overlaps'] == [], r['overlaps'])
            chk('popover 390 dark: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('popover 390 dark', False, str(e)[:200])
        ctx.close()
        b.close()
    (shots / 'ta-stage2-perf.json').write_text(json.dumps(perf, indent=1))
    print('TA STAGE 2:', 'PASS (%d checks)' % n if not fails else 'FAIL (%d/%d)' % (len(fails), n))
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
