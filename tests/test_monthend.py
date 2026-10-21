"""Local test of the month-end logic embedded in .github/workflows/prices.yml (run: python3 tests/test_monthend.py)."""
import re, json, datetime, urllib.request, textwrap, pathlib
src = pathlib.Path(__file__).resolve().parents[1].joinpath('.github/workflows/prices.yml').read_text()
code = textwrap.dedent(re.search(r'(# --- monthend begin ---.*?# --- monthend end ---)', src, re.S).group(1).replace('\n          ', '\n'))
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'paperstreetbtc-cache'}), timeout=15) as f: return json.load(f)
g = {'datetime': datetime}; exec(code, g)
U = lambda s: datetime.datetime.fromisoformat(s).replace(tzinfo=datetime.timezone.utc)
D = datetime.date.fromisoformat
ok = True
def check(name, got, want):
    global ok; r = got == want; ok &= r; print(('PASS' if r else 'FAIL'), name, got, '(want', want, ')')
# target month in ET, incl. UTC-midnight boundary
check('Oct 31 midday ET -> Sep 30', g['me_target'](U('2026-10-31T16:00:00')), D('2026-09-30'))
check('Nov 1 02:00Z = Oct 31 22:00 ET -> Sep 30', g['me_target'](U('2026-11-01T02:00:00')), D('2026-09-30'))
check('Nov 1 04:30Z = Nov 1 00:30 ET -> Oct 31', g['me_target'](U('2026-11-01T04:30:00')), D('2026-10-31'))
check('Sat 00:30Z run (Fri evening ET) Mar 1 2025 -> Jan 31', g['me_target'](U('2025-03-01T00:30:00')), D('2025-01-31'))
# last actual trading session (real Yahoo bars)
for name, sym, last, want in [
    ('weekday Sep 30 2026 (Wed)', 'SPY', '2026-09-30', '2026-09-30'),
    ('Saturday month-end Feb 28 2026', 'SPY', '2026-02-28', '2026-02-27'),
    ('Sunday month-end Aug 31 2025', 'SPY', '2025-08-31', '2025-08-29'),
    ('holiday: Mar 31 2024 Sun, Mar 29 Good Friday', 'SPY', '2024-03-31', '2024-03-28'),
    ('holiday GLD Good Friday 2024', 'GLD', '2024-03-31', '2024-03-28'),
    ('BTC 24/7 Aug 31 2025 (Sunday)', 'BTC-USD', '2025-08-31', '2025-08-31'),
    ('BTC Feb 28 2026 (Saturday)', 'BTC-USD', '2026-02-28', '2026-02-28')]:
    dd, c = g['me_close'](sym, D(last), get); check(f'{name}: {sym} close {round(c,2)}', dd, D(want))
print('ALL PASS' if ok else 'FAILURES'); raise SystemExit(0 if ok else 1)
