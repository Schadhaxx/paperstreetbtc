#!/usr/bin/env python3
"""PaperStreet live data test (browser). Checks every recap page's sleeve cards, dividends and BTC table, and the
recap index, against history.json, using the 'through' date each page states (month-to-date pages included).
usage: python3 tools/datatest.py [BASE_URL]   (needs: pip install playwright; a Chromium/Chrome)"""
import json, re, sys, os, calendar, datetime as dt, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recap_lib import SL, ledger, strc_from_ledger, expected_months, page_dates, pc, fetch_json
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else 'https://paperstreetbtc.com').rstrip('/')
def fresh_history():  # CR-007: bypass the raw.githubusercontent CDN cache (API read first; if rate-limited, cache-busted no-cache raw read)
    for u, h in [('https://api.github.com/repos/Schadhaxx/paperstreetbtc/contents/history.json?ref=data', {'Accept': 'application/vnd.github.raw'}),
                 ('https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/history.json?t=%d' % dt.datetime.now().timestamp(), {})]:
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'paperstreet-test', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache', **h}), timeout=30))
        except urllib.error.HTTPError: continue
    raise SystemExit('history.json unavailable')
H = json.load(open(os.environ['DT_HISTORY'])) if os.environ.get('DT_HISTORY') else fresh_history(); C = H['closes']; D = sorted(C)  # CR-007: API read bypasses raw.githubusercontent CDN cache
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
    pg.goto(BASE + '/'); pg.wait_for_timeout(6000)  # CR-009: Pulse move must equal the tracker card 'since <prior close>' move
    pv = pg.evaluate("[...document.querySelectorAll('#pulseGrid .pulse-card')].map(c=>[c.querySelector('.pulse-name').textContent,(c.querySelector('.pulse-chg span')||c.querySelector('.pulse-chg')).textContent]  /* % span only: label 'since Oct 23, 2026' has digits */)")
    cv = dict(pg.evaluate("[...document.querySelectorAll('.pf-card')].map(c=>[c.querySelector('.pf-name').textContent,c.querySelector('.pf-sub span').textContent])"))
    for n, t in pv: R.append(('home', n, 'Pulse % = card since-close %', num(cv.get(n)), num(t), 0))
    R.append(('home', 'pulse', 'note says move = since daily close', 1, 1 if 'since daily close' in pg.inner_text('#pulseNote') and '24h' not in pg.inner_text('#pulseNote') else 0, 0))
    pg.goto(BASE + '/recap/'); pg.wait_for_timeout(1200)
    R.append(('index', 'cards', 'count (= months Jan..newest final close)', len(months), pg.evaluate("document.querySelectorAll('#list a.rc').length"), 0))
    # ET standard + fix 5 (added checks)
    for path in ['/', '/compare/', '/custom/', '/recap/', f'/recap/{months[-1]}/']:
        pg.goto(BASE + path); pg.wait_for_timeout(800)
        R.append((path, 'ET', 'et.js loaded (window.ET defined)', 1, 1 if pg.evaluate("!!(window.ET&&ET.today)") else 0, 0))
    pg.goto(BASE + '/'); pg.wait_for_timeout(6000)
    R.append(('home', 'btcTime', "BTC bar time ends with ' ET'", 1, 1 if pg.inner_text('#btcTime').strip().endswith(' ET') else 0, 0))
    same = pg.evaluate("(()=>{const c=document.querySelector('.pf-card');c.click();window.dispatchEvent(new CustomEvent('btcprice',{detail:{usd:12345,chg:0,src:'test',time:'x'}}));const n=document.querySelector('.pf-card[data-i=\"'+c.dataset.i+'\"]');return n===c&&c.isConnected&&c.classList.contains('open')})()")
    R.append(('home', 'cards', 'same card node + open state survive a live update', 1, 1 if same else 0, 0))
    b.close()
def tol(r):  # a revised upstream close must not fail the site: ~0.01% on values, 0.01 on %/price checks
    if isinstance(r[3], (int, float)) and 'value' in str(r[2]) or 'BTC table' in str(r[1]): return max(r[5], abs(r[3]) * 1e-4)
    return max(r[5], 0.01) if r[5] else r[5]
STRICT = os.environ.get('LENIENT') != '1'   # strict by default (after P6). LENIENT=1 allows ~0.01% revised-close drift and reports it as WARN
F = [r for r in R if r[4] is None or abs(r[3] - r[4]) > (r[5] if STRICT else tol(r))]
W = [r for r in R if r not in F and r[4] is not None and abs(r[3] - r[4]) > r[5]]
for r in W: print('WARN absorbed by revised-close tolerance (check revisions_ignored):', r)
if W:
    print('=' * 70); print(f'WARNINGS: {len(W)} value(s) differ beyond the strict tolerance but were accepted (LENIENT=1):')
    for r in W: print(f'  WARN {r[0]} {r[1]} {r[2]}: expected {r[3]:.6g}, page {r[4]:.6g}')
    print('=' * 70)
    if os.environ.get('GITHUB_STEP_SUMMARY'): open(os.environ['GITHUB_STEP_SUMMARY'], 'a').write(f'### :warning: datatest: {len(W)} WARN\n' + ''.join(f'- {r[0]} {r[1]} {r[2]}: {r[3]:.6g} vs {r[4]:.6g}\n' for r in W))
for r in F: print('FAIL', r)
print('CHECKS', len(R), 'FAIL', len(F) + len(fails), 'WARN', len(W), fails, 'reqfailed', sorted(set(bad)))
sys.exit(1 if F or fails else 0)
