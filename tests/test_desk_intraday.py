#!/usr/bin/env python3
"""tools/desk_intraday.py — offline fixtures. No network.

Covers: refresh-in-place (past weeks byte-identical), new-week append,
fail-closed on bad Yahoo/fixture data, BRK.B -> BRK-B, CADUSD = CADUSD=X
~0.709, the ET time gate (hours / holiday / early close, EST + EDT,
10 PM ET outside), tzdata fail-safe (missing/stale zone skips the run),
holiday/early-close list coverage (fails when a year is not covered),
the partial-failure rule (warn naming stale symbols; fail if > 3 fail),
Yahoo 429 (one 429 fails closed, two in a row abort), and
commit-only-on-change (no write when nothing changed, even at a later
--now).
"""
import copy, datetime as dt, io, json, os, shutil, subprocess, sys, tempfile
import urllib.error, urllib.request
from zoneinfo import ZoneInfo
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'tools'))
import desk_intraday as D
import stock_weekly as SW
import indicator_weekly as IW

n = f = 0
def chk(name, ok, info=''):
    global n, f
    n += 1
    f += (not ok)
    print(('PASS' if ok else 'FAIL'), name, '' if ok else info)

def run_cli(args):
    p = subprocess.run([sys.executable, os.path.join(R, 'tools/desk_intraday.py')] + args,
                       capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

def stock_doc(weeks, asof='2026-01-14', last='2026-01-14', prog=True):
    return {
        'source': 'Yahoo TSLA unadjusted daily OHLC', 'asOf': asof,
        'asOfLabel': '14 Jan 2026', 'unit': 'usd', 'basis': 'ytd',
        'baseClose': 449.72, 'baseSession': '2025-12-31', 'baseLabel': '31 Dec close',
        'lastSession': last,
        'inProgress': 'in progress, through last completed session 14 Jan 2026 — week not finished' if prog else None,
        'note': ('Weekly candles, UTC Monday-Sunday weeks, YTD 2026. First week is partial: 1 trading day '
                 '(2 Jan 2026), week starting Mon 29 Dec 2025. The 31 Dec 2025 close is the baseline, not a candle. '
                 'Latest week is in progress as of 14 Jan 2026. Dated snapshot shipped with the screener — not a live quote.'),
        'weeks': weeks,
    }

def wk(mon, days, o, h, l, c, vol=None):
    sun = dt.date.fromisoformat(mon) + dt.timedelta(days=6)
    w = {'monday': mon, 'sunday': sun.isoformat(),
         'label': f"{SW.dlabel(dt.date.fromisoformat(mon))} \u2013 {SW.dlabel(sun)}",
         'days': days, 'open': o, 'high': h, 'low': l, 'close': c}
    if vol is not None:
        w['volume'] = vol
    return w

def bar(date, o, h, l, c, vol=None):
    r = {'date': date, 'open': o, 'high': h, 'low': l, 'close': c}
    if vol is not None:
        r['volume'] = vol
    return r

# Fixture bars for the week of Mon 12 Jan 2026 (Mon-Thu), TSLA.
WEEK_BARS = [
    bar('2026-01-12', 453.00, 455.00, 451.00, 454.00, 1000),
    bar('2026-01-13', 454.00, 456.00, 452.00, 455.00, 1100),
    bar('2026-01-14', 455.00, 457.00, 453.00, 456.00, 1200),
    bar('2026-01-15', 456.00, 458.00, 454.00, 457.00, 1300),
]
# Recomputed candle from WEEK_BARS: open 453, high 458, low 451, close 457, days 4, volume 4600.

# --- (a) refresh-in-place: only the current week changes, past weeks byte-identical ---
td = tempfile.mkdtemp(prefix='di-')
try:
    past = wk('2026-01-05', 5, 453.00, 462.50, 449.80, 460.50, 5000)
    cur = wk('2026-01-12', 4, 453.00, 462.50, 449.80, 455.00, 4000)
    doc = stock_doc([past, cur])
    open(os.path.join(td, 'stock-weekly-TSLA.json'), 'w').write(json.dumps(doc, indent=2) + '\n')
    fx = {'now': '2026-01-15T12:00:00-05:00', 'stocks': {'TSLA': WEEK_BARS}}
    fxp = os.path.join(td, 'fx.json'); json.dump(fx, open(fxp, 'w'))
    code, out, err = run_cli(['--fixture', fxp, '--out-dir', td, '--symbol', 'TSLA'])
    chk('(a) refresh CLI exit 0', code == 0, err)
    new = json.load(open(os.path.join(td, 'stock-weekly-TSLA.json')))
    chk('(a) past week byte-identical', json.dumps(new['weeks'][0], sort_keys=True) == json.dumps(past, sort_keys=True), new['weeks'][0])
    chk('(a) still two weeks, no append', len(new['weeks']) == 2)
    w = new['weeks'][1]
    chk('(a) current week recomputed', (w['open'], w['high'], w['low'], w['close'], w['days']) == (453.0, 458.0, 451.0, 457.0, 4), w)
    chk('(a) volume summed from daily bars', w.get('volume') == 4600, w)
    chk('(a) asOf/lastSession moved to last bar', new['asOf'] == '2026-01-15' and new['lastSession'] == '2026-01-15', new)
    chk('(a) still in progress', isinstance(new['inProgress'], str) and 'not finished' in new['inProgress'], new.get('inProgress'))
    chk('(a) note has exactly one Latest-week sentence', new['note'].count('Latest week') == 1, new['note'])
    chk('(a) note keeps the dated-snapshot line', 'Dated snapshot shipped with the screener' in new['note'], new['note'])
    # Second run, same fixture + same --now: nothing changes, file untouched.
    before = open(os.path.join(td, 'stock-weekly-TSLA.json'), 'rb').read()
    code2, out2, err2 = run_cli(['--fixture', fxp, '--out-dir', td, '--symbol', 'TSLA'])
    after = open(os.path.join(td, 'stock-weekly-TSLA.json'), 'rb').read()
    chk('(g) second identical run writes nothing', code2 == 0 and before == after, err2)
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- (b) new week appends, past weeks untouched ---
td = tempfile.mkdtemp(prefix='di-')
try:
    past = wk('2026-01-05', 5, 453.00, 462.50, 449.80, 460.50, 5000)
    doc = stock_doc([past], asof='2026-01-09', last='2026-01-09')
    open(os.path.join(td, 'stock-weekly-TSLA.json'), 'w').write(json.dumps(doc, indent=2) + '\n')
    fx = {'now': '2026-01-13T12:00:00-05:00', 'stocks': {'TSLA': WEEK_BARS[:2]}}
    fxp = os.path.join(td, 'fx.json'); json.dump(fx, open(fxp, 'w'))
    code, out, err = run_cli(['--fixture', fxp, '--out-dir', td, '--symbol', 'TSLA'])
    chk('(b) append CLI exit 0', code == 0, err)
    new = json.load(open(os.path.join(td, 'stock-weekly-TSLA.json')))
    chk('(b) past week untouched', new['weeks'][0] == past, new['weeks'][0])
    chk('(b) new week appended', len(new['weeks']) == 2 and new['weeks'][1]['monday'] == '2026-01-12', new['weeks'])
    chk('(b) appended candle is Mon-Tue only', (new['weeks'][1]['open'], new['weeks'][1]['close'], new['weeks'][1]['days']) == (453.0, 455.0, 2), new['weeks'][1])
    chk('(b) asOf is the last bar', new['asOf'] == '2026-01-13', new)
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- (c) bad data fails closed: file unchanged ---
for name, bad_bars in [
    ('empty bars', []),
    ('null close', [bar('2026-01-12', 453.0, 455.0, 451.0, None)]),
    ('high below close', [bar('2026-01-12', 453.0, 454.0, 451.0, 455.0)]),
    ('low above open', [bar('2026-01-12', 453.0, 455.0, 454.0, 452.0)]),
    ('non-positive close', [bar('2026-01-12', 453.0, 455.0, 451.0, 0.0)]),
    ('non-numeric open', [dict(bar('2026-01-12', 453.0, 455.0, 451.0, 454.0), open='abc')]),
]:
    td = tempfile.mkdtemp(prefix='di-')
    try:
        past = wk('2026-01-05', 5, 453.00, 462.50, 449.80, 460.50, 5000)
        cur = wk('2026-01-12', 4, 453.00, 462.50, 449.80, 455.00, 4000)
        doc = stock_doc([past, cur])
        p = os.path.join(td, 'stock-weekly-TSLA.json')
        open(p, 'w').write(json.dumps(doc, indent=2) + '\n')
        before = open(p, 'rb').read()
        fx = {'now': '2026-01-15T12:00:00-05:00', 'stocks': {'TSLA': bad_bars}}
        fxp = os.path.join(td, 'fx.json'); json.dump(fx, open(fxp, 'w'))
        code, out, err = run_cli(['--fixture', fxp, '--out-dir', td, '--symbol', 'TSLA'])
        after = open(p, 'rb').read()
        chk(f'(c) {name}: file unchanged', before == after, out + err)
        chk(f'(c) {name}: single-symbol run exits 1 (all failed)', code == 1, f'code={code} out={out} err={err}')
    finally:
        shutil.rmtree(td, ignore_errors=True)

# One bad symbol must not abort the run: good symbol still refreshes, exit 0.
td = tempfile.mkdtemp(prefix='di-')
try:
    for sym in ('TSLA', 'PLTR'):
        past = wk('2026-01-05', 5, 453.00, 462.50, 449.80, 460.50, 5000)
        cur = wk('2026-01-12', 4, 453.00, 462.50, 449.80, 455.00, 4000)
        doc = stock_doc([past, cur])
        doc['source'] = f'Yahoo {sym} unadjusted daily OHLC'
        open(os.path.join(td, f'stock-weekly-{sym}.json'), 'w').write(json.dumps(doc, indent=2) + '\n')
    fx = {'now': '2026-01-15T12:00:00-05:00',
          'stocks': {'TSLA': [], 'PLTR': WEEK_BARS}}
    fxp = os.path.join(td, 'fx.json'); json.dump(fx, open(fxp, 'w'))
    code, out, err = run_cli(['--fixture', fxp, '--out-dir', td])
    chk('(c) bad TSLA does not abort the run', code == 0, err)
    pltr = json.load(open(os.path.join(td, 'stock-weekly-PLTR.json')))
    chk('(c) good PLTR still refreshed', pltr['weeks'][1]['close'] == 457.0, pltr['weeks'][1])
    tsla = json.load(open(os.path.join(td, 'stock-weekly-TSLA.json')))
    chk('(c) bad TSLA file untouched', tsla['weeks'][1]['close'] == 455.00, tsla['weeks'][1])
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- (d) BRK.B fetches as BRK-B ---
chk('(d) YAHOO_MAP maps BRK.B to BRK-B', SW.YAHOO_MAP.get('BRK.B') == 'BRK-B', SW.YAHOO_MAP)
chk('(d) yahoo_symbol(BRK.B) is BRK-B', D.yahoo_symbol('BRK.B') == 'BRK-B')
chk('(d) yahoo URL for BRK.B uses BRK-B', 'chart/BRK-B?' in D.yahoo_url(D.yahoo_symbol('BRK.B'), dt.date(2026, 1, 12)), D.yahoo_url('BRK-B', dt.date(2026, 1, 12)))
chk('(d) other tickers map to themselves', all(D.yahoo_symbol(s) == s for s in ['TSLA', 'XYZ', 'SPCX']))
chk('(d) BRK.B is in SPECS with the YTD baseline', SW.SPECS.get('BRK.B', {}).get('base_session') == '2025-12-31', SW.SPECS.get('BRK.B'))
chk('(d) full-rebuild SYMS still omits BRK.B (rebuild logic unchanged)', 'BRK.B' not in SW.SYMS)
td = tempfile.mkdtemp(prefix='di-')
try:
    past = wk('2026-01-05', 5, 500.00, 505.00, 495.00, 502.00, 2000)
    cur = wk('2026-01-12', 4, 502.00, 506.00, 500.00, 504.00, 1500)
    doc = stock_doc([past, cur]); doc['source'] = 'Yahoo BRK-B unadjusted daily OHLC'
    doc['baseClose'] = 502.65
    open(os.path.join(td, 'stock-weekly-BRK.B.json'), 'w').write(json.dumps(doc, indent=2) + '\n')
    bars = [bar('2026-01-12', 502.0, 503.0, 501.0, 502.5, 500),
            bar('2026-01-13', 502.5, 504.0, 502.0, 503.5, 600)]
    fx = {'now': '2026-01-13T12:00:00-05:00', 'stocks': {'BRK.B': bars}}
    fxp = os.path.join(td, 'fx.json'); json.dump(fx, open(fxp, 'w'))
    code, out, err = run_cli(['--fixture', fxp, '--out-dir', td, '--symbol', 'BRK.B'])
    new = json.load(open(os.path.join(td, 'stock-weekly-BRK.B.json')))
    chk('(d) BRK.B fixture refresh exit 0', code == 0, err)
    chk('(d) BRK.B candle recomputed', (new['weeks'][1]['open'], new['weeks'][1]['close'], new['weeks'][1]['days']) == (502.0, 503.5, 2), new['weeks'][1])
    chk('(d) BRK.B source still says BRK-B', new['source'] == 'Yahoo BRK-B unadjusted daily OHLC', new['source'])
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- (e) CADUSD uses CADUSD=X, values ~0.709 USD per CAD ---
chk('(e) CADUSD Yahoo symbol is CADUSD%3DX', IW.SPECS['CADUSD'][0] == 'CADUSD%3DX', IW.SPECS['CADUSD'])
chk('(e) CADUSD is 4dp', IW.SPECS['CADUSD'][1] == 4)
chk('(e) CADUSD file is usdcad-weekly.json', IW.FILES['CADUSD'] == 'usdcad-weekly.json')
chk('(e) DJIA Yahoo symbol is %5EDJI, 2dp', IW.SPECS['DJIA'][0] == '%5EDJI' and IW.SPECS['DJIA'][1] == 2, IW.SPECS['DJIA'])
chk('(e) QQQ Yahoo symbol is QQQ, 2dp', IW.SPECS['QQQ'][0] == 'QQQ' and IW.SPECS['QQQ'][1] == 2, IW.SPECS['QQQ'])
chk('(e) DXY Yahoo symbol is DX-Y.NYB, 2dp', IW.SPECS['DXY'][0] == 'DX-Y.NYB' and IW.SPECS['DXY'][1] == 2, IW.SPECS['DXY'])
chk('(e) indicator SPECS now has all 8', set(IW.SPECS) == {'WTI', 'GOLD', 'US10Y', 'VIX', 'DJIA', 'QQQ', 'CADUSD', 'DXY'}, set(IW.SPECS))
td = tempfile.mkdtemp(prefix='di-')
try:
    past = wk('2026-01-05', 5, 0.7275, 0.7278, 0.7192, 0.7213)
    cur = wk('2026-01-12', 4, 0.7080, 0.7100, 0.7070, 0.7085)
    doc = {'source': 'Yahoo CADUSD=X (CAD/USD), USD per 1 CAD', 'asOf': '14 Jan 2026, 12:00 PM ET',
           'note': ('Weekly candles, UTC Monday-Sunday weeks, YTD 2026. First week is partial: week starting Mon 29 Dec 2025. '
                    'Values are USD per 1 CAD (Yahoo CADUSD=X). Weekly snapshot — the latest week is in progress until it closes.'),
           'weeks': [past, cur], 'inProgress': 'in progress, as of 14 Jan 2026, 12:00 PM ET'}
    open(os.path.join(td, 'usdcad-weekly.json'), 'w').write(json.dumps(doc, indent=2) + '\n')
    bars = [bar('2026-01-12', 0.7080, 0.7095, 0.7074, 0.7088),
            bar('2026-01-13', 0.7088, 0.7106, 0.7080, 0.7090),
            bar('2026-01-14', 0.7090, 0.7100, 0.7085, 0.7092)]
    fx = {'now': '2026-01-14T12:00:00-05:00', 'indicators': {'CADUSD': bars}}
    fxp = os.path.join(td, 'fx.json'); json.dump(fx, open(fxp, 'w'))
    code, out, err = run_cli(['--fixture', fxp, '--out-dir', td, '--symbol', 'CADUSD'])
    chk('(e) CADUSD refresh exit 0', code == 0, err)
    new = json.load(open(os.path.join(td, 'usdcad-weekly.json')))
    w = new['weeks'][1]
    chk('(e) CADUSD candle ~0.709 USD per CAD', (w['open'], w['high'], w['low'], w['close']) == (0.708, 0.7106, 0.7074, 0.7092), w)
    chk('(e) CADUSD has no volume field (shape preserved)', 'volume' not in w, w)
    chk('(e) CADUSD asOf is an ET datetime string', new['asOf'] == '14 Jan 2026, 12:00 PM ET', new['asOf'])
    chk('(e) CADUSD past week untouched', new['weeks'][0] == past, new['weeks'][0])
    # Yahoo returns zero volumes for indexes/FX: a zero sum must not
    # invent a "volume": 0 field on a file that never had one.
    zero = D.candle_for_week({dt.date(2026, 1, 12): {'open': 0.708, 'high': 0.71, 'low': 0.7074, 'close': 0.709}},
                             dt.date(2026, 1, 12), {dt.date(2026, 1, 12): 0}, None)
    chk('(e) zero Yahoo volume adds no volume field', 'volume' not in zero, zero)
    kept = D.candle_for_week({dt.date(2026, 1, 12): {'open': 90.0, 'high': 91.0, 'low': 89.5, 'close': 90.5}},
                             dt.date(2026, 1, 12), {}, 12345)
    chk('(e) missing volume falls back to the old volume', kept.get('volume') == 12345, kept)
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- (f) ET time gate: hours / holiday / early close ---
# Early closes are the official NYSE list (see EARLY_CLOSES): 2026 has
# two (27 Nov, 24 Dec), 2027 has one (26 Nov), 2028 has two (3 Jul,
# 24 Nov). 25 Nov 2026, 2 Jul 2026/2027 and 31 Dec are FULL sessions.
def gate(iso):
    return D.in_window(SW.parse_now(iso))
chk('(f) Mon 10:00 ET is inside', gate('2026-11-09T10:00:00-05:00')[0] is True, gate('2026-11-09T10:00:00-05:00'))
chk('(f) Mon 09:30 ET is inside (open)', gate('2026-11-09T09:30:00-05:00')[0] is True)
chk('(f) Mon 09:29 ET is outside (before open)', gate('2026-11-09T09:29:00-05:00')[0] is False)
chk('(f) Mon 16:30 ET is inside (final run)', gate('2026-11-09T16:30:00-05:00')[0] is True)
chk('(f) Mon 16:31 ET is outside', gate('2026-11-09T16:31:00-05:00')[0] is False)
chk('(f) Mon 08:00 ET is outside', gate('2026-11-09T08:00:00-05:00')[0] is False)
chk('(f) Mon 22:00 ET is outside (Stage 2 deploy window)', gate('2026-11-09T22:00:00-05:00')[0] is False)
chk('(f) Mon 22:00 EDT is outside', gate('2026-07-06T22:00:00-04:00')[0] is False)
chk('(f) Saturday skips', gate('2026-11-07T10:00:00-05:00')[0] is False)
chk('(f) Sunday skips', gate('2026-11-08T10:00:00-05:00')[0] is False)
chk('(f) Thanksgiving 26 Nov 2026 skips', gate('2026-11-26T10:00:00-05:00')[0] is False)
chk('(f) Christmas 25 Dec 2026 skips', gate('2026-12-25T10:00:00-05:00')[0] is False)
chk('(f) Christmas observed 24 Dec 2027 skips (full holiday)', gate('2027-12-24T10:00:00-05:00')[0] is False)
chk('(f) early-close 27 Nov 2026 12:00 is inside', gate('2026-11-27T12:00:00-05:00')[0] is True, gate('2026-11-27T12:00:00-05:00'))
chk('(f) early-close 27 Nov 2026 13:30 is inside (final run)', gate('2026-11-27T13:30:00-05:00')[0] is True)
chk('(f) early-close 27 Nov 2026 13:31 is outside', gate('2026-11-27T13:31:00-05:00')[0] is False)
chk('(f) early-close 27 Nov 2026 14:00 is outside', gate('2026-11-27T14:00:00-05:00')[0] is False)
chk('(f) early-close 24 Dec 2026 12:00 is inside', gate('2026-12-24T12:00:00-05:00')[0] is True)
chk('(f) early-close 24 Dec 2026 14:00 is outside', gate('2026-12-24T14:00:00-05:00')[0] is False)
chk('(f) early-close 26 Nov 2027 12:00 is inside', gate('2027-11-26T12:00:00-05:00')[0] is True)
chk('(f) early-close 26 Nov 2027 14:00 is outside', gate('2027-11-26T14:00:00-05:00')[0] is False)
chk('(f) early-close 3 Jul 2028 (EDT) 12:00 is inside', gate('2028-07-03T12:00:00-04:00')[0] is True)
chk('(f) early-close 3 Jul 2028 (EDT) 14:00 is outside', gate('2028-07-03T14:00:00-04:00')[0] is False)
chk('(f) early-close 24 Nov 2028 14:00 is outside', gate('2028-11-24T14:00:00-05:00')[0] is False)
# Dates an earlier draft wrongly listed as early closes are full sessions.
chk('(f) 25 Nov 2026 15:00 is inside (full session, not early close)', gate('2026-11-25T15:00:00-05:00')[0] is True)
chk('(f) 2 Jul 2026 15:00 is inside (full session)', gate('2026-07-02T15:00:00-04:00')[0] is True)
chk('(f) 2 Jul 2027 15:00 is inside (full session)', gate('2027-07-02T15:00:00-04:00')[0] is True)
chk('(f) 31 Dec 2026 15:00 is inside (full session)', gate('2026-12-31T15:00:00-05:00')[0] is True)
chk('(f) 31 Dec 2027 15:00 is inside (full session)', gate('2027-12-31T15:00:00-05:00')[0] is True)
chk('(f) EDT Monday 10:00 is inside', gate('2026-07-06T10:00:00-04:00')[0] is True)
chk('(f) EST January Monday 10:00 is inside', gate('2026-01-12T10:00:00-05:00')[0] is True)
code, out, err = run_cli(['--gate', '--now', '2026-11-09T10:00:00-05:00'])
chk('(f) --gate CLI prints run=1 inside hours', code == 0 and 'run=1' in out, out + err)
code, out, err = run_cli(['--gate', '--now', '2026-11-09T08:00:00-05:00'])
chk('(f) --gate CLI prints run=0 outside hours', code == 0 and 'run=0' in out, out + err)
code, out, err = run_cli(['--gate', '--now', '2026-11-09T22:00:00-05:00'])
chk('(f) --gate CLI prints run=0 at 10 PM ET', code == 0 and 'run=0' in out, out + err)

# --- (g) check-only writes nothing ---
td = tempfile.mkdtemp(prefix='di-')
try:
    past = wk('2026-01-05', 5, 453.00, 462.50, 449.80, 460.50, 5000)
    cur = wk('2026-01-12', 4, 453.00, 462.50, 449.80, 455.00, 4000)
    doc = stock_doc([past, cur])
    p = os.path.join(td, 'stock-weekly-TSLA.json')
    open(p, 'w').write(json.dumps(doc, indent=2) + '\n')
    before = open(p, 'rb').read()
    fx = {'now': '2026-01-15T12:00:00-05:00', 'stocks': {'TSLA': WEEK_BARS}}
    fxp = os.path.join(td, 'fx.json'); json.dump(fx, open(fxp, 'w'))
    code, out, err = run_cli(['--fixture', fxp, '--out-dir', td, '--symbol', 'TSLA', '--check-only'])
    chk('(g) check-only exit 0 and writes nothing', code == 0 and open(p, 'rb').read() == before, out + err)
    chk('(g) check-only says what it would do', 'would refreshed' in out, out)
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- (h) stale or missing time zone data must SKIP the run (fail safe) ---
chk('(h) tz_healthy() is True with the real zone', D.tz_healthy() is True)
chk('(h) tz_healthy() is True for an explicit ET zone', D.tz_healthy(ZoneInfo('America/New_York')) is True)
chk('(h) tz_healthy() is False for None (missing tzdata)', D.tz_healthy(None) is False)
chk('(h) tz_healthy() is False for UTC (wrong offsets = stale tzdata)', D.tz_healthy(ZoneInfo('UTC')) is False)
chk('(h) tz_healthy() is False for a fixed -05:00 zone (no DST = stale)', D.tz_healthy(dt.timezone(dt.timedelta(hours=-5))) is False)
# Simulate missing tzdata by clearing the module zone: the gate must skip.
saved_ny = D.NY
try:
    D.NY = None
    chk('(h) missing tzdata: tz_healthy() is False', D.tz_healthy() is False)
    inside, reason = D.in_window(SW.parse_now('2026-11-09T10:00:00-05:00'))
    chk('(h) missing tzdata: gate skips (run=0)', inside is False and 'time zone' in reason, reason)
finally:
    D.NY = saved_ny
chk('(h) zone restored: gate is inside again', D.in_window(SW.parse_now('2026-11-09T10:00:00-05:00'))[0] is True)
# Simulate stale tzdata (a zone with the wrong offsets): UTC has 0/0.
try:
    D.NY = ZoneInfo('UTC')
    chk('(h) stale tzdata: tz_healthy() is False', D.tz_healthy() is False)
    inside, reason = D.in_window(SW.parse_now('2026-11-09T10:00:00-05:00'))
    chk('(h) stale tzdata: gate skips (run=0)', inside is False and 'time zone' in reason, reason)
finally:
    D.NY = saved_ny
# stock_weekly.parse_now must fail loudly (not silently mis-parse) without a zone.
saved_sw_ny = SW.NY
try:
    SW.NY = None
    try:
        SW.parse_now('2026-11-09T10:00:00-05:00')
        chk('(h) parse_now without a zone raises', False, 'no error raised')
    except RuntimeError as e:
        chk('(h) parse_now without a zone raises a clear error', 'time zone' in str(e), str(e))
finally:
    SW.NY = saved_sw_ny
# Both zones gone at once: the --gate path must still print run=0 and exit 0.
def run_main_in_process(args):
    """Call D.main in-process (so a monkeypatched fetch is used); returns (code, out, err)."""
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
    try:
        code = D.main(args)
    finally:
        out, err = sys.stdout.getvalue(), sys.stderr.getvalue()
        sys.stdout, sys.stderr = old_out, old_err
    return code, out, err
saved_ny, saved_sw_ny = D.NY, SW.NY
try:
    D.NY = None
    SW.NY = None
    code, out, err = run_main_in_process(['--gate', '--now', '2026-11-09T10:00:00-05:00'])
    chk('(h) gate with no tzdata at all prints run=0 and exits 0', code == 0 and 'run=0' in out, out + err)
finally:
    D.NY, SW.NY = saved_ny, saved_sw_ny
# And the refresh path must skip (exit 0, no write) when the zone is bad.
td = tempfile.mkdtemp(prefix='di-')
try:
    past = wk('2026-01-05', 5, 453.00, 462.50, 449.80, 460.50, 5000)
    cur = wk('2026-01-12', 4, 453.00, 462.50, 449.80, 455.00, 4000)
    doc = stock_doc([past, cur])
    p = os.path.join(td, 'stock-weekly-TSLA.json')
    open(p, 'w').write(json.dumps(doc, indent=2) + '\n')
    before = open(p, 'rb').read()
    fx = {'now': '2026-01-15T12:00:00-05:00', 'stocks': {'TSLA': WEEK_BARS}}
    fxp = os.path.join(td, 'fx.json'); json.dump(fx, open(fxp, 'w'))
    saved_ny = D.NY
    try:
        D.NY = None
        code, out, err = run_main_in_process(['--fixture', fxp, '--out-dir', td, '--symbol', 'TSLA'])
    finally:
        D.NY = saved_ny
    chk('(h) refresh with bad tzdata skips (exit 0, no write)', code == 0 and open(p, 'rb').read() == before, out + err)
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- (i) holiday / early-close lists must cover the current and next year ---
# This test FAILS when a year is not covered, so the lists must be kept
# current. It also locks in the NYSE early-close corrections (see EARLY_CLOSES).
today = dt.date.today()
for yr in (today.year, today.year + 1):
    chk(f'(i) HOLIDAYS covers {yr}', any(d.startswith(str(yr)) for d in SW.HOLIDAYS), str(yr))
    chk(f'(i) EARLY_CLOSES covers {yr}', any(d.startswith(str(yr)) for d in D.EARLY_CLOSES), str(yr))
for d in ('2026-11-27', '2026-12-24', '2027-11-26', '2028-07-03', '2028-11-24'):
    chk(f'(i) {d} is an NYSE early close', d in D.EARLY_CLOSES)
for d in ('2026-07-02', '2026-11-25', '2026-12-31', '2027-07-02', '2027-11-24', '2027-12-24', '2027-12-31'):
    chk(f'(i) {d} is NOT an early close (full session or full holiday)', d not in D.EARLY_CLOSES, d)
for d in D.EARLY_CLOSES:
    dd = dt.date.fromisoformat(d)
    chk(f'(i) early close {d} is a weekday and not a full holiday', dd.weekday() < 5 and d not in SW.HOLIDAYS, d)

# --- (j) no silent partial failures: warn naming the stale symbols, fail if > 3 fail ---
def five_symbol_setup(td, bad_syms):
    """Temp files for 5 stocks; `bad_syms` get empty (failing) fixture bars."""
    for sym in ('TSLA', 'PLTR', 'MSTR', 'IBIT', 'MU'):
        past = wk('2026-01-05', 5, 453.00, 462.50, 449.80, 460.50, 5000)
        cur = wk('2026-01-12', 4, 453.00, 462.50, 449.80, 455.00, 4000)
        doc = stock_doc([past, cur])
        doc['source'] = f'Yahoo {sym} unadjusted daily OHLC'
        open(os.path.join(td, f'stock-weekly-{sym}.json'), 'w').write(json.dumps(doc, indent=2) + '\n')
    stocks = {sym: ([] if sym in bad_syms else WEEK_BARS) for sym in ('TSLA', 'PLTR', 'MSTR', 'IBIT', 'MU')}
    fx = {'now': '2026-01-15T12:00:00-05:00', 'stocks': stocks}
    fxp = os.path.join(td, 'fx.json'); json.dump(fx, open(fxp, 'w'))
    return fxp
# 4 failures (> 3): the run fails and names the 4 stale symbols.
td = tempfile.mkdtemp(prefix='di-')
try:
    fxp = five_symbol_setup(td, {'TSLA', 'PLTR', 'MSTR', 'IBIT'})
    code, out, err = run_cli(['--fixture', fxp, '--out-dir', td])
    chk('(j) 4 failures: run exits 1', code == 1, f'code={code} out={out} err={err}')
    chk('(j) 4 failures: warning names all 4 stale symbols',
        all(s in err for s in ('TSLA', 'PLTR', 'MSTR', 'IBIT')) and 'stale' in err.lower(), err)
    chk('(j) 4 failures: the good symbol still refreshed', json.load(open(os.path.join(td, 'stock-weekly-MU.json')))['weeks'][1]['close'] == 457.0)
    chk('(j) 4 failures: a bad symbol file is untouched', json.load(open(os.path.join(td, 'stock-weekly-TSLA.json')))['weeks'][1]['close'] == 455.00)
finally:
    shutil.rmtree(td, ignore_errors=True)
# 3 failures (at the limit): the run passes, but still names the stale symbols.
td = tempfile.mkdtemp(prefix='di-')
try:
    fxp = five_symbol_setup(td, {'TSLA', 'PLTR', 'MSTR'})
    code, out, err = run_cli(['--fixture', fxp, '--out-dir', td])
    chk('(j) 3 failures: run exits 0', code == 0, f'code={code} out={out} err={err}')
    chk('(j) 3 failures: warning still names the 3 stale symbols',
        all(s in err for s in ('TSLA', 'PLTR', 'MSTR')) and 'stale' in err.lower(), err)
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- (k) Yahoo 429: one 429 fails closed for that symbol; two in a row abort ---
NY_TZ = ZoneInfo('America/New_York')
def yahoo_payload(rows):
    """Fixture bars -> a Yahoo chart.result[0] payload (noon-ET timestamps)."""
    ts, o, h, l, c = [], [], [], [], []
    for r in rows:
        d = dt.date.fromisoformat(r['date'])
        ts.append(int(dt.datetime(d.year, d.month, d.day, 12, 0, tzinfo=NY_TZ).timestamp()))
        o.append(r['open']); h.append(r['high']); l.append(r['low']); c.append(r['close'])
    return {'meta': {'currency': 'USD'}, 'timestamp': ts,
            'indicators': {'quote': [{'open': o, 'high': h, 'low': l, 'close': c}]}}
PAST_BARS = [
    bar('2026-01-05', 450.00, 452.00, 449.00, 451.00, 900),
    bar('2026-01-06', 451.00, 453.00, 450.00, 452.00, 950),
    bar('2026-01-07', 452.00, 454.00, 451.00, 453.00, 1000),
    bar('2026-01-08', 453.00, 455.00, 452.00, 454.00, 1050),
]
# PAST_BARS are the week of Mon 5 Jan — before the current week (Mon 12 Jan),
# so a payload built from them yields "no bars for the current week" -> skipped.
def stock_file(td, sym):
    past = wk('2026-01-05', 5, 453.00, 462.50, 449.80, 460.50, 5000)
    cur = wk('2026-01-12', 4, 453.00, 462.50, 449.80, 455.00, 4000)
    doc = stock_doc([past, cur]); doc['source'] = f'Yahoo {sym} unadjusted daily OHLC'
    open(os.path.join(td, f'stock-weekly-{sym}.json'), 'w').write(json.dumps(doc, indent=2) + '\n')
# fetch_yahoo_payload raises YahooRateLimited on HTTP 429, RuntimeError otherwise.
orig_urlopen = urllib.request.urlopen
def _fake_urlopen_429(req, timeout=None):
    raise urllib.error.HTTPError('https://query1.finance.yahoo.com/', 429, 'Too Many Requests', {}, None)
urllib.request.urlopen = _fake_urlopen_429
try:
    try:
        D.fetch_yahoo_payload('TSLA', dt.date(2026, 1, 12))
        chk('(k) fetch raises YahooRateLimited on HTTP 429', False, 'no error raised')
    except D.YahooRateLimited as e:
        chk('(k) fetch raises YahooRateLimited on HTTP 429', '429' in str(e), str(e))
    except Exception as e:
        chk('(k) fetch raises YahooRateLimited on HTTP 429', False, f'wrong error: {type(e).__name__}: {e}')
finally:
    urllib.request.urlopen = orig_urlopen
def _fake_urlopen_500(req, timeout=None):
    raise urllib.error.HTTPError('https://query1.finance.yahoo.com/', 500, 'Server Error', {}, None)
urllib.request.urlopen = _fake_urlopen_500
try:
    try:
        D.fetch_yahoo_payload('TSLA', dt.date(2026, 1, 12))
        chk('(k) fetch raises RuntimeError (not YahooRateLimited) on HTTP 500', False, 'no error raised')
    except D.YahooRateLimited:
        chk('(k) fetch raises RuntimeError (not YahooRateLimited) on HTTP 500', False, 'got YahooRateLimited for 500')
    except RuntimeError as e:
        chk('(k) fetch raises RuntimeError (not YahooRateLimited) on HTTP 500', '500' in str(e), str(e))
finally:
    urllib.request.urlopen = orig_urlopen
# Two 429s in a row (TSLA, then PLTR) abort the run before MSTR is touched.
td = tempfile.mkdtemp(prefix='di-')
try:
    for sym in ('TSLA', 'PLTR', 'MSTR'):
        stock_file(td, sym)
    mstr_before = open(os.path.join(td, 'stock-weekly-MSTR.json'), 'rb').read()
    orig_fetch = D.fetch_yahoo_payload
    def fake_fetch_429(ysym, since):
        if ysym in ('TSLA', 'PLTR'):
            raise D.YahooRateLimited(f'Yahoo rate-limited {ysym} (HTTP 429)')
        if ysym == 'MSTR':
            return yahoo_payload(WEEK_BARS)  # would refresh MSTR if the run continued
        return yahoo_payload(PAST_BARS)
    D.fetch_yahoo_payload = fake_fetch_429
    try:
        code, out, err = run_main_in_process(['--out-dir', td, '--now', '2026-01-15T12:00:00-05:00'])
    finally:
        D.fetch_yahoo_payload = orig_fetch
    chk('(k) two 429s in a row: run exits 1', code == 1, f'code={code} out={out} err={err}')
    chk('(k) two 429s in a row: output says ABORTING and names 429', 'ABORTING' in err and '429' in err, err)
    chk('(k) two 429s in a row: MSTR file untouched (run stopped before it)',
        open(os.path.join(td, 'stock-weekly-MSTR.json'), 'rb').read() == mstr_before, out + err)
    chk('(k) two 429s in a row: TSLA/PLTR files untouched (kept last good)',
        json.load(open(os.path.join(td, 'stock-weekly-TSLA.json')))['weeks'][1]['close'] == 455.00
        and json.load(open(os.path.join(td, 'stock-weekly-PLTR.json')))['weeks'][1]['close'] == 455.00)
finally:
    shutil.rmtree(td, ignore_errors=True)
# One 429 (TSLA) then a success (PLTR): the run continues and exits 0.
td = tempfile.mkdtemp(prefix='di-')
try:
    for sym in D.STOCK_SYMS:
        stock_file(td, sym)
    for key in D.INDICATOR_KEYS:
        past = wk('2026-01-05', 5, 100.00, 101.00, 99.00, 100.50)
        cur = wk('2026-01-12', 4, 100.50, 102.00, 100.00, 101.00)
        doc = {'source': f'Yahoo {key}', 'asOf': '14 Jan 2026, 12:00 PM ET',
               'note': 'Weekly candles. Latest week is in progress as of 14 Jan 2026, 12:00 PM ET; its close is not a final close.',
               'weeks': [past, cur], 'inProgress': 'in progress, as of 14 Jan 2026, 12:00 PM ET'}
        open(os.path.join(td, IW.FILES[key]), 'w').write(json.dumps(doc, indent=2) + '\n')
    orig_fetch = D.fetch_yahoo_payload
    def fake_fetch_one_429(ysym, since):
        if ysym == 'TSLA':
            raise D.YahooRateLimited('Yahoo rate-limited TSLA (HTTP 429)')
        if ysym == 'PLTR':
            return yahoo_payload(WEEK_BARS)
        return yahoo_payload(PAST_BARS)
    D.fetch_yahoo_payload = fake_fetch_one_429
    try:
        code, out, err = run_main_in_process(['--out-dir', td, '--now', '2026-01-15T12:00:00-05:00'])
    finally:
        D.fetch_yahoo_payload = orig_fetch
    chk('(k) one 429: run exits 0 (does not abort)', code == 0, f'code={code} out={out} err={err}')
    chk('(k) one 429: warning names TSLA as stale', 'TSLA' in err and 'stale' in err.lower(), err)
    chk('(k) one 429: PLTR still refreshed (run continued)', json.load(open(os.path.join(td, 'stock-weekly-PLTR.json')))['weeks'][1]['close'] == 457.0)
    chk('(k) one 429: TSLA file untouched (kept last good)', json.load(open(os.path.join(td, 'stock-weekly-TSLA.json')))['weeks'][1]['close'] == 455.00)
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- (l) commit only on value change: same values, later --now, no write ---
td = tempfile.mkdtemp(prefix='di-')
try:
    past = wk('2026-01-05', 5, 453.00, 462.50, 449.80, 460.50, 5000)
    cur = wk('2026-01-12', 4, 453.00, 462.50, 449.80, 455.00, 4000)
    doc = stock_doc([past, cur])
    p = os.path.join(td, 'stock-weekly-TSLA.json')
    open(p, 'w').write(json.dumps(doc, indent=2) + '\n')
    fx = {'now': '2026-01-15T12:00:00-05:00', 'stocks': {'TSLA': WEEK_BARS}}
    fxp = os.path.join(td, 'fx.json'); json.dump(fx, open(fxp, 'w'))
    code, out, err = run_cli(['--fixture', fxp, '--out-dir', td, '--symbol', 'TSLA'])
    chk('(l) first run refreshes (value changed)', code == 0, err)
    before = open(p, 'rb').read()
    # Same bars, two hours later the same day: nothing changed, so no write
    # — no timestamp-only write, no commit, no Pages build.
    fx2 = {'now': '2026-01-15T14:00:00-05:00', 'stocks': {'TSLA': WEEK_BARS}}
    fxp2 = os.path.join(td, 'fx2.json'); json.dump(fx2, open(fxp2, 'w'))
    code2, out2, err2 = run_cli(['--fixture', fxp2, '--out-dir', td, '--symbol', 'TSLA'])
    after = open(p, 'rb').read()
    chk('(l) same values, later --now: file byte-identical (no write)', code2 == 0 and before == after, out2 + err2)
    chk('(l) same values, later --now: run says unchanged', 'unchanged' in out2, out2)
finally:
    shutil.rmtree(td, ignore_errors=True)
# Same for an indicator (its asOf is a datetime string — it must not move
# when the candle does not).
td = tempfile.mkdtemp(prefix='di-')
try:
    past = wk('2026-01-05', 5, 0.7275, 0.7278, 0.7192, 0.7213)
    cur = wk('2026-01-12', 4, 0.7080, 0.7100, 0.7070, 0.7085)
    doc = {'source': 'Yahoo CADUSD=X (CAD/USD), USD per 1 CAD', 'asOf': '14 Jan 2026, 12:00 PM ET',
           'note': ('Weekly candles, UTC Monday-Sunday weeks, YTD 2026. First week is partial: week starting Mon 29 Dec 2025. '
                    'Values are USD per 1 CAD (Yahoo CADUSD=X). Weekly snapshot — the latest week is in progress until it closes.'),
           'weeks': [past, cur], 'inProgress': 'in progress, as of 14 Jan 2026, 12:00 PM ET'}
    p = os.path.join(td, 'usdcad-weekly.json')
    open(p, 'w').write(json.dumps(doc, indent=2) + '\n')
    bars = [bar('2026-01-12', 0.7080, 0.7095, 0.7074, 0.7088),
            bar('2026-01-13', 0.7088, 0.7106, 0.7080, 0.7090),
            bar('2026-01-14', 0.7090, 0.7100, 0.7085, 0.7092)]
    fx = {'now': '2026-01-14T12:00:00-05:00', 'indicators': {'CADUSD': bars}}
    fxp = os.path.join(td, 'fx.json'); json.dump(fx, open(fxp, 'w'))
    code, out, err = run_cli(['--fixture', fxp, '--out-dir', td, '--symbol', 'CADUSD'])
    chk('(l) indicator first run refreshes', code == 0, err)
    before = open(p, 'rb').read()
    fx2 = {'now': '2026-01-14T14:30:00-05:00', 'indicators': {'CADUSD': bars}}
    fxp2 = os.path.join(td, 'fx2.json'); json.dump(fx2, open(fxp2, 'w'))
    code2, out2, err2 = run_cli(['--fixture', fxp2, '--out-dir', td, '--symbol', 'CADUSD'])
    after = open(p, 'rb').read()
    chk('(l) indicator same values, later --now: file byte-identical', code2 == 0 and before == after, out2 + err2)
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- shipped-file sanity: the tool's symbol lists cover the shipped files ---
shipped_stocks = sorted(f[13:-5] for f in os.listdir(os.path.join(R, 'assets/data'))
                        if f.startswith('stock-weekly-') and f.endswith('.json'))
chk('shipped stock files match the 16 intraday stocks', shipped_stocks == sorted(D.STOCK_SYMS), shipped_stocks)
shipped_ind = sorted(f[:-12] for f in os.listdir(os.path.join(R, 'assets/data'))
                     if f.endswith('-weekly.json'))
chk('shipped indicator files match the 8 intraday indicators',
    shipped_ind == sorted(IW.FILES[k].replace('-weekly.json', '') for k in D.INDICATOR_KEYS), shipped_ind)

print('DESK_INTRADAY TESTS', n, 'FAIL', f)
sys.exit(1 if f else 0)
