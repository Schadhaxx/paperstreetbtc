#!/usr/bin/env python3
"""TG mutation harness: mutants of the NEW Tiingo cross-check code only, each run against tests/test_tiingo.py in a git-archive temp copy
(reuses mutate.stage_repo: tracked files only, never a filesystem copy). Exit 1 if any mutant survives. usage: python3 tests/mutate_tiingo.py"""
import os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import mutate
Y = '.github/workflows/prices.yml'
M = [
 ('stock tol 0.05% -> 0.1%', "TG_TOL_STOCK = 0.0005", "TG_TOL_STOCK = 0.001"),
 ('stock tol 0.05% -> 0.04%', "TG_TOL_STOCK = 0.0005", "TG_TOL_STOCK = 0.0004"),
 ('BTC tol 0.3% -> 0.5%', "TG_TOL = {'BTC': 0.003}", "TG_TOL = {'BTC': 0.005}"),
 ('BTC tol 0.3% -> 0.25%', "TG_TOL = {'BTC': 0.003}", "TG_TOL = {'BTC': 0.0025}"),
 ('BTC tol applied to stocks', "tol = TG_TOL.get(k, TG_TOL_STOCK)", "tol = 0.003"),
 ('> becomes >=', "if diff > tol:", "if diff >= tol:"),
 ('adjClose read instead of close', "c = row.get('close')   # raw close", "c = row.get('adjClose')   # raw close"),
 ('date match dropped', "if str(row.get('date', ''))[:10] == d and isinstance", "if isinstance"),
 ('non-positive close accepted', "math.isfinite(c) and c > 0: return", "math.isfinite(c): return"),
 ('inf/NaN close accepted', "and math.isfinite(c) and c > 0: return", "and c > 0: return"),
 ('bool close accepted', "and not isinstance(c, bool) and math.isfinite", "and math.isfinite"),
 ('stock final cut 8 PM -> 4 PM ET', "replace(hour=20, tzinfo=ET_)\n", "replace(hour=16, tzinfo=ET_)\n"),
 ('BTC provisional checked', "fin = d not in pv and now_utc", "fin = now_utc"),
 ('BTC +20 min dropped', "_dt.timedelta(days=1, minutes=20)\n                      else: fin", "_dt.timedelta(days=1)\n                      else: fin"),
 ('ffill not skipped', "if src.startswith('ffill'): continue", "pass"),
 ('cache ignored (call every run)', "if c is None or (c.get('v') is None", "if True or (c.get('v') is None"),
 ('miss retried every run', ">= _dt.timedelta(minutes=TG_RETRY_MIN)", ">= _dt.timedelta(minutes=0)"),
 ('call cap removed', "if calls >= TG_MAX_CALLS: continue", "pass"),
 ('error not caught', "try: tv = tiingo_close(get_t, k, d)\n", "tv = tiingo_close(get_t, k, d)\n                  if 0: pass\n"),
 ('flag writes the close', "flags.append(f); new.append(f)", "flags.append(f); new.append(f); h['closes'][d][k] = c['v']"),
 ('flag dedupe removed', "if not any(x.get('date') == d and x.get('sym') == k and x.get('site') == v and x.get('tiingo') == c['v'] for x in flags):", "if True:"),
 ('7-day window -> 30', "TG_DAYS = 7", "TG_DAYS = 30"),
 ('key in URL', "headers={'Authorization': 'Token ' + key,", "headers={'X': key}) if 0 else _ur.Request(u + '&token=' + key, headers={'Authorization': 'Token ' + key,"),
 ('key given to weekend job', "      - name: btc-daily stall check (no writes)\n", "      - name: btc-daily stall check (no writes)\n        env:\n          TIINGO_API_KEY: ${{ secrets.TIINGO_API_KEY }}\n"),
]
def main():
    surv = 0; res = []
    for name, old, new in M:
        td = tempfile.mkdtemp(prefix='psmut.'); dst = os.path.join(td, 'r')
        try:
            mutate.stage_repo(dst); p = os.path.join(dst, Y); s = open(p).read()
            if old not in s: res.append((name, 'NO MATCH')); surv += 1; continue
            open(p, 'w').write(s.replace(old, new, 1))
            r = subprocess.run([sys.executable, os.path.join(dst, 'tests/test_tiingo.py'), '--repo', dst], capture_output=True, text=True, timeout=120)
            out = r.stdout + r.stderr; fails = out.count('\nFAIL ') + out.startswith('FAIL '); crash = 'Traceback' in out
            ok = r.returncode != 0 and (fails or crash); res.append((name, f'caught ({fails} FAIL{", crash" if crash else ""})' if ok else 'SURVIVED')); surv += 0 if ok else 1
        finally: shutil.rmtree(td, ignore_errors=True)
    for n, v in res: print(f'  {v:<26} {n}')
    print(f'TG MUTANTS {len(res)} SURVIVED {surv}'); return 1 if surv else 0
if __name__ == '__main__': sys.exit(main())
