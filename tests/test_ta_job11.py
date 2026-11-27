#!/usr/bin/env python3
"""TA Drawing Fixes Job 11 checks (22 Nov 2026): range switch + chart-type
availability — Max only + the 1W Candles -> 1D switch (scan #2, Sun ~00:13).

1. 1W Candles -> 1D silently dropped to Line on the live site (scan #2).
   That was live main (pre-Job-5); Job 5's range-click type carry already
   covers this direction in the branch — verified here as a regression
   test, both the 4H and the Daily-size variants, via the TA menu (the
   user-facing control; the bcCg buttons are hidden and driven by it).
2. Candles reachable on Max. Job 9 did the 5Y/10Y half; Max was still
   Line-only (pill disabled, no menu). Max now offers Daily/Weekly/
   Monthly/Yearly (default Daily, finest-first), from the same batched
   extended fetch back to the first daily close (2010-08-18). Gating is
   gran-based, so no new rules: the monthly 200s gate and the yearly
   all-MA + Bollinger gate apply on Max exactly as on 10Y. Trendlines
   stay off on Max by design (Job 7 diagnosis, untouched).

Serves this checkout on localhost, stubs the price/candle feeds (the
Coinbase stub serves the repo's own real daily closes for granularity
86400 — the panel's warm-up comes from that same file, so warm + visible
are one series, as on the real site), frozen clock 2026-10-30 20:00 UTC,
all TA overlays on. Expected candle counts and yearly closes are computed
from the repo's own btc-daily.json at runtime, not hardcoded.
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
    print('ok' if ok else 'FAIL', name, '' if ok else str(detail)[:300], flush=True)
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
        # Daily candles: the repo's own real daily closes (o = prior close).
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
  const t = window.__TA_TL_DEBUG ? window.__TA_TL_DEBUG() : null;
  if (!d) return {error: 'no probe'};
  const rsiEl = document.querySelector('.ta-rsi');
  const hb = rsiEl ? rsiEl.querySelector('.ta-rsi-t b') : null;
  const pill = document.getElementById('taPill');
  const nn = pill ? pill.querySelector('.ta-n') : null;
  return {kind: d.kind, n: d.n, warm: d.warm,
          closes: d.closes, warmCloses: d.warmCloses,
          fvBB: d.firstValid.bb, fvRSI: d.firstValid.rsi, fv: d.firstValidMas,
          last: d.last,
          tl: t ? {status: t.status, tf: t.tf, lines: (t.last && t.last.lines ? t.last.lines.length : null)} : null,
          rsiStrip: rsiEl ? {hidden: rsiEl.hidden, header: hb ? hb.textContent : null} : null,
          badge: nn ? nn.textContent : null};
}"""

STATE_JS = """() => {
  const st = window.__BCTA ? window.__BCTA.state() : null;
  return st ? {rng: st.rng, CT: st.CT, RGCT: st.RGCT, RGGRAN: st.RGGRAN, candViewActive: st.candViewActive} : null;
}"""

COLOURS = {'bb': (167, 139, 250), 'sma20': (244, 114, 182), 'sma50': (251, 191, 36),
           'sma200': (20, 184, 166), 'ema20': (56, 189, 248), 'ema50': (251, 146, 60),
           'ema200': (163, 230, 53), 'tl': (34, 197, 94)}

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

def measure(pg, name):
    pg.wait_for_timeout(2500)
    m = pg.evaluate(MEASURE_JS)
    if 'error' in m:
        print('  [%s] PROBE ERROR %s' % (name, m), flush=True)
        return m
    m['px'] = {k: colour_count(pg, v) for k, v in COLOURS.items()}
    print('  [%s] kind=%s n=%s warm=%s fvBB=%s fvRSI=%s fvSMA200=%s px=%s tl=%s badge=%s' % (
        name, m['kind'], m['n'], m['warm'], m['fvBB'], m['fvRSI'],
        (m['fv'] or {}).get('sma200'), m['px'], m['tl'], m['badge']), flush=True)
    return m

def state(pg):
    return pg.evaluate(STATE_JS)

def pick_line(pg):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-pick="line"]'); pg.wait_for_timeout(1200)

def pick_candles(pg):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-pick="candles"]'); pg.wait_for_timeout(1200)

def pick_size(pg, size):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-size="%s"]' % size); pg.wait_for_timeout(1200)

def go_range(pg, r):
    pg.click('#bcRgs button[data-r="%s"]' % r); pg.wait_for_timeout(1200)

def wait_not_loading(pg, timeout=30000):
    # After a range click the panel shows 'Loading … candles' while the
    # extended fetch runs (Max fires ~24 windows); wait until that text is gone.
    pg.wait_for_function("() => { const el = document.getElementById('bcRr'); return el && !el.textContent.includes('Loading'); }", timeout=timeout)

def menu_sizes(pg):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    sizes = pg.evaluate("""() => [...document.querySelectorAll('.ta-menu [data-ta-size]')].map(b => b.dataset.taSize)""")
    pg.click('#taTyp'); pg.wait_for_timeout(400)
    return sizes

def pill_label(pg):
    return pg.evaluate("""() => { const s = document.querySelector('#taTyp span'); return s ? s.textContent : null; }""")

def pill_disabled(pg):
    return pg.is_disabled('#taTyp')

def disabled(pg, sel):
    return pg.is_disabled(sel)

def ensure_panel(pg):
    vis = pg.evaluate("""() => {
      const p = document.querySelector('.ta-panel');
      return p ? !p.hidden : false;
    }""")
    if not vis:
        pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
        pg.wait_for_timeout(400)

# --- expected values, computed from the repo's own btc-daily.json ---
def max_rows():
    # Every daily close the extended fetch can serve: from the first close
    # (2010-08-18) up to the frozen clock (2026-10-30 20:00 UTC).
    return [(t, c) for t, c in load_data_daily() if t < FIXED.timestamp()]

def n_max_daily():
    return len(max_rows())

def n_max_weeks():
    s = set()
    for t, c in max_rows():
        d = dt.datetime.fromtimestamp(t, dt.timezone.utc)
        s.add((d - dt.timedelta(days=d.weekday())).date())
    return len(s)

def n_max_months():
    return len({(dt.datetime.fromtimestamp(t, dt.timezone.utc).year,
                 dt.datetime.fromtimestamp(t, dt.timezone.utc).month) for t, c in max_rows()})

def max_year_closes():
    # Last daily close of each year 2010-2025, plus the live price for the
    # in-progress 2026 yearly candle (live-extended to the stub's 77500).
    yc = {}
    for t, c in load_data_daily():
        yc[dt.datetime.fromtimestamp(t, dt.timezone.utc).year] = c
    return [yc[y] for y in range(2010, 2026)] + [77500]

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
        pg = b.new_page(viewport={'width': 1440, 'height': 900})
        pg.clock.set_fixed_time(FIXED)
        pg.route('**/*', handler)
        pg.add_init_script("try{localStorage.setItem('ps-ta-v1', JSON.stringify({tl:true,bb:true,ma:true,maSet:{sma20:true,sma50:true,sma200:true,ema20:true,ema50:true,ema200:true},rsi:true,rsiCol:false,last1DSize:'1h'}));}catch(e){}")
        pg.goto(U + 'clock/', wait_until='domcontentloaded')
        pg.wait_for_selector('#bcC', timeout=10000)
        pg.wait_for_timeout(3000)

        # ---- 1W Candles -> 1D (scan #2): the type must survive ----
        print('--- 1W Candles -> 1D (scan #2 case) ---')
        st = state(pg)
        chk('scan case setup: chart opens on 1D Line', st['rng'] == '1D' and st['CT'] == 'line' and pill_label(pg) == 'Line', str(st))
        go_range(pg, '1W')
        chk('1W: Line view until Candles is picked', pill_label(pg) == 'Line', repr(pill_label(pg)))
        pick_candles(pg)
        chk('1W Candles: pill reads 4H candles (1W default)', pill_label(pg) == '4H candles', repr(pill_label(pg)))
        go_range(pg, '1D')
        st = state(pg)
        chk('1W Candles (4H) -> 1D lands on 4H candles, not Line',
            st['CT'] == '4h' and st['candViewActive'] and pill_label(pg) == '4H candles',
            'state=%s pill=%s' % (st, pill_label(pg)))
        # Daily-size variant: 1W Daily has no 1D equivalent, so it falls
        # back to the last 1D size (1H) — still candles, never Line.
        # Reset to Line on 1D first: the carry only sets CT when it is
        # still 'line' (a kept 1D size survives the round trip instead).
        pick_line(pg)
        chk('1D Line: pill reads Line after picking Line', pill_label(pg) == 'Line', repr(pill_label(pg)))
        go_range(pg, '1W')
        pick_candles(pg)
        pick_size(pg, 'daily')
        chk('1W Candles Daily: pill reads Candles · Daily', pill_label(pg) == 'Candles · Daily', repr(pill_label(pg)))
        go_range(pg, '1D')
        st = state(pg)
        chk('1W Candles (Daily) -> 1D lands on 1H candles, not Line',
            st['CT'] == '1h' and st['candViewActive'] and pill_label(pg) == '1H candles',
            'state=%s pill=%s' % (st, pill_label(pg)))
        # Line carries too: 1D Line -> Max -> 1D stays Line.
        pick_line(pg)
        chk('1D Line: pill reads Line before the Max round trip', pill_label(pg) == 'Line', repr(pill_label(pg)))
        go_range(pg, 'Max'); wait_not_loading(pg)
        chk('Max Line: pill reads Line (opens on Line)', pill_label(pg) == 'Line', repr(pill_label(pg)))
        go_range(pg, '1D')
        st = state(pg)
        chk('1D Line -> Max -> 1D stays Line',
            st['CT'] == 'line' and not st['candViewActive'] and pill_label(pg) == 'Line',
            'state=%s pill=%s' % (st, pill_label(pg)))

        # ---- Max: candles reachable ----
        print('--- Max candles ---')
        go_range(pg, 'Max'); wait_not_loading(pg)
        chk('Max: pill is enabled (no longer Line-only)', not pill_disabled(pg))
        chk('Max: menu offers Yearly, Monthly, Weekly, Daily',
            menu_sizes(pg) == ['yearly', 'monthly', 'weekly', 'daily'], str(menu_sizes(pg)))
        pick_candles(pg); wait_not_loading(pg)
        chk('Max: first Candles pick defaults to Daily (finest-first)', pill_label(pg) == 'Candles · Daily', repr(pill_label(pg)))
        m = measure(pg, 'Max daily')
        chk('Max daily: candle view with %d daily candles' % n_max_daily(), m['kind'] == 'candles-range' and m['n'] == n_max_daily(), 'kind=%s n=%s' % (m['kind'], m['n']))
        chk('Max daily: no warm-up (the window IS the whole history)', m['warm'] == 0, 'warm=%s' % m['warm'])
        chk('Max daily: Bollinger valid from index 19, SMA 200 from 199 (no warm-up)', m['fvBB'] == 19 and (m['fv'] or {}).get('sma200') == 199,
            'fvBB=%s fvSMA200=%s' % (m['fvBB'], (m['fv'] or {}).get('sma200')))
        chk('Max daily: Bollinger + SMA 200 draw', m['px']['bb'] > 0 and m['px']['sma200'] >= 50, 'px=%s' % (m['px'],))
        chk('Max daily: badge counts 8 drawings (BB+6 MA+RSI, no trendlines on Max)', m['badge'] == '8', 'badge=%s' % m['badge'])
        chk('Max daily: subtitle counts %d daily candles' % n_max_daily(),
            ('%d daily candles' % n_max_daily()) in pg.inner_text('#bcRr'), repr(pg.inner_text('#bcRr'))[:200])
        chk('Max daily: subtitle starts at the first close (Aug 18, $0.07)',
            'Aug 18' in pg.inner_text('#bcRr') and '($0.07)' in pg.inner_text('#bcRr'),
            repr(pg.inner_text('#bcRr'))[:200])
        pick_size(pg, 'weekly')
        chk('Max: Weekly pick shows the Weekly pill', pill_label(pg) == 'Candles · Weekly', repr(pill_label(pg)))
        m = measure(pg, 'Max weekly')
        chk('Max weekly: candle view with %d weekly candles' % n_max_weeks(), m['kind'] == 'candles-range' and m['n'] == n_max_weeks(), 'kind=%s n=%s' % (m['kind'], m['n']))
        pick_size(pg, 'monthly')
        chk('Max: Monthly pick shows the Monthly pill', pill_label(pg) == 'Candles · Monthly', repr(pill_label(pg)))
        m = measure(pg, 'Max monthly')
        chk('Max monthly: candle view with %d monthly candles' % n_max_months(), m['kind'] == 'candles-range' and m['n'] == n_max_months(), 'kind=%s n=%s' % (m['kind'], m['n']))
        ensure_panel(pg)
        chk('Max monthly: SMA 200 / EMA 200 chips disabled (Job 8 gate covers Max)',
            disabled(pg, '.ta-panel [data-ta-ma="sma200"]') and disabled(pg, '.ta-panel [data-ta-ma="ema200"]'))
        chk('Max monthly: SMA 20 / EMA 20 chips enabled (only the 200s gate on monthly)',
            not disabled(pg, '.ta-panel [data-ta-ma="sma20"]') and not disabled(pg, '.ta-panel [data-ta-ma="ema20"]'))
        pick_size(pg, 'yearly')
        chk('Max: Yearly pick shows the Yearly pill', pill_label(pg) == 'Candles · Yearly', repr(pill_label(pg)))
        m = measure(pg, 'Max yearly')
        chk('Max yearly: candle view with 17 yearly candles', m['kind'] == 'candles-range' and m['n'] == 17, 'kind=%s n=%s' % (m['kind'], m['n']))
        exp = max_year_closes()
        got = m.get('closes') or []
        chk('Max yearly: each yearly close is its year-end daily close (2026 is the live price)',
            len(got) == 17 and all(abs(g - e) < 0.01 for g, e in zip(got, exp)),
            'got=%s exp=%s' % (got, exp))
        chk('Max yearly: no warm-up (no closes before 2010)', m['warm'] == 0, 'warm=%s' % m['warm'])
        chk('Max yearly: RSI valid from visible index 14 (first value needs 14 closes, no warm-up)',
            m['fvRSI'] == 14, 'fvRSI=%s' % m['fvRSI'])
        chk('Max yearly: RSI strip visible with a live value', (m['rsiStrip'] or {}).get('hidden') is False and (m['rsiStrip'] or {}).get('header') not in (None, '', '—'), str(m['rsiStrip']))
        chk('Max yearly: Bollinger + all MAs draw nothing (gated — can never compute)',
            m['px']['bb'] == 0 and m['px']['sma20'] == 0 and m['px']['sma200'] == 0 and m['px']['ema20'] == 0,
            'px=%s' % (m['px'],))
        chk('Max yearly: badge counts 1 drawing (RSI only)', m['badge'] == '1', 'badge=%s' % m['badge'])
        chk('Max yearly: subtitle counts 17 yearly candles',
            '17 yearly candles' in pg.inner_text('#bcRr'), repr(pg.inner_text('#bcRr'))[:200])
        ensure_panel(pg)
        chk('Max yearly: Bollinger chip disabled (Job 9 gate covers Max)',
            disabled(pg, '.ta-panel [data-ta-key="bb"]'))
        chk('Max yearly: all six MA chips disabled (Job 9 gate covers Max)',
            all(disabled(pg, '.ta-panel [data-ta-ma="%s"]' % k) for k in
                ['sma20', 'sma50', 'sma200', 'ema20', 'ema50', 'ema200']))
        chk('Max yearly: RSI chip enabled (RSI computes there)',
            not disabled(pg, '.ta-panel [data-ta-key="rsi"]'))

        # ---- type carry through Max ----
        print('--- type carry through Max ---')
        pick_size(pg, 'daily')
        chk('Max Candles Daily: pill reads Candles · Daily', pill_label(pg) == 'Candles · Daily', repr(pill_label(pg)))
        go_range(pg, '1D')
        st = state(pg)
        chk('Max Candles -> 1D lands on candles, not Line',
            st['CT'] != 'line' and st['candViewActive'], 'state=%s pill=%s' % (st, pill_label(pg)))
        pick_candles(pg)
        go_range(pg, 'Max'); wait_not_loading(pg)
        st = state(pg)
        chk('1D Candles -> Max stays on Candles (Daily default)',
            st['RGCT'] == 'candles' and pill_label(pg) == 'Candles · Daily',
            'state=%s pill=%s' % (st, pill_label(pg)))
        b.close()
    print('JOB11 %d checks, %d FAIL' % (n, len(fails)))
    for f in fails:
        print('  FAIL:', f)
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
