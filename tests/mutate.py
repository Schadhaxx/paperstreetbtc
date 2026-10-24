#!/usr/bin/env python3
"""Mutation harness (BP). Applies each mutation to a TEMP COPY of the repo (the checkout is never modified), runs tests/test_freeze.py
against it, and requires every mutant to be caught (>= 1 FAIL or a crash). Exit 1 if any mutant survives or a mutation no longer matches.
usage: python3 tests/mutate.py [--history PATH_OR_URL] [--only SUBSTRING]"""
import os, shutil, subprocess, sys, tempfile
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
Y, B, RG = '.github/workflows/prices.yml', 'tools/btc_daily.py', 'tools/recap_gen.py'
M = [  # (name, file, old, new) -- BP code only: freeze rule, fallback replacement, heal/provisional, 48 h stall, Stooq guards
 ('freeze cut 8 PM -> 7 PM ET', Y, "def stock_cut(d): return _dt.datetime.fromisoformat(d).replace(hour=20,", "def stock_cut(d): return _dt.datetime.fromisoformat(d).replace(hour=19,"),
 ('freeze cut 8 PM -> 9 PM ET', Y, "def stock_cut(d): return _dt.datetime.fromisoformat(d).replace(hour=20,", "def stock_cut(d): return _dt.datetime.fromisoformat(d).replace(hour=21,"),
 ('stock freeze without a post-cutoff publish', Y, "prev_upd >= stock_cut(d) and frozen_ok(d, k)", "frozen_ok(d, k)"),
 ('BTC final close never frozen', Y, "if d in prevc and d not in prevprov and prevc[d].get('BTC') is not None and frozen_ok(d, 'BTC'):", "if False:"),
 ('fallback values freeze', Y, "if not s_.endswith('-unchecked'): return is_primary(s_)", "if not s_.endswith('-unchecked'): return True"),
 ('coinbase/yahoo-meta treated as primary', Y, "PRIMARY = {'yahoo', ", "PRIMARY = {'coinbase', 'yahoo-meta', 'yahoo', "),
 ('unchecked freezes by age after 20 h (not ~3 days)', Y, "timedelta(days=2, hours=20)", "timedelta(days=0, hours=20)"),
 ('unchecked-by-age 15% guard -> 50%', Y, "0.85 * p_ <= val <= p_ / 0.85", "0.5 * p_ <= val <= p_ / 0.5"),
 ('single source counted as checked', Y, ">= 2 else (src_ or 'yahoo') + '-unchecked'", ">= 1 else (src_ or 'yahoo') + '-unchecked'"),
 ('sanity band 40% dropped', Y, "if p_ and not (0.6 * p_ <= v <= 1.0 / 0.6 * p_)", "if False"),
 ('_agree: 0/NaN/negative count as values', Y, "isinstance(v, (int, float)) and v == v and 0 < v < float('inf')]", "v is not None]"),
 ('BTC final 20 min after UTC day -> immediately', Y, "def final_btc(d): return now_utc >= _dt.datetime.fromisoformat(d).replace(tzinfo=_dt.timezone.utc) + _dt.timedelta(days=1, minutes=20)", "def final_btc(d): return now_utc >= _dt.datetime.fromisoformat(d).replace(tzinfo=_dt.timezone.utc) + _dt.timedelta(days=0, minutes=20)"),
 ('fallback BTC dropped while Yahoo is null (not kept)', Y, "elif d < today_utc and v is None and d in prevc and d not in prevprov and prevc[d].get('BTC') is not None:", "elif False:"),
 ('fallback stock dropped while Yahoo is null (not kept)', Y, "elif v is None and d in prevc and prevc[d].get(k) is not None:", "elif False:"),
 ('fallback replacement not logged', Y, "'src': f'fallback ({ps_}) replaced by primary final bar'})\n                          elif v is None:", "'src': 'x'})\n                          elif v is None:"),
 ('unconfirmed re-pull before freeze accepted', Y, "if cf and all(abs(x / v - 1) <= TOL_STOCK for _, x in cf)", "if True"),
 ('revision log not carried forward', Y, "for r_ in ((hold_prev or {}).get('revisions_ignored') or []) + revs:", "for r_ in revs:"),
 ('R-i residual hold restored', Y, "if pub is None or is_primary(ps) or (k == 'BTC' and d in prevprov): raise", "raise"),
 ('R-i ::error:: after 8 PM dropped', Y, "FEED_ERR.append(msg) if now_utc >= due else", "None if True else"),
 ('G5 Stooq for dividend payers (history)', Y, "stooq = (lambda y, d: None if y in DIV_SYMS else _st0(y, d)) if _st0 else None", "stooq = _st0"),
 ('merge: fallback_sources union dropped', Y, "for d, s in (new.get('fallback_sources') or {}).items(): fs.setdefault(d, {}).update(s)", "pass"),
 ('R-q heal neighbour band 0.5x -> 0.4x', B, "0.5 * n_ < v_ < 2 * n_", "0.4 * n_ < v_ < 2 * n_"),
 ('R-q heal neighbour band 2x -> 2.5x', B, "0.5 * n_ < v_ < 2 * n_", "0.5 * n_ < v_ < 2.5 * n_"),
 ('R-q heal neighbour band <= (boundary)', B, "0.5 * n_ < v_ < 2 * n_", "0.5 * n_ <= v_ <= 2 * n_"),
 ('R-q no-history path heals non-provisional dates', B, "        for d_ in sorted(PROV):\n            if d_ <= last and d_ in YB:", "        for d_ in sorted(YB):\n            if d_ <= last and d_ in YB:"),
 ('heal: btc-daily never re-synced', B, "if Bd[d_] != t_: HEAL[d_] = t_", "pass"),
 ('heal: fallback date not marked provisional', B, "elif base_ != 'ffill': PROV.add(d_)", "elif False: PROV.add(d_)"),
 ('heal: fallback value treated as final', B, "if base_ == 'yahoo':", "if True:"),
 ('heal: no-history path never heals', B, "if dict(j['d']).get(d_) != YB[d_]: HEAL[d_] = YB[d_]", "pass"),
 ('Coinbase-filled day not provisional', B, "; PROV.add(k.isoformat()); print('Coinbase close used for'", "; print('Coinbase close used for'"),
 ('fallback day does not pause btc-daily', B, "hold_from = fb\n", "hold_from = []\n"),
 ('stall 48 h -> 72 h', B, "STALL_H = 48;", "STALL_H = 72;"),
 ('stall: provisional > 48 h no stall', B, "if d_ <= last and now - (", "if False and now - ("),
 ('stall: fallback after last no stall', B, "if d_ > last and now - (", "if False and now - ("),
 ('recap: provisional note dropped', RG, "if any(x in bdays for x in BPROV) else ''", "if False else ''"),
 ('R-s (1) record check dropped', B, "rec_ = d_ in FBREC or d_ in HLIST;", "rec_ = True;"),
 ('R-s (1) heal list ignored', B, "rec_ = d_ in FBREC or d_ in HLIST;", "rec_ = d_ in FBREC;"),
 ('R-s (1) revision log ignored', B, "rec_ = d_ in FBREC or d_ in HLIST;", "rec_ = d_ in HLIST;"),
 ('R-s (1) any revision counts as a fallback record', B, "and str(r_.get('src', '')).startswith('fallback (') and 'replaced by primary' in str(r_.get('src', ''))}", "}"),
 ('R-s (1) revision symbol not checked', B, "r_.get('sym') == 'BTC'", "True"),
 ('R-s (1) revision date not checked', B, "FBREC = {str(r_.get('date')) for r_", "FBREC = {d_ for d_ in Bd for r_"),
 ('R-s (1) heal list values accepted', B, "if not (isinstance(L_, list) and all(", "if not (True or all("),
 ('R-s (2) 7 days -> 8', B, "HEAL_DAYS = 7;", "HEAL_DAYS = 8;"),
 ('R-s (2) 7 days -> 6', B, "HEAL_DAYS = 7;", "HEAL_DAYS = 6;"),
 ('R-s (2) age in UTC instead of ET', B, "today_et = now.astimezone(zoneinfo.ZoneInfo('America/New_York')).date()", "today_et = now.date()"),
 ('R-s (2) age check dropped', B, "rec_ and 0 <= age_ <= HEAL_DAYS and chg_", "rec_ and chg_"),
 ('R-s (3) 0.5% -> 0.51%', B, "HEAL_MAX = 0.005;", "HEAL_MAX = 0.0051;"),
 ('R-s (3) 0.5% -> 0.49%', B, "HEAL_MAX = 0.005;", "HEAL_MAX = 0.0049;"),
 ('R-s (3) epsilon dropped (exact -0.5% refused)', B, "HEAL_EPS = 1e-12", "HEAL_EPS = -1e-12"),
 ('R-s (3) change check dropped', B, "and chg_ <= HEAL_MAX + HEAL_EPS):", "):"),
 ('R-s refusal still writes the file', B, " (R-s); file unchanged'); sys.exit(1)", " (R-s); file unchanged')"),
 ('R-s provisional rows treated as final', B, "if d_ in PROV0: continue", "pass"),
 ('R-t old tag dropped when the date is absent from the new run (bp-3b117f801a8d behaviour)', Y, "if d in m['closes'] and not (d in NC and k in NC[d]): fs.setdefault(d, {})[k] = t", "if d in NC and k not in NC[d]: fs.setdefault(d, {})[k] = t"),
 ('R-t old tag never dropped (even if the new run is primary)', Y, "if d in m['closes'] and not (d in NC and k in NC[d]): fs.setdefault(d, {})[k] = t", "if d in m['closes']: fs.setdefault(d, {})[k] = t"),
 ('R-t new tags not applied', Y, "if d in m['closes']: fs.setdefault(d, {}).update(s)", "pass"),
 ('R-t old-only provisional dropped (live behaviour)', Y, " | set(d for d in old.get('btc_provisional', []) if d in m['closes'] and d not in NC))", ")"),
 ('R-t old provisional re-added for a date the new run has', Y, "if d in m['closes'] and d not in NC))", "if d in m['closes']))"),
 ('check-only uses the network', B, "if CHECK: raise RuntimeError('check-only: no fetch')", "if False: raise RuntimeError('check-only: no fetch')"),
]
def main(argv):
    hist = argv[argv.index('--history') + 1] if '--history' in argv else None
    only = argv[argv.index('--only') + 1] if '--only' in argv else ''
    res = []; surv = 0
    for name, f, old, new in M:
        if only and only not in name: continue
        td = tempfile.mkdtemp(); dst = os.path.join(td, 'r')
        shutil.copytree(REPO, dst, ignore=shutil.ignore_patterns('.git'))
        src = open(os.path.join(dst, f)).read()
        if src.count(old) < 1: res.append((name, 'NO MATCH')); surv += 1; shutil.rmtree(td); continue
        open(os.path.join(dst, f), 'w').write(src.replace(old, new, 1))
        cmd = [sys.executable, os.path.join(dst, 'tests/test_freeze.py'), '--repo', dst] + (['--history', hist] if hist else [])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300); out = r.stdout + r.stderr
        fails = sum(1 for l in out.splitlines() if l.startswith('FAIL ')); crash = 'Traceback' in out
        caught = r.returncode != 0 and (fails > 0 or crash)
        res.append((name, f'caught ({fails} FAIL{", crash" if crash else ""})' if caught else 'SURVIVED')); surv += 0 if caught else 1
        shutil.rmtree(td)
    for n, v in res: print(f'  {v:<26} {n}')
    print(f'MUTANTS {len(res)} SURVIVED {surv}'); return 1 if surv else 0
if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
