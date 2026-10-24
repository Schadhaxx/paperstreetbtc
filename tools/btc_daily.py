#!/usr/bin/env python3
"""Append FINAL daily BTC-USD closes (UTC day, weekends included) to assets/data/btc-daily.json.
Source: Yahoo Finance BTC-USD daily bars (same source as the file and as history.json); Coinbase BTC-USD daily candles fill any day Yahoo leaves empty. A UTC day counts as final
20 minutes after it ends. Only dates after the file's last date are added (backfills any gap); nothing is rewritten.
Exit 0 = ok (changed or not), 1 = fetch/validation failed (file untouched),
3 = STALLED: a BTC day is still on a fallback source (Coinbase/CoinGecko) more than 48 h after its UTC day ended, because Yahoo never
    published its final bar. Days before it are still appended; the recap job turns RED (::error::) but keeps publishing.
    Manual way out (BP; the manual-correction path is paused until Tiingo): see bp/ROLLOUT.md "Stall" (reviewed PR, Code Owners).
BP HEAL (generic, no hard-coded dates/values): every EXISTING date is re-synced to history.json's final BTC close when history.json's provenance for it is
    Yahoo (the single source of truth), e.g. a date the pre-v5 code wrote from Coinbase/an early Yahoo bar. A date whose history.json
    provenance is a fallback (coinbase/coingecko/...) keeps its value but is listed in "provisional" (not final) until Yahoo's final bar replaces it.
    Without history.json, provisional dates heal from Yahoo's own final bar. A date this script fills from Coinbase is provisional too.
R-s: a FINAL (non-provisional) row is rewritten only if ALL hold: (1) the date is on record as fallback-sourced: history.json revisions_ignored has a
    'fallback (...) replaced by primary' BTC entry for it, or it is in the one-time heal list kept in DATA (--heal-list PATH: a JSON list of dates,
    no values; data branch btc-heal-once.json); (2) the date is within 7 days of today (ET); (3) the change is at most 0.5%.
    Otherwise ::error:: and exit 1 with the file unchanged."""
import json, sys, time, datetime as dt, urllib.request, os, re, zoneinfo
STALL_H = 48; STALL = []
HEAL_DAYS = 7; HEAL_MAX = 0.005; HEAL_EPS = 1e-12   # R-s
HLIST = set()
if '--heal-list' in sys.argv:                 # R-s (1): one-time heal list from DATA (dates only, never values)
    i_ = sys.argv.index('--heal-list'); hp_ = sys.argv[i_ + 1]; del sys.argv[i_:i_ + 2]
    try:
        L_ = json.load(open(hp_))
        if not (isinstance(L_, list) and all(isinstance(x, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', x) for x in L_)): raise ValueError('must be a JSON list of YYYY-MM-DD dates (no values)')
        HLIST = set(L_)
    except FileNotFoundError: pass
    except Exception as e: print(f'::error title=btc-daily heal list ignored::{hp_}: {type(e).__name__}: {e}'); HLIST = set()
CHECK = '--check-only' in sys.argv          # v7 (SL v6c1-4): weekend stall alarm; reads history.json only, never fetches or writes
if CHECK: sys.argv.remove('--check-only')
F = sys.argv[1] if len(sys.argv) > 1 else 'assets/data/btc-daily.json'
def fetch(u, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 paperstreet'}), timeout=20) as r: return json.load(r)
        except Exception as e:
            if i == tries - 1: raise
            time.sleep([5, 15, 30][min(i, 2)])
try:
    j = json.load(open(F)); last = j['d'][-1][0]
    now = dt.datetime.now(dt.timezone.utc)
    PROV0 = sorted(set(j.get('provisional') or [])); PROV = set(PROV0); HEAL = {}; YB = {}   # v10 heal state
    p0 = int((dt.datetime.fromisoformat(min([last] + PROV0)).replace(tzinfo=dt.timezone.utc) - dt.timedelta(days=3)).timestamp())
    final = lambda d: now >= dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc) + dt.timedelta(days=1, minutes=20)
    bars = {}
    try:
        if CHECK: raise RuntimeError('check-only: no fetch')
        r = fetch(f'https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?period1={p0}&period2={int(now.timestamp())+86400}&interval=1d')['chart']['result'][0]
        for t, c in zip(r.get('timestamp') or [], r['indicators']['quote'][0]['close']):
            if c is None: continue
            d = dt.datetime.fromtimestamp(t, dt.timezone.utc).date()
            if final(d): bars[d.isoformat()] = YB[d.isoformat()] = round(float(c), 2)
    except Exception as e: print('Yahoo failed, trying Coinbase:', type(e).__name__, e)
    # Coinbase backup (CR-008): fill any final UTC day Yahoo left empty (Yahoo often returns null closes just after 00:00 UTC)
    need = []; d = dt.date.fromisoformat(last) + dt.timedelta(days=1)
    while final(d): need.append(d.isoformat()); d += dt.timedelta(days=1)
    if any(x not in bars for x in need) and not CHECK:
        try:
            cb = fetch(f'https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400&start={dt.datetime.fromtimestamp(p0, dt.timezone.utc).isoformat()}&end={now.isoformat()}')
            for t, lo, hi, op, cl, vol in cb:
                k = dt.datetime.fromtimestamp(t, dt.timezone.utc).date()
                if k.isoformat() in need and k.isoformat() not in bars: bars[k.isoformat()] = round(float(cl), 2); PROV.add(k.isoformat()); print('Coinbase close used for', k.isoformat(), bars[k.isoformat()], '(provisional)')
        except Exception as e: print('Coinbase backup failed:', type(e).__name__, e)
    # P5: one source of truth. Where history.json (data branch) already has the FINAL close for a day, use it (frozen, cross-checked)
    if len(sys.argv) > 2:
        try:
            H = json.load(open(sys.argv[2])); pv = set(H.get('btc_provisional') or [])
            for d_, r_ in H['closes'].items():
                if d_ > last and d_ not in pv and final(dt.date.fromisoformat(d_)) and r_.get('BTC'): bars[d_] = round(float(r_['BTC']), 2)
            fsrc = H.get('fallback_sources') or {}
            fb = sorted(d_ for d_, s_ in fsrc.items() if s_.get('BTC', 'yahoo').split('-')[0] not in ('yahoo', 'ffill'))   # fallback value not yet replaced by Yahoo
            hold_from = fb
            for d_ in fb:   # a fallback Yahoo never replaces must not stall silently
                if d_ > last and now - (dt.datetime.fromisoformat(d_).replace(tzinfo=dt.timezone.utc) + dt.timedelta(days=1)) > dt.timedelta(hours=STALL_H): STALL.append(d_)
            Bd = dict(j['d'])
            for d_, r_ in H['closes'].items():   # v10 HEAL: existing dates follow history.json's final close when its provenance is Yahoo
                if d_ > last or d_ not in Bd or d_ in pv or not r_.get('BTC') or not final(dt.date.fromisoformat(d_)): continue
                base_ = str(fsrc.get(d_, {}).get('BTC', 'yahoo')).split('-')[0]
                if base_ == 'yahoo':
                    PROV.discard(d_); t_ = round(float(r_['BTC']), 2)
                    if Bd[d_] != t_: HEAL[d_] = t_
                elif base_ != 'ffill': PROV.add(d_)                                  # fallback in history.json: not final here either
            for d_ in sorted(PROV):
                if d_ <= last and now - (dt.datetime.fromisoformat(d_).replace(tzinfo=dt.timezone.utc) + dt.timedelta(days=1)) > dt.timedelta(hours=STALL_H): STALL.append(d_)
            FBREC = {str(r_.get('date')) for r_ in (H.get('revisions_ignored') or []) if isinstance(r_, dict) and r_.get('sym') == 'BTC'
                     and str(r_.get('src', '')).startswith('fallback (') and 'replaced by primary' in str(r_.get('src', ''))}
            today_et = now.astimezone(zoneinfo.ZoneInfo('America/New_York')).date()
            for d_ in sorted(HEAL):   # R-s: rewriting a FINAL row needs a fallback record AND <= 7 days (ET) AND <= 0.5%
                if d_ in PROV0: continue                                          # provisional rows: not final, heal as before
                rec_ = d_ in FBREC or d_ in HLIST; age_ = (today_et - dt.date.fromisoformat(d_)).days; chg_ = abs(HEAL[d_] / Bd[d_] - 1)
                if not (rec_ and 0 <= age_ <= HEAL_DAYS and chg_ <= HEAL_MAX + HEAL_EPS):
                    why_ = [w for w, c in (('no fallback record (revision log / heal list)', not rec_), (f'{age_} days old (> {HEAL_DAYS})', not 0 <= age_ <= HEAL_DAYS), (f'change {chg_:.4%} (> {HEAL_MAX:.1%})', chg_ > HEAL_MAX + HEAL_EPS)) if c]
                    print(f'::error title=btc-daily heal refused::{d_} {Bd[d_]} -> {HEAL[d_]}: ' + '; '.join(why_) + ' (R-s); file unchanged'); sys.exit(1)
            if hold_from:
                for d_ in [x for x in bars if x >= hold_from[0]]: del bars[d_]
                print(f'::warning::btc-daily paused at {hold_from[0]} (BTC value pending: fallback source); later days wait so the file stays gap-free')
        except Exception as e: print('history.json not used:', type(e).__name__, e); HEAL.clear()
    else:                                                    # no history.json: provisional dates heal from Yahoo's own final bar
        for d_ in sorted(PROV):
            if d_ <= last and d_ in YB:
                PROV.discard(d_)
                if dict(j['d']).get(d_) != YB[d_]: HEAL[d_] = YB[d_]
    def done(code=0):
        if STALL and code == 0:
            print(f'::error title=btc-daily stalled::BTC {STALL[0]} still on a fallback source more than {STALL_H} h after its UTC day ended (Yahoo final bar never arrived). See tools/btc_daily.py header / bp ROLLOUT "Stall".')
            sys.exit(3)
        sys.exit(code)
    if CHECK: print('btc-daily check-only: no stall' if not STALL else ''); done(0)
    new = sorted(d for d in bars if d > last)
    # no gaps allowed: every calendar day from last+1 to the newest added must be present
    want = []; d = dt.date.fromisoformat(last) + dt.timedelta(days=1)
    while new and d.isoformat() <= new[-1]: want.append(d.isoformat()); d += dt.timedelta(days=1)
    if new and want != new: print('gap in Yahoo bars, not appending:', sorted(set(want) - set(new))); sys.exit(1)
    PROV = {d_ for d_ in PROV if d_ <= (new[-1] if new else last)}
    if not new and not HEAL and sorted(PROV) == PROV0: print(f'btc-daily up to date (through {last})' + (f'; provisional (fallback, waiting for Yahoo): {sorted(PROV)}' if PROV else '')); done(0)
    for d_, v_ in HEAL.items():                               # sanity: a heal is never a large jump vs. the neighbouring stored closes
        nb = [v for x, v in j['d'] if x != d_ and abs((dt.date.fromisoformat(x) - dt.date.fromisoformat(d_)).days) == 1]
        if not v_ > 0 or any(not (0.5 * n_ < v_ < 2 * n_) for n_ in nb): print('implausible heal', d_, v_); sys.exit(1)
    j['d'] = [[x, HEAL.get(x, v)] for x, v in j['d']]
    prev = j['d'][-1][1]
    for d in new:
        if not (0.5 * prev < bars[d] < 2 * prev): print('implausible close', d, bars[d]); sys.exit(1)
        prev = bars[d]
    j['d'] += [[d, bars[d]] for d in new]
    if new: j['end'] = new[-1]
    if PROV: j['provisional'] = sorted(PROV)
    else: j.pop('provisional', None)
    tmp = F + '.tmp'; json.dump(j, open(tmp, 'w'), separators=(',', ':')); json.load(open(tmp)); os.replace(tmp, F)
    if HEAL: print('btc-daily HEALED to the final close:', ', '.join(f'{d} {v}' for d, v in sorted(HEAL.items())))
    if new: print('btc-daily appended:', ', '.join(f'{d} {bars[d]}' for d in new))
    print('btc-daily provisional (fallback, waiting for Yahoo):', sorted(PROV) if PROV else 'none')
    done(0)
except SystemExit: raise
except Exception as e:
    print('btc-daily update failed (file untouched):', type(e).__name__, e); sys.exit(1)
