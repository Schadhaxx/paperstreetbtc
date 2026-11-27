#!/usr/bin/env python3
"""TA Drawing Fixes Job 9 checks (22 Nov 2026): candle additions.

3M/6M/YTD gain DAILY (default becomes daily, finest-first); 5Y gains
WEEKLY + MONTHLY (default stays daily); 10Y gains MONTHLY + YEARLY
(default stays daily). Yearly is NEW — calendar-year aggregation in
aggDailyCandles, a Yearly button, a 'Candles · Yearly' pill label, and
the live-extend / countdown / note text follow the calendar year.
5Y/10Y are no longer Line-only: the chart-type pill + menu work there
(Max stays Line-only here — Job 11, 22 Nov 2026, gave Max candles too).
1Y is unchanged (monthly/weekly, default weekly).

Serves this checkout on localhost, stubs the price/candle feeds (the
Coinbase stub serves the repo's own real daily closes for granularity
86400 — the panel's warm-up comes from that same file, so warm + visible
are one series, as on the real site), frozen clock 2026-10-30 20:00 UTC,
all TA overlays on. Expected candle counts and yearly closes are computed
from the repo's own btc-daily.json at runtime, not hardcoded.

Yearly gating (Job 9 decision): Bollinger + all six MAs are greyed on
10Y yearly — only 17 yearly closes exist (2010–2026) and the shortest
(SMA/EMA 20) needs 20, so none can ever compute there. RSI is NOT gated:
6 warm yearly closes + 11 visible = 17, so its 14 closes are covered
and it draws from visible index 7. The Job 8 monthly 200s gate keys on
granularity, so it already covers the new 5Y/10Y monthly views.
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

COLOURS = {'bb': (167, 139, 250), 'sma20': (244, 114, 182), 'sma50': (251, 191, 36),
           'sma200': (232, 238, 247), 'ema20': (56, 189, 248), 'ema50': (251, 146, 60),
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

def wait_not_loading(pg, timeout=20000):
    # After a range click the panel shows 'Loading … candles' while the
    # extended fetch runs (5Y/10Y); wait until that text is gone.
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
def win_rows(days):
    cut = FIXED.timestamp() - days * 86400
    return [(t, c) for t, c in load_data_daily() if cut <= t < FIXED.timestamp()]

def n_daily(days):
    return len(win_rows(days))

def n_months(days):
    return len({(dt.datetime.fromtimestamp(t, dt.timezone.utc).year,
                 dt.datetime.fromtimestamp(t, dt.timezone.utc).month) for t, c in win_rows(days)})

def n_weeks(days):
    s = set()
    for t, c in win_rows(days):
        d = dt.datetime.fromtimestamp(t, dt.timezone.utc)
        s.add((d - dt.timedelta(days=d.weekday())).date())
    return len(s)

def n_ytd():
    jan1 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc).timestamp()
    return len([(t, c) for t, c in load_data_daily() if jan1 <= t < FIXED.timestamp()])

def year_closes():
    # Last daily close of each year 2016-2025, plus the live price for the
    # in-progress 2026 yearly candle (live-extended to the stub's 77500).
    yc = {}
    for t, c in load_data_daily():
        yc[dt.datetime.fromtimestamp(t, dt.timezone.utc).year] = c
    return [yc[y] for y in range(2016, 2026)] + [77500]

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

        # ---- 3M: Daily is new, and the new default ----
        print('--- 3M ---')
        go_range(pg, '3M')
        chk('3M: menu offers Monthly, Weekly, Daily (Daily is new)', menu_sizes(pg) == ['monthly', 'weekly', 'daily'])
        pick_candles(pg)
        chk('3M: first Candles pick defaults to Daily (finest-first)', pill_label(pg) == 'Candles · Daily', repr(pill_label(pg)))
        m = measure(pg, '3M daily')
        chk('3M daily: candle view with %d daily candles' % n_daily(92), m['kind'] == 'candles-range' and m['n'] == n_daily(92), 'kind=%s n=%s' % (m['kind'], m['n']))
        chk('3M daily: Bollinger + SMA 200 valid from index 0', m['fvBB'] == 0 and (m['fv'] or {}).get('sma200') == 0,
            'fvBB=%s fvSMA200=%s' % (m['fvBB'], (m['fv'] or {}).get('sma200')))
        chk('3M daily: Bollinger + SMA 200 draw', m['px']['bb'] > 0 and m['px']['sma200'] >= 50, 'px=%s' % (m['px'],))
        chk('3M daily: badge counts all 9 drawings (TL+BB+6 MA+RSI)', m['badge'] == '9', 'badge=%s' % m['badge'])

        # ---- 6M: Daily is the new default on a range switch ----
        print('--- 6M ---')
        go_range(pg, '6M')
        chk('6M: range switch keeps Candles and resets to the Daily default', pill_label(pg) == 'Candles · Daily', repr(pill_label(pg)))
        chk('6M: menu offers Monthly, Weekly, Daily', menu_sizes(pg) == ['monthly', 'weekly', 'daily'])
        m = measure(pg, '6M daily')
        chk('6M daily: candle view with %d daily candles' % n_daily(183), m['kind'] == 'candles-range' and m['n'] == n_daily(183), 'kind=%s n=%s' % (m['kind'], m['n']))
        chk('6M daily: Bollinger + SMA 200 valid from index 0', m['fvBB'] == 0 and (m['fv'] or {}).get('sma200') == 0)

        # ---- YTD: Daily is the new default (extended fetch) ----
        print('--- YTD ---')
        go_range(pg, 'YTD'); wait_not_loading(pg)
        chk('YTD: range switch keeps Candles and resets to the Daily default', pill_label(pg) == 'Candles · Daily', repr(pill_label(pg)))
        chk('YTD: menu offers Monthly, Weekly, Daily', menu_sizes(pg) == ['monthly', 'weekly', 'daily'])
        m = measure(pg, 'YTD daily')
        chk('YTD daily: candle view with %d daily candles' % n_ytd(), m['kind'] == 'candles-range' and m['n'] == n_ytd(), 'kind=%s n=%s' % (m['kind'], m['n']))

        # ---- 1Y: unchanged (no Daily, default stays Weekly) ----
        print('--- 1Y (unchanged) ---')
        go_range(pg, '1Y'); wait_not_loading(pg)
        chk('1Y: menu still offers Monthly, Weekly only (no Daily)', menu_sizes(pg) == ['monthly', 'weekly'])
        chk('1Y: range switch keeps Candles and defaults to Weekly (unchanged)', pill_label(pg) == 'Candles · Weekly', repr(pill_label(pg)))
        m = measure(pg, '1Y weekly')
        chk('1Y weekly: candle view with %d weekly candles' % n_weeks(366), m['kind'] == 'candles-range' and m['n'] == n_weeks(366), 'kind=%s n=%s' % (m['kind'], m['n']))

        # ---- 5Y: candles arrive (Daily default, Weekly + Monthly new) ----
        print('--- 5Y ---')
        go_range(pg, '5Y'); wait_not_loading(pg)
        chk('5Y: pill is enabled (no longer Line-only)', not pill_disabled(pg))
        chk('5Y: range switch lands on the Daily default', pill_label(pg) == 'Candles · Daily', repr(pill_label(pg)))
        chk('5Y: menu offers Yearly, Monthly, Weekly, Daily', menu_sizes(pg) == ['yearly', 'monthly', 'weekly', 'daily'])
        m = measure(pg, '5Y daily')
        chk('5Y daily: candle view with %d daily candles' % n_daily(1827), m['kind'] == 'candles-range' and m['n'] == n_daily(1827), 'kind=%s n=%s' % (m['kind'], m['n']))
        chk('5Y daily: Bollinger + SMA 200 valid from index 0', m['fvBB'] == 0 and (m['fv'] or {}).get('sma200') == 0)
        chk('5Y daily: badge counts 8 drawings (no trendlines on 5Y)', m['badge'] == '8', 'badge=%s' % m['badge'])
        pick_size(pg, 'weekly')
        chk('5Y: Weekly pick shows the Weekly pill', pill_label(pg) == 'Candles · Weekly', repr(pill_label(pg)))
        m = measure(pg, '5Y weekly')
        chk('5Y weekly: candle view with %d weekly candles' % n_weeks(1827), m['kind'] == 'candles-range' and m['n'] == n_weeks(1827), 'kind=%s n=%s' % (m['kind'], m['n']))
        chk('5Y weekly: Bollinger + SMA 200 valid from index 0', m['fvBB'] == 0 and (m['fv'] or {}).get('sma200') == 0)
        pick_size(pg, 'monthly')
        chk('5Y: Monthly pick shows the Monthly pill', pill_label(pg) == 'Candles · Monthly', repr(pill_label(pg)))
        m = measure(pg, '5Y monthly')
        chk('5Y monthly: candle view with %d monthly candles' % n_months(1827), m['kind'] == 'candles-range' and m['n'] == n_months(1827), 'kind=%s n=%s' % (m['kind'], m['n']))
        chk('5Y monthly: SMA 20 / EMA 20 still draw', m['px']['sma20'] > 0 and m['px']['ema20'] > 0, 'px=%s' % (m['px'],))
        ensure_panel(pg)
        chk('5Y monthly: SMA 200 / EMA 200 chips disabled (Job 8 gate covers the new view)',
            disabled(pg, '.ta-panel [data-ta-ma="sma200"]') and disabled(pg, '.ta-panel [data-ta-ma="ema200"]'))
        chk('5Y monthly: SMA 20 / EMA 20 chips enabled (only the 200s are gated)',
            not disabled(pg, '.ta-panel [data-ta-ma="sma20"]') and not disabled(pg, '.ta-panel [data-ta-ma="ema20"]'))
        pick_size(pg, 'yearly')
        chk('5Y: Yearly pick shows the Yearly pill', pill_label(pg) == 'Candles \u00b7 Yearly', repr(pill_label(pg)))

        # ---- 10Y: candles arrive (Daily default, Monthly + Yearly new) ----
        print('--- 10Y ---')
        go_range(pg, '10Y'); wait_not_loading(pg)
        chk('10Y: pill is enabled (no longer Line-only)', not pill_disabled(pg))
        chk('10Y: range switch lands on the Daily default', pill_label(pg) == 'Candles · Daily', repr(pill_label(pg)))
        chk('10Y: menu offers Yearly, Monthly, Daily (no Weekly)', menu_sizes(pg) == ['yearly', 'monthly', 'daily'])
        m = measure(pg, '10Y daily')
        chk('10Y daily: candle view with %d daily candles' % n_daily(3653), m['kind'] == 'candles-range' and m['n'] == n_daily(3653), 'kind=%s n=%s' % (m['kind'], m['n']))
        chk('10Y daily: Bollinger + SMA 200 valid from index 0', m['fvBB'] == 0 and (m['fv'] or {}).get('sma200') == 0)
        pick_size(pg, 'monthly')
        chk('10Y: Monthly pick shows the Monthly pill', pill_label(pg) == 'Candles · Monthly', repr(pill_label(pg)))
        m = measure(pg, '10Y monthly')
        chk('10Y monthly: candle view with %d monthly candles' % n_months(3653), m['kind'] == 'candles-range' and m['n'] == n_months(3653), 'kind=%s n=%s' % (m['kind'], m['n']))
        ensure_panel(pg)
        chk('10Y monthly: SMA 200 / EMA 200 chips disabled (Job 8 gate covers the new view)',
            disabled(pg, '.ta-panel [data-ta-ma="sma200"]') and disabled(pg, '.ta-panel [data-ta-ma="ema200"]'))
        pick_size(pg, 'yearly')
        chk('10Y: Yearly pick shows the Yearly pill', pill_label(pg) == 'Candles · Yearly', repr(pill_label(pg)))
        m = measure(pg, '10Y yearly')
        chk('10Y yearly: candle view with 11 yearly candles', m['kind'] == 'candles-range' and m['n'] == 11, 'kind=%s n=%s' % (m['kind'], m['n']))
        exp = year_closes()
        got = m.get('closes') or []
        chk('10Y yearly: each yearly close is its year-end daily close (2026 is the live price)',
            len(got) == 11 and all(abs(g - e) < 0.01 for g, e in zip(got, exp)),
            'got=%s exp=%s' % (got, exp))
        chk('10Y yearly: warm-up has the 7 yearly closes before the window (2010–2016)',
            m['warm'] == 7, 'warm=%s' % m['warm'])
        chk('10Y yearly: RSI valid from visible index 7 (14 closes = 7 warm + 11 visible)',
            m['fvRSI'] == 7, 'fvRSI=%s' % m['fvRSI'])
        chk('10Y yearly: RSI strip visible with a live value', (m['rsiStrip'] or {}).get('hidden') is False and (m['rsiStrip'] or {}).get('header') not in (None, '', '—'), str(m['rsiStrip']))
        chk('10Y yearly: Bollinger + all MAs draw nothing (gated — can never compute)',
            m['px']['bb'] == 0 and m['px']['sma20'] == 0 and m['px']['sma200'] == 0 and m['px']['ema20'] == 0,
            'px=%s' % (m['px'],))
        chk('10Y yearly: badge counts 1 drawing (RSI only)', m['badge'] == '1', 'badge=%s' % m['badge'])
        chk('10Y yearly: subtitle counts 11 yearly candles',
            '11 yearly candles' in pg.inner_text('#bcRr'), repr(pg.inner_text('#bcRr'))[:200])
        ensure_panel(pg)
        chk('10Y yearly: Bollinger chip disabled (Job 9 gate)',
            disabled(pg, '.ta-panel [data-ta-key="bb"]'))
        chk('10Y yearly: all six MA chips disabled (Job 9 gate)',
            all(disabled(pg, '.ta-panel [data-ta-ma="%s"]' % k) for k in
                ['sma20', 'sma50', 'sma200', 'ema20', 'ema50', 'ema200']))
        chk('10Y yearly: RSI chip enabled (RSI computes there)',
            not disabled(pg, '.ta-panel [data-ta-key="rsi"]'))

        # ---- Max: no longer Line-only (Job 11, 22 Nov 2026) ----
        # Max now has candles (Daily/Weekly/Monthly/Yearly, default
        # Daily). The pill is enabled — and the Job 5 type carry applies:
        # the previous view here is 10Y yearly candles, so Max lands on
        # Candles at its Daily default, not Line. The candle behaviour
        # itself is covered in depth by tests/test_ta_job11.py.
        print('--- Max (Job 11: candles reachable, type carried from 10Y) ---')
        go_range(pg, 'Max')
        chk('Max: pill enabled and reads Candles · Daily (carried from 10Y yearly candles)',
            not pill_disabled(pg) and pill_label(pg) == 'Candles · Daily',
            'disabled=%s label=%s' % (pill_disabled(pg), pill_label(pg)))
        b.close()
    print('JOB9 %d checks, %d FAIL' % (n, len(fails)))
    for f in fails:
        print('  FAIL:', f)
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
