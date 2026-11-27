#!/usr/bin/env python3
"""Must-fixes from Grok Bot's Friday review (27 Nov 2026) — regression test.

Covers, per tree (checks self-adapt: a check is skipped, not failed, when the
tree has no such code — the candle-layout hook exists only where the item-8
fixes landed, labelPlacements only where the item-9 tag spread landed):

1.  recap/2026-11 copy: the Low-close cell keeps '(provisional)' and the
    note keeps the Tiingo sentence (static read).
6.  RSI switch enabled + strip visible on 1D/1W; 5Y/10Y/Max year labels are
    consecutive years, none skipped or repeated; 6M Candles -> 5Y either
    keeps candles or explains the Line-only range (pill title + note) and
    keeps the candles preference, so returning to 6M restores candles.
7.  1W Line: the y-axis includes the whole Bollinger band (floor at or
    below the lowest lower-band value, top at or above the highest upper
    value, recomputed independently from the probe's closes); SMA 200
    draws in teal, not the old green (and not the support-line green).
8.  (hook trees only) 10Y candle floor >= 0; 5Y/10Y candle labels carry
    the year; 1W 4H labels never repeat a date; 1D time labels are the
    neutral axis grey, not candle red/green.
9.  (Job 12 only) 10Y/Max Line floor >= 0; the 1D trendline price tags
    never overlap (placed centres >= 16px apart — the pills are 16px
    tall), verified on a bottom-clustered trendline fixture.

Serves this checkout on localhost (or takes the base URL as argv[1],
shots dir as argv[2] like the other ta_job tests), stubs the price/candle
feeds (Coinbase stub serves the repo's own real daily closes for
granularity 86400), frozen clock 2026-10-30 20:00 UTC, all TA overlays on.
The trendline fixture clusters five/six levels in a $180 band just above
the 1D-4h plot floor, so the old push-down-only tag pass would pile them
at the plot bottom.
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
fails, n, skipped = [], 0, 0

def chk(name, ok, detail=''):
    global n
    n += 1
    print('ok' if ok else 'FAIL', name, '' if ok else str(detail)[:300], flush=True)
    if not ok:
        fails.append(name)

def skip(name, why):
    global skipped
    skipped += 1
    print('skip', name, '-', why, flush=True)

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

def fixture_cluster():
    # Bottom cluster: levels in a $180 band just above the 1D-4h plot floor
    # ($76,665), so the old push-down-only tag pass piles them at B-8.
    h1, h4, d1 = FIXED - dt.timedelta(minutes=10), FIXED - dt.timedelta(hours=1), FIXED - dt.timedelta(hours=5)
    t1h = tf(h1, [lvl(76900, 'support')], [slp('support', 30, FIXED - dt.timedelta(hours=12), 75500)])
    t4h = tf(h4, [lvl(76940, 'resistance'), lvl(76860, 'support'), lvl(76780, 'support')], [slp('support', 120, FIXED - dt.timedelta(hours=20), 74000)])
    t1d = tf(d1, [lvl(76820, 'resistance'), lvl(76760, 'support')], [slp('support', -30, dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc), 76000)])
    return {'v': 1, 'kind': 'ta-lines', 'asOf': iso(FIXED), 'timeframes': {'1h': t1h, '4h': t4h, '1d': t1d}}

FIXTURE = fixture_cluster()

def base_price(t_ms):
    t = t_ms / 1000.0
    return 77500 + 900 * math.sin(t / 18000.0) + 350 * math.cos(t / 10800.0)

DATA_DAILY = None
def load_data_daily():
    global DATA_DAILY
    if DATA_DAILY is None:
        d = json.load(open(R / 'assets' / 'data' / 'btc-daily.json'))['d']
        DATA_DAILY = [(int(dt.datetime.fromisoformat(p[0]).replace(tzinfo=dt.timezone.utc).timestamp()), p[1]) for p in d]
    return DATA_DAILY

def coinbase(route):
    u = urllib.parse.urlparse(route.request.url); q = urllib.parse.parse_qs(u.query)
    if 'spot' in u.path:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'data': {'amount': '77500.00', 'currency': 'USD'}}))
    g = int(q.get('granularity', ['86400'])[0])
    end = int(dt.datetime.fromisoformat(q['end'][0].replace('Z', '+00:00')).timestamp()) if 'end' in q else int(FIXED.timestamp())
    start = int(dt.datetime.fromisoformat(q['start'][0].replace('Z', '+00:00')).timestamp()) if 'start' in q else end - 300 * g
    if g == 86400:
        daily = load_data_daily()
        rows, prev = [], None
        for t, c in daily:
            if start <= t < end:
                o = prev if prev is not None else c
                rows.append([t, min(o, c), max(o, c), o, c, 10])
            prev = c
        rows.sort(key=lambda r: r[0])
        return route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))
    rows, t = [], end - end % g
    while t >= start and len(rows) < 300:
        o = base_price(t * 1000); c = base_price((t + g) * 1000)
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

MEASURE_JS = """() => {
  const d = window.__TA_DEBUG ? window.__TA_DEBUG() : null;
  const L = window.__BTC_LINE_LAYOUT || null;
  const C = window.__BTC_CANDLE_LAYOUT || null;
  const st = window.__BCTA ? window.__BCTA.state() : null;
  const rsiEl = document.querySelector('.ta-rsi');
  const sw = document.querySelector('.ta-panel [data-ta-key="rsi"]');
  const pill = document.getElementById('taTyp');
  const note = document.getElementById('bcNt');
  const tl = window.__TA_TL_DEBUG ? window.__TA_TL_DEBUG() : null;
  return {layout: L ? {kind: L.kind, yTicks: L.yTicks, xLabels: L.xLabels} : null,
    candle: C ? {kind: C.kind, lo: C.lo, hi: C.hi, yLabels: C.yLabels, xLabels: C.xLabels} : null,
    state: st,
    rsiSwitchDisabled: sw ? sw.disabled : null,
    rsiHidden: rsiEl ? rsiEl.hidden : null,
    rsiHeader: rsiEl ? (rsiEl.querySelector('.ta-rsi-t b')||{}).textContent : null,
    typePill: pill ? {label: (pill.querySelector('span')||{}).textContent, disabled: pill.disabled, title: pill.getAttribute('title'), aria: pill.getAttribute('aria-label')} : null,
    note: note ? note.textContent : null,
    debug: d ? {kind: d.kind, n: d.n, warm: d.warm, closes: d.closes, warmCloses: d.warmCloses} : null,
    labelPlacements: tl && tl.last ? (tl.last.labelPlacements || null) : null};
}"""

def colour_count(pg, rgb, sel='#bcC', tol=10):
    return pg.evaluate("""([rgb, sel, tol]) => {
      const cv = document.querySelector(sel);
      if (!cv) return -1;
      const ctx = cv.getContext('2d');
      const w = cv.width, h = cv.height;
      const d = ctx.getImageData(0, 0, w, h).data;
      let c = 0;
      for (let i = 0; i < d.length; i += 4) {
        if (Math.abs(d[i] - rgb[0]) <= tol && Math.abs(d[i+1] - rgb[1]) <= tol && Math.abs(d[i+2] - rgb[2]) <= tol) c++;
      }
      return c;
    }""", [list(rgb), sel, tol])

def strip_colours(pg):
    """Pixels in the bottom 16px strip of #bcC (the 1D time-label row):
    counts of candle-red, support-green and neutral axis-grey text."""
    return pg.evaluate("""() => {
      const cv = document.querySelector('#bcC');
      if (!cv) return null;
      const ctx = cv.getContext('2d');
      const w = cv.width, h = cv.height, dpr = cv.width / cv.clientWidth;
      const stripH = Math.round(16 * dpr);
      const d = ctx.getImageData(0, h - stripH, w, stripH).data;
      const near = (r, g, b, t) => (i) => Math.abs(d[i]-r)<=t && Math.abs(d[i+1]-g)<=t && Math.abs(d[i+2]-b)<=t;
      const isRed = near(239, 68, 68, 15), isGreen = near(34, 197, 94, 15), isGrey = near(154, 166, 188, 15);
      let red = 0, green = 0, grey = 0;
      for (let i = 0; i < d.length; i += 4) { if (isRed(i)) red++; else if (isGreen(i)) green++; else if (isGrey(i)) grey++; }
      return {red: red, green: green, grey: grey};
    }""")

def measure(pg, name):
    pg.wait_for_timeout(2500)
    m = pg.evaluate(MEASURE_JS)
    print('  [%s] layout=%s candle=%s pill=%s rsi=%s/%s' % (
        name, (m.get('layout') or {}), (m.get('candle') or {}),
        m.get('typePill'), m.get('rsiSwitchDisabled'), m.get('rsiHeader')), flush=True)
    return m

def bb_range(warm, closes, per=20, mult=2):
    """Bollinger lo/hi over the visible window, recomputed independently
    (population std, like taBB). Returns (minLo, maxUp) or (None, None)."""
    full = (warm or []) + (closes or [])
    w = len(warm or [])
    los, ups = [], []
    for j in range(len(closes or [])):
        i = w + j
        if i < per - 1:
            continue
        win = full[i - per + 1:i + 1]
        mu = sum(win) / per
        va = math.sqrt(sum((v - mu) ** 2 for v in win) / per)
        los.append(mu - mult * va)
        ups.append(mu + mult * va)
    if not los:
        return None, None
    return min(los), max(ups)

def pick_line(pg):
    if pg.is_disabled('#taTyp'):
        return False
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-pick="line"]'); pg.wait_for_timeout(1200)
    return True

def pick_candles(pg):
    if pg.is_disabled('#taTyp'):
        return False
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-pick="candles"]'); pg.wait_for_timeout(1200)
    return True

def pick_size(pg, size):
    if pg.is_disabled('#taTyp'):
        return False
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    els = pg.query_selector_all('.ta-menu [data-ta-size="%s"]' % size)
    if not els:
        try: pg.keyboard.press('Escape')
        except Exception: pass
        pg.wait_for_timeout(300); return False
    pg.click('.ta-menu [data-ta-size="%s"]' % size); pg.wait_for_timeout(1500)
    return True

def go_range(pg, r):
    pg.click('#bcRgs button[data-r="%s"]' % r); pg.wait_for_timeout(1500)

def ensure_panel(pg):
    vis = pg.evaluate("""() => { const p = document.querySelector('.ta-panel'); return p ? !p.hidden : false; }""")
    if not vis:
        pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
        pg.wait_for_timeout(400)

def main():
    global U
    # ---- item 1 (static): recap copy keeps 'provisional' + the Tiingo note ----
    recap = R / 'recap' / '2026-11' / 'index.html'
    txt = recap.read_text()
    chk('recap: Low-close cell keeps (provisional)', '$58,814.99 · Nov 20 (provisional)' in txt)
    chk('recap: note keeps the Tiingo sentence', "Tiingo-confirmed (Yahoo's final bar pending): Nov 20." in txt)

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
        pg.add_init_script("try{localStorage.setItem('ps-ta-v1', JSON.stringify({tl:true,bb:true,ma:true,maSet:{sma20:true,sma50:true,sma200:true,ema20:true,ema50:true,ema200:true},rsi:true,rsiCol:false,last1DSize:'1h'}));}catch(e){}")
        pg.goto(U + 'clock/', wait_until='domcontentloaded')
        pg.wait_for_selector('#bcC', timeout=10000)
        pg.wait_for_timeout(3000)

        # ---- 1D Line: RSI renders, tags spread (Job 12 only) ----
        print('--- 1D Line ---')
        go_range(pg, '1D'); pick_line(pg); ensure_panel(pg)
        m = measure(pg, '1D Line')
        chk('1D Line: RSI switch enabled', m['rsiSwitchDisabled'] is False, str(m['rsiSwitchDisabled']))
        chk('1D Line: RSI strip visible with a live value',
            m['rsiHidden'] is False and m['rsiHeader'] not in (None, '', '—'), str(m['rsiHeader']))
        pl = m.get('labelPlacements')
        if pl is None:
            skip('1D Line: price tags never overlap', 'no labelPlacements hook on this tree')
        else:
            ys = sorted(x['y'] for x in pl)
            gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
            chk('1D Line: price tags never overlap (min gap >= 16px)',
                len(ys) >= 4 and (not gaps or min(gaps) >= 16), 'ys=%s gaps=%s' % (ys, gaps))

        # ---- 1D 4H: time labels neutral (hook trees), tags spread ----
        print('--- 1D 4H candles ---')
        pick_size(pg, '4h'); ensure_panel(pg)
        m = measure(pg, '1D 4H')
        has_hook = m.get('candle') is not None
        if not has_hook:
            skip('1D 4H: time labels are neutral grey', 'no candle-layout hook on this tree')
            skip('1D 4H: price tags never overlap', 'no labelPlacements hook on this tree')
        else:
            sc = strip_colours(pg)
            chk('1D 4H: time labels are neutral grey, not candle red/green',
                sc and sc['red'] == 0 and sc['green'] == 0 and sc['grey'] > 0, str(sc))
            pl = m.get('labelPlacements')
            if pl is None:
                skip('1D 4H: price tags never overlap', 'no labelPlacements hook on this tree')
            else:
                ys = sorted(x['y'] for x in pl)
                gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
                chk('1D 4H: price tags never overlap (min gap >= 16px)',
                    len(ys) >= 3 and (not gaps or min(gaps) >= 16), 'ys=%s gaps=%s' % (ys, gaps))

        # ---- 1W Line: BB inside the axis, SMA 200 teal ----
        print('--- 1W Line ---')
        go_range(pg, '1W'); pick_line(pg); ensure_panel(pg)
        m = measure(pg, '1W Line')
        chk('1W Line: RSI switch enabled', m['rsiSwitchDisabled'] is False, str(m['rsiSwitchDisabled']))
        chk('1W Line: RSI strip visible with a live value',
            m['rsiHidden'] is False and m['rsiHeader'] not in (None, '', '—'), str(m['rsiHeader']))
        ticks = (m.get('layout') or {}).get('yTicks') or []
        dbg = m.get('debug') or {}
        lo, hi = bb_range(dbg.get('warmCloses'), dbg.get('closes'))
        chk('1W Line: Bollinger band inside the axis (floor <= BB-lo, top >= BB-up)',
            lo is not None and ticks and ticks[0] <= lo and ticks[-1] >= hi,
            'ticks=%s BBlo=%.0f BBup=%.0f' % (ticks[:2], lo or -1, hi or -1))
        teal = colour_count(pg, (20, 184, 166))
        old_green = colour_count(pg, (52, 211, 153))
        chk('1W Line: SMA 200 draws in teal', teal >= 50, 'px=%d' % teal)
        chk('1W Line: SMA 200 no longer draws in the old green (below the 50px real-line threshold)',
            old_green < 50, 'px=%d' % old_green)

        # ---- 6M Candles -> 5Y -> 6M: no silent reset ----
        print('--- 6M Candles -> 5Y -> 6M ---')
        go_range(pg, '6M'); pick_candles(pg); ensure_panel(pg)
        m = measure(pg, '6M candles')
        st6 = m.get('state') or {}
        chk('6M: candles view reached', st6.get('candViewActive') is True and st6.get('RGCT') == 'candles', str(st6))
        go_range(pg, '5Y'); pg.wait_for_timeout(1500); ensure_panel(pg)
        m = measure(pg, '5Y after 6M candles')
        st5 = m.get('state') or {}
        pill5 = m.get('typePill') or {}
        kept = st5.get('candViewActive') is True and st5.get('RGCT') == 'candles'
        explained = (pill5.get('disabled') is True and 'Line only' in (pill5.get('title') or '')
                     and st5.get('RGCT') == 'candles' and 'Line only' in (m.get('note') or ''))
        chk('5Y after 6M candles: candles kept, or Line-only explained with preference kept',
            kept or explained, 'kept=%s explained=%s pill=%s state=%s' % (kept, explained, pill5, st5))
        go_range(pg, '6M'); pg.wait_for_timeout(1500); ensure_panel(pg)
        m = measure(pg, '6M after 5Y')
        st6b = m.get('state') or {}
        chk('6M after 5Y: candles restored', st6b.get('candViewActive') is True and st6b.get('RGCT') == 'candles', str(st6b))

        # ---- 5Y / 10Y / Max Line: year labels + floors ----
        for rng, first in [('5Y', 2021), ('10Y', 2016), ('Max', 2010)]:
            print('--- %s Line ---' % rng)
            go_range(pg, rng); pick_line(pg); ensure_panel(pg)
            m = measure(pg, '%s Line' % rng)
            labs = (m.get('layout') or {}).get('xLabels') or []
            exp = [str(y) for y in range(first, 2027)]
            chk('%s Line: year labels are every year, none skipped or repeated' % rng,
                labs == exp, 'labels=%s' % (labs,))
            ticks = (m.get('layout') or {}).get('yTicks') or []
            chk('%s Line: floor is not negative' % rng, ticks and ticks[0] >= 0, 'ticks=%s' % (ticks[:3],))

        # ---- 10Y daily candles + 1W 4H: item 8 (hook trees only) ----
        print('--- 10Y daily candles ---')
        go_range(pg, '10Y'); pick_size(pg, 'daily'); ensure_panel(pg)
        m = measure(pg, '10Y daily')
        c = m.get('candle')
        if c is None:
            skip('10Y daily: candle floor >= 0', 'no candle-layout hook on this tree')
            skip('10Y daily: labels carry the year', 'no candle-layout hook on this tree')
        else:
            chk('10Y daily: candle floor >= 0', c['lo'] >= 0 and (c['yLabels'] or [0])[0] >= 0,
                'lo=%s yLabels=%s' % (c['lo'], c['yLabels']))
            xl = c.get('xLabels') or []
            chk('10Y daily: labels carry the year, none repeated',
                xl and all(("'" in x) or (len(x) == 4 and x.isdigit()) for x in xl) and len(xl) == len(set(xl)),
                'xLabels=%s' % (xl,))
        print('--- 1W 4H candles ---')
        go_range(pg, '1W'); pick_size(pg, '4h'); ensure_panel(pg)
        m = measure(pg, '1W 4H')
        c = m.get('candle')
        if c is None:
            skip('1W 4H: no date repeats', 'no candle-layout hook on this tree')
        else:
            xl = c.get('xLabels') or []
            chk('1W 4H: no date repeats', xl and len(xl) == len(set(xl)), 'xLabels=%s' % (xl,))
        b.close()
    print('MUSTFIX27 %d checks, %d FAIL, %d skipped' % (n, len(fails), skipped))
    for f in fails:
        print('  FAIL:', f)
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
