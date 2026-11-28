#!/usr/bin/env python3
"""Chart.js removal (20 Nov 2026): every chart on the site is native canvas.

Replaces test_needchart_retry.py (needChart and the lazy chart.umd.min.js inject
are gone). Static: no page or script references Chart.js (script tags, vendor
file, window.Chart, new Chart, needChart), both vendored copies are deleted, and
the BTC panel's open()/mountInline() wait on getData() only. Browser: with every
chart.umd.min.js request blocked, the homepage YTD hero + BTC popover (1D, 1Y)
and the clock page's inline BTC chart draw, with no console errors and zero
chart.umd requests. Serves this checkout on localhost; optional base URL argv[1].
"""
import os, re, socket, subprocess, sys, time, urllib.request
from pathlib import Path

R = Path(__file__).resolve().parents[1]
CHROME = os.environ.get('CHROME_PATH', '/usr/bin/google-chrome')
fails = []
n = 0

def chk(name, ok, detail=''):
    global n
    n += 1
    print('ok' if ok else 'FAIL', name, '' if ok else detail)
    if not ok:
        fails.append(name)

SKIP_DIRS = {'.git', 'tests', 'proposals', 'node_modules'}
site = []
for dp, dns, fns in os.walk(R):
    dns[:] = [d for d in dns if d not in SKIP_DIRS]
    for f in fns:
        if f.endswith(('.html', '.js', '.css', '.json', '.yml', '.toml')) and not f.endswith('.min.js'):
            site.append(Path(dp) / f)
pat = re.compile(r"chart\.umd|window\.Chart\b|new Chart\s*\(|typeof Chart\b|needChart|Chart\.getChart")
hits = []
for p in site:
    if p.suffix == '.json' and 'data' in p.parts:
        continue
    for i, line in enumerate(p.read_text(errors='ignore').splitlines(), 1):
        if pat.search(line):
            hits.append(f'{p.relative_to(R)}:{i}')
chk('no site file references Chart.js (chart.umd / window.Chart / new Chart / typeof Chart / needChart)', not hits, hits[:10])
chk('assets/vendor/chart.umd.min.js deleted', not (R / 'assets/vendor/chart.umd.min.js').exists())
chk('recap/assets/chart.umd.min.js deleted', not (R / 'recap/assets/chart.umd.min.js').exists())
PANEL = (R / 'assets/js/btcchart-panel.js').read_text()
chk('panel open()/mountInline() wait on getData() only',
    PANEL.count("getData().then(draw).catch(") == 2 and 'Promise.all([getData()' not in PANEL)
chk('panel has no NATIVE_LINE flag or Chart.js guard', 'NATIVE_LINE' not in PANEL and '!window.Chart' not in PANEL)
chk('panel: failed native line draw leaves a retry (lineFail + redrawLine)',
    'function lineFail(){' in PANEL and 'function redrawLine(){if(lineDrawn||lineRetry)draw();}' in PANEL)
CMP = (R / 'assets/js/compare.js').read_text()
chk('compare resize redraw not gated on a previous native draw',
    'var f = function(){ cmpRaf = 0; if (window.__psRedraw) window.__psRedraw(); };' in CMP)
THEME = (R / 'chart-theme.js').read_text()
chk('chart-theme.js trimmed to psC only', 'window.psC' in THEME and 'Chart' not in THEME.split('*/', 1)[1])


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


def browser_checks():
    from playwright.sync_api import sync_playwright
    srv = None
    if len(sys.argv) > 1:
        base = sys.argv[1].rstrip('/')
    else:
        port = free_port()
        srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'],
                               cwd=str(R), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = 'http://127.0.0.1:%d' % port
        for _ in range(40):
            try:
                urllib.request.urlopen(base + '/index.html', timeout=1); break
            except Exception:
                time.sleep(0.25)
    drawn = """(id) => { const c = document.getElementById(id); if (!c || !c.width || !c.height) return false;
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; const s = new Set(); let ink = 0;
      for (let i = 0; i < d.length; i += 16) { if (d[i+3] > 0) { ink++; if (s.size < 16) s.add(d[i]+','+d[i+1]+','+d[i+2]); } }
      return ink > 50 && s.size > 4; }"""
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=CHROME, args=['--no-sandbox', '--disable-gpu'])
            for path, label in (('index.html', 'home'), ('clock/index.html', 'clock')):
                pg = b.new_page(viewport={'width': 1280, 'height': 900})
                errs, umd = [], []
                pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
                pg.on('pageerror', lambda e: errs.append(str(e)))
                def route(r):
                    if 'chart.umd' in r.request.url:
                        umd.append(r.request.url); return r.abort()
                    return r.continue_()
                pg.route('**/*', route)
                pg.goto(base + '/' + path, wait_until='load', timeout=60000)
                try:
                    if label == 'home':
                        pg.wait_for_function('window.__S2_NATIVE_DRAWN === true', timeout=30000)
                        chk('home: YTD hero drawn (native, Chart.js blocked)', pg.evaluate(drawn, 'ytdChart'))
                        pg.locator('#btcLive').click()
                    pg.wait_for_function('!!window.__BTC_LINE_LAYOUT', timeout=30000)
                    pg.wait_for_timeout(300)
                    chk(f'{label}: BTC chart 1D drawn with Chart.js blocked', pg.evaluate(drawn, 'bcC'))
                    pg.locator('#bcRg [data-r="1Y"]').first.click()
                    pg.wait_for_function('!!window.__BTC_LINE_LAYOUT', timeout=15000)
                    pg.wait_for_timeout(300)
                    chk(f'{label}: BTC chart 1Y drawn with Chart.js blocked', pg.evaluate(drawn, 'bcC'))
                except Exception as e:
                    chk(f'{label}: charts drew', False, str(e)[:200])
                pg.wait_for_timeout(800)
                chk(f'{label}: no console errors', not errs, errs[:3])
                chk(f'{label}: zero chart.umd requests', not umd, umd)
                pg.close()
            b.close()
    finally:
        if srv:
            srv.terminate()

def browser_checks_scrolled():
    """Must-fix (28 Nov 2026): the BTC popup opened off-screen when the page
    was scrolled — open() added html.bc-lock before place() ran, and locking
    body too un-sticks the header, so place() measured the pill above the
    viewport (top -332px at 1440x900 scrolled 400px, vs 68px on main).
    Opens the popup from a scrolled page and checks the dialog lands below
    the (still stuck) header and the wheel stays blocked."""
    from playwright.sync_api import sync_playwright
    srv = None
    if len(sys.argv) > 1:
        base = sys.argv[1].rstrip('/')
    else:
        port = free_port()
        srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'],
                               cwd=str(R), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = 'http://127.0.0.1:%d' % port
        for _ in range(40):
            try:
                urllib.request.urlopen(base + '/index.html', timeout=1); break
            except Exception:
                time.sleep(0.25)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=CHROME, args=['--no-sandbox', '--disable-gpu'])
            pg = b.new_page(viewport={'width': 1440, 'height': 900})
            pg.goto(base + '/index.html', wait_until='load', timeout=60000)
            try:
                pg.wait_for_function('window.__S2_NATIVE_DRAWN === true', timeout=30000)
                pg.evaluate('window.scrollTo(0, 400)')
                pg.wait_for_timeout(500)
                chk('scrolled: header stuck before open',
                    pg.evaluate("Math.round(document.querySelector('.header').getBoundingClientRect().top)") == 0)
                pg.locator('#hdrTick').click()
                pg.wait_for_selector('.bc-w:not([hidden])', timeout=15000)
                pg.wait_for_timeout(1500)
                m = pg.evaluate("""(function(){
                  var r = document.querySelector('.bc-w').getBoundingClientRect();
                  var hdr = document.querySelector('.header').getBoundingClientRect();
                  var pill = document.getElementById('hdrTick').getBoundingClientRect();
                  return {top: Math.round(r.top), headerTop: Math.round(hdr.top),
                          pillBottom: Math.round(pill.bottom), scrollY: Math.round(window.scrollY)};})()""")
                chk('scrolled: popup opens below the header (top = pill bottom + 10)',
                    40 <= m['top'] <= 100 and abs(m['top'] - (m['pillBottom'] + 10)) <= 1, m)
                chk('scrolled: header stays stuck while popup is open', m['headerTop'] == 0, m)
                pg.mouse.move(720, 450)
                pg.mouse.wheel(0, 600)
                pg.wait_for_timeout(500)
                chk('scrolled: wheel over open popup does not scroll the page',
                    pg.evaluate('Math.round(window.scrollY)') == 400)
            except Exception as e:
                chk('scrolled: popup opens from a scrolled page', False, str(e)[:200])
            pg.close()
            b.close()
    finally:
        if srv:
            srv.terminate()

browser_checks()
browser_checks_scrolled()
print('NO CHART.JS TESTS', n, 'FAIL', len(fails))
sys.exit(1 if fails else 0)
