#!/usr/bin/env python3
"""Refresh the current month's recap page (recap/YYYY-MM/index.html) and its card in recap/months.js
from history.json, using FINAL closes only (dates listed in btc_provisional are ignored).

- Only the month of the newest final close is written. Completed months are never rewritten
  (the one exception: when a new month starts, the previous page's "All recaps ->" link becomes "<Month> 2026 ->").
- The month's page is "month to date" until its last NYSE trading day has a final close; then it is finalized.
- Idempotent: if nothing changes, nothing is written. Writes go to *.tmp, are validated, then moved into place.
- Exit 0 = ok (changed or not), exit 1 = validation failed (nothing written).

usage: recap_gen.py [--history PATH_OR_URL] [--repo DIR] [--dry-run]
"""
import argparse, calendar, datetime as dt, json, os, re, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recap_lib import SL, ledger as _ledger

HOL = {"2026-01-01","2026-01-19","2026-02-16","2026-04-03","2026-05-25","2026-06-19","2026-07-03","2026-09-07","2026-11-26","2026-12-25",
       "2027-01-01","2027-01-18","2027-02-15","2027-03-26","2027-05-31","2027-06-18","2027-07-05","2027-09-06","2027-11-25","2027-12-24"}
BASE = '2025-12-31'
URL = 'https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/history.json'

def load(src):
    if re.match(r'https?://', src):
        r = urllib.request.Request(src + ('&' if '?' in src else '?') + 't=%d' % dt.datetime.now().timestamp(), headers={'User-Agent': 'paperstreet-recap'})
        return json.load(urllib.request.urlopen(r, timeout=30))
    return json.load(open(src))

def trading(d): return d.weekday() < 5 and d.isoformat() not in HOL
def next_trading(d):
    d += dt.timedelta(days=1)
    while not trading(d): d += dt.timedelta(days=1)
    return d
nice = lambda d: dt.date.fromisoformat(d).strftime('%b %-d')
nicey = lambda d: dt.date.fromisoformat(d).strftime('%b %-d, %Y')
pc = lambda a, b: (b / a - 1) * 100

def ledger(C, D, strc): return _ledger(C, D, strc)

def sub1(s, pat, rep, flags=0):
    s2, n = re.subn(pat, lambda m: rep, s, count=1, flags=flags)
    if n != 1: raise ValueError('pattern not found: ' + pat[:60])
    return s2

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--history', default=URL); ap.add_argument('--repo', default='.'); ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(); os.chdir(a.repo)
    H = load(a.history); prov = set(H.get('btc_provisional') or [])
    C = {d: v for d, v in H['closes'].items() if d not in prov}; D = sorted(C); LASTF = D[-1]
    m = LASTF[:7]; y, mo = map(int, m.split('-')); full = calendar.month_name[mo]
    pfile = f'recap/{m}/index.html'
    final = next_trading(dt.date.fromisoformat(LASTF)).month != mo
    prev_m = (dt.date(y, mo, 1) - dt.timedelta(days=1)).strftime('%Y-%m')
    if os.path.exists(pfile):
        cur = open(pfile).read()
        if 'month to date' not in cur.split('</title>')[0]:
            print(f'{m} already finalized; nothing to do'); return 0
        mme = re.search(r"const ME='([\d-]+)'", cur).group(1)
        if mme > LASTF:
            print(f'{m} page is through {mme}, which is not a final close yet; rebuilding it on the newest final close {LASTF}')
        src = cur; new_month = False
    else:
        src = open(f'recap/{prev_m}/index.html').read(); new_month = True
    # data
    ledjs = open('assets/js/ledger.js').read()
    strc = [(x, z, float(w)) for _, x, z, w in re.findall(r"\['(\d{4}-\d\d-\d\d)',\s*'(\d{4}-\d\d-\d\d)',\s*'(\d{4}-\d\d-\d\d)',\s*([\d.]+)\]", ledjs)]
    if not strc:  # fallback: page's own ledger constants
        strc = [(x, z, float(w)) for x, z, w in re.findall(r"\['(\d{4}-\d\d-\d\d)','(\d{4}-\d\d-\d\d)',([\d.]+)\]", src)]
    VAL, EV = ledger(C, D, strc)
    ME = LASTF; pm_cal = (dt.date(y, mo, 1) - dt.timedelta(days=1)).isoformat(); PM = max(d for d in D if d <= pm_cal)
    B = {k: v for k, v in json.load(open('assets/data/btc-daily.json'))['d']}
    for d in D:
        if d not in B: B[d] = C[d]['BTC']
    bdays = sorted(k for k in B if k.startswith(m) and k <= (f'{m}-{calendar.monthrange(y, mo)[1]:02d}' if final else ME))
    bopen = max(k for k in B if k <= pm_cal); bo, bc = B[bopen], B[bdays[-1]]; hi = max(bdays, key=B.get); lo = min(bdays, key=B.get); chg = pc(bo, bc)
    ndays = (dt.date.fromisoformat(bdays[-1]) - dt.date(y, mo, 1)).days + 1
    title = f'{full} {y}' + ('' if final else f' (month to date, through {nicey(ME)})')
    s = src
    s = sub1(s, r'<title>[^<]*</title>', f'<title>{title} Recap · Paperstreet BTC</title>')
    s = sub1(s, r'<h1>[^<]*</h1>', f'<h1>{title} recap</h1>')
    s = sub1(s, r'(<p class="sub">)How the four sleeves did in [A-Za-z]+ against spot BTC, (?:latest|month-end) close [A-Za-z]+ \d+, \d{4}\.',
             f'<p class="sub">How the four sleeves did in {full} against spot BTC, {"month-end" if final else "latest"} close {nicey(ME)}.')
    days_txt = (f'all {ndays} calendar days{"" if final else " so far"} incl. weekends' if len(bdays) == ndays
                else f'{len(bdays)} daily closes; weekend closes after {nice(max(k for k in B if k <= ME and k in dict(json.load(open("assets/data/btc-daily.json"))["d"])))} not yet in the site history')
    card = ('<section><h2>Bitcoin in %s</h2><div class="card"><div style="overflow-x:auto"><table class="btcm">'
            '<tr><th>Open (%s close)</th><th>Close (%s)</th><th>Change</th><th>High close (in %s)</th><th>Low close (in %s)</th></tr>'
            '<tr><td>$%s</td><td>$%s</td><td class="%s">%+.2f%%</td><td>$%s · %s</td><td>$%s · %s</td></tr></table></div>'
            '<p class="note">BTC-USD daily closes (UTC day, %s) from the site\'s BTC history (Yahoo Finance). High/low are the highest and lowest daily closes, not intraday extremes.%s</p></div></section>\n') % (
        full + ('' if final else ' (to date)'), nicey(bopen) if mo == 1 else nice(bopen), nice(bdays[-1]), full, full, f'{bo:,.2f}', f'{bc:,.2f}', 'pos' if chg >= 0 else 'neg', chg,
        f'{B[hi]:,.2f}', nice(hi), f'{B[lo]:,.2f}', nice(lo), days_txt, '' if final else f' Static snapshot through {nicey(bdays[-1])}; the month is not complete.')
    s = sub1(s, r'<section><h2>Bitcoin in .*?</section>\n(?=<section><h2>Sleeves vs spot BTC</h2>)', card, re.S)
    s = sub1(s, r'<p class="note" style="margin-bottom:12px">Month = [^<]*',
             f'<p class="note" style="margin-bottom:12px">Month = {nicey(PM) if PM < "2026-01-01" else nice(PM)} → {nice(ME)} close. YTD = Dec 31, 2025 → {nice(ME)} close.')
    s = sub1(s, r'STRC dividends paid in [A-Za-z]+(?: \(to date\))?', f'STRC dividends paid in {full}' + ('' if final else ' (to date)'))
    s = re.sub(r'<span>[A-Z][a-z]+(?: MTD)?</span>', f'<span>{full}{"" if final else " MTD"}</span>', s)
    s = sub1(s, r'through \d{4}-\d\d-\d\d; live BTC', f'through {ME}; live BTC')
    cl = {d: {k: C[d][k] for k in ['BTC', 'MSTR', 'STRC', 'TSLA', 'PLTR', 'GLD']} for d in D}
    s = sub1(s, r'const CL=\{.*?\}\},', 'const CL=' + json.dumps(cl, separators=(',', ':')) + ',', re.S)
    s = sub1(s, r"const ME='[\d-]+',PM='[\d-]+';", f"const ME='{ME}',PM='{PM}';")
    s = sub1(s, r"e\.payD>='\d{4}-\d\d-01'", f"e.payD>='{m}-01'")
    pfull = calendar.month_name[int(prev_m[5:])]
    s = sub1(s, r'<nav class="pn"[^>]*>.*?</nav>', f'<nav class="pn" style="display:flex;justify-content:space-between;gap:12px;margin:24px 0 8px;font-weight:600"><a href="../{prev_m}/index.html">← {pfull} {prev_m[:4]}</a><a href="../index.html">All recaps →</a></nav>', re.S)
    # months.js card
    best = None; sl = []
    for k, (n, _, _) in SL.items():
        mm, yy = pc(VAL[k][PM], VAL[k][ME]), pc(VAL[k][BASE], VAL[k][ME]); sl.append((n, mm, yy))
        if best is None or mm > best[1]: best = (n, mm)
    ent = "  {slug:'%s',title:'%s',blurb:'%s led with %+.2f%% for the %s; sleeves vs spot BTC, STRC dividends.',btc:{open:%.2f,close:%.2f,chg:%.2f,hi:%.2f,hid:'%s',lo:%.2f,lod:'%s'},sl:[%s]}" % (
        m, title, best[0], best[1], 'month' if final else 'month to date', bo, bc, chg, B[hi], hi, B[lo], lo, ','.join("{n:'%s',m:%.2f,y:%.2f}" % x for x in sl))
    mj = open('recap/months.js').read()
    if re.search(r"^  \{slug:'%s'.*$" % m, mj, re.M): mj2 = re.sub(r"^  \{slug:'%s'.*?(?=,?\n)" % m, lambda _: ent, mj, count=1, flags=re.M)
    else: mj2 = mj.replace('window.RECAP_MONTHS=[\n', 'window.RECAP_MONTHS=[\n' + ent + ',\n', 1)
    # validate
    err = []
    if 'pollPX(' not in s or 'assets/js/et.js' not in s: err.append('live ticker / et.js missing')
    if 'NaN' in s or 'undefined' in s.split('<script>')[0] or 'NaN' in ent: err.append('NaN/undefined in output')
    if not (0.5 * len(src) < len(s) < 2 * len(src)): err.append('page size out of range')
    if f"const ME='{ME}'" not in s or ME != LASTF: err.append('through date mismatch')
    if mj2.count('{slug:') != mj.count('{slug:') + (1 if new_month else 0): err.append('months.js entry count wrong')
    for txt in (s,):
        if txt.count('<html') != 1 or txt.count('</html>') != 1: err.append('html not well-formed')
    if err: print('VALIDATION FAILED:', err); return 1
    writes = {}
    if s != (open(pfile).read() if os.path.exists(pfile) else None): writes[pfile] = s
    if mj2 != mj: writes['recap/months.js'] = mj2
    if new_month:  # link the previous page forward (nav only)
        pp = f'recap/{prev_m}/index.html'; ps = open(pp).read()
        ps2 = ps.replace('<a href="../index.html">All recaps →</a></nav>', f'<a href="../{m}/index.html">{full} {y} →</a></nav>', 1)
        if ps2 != ps: writes[pp] = ps2
    if not writes: print(f'{m}: up to date (through {ME}{", final" if final else ""})'); return 0
    if a.dry_run: print('would write', list(writes)); return 0
    for f, txt in writes.items():
        os.makedirs(os.path.dirname(f), exist_ok=True); open(f + '.tmp', 'w').write(txt)
    for f in writes: os.replace(f + '.tmp', f)
    print(f'{m}: wrote {list(writes)} (through {ME}{", FINAL" if final else ", month to date"}; best {best[0]} {best[1]:+.2f}%)')
    return 0

if __name__ == '__main__':
    try: sys.exit(main())
    except Exception as e:
        print('RECAP GENERATION FAILED (nothing written):', type(e).__name__, e); sys.exit(1)
