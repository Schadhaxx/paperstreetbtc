#!/usr/bin/env python3
"""BTC trend-support (floor) test pack.

Always checks the reference against fixtures/. With --impl / --repo /
FLOOR_IMPL / FLOOR_REPO, also asserts Pepper's tools/ta_floor.py matches.

usage:
  python3 test_floor_pack.py --impl reference_floor.py
  python3 test_floor_pack.py --repo /path/to/paperstreetbtc
  FLOOR_IMPL=tools/ta_floor.py python3 test_floor_pack.py
exit 0 = all pass
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import os
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / 'fixtures'
sys.path.insert(0, str(HERE))
import reference_floor as REF  # noqa: E402

n = 0
f = 0
TARGET = 'reference'


def chk(name, ok, info=''):
    global n, f
    n += 1
    if ok:
        print('PASS', f'[{TARGET}]', name)
    else:
        f += 1
        extra = '' if info == '' else '  ' + (info if isinstance(info, str) else json.dumps(info, default=str))
        print('FAIL', f'[{TARGET}]', name + extra)


def close(a, b, tol=0.005):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def load_json(name):
    return json.loads((FIX / name).read_text())


def load_module(path):
    path = Path(path).resolve()
    spec = importlib.util.spec_from_file_location('floor_impl', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, path


def get(mod, *names):
    for name in names:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn
    return None


def ev_of(mod, payload, as_of=None):
    fn = get(mod, 'evaluate_break', 'evaluateBreak')
    if fn is None:
        return None, 'missing evaluate_break'
    try:
        sig = inspect.signature(fn)
        if len(sig.parameters) >= 2:
            return fn(payload, as_of), None
        return fn(payload), None
    except TypeError:
        return fn(payload, as_of), None


def broken_of(mod, payload, as_of=None):
    ev, err = ev_of(mod, payload, as_of)
    if ev is not None and isinstance(ev, dict) and 'broken' in ev:
        return ev['broken'], ev, None
    fn = get(mod, 'floor_broken', 'broken')
    if fn is None:
        return None, ev, err or 'missing floor_broken / evaluate_break'
    try:
        sig = inspect.signature(fn)
        if len(sig.parameters) >= 2:
            return fn(payload, as_of), ev, None
        return fn(payload), ev, None
    except TypeError:
        return fn(payload, as_of), ev, None


def display_of(mod, payload, as_of=None):
    fn = get(mod, 'display_copy', 'floor_display', 'display')
    if fn is None:
        return None, 'missing display_copy / floor_display / display'
    try:
        sig = inspect.signature(fn)
        if len(sig.parameters) >= 2:
            return fn(payload, as_of), None
        return fn(payload), None
    except TypeError:
        return fn(payload, as_of), None


def week_complete_of(mod, week_start, as_of):
    fn = get(mod, 'is_week_complete', 'isWeekComplete')
    if fn is None:
        return None, 'missing is_week_complete'
    return fn(week_start, as_of), None


def week_monday_of(mod, ts):
    fn = get(mod, 'week_monday', 'weekMonday')
    if fn is None:
        return None, 'missing week_monday'
    val = fn(ts)
    if hasattr(val, 'isoformat'):
        # datetime.date or datetime
        if hasattr(val, 'date') and not isinstance(val, date):
            # datetime
            from datetime import datetime as _dt
            if isinstance(val, _dt):
                return val.date().isoformat(), None
        return val.isoformat()[:10], None
    return str(val)[:10], None


def floor_at_of(mod, payload, ds):
    fn = get(mod, 'floor_at_payload', 'at')
    if fn is not None:
        return fn(payload, ds)
    fn = get(mod, 'floor_at', 'floorAt')
    if fn is None:
        return 'MISSING'
    sig = inspect.signature(fn)
    if len(sig.parameters) >= 4:
        a = payload['anchor']
        return fn(a['date'], a['low'], payload['slopePerWeek'], ds)
    return fn(payload, ds)


COMPARE_KEYS = (
    'broken', 'lastCompletedWeek', 'lastCompletedSunday', 'lastCompletedClose',
    'floorAtLastCompleted', 'pctAtLastCompleted', 'inProgressWeek',
    'inProgressClose', 'inProgressPct', 'inProgressTriggersBreak',
    'maxUnderPct', 'floorNow', 'breakTrigger', 'dashInProgress', 'lineIsRed',
)


def chk_eval(label, got, exp, tol_money=0.005, tol_pct=0.05):
    if got is None:
        chk(label + ': evaluate_break present', False, 'missing evaluate_break')
        return
    chk(label + ': broken', got.get('broken') is exp['broken'],
        f"got {got.get('broken')} want {exp['broken']}")
    for key in COMPARE_KEYS:
        if key not in exp:
            continue
        want, have = exp[key], got.get(key)
        if key == 'broken' or isinstance(want, bool) or want is None or have is None:
            if key == 'broken':
                continue
            chk(f'{label}: {key}', have == want, f'got {have} want {want}')
        elif key.endswith('Pct') or key == 'maxUnderPct':
            chk(f'{label}: {key}', close(have, want, tol_pct), f'got {have} want {want}')
        elif isinstance(want, (int, float)):
            chk(f'{label}: {key}', close(have, want, tol_money), f'got {have} want {want}')
        else:
            chk(f'{label}: {key}', have == want, f'got {have} want {want}')


def chk_display(label, got, exp, err=None):
    if got is None:
        chk(label + ': display_copy present', False, err or 'missing')
        return
    for key in ('label', 'asOf', 'source', 'breakRule', 'brokenNote'):
        chk(f'{label}: display.{key}', got.get(key) == exp[key],
            f'got {got.get(key)!r} want {exp[key]!r}')


def run_reference_and_impl(mod, real, completed, inprog, boundary, weekb):
    # --- real 26 Nov ---
    ev, err = ev_of(mod, real, real['asOf'])
    if ev is None and mod is REF:
        ev = REF.evaluate_break(real, real['asOf'])
        err = None
    chk_eval('real_26nov', ev, real['expected'])
    br, _ev, berr = broken_of(mod, real, real['asOf'])
    chk('real_26nov: floor_broken is False (in-progress Thu close must not break)',
        br is False, f'got {br} {berr or ""}')
    # Stale broken=true flag must be ignored when weeks are present.
    stale = dict(real)
    stale['broken'] = True
    br_stale, _, _ = broken_of(mod, stale, real['asOf'])
    chk('real_26nov: stale broken=true flag is ignored',
        br_stale is False, f'got {br_stale}')
    disp, derr = display_of(mod, real, real['asOf'])
    chk_display('real_26nov', disp, real['expected']['display'], derr)
    for ds, want in real['expected']['floorAt'].items():
        have = floor_at_of(mod, real, ds)
        if have == 'MISSING':
            chk(f'real_26nov: floor_at({ds})', False, 'missing floor_at')
            break
        if want is None:
            chk(f'real_26nov: floor_at({ds}) is null', have is None, have)
        else:
            chk(f'real_26nov: floor_at({ds})', close(have, want, 0.05),
                f'got {have} want {want}')

    # --- completed-week break ---
    ev, _ = ev_of(mod, completed, completed['asOf'])
    if ev is None and mod is REF:
        ev = REF.evaluate_break(completed)
    chk_eval('completed_week_break', ev, completed['expected'])
    br, _, _ = broken_of(mod, completed, completed['asOf'])
    chk('completed_week_break: floor_broken is True', br is True, f'got {br}')
    disp, derr = display_of(mod, completed, completed['asOf'])
    chk_display('completed_week_break', disp, completed['expected']['display'], derr)
    if disp:
        chk('completed_week_break: visible broken note (not only a colour change)',
            isinstance(disp.get('brokenNote'), str) and len(disp['brokenNote']) > 0,
            disp.get('brokenNote'))

    # --- in-progress-only dip ---
    ev, _ = ev_of(mod, inprog, inprog['asOf'])
    if ev is None and mod is REF:
        ev = REF.evaluate_break(inprog)
    chk_eval('in_progress_only_dip', ev, inprog['expected'])
    br, _, _ = broken_of(mod, inprog, inprog['asOf'])
    chk('in_progress_only_dip: floor_broken is False', br is False, f'got {br}')
    disp, derr = display_of(mod, inprog, inprog['asOf'])
    chk_display('in_progress_only_dip', disp, inprog['expected']['display'], derr)

    # --- -2.0% boundary ---
    for i, case in enumerate(boundary['cases']):
        payload = {**boundary, 'asOf': case['asOf'], 'weeks': case['weeks']}
        ev, _ = ev_of(mod, payload, case['asOf'])
        if ev is None and mod is REF:
            ev = REF.evaluate_break(payload, case['asOf'])
        tag = f'boundary[{i} close={case["weeks"][-1][1]} asOf={case["asOf"]}]'
        chk(f'{tag}: broken', ev is not None and ev.get('broken') is case['expected']['broken'],
            None if ev is None else ev.get('broken'))

    # --- week boundary ---
    for case in weekb['cases']:
        payload = {**weekb, 'asOf': case['asOf'], 'weeks': case['weeks']}
        complete, cerr = week_complete_of(mod, weekb['weekUnderTest'], case['asOf'])
        chk(f'week_boundary asOf={case["asOf"]}: is_week_complete',
            cerr is None and complete is case['expectedComplete'],
            cerr or f'got {complete} want {case["expectedComplete"]}')
        mon, merr = week_monday_of(mod, case['asOf'])
        chk(f'week_boundary asOf={case["asOf"]}: week_monday',
            merr is None and mon == case['expectedMondayOfAsOf'],
            merr or f'got {mon} want {case["expectedMondayOfAsOf"]}')
        br, _, berr = broken_of(mod, payload, case['asOf'])
        chk(f'week_boundary asOf={case["asOf"]}: broken',
            berr is None and br is case['expected']['broken'],
            berr or f'got {br} want {case["expected"]["broken"]}')


def call_compute_floor(mod, dates, closes, lows, last_date):
    fn = get(mod, 'compute_floor')
    if fn is None:
        return None, 'missing compute_floor'
    sig = inspect.signature(fn)
    names = list(sig.parameters)
    kwargs = {}
    if 'last_date' in sig.parameters:
        kwargs['last_date'] = last_date
    elif 'as_of' in sig.parameters:
        kwargs['as_of'] = last_date
    elif len(names) >= 4 and names[3] not in ('args', 'kwargs'):
        return fn(dates, closes, lows, last_date), None
    return fn(dates, closes, lows, **kwargs), None


def run_compute_floor_on_daily(mod, repo: Path, real):
    daily = repo / 'assets' / 'data' / 'btc-daily.json'
    if not daily.is_file():
        chk('compute_floor vs btc-daily.json', False, f'not found: {daily}')
        return
    if get(mod, 'load_daily') is None or get(mod, 'build_weeks') is None or get(mod, 'compute_floor') is None:
        chk('compute_floor + build_weeks + load_daily present', False, 'Pepper job helpers missing')
        return
    rows, _src = mod.load_daily(str(daily))
    dates, closes, lows, last_date = mod.build_weeks(rows)
    out, err = call_compute_floor(mod, dates, closes, lows, last_date)
    if out is None:
        chk('compute_floor runs on btc-daily.json', False, err)
        return
    exp = real['expected']
    is_26nov = str(dates[-1]) == '2026-11-23' and str(last_date) == '2026-11-26'
    if not is_26nov:
        chk('compute_floor vs btc-daily.json: snapshot is 26 Nov 2026',
            False, f'last_week={dates[-1]} last_date={last_date} (frozen numbers skipped)')
        return
    chk('compute_floor: broken is False (in-progress week must not break)',
        out.get('broken') is False, out.get('broken'))
    chk('compute_floor: floorNow still $62,440.91 (line includes the in-progress week)',
        close(out.get('floorNow'), 62440.91, 0.05), out.get('floorNow'))
    chk('compute_floor: lastCompletedClose $61,161.91',
        'lastCompletedClose' in out and close(out.get('lastCompletedClose'), 61161.91, 0.05),
        out.get('lastCompletedClose', 'MISSING'))
    chk('compute_floor: maxUnderPct is the completed-week max (~-1.70), not the in-progress -3.12',
        'maxUnderPct' in out and close(out.get('maxUnderPct'), exp['maxUnderPct'], 0.05),
        out.get('maxUnderPct', 'MISSING'))


def discover_repo(cli_repo):
    raw = os.environ.get('FLOOR_REPO') or cli_repo
    if raw:
        p = Path(raw).resolve()
        return p if p.is_dir() else None
    here = HERE
    for cand in (
        here / 'tools' / 'ta_floor.py',
        here.parent / 'tools' / 'ta_floor.py',
        here.parent.parent / 'tools' / 'ta_floor.py',
    ):
        if cand.is_file() and (cand.parents[1] / 'assets' / 'data').is_dir():
            return cand.parents[1]
    return None


def discover_impl(cli_impl, repo):
    raw = os.environ.get('FLOOR_IMPL') or cli_impl
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        return p
    if repo:
        p = Path(repo) / 'tools' / 'ta_floor.py'
        if p.is_file():
            return p
    return None


def main():
    global TARGET
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--impl', default=None, help='Path to Pepper tools/ta_floor.py (or this reference)')
    ap.add_argument('--repo', default=None, help='paperstreetbtc repo root')
    ap.add_argument('--ref-only', action='store_true', help='Skip Pepper; only self-check the reference')
    args = ap.parse_args()

    real = load_json('real_26nov.json')
    completed = load_json('completed_week_break.json')
    inprog = load_json('in_progress_only_dip.json')
    boundary = load_json('boundary_minus_2pct.json')
    weekb = load_json('week_boundary_sun_mon.json')

    TARGET = 'reference'
    run_reference_and_impl(REF, real, completed, inprog, boundary, weekb)

    if args.ref_only:
        print('FLOOR PACK PY TESTS', n, 'FAIL', f, '(reference only)')
        sys.exit(1 if f else 0)

    repo = discover_repo(args.repo)
    impl_path = discover_impl(args.impl, repo)
    if impl_path is None:
        print('FLOOR PACK PY TESTS', n, 'FAIL', f, '(reference only; pass --impl or --repo to check Pepper)')
        sys.exit(1 if f else 0)

    TARGET = str(impl_path)
    try:
        mod, impl_path = load_module(impl_path)
    except Exception as e:
        chk(f'import {impl_path}', False, str(e))
        print('FLOOR PACK PY TESTS', n, 'FAIL', f)
        sys.exit(1)

    # If the "impl" is this reference file, the second pass is a self-match.
    run_reference_and_impl(mod, real, completed, inprog, boundary, weekb)
    if repo and (Path(repo) / 'assets' / 'data' / 'btc-daily.json').is_file():
        run_compute_floor_on_daily(mod, Path(repo), real)
    elif get(mod, 'compute_floor') and get(mod, 'load_daily'):
        # impl is ta_floor.py; infer repo from the file path
        guessed = Path(impl_path).resolve().parents[1]
        if (guessed / 'assets' / 'data' / 'btc-daily.json').is_file():
            run_compute_floor_on_daily(mod, guessed, real)

    print('FLOOR PACK PY TESTS', n, 'FAIL', f)
    sys.exit(1 if f else 0)


if __name__ == '__main__':
    main()
