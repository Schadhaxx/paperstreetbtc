#!/usr/bin/env python3
"""tools/desk_intraday.py --live-json / --validate-live (5-minute Desk,
option b): the one small current-week candle file for every Desk symbol
that is published to the data branch next to prices.json. Offline
fixtures only, no network.

Covers: all 24 Desk symbols (incl. DIA) present with a validated
current-week candle; schema/finite/positive/consistency checks reject
NaN, inf, zero, negative, bool, inconsistent OHLC, a non-Monday week,
missing/unknown symbols, a failed entry carrying a candle, a wrong
failed list, a bad asOf and an oversized file; an invalid document is
never written; a bad symbol is marked failed with no candle; --check-only
leaves the weekly files byte-identical; --validate-live exit codes.
"""
import copy, datetime as dt, glob, json, math, os, shutil, subprocess, sys, tempfile
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'tools'))
import desk_intraday as D
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

NOW = '2026-11-12T15:00:00-05:00'   # Thu, session open; current week Mon 9 Nov 2026
MON = dt.date(2026, 11, 9)

def mk_tree():
    """Temp out-dir holding copies of every shipped Desk weekly file, with
    the current week (9 Nov) dropped so the fixture rebuilds it."""
    td = tempfile.mkdtemp(prefix='dlive-')
    names = list(D.STOCK_FILES.values()) + [IW.FILES[k] for k in D.INDICATOR_KEYS]
    for nm in names:
        doc = json.load(open(os.path.join(R, 'assets', 'data', nm)))
        doc['weeks'] = [w for w in doc['weeks'] if w['monday'] < MON.isoformat()]
        doc['inProgress'] = None
        with open(os.path.join(td, nm), 'w') as fh:
            json.dump(doc, fh, indent=2); fh.write('\n')
    return td

def rows_for(base, nd, vol=True):
    out = []
    for i in range(4):   # Mon-Thu
        d = MON + dt.timedelta(days=i)
        o = round(base * (1 + 0.001 * i), nd); c = round(base * (1 + 0.001 * (i + 1)), nd)
        h = round(max(o, c) * 1.002, nd); l = round(min(o, c) * 0.998, nd)
        r = {'date': d.isoformat(), 'open': o, 'high': h, 'low': l, 'close': c}
        if vol:
            r['volume'] = 1000 + i
        out.append(r)
    return out

def fixture(td, bad=()):
    fx = {'now': NOW, 'stocks': {}, 'indicators': {}}
    for s in D.STOCK_SYMS:
        last = json.load(open(os.path.join(td, D.STOCK_FILES[s])))['weeks'][-1]['close']
        fx['stocks'][s] = rows_for(last, 2)
    for k in D.INDICATOR_KEYS:
        last = json.load(open(os.path.join(td, IW.FILES[k])))['weeks'][-1]['close']
        fx['indicators'][k] = rows_for(last, IW.SPECS[k][1], vol=k in ('WTI', 'GOLD', 'DIA', 'QQQ'))
    for s in bad:
        grp = 'stocks' if s in D.STOCK_SYMS else 'indicators'
        fx[grp][s][-1]['close'] = None
    p = os.path.join(td, 'fx.json')
    json.dump(fx, open(p, 'w'))
    return p

def snapshot(td):
    return {p: open(p, 'rb').read() for p in sorted(glob.glob(os.path.join(td, '*-weekly*.json')))}

ALL = set(D.STOCK_SYMS) | set(D.INDICATOR_KEYS)
chk('Desk symbols are the 16 stocks + 8 tiles, DIA included, DJIA gone', len(ALL) == 24 and 'DIA' in ALL and 'DJIA' not in ALL, sorted(ALL))

# --- (a) full fixture run, check-only: live file written, weekly files untouched ---
td = mk_tree()
try:
    fxp = fixture(td)
    before = snapshot(td)
    lp = os.path.join(td, 'out', 'desk-live.json')
    code, out, err = run_cli(['--fixture', fxp, '--out-dir', td, '--check-only', '--live-json', lp])
    chk('(a) check-only + live-json exits 0', code == 0, (out[-400:], err[-400:]))
    chk('(a) weekly files byte-identical under --check-only', snapshot(td) == before)
    doc = json.load(open(lp))
    chk('(a) document validates', D.validate_live_doc(doc) == [], D.validate_live_doc(doc))
    chk('(a) every Desk symbol present', set(doc['symbols']) == ALL, set(doc['symbols']) ^ ALL)
    chk('(a) all 24 ok, none failed', all(e['status'] == 'ok' for e in doc['symbols'].values()) and doc['failed'] == [])
    chk('(a) v/kind/asOf/sessionOpen', doc['v'] == 1 and doc['kind'] == 'desk-live' and doc['asOf'] == '2026-11-12T20:00:00Z' and doc['sessionOpen'] is True, {k: doc[k] for k in ('v', 'kind', 'asOf', 'sessionOpen')})
    chk('(a) asOfLabel in ET', doc['asOfLabel'] == '12 Nov 2026, 3:00 PM ET', doc['asOfLabel'])
    t = doc['symbols']['TSLA']; rows = json.load(open(fxp))['stocks']['TSLA']
    chk('(a) TSLA candle = candle_for_week of the fixture bars', (t['monday'], t['sunday'], t['days'], t['open'], t['close'], t['high'], t['low'], t['volume']) ==
        ('2026-11-09', '2026-11-15', 4, rows[0]['open'], rows[-1]['close'], max(r['high'] for r in rows), min(r['low'] for r in rows), sum(r['volume'] for r in rows)), t)
    chk('(a) TSLA inProgress true + lastSession Thu', t['inProgress'] is True and t['lastSession'] == '2026-11-12', t)
    dia = doc['symbols']['DIA']
    chk('(a) DIA is an indicator entry pointing at dia-weekly.json', dia['kind'] == 'indicator' and dia['file'] == 'dia-weekly.json' and dia['status'] == 'ok', dia)
    chk('(a) CADUSD keyed as the tool keys it, file usdcad-weekly.json', doc['symbols']['CADUSD']['file'] == 'usdcad-weekly.json')
    chk('(a) VIX carries no volume (index: zero/absent volume is not a volume)', 'volume' not in doc['symbols']['VIX'], doc['symbols']['VIX'])
    raw = open(lp).read()
    chk('(a) file is small (< 8 KB) and compact', len(raw.encode()) < 8 * 1024 and '\n' not in raw.rstrip('\n'), len(raw))
    chk('(a) no NaN/Infinity tokens', 'NaN' not in raw and 'Infinity' not in raw)
    code, out, err = run_cli(['--validate-live', lp])
    chk('(a) --validate-live OK on the written file', code == 0 and 'desk-live OK: 24/24' in out, (out, err))
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- (b) normal run (not check-only) also writes the weekly files as before ---
td = mk_tree()
try:
    fxp = fixture(td)
    lp = os.path.join(td, 'desk-live.json')
    code, out, err = run_cli(['--fixture', fxp, '--out-dir', td, '--live-json', lp])
    tsla = json.load(open(os.path.join(td, D.STOCK_FILES['TSLA'])))
    live = json.load(open(lp))
    chk('(b) normal run exits 0 and appends the current week to the weekly file', code == 0 and tsla['weeks'][-1]['monday'] == '2026-11-09', (code, err[-300:]))
    w = tsla['weeks'][-1]; e = live['symbols']['TSLA']
    chk('(b) live candle == weekly-file candle (same validated candle)', all(w[k] == e[k] for k in ('monday', 'sunday', 'days', 'open', 'high', 'low', 'close', 'volume')), (w, e))
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- (c) one bad symbol: marked failed, no candle, document still valid, run exit 0 ---
td = mk_tree()
try:
    fxp = fixture(td, bad=('NVDA',))
    lp = os.path.join(td, 'desk-live.json')
    code, out, err = run_cli(['--fixture', fxp, '--out-dir', td, '--check-only', '--live-json', lp])
    doc = json.load(open(lp))
    chk('(c) one bad symbol: exit 0', code == 0, err[-300:])
    chk('(c) NVDA failed, no candle', doc['symbols']['NVDA'] == {'kind': 'stock', 'file': 'stock-weekly-NVDA.json', 'status': 'failed'}, doc['symbols']['NVDA'])
    chk('(c) failed list names NVDA', doc['failed'] == ['NVDA'], doc['failed'])
    chk('(c) still validates', D.validate_live_doc(doc) == [])
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- (d) 4 bad symbols: run fails (>3), file still written with 4 failed ---
td = mk_tree()
try:
    fxp = fixture(td, bad=('NVDA', 'AAPL', 'WTI', 'DIA'))
    lp = os.path.join(td, 'desk-live.json')
    code, out, err = run_cli(['--fixture', fxp, '--out-dir', td, '--check-only', '--live-json', lp])
    doc = json.load(open(lp))
    chk('(d) >3 failures: exit 1 (workflow will not publish)', code == 1, code)
    chk('(d) file marks the 4 failed', doc['failed'] == sorted(['NVDA', 'AAPL', 'WTI', 'DIA']), doc['failed'])
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- (e) validator mutations (fail closed) ---
def good_doc():
    D.LIVE.clear()
    sts = {}
    for s in D.STOCK_SYMS:
        c = {'monday': '2026-11-09', 'sunday': '2026-11-15', 'days': 4, 'open': 10.0, 'high': 12.0, 'low': 9.0, 'close': 11.0, 'volume': 5}
        D.LIVE[('stock', s)] = D._live_entry('stock', s, c, True, '2026-11-12'); sts[('stock', s)] = 'ok'
    for k in D.INDICATOR_KEYS:
        c = {'monday': '2026-11-09', 'sunday': '2026-11-15', 'days': 4, 'open': 1.0, 'high': 1.2, 'low': 0.9, 'close': 1.1}
        D.LIVE[('indicator', k)] = D._live_entry('indicator', k, c, True); sts[('indicator', k)] = 'ok'
    return D.build_live_doc(dt.datetime.fromisoformat(NOW), sts)
g = good_doc()
chk('(e) baseline document validates', D.validate_live_doc(g) == [], D.validate_live_doc(g))
def mut(name, fn, expect_substr):
    d = copy.deepcopy(g); fn(d); errs = D.validate_live_doc(d)
    chk(f'(e) rejects {name}', bool(errs) and any(expect_substr in e for e in errs), errs)
mut('NaN close', lambda d: d['symbols']['TSLA'].__setitem__('close', float('nan')), 'bad close')
mut('inf high', lambda d: d['symbols']['DIA'].__setitem__('high', float('inf')), 'bad high')
mut('zero low', lambda d: d['symbols']['WTI'].__setitem__('low', 0), 'bad low')
mut('negative open', lambda d: d['symbols']['MU'].__setitem__('open', -1.0), 'bad open')
mut('bool close', lambda d: d['symbols']['MU'].__setitem__('close', True), 'bad close')
mut('string close', lambda d: d['symbols']['MU'].__setitem__('close', '11'), 'bad close')
mut('high below close', lambda d: d['symbols']['TSLA'].__setitem__('high', 10.5), 'OHLC inconsistent')
mut('low above open', lambda d: d['symbols']['TSLA'].__setitem__('low', 10.5), 'OHLC inconsistent')
mut('days 0', lambda d: d['symbols']['TSLA'].__setitem__('days', 0), 'bad days')
mut('days 8', lambda d: d['symbols']['TSLA'].__setitem__('days', 8), 'bad days')
mut('non-Monday week', lambda d: d['symbols']['TSLA'].update(monday='2026-11-10', sunday='2026-11-16'), 'bad week')
mut('sunday not monday+6', lambda d: d['symbols']['TSLA'].__setitem__('sunday', '2026-11-14'), 'bad week')
mut('negative volume', lambda d: d['symbols']['TSLA'].__setitem__('volume', -1), 'bad volume')
mut('float volume', lambda d: d['symbols']['TSLA'].__setitem__('volume', 1.5), 'bad volume')
mut('missing symbol', lambda d: d['symbols'].pop('DIA'), 'missing symbols')
mut('unknown symbol (old DJIA)', lambda d: d['symbols'].__setitem__('DJIA', copy.deepcopy(d['symbols']['DIA'])), 'unknown symbols')
mut('failed entry with a candle', lambda d: (d['symbols']['TSLA'].__setitem__('status', 'failed'), d.__setitem__('failed', ['TSLA'])), 'must not carry a candle')
mut('failed list mismatch', lambda d: d.__setitem__('failed', ['TSLA']), 'failed list')
mut('bad asOf', lambda d: d.__setitem__('asOf', '2026-11-12 20:00'), 'bad asOf')
mut('bad version', lambda d: d.__setitem__('v', 2), 'bad v')
mut('bad status', lambda d: d['symbols']['TSLA'].__setitem__('status', 'live'), 'bad status')
mut('inProgress not bool', lambda d: d['symbols']['TSLA'].__setitem__('inProgress', 'yes'), 'bad inProgress')

# --- (f) write_live_doc never writes an invalid document; size cap ---
td = tempfile.mkdtemp(prefix='dlive-w-')
try:
    p = os.path.join(td, 'desk-live.json')
    bad = copy.deepcopy(g); bad['symbols']['TSLA']['close'] = float('nan')
    try:
        D.write_live_doc(p, bad); raised = False
    except RuntimeError:
        raised = True
    chk('(f) invalid document raises and writes nothing', raised and not os.path.exists(p) and not os.path.exists(p + '.tmp'))
    old_cap = D.LIVE_MAX_BYTES; D.LIVE_MAX_BYTES = 100
    try:
        D.write_live_doc(p, g); raised = False
    except RuntimeError:
        raised = True
    D.LIVE_MAX_BYTES = old_cap
    chk('(f) oversized document refused', raised and not os.path.exists(p))
    nb = D.write_live_doc(p, g)
    chk('(f) good document written atomically, parses back equal', json.load(open(p)) == g and nb == os.path.getsize(p))
    # --validate-live on a hand-edited NaN file -> exit 1
    open(p, 'w').write(open(p).read().replace('"close":11.0', '"close":NaN', 1))
    code, out, err = run_cli(['--validate-live', p])
    chk('(f) --validate-live rejects a NaN token (exit 1)', code == 1, (out, err))
    open(p, 'w').write('{')
    code, out, err = run_cli(['--validate-live', p])
    chk('(f) --validate-live rejects unreadable JSON (exit 1)', code == 1)
finally:
    shutil.rmtree(td, ignore_errors=True)

# --- (g) stage 3 run type: only the after-close final run commits to main ---
import stock_weekly as SW
def rt(iso):
    return D.run_type(SW.parse_now(iso))
for iso, want, why in [
    ('2026-11-09T09:29:00-05:00', 'skip', 'Mon before open'),
    ('2026-11-09T09:30:00-05:00', 'intraday', 'Mon open'),
    ('2026-11-09T12:00:00-05:00', 'intraday', 'Mon midday'),
    ('2026-11-09T16:00:00-05:00', 'intraday', 'Mon 4:00 close, not settled'),
    ('2026-11-09T16:07:00-05:00', 'intraday', 'Mon 4:07 (GitHub cron :07) not settled'),
    ('2026-11-09T16:14:00-05:00', 'intraday', 'Mon 4:14'),
    ('2026-11-09T16:15:00-05:00', 'final', 'Mon 4:15 settle'),
    ('2026-11-09T16:30:00-05:00', 'final', 'Mon 4:30 window end'),
    ('2026-11-09T16:31:00-05:00', 'skip', 'Mon 4:31 outside'),
    ('2026-11-09T16:37:00-05:00', 'skip', 'Mon 4:37 (GitHub cron :37) outside'),
    ('2026-11-13T16:37:00-05:00', 'final', 'Fri 4:37 inside Friday extension'),
    ('2026-11-13T16:45:00-05:00', 'final', 'Fri 4:45 window end'),
    ('2026-11-13T16:46:00-05:00', 'skip', 'Fri 4:46 outside'),
    ('2026-07-06T16:20:00-04:00', 'final', 'EDT Mon 4:20'),
    ('2026-07-06T15:59:00-04:00', 'intraday', 'EDT Mon 3:59'),
    ('2026-11-14T16:20:00-05:00', 'skip', 'Saturday'),
    ('2026-11-15T16:20:00-05:00', 'skip', 'Sunday'),
    ('2026-11-26T16:20:00-05:00', 'skip', 'Thanksgiving holiday'),
    ('2026-12-25T12:00:00-05:00', 'skip', 'Christmas holiday'),
    ('2026-11-27T12:59:00-05:00', 'intraday', 'early close 27 Nov 12:59'),
    ('2026-11-27T13:14:00-05:00', 'intraday', 'early close 1:14'),
    ('2026-11-27T13:15:00-05:00', 'final', 'early close 1:15 settle'),
    ('2026-11-27T13:30:00-05:00', 'final', 'early close 1:30 window end'),
    ('2026-11-27T13:31:00-05:00', 'skip', 'early close 1:31 outside'),
    ('2026-11-27T16:20:00-05:00', 'skip', 'early close day 4:20 (not a final run)'),
    ('2026-11-25T16:20:00-05:00', 'final', '25 Nov full session 4:20'),
]:
    got = rt(iso)
    chk(f'(g) run type {why}: {want}', got == want, (iso, got))
    chk(f'(g) final_run agrees ({why})', D.final_run(SW.parse_now(iso)) == (want == 'final'))
for iso, run, fin in [('2026-11-09T16:20:00-05:00', '1', '1'), ('2026-11-09T11:00:00-05:00', '1', '0'),
                      ('2026-11-14T16:20:00-05:00', '0', '0'), ('2026-11-26T16:20:00-05:00', '0', '0')]:
    code, out, err = run_cli(['--gate', '--now', iso])
    lines = out.splitlines()
    chk(f'(g) --gate {iso} prints run={run} final={fin}', code == 0 and f'run={run}' in lines and f'final={fin}' in lines, out + err)
code, out, err = run_cli(['--gate', '--now', 'not-a-time'])
chk('(g) --gate with an unreadable time fails safe: run=0 final=0', code == 0 and 'run=0' in out.splitlines() and 'final=0' in out.splitlines(), out + err)

# --- (h) workflow wiring (static): final-only main commit, live publish never blocks it ---
import yaml
wf = yaml.safe_load(open(os.path.join(R, '.github', 'workflows', 'desk-intraday.yml')))
steps = wf['jobs']['desk-intraday']['steps']
by_id = {st.get('id'): (i, st) for i, st in enumerate(steps) if st.get('id')}
gate_run = by_id['gate'][1]['run']
chk('(h) gate step exports run= and final=', "grep -E '^(run|final)='" in gate_run, gate_run)
ref_i, ref = next((i, st) for i, st in enumerate(steps) if st.get('name', '').startswith('Refresh Desk weekly'))
chk('(h) refresh is --check-only unless final=1', '[ "${{ steps.gate.outputs.final }}" = "1" ] || ARGS="--check-only"' in ref['run'] and '$ARGS --live-json' in ref['run'], ref['run'])
li, live_st = by_id['live']
chk('(h) live publish is continue-on-error and runs on every gated run', live_st.get('continue-on-error') is True and live_st.get('if') == "steps.gate.outputs.run == '1'", live_st.get('if'))
pi, push_st = by_id['push']
chk('(h) main commit only on the final run', push_st.get('if') == "steps.gate.outputs.run == '1' && steps.gate.outputs.final == '1'", push_st.get('if'))
chk('(h) order: refresh < live publish < main commit', ref_i < li < pi)
chk('(h) main commit has no dependency on the live step outcome', 'steps.live' not in (push_st.get('if') or '') and 'steps.live' not in push_st['run'])
pages_st = by_id['pages'][1]
chk('(h) Pages build only after a main push', pages_st.get('if') == "steps.push.outputs.pushed == '1'", pages_st.get('if'))
chk('(h) schedule unchanged', wf[True]['schedule'] == [{'cron': '7,37 13-21 * * 1-5'}] if True in wf else wf['on']['schedule'] == [{'cron': '7,37 13-21 * * 1-5'}])

print(f'DESK_LIVE TESTS {n} FAIL {f}')
sys.exit(1 if f else 0)
