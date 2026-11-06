#!/usr/bin/env python3
"""OI-001 Compare scope check: crafted Coinbase day must label #pvChartNote + legend (not 'is final' / plain Spot BTC).
Serves this checkout on localhost; intercepts history.json. Exit 0 only if backup wording shows."""
import copy, json, os, sys, threading, http.server, socketserver
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
DAY = '2026-10-23'
BACKUP_NOTE = f'BTC close {DAY} from backup source'
BACKUP_LBL = "Spot BTC (close from backup source until Yahoo's final bar)"
CHROME = os.environ.get('CHROME_PATH', '/usr/bin/google-chrome')
PORT = int(os.environ.get('OI001_SCOPE_PORT', '8777'))

# Prefer a frozen live history if present; else minimal stub with enough closes for Compare to boot.
HIST_CANDIDATES = [
    Path('/workspace/oi001-review/history.live.json'),
    REPO / 'assets/data/history.json',
]

def load_history():
    for p in HIST_CANDIDATES:
        if p.is_file():
            h = json.loads(p.read_text())
            print(f'history source: {p}')
            return h
    # Fallback: pull from data branch (read-only)
    import urllib.request
    url = 'https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/history.json'
    h = json.loads(urllib.request.urlopen(url, timeout=30).read())
    print('history source: live data branch')
    return h

def craft(h, day=DAY):
    h = copy.deepcopy(h)
    fs = h.setdefault('fallback_sources', {})
    # clear other BTC backup marks so the note names DAY
    for d, v in list(fs.items()):
        if isinstance(v, dict) and 'BTC' in v:
            v = dict(v); del v['BTC']
            if v: fs[d] = v
            else: del fs[d]
    entry = dict(fs.get(day) or {})
    entry['BTC'] = 'coinbase'
    fs[day] = entry
    h['btc_provisional'] = []
    return h

def serve(root, port):
    os.chdir(root)
    handler = http.server.SimpleHTTPRequestHandler
    # quiet logs
    class Quiet(handler):
        def log_message(self, *a): pass
    httpd = socketserver.TCPServer(('127.0.0.1', port), Quiet)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd

def main():
    hist = craft(load_history())
    body = json.dumps(hist)
    httpd = serve(str(REPO), PORT)
    fails = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=CHROME,
                args=['--no-sandbox', '--disable-gpu', '--font-render-hinting=none'],
            )
            page = browser.new_context(
                viewport={'width': 1280, 'height': 900},
                color_scheme='dark',
            ).new_page()

            def handle(route):
                if 'history.json' in route.request.url:
                    route.fulfill(status=200, content_type='application/json', body=body)
                else:
                    route.continue_()
            page.route('**/*', handle)
            page.goto(f'http://127.0.0.1:{PORT}/compare/', wait_until='domcontentloaded', timeout=60000)
            page.wait_for_selector('#pvChartNote', timeout=30000)
            # wait for fetch+draw
            page.wait_for_timeout(4500)
            note = page.locator('#pvChartNote').inner_text()
            # Chart.js legend is canvas; series buttons + note are the DOM contracts
            series = page.evaluate("""() => [...document.querySelectorAll('#pvSeries button')].map(b=>b.textContent).join('|')""")
            datasets = page.evaluate("""() => {
              const ch = (window.Chart && Chart.getChart) ? Chart.getChart(document.getElementById('pvChart')) : null;
              if (!ch) return [];
              return (ch.data.datasets || []).map(d => d.label || '');
            }""")
            print('NOTE:', note)
            print('SERIES_BTNS:', series)
            print('DATASET_LABELS:', datasets)

            def fail(msg):
                nonlocal fails
                fails += 1
                print('FAIL', msg)

            if BACKUP_NOTE not in note:
                fail(f'#pvChartNote missing backup wording; got: {note!r}')
            if 'is final' in note:
                fail(f'#pvChartNote still says is final: {note!r}')
            # Dataset label (Chart.js) must use BACKUP_LBL when BTC is on
            btc_labels = [x for x in datasets if 'BTC' in x or 'backup' in x.lower()]
            if not any(BACKUP_LBL == x or 'backup source' in x for x in datasets):
                fail(f'chart dataset labels missing backup: {datasets}')
            if any(x == 'Spot BTC' for x in datasets):
                fail(f'plain Spot BTC still in dataset labels: {datasets}')
            browser.close()
    finally:
        httpd.shutdown()

    if fails:
        print(f'OI-001 COMPARE SCOPE FAIL {fails}')
        return 1
    print('OI-001 COMPARE SCOPE PASS')
    return 0

if __name__ == '__main__':
    sys.exit(main())
