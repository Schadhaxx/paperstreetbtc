"""Shared helpers for recap generation and tests (pure Python, no browser)."""
import json, re, datetime as dt, calendar, urllib.request
BASE_DATE = '2025-12-31'
SL = {'berkshire': ('Berkshire Killer', {'BTC': .4, 'STRC': .2, 'TSLA': .3, 'PLTR': .1}, {'BTC': 1}),
      'hodlr': ('Hodler Jam Sandwich', {'BTC': .7, 'STRC': .1, 'MSTR': .2}, {'BTC': 1}),
      'hf': ('Hedge Fund Killer', {'BTC': .55, 'MSTR': .35, 'STRC': .1}, {'BTC': .5, 'MSTR': .5}),
      'saylor': ('Saylor Moon', {'MSTR': .5, 'STRC': .5}, {'MSTR': 1})}
pc = lambda a, b: (b / a - 1) * 100
def fetch_json(u):
    r = urllib.request.Request(u + ('&' if '?' in u else '?') + 't=%d' % dt.datetime.now().timestamp(), headers={'User-Agent': 'paperstreet-test'})
    return json.load(urllib.request.urlopen(r, timeout=30))
def strc_from_ledger(js):
    return [(x, z, float(w)) for _, x, z, w in re.findall(r"\['(\d{4}-\d\d-\d\d)',\s*'(\d{4}-\d\d-\d\d)',\s*'(\d{4}-\d\d-\d\d)',\s*([\d.]+)\]", js)]
def ledger(C, D, strc):
    fo = lambda d: next((x for x in D if x >= d), None)
    VAL, EV = {}, []
    for k, (n, w, dv) in SL.items():
        h = {a: 100000 * w[a] / C[BASE_DATE][a] for a in w}; rec = []; v = {}
        evs = [dict(ex=fo(ex), pay=fo(pay), amt=amt) for ex, pay, amt in strc if fo(ex)]
        for d in D:
            for e in evs:
                if e['ex'] == d: e['cash'] = h['STRC'] * e['amt']; rec.append(e)
            keep = []
            for e in rec:
                if e['pay'] == d:
                    for a in dv: h[a] = h.get(a, 0) + e['cash'] * dv[a] / C[d][a]
                    EV.append((k, e['ex'], d, e['cash']))
                else: keep.append(e)
            rec = keep; v[d] = sum(e['cash'] for e in rec) + sum(h[a] * C[d][a] for a in h)
        VAL[k] = v
    return VAL, EV
def expected_months(C, prov):
    """Months Jan 2026 .. month of the newest FINAL close."""
    last = max(d for d in C if d not in set(prov or []))
    y, m = 2026, 1; out = []
    while f'{y}-{m:02d}' <= last[:7]:
        out.append(f'{y}-{m:02d}'); m += 1
        if m == 13: y, m = y + 1, 1
    return out
def page_dates(html):
    """(ME, PM, is_month_to_date) as stated by the page itself."""
    me, pm = re.search(r"const ME='([\d-]+)',PM='([\d-]+)'", html).groups()
    return me, pm, 'month to date' in html.split('</title>')[0]
