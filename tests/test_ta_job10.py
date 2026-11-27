#!/usr/bin/env python3
"""TA Drawing Fixes Job 10 checks (22 Nov 2026): the 1D comparison pipeline.

Serves this checkout on localhost, stubs the price/candle feeds and the
data-branch cmp-intraday.json, frozen clock Fri 20 Nov 2026 2 PM ET
(mid-session), all TA overlays on.

The BTC intraday series is linear by construction (close = $60,000 +
$45 per 15-min bucket from the 9:30 AM ET open), and the compare bars
are linear too (SPX $5,980 + $1.50/bucket, Gold $3,525 - $0.50/bucket,
MSTR $210 + $0.80/bucket), so the expected header percentages are exact:
at the frozen clock the last complete bucket is 1:45 PM ET (bucket 17)
— BTC +1.3%, S&P 500 +0.4%, Gold -0.2%, MSTR +6.5%.

Checks: (1) BTC-only 1D Line is unchanged (no compare colours, live
point plotted, dollar axis, TA badge present); (2) toggling the three
compares draws the rebased session lines (exact header, % axis, no live
point, compare colours present, TA badge gone, the Job 6 note visible);
(3) turning toggles off returns to BTC-only; (4) 1D candles force the
toggles off in the UI while preserving the state (back on Line the
compare returns); (5) Saturday shows the last session, labelled;
(6) Monday after the open the stale file falls back to BTC-only with
the "Compare data unavailable" note.
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
FIXED = dt.datetime(2026, 11, 20, 19, tzinfo=dt.timezone.utc)  # Fri 2 PM ET, mid-session
SAT = dt.datetime(2026, 11, 21, 15, tzinfo=dt.timezone.utc)    # Sat 10 AM ET
MON = dt.datetime(2026, 11, 23, 15, tzinfo=dt.timezone.utc)    # Mon 10 AM ET, after the open
fails, n = [], 0

def chk(name, ok, detail=''):
    global n
    n += 1
    print('ok' if ok else 'FAIL', name, '' if ok else str(detail)[:300], flush=True)
    if not ok:
        fails.append(name)

def iso(d):
    return d.strftime('%Y-%m-%dT%H:%M:%SZ')

# --- the session: Fri 20 Nov 2026, 9:30 AM ET = 14:30 UTC ---
T0 = int(dt.datetime(2026, 11, 20, 14, 30, tzinfo=dt.timezone.utc).timestamp())

def btc_close(t):
    return 60000 + 45 * ((t - T0) // 900)

def cmp_fixture():
    bars = {}
    for sym, base, step in (('SPX', 5980, 1.5), ('GOLD', 3525, -0.5), ('MSTR', 210, 0.8)):
        b = []
        for k in range(18):  # 9:30 AM - 1:45 PM ET (the buckets complete by 2 PM ET)
            t = T0 + k * 900
            c = base + step * k
            b.append([t * 1000, c - 1, c + 1, c - 2, c])
        bars[sym] = {'bars': b}
    return {'v': 1, 'kind': 'cmp-intraday', 'asOf': '2026-11-20T18:50:00Z',
            'session': '2026-11-20', 'sessionOpen': '2026-11-20T14:30:00Z',
            'symbols': bars, 'failed': []}

CMP_FIXTURE = cmp_fixture()

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

def tl_fixture():
    h1, h4, d1 = FIXED - dt.timedelta(minutes=10), FIXED - dt.timedelta(hours=1), FIXED - dt.timedelta(hours=5)
    t1h = tf(h1, [lvl(79500, 'resistance'), lvl(76000, 'support')], [slp('support', 30, FIXED - dt.timedelta(hours=12), 75500)])
    t4h = tf(h4, [lvl(79500, 'resistance')], [slp('support', 120, FIXED - dt.timedelta(hours=20), 74000)])
    t1d = tf(d1, [lvl(81000, 'resistance'), lvl(75000, 'support')], [slp('support', -30, dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc), 76000)])
    return {'v': 1, 'kind': 'ta-lines', 'asOf': iso(FIXED), 'timeframes': {'1h': t1h, '4h': t4h, '1d': t1d}}

TL_FIXTURE = tl_fixture()

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
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'data': {'amount': '60765.00', 'currency': 'USD'}}))
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
    if g == 900:
        # 15-min candles, linear by construction: only complete buckets
        # (t < end, like the real API) so the last point is the last
        # complete bucket, never a half-open one.
        rows, t = [], end - 900
        s = start - start % 900
        while t >= s and len(rows) < 300:
            c = btc_close(t); o = btc_close(t - 900)
            rows.append([t, min(o, c) - 10, max(o, c) + 10, o, c, 10]); t -= 900
        rows.sort(key=lambda r: r[0])
        return route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))
    rows, t = [], end - end % g
    while t >= start and len(rows) < 300:
        o = base_price(t * 1000); c = base_price((t + g) * 1000)
        rows.append([t, min(o, c) - 120, max(o, c) + 120, o, c, 10]); t -= g
    route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))

def handler(route):
    url = route.request.url
    if 'cmp-intraday.json' in url:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps(CMP_FIXTURE))
    if 'ta-lines.json' in url:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps(TL_FIXTURE))
    if 'coinbase.com' in url: return coinbase(route)
    if 'paperstreet-quotes' in url:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'btc': {'usd': 60765, 'chg24h': 1.2}}))
    if 'coingecko.com' in url:
        if 'simple/price' in url:
            return route.fulfill(status=200, content_type='application/json', body=json.dumps({'bitcoin': {'usd': 60765, 'usd_24h_change': 1.2}}))
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'prices': [[int(FIXED.timestamp() * 1000) - i * 900000, 60765 + i] for i in range(96, 0, -1)]}))
    if 'raw.githubusercontent.com' in url or 'history.json' in url:
        return route.abort()
    if not url.startswith(U): return route.abort()
    route.continue_()

LAYOUT_JS = """() => {
  const l = window.__BTC_LINE_LAYOUT || null;
  return l ? {hasLive: l.hasLive, livePrice: l.livePrice, yTicks: l.yTicks} : null;
}"""

TA_STATE_JS = """() => {
  const nn = document.querySelector('#taPill .ta-n');
  const note = document.querySelector('.ta-cmp-out');
  return {badge: nn ? nn.textContent : null,
          cmpNoteHidden: note ? note.hidden : null,
          cmpNoteText: note ? note.textContent : null};
}"""

TOGGLE_JS = """() => {
  const g = id => { const el = document.getElementById(id); return el ? {pressed: el.getAttribute('aria-pressed'), off: el.classList.contains('off'), text: document.getElementById(id + 'T').textContent} : null; };
  return {spx: g('bcSpx'), gld: g('bcGld'), mstr: g('bcMstr')};
}"""

STATE_JS = """() => {
  const st = window.__BCTA ? window.__BCTA.state() : null;
  return st ? {rng: st.rng, CT: st.CT, candViewActive: st.candViewActive} : null;
}"""

def state(pg):
    return pg.evaluate(STATE_JS)

COLOURS = {'btc': (34, 211, 238), 'spx': (196, 181, 253), 'gld': (250, 204, 21), 'mstr': (249, 115, 22)}

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

def px(pg, tol=10):
    # Absence checks pass tol=0: the Bollinger band (#a78bfa) anti-aliases into
    # the SPX purple tolerance in light mode, so tol=10 counts a few stray px.
    return {k: colour_count(pg, v, tol=tol) for k, v in COLOURS.items()}

def header(pg):
    return pg.inner_text('#bcRr')

def note(pg):
    return pg.inner_text('#bcNt')

def wait_header(pg, text, timeout=15000):
    pg.wait_for_function("t => { const el = document.getElementById('bcRr'); return el && el.textContent.includes(t); }", arg=text, timeout=timeout)

def wait_not_loading(pg, timeout=30000):
    pg.wait_for_function("() => { const el = document.getElementById('bcRr'); return el && !el.textContent.includes('Loading'); }", timeout=timeout)

def click_toggle(pg, sel):
    pg.click(sel)
    pg.wait_for_timeout(400)

def pick_candles(pg, size='1h'):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-pick="candles"]'); pg.wait_for_timeout(800)
    if size != '1h':
        pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
        pg.click('.ta-menu [data-ta-size="%s"]' % size); pg.wait_for_timeout(800)

def pick_line(pg):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-pick="line"]'); pg.wait_for_timeout(800)

def pill_label(pg):
    return pg.evaluate("""() => { const s = document.querySelector('#taTyp span'); return s ? s.textContent : null; }""")

def new_page(b, clock):
    pg = b.new_page(viewport={'width': 1440, 'height': 900})
    pg.clock.set_fixed_time(clock)
    pg.route('**/*', handler)
    pg.add_init_script("try{localStorage.setItem('ps-ta-v1', JSON.stringify({tl:true,bb:true,ma:true,maSet:{sma20:true,sma50:true,sma200:true,ema20:true,ema50:true,ema200:true},rsi:true,rsiCol:false,last1DSize:'1h'}));}catch(e){}")
    pg.goto(U + 'clock/', wait_until='domcontentloaded')
    pg.wait_for_selector('#bcC', timeout=10000)
    wait_not_loading(pg)
    pg.wait_for_timeout(2500)
    return pg

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

        # ---- Friday 2 PM ET: mid-session compare ----
        print('--- Friday 2 PM ET: mid-session compare ---')
        pg = new_page(b, FIXED)
        st = state(pg)
        chk('chart opens on 1D Line', st['rng'] == '1D' and st['CT'] == 'line' and pill_label(pg) == 'Line', str(st))
        tg = pg.evaluate(TOGGLE_JS)
        chk('toggles start off (+ S&P 500 / + Gold / + MSTR)',
            tg['spx']['pressed'] == 'false' and tg['spx']['text'] == '+ S&P 500' and tg['gld']['text'] == '+ Gold' and tg['mstr']['text'] == '+ MSTR', str(tg))
        chk('BTC-only header is the 24-hour view', 'last 24 hours' in header(pg), repr(header(pg))[:200])
        c = px(pg, tol=0)
        chk('BTC-only: no compare colours on the canvas', c['spx'] == 0 and c['gld'] == 0 and c['mstr'] == 0, 'px=%s' % (c,))
        chk('BTC-only: the BTC line draws', c['btc'] > 50, 'px=%s' % (c,))
        lay = pg.evaluate(LAYOUT_JS)
        chk('BTC-only: live point plotted (hasLive, live price)',
            lay and lay['hasLive'] is True and lay['livePrice'] == 60765, str(lay))
        chk('BTC-only: y-axis is dollar-scale',
            lay and lay['yTicks'] and min(lay['yTicks']) > 1000, str(lay and lay['yTicks']))
        # TA draws on the BTC-only chart (badge present) — the warm-up is async.
        try:
            pg.wait_for_function("() => { const nn = document.querySelector('#taPill .ta-n'); return nn && nn.textContent !== ''; }", timeout=20000)
        except Exception:
            pass
        ta = pg.evaluate(TA_STATE_JS)
        chk('BTC-only: TA badge present (overlays drawing)',
            ta['badge'] is not None and ta['badge'] != '', str(ta))
        chk('BTC-only: no compare note', ta['cmpNoteHidden'] is not False, str(ta))

        click_toggle(pg, '#bcSpx'); click_toggle(pg, '#bcGld'); click_toggle(pg, '#bcMstr')
        wait_header(pg, '9:30 AM-4 PM ET')
        pg.wait_for_timeout(800)
        chk('compare header: exact rebased % values',
            '1D: BTC +1.3% \u00b7 S&P 500 +0.4% \u00b7 Gold -0.2% \u00b7 MSTR +6.5% \u00b7 9:30 AM-4 PM ET' in header(pg),
            repr(header(pg))[:250])
        chk('compare note explains the session + rebase',
            '9:30 AM ET open' in note(pg) and 'rebased to 100' in note(pg), repr(note(pg))[:250])
        lay = pg.evaluate(LAYOUT_JS)
        chk('compare: no live point plotted',
            lay and lay['hasLive'] is False and lay['livePrice'] is None, str(lay))
        chk('compare: y-axis is % change (ticks near 100)',
            lay and lay['yTicks'] and all(90 < t < 110 for t in lay['yTicks']), str(lay and lay['yTicks']))
        c = px(pg)
        chk('compare: all four lines draw (BTC + SPX + Gold + MSTR)',
            c['btc'] > 50 and c['spx'] > 50 and c['gld'] > 50 and c['mstr'] > 50, 'px=%s' % (c,))
        ta = pg.evaluate(TA_STATE_JS)
        chk('compare: TA badge gone while comparing (RSI hides like the other TA lines)',
            ta['badge'] is None, str(ta))
        chk('compare: Job 6 note visible (TA shows on BTC alone)',
            ta['cmpNoteHidden'] is False and ta['cmpNoteText'] and 'TA shows on BTC alone' in ta['cmpNoteText'], str(ta))

        # One toggle off: that series leaves, the compare stays.
        click_toggle(pg, '#bcSpx')
        wait_header(pg, 'Gold -0.2%')
        pg.wait_for_timeout(800)
        chk('SPX off: header drops S&P 500, keeps Gold + MSTR',
            'S&P 500' not in header(pg) and 'Gold -0.2%' in header(pg) and 'MSTR +6.5%' in header(pg),
            repr(header(pg))[:250])
        c = px(pg, tol=0)
        chk('SPX off: SPX colour gone, Gold + MSTR still draw',
            c['spx'] == 0 and c['gld'] > 50 and c['mstr'] > 50, 'px=%s' % (c,))

        # All toggles off: back to BTC-only.
        click_toggle(pg, '#bcGld'); click_toggle(pg, '#bcMstr')
        wait_header(pg, 'last 24 hours')
        pg.wait_for_timeout(800)
        c = px(pg, tol=0)
        chk('all off: back to BTC-only (no compare colours)',
            c['spx'] == 0 and c['gld'] == 0 and c['mstr'] == 0 and c['btc'] > 50, 'px=%s' % (c,))
        chk('all off: note is the intraday note again',
            'Compare data unavailable' not in note(pg) and 'last 24 hours' in note(pg), repr(note(pg))[:200])

        # Candles force the toggles off in the UI; the state survives the round trip.
        click_toggle(pg, '#bcSpx')
        wait_header(pg, '9:30 AM-4 PM ET')
        pick_candles(pg, '1h')
        chk('1H candles: pill reads 1H candles', pill_label(pg) == '1H candles', repr(pill_label(pg)))
        tg = pg.evaluate(TOGGLE_JS)
        chk('1H candles: toggles forced off in the UI',
            tg['spx']['pressed'] == 'false' and tg['spx']['off'] and tg['spx']['text'] == '+ S&P 500'
            and tg['gld']['pressed'] == 'false' and tg['mstr']['pressed'] == 'false', str(tg))
        pg.wait_for_timeout(800)
        c = px(pg, tol=0)
        chk('1H candles: BTC-only candles (no compare colours)',
            c['spx'] == 0 and c['gld'] == 0 and c['mstr'] == 0, 'px=%s' % (c,))
        pick_line(pg)
        wait_header(pg, '9:30 AM-4 PM ET')
        chk('back on Line: the compare returns (state preserved)',
            'S&P 500 +0.4%' in header(pg), repr(header(pg))[:250])
        pg.close()

        # ---- Saturday: the last session, labelled ----
        print('--- Saturday: last session ---')
        pg = new_page(b, SAT)
        click_toggle(pg, '#bcSpx'); click_toggle(pg, '#bcGld'); click_toggle(pg, '#bcMstr')
        wait_header(pg, '9:30 AM-4 PM ET')
        pg.wait_for_timeout(800)
        chk('Saturday: header labels the last session',
            '(last session 2026-11-20)' in header(pg), repr(header(pg))[:250])
        chk('Saturday: note says it is the last session',
            'last session' in note(pg).lower(), repr(note(pg))[:250])
        c = px(pg)
        chk('Saturday: the last session draws (all four lines)',
            c['btc'] > 50 and c['spx'] > 50 and c['gld'] > 50 and c['mstr'] > 50, 'px=%s' % (c,))
        lay = pg.evaluate(LAYOUT_JS)
        chk('Saturday: no live point (complete buckets only)',
            lay and lay['hasLive'] is False, str(lay))
        pg.close()

        # ---- Monday after the open: the stale file falls back to BTC-only ----
        print('--- Monday after the open: stale file ---')
        pg = new_page(b, MON)
        click_toggle(pg, '#bcSpx'); click_toggle(pg, '#bcGld'); click_toggle(pg, '#bcMstr')
        pg.wait_for_timeout(3000)
        chk('Monday: BTC-only with the unavailable note',
            'Compare data unavailable' in note(pg), repr(note(pg))[:250])
        c = px(pg, tol=0)
        chk('Monday: no compare colours (stale file never draws)',
            c['spx'] == 0 and c['gld'] == 0 and c['mstr'] == 0 and c['btc'] > 50, 'px=%s' % (c,))
        pg.close()
        b.close()
    print('JOB10 %d checks, %d FAIL' % (n, len(fails)))
    for f in fails:
        print('  FAIL:', f)
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
