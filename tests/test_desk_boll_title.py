#!/usr/bin/env python3
"""Desk Bollinger title follows each symbol's own mode (21 Nov 2026).

Bug (found by Pepper): the dialog title suffix " · daily Bollinger" carried
over to the next symbol. Set Gold to Daily, close, open AAPL: AAPL's switch
said Weekly but its title still said "daily Bollinger".

Serves this checkout on 127.0.0.1 and drives the real screener modal.
Run: python3 tests/test_desk_boll_title.py
"""
import os, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CHROME = os.environ.get('CHROME_PATH', '/usr/bin/google-chrome')
s = socket.socket(); s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]; s.close()
fails = 0
def chk(name, ok, info=''):
    global fails
    if not ok: fails += 1
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + str(info)) if info else ''))

def title(p): return p.evaluate("() => document.getElementById('ind-title').textContent")
def pressed(p, m): return p.evaluate("m => { const b = document.querySelector('[data-bollmode=\"' + m + '\"]'); return b && b.getAttribute('aria-pressed'); }", m)
def close(p):
    p.keyboard.press('Escape'); p.wait_for_timeout(300)
    if p.evaluate("() => document.getElementById('ind-modal').classList.contains('open')"):
        p.evaluate("() => { const b = document.querySelector('#ind-modal [data-close], #ind-close, #ind-modal .close'); if (b) b.click(); }")
        p.wait_for_timeout(300)

srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'],
                       cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(1.0)
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME, args=['--no-sandbox', '--disable-gpu'])
        p = b.new_page(viewport={'width': 1280, 'height': 900})
        errs = []; p.on('pageerror', lambda e: errs.append(str(e)))
        p.goto(f'http://127.0.0.1:{PORT}/screener.html', wait_until='networkidle')
        p.wait_for_timeout(1500)
        # Gold: Bollinger on, Daily
        p.click('.tile[data-symbol="GOLD"]'); p.wait_for_selector('#ind-modal.open', timeout=8000); p.wait_for_timeout(1000)
        p.click('[data-enh="boll"]'); p.wait_for_timeout(400)
        p.click('[data-bollmode="daily"]'); p.wait_for_timeout(1200)
        t = title(p)
        chk('Gold on Daily: title says daily Bollinger', 'daily Bollinger' in t, t)
        chk('Gold on Daily: Daily pressed', pressed(p, 'daily') == 'true')
        close(p)
        # AAPL: must start weekly, title must not carry Gold's suffix
        p.click('[data-symbol="AAPL"]'); p.wait_for_selector('#ind-modal.open', timeout=8000); p.wait_for_timeout(1000)
        t = title(p)
        chk('AAPL after Gold-daily: Weekly pressed', pressed(p, 'weekly') == 'true')
        chk('AAPL after Gold-daily: title has no daily Bollinger', 'daily Bollinger' not in t, t)
        chk('AAPL title is AAPL\'s own', 'AAPL' in t, t)
        # AAPL's own Daily still adds the suffix, Weekly removes it
        if p.evaluate("() => { const s = document.getElementById('ind-boll-mode'); return !!s && getComputedStyle(s).display !== 'none'; }"):
            p.click('[data-bollmode="daily"]'); p.wait_for_timeout(1200)
            chk('AAPL on Daily: title says daily Bollinger', 'daily Bollinger' in title(p), title(p))
            p.click('[data-bollmode="weekly"]'); p.wait_for_timeout(400)
            chk('AAPL back on Weekly: no suffix', 'daily Bollinger' not in title(p), title(p))
        chk('no page errors', not errs, errs[:2])
        b.close()
finally:
    srv.terminate()
print(('FAILED %d' % fails) if fails else 'ALL PASS')
sys.exit(1 if fails else 0)
