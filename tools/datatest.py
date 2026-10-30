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
# DIV-NOV (daily STRC from Nov 1 2026, Oct 29 8-K): the three dividend lists, checked as served
R = []
LJ = strc_from_ledger(get(BASE + '/assets/js/ledger.js'))
pair = lambda t: [(x, z, float(w)) for x, z, w in re.findall(r"\['(\d{4}-\d\d-\d\d)','(\d{4}-\d\d-\d\d)',([\d.]+)\]", t)]
CJ = pair(get(BASE + '/assets/js/compare.js')); RJ = pair(get(BASE + '/recap/2026-10/'))
nov = [e for e in LJ if e[0].startswith('2026-11')]
R.append(('ledger', 'DIV-NOV', 'ledger.js has 30 November STRC records', 30, len(nov), 0))
R.append(('ledger', 'DIV-NOV', 'November $/share sums to $1.00', 1.0, sum(e[2] for e in nov), 1e-5))
R.append(('ledger', 'DIV-NOV', 'compare.js list == ledger.js list (ex, pay, $)', 1, 1 if CJ == LJ else 0, 0))
R.append(('ledger', 'DIV-NOV', 'recap/2026-10 inline list == ledger.js list', 1, 1 if RJ == LJ else 0, 0))
R.append(('ledger', 'DIV-NOV', 'no cancelled Nov 15 $0.50 entry', 0, sum(1 for e in LJ if e[1] == '2026-11-15' and abs(e[2] - 0.5) < 1e-9), 0))
# STRC "Business Day" non-weekend closures used for November pay dates. ONE-LINE CHANGE POINT.
# Business Day = not Sat/Sun and not a day the NY Fed is closed (STRC CoD, Ex 3.2 to the Oct 29 2026 8-K). Nov 11 = Veterans Day, NY Fed holiday
# (Sunil, Oct 30: "Use Nov 12 for the Nov 10 dividend"); Nov 26 = Thanksgiving.
DIV_PAY_HOLIDAYS = {'2026-11-11', '2026-11-26'}
def _next_bd(d):
    x = dt.date.fromisoformat(d) + dt.timedelta(days=1)
    while x.weekday() >= 5 or x.isoformat() in DIV_PAY_HOLIDAYS: x += dt.timedelta(days=1)
    return x.isoformat()
_days = ['2026-11-%02d' % i for i in range(1, 31)]
for _lab, _lst in [('ledger.js', [(x, z) for x, z, _ in LJ]), ('compare.js', [(x, z) for x, z, _ in CJ]), ('recap/2026-10', [(x, z) for x, z, _ in RJ])]:
    _n = [(x, z) for x, z in _lst if x.startswith('2026-11')]
    R.append(('ledger', 'DIV-NOV', f'{_lab}: November ex/record dates are exactly Nov 1..30, once each', 1, 1 if sorted(x for x, _ in _n) == _days else 0, 0))
    R.append(('ledger', 'DIV-NOV', f'{_lab}: every November pay date = next Business Day (holidays {sorted(DIV_PAY_HOLIDAYS)})', 0, sum(1 for x, z in _n if z != _next_bd(x)), 0))
_C = {d: v for d, v in C.items() if d <= '2026-10-30'}; _x = dict(_C[max(_C)]); _C['2026-11-02'] = _x; _C['2026-11-03'] = _x   # synthetic flat closes: tests the dates, not prices
_, _E = ledger(_C, sorted(_C), LJ)
_b = [e for e in _E if e[0] == 'berkshire' and e[2] == '2026-11-02']
R.append(('ledger', 'DIV-NOV', 'Nov 1 record + Oct 15 record both bought at the Nov 2 close (Berkshire)', 2, len(_b), 0))
R.append(('ledger', 'DIV-NOV', 'Oct 15 record still pays $0.50/sh at the Nov 2 close', 1, 1 if any(abs(e[3] / (20000 / C['2025-12-31']['STRC']) - 0.5) < 1e-9 for e in _b) else 0, 0))
NM = {SL[k][0]: k for k in SL}
S = {n: VAL[k] for n, k in NM.items()}; S['Spot BTC'] = {d: C[d]['BTC'] for d in D}
num = lambda s: float(re.sub(r'[^\d.\-]', '', s.replace('−', '-'))) if s and re.search(r'\d', s) else None
months = expected_months(C, H.get('btc_provisional'))
fails = []
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
        R += [(m, 'divs', 'rows (one per sleeve per pay date)', len({(e[0], e[2]) for e in ev}), len(rows), 0), (m, 'divs', 'cash (sum of the page\'s cent-rounded rows)', sum(round(sum(e[3] for e in ev if (e[0], e[2]) == g), 2) for g in {(e[0], e[2]) for e in ev}), sum(num(r[4]) for r in rows), 0.011)]
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
    # CR-005: Custom-page extra contributions are bought at the trading day's OPEN (assets/data/opens.json), weekend/holiday
    # dates held to the next trading day's open, STRC dividends on them reinvested at the pay day's open; valued at the latest close.
    try: OPN = fetch_json(BASE + '/assets/data/opens.json')['o']
    except Exception as e: OPN = {}; fails.append(('custom', 'CR-005 opens.json unreadable', str(e)[:60]))
    CJS = get(BASE + '/assets/js/compare.js')
    CST = [(x, z, float(w)) for x, z, w in re.findall(r"\['(\d{4}-\d\d-\d\d)','(\d{4}-\d\d-\d\d)',([\d.]+)\]", CJS)]
    LST = D[-1]; fo = lambda d: next((x for x in D if x >= d), None)
    def lump(k, d, c, px):
        w, dv = SL[k][1], SL[k][2]; h = {a: c * w[a] / px(d, a) for a in w}; rec = []
        evs = [dict(ex=fo(ex), pay=fo(pay), amt=amt) for ex, pay, amt in CST if fo(ex) and fo(ex) > d and fo(ex) <= LST]
        for x in D:
            if x <= d: continue
            for e in evs:
                if e['ex'] == x: e['cash'] = h['STRC'] * e['amt']; rec.append(e)
            keep = []
            for e in rec:
                if e['pay'] and e['pay'] == x:
                    for a in dv: h[a] = h.get(a, 0) + e['cash'] * dv[a] / px(x, a)
                else: keep.append(e)
            rec = keep
        return sum(e['cash'] for e in rec) + sum(h[a] * C[LST][a] for a in h)
    po = lambda d, a: OPN.get(d, {}).get(a, C[d][a]); pcl = lambda d, a: C[d][a]
    pg.goto(BASE + '/custom/'); pg.wait_for_timeout(6000)
    for k, dd, why in [('berkshire', '2026-10-21', 'weekday'), ('berkshire', '2026-10-24', 'Saturday -> Mon open'), ('hf', '2026-01-19', 'holiday (MLK) -> next open'),
                       ('saylor', '2026-01-05', 'dividends reinvested at pay-day open'), ('hf', '2026-03-02', 'dividends to BTC+MSTR at open')]:
        bd = fo(dd)
        note = pg.evaluate("""([k,dd])=>{const s=document.getElementById('pvS');s.value=k;s.dispatchEvent(new Event('input'));const w=document.getElementById('pvX');w.innerHTML='';
          document.getElementById('pvXAdd').click();const r=w.querySelector('.pvx-row');const a=r.querySelector('.pvx-a'),d=r.querySelector('.pvx-d');a.value='1000';d.value=dd;
          d.dispatchEvent(new Event('input'));return r.querySelector('.pvx-n').textContent}""", [k, dd])
        mw = re.search(r'Worth \$([\d,]+) today', note); got = float(mw.group(1).replace(',', '')) if mw else None
        R.append(('custom', f'CR-005 {k} {dd}', f'lump value at {bd} open ({why})', lump(k, bd, 1000, po), got, 1))
        R.append(('custom', f'CR-005 {k} {dd}', 'test is sensitive: open vs close value differ > $1', 1, 1 if abs(lump(k, bd, 1000, po) - lump(k, bd, 1000, pcl)) > 1 else 0, 0))
        R.append(('custom', f'CR-005 {k} {dd}', f'note says bought at the {bd} open, no close wording', 1, 1 if (bd + ' open') in note.replace("open, " + bd, bd + ' open') and not re.search(r'\bclose\b', note) else 0, 0))
    pg.evaluate("document.getElementById('pvX').innerHTML=''")
    R.append(('custom', 'CR-005', 'contributions note says each at its trading day open', 1, 1 if "trading day's open" in pg.inner_text('.pvx .note') and not re.search(r'\bclose\b', pg.inner_text('.pvx .note')) else 0, 0))
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
