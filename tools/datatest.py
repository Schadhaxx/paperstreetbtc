#!/usr/bin/env python3
"""PaperStreet live data test (browser). Checks every recap page's sleeve cards, dividends and BTC table, and the
recap index, against history.json, using the 'through' date each page states (month-to-date pages included).
usage: python3 tools/datatest.py [BASE_URL]   (needs: pip install playwright; a Chromium/Chrome)"""
import json, re, sys, os, calendar, datetime as dt, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recap_lib import SL, ledger, strc_from_ledger, expected_months, page_dates, pc, fetch_json
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else 'https://paperstreetbtc.com').rstrip('/')
H = fetch_json('https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/history.json'); C = H['closes']; D = sorted(C)
BD = dict(fetch_json(BASE + '/assets/data/btc-daily.json')['d'])
for d in D: BD.setdefault(d, C[d]['BTC'])
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'paperstreet-test'}), timeout=30).read().decode()
VAL, EV = ledger(C, D, strc_from_ledger(get(BASE + '/assets/js/ledger.js')))
NM = {SL[k][0]: k for k in SL}
S = {n: VAL[k] for n, k in NM.items()}; S['Spot BTC'] = {d: C[d]['BTC'] for d in D}
num = lambda s: float(re.sub(r'[^\d.\-]', '', s.replace('−', '-'))) if s and re.search(r'\d', s) else None
months = expected_months(C, H.get('btc_provisional'))
R = []; fails = []
exe = next((p for p in ['/usr/bin/google-chrome', '/usr/bin/chromium'] if os.path.exists(p)), None)
with sync_playwright() as p:
    b = p.chromium.launch(**({'executable_path': exe} if exe else {})); pg = b.new_page(); bad = []
    pg.on('requestfailed', lambda r: bad.append(r.url[:70]))
    for m in months:
        html = get(BASE + f'/recap/{m}/?t={dt.datetime.now().timestamp():.0f}'); ME, PM, mtd = page_dates(html)
        y, mo = map(int, m.split('-')); mend = f'{m}-{calendar.monthrange(y, mo)[1]:02d}'; pend = (dt.date(y, mo, 1) - dt.timedelta(days=1)).isoformat()
        R.append((m, 'page', 'through date is a history close', 0, 0 if ME in C else 1, 0))
        pg.goto(BASE + f'/recap/{m}/'); pg.wait_for_timeout(1200)
        cards = pg.evaluate("[...document.querySelectorAll('#cards .card')].map(c=>[c.querySelector('h3').textContent,c.querySelector('.big').textContent,[...c.querySelectorAll('.row span')].map(s=>s.textContent)])")
        for h3, big, rows in cards:
            n = 'Spot BTC' if h3.startswith('Spot BTC') else h3
            if n not in S: fails.append((m, 'unknown card', h3)); continue
            v = S[n]
            R += [(m, n, 'value', v[ME], num(big), 1), (m, n, 'month %', pc(v[PM], v[ME]), num(rows[1]), 0.006), (m, n, 'YTD %', pc(v['2025-12-31'], v[ME]), num(rows[3]), 0.006)]
        rows = pg.evaluate("[...document.querySelectorAll('#divs tr')].slice(1).map(r=>[...r.children].map(c=>c.textContent))")
        ev = [e for e in EV if e[2] >= m + '-01' and e[2] <= ME]
        R += [(m, 'divs', 'rows', len(ev), len(rows), 0), (m, 'divs', 'cash', sum(e[3] for e in ev), sum(num(r[4]) for r in rows), 0.05)]
        cells = pg.evaluate("[...document.querySelectorAll('table.btcm tr:nth-child(2) td')].map(t=>t.textContent)")
        ds_ = sorted(d for d in BD if d.startswith(m) and (d <= ME if mtd else d <= mend))
        bo = BD[max(d for d in BD if d <= pend)]
        R += [(m, 'BTC table', 'open', bo, num(cells[0]), 0.006), (m, 'BTC table', 'close', BD[ds_[-1]], num(cells[1]), 0.006),
              (m, 'BTC table', 'high', max(BD[d] for d in ds_), num(cells[3].split('·')[0]), 0.006), (m, 'BTC table', 'low', min(BD[d] for d in ds_), num(cells[4].split('·')[0]), 0.006)]
    pg.goto(BASE + '/recap/'); pg.wait_for_timeout(1200)
    R.append(('index', 'cards', 'count (= months Jan..newest final close)', len(months), pg.evaluate("document.querySelectorAll('#list a.rc').length"), 0))
    b.close()
F = [r for r in R if r[4] is None or abs(r[3] - r[4]) > r[5]]
for r in F: print('FAIL', r)
print('CHECKS', len(R), 'FAIL', len(F) + len(fails), fails, 'reqfailed', sorted(set(bad)))
sys.exit(1 if F or fails else 0)
