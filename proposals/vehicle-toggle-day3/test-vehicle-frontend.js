/* Vehicle toggle Day 3 headless harness (Node, no browser).
   What it proves:
   1. book.js navV (the homepage engine) still gives the Day 2 vehicle NAVs.
   2. The compare.js vehicleVals replica (same re-basing algorithm, written
      for the Compare page which has its own ledger) reproduces book.js
      navV to the cent at base and at the latest close, for every sleeve
      and vehicle — so the Compare line cannot drift from the tracker.
   3. The latest-close / weekend-flat price-date logic used by s6.js
      (vehiclePriceOnOrBefore semantics) behaves as specified.
   What it does NOT prove (needs a real browser, Day 4): DOM rendering,
   button clicks, the popover, phone-width layout, or the live-price flow.
   Usage: node proposals/vehicle-toggle-day3/test-vehicle-frontend.js
   Exit 0 = all checks pass. */
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const root = path.join(__dirname, '..', '..');
const history = JSON.parse(fs.readFileSync('/tmp/history.json', 'utf8'));
const vehicle = JSON.parse(fs.readFileSync(path.join(root, 'assets/data/vehicle-daily.json'), 'utf8'));

const sandbox = { console, location: { search: '' },
  fetch: (url) => String(url).includes('history.json')
    ? Promise.resolve({ ok: true, json: () => Promise.resolve(history) })
    : Promise.reject(new Error('unexpected fetch: ' + url)) };
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root, 'assets/js/ledger.js'), 'utf8'), sandbox);
vm.runInContext(fs.readFileSync(path.join(root, 'assets/js/book.js'), 'utf8'), sandbox);

let failures = 0;
function check(name, cond, detail) {
  console.log((cond ? 'PASS' : 'FAIL') + ' ' + name + (detail !== undefined ? ' — ' + detail : ''));
  if (!cond) failures++;
}
function cents(v) { return Math.round(v * 100) / 100; }

/* Compare-page replica, transcribed from compare.js vehicleVals (same
   inputs: history closes CL, sessions D, ledger L, firstOn/lastOn). */
const CL = history.closes;
const D = Object.keys(CL).sort();
const LAST = D[D.length - 1];
const L0 = sandbox.window.PSLEDGER;
/* Compare.js carries its own ledger copy whose strc rows are
   [ex, pay, $/share] (3 fields), while ledger.js rows are
   [record, ex, pay, $/share] (4 fields). The replica must use the
   Compare shape, or the amount destructures to a date string (NaN). */
const L = { base: L0.base, start: L0.start, sleeves: L0.sleeves,
  strc: L0.strc.map((r) => [r[1], r[2], r[3]]) };
const firstOn = (d) => D.find((x) => x >= d);
const lastOn = (d) => [...D].reverse().find((x) => x <= d);
function vehicleVals(VD, veh) {
  const VM = {}; VD.vehicles[veh].forEach((p) => { VM[p[0]] = p[1]; });
  const out = {};
  for (const k in L.sleeves) {
    const sl = L.sleeves[k], h = {}, b = CL[L.base];
    for (const a in sl.w) h[a] = a === 'BTC' ? L.start * sl.w[a] / VM[L.base] : L.start * sl.w[a] / b[a];
    let rec = []; const v = {};
    const evs = L.strc.map(([ex, pay, amt]) => ({ ex: firstOn(ex), pay: firstOn(pay), payS: pay, amt })).filter((e) => e.ex && e.ex <= LAST);
    for (const d of D) {
      for (const e of evs) { if (e.ex === d) { e.cash = h.STRC * e.amt; e.sh = h.STRC; rec.push(e); } }
      rec = rec.filter((e) => { if (e.pay && e.pay === d) { e.buys = {}; for (const a in sl.div) { const px = a === 'BTC' ? (VM[d] != null ? VM[d] : VM[lastOn(d)]) : CL[d][a]; const q = e.cash * sl.div[a] / px; h[a] = (h[a] || 0) + q; e.buys[a] = q; } return false; } return true; });
      let t = rec.reduce((x, e) => x + e.cash, 0);
      for (const a in h) t += h[a] * (a === 'BTC' ? (VM[d] != null ? VM[d] : VM[lastOn(d)]) : CL[d][a]);
      v[d] = t;
    }
    out[k] = v;
  }
  return out;
}

(async () => {
  const B = await sandbox.window.PSBook.ready;
  B.loadVehicleData(vehicle);
  const keys = ['berkshire', 'hodlr', 'hf', 'saylor'];
  const day2 = { // Day 2 report, 2026-10-28 vehicle NAVs
    IBIT: { berkshire: 97677.48, hodlr: 95391.75, hf: 95789.65, saylor: 104013.87 },
    FBTC: { berkshire: 97682.13, hodlr: 95400.02, hf: 95796.16, saylor: 104013.87 } };

  // 1. Homepage engine still matches Day 2.
  for (const v of ['IBIT', 'FBTC']) for (const k of keys)
    check('book navV ' + v + '/' + k + ' 2026-10-28', cents(B.navV(k, '2026-10-28', v)) === day2[v][k],
      '$' + cents(B.navV(k, '2026-10-28', v)) + ' vs Day 2 $' + day2[v][k]);

  // 2. Compare replica == book.js, to the cent, base + latest close.
  for (const v of ['IBIT', 'FBTC']) {
    const VV = vehicleVals(vehicle, v);
    for (const k of keys) {
      check('compare replica base ' + v + '/' + k, cents(VV[k]['2025-12-31']) === 100000, '$' + cents(VV[k]['2025-12-31']));
      check('compare replica == book ' + v + '/' + k + ' 2026-10-28',
        cents(VV[k]['2026-10-28']) === cents(B.navV(k, '2026-10-28', v)),
        'compare $' + cents(VV[k]['2026-10-28']) + ' vs book $' + cents(B.navV(k, '2026-10-28', v)));
      check('compare replica saylor/spot sanity ' + v + '/' + k, cents(VV[k]['2026-10-28']) > 0, '');
    }
  }

  // 3. Latest-close / weekend-flat semantics (book.js vehiclePriceOnOrBefore).
  check('latest close on/before 2026-10-29 is 2026-10-28 (pre-prices.yml)',
    B.vehiclePriceOnOrBefore('IBIT', '2026-10-29') === 46.14, '$' + B.vehiclePriceOnOrBefore('IBIT', '2026-10-29'));
  check('weekend flat Sat 2026-01-03 = Fri 2026-01-02 close',
    B.vehiclePriceOnOrBefore('IBIT', '2026-01-03') === vehicle.vehicles.IBIT.find((p) => p[0] === '2026-01-02')[1], '');
  check('weekend flat Sun 2026-01-04 = Fri 2026-01-02 close',
    B.vehiclePriceOnOrBefore('FBTC', '2026-01-04') === vehicle.vehicles.FBTC.find((p) => p[0] === '2026-01-02')[1], '');

  // 4. Static wiring checks: the files that must mention the shared protocol.
  const has = (f, s) => fs.readFileSync(path.join(root, f), 'utf8').includes(s);
  check('index.html loads vehicle.js', has('index.html', 'assets/js/vehicle.js'), '');
  check('vehicle.js uses sessionStorage (session-only)', has('assets/js/vehicle.js', 'sessionStorage'), '');
  check('vehicle.js dispatches psvehicle', has('assets/js/vehicle.js', "CustomEvent('psvehicle'"), '');
  check('s6.js uses atV', has('assets/js/s6.js', 'BK.atV'), '');
  check('s6.js uses navV for prior close', has('assets/js/s6.js', 'navPrior'), '');
  check('s2.js rebuilds on psvehicle', has('assets/js/s2.js', "addEventListener('psvehicle'"), '');
  check('s2.js uses navV', has('assets/js/s2.js', 'B.navV'), '');
  check('btcchart.js has popover vehicle row', has('assets/js/btcchart.js', 'bcVeh'), '');
  check('btcchart.js note: chart stays Spot', has('assets/js/btcchart.js', 'This chart stays Spot BTC'), '');
  check('compare.js follows psvehicle', has('assets/js/compare.js', "addEventListener('psvehicle'"), '');
  check('compare.js replica present', has('assets/js/compare.js', 'function vehicleVals'), '');
  check('no prices.yml change in Day 3', !fs.readFileSync(path.join(root, '.github/workflows/prices.yml'), 'utf8').includes('IBIT'), '');

  console.log(failures === 0 ? 'ALL CHECKS PASSED' : failures + ' CHECK(S) FAILED');
  process.exit(failures === 0 ? 0 : 1);
})().catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
