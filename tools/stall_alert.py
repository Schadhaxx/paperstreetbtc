#!/usr/bin/env python3
"""Stall alerts: recap stalled >48 h, Tiingo-final notes, prices.json stale.

A recap stall today is silent — the recap simply does not advance, and
nothing says so except btc_daily.py's ::error:: in the recap job log.
This tool is the notification for that stall (and for the other pipeline
stall), riding on existing channels only: an `alerts` field in health.json
(slice 1's file, data branch) plus ::warning:: lines in the Actions log.
It leaves account settings untouched — no notification or email setting
is changed, and no new alerting system is created.

What it detects (all from the published data, no fetching, no writing
to history.json or prices.json):

1. Recap stall (severity error): a BTC date in `btc_provisional` more
   than 48 h after its UTC day ended — the same clock btc_daily.py
   uses — that is NOT in `tiingo_final`. The recap cannot advance past
   it, and slice 2 has not un-stalled it (Tiingo disagreed, the key was
   missing, or the call budget was spent). This is the stall the alert
   exists for.
2. Tiingo-final note (severity info): a date in `tiingo_final` (still
   in `btc_provisional`). NOT a stall — the recap advanced on it. The
   alert notes the un-stall so a human knows the recap is running on a
   confirmed-but-not-Yahoo-final value; it does not re-stall it.
3. Prices stall (severity warning): `now` is inside the fetch window
   (weekday, 03:55-21:30 ET — the same gate prices.yml uses) and
   prices.json `updated` is more than 60 min old. The fetch job has
   not succeeded in over an hour. Outside the window, an old
   prices.json is normal (no runs at night/weekends) and is not
   flagged. The failed fetch run already emails; this is the durable
   record of it in health.json.

health.json: this tool owns the `alerts` field only. It reads an
existing health.json (written by slice 1's validate.py), sets its
`alerts` list, preserves every other field, and writes it back. When
there are no alerts, `alerts` is [] — the field is always present
after this tool runs, so a reader can tell the check ran. If no
health file is given, a minimal one is written (last_run + alerts).
Run this step LAST in the job — after the validate gate and after the
prices + health writes — so nothing after it overwrites the `alerts`
field. That order is the settled default: alerts merge last.

Writes are safe: health.json (and the optional alerts.json) are
serialised with allow_nan=False (non-finite numbers can never be
written) and published by write-to-temp + atomic rename, so a failed
run can never leave a partial file.

This is a REPORTER, not a gate: it never holds a run, never changes a
price, and exits 0 whether or not alerts were found. A finding is a
data event for a human. The recap stall's hard signal stays
btc_daily.py's ::error:: (exit 3); this tool prints ::warning:: for
all its alerts so its own step does not look failed.

Stdlib only, no network, no key.

CLI: python3 tools/stall_alert.py --history <history.json>
     [--prices <prices.json>] [--health <health.json>]
     [--out-health <health.json>] [--out <alerts.json>] [--now <ISO>]
Exit 0 = scan complete (alerts or not), 1 = input unreadable /
unwritable, 2 = usage error.
"""
import datetime as dt
import json
import os
import sys
import tempfile
import zoneinfo

STALL_H = 48
PRICES_STALE_MIN = 60
# Fetch window (matches the prices.yml gate): weekday, 03:55-21:30 ET.
FETCH_START_MIN = 235   # 03:55
FETCH_END_MIN = 1290    # 21:30
ET = zoneinfo.ZoneInfo('America/New_York')


def _parse_now(s):
    if s is None:
        return dt.datetime.now(dt.timezone.utc)
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00'))


def _stall_deadline(d):
    """btc_daily.py's clock: the date's UTC day ends at midnight UTC the
    next day; the stall is 48 h after that."""
    return (dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc)
            + dt.timedelta(days=1))


def detect(history, prices, now):
    """Return the alerts list for this run. Pure: reads only."""
    alerts = []
    prov = set(history.get('btc_provisional') or [])
    tf = history.get('tiingo_final') or {}
    # 1. Recap stall: provisional >48 h after its UTC day ended, and
    #    slice 2 has not frozen it.
    for d in sorted(prov):
        if d in tf:
            continue
        if now - _stall_deadline(d) > dt.timedelta(hours=STALL_H):
            alerts.append({
                'type': 'recap_stalled',
                'severity': 'error',
                'since': d,
                'detail': ('BTC %s still on a fallback source more than '
                           '%d h after its UTC day ended (Yahoo final '
                           'bar never arrived); the recap cannot advance '
                           'past it. Tiingo did not confirm it '
                           '(disagreed, no key, or budget spent).'
                           % (d, STALL_H))})
    # 2. Tiingo-final note: the recap advanced on a confirmed value.
    #    Informational only — this is not a stall.
    for d in sorted(tf.keys()):
        if d not in prov:
            continue
        alerts.append({
            'type': 'recap_tiingo_final',
            'severity': 'info',
            'since': d,
            'detail': ('Recap advanced on a Tiingo-final value for %s '
                       '(confirmed by Tiingo, Yahoo final bar pending).'
                       % d)})
    # 3. Prices stall: inside the fetch window and prices.json is old.
    if isinstance(prices, dict):
        upd = prices.get('updated')
        upd_dt = None
        if isinstance(upd, str):
            try:
                upd_dt = dt.datetime.fromisoformat(
                    upd.replace('Z', '+00:00'))
            except ValueError:
                upd_dt = None
        if upd_dt is not None:
            now_et = now.astimezone(ET)
            mins = now_et.hour * 60 + now_et.minute
            in_window = (now_et.weekday() <= 4
                         and FETCH_START_MIN <= mins <= FETCH_END_MIN)
            age_min = (now - upd_dt).total_seconds() / 60
            if in_window and age_min > PRICES_STALE_MIN:
                alerts.append({
                    'type': 'prices_stale',
                    'severity': 'warning',
                    'since': upd,
                    'detail': ('prices.json last updated %s, %.0f min '
                               'ago, during the fetch window; the fetch '
                               'job has not succeeded in over an hour.'
                               % (upd, age_min))})
    return alerts


def update_health(health, alerts, now):
    """Return a health dict with the alerts field set, preserving every
    other field. `last_run` is set only if the file had none."""
    out = dict(health or {})
    out['alerts'] = alerts
    if 'last_run' not in out:
        out['last_run'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    return out


def _atomic_write_json(path, data):
    """Write JSON safely: finite numbers only, atomically.

    The data is serialised first with allow_nan=False, so a NaN or
    Infinity anywhere raises BEFORE the target is touched; then it is
    written to a temp file in the same directory, fsynced, and moved
    over the target with os.replace. A failed write can never leave a
    partial file, and no non-finite number can ever be published.
    Existing health fields are preserved because the caller passes the
    full merged dict (see update_health) — this helper only writes it.
    """
    text = json.dumps(data, indent=2, sort_keys=True,
                      allow_nan=False) + '\n'
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.stall-alert-',
                               suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _parse_args(argv):
    history = None
    prices = None
    health = None
    out_health = None
    out = None
    now_s = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--history' and i + 1 < len(argv):
            history = argv[i + 1]
            i += 2
        elif a == '--prices' and i + 1 < len(argv):
            prices = argv[i + 1]
            i += 2
        elif a == '--health' and i + 1 < len(argv):
            health = argv[i + 1]
            i += 2
        elif a == '--out-health' and i + 1 < len(argv):
            out_health = argv[i + 1]
            i += 2
        elif a == '--out' and i + 1 < len(argv):
            out = argv[i + 1]
            i += 2
        elif a == '--now' and i + 1 < len(argv):
            now_s = argv[i + 1]
            i += 2
        else:
            return None
    if not history:
        return None
    return {'history': history, 'prices': prices, 'health': health,
            'out_health': out_health or health, 'out': out,
            'now': now_s}


def main(argv):
    args = _parse_args(argv)
    if args is None:
        print('usage: stall_alert.py --history <history.json> '
              '[--prices <prices.json>] [--health <health.json>] '
              '[--out-health <health.json>] [--out <alerts.json>] '
              '[--now <ISO>]', file=sys.stderr)
        return 2
    try:
        now = _parse_now(args['now'])
    except ValueError as e:
        print(f'stall-alert: bad --now: {e}', file=sys.stderr)
        return 2
    try:
        history = json.load(open(args['history']))
    except Exception as e:
        print(f'stall-alert: cannot read {args["history"]}: '
              f'{type(e).__name__}: {e}', file=sys.stderr)
        return 1
    if not isinstance(history, dict):
        print('stall-alert: history.json is not an object', file=sys.stderr)
        return 1
    prices = None
    if args['prices']:
        try:
            prices = json.load(open(args['prices']))
        except Exception as e:
            print(f'stall-alert: cannot read {args["prices"]}: '
                  f'{type(e).__name__}: {e}', file=sys.stderr)
            return 1
    health = {}
    if args['health']:
        try:
            health = json.load(open(args['health']))
        except FileNotFoundError:
            health = {}
        except Exception as e:
            print(f'stall-alert: cannot read {args["health"]}: '
                  f'{type(e).__name__}: {e}', file=sys.stderr)
            return 1
        if not isinstance(health, dict):
            print('stall-alert: health.json is not an object',
                  file=sys.stderr)
            return 1
    alerts = detect(history, prices, now)
    for a in alerts:
        print(f'::warning::stall-alert [{a["type"]}]: {a["detail"]}')
    if not alerts:
        print('stall-alert: no stalls')
    if args['out']:
        try:
            _atomic_write_json(args['out'], alerts)
        except Exception as e:
            print(f'stall-alert: cannot write {args["out"]}: '
                  f'{type(e).__name__}: {e}', file=sys.stderr)
            return 1
    if args['out_health']:
        try:
            _atomic_write_json(args['out_health'],
                               update_health(health, alerts, now))
        except Exception as e:
            print(f'stall-alert: cannot write {args["out_health"]}: '
                  f'{type(e).__name__}: {e}', file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
