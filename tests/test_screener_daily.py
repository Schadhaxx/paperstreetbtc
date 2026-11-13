#!/usr/bin/env python3
"""Tests for tools/screener_daily.py — daily closes for the screener
Bollinger Weekly/Daily switch. Fixture-based, no network.

Run: python3 tests/test_screener_daily.py
"""
import json, os, sys, tempfile, unittest, datetime as dt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import screener_daily as sd

# TSLA, Jan 2-30 2026: 20 sessions. Last session of each week matches
# the shipped weekly close for that week (438.07 / 445.01 / 437.50 /
# 449.06 / 430.41). Jan 19 is MLK Day (no session).
TSLA_ROWS = [
    ('2026-01-02', 438.07), ('2026-01-05', 440.00), ('2026-01-06', 442.50),
    ('2026-01-07', 441.00), ('2026-01-08', 443.25), ('2026-01-09', 445.01),
    ('2026-01-12', 446.00), ('2026-01-13', 444.00), ('2026-01-14', 440.00),
    ('2026-01-15', 438.00), ('2026-01-16', 437.50),
    ('2026-01-20', 442.00), ('2026-01-21', 445.00), ('2026-01-22', 447.50),
    ('2026-01-23', 449.06),
    ('2026-01-26', 447.00), ('2026-01-27', 444.00), ('2026-01-28', 438.00),
    ('2026-01-29', 433.00), ('2026-01-30', 430.41),
]
TSLA_WEEKS = [
    {'monday': '2025-12-29', 'sunday': '2026-01-04', 'close': 438.07},
    {'monday': '2026-01-05', 'sunday': '2026-01-11', 'close': 445.01},
    {'monday': '2026-01-12', 'sunday': '2026-01-18', 'close': 437.50},
    {'monday': '2026-01-19', 'sunday': '2026-01-25', 'close': 449.06},
    {'monday': '2026-01-26', 'sunday': '2026-02-01', 'close': 430.41},
]
NOW = '2026-01-30T17:00:00-05:00'  # Friday, after the 16:15 ET final cutoff


def rows(pairs):
    return [{'date': d, 'close': c} for d, c in pairs]


class TestStockBuild(unittest.TestCase):
    def test_tsla_doc_shape(self):
        closes = sd.closes_from_fixture_rows('TSLA', rows(TSLA_ROWS))
        doc, mism = sd.build_doc('TSLA', closes, NOW, TSLA_WEEKS)
        self.assertEqual(mism, [])
        self.assertEqual(doc['asOf'], '2026-01-30')
        self.assertEqual(doc['unit'], 'usd')
        self.assertEqual(doc['basis'], 'ytd')
        self.assertEqual(doc['firstSession'], '2026-01-02')
        self.assertEqual(len(doc['days']), 20)
        self.assertEqual(doc['days'][0], {'date': '2026-01-02', 'close': 438.07})
        self.assertEqual(doc['days'][-1], {'date': '2026-01-30', 'close': 430.41})
        # Dates strictly ascending, all closes finite and positive.
        dates = [r['date'] for r in doc['days']]
        self.assertEqual(dates, sorted(dates))
        self.assertTrue(all(isinstance(r['close'], float) and r['close'] > 0 for r in doc['days']))

    def test_tsla_before_cutoff_excludes_today(self):
        # 15:00 ET on Friday 30 Jan: today is not final, so asOf is 29 Jan.
        closes = sd.closes_from_fixture_rows('TSLA', rows(TSLA_ROWS))
        doc, _ = sd.build_doc('TSLA', closes, '2026-01-30T15:00:00-05:00', TSLA_WEEKS)
        self.assertEqual(doc['asOf'], '2026-01-29')
        self.assertEqual(len(doc['days']), 19)

    def test_stock_weekly_mismatch_is_hard_error(self):
        # Mismatch on a completed prior week (16 Jan, week of 12 Jan),
        # not the in-progress week containing NOW (30 Jan).
        bad = [('2026-01-16', 438.00)] + [p for p in TSLA_ROWS if p[0] != '2026-01-16']
        closes = sd.closes_from_fixture_rows('TSLA', rows(bad))
        with self.assertRaises(RuntimeError) as cm:
            sd.build_doc('TSLA', closes, NOW, TSLA_WEEKS)
        self.assertIn('weekly-consistency', str(cm.exception))
        self.assertIn('2026-01-12', str(cm.exception))

    def test_in_progress_week_mismatch_is_skipped(self):
        # NOW is Friday 30 Jan, still inside the week of 26 Jan.
        # A desk-intraday weekly close that does not match the official
        # daily bar on 30 Jan must not fail the build.
        bad = [('2026-01-30', 431.00)] + [p for p in TSLA_ROWS if p[0] != '2026-01-30']
        closes = sd.closes_from_fixture_rows('TSLA', rows(bad))
        doc, mism = sd.build_doc('TSLA', closes, NOW, TSLA_WEEKS)
        self.assertEqual(mism, [])
        self.assertEqual(doc['asOf'], '2026-01-30')
        self.assertEqual(doc['days'][-1], {'date': '2026-01-30', 'close': 431.00})

    def test_missing_session_is_hard_error(self):
        short = [p for p in TSLA_ROWS if p[0] != '2026-01-14']
        closes = sd.closes_from_fixture_rows('TSLA', rows(short))
        with self.assertRaises(RuntimeError) as cm:
            sd.build_doc('TSLA', closes, NOW, TSLA_WEEKS)
        self.assertIn('missing 1 completed session', str(cm.exception))

    def test_short_doc_builds_under_20_days(self):
        # Fewer than 20 closes is NOT an error: the daily file is still
        # written (it grows daily), and the JS draws no bands until 20
        # daily closes are available. 11 sessions, Jan 2-16.
        closes = sd.closes_from_fixture_rows('TSLA', rows(TSLA_ROWS[:11]))
        doc, mism = sd.build_doc('TSLA', closes, '2026-01-16T17:00:00-05:00', TSLA_WEEKS)
        self.assertEqual(mism, [])
        self.assertEqual(len(doc['days']), 11)
        self.assertEqual(doc['asOf'], '2026-01-16')

    def test_spcx_listing_basis(self):
        # SPCX from listing (12 Jun 2026). 20 sessions, 12 Jun - 13 Jul.
        # 19 Jun and 3 Jul are NYSE holidays (not sessions). The last
        # session of each week matches that week's close.
        pairs = [
            ('2026-06-12', 160.95),
            ('2026-06-15', 162.00), ('2026-06-16', 161.00), ('2026-06-17', 163.50),
            ('2026-06-18', 164.00),
            ('2026-06-22', 159.00), ('2026-06-23', 160.00), ('2026-06-24', 161.00),
            ('2026-06-25', 162.00), ('2026-06-26', 165.25),
            ('2026-06-29', 166.00), ('2026-06-30', 167.00), ('2026-07-01', 168.00),
            ('2026-07-02', 169.00),
            ('2026-07-06', 171.00), ('2026-07-07', 172.00), ('2026-07-08', 173.50),
            ('2026-07-09', 174.00), ('2026-07-10', 175.25),
            ('2026-07-13', 176.00),
        ]
        self.assertEqual(len(pairs), 20)
        weeks = [
            {'monday': '2026-06-08', 'sunday': '2026-06-14', 'close': 160.95},
            {'monday': '2026-06-15', 'sunday': '2026-06-21', 'close': 164.00},
            {'monday': '2026-06-22', 'sunday': '2026-06-28', 'close': 165.25},
            {'monday': '2026-06-29', 'sunday': '2026-07-05', 'close': 169.00},
            {'monday': '2026-07-06', 'sunday': '2026-07-12', 'close': 175.25},
            {'monday': '2026-07-13', 'sunday': '2026-07-19', 'close': 176.00},
        ]
        closes = sd.closes_from_fixture_rows('SPCX', rows(pairs))
        doc, mism = sd.build_doc('SPCX', closes, '2026-07-13T17:00:00-05:00', weeks)
        self.assertEqual(mism, [])
        self.assertEqual(doc['basis'], 'listing')
        self.assertEqual(doc['firstSession'], '2026-06-12')
        self.assertEqual(len(doc['days']), 20)


class TestIndicatorBuild(unittest.TestCase):
    def test_gold_mismatch_reported_not_fatal(self):
        # GOLD, Jan 2026. Weekly close for week of 5 Jan is 4320.00 in the
        # fixture weekly list, but the daily close on 9 Jan is 4320.50 —
        # a flagged shipped value. The build must SUCCEED and report it.
        pairs = [
            ('2026-01-02', 4300.00), ('2026-01-05', 4310.00), ('2026-01-06', 4315.00),
            ('2026-01-07', 4312.00), ('2026-01-08', 4318.00), ('2026-01-09', 4320.50),
            ('2026-01-12', 4322.00), ('2026-01-13', 4325.00), ('2026-01-14', 4328.00),
            ('2026-01-15', 4330.00), ('2026-01-16', 4335.00),
            ('2026-01-19', 4336.00), ('2026-01-20', 4340.00), ('2026-01-21', 4342.00),
            ('2026-01-22', 4345.00), ('2026-01-23', 4350.00),
            ('2026-01-26', 4352.00), ('2026-01-27', 4355.00), ('2026-01-28', 4358.00),
            ('2026-01-29', 4360.00),
        ]
        weeks = [
            {'monday': '2025-12-29', 'sunday': '2026-01-04', 'close': 4300.00},
            {'monday': '2026-01-05', 'sunday': '2026-01-11', 'close': 4320.00},
            {'monday': '2026-01-12', 'sunday': '2026-01-18', 'close': 4335.00},
            {'monday': '2026-01-19', 'sunday': '2026-01-25', 'close': 4350.00},
            {'monday': '2026-01-26', 'sunday': '2026-02-01', 'close': 4360.00},
        ]
        closes = sd.closes_from_fixture_rows('GOLD', rows(pairs))
        doc, mism = sd.build_doc('GOLD', closes, NOW, weeks)
        self.assertEqual(len(mism), 1)
        self.assertIn('4320.5', mism[0])
        self.assertIn('4320', mism[0])
        self.assertEqual(len(doc['days']), 20)
        self.assertIn('preserved shipped value', doc['note'])

    def test_us10y_three_decimals(self):
        pairs = [(f'2026-01-{d:02d}', 4.100 + i * 0.001) for i, d in enumerate(
            [2, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 20, 21, 22, 23, 26, 27, 28, 29, 30])]
        closes = sd.closes_from_fixture_rows('US10Y', rows(pairs))
        doc, _ = sd.build_doc('US10Y', closes, NOW, [])
        self.assertEqual(doc['unit'], 'pct')
        self.assertTrue(all(abs(c['close'] - round(c['close'], 3)) < 1e-9 for c in doc['days']))

    def test_indicator_in_progress_bar_is_dropped_until_1800_et(self):
        # Yahoo serves today's bar while the session is still trading.
        # It must not be written as a close until 18:00 ET (ET date).
        pairs = [('2026-11-09', 4114.5), ('2026-11-10', 4030.2), ('2026-11-11', 4062.0)]
        closes = sd.closes_from_fixture_rows('GOLD', rows(pairs))
        for now in ('2026-11-11T05:15:00-05:00', '2026-11-11T17:59:00-05:00',
                    '2026-11-11T09:30:00Z'):
            doc, _ = sd.build_doc('GOLD', closes, now, [])
            self.assertEqual(doc['asOf'], '2026-11-10', now)
            self.assertEqual(doc['days'][-1], {'date': '2026-11-10', 'close': 4030.2}, now)
        doc, _ = sd.build_doc('GOLD', closes, '2026-11-11T18:00:00-05:00', [])
        self.assertEqual(doc['asOf'], '2026-11-11')
        self.assertEqual(doc['days'][-1]['close'], 4062.0)

    def test_indicator_next_day_bar_excluded_after_utc_midnight(self):
        # 19:30 ET on 11 Nov is already 12 Nov in UTC; a 12 Nov bar (the
        # next futures session) must not be included.
        pairs = [('2026-11-10', 86.04), ('2026-11-11', 86.91), ('2026-11-12', 87.30)]
        closes = sd.closes_from_fixture_rows('WTI', rows(pairs))
        doc, _ = sd.build_doc('WTI', closes, '2026-11-11T19:30:00-05:00', [])
        self.assertEqual(doc['asOf'], '2026-11-11')
        self.assertEqual([r['date'] for r in doc['days']], ['2026-11-10', '2026-11-11'])

    def test_indicator_rerun_same_day_is_byte_identical(self):
        # A recap rerun before 18:00 ET with a moved in-progress price
        # must produce the same file (so the workflow commits nothing).
        base = [('2026-11-09', 19.92), ('2026-11-10', 19.46)]
        a, _ = sd.build_doc('VIX', sd.closes_from_fixture_rows('VIX', rows(base + [('2026-11-11', 18.64)])), '2026-11-11T05:15:00-05:00', [])
        b, _ = sd.build_doc('VIX', sd.closes_from_fixture_rows('VIX', rows(base + [('2026-11-11', 18.20)])), '2026-11-11T10:40:00-05:00', [])
        self.assertEqual(json.dumps(a, indent=2), json.dumps(b, indent=2))

    def test_indicator_payload_skips_holiday_nulls(self):
        # Null close on a Saturday and on 2026-01-01 (holiday) is skipped;
        # a null close on a weekday is a hard error.
        # Timestamps are UTC midnights: Jan 1 (Thu, holiday), Jan 2 (Fri),
        # Jan 3 (Sat), Jan 5 (Mon).
        payload = {
            'timestamp': [1767225600, 1767312000, 1767398400, 1767571200],
            'indicators': {'quote': [{'close': [None, 100.0, None, 101.0]}]},
        }
        out = sd.closes_from_payload('GOLD', payload, False)
        self.assertEqual(sorted(out), [dt.date(2026, 1, 2), dt.date(2026, 1, 5)])
        bad = {
            'timestamp': [1767312000, 1767571200],
            'indicators': {'quote': [{'close': [100.0, None]}]},
        }
        with self.assertRaises(RuntimeError):
            sd.closes_from_payload('GOLD', bad, False)

    def test_stock_payload_null_close_is_hard_error(self):
        payload = {
            'timestamp': [1767312000, 1767398400],
            'indicators': {'quote': [{'close': [100.0, None]}]},
        }
        with self.assertRaises(RuntimeError):
            sd.closes_from_payload('TSLA', payload, True)


class TestCheckOnly(unittest.TestCase):
    def test_check_only_roundtrip(self):
        closes = sd.closes_from_fixture_rows('TSLA', rows(TSLA_ROWS))
        doc, _ = sd.build_doc('TSLA', closes, NOW, TSLA_WEEKS)
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, 'stock-daily-TSLA.json'), 'w') as f:
                json.dump(doc, f)
            # Weekly file the tool can read for the consistency check.
            with open(os.path.join(td, 'stock-weekly-TSLA.json'), 'w') as f:
                json.dump({'weeks': TSLA_WEEKS, 'asOf': '2026-01-30'}, f)
            rc = sd.main(['--check-only', '--symbol', 'TSLA',
                          '--out-dir', td, '--weekly-dir', td, '--now', NOW])
            self.assertEqual(rc, 0)




class TestPartialWrite(unittest.TestCase):
    def test_one_stock_failure_still_writes_the_rest(self):
        # TSLA builds; AAPL fails a completed-week consistency check.
        # The run must write TSLA, skip AAPL, and exit 1.
        aapl_rows = list(TSLA_ROWS)
        aapl_rows = [('2026-01-16', 438.00) if d == '2026-01-16' else (d, c) for d, c in aapl_rows]
        fx = {
            'now': NOW,
            'symbols': {
                'TSLA': rows(TSLA_ROWS),
                'AAPL': rows(aapl_rows),
            },
        }
        with tempfile.TemporaryDirectory() as td:
            fxpath = os.path.join(td, 'fx.json')
            with open(fxpath, 'w') as f:
                json.dump(fx, f)
            for k in ('TSLA', 'AAPL'):
                with open(os.path.join(td, f'stock-weekly-{k}.json'), 'w') as f:
                    json.dump({'weeks': TSLA_WEEKS, 'asOf': '2026-01-30'}, f)
            rc = sd.main(['--fixture', fxpath, '--out-dir', td, '--weekly-dir', td, '--now', NOW])
            self.assertEqual(rc, 1)
            tsla_path = os.path.join(td, 'stock-daily-TSLA.json')
            aapl_path = os.path.join(td, 'stock-daily-AAPL.json')
            self.assertTrue(os.path.exists(tsla_path))
            self.assertFalse(os.path.exists(aapl_path))
            with open(tsla_path) as f:
                doc = json.load(f)
            self.assertEqual(doc['asOf'], '2026-01-30')
            self.assertEqual(len(doc['days']), 20)


class TestNewDeskStockCoverage(unittest.TestCase):
    """The nine Desk stocks added 9 Nov 2026 must be in the daily
    generator the same way TSLA/MU are: STOCKS entry, weekly file
    map, ytd from 2 Jan 2026, and BRK.B fetched as Yahoo BRK-B."""

    NEW = ('BRK.B', 'AAPL', 'AMZN', 'MSFT', 'NFLX', 'SPOT', 'XYZ', 'GOOGL', 'NVDA')

    def test_new_stocks_are_in_STOCKS_like_tsla(self):
        for k in ('TSLA', 'MU') + self.NEW:
            self.assertIn(k, sd.STOCKS)
            ysym, nd, unit, basis, first, fname = sd.STOCKS[k]
            self.assertEqual(nd, 2)
            self.assertEqual(unit, 'usd')
            self.assertEqual(basis, 'ytd' if k != 'SPCX' else 'listing')
            self.assertEqual(first, '2026-01-02')
            self.assertEqual(fname, f'stock-daily-{k}.json')
            self.assertEqual(sd.WEEKLY_FILES[k], f'stock-weekly-{k}.json')

    def test_brk_b_yahoo_symbol_is_hyphenated(self):
        self.assertEqual(sd.STOCKS['BRK.B'][0], 'BRK-B')
        self.assertEqual(sd.STOCKS['AAPL'][0], 'AAPL')
        self.assertEqual(sd.STOCKS['TSLA'][0], 'TSLA')

    def test_new_indicators_are_not_in_daily_tool(self):
        for k in ('DJIA', 'QQQ', 'USDCAD', 'CADUSD', 'DXY'):
            self.assertNotIn(k, sd.STOCKS)
            self.assertNotIn(k, sd.INDICATORS)

    def test_dia_daily_is_an_indicator_like_vix(self):
        # DIA (SPDR Dow Jones Industrial Average ETF) replaced the DJIA
        # index tile on 13 Nov 2026 and gets daily closes for the
        # Bollinger Daily switch, same pipeline as the other tiles.
        self.assertEqual(sd.INDICATORS['DIA'], ('DIA', 2, 'usd', 'ytd', '2026-01-02', 'ind-daily-dia.json'))
        self.assertEqual(sd.WEEKLY_FILES['DIA'], 'dia-weekly.json')
        root = os.path.join(os.path.dirname(__file__), '..', 'assets', 'data')
        with open(os.path.join(root, 'ind-daily-dia.json')) as f:
            doc = json.load(f)
        self.assertEqual(doc['firstSession'], '2026-01-02')
        self.assertEqual(doc['unit'], 'usd')
        self.assertTrue(all(isinstance(r['close'], (int, float)) and r['close'] > 0 for r in doc['days']))

    def test_shipped_daily_files_match_tsla_calendar(self):
        root = os.path.join(os.path.dirname(__file__), '..', 'assets', 'data')
        with open(os.path.join(root, 'stock-daily-TSLA.json')) as f:
            tsla = json.load(f)
        tsla_dates = [r['date'] for r in tsla['days']]
        self.assertTrue(tsla_dates)
        # asOf is the last completed session in the shipped daily file,
        # not a pinned calendar date — files advance after each recap.
        self.assertEqual(tsla['asOf'], tsla_dates[-1])
        for k in self.NEW:
            with open(os.path.join(root, f'stock-daily-{k}.json')) as f:
                doc = json.load(f)
            self.assertEqual(doc['asOf'], tsla['asOf'])
            self.assertEqual(doc['firstSession'], '2026-01-02')
            self.assertEqual(doc['basis'], 'ytd')
            self.assertEqual([r['date'] for r in doc['days']], tsla_dates)
            self.assertTrue(all(isinstance(r['close'], float) and r['close'] > 0 for r in doc['days']))
        with open(os.path.join(root, 'stock-daily-BRK.B.json')) as f:
            brk = json.load(f)
        self.assertIn('BRK-B', brk['source'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
