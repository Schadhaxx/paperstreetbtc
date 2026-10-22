#!/usr/bin/env python3
"""Static recap checks (no browser). Each recap is validated against the 'through' date the page itself states.
usage: python3 tests/test_recap.py [--history PATH_OR_URL] [--repo DIR]   exit 0 = all pass"""
import argparse, json, os, re, sys, calendar, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from recap_lib import SL, ledger, strc_from_ledger, expected_months, page_dates, pc, fetch_json
ap = argparse.ArgumentParser(); ap.add_argument('--history', default='https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/history.json'); ap.add_argument('--repo', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
a = ap.parse_args(); os.chdir(a.repo)
H = fetch_json(a.history) if a.history.startswith('http') else json.load(open(a.history))
C = H['closes']; D = sorted(C); prov = H.get('btc_provisional') or []
VAL, EV = ledger(C, D, strc_from_ledger(open('assets/js/ledger.js').read()))
BD = dict(json.load(open('assets/data/btc-daily.json'))['d'])
for d in D: BD.setdefault(d, C[d]['BTC'])
num = lambda s: float(re.sub(r'[^\d.\-]', '', s.replace('−', '-')))
R = []
def chk(name, ok, detail=''): R.append((name, bool(ok), detail))
months = expected_months(C, prov)
mj = open('recap/months.js').read()
ents = {m: e for m, e in re.findall(r"^  (\{slug:'(\d{4}-\d\d)'.*?\})(?=,?\n)", mj, re.M) and [(x[1], x[0]) for x in re.findall(r"^  (\{slug:'(\d{4}-\d\d)'.*?\})(?=,?\n)", mj, re.M)]}
chk('months.js lists exactly the expected months %s..%s (%d)' % (months[0], months[-1], len(months)), sorted(ents) == months, sorted(ents))
for m in months:
    f = f'recap/{m}/index.html'
    if not os.path.exists(f): chk(f'{m} page exists', False); continue
    s = open(f).read(); ME, PM, mtd = page_dates(s)
    y, mo = map(int, m.split('-')); mend = f'{m}-{calendar.monthrange(y, mo)[1]:02d}'
    pend = (dt.date(y, mo, 1) - dt.timedelta(days=1)).isoformat()
    chk(f'{m} through date {ME} is a history close', ME in C)
    chk(f'{m} through date inside month', ME.startswith(m))
    if mtd: chk(f'{m} only the newest month may be month-to-date', m == months[-1])
    else: chk(f'{m} completed month ends on last session {max(d for d in D if d <= mend)}', ME == max(d for d in D if d <= mend))
    if mtd: chk(f'{m} title states through {ME}', dt.date.fromisoformat(ME).strftime('%b %-d, %Y') in s.split('</title>')[0])
    chk(f'{m} PM is last session of previous month', PM == max(d for d in D if d <= pend))
    cl = json.loads(re.search(r'const CL=(\{.*?\}\}),', s, re.S).group(1))
    bad = [d for d in D if d <= ME and (d not in cl or any(abs(cl[d][k] - C[d][k]) > 1e-6 for k in cl[d]))]
    chk(f'{m} embedded closes match history through {ME}', not bad, bad[:3])
    cells = re.search(r'<table class="btcm">.*?</tr><tr>(.*?)</tr>', s).group(1)
    td = re.findall(r'<td[^>]*>(.*?)</td>', cells)
    days = sorted(d for d in BD if d.startswith(m) and (d <= ME if mtd else d <= mend))
    exp = [BD[pend], BD[days[-1]], pc(BD[pend], BD[days[-1]]), max(BD[d] for d in days), min(BD[d] for d in days)]
    got = [num(td[0]), num(td[1]), num(td[2]), num(td[3].split('·')[0]), num(td[4].split('·')[0])]
    for lab, e, g in zip(['open', 'close', 'change %', 'high', 'low'], exp, got): chk(f'{m} BTC table {lab}', abs(e - g) <= 0.006, (e, g))
    e = ents.get(m, '')
    for k, (n, _, _) in SL.items():
        mm = re.search(r"\{n:'%s',m:(-?[\d.]+),y:(-?[\d.]+)\}" % re.escape(n), e)
        chk(f'{m} index card {n} month %', mm and abs(float(mm.group(1)) - pc(VAL[k][PM], VAL[k][ME])) <= 0.006)
        chk(f'{m} index card {n} YTD %', mm and abs(float(mm.group(2)) - pc(VAL[k]['2025-12-31'], VAL[k][ME])) <= 0.006)
    chk(f'{m} no NaN/undefined', 'NaN' not in s and 'NaN' not in e)
fails = [r for r in R if not r[1]]
for r in R: print('PASS' if r[1] else 'FAIL', r[0], '' if r[1] else r[2])
print('RECAP STATIC CHECKS', len(R), 'FAIL', len(fails))
sys.exit(1 if fails else 0)
