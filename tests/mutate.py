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
 ('R-s (1) record check dropped', B, "rec_ok = lst_ or (log_ and 0 <= age_ <= HEAL_DAYS)", "rec_ok = True"),
 ('R-s (1) one-time list ignored', B, "lst_ = d_ in HLIST;", "lst_ = False;"),
 ('R-s (1) revision log ignored', B, "log_ = d_ in FBREC;", "log_ = False;"),
 ('R-s (1) log src prefix not checked', B, "str(r_.get('src', '')).startswith('fallback (') and isinstance(hv_", "isinstance(hv_"),
 ('R-s (1) log symbol not checked', B, "if r_.get('sym') == 'BTC' and str(", "if str("),
 ('R-s (1) log kept == history value not checked', B, "and round(float(r_.get('kept')) * 100) == round(float(hv_) * 100): FBREC.add(d_)", ": FBREC.add(d_)"),
 ('R-s (1) heal list values accepted', B, "if not (isinstance(L_, list) and all(", "if not (True or all("),
 ('R-s (2) 7 days -> 8', B, "HEAL_DAYS = 7;", "HEAL_DAYS = 8;"),
 ('R-s (2) 7 days -> 6', B, "HEAL_DAYS = 7;", "HEAL_DAYS = 6;"),
 ('R-s (2) age in UTC instead of ET', B, "today_et = now.astimezone(zoneinfo.ZoneInfo('America/New_York')).date()", "today_et = now.date()"),
 ('R-s (2) window applied to list dates too', B, "rec_ok = lst_ or (log_ and 0 <= age_ <= HEAL_DAYS)", "rec_ok = (lst_ or log_) and 0 <= age_ <= HEAL_DAYS"),
 ('R-s (2) window dropped for log dates', B, "rec_ok = lst_ or (log_ and 0 <= age_ <= HEAL_DAYS)", "rec_ok = lst_ or log_"),
 ('R-s (3) 0.5% -> 0.6%', B, "HEAL_MAX_PER_MILLE = 5 ", "HEAL_MAX_PER_MILLE = 6 "),
 ('R-s (3) 0.5% -> 0.4%', B, "HEAL_MAX_PER_MILLE = 5 ", "HEAL_MAX_PER_MILLE = 4 "),
 ('R-s (3) cap <= -> <', B, "abs(cn_ - co_) * 1000 <= HEAL_MAX_PER_MILLE * co_", "abs(cn_ - co_) * 1000 < HEAL_MAX_PER_MILLE * co_"),
 ('R-s (3) cap in float, not cents', B, "co_, cn_ = round(Bd0[d_] * 100), round(HEAL[d_] * 100)", "co_, cn_ = Bd0[d_] * 100, HEAL[d_] * 100.0001"),
 ('R-s (3) cap dropped', B, "if not (rec_ok and cap_ok):", "if not rec_ok:"),
 ('R-s (4) refusal exit 1 (not red)', B, "            sys.exit(4)\n", "            sys.exit(1)\n"),
 ('R-s (4) refusal still writes the file', B, "            sys.exit(4)\n", "            pass\n"),
 ('R-s (5) provisional rows treated as final', B, "if d_ in PROV0: continue", "pass"),
 ('R-s (6) no-history path heals final rows without the list', B, "if d_ in HLIST and d_ not in PROV0 and d_ in YB", "if d_ not in PROV0 and d_ in YB"),
 ('pin stall > -> >= (48h00m00s fires)', B, "if d_ > last and now - (dt.datetime.fromisoformat(d_).replace(tzinfo=dt.timezone.utc) + dt.timedelta(days=1)) > dt.timedelta(hours=STALL_H)", "if d_ > last and now - (dt.datetime.fromisoformat(d_).replace(tzinfo=dt.timezone.utc) + dt.timedelta(days=1)) >= dt.timedelta(hours=STALL_H)"),
 ('pin _agree inf counts as a value', Y, "0 < v < float('inf')]", "0 < v]"),
 ('pin BTC final +20 -> +19 min', Y, "def final_btc(d): return now_utc >= _dt.datetime.fromisoformat(d).replace(tzinfo=_dt.timezone.utc) + _dt.timedelta(days=1, minutes=20)", "def final_btc(d): return now_utc >= _dt.datetime.fromisoformat(d).replace(tzinfo=_dt.timezone.utc) + _dt.timedelta(days=1, minutes=19)"),
 ('pin BTC final +20 -> +22 min', Y, "def final_btc(d): return now_utc >= _dt.datetime.fromisoformat(d).replace(tzinfo=_dt.timezone.utc) + _dt.timedelta(days=1, minutes=20)", "def final_btc(d): return now_utc >= _dt.datetime.fromisoformat(d).replace(tzinfo=_dt.timezone.utc) + _dt.timedelta(days=1, minutes=22)"),
 ('pin ffill treated as a fallback', B, "not in ('yahoo', 'ffill'))", "not in ('yahoo',))"),
 ('pin merge: older file wins', Y, "new, old = (b, a) if b.get('updated', '') >= a.get('updated', '') else (a, b)", "new, old = b, a"),
 ('R-t old tag dropped when the date is absent from the new run (bp-3b117f801a8d behaviour)', Y, "if d in m['closes'] and not (d in NC and k in NC[d]): fs.setdefault(d, {})[k] = t", "if d in NC and k not in NC[d]: fs.setdefault(d, {})[k] = t"),
 ('R-t old tag never dropped (even if the new run is primary)', Y, "if d in m['closes'] and not (d in NC and k in NC[d]): fs.setdefault(d, {})[k] = t", "if d in m['closes']: fs.setdefault(d, {})[k] = t"),
 ('R-t new tags not applied', Y, "if d in m['closes']: fs.setdefault(d, {}).update(s)", "pass"),
 ('R-t old-only provisional dropped (live behaviour)', Y, " | set(d for d in old.get('btc_provisional', []) if d in m['closes'] and d not in NC))", ")"),
 ('R-t old provisional re-added for a date the new run has', Y, "if d in m['closes'] and d not in NC))", "if d in m['closes']))"),
 ('check-only uses the network', B, "if CHECK: raise RuntimeError('check-only: no fetch')", "if False: raise RuntimeError('check-only: no fetch')"),
]
def stage_repo(dst):
    # DISK SAFETY (bp2): stage ONLY git-tracked files of HEAD (git archive), never a raw filesystem copy.
    top = subprocess.run(['git', '-C', REPO, 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True).stdout.strip()
    if os.path.realpath(top) in ('/', '/proc', '/tmp', os.path.expanduser('~')) or not os.path.isfile(os.path.join(top, 'tests/mutate.py')):
        raise SystemExit(f'REFUSING to stage from {top}')
    if not os.path.realpath(dst).startswith(os.path.realpath(tempfile.gettempdir()) + '/psmut.'):
        raise SystemExit(f'REFUSING to stage outside a psmut temp dir: {dst}')
    os.makedirs(dst)
    arch = subprocess.Popen(['git', '-C', top, 'archive', '--format=tar', 'HEAD'], stdout=subprocess.PIPE)
    subprocess.run(['tar', '-x', '-C', dst], stdin=arch.stdout, check=True); arch.stdout.close()
    if arch.wait() != 0: raise SystemExit('git archive failed')
def main(argv):
    hist = argv[argv.index('--history') + 1] if '--history' in argv else None
    only = argv[argv.index('--only') + 1] if '--only' in argv else ''
    res = []; surv = 0
    for name, f, old, new in M:
        if only and only not in name: continue
        td = tempfile.mkdtemp(prefix='psmut.'); dst = os.path.join(td, 'r')
        stage_repo(dst)
        src = open(os.path.join(dst, f)).read()
        if src.count(old) < 1: res.append((name, 'NO MATCH')); surv += 1; shutil.rmtree(td); continue
        open(os.path.join(dst, f), 'w').write(src.replace(old, new, 1))
        cmd = [sys.executable, os.path.join(dst, 'tests/test_freeze.py'), '--repo', dst] + (['--history', hist] if hist else [])
        try: r = subprocess.run(cmd, capture_output=True, text=True, timeout=300); out = r.stdout + r.stderr
        finally: shutil.rmtree(td, ignore_errors=True)
        fails = sum(1 for l in out.splitlines() if l.startswith('FAIL ')); crash = 'Traceback' in out
        caught = r.returncode != 0 and (fails > 0 or crash)
        res.append((name, f'caught ({fails} FAIL{", crash" if crash else ""})' if caught else 'SURVIVED')); surv += 0 if caught else 1
    for n, v in res: print(f'  {v:<26} {n}')
    print(f'MUTANTS {len(res)} SURVIVED {surv}'); return 1 if surv else 0
if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
