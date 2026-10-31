#!/usr/bin/env python3
"""Pulse-note acceptance fixture (brief 31 Oct 2026, item A1): the check in
tools/datatest.py must accept the weekday wording AND the weekend wording.
Reads the actual check expression out of datatest.py and evaluates it against
sample notes, so a regression in the source fails here."""
import re, sys, pathlib
src = pathlib.Path(__file__).resolve().parent.parent.joinpath('tools/datatest.py').read_text()
m = re.search(r"R\.append\(\('home', 'pulse', 'note says move = since daily close', 1, (.*?), 0\)\)", src, re.S)
assert m, 'pulse check expression not found in tools/datatest.py'
expr = m.group(1)
# The expression references pg.inner_text('#pulseNote'); bind it to NOTE.
expr = expr.replace("pg.inner_text('#pulseNote')", "NOTE")
# The edited check assigns _pn first; support both the old and new forms.
def ok(note):
    NOTE = note
    _pn = note
    return bool(eval(expr))
cases = [
    ("weekday note", "Oct 30, 2026 · BTC: CoinGecko (every 60s), move = since daily close · stocks: last close", True),
    ("weekend note", "Weekend move · BTC only · Stocks closed at Friday, Oct 30, 2026 close · BTC live", True),
    ("24h wording rejected", "move = since daily close, 24h change", False),
    ("empty note rejected", "", False),
]
fails = 0
for name, note, want in cases:
    got = ok(note)
    print(('PASS' if got == want else 'FAIL'), name, 'got', got, 'want', want)
    fails += got != want
print('PULSE NOTE TESTS', len(cases), 'FAIL', fails)
sys.exit(1 if fails else 0)
