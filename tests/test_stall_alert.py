#!/usr/bin/env python3
"""Tests for tools/stall_alert.py (Python supercharge slice 5, Part 3).

Pure Python, no network, no browser. Synthetic histories with fixed
`--now` values, so every boundary is exact. Run:
python3 tests/test_stall_alert.py   exit 0 = all pass
"""
import copy
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'tools'))
import stall_alert as SA

R = []


def chk(name, ok, detail=''):
    R.append((name, bool(ok), detail))
    print('%-58s %s %s' % (name, 'PASS' if ok else 'FAIL', detail))


# Friday 2026-11-06 23:00 UTC = 18:00 ET, inside the fetch window.
NOW = '2026-11-06T23:00:00Z'


def hist(prov=None, tf=None):
    h = {'v': 1, 'closes': {'2026-11-06': {'BTC': 75877.0}},
         'btc_provisional': list(prov or [])}
    if tf is not None:
        h['tiingo_final'] = tf
    return h


def prices(updated='2026-11-06T22:55:00Z'):
    return {'updated': updated, 'stocks': {}}


def types(alerts):
    return [a['type'] for a in alerts]


def main():
    # 1. Clean run: no provisional dates, fresh prices -> no alerts.
    a = SA.detect(hist(), prices(), SA._parse_now(NOW))
    chk('clean run: no alerts', a == [])

    # 2. Recap stall: 2026-11-03 provisional, >48 h after its UTC day
    #    ended (day ends 2026-11-04T00:00Z; +48 h = 2026-11-06T00:00Z;
    #    now is 23:00Z) and not Tiingo-final -> recap_stalled, error.
    a = SA.detect(hist(prov=['2026-11-03']), prices(), SA._parse_now(NOW))
    chk('recap stall: recap_stalled alert',
        types(a) == ['recap_stalled']
        and a[0]['severity'] == 'error' and a[0]['since'] == '2026-11-03',
        str(a))

    # 3. Stall boundary: exactly 48 h -> NOT stalled; 48 h + 1 min -> stalled.
    #    2026-11-04's day ends 2026-11-05T00:00Z; +48 h = 2026-11-07T00:00Z.
    #    (prices.json is kept fresh in both, so only the recap check speaks.)
    a = SA.detect(hist(prov=['2026-11-04']),
                  prices('2026-11-06T23:55:00Z'),
                  SA._parse_now('2026-11-07T00:00:00Z'))
    chk('stall boundary exactly 48h: not stalled', a == [], str(a))
    a = SA.detect(hist(prov=['2026-11-04']),
                  prices('2026-11-06T23:56:00Z'),
                  SA._parse_now('2026-11-07T00:01:00Z'))
    chk('stall boundary 48h+1min: stalled',
        types(a) == ['recap_stalled'], str(a))

    # 4. Fresh provisional (< 48 h) -> not stalled.
    a = SA.detect(hist(prov=['2026-11-05']), prices(), SA._parse_now(NOW))
    chk('fresh provisional (<48h): not stalled', a == [], str(a))

    # 5. Tiingo-final date: in provisional AND tiingo_final -> info note
    #    only, NOT a recap_stalled alert (the alert notes the un-stall,
    #    it does not re-stall it).
    a = SA.detect(hist(prov=['2026-11-03'],
                       tf={'2026-11-03': {'BTC': 75799.14}}),
                  prices(), SA._parse_now(NOW))
    chk('tiingo-final: info note, not a stall',
        types(a) == ['recap_tiingo_final']
        and a[0]['severity'] == 'info', str(a))

    # 6. Tiingo-final date no longer provisional (Yahoo replaced it) ->
    #    no note at all.
    a = SA.detect(hist(prov=[],
                       tf={'2026-11-03': {'BTC': 75799.14}}),
                  prices(), SA._parse_now(NOW))
    chk('tiingo-final, no longer provisional: no note', a == [], str(a))

    # 7. A stalled date AND a Tiingo-final date together: both alerts,
    #    the Tiingo-final one info, the stalled one error.
    a = SA.detect(hist(prov=['2026-11-02', '2026-11-03'],
                       tf={'2026-11-03': {'BTC': 75799.14}}),
                  prices(), SA._parse_now(NOW))
    chk('stalled + tiingo-final together',
        types(a) == ['recap_stalled', 'recap_tiingo_final']
        and a[0]['severity'] == 'error'
        and a[1]['severity'] == 'info', str(a))

    # 8. Prices stall: in the fetch window, prices.json 90 min old.
    a = SA.detect(hist(), prices('2026-11-06T21:30:00Z'),
                  SA._parse_now(NOW))
    chk('prices 90 min old in window: prices_stale warning',
        types(a) == ['prices_stale']
        and a[0]['severity'] == 'warning', str(a))

    # 9. Prices fresh (30 min) in the window -> no prices alert.
    a = SA.detect(hist(), prices('2026-11-06T22:30:00Z'),
                  SA._parse_now(NOW))
    chk('prices 30 min old in window: no alert', a == [], str(a))

    # 10. Prices boundary: exactly 60 min -> not flagged; 61 min -> flagged.
    a = SA.detect(hist(), prices('2026-11-06T22:00:00Z'),
                  SA._parse_now(NOW))
    chk('prices exactly 60 min old: not flagged', a == [], str(a))
    a = SA.detect(hist(), prices('2026-11-06T21:59:00Z'),
                  SA._parse_now(NOW))
    chk('prices 61 min old: flagged',
        types(a) == ['prices_stale'], str(a))

    # 11. Prices old but OUTSIDE the fetch window -> no alert (normal).
    #     Friday 22:00 ET (2026-11-07T03:00:00Z) is past 21:30 ET.
    a = SA.detect(hist(), prices('2026-11-06T21:30:00Z'),
                  SA._parse_now('2026-11-07T03:00:00Z'))
    chk('prices old at night (outside window): no alert', a == [], str(a))
    #     Saturday 10:00 ET.
    a = SA.detect(hist(), prices('2026-11-06T21:30:00Z'),
                  SA._parse_now('2026-11-07T15:00:00Z'))
    chk('prices old on Saturday: no alert', a == [], str(a))

    # 12. No prices.json at all -> no prices alert (recap checks still run).
    a = SA.detect(hist(prov=['2026-11-03']), None, SA._parse_now(NOW))
    chk('no prices.json: recap stall still found, no prices alert',
        types(a) == ['recap_stalled'], str(a))

    # 13. Health update: existing fields preserved, alerts set, last_run
    #     preserved when present and set when absent.
    h = {'last_run': '2026-11-06T23:00:00Z', 'status': 'ok',
         'symbols': {'BTC': {'source': 'yahoo'}}}
    out = SA.update_health(h, [{'type': 'recap_stalled'}],
                           SA._parse_now(NOW))
    chk('health update preserves fields',
        out['status'] == 'ok' and out['symbols'] == h['symbols']
        and out['last_run'] == '2026-11-06T23:00:00Z'
        and out['alerts'] == [{'type': 'recap_stalled'}])
    out = SA.update_health({}, [], SA._parse_now(NOW))
    chk('health update sets last_run when absent',
        out['last_run'] == '2026-11-06T23:00:00Z' and out['alerts'] == [])
    #     ... and does not mutate the input.
    h2 = {'status': 'ok'}
    SA.update_health(h2, [{'type': 'x'}], SA._parse_now(NOW))
    chk('health update does not mutate input', 'alerts' not in h2)

    # 14. CLI end-to-end (subprocess).
    with tempfile.TemporaryDirectory() as tmp:
        hp = os.path.join(tmp, 'history.json')
        pp = os.path.join(tmp, 'prices.json')
        hh = os.path.join(tmp, 'health.json')
        json.dump(hist(prov=['2026-11-03']), open(hp, 'w'))
        json.dump(prices('2026-11-06T21:30:00Z'), open(pp, 'w'))
        json.dump({'last_run': '2026-11-06T23:00:00Z', 'status': 'ok'},
                  open(hh, 'w'))
        tool = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'tools', 'stall_alert.py')
        r = subprocess.run(
            [sys.executable, tool, '--history', hp, '--prices', pp,
             '--health', hh, '--out-health', hh, '--now', NOW],
            capture_output=True, text=True)
        out = json.load(open(hh))
        chk('CLI: exit 0 with alerts',
            r.returncode == 0, r.stderr.strip()[:200])
        chk('CLI: health keeps status, gains alerts',
            out['status'] == 'ok'
            and types(out['alerts']) == ['recap_stalled', 'prices_stale'],
            str(out.get('alerts')))
        chk('CLI: warning lines printed for the Actions log',
            '::warning::' in r.stdout, r.stdout[:300])
        # Clean run: exit 0, alerts [].
        json.dump(hist(), open(hp, 'w'))
        json.dump(prices('2026-11-06T22:55:00Z'), open(pp, 'w'))
        r = subprocess.run(
            [sys.executable, tool, '--history', hp, '--prices', pp,
             '--health', hh, '--out-health', hh, '--now', NOW],
            capture_output=True, text=True)
        out = json.load(open(hh))
        chk('CLI clean run: exit 0, alerts []',
            r.returncode == 0 and out['alerts'] == [],
            r.stderr.strip()[:200])
        # Malformed history -> exit 1.
        bad = os.path.join(tmp, 'bad.json')
        open(bad, 'w').write('{not json')
        r = subprocess.run(
            [sys.executable, tool, '--history', bad],
            capture_output=True, text=True)
        chk('CLI malformed history: exit 1', r.returncode == 1)
        # Missing --history -> exit 2.
        r = subprocess.run([sys.executable, tool],
                           capture_output=True, text=True)
        chk('CLI missing --history: exit 2', r.returncode == 2)

    # 15. r2: safe finite-only atomic writes. A health file carrying a
    #     non-finite value must exit 1 with the file byte-identical
    #     (never half-written), and no temp files may be left behind.
    with tempfile.TemporaryDirectory() as tmp:
        hp = os.path.join(tmp, 'history.json')
        hh = os.path.join(tmp, 'health.json')
        tool = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'tools', 'stall_alert.py')
        json.dump(hist(), open(hp, 'w'))
        open(hh, 'w').write('{"last_run": "2026-11-06T23:00:00Z", '
                            '"status": "ok", "score": NaN}')
        before = open(hh).read()
        r = subprocess.run(
            [sys.executable, tool, '--history', hp, '--health', hh,
             '--out-health', hh, '--now', NOW],
            capture_output=True, text=True)
        chk('CLI non-finite health.json: exit 1, file untouched',
            r.returncode == 1 and open(hh).read() == before,
            r.stderr.strip()[:200])
        chk('CLI non-finite health.json: no temp files left',
            [f for f in os.listdir(tmp)
             if f.startswith('.stall-alert-')] == [], str(os.listdir(tmp)))
        # ... and a clean write leaves no temp files either.
        json.dump({'last_run': '2026-11-06T23:00:00Z', 'status': 'ok'},
                  open(hh, 'w'))
        r = subprocess.run(
            [sys.executable, tool, '--history', hp, '--health', hh,
             '--out-health', hh, '--now', NOW],
            capture_output=True, text=True)
        out = json.load(open(hh))
        chk('CLI clean write: exit 0, fields kept, no temp files',
            r.returncode == 0 and out['status'] == 'ok'
            and out['alerts'] == []
            and [f for f in os.listdir(tmp)
                 if f.startswith('.stall-alert-')] == [],
            str(os.listdir(tmp)))

    bad = [x for x in R if not x[1]]
    print('\n%d checks, %d failed' % (len(R), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
