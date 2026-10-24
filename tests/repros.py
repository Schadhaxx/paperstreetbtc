#!/usr/bin/env python3
"""Reviewer-repro regression suite (BP). Replays the reviewer repros from v5..v11 that apply to BP (freeze, fallback, heal, stall; no override repros) (Site Launch = SL, Grok Bot = GB/Grok) that lives in
tests/test_freeze.py (checks whose name carries a reviewer tag) and lists each one with its outcome. Exit 1 if any repro fails, or if fewer repros
ran than the recorded floor (a deleted/renamed repro is a failure, not a silent pass).
usage: python3 tests/repros.py [--history PATH_OR_URL]"""
import os, re, subprocess, sys
FLOOR = 136                                       # repros present in v11; raise it when adding repros, never lower it
TAG = re.compile(r'\b(SL|GB|Grok)\b|SL#|GB-|SL-|\bc1-|v\dc1|v\d+-\d|Grok:')
here = os.path.dirname(os.path.abspath(__file__))
cmd = [sys.executable, os.path.join(here, 'test_freeze.py')] + sys.argv[1:]
out = subprocess.run(cmd, capture_output=True, text=True).stdout
rows = [(l[:4], l[5:]) for l in out.splitlines() if l.startswith(('PASS ', 'FAIL ')) and TAG.search(l)]
for st, name in rows: print(f'{st}  {name[:170]}')
g = subprocess.run([sys.executable, os.path.join(here, 'simbp1_grok.py')] + sys.argv[1:], capture_output=True, text=True).stdout
grows = [(l[:4], 'Grok simbp1 ' + l.split('|')[1].strip()) for l in g.splitlines() if l.startswith(('PASS |', 'FAIL |'))]
if len(grows) != 40: grows.append(('FAIL', f'Grok simbp1: expected 40 cases, got {len(grows)}'))
for st, name in grows: print(f'{st}  {name[:170]}')
rows += grows
bad = [n for s, n in rows if s == 'FAIL']
print(f'REVIEWER REPROS {len(rows)} FAIL {len(bad)} (floor {FLOOR})')
sys.exit(1 if bad or len(rows) < FLOOR else 0)
