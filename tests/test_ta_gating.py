#!/usr/bin/env python3
"""TA drawing fixes Stage 1 checks (21 Nov 2026): per-view toggle gating.
On a gated view the toggle stays visible but disabled (greyed out) and its
overlay does not draw; the same toggle works normally on other views. The
agreed lists are in ~/workspace/your_files/ta-gating-pass-sheet-2026-11-22.md:
Trendlines NO LONGER gated anywhere (Job 1, 21 Nov 2026 — the Line y-range
expands to include the drawn lines, so they draw on Line 1D/1W);
Bollinger NO LONGER gated anywhere (Job 2, 21 Nov 2026 — the pre-warm
fetches history before the visible window, so a 20-period is valid from
index 0); SMA 20/50 on 1W; SMA 200 NO LONGER gated on 1D/1W (Job 2 —
same pre-warm; it was already live on the longer ranges);
EMA 50 on 1W, EMA 200 NO LONGER gated on 1D/1W (Job 2 — SMA 200's twin),
EMA 20 never; RSI NO LONGER gated anywhere (Job 3, 22 Nov 2026 — the
strip now has a scale, shaded 30/70 bands and a live value); 5Y/10Y/Max
trendlines untouched.
Serves this checkout on localhost (or takes a base URL argv[1] and a shots
dir argv[2], as run_all.sh does), stubs the live-price and candle feeds
with deterministic data, serves a synthetic ta-lines.json fixture, and
verifies at phone 390 dark + desktop 1440 light: each greyed-out toggle
is disabled on its gated view and enabled elsewhere; the overlay stays
off on gated views while the non-gated overlays still draw; the toggle
comes back to life on a view where it works. The saved state is seeded
with every overlay on (localStorage ps-ta-v1) so the gating, not the
toggle, is what is under test. Comparison-on behaviour is unchanged and
not re-tested here (covered by test_ta_stage2.py).
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

def iso(d):
    return d.strftime('%Y-%m-%dT%H:%M:%SZ')

def lvl(price, kind, ext=False, brk=False):
    return {'price': price, 'kind': kind, 'score': 2.5, 'rawScore': 4.0, 'distAtr': 2.0,
            'touches': 3, 'lastTouch': '2026-10-29T00:00:00Z', 'ageCandles': 5,
            'broken': brk, 'held': False, 'extreme': ext}

def slp(kind, slope, anchor, anchor_price):
    return {'kind': kind, 'slope': slope, 'anchor': {'t': iso(anchor), 'price': anchor_price},
            'touches': 5, 'score': 5.0, 'rawScore': 6.0, 'distAtr': 1.0, 'priceNow': anchor_price,
            'broken': False, 'held': False}

def tf(asOf, levels, sloped, missS=False, missR=False):
    return {'asOf': iso(asOf), 'atr': 700, 'lastClose': 77500, 'levels': levels, 'sloped': sloped,
            'missingSupport': missS, 'missingResistance': missR}

def fixture():
    """Fresh fixture (same shape as test_ta_stage4.py): 12 lines on a 1h
    chart (1h 6 + 4h 3 + 1d 3), 3 lines on a 1d chart."""
    h1 = FIXED - dt.timedelta(minutes=10)
    h4 = FIXED - dt.timedelta(hours=1)
    d1 = FIXED - dt.timedelta(hours=5)
    t1h = tf(h1,
        [lvl(79500, 'resistance'), lvl(79000, 'resistance', brk=True), lvl(76000, 'support'), lvl(74800, 'support', ext=True)],
        [slp('support', 30, FIXED - dt.timedelta(hours=12), 75500),
         slp('resistance', -20, FIXED - dt.timedelta(hours=10), 79800)])
    t4h = tf(h4,
        [lvl(79500, 'resistance')],
        [slp('support', 120, FIXED - dt.timedelta(hours=20), 74000),
         slp('support', 90, FIXED - dt.timedelta(hours=24), 73000)],
        missS=True)
    t1d = tf(d1,
        [lvl(81000, 'resistance'), lvl(75000, 'support')],
        [slp('support', -30, dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc), 76000)])
    return {'v': 1, 'kind': 'ta-lines', 'asOf': iso(FIXED), 'timeframes': {'1h': t1h, '4h': t4h, '1d': t1d}}

FIXTURE = {'body': fixture()}

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
        return route.fulfill(status=200, content_type='application/json', body=json.dumps(FIXTURE['body']))
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

# Every overlay on in the saved state, so the gating (not the toggle) is
# what is under test: tl + bb + SMA 20/50/200 + EMA 20 + RSI.
SEED = "window.localStorage.setItem('ps-ta-v1', JSON.stringify({tl:true,bb:true,ma:true,maSet:{sma20:true,sma50:true,sma200:true,ema20:true},rsi:true,rsiCol:false,last1DSize:'1h'}))"

def colour_present(pg, rgb, sel='#bcC', tol=20):
    """True if an (R,G,B) appears on the canvas within +/-tol per channel.
    tol is 20 (not the 40 the Stage 2/4 tests use): the cyan price line's
    anti-aliased edges and pink x cyan crossing blends land within 40 of
    the Bollinger violet and the SMA 200 teal, so 40 false-positives
    here. 20 still catches the solid core pixels of a drawn line."""
    return pg.evaluate("""([s, rgb, tol]) => { const c = document.querySelector(s); if (!c) return false;
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      for (let i = 0; i < d.length; i += 4) {
        if (Math.abs(d[i] - rgb[0]) <= tol && Math.abs(d[i+1] - rgb[1]) <= tol && Math.abs(d[i+2] - rgb[2]) <= tol) return true; }
      return false; }""", [sel, rgb, tol])

def colour_count(pg, rgb, sel='#bcC', tol=20):
    """Count of pixels on the canvas within +/-tol of rgb. A real drawn
    line (2px wide across ~300px) is hundreds of pixels; anti-aliased
    edge pixels of another line are a handful. Use this, not
    colour_present, when another overlay's edges can land near the
    colour — the Job 1 trendlines on 1D Line put 7 edge pixels within
    tol=10 of the SMA 200 teal, with 0 exact."""
    return pg.evaluate("""([s, rgb, tol]) => { const c = document.querySelector(s); if (!c) return 0;
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0;
      for (let i = 0; i < d.length; i += 4) {
        if (Math.abs(d[i] - rgb[0]) <= tol && Math.abs(d[i+1] - rgb[1]) <= tol && Math.abs(d[i+2] - rgb[2]) <= tol) n++; }
      return n; }""", [sel, rgb, tol])

def tl(pg):
    return pg.evaluate("window.__TA_TL_DEBUG ? window.__TA_TL_DEBUG() : null")

def wait_status(pg, want, timeout=10000):
    pg.wait_for_function("window.__TA_TL_DEBUG && window.__TA_TL_DEBUG().status === '%s'" % want, timeout=timeout)

def open_panel(pg):
    pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)

def disabled(pg, sel):
    return pg.is_disabled(sel)

def panel_status(pg):
    if pg.evaluate("document.querySelector('.ta-panel').hidden"):
        open_panel(pg)
    return pg.inner_text('.ta-panel .ta-tl-status')

def pick_size(pg, size):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-size="%s"]' % size); pg.wait_for_timeout(1200)

def pick_type(pg, typ):
    """Pick a chart type (line/candles) from the type menu. Job 5: a range
    switch now carries the chart type over (1D candles stay candles on
    1W), so a phase that wants Line must pick it explicitly instead of
    relying on the old reset-to-Line side effect."""
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-pick="%s"]' % typ); pg.wait_for_timeout(1200)

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
        # ---- clock page, phone 390 dark ----
        ctx = b.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce'); ctx.route('**/*', handler)
        ctx.add_init_script(SEED)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'clock/index.html', wait_until='networkidle')
            pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            # ---- Phase A: 1D Line (default view; Job 1 ungreyed trendlines) ----
            open_panel(pg)
            chk('A 1D Line: trendlines toggle enabled (Job 1)', not disabled(pg, '.ta-panel [data-ta-key="tl"]'))
            chk('A 1D Line: Bollinger toggle enabled (Job 2)', not disabled(pg, '.ta-panel [data-ta-key="bb"]'))
            chk('A 1D Line: RSI toggle enabled (Job 3)', not disabled(pg, '.ta-panel [data-ta-key="rsi"]'))
            chk('A 1D Line: MA group switch enabled', not disabled(pg, '.ta-panel [data-ta-key="ma"]'))
            chk('A 1D Line: SMA 20 chip enabled', not disabled(pg, '.ta-panel [data-ta-ma="sma20"]'))
            chk('A 1D Line: SMA 50 chip enabled', not disabled(pg, '.ta-panel [data-ta-ma="sma50"]'))
            chk('A 1D Line: SMA 200 chip enabled (Job 2)', not disabled(pg, '.ta-panel [data-ta-ma="sma200"]'))
            chk('A 1D Line: EMA 20 chip enabled', not disabled(pg, '.ta-panel [data-ta-ma="ema20"]'))
            chk('A 1D Line: EMA 50 chip enabled', not disabled(pg, '.ta-panel [data-ta-ma="ema50"]'))
            chk('A 1D Line: EMA 200 chip enabled (Job 2)', not disabled(pg, '.ta-panel [data-ta-ma="ema200"]'))
            chk('A 1D Line: pill badge still counts saved state (7)', '7' in pg.inner_text('#taPill'), pg.inner_text('#taPill'))
            wait_status(pg, 'live')
            pr = tl(pg)
            chk('A 1D Line: trendlines live, 12 lines draw (Job 1)', pr['tf'] == '1h' and pr['status'] == 'live' and len(pr['last']['lines']) == 12, str(pr))
            chk('A 1D Line: panel says Live', panel_status(pg).startswith('Live'), panel_status(pg))
            chk('A 1D Line: Bollinger violet draws (Job 2)', colour_present(pg, (167, 139, 250)))
            chk('A 1D Line: SMA 20 pink draws', colour_present(pg, (244, 114, 182)))
            chk('A 1D Line: SMA 50 amber draws', colour_present(pg, (251, 191, 36)))
            n_sma200 = colour_count(pg, (20, 184, 166), tol=10)
            chk('A 1D Line: SMA 200 teal draws (Job 2)', n_sma200 >= 50, 'count=%d' % n_sma200)
            chk('A 1D Line: RSI strip shows (Job 3)', not pg.evaluate("document.getElementById('taRsi').hidden"))
            pg.screenshot(path=str(shots / 'clock-390-dark-ta-gating-panel.png'), animations='disabled')
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            # ---- Phase B: 1D 1H candles (trendlines live again) ----
            pick_size(pg, '1h'); pg.wait_for_timeout(600)
            open_panel(pg)
            chk('B 1D 1H: trendlines toggle enabled', not disabled(pg, '.ta-panel [data-ta-key="tl"]'))
            chk('B 1D 1H: Bollinger enabled (Job 2)', not disabled(pg, '.ta-panel [data-ta-key="bb"]'))
            chk('B 1D 1H: RSI enabled (Job 3)', not disabled(pg, '.ta-panel [data-ta-key="rsi"]'))
            chk('B 1D 1H: SMA 200 chip enabled (Job 2)', not disabled(pg, '.ta-panel [data-ta-ma="sma200"]'))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            wait_status(pg, 'live')
            pr = tl(pg)
            chk('B 1D 1H: trendlines live, 12 lines draw', pr['tf'] == '1h' and pr['status'] == 'live' and len(pr['last']['lines']) == 12, str(pr))
            chk('B 1D 1H: Bollinger violet draws (Job 2)', colour_present(pg, (167, 139, 250)))
            chk('B 1D 1H: SMA 20 + 50 + 200 draw (Job 2)', colour_present(pg, (244, 114, 182)) and colour_present(pg, (251, 191, 36)) and colour_present(pg, (20, 184, 166), tol=10))
            # ---- Phase C: 1M Line (Bollinger ungated everywhere now, Job 2; SMA 200 live) ----
            # Job 5: the range switch carries the type over, so 1D 1H candles
            # would land on 1M candles — pick Line explicitly for this phase.
            pg.click('#bcRgs button[data-r="1M"]'); pg.wait_for_timeout(1200)
            pick_type(pg, 'line')
            open_panel(pg)
            chk('C 1M Line: trendlines toggle enabled', not disabled(pg, '.ta-panel [data-ta-key="tl"]'))
            chk('C 1M Line: Bollinger toggle enabled (Job 2)', not disabled(pg, '.ta-panel [data-ta-key="bb"]'))
            chk('C 1M Line: RSI enabled (Job 3)', not disabled(pg, '.ta-panel [data-ta-key="rsi"]'))
            chk('C 1M Line: SMA 200 chip enabled', not disabled(pg, '.ta-panel [data-ta-ma="sma200"]'))
            chk('C 1M Line: SMA 20/50 chips enabled', not disabled(pg, '.ta-panel [data-ta-ma="sma20"]') and not disabled(pg, '.ta-panel [data-ta-ma="sma50"]'))
            chk('C 1M Line: EMA 50/200 chips enabled', not disabled(pg, '.ta-panel [data-ta-ma="ema50"]') and not disabled(pg, '.ta-panel [data-ta-ma="ema200"]'))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            wait_status(pg, 'live')
            pr = tl(pg)
            chk('C 1M Line: trendlines live, 3 lines draw (1d only)', pr['tf'] == '1d' and pr['status'] == 'live' and len(pr['last']['lines']) == 3, str(pr))
            chk('C 1M Line: Bollinger violet draws (Job 2)', colour_present(pg, (167, 139, 250)))
            chk('C 1M Line: SMA 200 teal draws', colour_present(pg, (20, 184, 166), tol=10))
            # ---- Phase D: 1W Line then 1W daily candles (Job 1 ungreyed 1W Line) ----
            # Job 5: the range switch carries the type over, so 1M Line
            # lands on 1W Line here (Line carries the same way as candles).
            pg.click('#bcRgs button[data-r="1W"]'); pg.wait_for_timeout(1200)
            pick_type(pg, 'line')
            open_panel(pg)
            chk('D 1W Line: trendlines toggle enabled (Job 1)', not disabled(pg, '.ta-panel [data-ta-key="tl"]'))
            chk('D 1W Line: SMA 20 chip disabled', disabled(pg, '.ta-panel [data-ta-ma="sma20"]'))
            chk('D 1W Line: SMA 50 chip disabled', disabled(pg, '.ta-panel [data-ta-ma="sma50"]'))
            chk('D 1W Line: SMA 200 chip enabled (Job 2)', not disabled(pg, '.ta-panel [data-ta-ma="sma200"]'))
            chk('D 1W Line: EMA 20 chip enabled', not disabled(pg, '.ta-panel [data-ta-ma="ema20"]'))
            chk('D 1W Line: EMA 50 chip disabled', disabled(pg, '.ta-panel [data-ta-ma="ema50"]'))
            chk('D 1W Line: EMA 200 chip enabled (Job 2)', not disabled(pg, '.ta-panel [data-ta-ma="ema200"]'))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            wait_status(pg, 'live')
            pr = tl(pg)
            chk('D 1W Line: trendlines live, 3 lines draw (Job 1)', pr['tf'] == '1d' and pr['status'] == 'live' and len(pr['last']['lines']) == 3, str(pr))
            pick_size(pg, 'daily'); pg.wait_for_timeout(600)
            open_panel(pg)
            chk('D 1W candles: trendlines toggle enabled', not disabled(pg, '.ta-panel [data-ta-key="tl"]'))
            chk('D 1W candles: SMA 20/50 chips still disabled (1W)', disabled(pg, '.ta-panel [data-ta-ma="sma20"]') and disabled(pg, '.ta-panel [data-ta-ma="sma50"]'))
            chk('D 1W candles: SMA 200 chip enabled (Job 2)', not disabled(pg, '.ta-panel [data-ta-ma="sma200"]'))
            chk('D 1W candles: Bollinger enabled (Job 2)', not disabled(pg, '.ta-panel [data-ta-key="bb"]'))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            wait_status(pg, 'live')
            pr = tl(pg)
            chk('D 1W candles: trendlines live, 3 lines draw (1d only)', pr['tf'] == '1d' and pr['status'] == 'live' and len(pr['last']['lines']) == 3, str(pr))
            # ---- Phase E: 5Y (trendlines untouched — off by design) ----
            pg.click('#bcRgs button[data-r="5Y"]'); pg.wait_for_timeout(1200)
            open_panel(pg)
            chk('E 5Y: trendlines toggle NOT disabled (untouched)', not disabled(pg, '.ta-panel [data-ta-key="tl"]'))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            wait_status(pg, 'unavailable')
            pr = tl(pg)
            chk('E 5Y: status unavailable, no lines (as before)', pr['status'] == 'unavailable' and pr['last']['lines'] == [], str(pr))
            chk('E 5Y: panel says Not available on this range', panel_status(pg) == 'Not available on this range', panel_status(pg))
            # ---- Phase F: back to 1D 1H candles (toggle comes back to life) ----
            pg.click('#bcRgs button[data-r="1D"]'); pg.wait_for_timeout(1200)
            pick_size(pg, '1h'); pg.wait_for_timeout(600)
            open_panel(pg)
            chk('F back to 1D 1H: trendlines toggle enabled', not disabled(pg, '.ta-panel [data-ta-key="tl"]'))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            wait_status(pg, 'live')
            pr = tl(pg)
            chk('F back to 1D 1H: trendlines live again, 12 lines', pr['tf'] == '1h' and pr['status'] == 'live' and len(pr['last']['lines']) == 12, str(pr))
            chk('A-F clock 390 dark: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('A-F clock 390 dark', False, str(e)[:200])
        ctx.close()
        # ---- desktop 1440 light: spot-check the matrix ----
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
            open_panel(pg)
            chk('G 1440 light 1D Line: tl + bb + rsi enabled (Job 3)', not disabled(pg, '.ta-panel [data-ta-key="tl"]') and not disabled(pg, '.ta-panel [data-ta-key="bb"]') and not disabled(pg, '.ta-panel [data-ta-key="rsi"]'))
            chk('G 1440 light 1D Line: panel says Live (Job 1)', panel_status(pg).startswith('Live'), panel_status(pg))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            pg.click('#bcRgs button[data-r="1M"]'); pg.wait_for_timeout(1200)
            open_panel(pg)
            chk('G 1440 light 1M Line: tl + sma200 + bb + rsi enabled (Job 3)', not disabled(pg, '.ta-panel [data-ta-key="tl"]') and not disabled(pg, '.ta-panel [data-ta-ma="sma200"]') and not disabled(pg, '.ta-panel [data-ta-key="bb"]') and not disabled(pg, '.ta-panel [data-ta-key="rsi"]'))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            wait_status(pg, 'live')
            chk('G 1440 light 1M Line: Bollinger violet draws (Job 2)', colour_present(pg, (124, 58, 237)))
            chk('G 1440 light: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('G 1440 light', False, str(e)[:200])
        ctx.close()
        b.close()
    print('TA GATING:', 'PASS (%d checks)' % n if not fails else 'FAIL (%d/%d)' % (len(fails), n))
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
