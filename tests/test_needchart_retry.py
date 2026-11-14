#!/usr/bin/env python3
"""needChart (btcchart-panel.js): a failed Chart.js inject removes the dead
script tag and resets the promise, so a retry starts fresh and succeeds.

Resurrected from the reverted Speed Option 2 test, updated: exercises the
REAL shipped needChart (exposed as window.__BTCP._needChart) instead of a
simulation, with the first chart.umd.min.js request aborted and the retry
fulfilled from a stub. Serves this checkout on localhost; takes an optional
base URL as argv[1] (same convention as test_ytd_chart_scroll.py).
"""
import re, socket, subprocess, sys, time, urllib.request
from pathlib import Path

R = Path(__file__).resolve().parents[1]
PANEL = (R / 'assets/js/btcchart-panel.js').read_text()
fails = []
n = 0

def chk(name, ok, detail=''):
    global n
    n += 1
    if ok:
        print('ok', name)
    else:
        print('FAIL', name, detail)
        fails.append(name)

chk('needChart removes failed script on error',
    bool(re.search(r"s\.onerror=function\(\)\{[\s\S]*?removeChild\(s\)[\s\S]*?chartP=null", PANEL)))
chk('needChart strips leftover umd tags before reinject',
    'querySelectorAll(\'script[src*="chart.umd.min.js"]\')' in PANEL and 'el.remove()' in PANEL)
chk('needChart dedupes in-flight inject (chartP)',
    'var chartP=null' in PANEL and 'if(chartP)return chartP;' in PANEL)
chk('panel exposes _needChart for this test',
    'P._needChart=needChart' in PANEL)


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p

def main():
    from playwright.sync_api import sync_playwright
    base = None
    srv = None
    if len(sys.argv) > 1:
        base = sys.argv[1].rstrip('/')
    else:
        port = free_port()
        srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port),
                                '--bind', '127.0.0.1'], cwd=str(R),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = 'http://127.0.0.1:%d' % port
        for _ in range(40):
            try:
                urllib.request.urlopen(base + '/assets/js/btcchart.js?v=et24', timeout=1)
                break
            except Exception:
                time.sleep(0.25)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox', '--disable-gpu'])
            page = browser.new_page()
            attempts = {'n': 0}
            def route_umd(route):
                attempts['n'] += 1
                if attempts['n'] == 1:
                    route.abort()
                else:
                    route.fulfill(status=200, content_type='text/javascript',
                                  body='window.Chart=function(){};')
            page.route('**/chart.umd.min.js', route_umd)
            # Bare harness page: a pill is all the eager file needs to define __BTCP.
            page.set_content('<!doctype html><html><head></head><body>'
                             '<button type="button" id="hdrTick"></button></body></html>')
            page.add_script_tag(url=base + '/assets/js/btcchart.js?v=et24')
            page.wait_for_function("!!window.__BTCP", timeout=5000)
            page.add_script_tag(url=base + '/assets/js/btcchart-panel.js?v=et24')
            page.wait_for_function("!!(window.__BTCP && window.__BTCP.panelReady)", timeout=5000)
            result = page.evaluate("""async () => {
              const B = window.__BTCP;
              let firstErr = null;
              try { await B._needChart(); } catch (e) { firstErr = String(e.message || e); }
              const tagsAfterFail = document.querySelectorAll('script[src*="chart.umd.min.js"]').length;
              let second = null, secondErr = null;
              try { second = await B._needChart(); } catch (e) { secondErr = String(e.message || e); }
              return {
                firstErr, tagsAfterFail, second, secondErr,
                hasChart: typeof window.Chart === 'function',
                tagsAfterRetry: document.querySelectorAll('script[src*="chart.umd.min.js"]').length
              };
            }""")
            browser.close()
        chk('first attempt fails', result['firstErr'] == 'chart', str(result.get('firstErr')))
        chk('failed script tag removed', result['tagsAfterFail'] == 0, str(result.get('tagsAfterFail')))
        chk('retry succeeds', result['second'] is None and result['secondErr'] is None, str(result))
        chk('Chart present after retry', result['hasChart'], str(result))
        chk('exactly two inject attempts', attempts['n'] == 2, str(attempts))
        chk('one script tag after retry', result['tagsAfterRetry'] == 1, str(result))
    finally:
        if srv:
            srv.terminate()

main()
print('NEEDCHART RETRY TESTS', n, 'FAIL', len(fails))
sys.exit(1 if fails else 0)
