#!/usr/bin/env python3
"""Tests for tools/screener_alert.py — the recap job's fail-loud step.

Fixture-based, no network: the GitHub lookup takes a stub _gh_api.
Run: python3 tests/test_screener_alert.py
"""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import screener_alert as sa
import screener_daily as sd

LOG_NULL = (
    'FAILED TSLA: TSLA: null close on 2026-11-27 — refusing to skip or fill\n'
    'FAILED DIA: DIA: null close on 2026-11-27 — refusing to skip or fill\n'
    'screener-daily: skipped TSLA, DIA (2 failed, 19 written)\n'
)
LOG_CLEAN = 'screener-daily wrote 21 file(s) -> /tmp/screener-daily\n'
LOG_FETCH_FAIL = (
    'FAILED TSLA: Yahoo fetch failed (URLError: timeout)\n'
    'FAILED DIA: Yahoo fetch failed (URLError: timeout)\n'
    'FAILED AAPL: Yahoo fetch failed (URLError: timeout)\n'
    'screener-daily: skipped TSLA, DIA, AAPL (3 failed, 18 written)\n'
)
LOG_MISSING_SESSIONS = (
    'screener-daily: missing 1 completed session(s)\n'
    'FAILED TSLA: TSLA: missing 1 completed session(s)\n'
)
# Fixed "now" for the no-null-close path: Fri 27 Nov 2026 21:09 ET, so
# cutoff_date is 2026-11-27.
NOW = dt.datetime(2026, 11, 27, 21, 9, tzinfo=sd.ET)


def write_daily(tmp, key, asof, close=100.0):
    fname = sa.FILEMAP[key]
    doc = {'asOf': asof, 'days': [{'date': asof, 'close': close}]}
    with open(os.path.join(tmp, fname), 'w') as f:
        json.dump(doc, f)


def write_log(tmp, text):
    path = os.path.join(tmp, 'screener-daily.log')
    with open(path, 'w') as f:
        f.write(text)
    return path


class TestParse(unittest.TestCase):
    def test_parse_list(self):
        self.assertEqual(sa.parse_list('TSLA, PLTR,TSLA'), ['PLTR', 'TSLA'])
        self.assertEqual(sa.parse_list(''), [])
        self.assertEqual(sa.parse_list(None), [])

    def test_session_date_from_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write_log(tmp, LOG_NULL)
            self.assertEqual(sa.session_date_from_log(p),
                             dt.date(2026, 11, 27))
            p2 = write_log(tmp, LOG_CLEAN)
            self.assertIsNone(sa.session_date_from_log(p2))
            self.assertIsNone(sa.session_date_from_log('/nonexistent.log'))

    def test_filemap_matches_screener_daily(self):
        # The alert tool's filename map must stay in sync with the
        # screener's ALL dict; a rename in one place fails here.
        for key, spec in sd.ALL.items():
            self.assertEqual(sa.FILEMAP[key], spec[5], key)
        self.assertEqual(set(sa.FILEMAP), set(sd.ALL))


class TestCoverage(unittest.TestCase):
    def test_covered_when_file_holds_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'TSLA', '2026-11-27')
            write_daily(tmp, 'DIA', '2026-11-27')
            log = write_log(tmp, LOG_NULL)
            self.assertEqual(
                sa.uncovered(['TSLA', 'DIA'], [], dt.date(2026, 11, 27), tmp),
                [])

    def test_uncovered_when_file_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'TSLA', '2026-11-25')
            write_daily(tmp, 'DIA', '2026-11-27')
            self.assertEqual(
                sa.uncovered(['TSLA', 'DIA'], [], dt.date(2026, 11, 27), tmp),
                ['TSLA'])

    def test_uncovered_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                sa.uncovered(['TSLA'], [], dt.date(2026, 11, 27), tmp),
                ['TSLA'])

    def test_stale_key_covered_same_way(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'VIX', '2026-11-27')
            self.assertEqual(
                sa.uncovered([], ['VIX'], dt.date(2026, 11, 27), tmp), [])
            write_daily(tmp, 'VIX', '2026-11-25')
            self.assertEqual(
                sa.uncovered([], ['VIX'], dt.date(2026, 11, 27), tmp),
                ['VIX'])

    def test_newest_asof(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'TSLA', '2026-11-27')
            write_daily(tmp, 'VIX', '2026-11-25')
            self.assertEqual(sa.newest_asof(tmp), dt.date(2026, 11, 27))
            self.assertIsNone(sa.newest_asof('/nonexistent-dir'))


class TestSignature(unittest.TestCase):
    def test_signature_canonical(self):
        s1 = sa.signature(['TSLA', 'DIA'], [], dt.date(2026, 11, 27))
        s2 = sa.signature(['DIA', 'TSLA'], [], dt.date(2026, 11, 27))
        self.assertEqual(s1, s2)
        self.assertIn('session=2026-11-27', s1)
        s3 = sa.signature(['TSLA', 'DIA'], [], dt.date(2026, 11, 30))
        self.assertNotEqual(s1, s3)

    def test_parse_alert_message_new_format(self):
        msg = ('::error::screener-daily failed for: DIA, TSLA; '
               'ind-daily stale: ; session: 2026-11-27. The recap still '
               'published; see the screener-daily step log.')
        parsed = sa.parse_alert_message(msg)
        self.assertEqual(parsed, (['DIA', 'TSLA'], [], '2026-11-27'))

    def test_parse_alert_message_old_format(self):
        msg = ('screener-daily failed for: TSLA, DIA; ind-daily stale: . '
               'The recap still published; see the screener-daily step log.')
        parsed = sa.parse_alert_message(msg)
        self.assertEqual(parsed[0], ['DIA', 'TSLA'])
        self.assertEqual(parsed[1], [])
        self.assertIsNone(parsed[2])

    def test_parse_alert_message_not_an_alert(self):
        self.assertIsNone(sa.parse_alert_message('Process completed.'))
        self.assertIsNone(sa.parse_alert_message(''))


def stub_gh_api_factory(runs, per_run):
    """Fake gh_api: `runs` is the workflow-runs list; `per_run` maps a
    run id to (jobs, annotations) for that run."""
    def fake(path, token):
        if 'workflows/prices.yml/runs' in path:
            return {'workflow_runs': runs}
        if '/jobs?' in path:
            rid = int(path.split('/actions/runs/')[1].split('/')[0])
            return {'jobs': per_run.get(rid, ([], []))[0]}
        if '/annotations' in path:
            cid = int(path.split('/check-runs/')[1].split('/')[0])
            for rid, (jobs, anns) in per_run.items():
                if any(j.get('id') == cid for j in jobs):
                    return anns
            return []
        raise AssertionError('unexpected path %s' % path)
    return fake


def alert_ann(failed='DIA, TSLA', stale='', session='2026-11-27'):
    return [{'message': (
        'screener-daily failed for: %s; ind-daily stale: %s; '
        'session: %s. The recap still published.' % (failed, stale, session))}]


class TestDecide(unittest.TestCase):
    def _setup(self, tmp, asof='2026-11-27'):
        write_daily(tmp, 'TSLA', asof)
        write_daily(tmp, 'DIA', asof)
        return write_log(tmp, LOG_NULL)

    def test_quiet_when_files_hold_session(self):
        # (b) Tonight's case, once the fallback has run: the gen failed
        # but the published files already hold Nov 27 -- stay quiet.
        with tempfile.TemporaryDirectory() as tmp:
            log = self._setup(tmp)
            code, msg = sa.decide('TSLA, DIA', '', log, tmp)
            self.assertEqual(code, 0)
            self.assertIn('quiet', msg)

    def test_red_when_real_miss_and_no_previous(self):
        # Files behind the session, no previous run to compare -- alert.
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'TSLA', '2026-11-25')
            write_daily(tmp, 'DIA', '2026-11-25')
            log = write_log(tmp, LOG_NULL)
            fake = stub_gh_api_factory([], {})
            code, msg = sa.decide('TSLA, DIA', '', log, tmp,
                                  repo='o/r', run_id=100, token='t',
                                  _gh_api=fake)
            self.assertEqual(code, 1)
            self.assertIn('::error::', msg)

    def test_quiet_on_identical_repeat(self):
        # (a) Previous run alerted on the identical signature -- repeat.
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'TSLA', '2026-11-25')
            write_daily(tmp, 'DIA', '2026-11-25')
            log = write_log(tmp, LOG_NULL)
            fake = stub_gh_api_factory(
                [{'id': 99, 'status': 'completed'}],
                {99: ([{'id': 7, 'name': 'recap'}], alert_ann())})
            code, msg = sa.decide('TSLA, DIA', '', log, tmp,
                                  repo='o/r', run_id=100, token='t',
                                  _gh_api=fake)
            self.assertEqual(code, 0)
            self.assertIn('repeat', msg)

    def test_quiet_when_previous_run_quiet_but_earlier_alert_matches(self):
        # The walk-back must skip quiet runs: run 99 is quiet (no alert
        # line), run 98 alerted on the identical signature -- still a
        # repeat. Without the walk-back the chain would break here.
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'TSLA', '2026-11-25')
            write_daily(tmp, 'DIA', '2026-11-25')
            log = write_log(tmp, LOG_NULL)
            fake = stub_gh_api_factory(
                [{'id': 99, 'status': 'completed'},
                 {'id': 98, 'status': 'completed'}],
                {99: ([{'id': 7, 'name': 'recap'}], []),
                 98: ([{'id': 6, 'name': 'recap'}], alert_ann())})
            code, msg = sa.decide('TSLA, DIA', '', log, tmp,
                                  repo='o/r', run_id=100, token='t',
                                  _gh_api=fake)
            self.assertEqual(code, 0)
            self.assertIn('repeat', msg)

    def test_red_when_most_recent_alert_differs(self):
        # The most recent alert (run 98) was for a different session;
        # run 99 was quiet. This is a new incident -- alert.
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'TSLA', '2026-11-25')
            write_daily(tmp, 'DIA', '2026-11-25')
            log = write_log(tmp, LOG_NULL)
            fake = stub_gh_api_factory(
                [{'id': 99, 'status': 'completed'},
                 {'id': 98, 'status': 'completed'}],
                {99: ([{'id': 7, 'name': 'recap'}], []),
                 98: ([{'id': 6, 'name': 'recap'}],
                      alert_ann(session='2026-11-26'))})
            code, _ = sa.decide('TSLA, DIA', '', log, tmp,
                                repo='o/r', run_id=100, token='t',
                                _gh_api=fake)
            self.assertEqual(code, 1)

    def test_red_when_new_session_same_symbols(self):
        # Same symbols failing, but a NEW session date -- not a repeat.
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'TSLA', '2026-11-27')
            write_daily(tmp, 'DIA', '2026-11-27')
            log = write_log(tmp, LOG_NULL.replace('2026-11-27',
                                                  '2026-11-30'))
            fake = stub_gh_api_factory(
                [{'id': 99, 'status': 'completed'}],
                {99: ([{'id': 7, 'name': 'recap'}], alert_ann())})
            code, msg = sa.decide('TSLA, DIA', '', log, tmp,
                                  repo='o/r', run_id=100, token='t',
                                  _gh_api=fake)
            # Files hold Nov 27 but the failing session is Nov 30, so the
            # files do NOT hold the session -- a real miss, and the
            # previous alert was for a different session, so it goes red.
            self.assertEqual(code, 1)

    def test_red_when_previous_alert_old_format(self):
        # Previous alert predates the session date: cannot confirm a
        # repeat, so fail open and alert.
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'TSLA', '2026-11-25')
            log = write_log(tmp, LOG_NULL)
            anns = [{'message': (
                'screener-daily failed for: TSLA, DIA; ind-daily stale: . '
                'The recap still published.')}]
            fake = stub_gh_api_factory(
                [{'id': 99, 'status': 'completed'}],
                {99: ([{'id': 7, 'name': 'recap'}], anns)})
            code, _ = sa.decide('TSLA, DIA', '', log, tmp,
                                repo='o/r', run_id=100, token='t',
                                _gh_api=fake)
            self.assertEqual(code, 1)

    def test_red_when_api_lookup_fails(self):
        # Lookup error -> fail open and alert.
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'TSLA', '2026-11-25')
            log = write_log(tmp, LOG_NULL)

            def boom(path, token):
                raise RuntimeError('network down')

            code, _ = sa.decide('TSLA, DIA', '', log, tmp,
                                repo='o/r', run_id=100, token='t',
                                _gh_api=boom)
            self.assertEqual(code, 1)

    def test_red_when_no_api_credentials(self):
        # No repo/run/token (e.g. local run): no repeat check, alert on
        # a real miss.
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'TSLA', '2026-11-25')
            log = write_log(tmp, LOG_NULL)
            code, _ = sa.decide('TSLA, DIA', '', log, tmp)
            self.assertEqual(code, 1)

    def test_red_when_all_fail_fetch_error_files_at_prior_session(self):
        # Grok Bot must-fix (1): every symbol fails with a non-null-close
        # error while the files sit at the prior session. The old code
        # fell back to newest_asof (the files' own date) and called them
        # "already published" -- exit 0, a real outage going silent.
        # Must go red.
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'TSLA', '2026-11-25')
            write_daily(tmp, 'DIA', '2026-11-25')
            write_daily(tmp, 'AAPL', '2026-11-25')
            log = write_log(tmp, LOG_FETCH_FAIL)
            code, msg = sa.decide('TSLA, DIA, AAPL', '', log, tmp, now=NOW)
            self.assertEqual(code, 1)
            self.assertIn('::error::', msg)

    def test_red_when_missing_sessions_files_unchanged(self):
        # Grok Bot must-fix (2): a "missing N completed session(s)"
        # failure with the files unchanged at the current session. The
        # old code fell back to newest_asof and went quiet because every
        # asOf equalled it. Must go red.
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'TSLA', '2026-11-27')
            log = write_log(tmp, LOG_MISSING_SESSIONS)
            code, msg = sa.decide('TSLA', '', log, tmp, now=NOW)
            self.assertEqual(code, 1)
            self.assertIn('::error::', msg)

    def test_quiet_on_identical_repeat_without_null_close(self):
        # The dedupe still limits noise on the no-null-close path: the
        # previous run alerted on the identical signature (same symbols,
        # session from cutoff_date) -- a repeat, stay quiet.
        with tempfile.TemporaryDirectory() as tmp:
            write_daily(tmp, 'TSLA', '2026-11-27')
            write_daily(tmp, 'DIA', '2026-11-27')
            write_daily(tmp, 'AAPL', '2026-11-27')
            log = write_log(tmp, LOG_FETCH_FAIL)
            fake = stub_gh_api_factory(
                [{'id': 99, 'status': 'completed'}],
                {99: ([{'id': 7, 'name': 'recap'}],
                      alert_ann(failed='AAPL, DIA, TSLA',
                                session='2026-11-27'))})
            code, msg = sa.decide('TSLA, DIA, AAPL', '', log, tmp,
                                  repo='o/r', run_id=100, token='t',
                                  _gh_api=fake, now=NOW)
            self.assertEqual(code, 0)
            self.assertIn('repeat', msg)


if __name__ == '__main__':
    unittest.main(verbosity=1)
