#!/usr/bin/env python3
"""needChart: failed Chart.js inject removes the tag and resets the promise so retry is fresh."""
import re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

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
    bool(re.search(r's\.onerror=function\(\)\{[\s\S]*?removeChild\(s\)[\s\S]*?chartP=null', PANEL)))
chk('needChart strips leftover umd tags before reinject',
    'querySelectorAll(\'script[src*="chart.umd.min.js"]\')' in PANEL and 'el.remove()' in PANEL)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--disable-gpu'])
    page = browser.new_page()
    page.set_content('<!doctype html><html><body></body></html>')
    # Simulate without real network: exercise remove-tag + chartP=null + second inject
    result = page.evaluate("""async () => {
      let chartP = null, attempt = 0;
      const loads = [];
      function needChart(failOnce) {
        if (window.Chart) return Promise.resolve('had');
        if (chartP) return chartP;
        chartP = new Promise(function (ok, no) {
          document.querySelectorAll('script[src*=\"chart.umd.min.js\"]').forEach(function (el) {
            if (!window.Chart) el.remove();
          });
          attempt += 1;
          const s = document.createElement('script');
          s.src = 'chart.umd.min.js?try=' + attempt;
          loads.push(s.src);
          document.head.appendChild(s);
          // Deterministic outcome (no network): first call fails, second succeeds
          Promise.resolve().then(function () {
            if (failOnce && attempt === 1) {
              if (s.parentNode) s.parentNode.removeChild(s);
              chartP = null;
              no(new Error('chart'));
            } else {
              window.Chart = function () {};
              ok('loaded-' + attempt);
            }
          });
        });
        return chartP;
      }
      let firstErr = null;
      try { await needChart(true); } catch (e) { firstErr = String(e.message || e); }
      const tagsAfterFail = document.querySelectorAll('script[src*=\"chart.umd.min.js\"]').length;
      const second = await needChart(false);
      return {
        firstErr, tagsAfterFail, second, loads: loads.slice(),
        hasChart: typeof window.Chart === 'function',
        // Also verify attaching to a leftover failed tag would hang — we removed it
        leftover: document.querySelectorAll('script[src*=\"chart.umd.min.js\"]').length
      };
    }""")
    browser.close()

chk('first attempt fails', result['firstErr'] == 'chart', str(result.get('firstErr')))
chk('failed script tag removed', result['tagsAfterFail'] == 0, str(result.get('tagsAfterFail')))
chk('retry loads fresh and succeeds', result['second'] == 'loaded-2', str(result))
chk('two distinct inject attempts', len(result['loads']) == 2 and result['loads'][0] != result['loads'][1], str(result['loads']))
chk('Chart present after retry', result['hasChart'])
print('NEEDCHART RETRY TESTS', n, 'FAIL', len(fails))
sys.exit(1 if fails else 0)
