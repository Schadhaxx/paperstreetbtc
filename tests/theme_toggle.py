#!/usr/bin/env python3
"""Light-mode opt-in tests + screenshots (local static server, external network blocked).

Checks on every page:
  * no query + empty storage -> dark (no data-theme attr), storage untouched
  * storage 'light' -> light; garbage storage -> dark and the garbage key is removed
  * ?theme=light -> light and saved; ?theme=dark -> dark and key cleared
  * footer pages: 'Light version' visible in dark, 'Back to dark' hidden;
    clicking toggles, and 'Back to dark' clears storage
  * footerless pages: 'Back to dark' visible only in light
  * no page errors / console errors (other than blocked external requests) in either mode
Also saves light (and dark) screenshots of every page and key widgets at 390 and 1280.

usage: python3 tests/theme_toggle.py SITE_DIR SHOT_DIR
"""
import os, sys, threading, functools, http.server, socketserver
from playwright.sync_api import sync_playwright

PAGES = ['index.html', 'screener.html', 'compare/index.html', 'custom/index.html', 'recap/index.html'] + \
        ['recap/2026-%02d/index.html' % m for m in range(1, 12)]
FOOTER = {'index.html'} | {'recap/2026-%02d/index.html' % m for m in range(1, 12)}
exe = next((p for p in ['/usr/bin/google-chrome', '/usr/bin/chromium'] if os.path.exists(p)), None)
CLOCK = '2026-10-30T20:00:00Z'


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


site, shots = sys.argv[1], sys.argv[2]
os.makedirs(shots, exist_ok=True)
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=site)); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
U = 'http://127.0.0.1:%d/' % srv.server_address[1]
results = []


def check(name, cond, info=''):
    results.append((name, bool(cond), info)); print(('PASS ' if cond else 'FAIL ') + name + (' ' + info if info and not cond else ''), flush=True)


def fake_coinbase(route):
    """Synthetic, deterministic Coinbase responses (widgets only) so candle views render offline."""
    import json, math, urllib.parse, datetime as dt
    u = urllib.parse.urlparse(route.request.url); q = urllib.parse.parse_qs(u.query)
    if 'spot' in u.path:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'data': {'amount': '77500.00', 'currency': 'USD'}}))
    g = int(q.get('granularity', ['86400'])[0])
    end = int(dt.datetime(2026, 10, 30, 20, tzinfo=dt.timezone.utc).timestamp())
    if 'end' in q:
        try: end = min(end, int(dt.datetime.fromisoformat(q['end'][0].replace('Z', '+00:00')).timestamp()))
        except Exception: pass
    start = end - 300 * g
    if 'start' in q:
        try: start = max(start, int(dt.datetime.fromisoformat(q['start'][0].replace('Z', '+00:00')).timestamp()))
        except Exception: pass
    rows = []; t = end - end % g
    while t >= start and len(rows) < 300:
        o = 77500 + 900 * math.sin(t / g / 5.0); c = o + 350 * math.cos(t / g / 3.0)
        rows.append([t, min(o, c) - 120, max(o, c) + 120, o, c, 10]); t -= g
    route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))


def ctx_page(b, w=390, store=None, cb=False):
    ctx = b.new_context(viewport={'width': w, 'height': 900}, reduced_motion='reduce')
    ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith(U) else (fake_coinbase(r) if cb and 'coinbase.com' in r.request.url else r.abort()))
    if store is not None:
        ctx.add_init_script('if(!sessionStorage.getItem("_s")){sessionStorage.setItem("_s",1);localStorage.setItem("ps-theme",%r)}' % store)
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
    pg.clock.set_fixed_time(CLOCK)
    return ctx, pg, errs


TH = 'document.documentElement.getAttribute("data-theme")'
ST = 'localStorage.getItem("ps-theme")'

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    for pgname in PAGES:
        ctx, pg, errs = ctx_page(b)
        pg.goto(U + pgname, wait_until='networkidle')
        check(pgname + ' default dark', pg.evaluate(TH) is None and pg.evaluate(ST) is None)
        # floating pill (v3): only on pages with Top (index); always visible there
        pill = pg.locator('#psThemePill')
        if pgname == 'index.html':
            check(pgname + ' floating pill visible in dark', pill.count() == 1 and pill.is_visible())
        else:
            check(pgname + ' no floating pill (Top not on this page)', pill.count() == 0)
        if pgname == 'index.html' and pill.count():
            check(pgname + ' pill label is Light in dark', pill.inner_text().strip() == 'Light')
            check(pgname + ' pill aria-pressed false in dark', pill.get_attribute('aria-pressed') == 'false')
            box = pill.bounding_box()
            # Match Top's touch target; Top itself is ~34-40px with current padding, so require >= 32
            check(pgname + ' pill touch target matches Top scale', box and box['height'] >= 32, str(box))
            pill.focus(); pg.wait_for_timeout(50)
            with pg.expect_navigation():
                pill.click()
            pg.wait_for_load_state('networkidle')
            check(pgname + ' pill click -> light + saved', pg.evaluate(TH) == 'light' and pg.evaluate(ST) == 'light')
            check(pgname + ' pill label is Dark in light', pg.locator('#psThemePill').inner_text().strip() == 'Dark')
            check(pgname + ' pill aria-pressed true in light', pg.locator('#psThemePill').get_attribute('aria-pressed') == 'true')
            # keyboard: focus + Enter
            pg.locator('#psThemePill').focus()
            with pg.expect_navigation():
                pg.locator('#psThemePill').press('Enter')
            pg.wait_for_load_state('networkidle')
            check(pgname + ' pill Enter -> dark + cleared', pg.evaluate(TH) is None and pg.evaluate(ST) is None)
        if pgname in FOOTER:
            check(pgname + ' "Light version" visible in dark', pg.locator('.ps-theme-link .ps-to-light').is_visible() and not pg.locator('.ps-theme-link .ps-to-dark').is_visible())
            pg.locator('.ps-theme-link .ps-to-light').click(); pg.wait_for_load_state('networkidle')
            check(pgname + ' click Light version -> light + saved', pg.evaluate(TH) == 'light' and pg.evaluate(ST) == 'light')
            check(pgname + ' "Back to dark" shown in light', pg.locator('.ps-theme-link .ps-to-dark').is_visible() and not pg.locator('.ps-theme-link .ps-to-light').is_visible())
            pg.goto(U + pgname, wait_until='networkidle')
            check(pgname + ' light remembered without query', pg.evaluate(TH) == 'light')
            pg.locator('.ps-theme-link .ps-to-dark').click(); pg.wait_for_load_state('networkidle')
            check(pgname + ' Back to dark -> dark + storage cleared', pg.evaluate(TH) is None and pg.evaluate(ST) is None)
        else:
            check(pgname + ' no theme link visible in dark', not pg.locator('.ps-theme-alt').is_visible())
            pg.goto(U + pgname + '?theme=light', wait_until='networkidle')
            check(pgname + ' ?theme=light -> light + saved', pg.evaluate(TH) == 'light' and pg.evaluate(ST) == 'light')
            check(pgname + ' "Back to dark" visible in light', pg.locator('.ps-theme-alt .ps-to-dark').is_visible() and not pg.locator('.ps-theme-alt .ps-to-light').is_visible())
            pg.locator('.ps-theme-alt .ps-to-dark').click(); pg.wait_for_load_state('networkidle')
            check(pgname + ' Back to dark -> dark + storage cleared', pg.evaluate(TH) is None and pg.evaluate(ST) is None)
        check(pgname + ' no console errors (toggle run)', not errs, '; '.join(errs[:3]))
        ctx.close()
        ctx, pg, errs = ctx_page(b, store='banana'); pg.goto(U + pgname, wait_until='networkidle')
        check(pgname + ' garbage storage -> dark, key removed', pg.evaluate(TH) is None and pg.evaluate(ST) is None); ctx.close()
        ctx, pg, errs = ctx_page(b, store='light'); pg.goto(U + pgname + '?theme=dark', wait_until='networkidle')
        check(pgname + ' ?theme=dark overrides saved light and clears it', pg.evaluate(TH) is None and pg.evaluate(ST) is None); ctx.close()
        # screenshots + console check in light at both widths
        for w in (390, 1280):
            for mode in ('light',):
                ctx, pg, errs = ctx_page(b, w, store='light'); pg.goto(U + pgname, wait_until='networkidle'); pg.evaluate("document.querySelectorAll('img[loading=lazy]').forEach(function(i){i.loading='eager'})"); pg.wait_for_load_state('networkidle'); pg.wait_for_timeout(800)
                pg.screenshot(path='%s/%s_%d_light.png' % (shots, pgname.replace('/', '_').replace('.html', ''), w), full_page=True, animations='disabled')
                check('%s %d light: no console errors' % (pgname, w), not errs, '; '.join(errs[:3])); ctx.close()
    # ---- key widgets, both modes ----
    for w in (390, 1280):
        for mode in ('dark', 'light'):
            tag = '%d_%s' % (w, mode)
            ctx, pg, errs = ctx_page(b, w, store='light' if mode == 'light' else None, cb=True)
            pg.goto(U + 'index.html', wait_until='networkidle')
            try:
                pg.evaluate('document.getElementById("hdrTick").click()'); pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
                pg.screenshot(path='%s/widget_btcchart_1D_%s.png' % (shots, tag), animations='disabled')
                pg.click('#bcCt button[data-ct="1h"]'); pg.wait_for_timeout(1200)
                bx = pg.locator('#bcC').bounding_box(); pg.mouse.click(bx['x'] + bx['width'] * 0.7, bx['y'] + bx['height'] * 0.5); pg.wait_for_timeout(500)
                pg.screenshot(path='%s/widget_candle_pill_%s.png' % (shots, tag), animations='disabled')
                check('candle pill shown (%s)' % tag, pg.locator('#bcSel').is_visible())
                pg.keyboard.press('Escape')
            except Exception as e:
                check('btc chart widget (%s)' % tag, False, str(e)[:200])
            # chart tooltip on a recap Chart.js chart
            pg.goto(U + 'recap/2026-10/index.html', wait_until='networkidle'); pg.wait_for_timeout(800)
            cv = pg.locator('canvas').first
            if cv.count():
                cv.scroll_into_view_if_needed(); bb = cv.bounding_box(); pg.mouse.move(bb['x'] + bb['width'] * 0.6, bb['y'] + bb['height'] * 0.5); pg.wait_for_timeout(500)
                pg.screenshot(path='%s/widget_recap_chart_tooltip_%s.png' % (shots, tag), clip={'x': 0, 'y': max(0, bb['y'] - 60), 'width': w, 'height': min(700, bb['height'] + 120)}, animations='disabled')
            pg.goto(U + 'screener.html', wait_until='networkidle'); pg.wait_for_timeout(800)
            try:
                card = pg.locator('.card[data-symbol]').first; card.scroll_into_view_if_needed(); card.click(); pg.wait_for_selector('#ind-modal.open', timeout=8000); pg.wait_for_timeout(1200)
                pg.screenshot(path='%s/widget_screener_modal_%s.png' % (shots, tag), animations='disabled')
                check('screener modal opens (%s)' % tag, True)
            except Exception as e:
                check('screener modal opens (%s)' % tag, False, str(e)[:200])
            check('widgets %s: no console errors' % tag, not errs, '; '.join(errs[:3]))
            ctx.close()
    b.close()
n = sum(1 for r in results if not r[1])
print('theme toggle: %d checks, %d failed' % (len(results), n))
sys.exit(1 if n else 0)
