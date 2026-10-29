/* Vehicle toggle Day 2 test harness (Node, headless).
   Loads ledger.js + book.js with stubbed window/location/fetch, feeds the
   real data-branch history.json and the Day 1 vehicle-daily.json, then runs
   the SPOT REGRESSION GATE and the vehicle-mapping checks.
   Usage: node proposals/vehicle-toggle-day2/test-vehicle-mapping.js
   Exit 0 = all checks pass. Any failure exits 1 and names the check. */
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const root = path.join(__dirname, '..', '..');
const history = JSON.parse(fs.readFileSync('/tmp/history.json', 'utf8'));
const vehicle = JSON.parse(fs.readFileSync(path.join(root, 'assets/data/vehicle-daily.json'), 'utf8'));
const baseline = JSON.parse(fs.readFileSync(path.join(root, 'proposals/vehicle-toggle-day1/baseline-snapshot-2026-10-29.json'), 'utf8'));

const sandbox = {
  console,
  location: { search: '' },
  fetch: (url) => {
    if (String(url).includes('history.json')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(history) });
    }
    return Promise.reject(new Error('unexpected fetch: ' + url));
  },
};
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

(async () => {
  const B = await sandbox.window.PSBook.ready;
  console.log('history sessions:', B.dates.length, 'last:', B.last);
  B.loadVehicleData(vehicle);
  const LAST = '2026-10-28';
  const keys = ['berkshire', 'hodlr', 'hf', 'saylor'];

  // 1. SPOT REGRESSION GATE — must match Day 1 baseline to the cent.
  for (const k of keys) {
    const got = cents(B.nav(k, LAST));
    const want = baseline.sleeves[k].latest_close_value;
    check('spot nav ' + k + ' ' + LAST, got === want, 'got $' + got + ', want $' + want);
    const at = B.at(k, LAST);
    check('spot cash ' + k, cents(at.cash) === baseline.sleeves[k].receivable_cash,
      'got $' + cents(at.cash) + ', want $' + baseline.sleeves[k].receivable_cash);
    for (const [asset, units] of Object.entries(baseline.sleeves[k].holdings_units_at_last_session)) {
      const diff = Math.abs((at.h[asset] || 0) - units);
      check('spot units ' + k + '/' + asset, diff < 1e-6, 'diff ' + diff);
    }
    // Spot via the vehicle API must be identical to the legacy API.
    check('atV SPOT == at ' + k, cents(B.navV(k, LAST, 'SPOT')) === got, '');
  }

  // 2. Vehicle base: every sleeve starts at exactly $100,000 in every mode.
  for (const v of ['SPOT', 'IBIT', 'FBTC']) {
    for (const k of keys) {
      check('base nav ' + v + '/' + k, cents(B.navV(k, '2025-12-31', v)) === 100000,
        '$' + cents(B.navV(k, '2025-12-31', v)));
    }
  }

  // 3. Vehicle NAVs at the latest close (reported, sanity-banded, not asserted
  // against an external figure — there is none; the gate is spot, above).
  for (const v of ['IBIT', 'FBTC']) {
    for (const k of keys) {
      console.log('INFO nav ' + v + '/' + k + ' ' + LAST + ' = $' + cents(B.navV(k, LAST, v)));
    }
  }

  // 4. Saylor Moon has no BTC slice: vehicle NAV must equal spot NAV exactly.
  for (const v of ['IBIT', 'FBTC']) {
    check('saylor unchanged in ' + v, cents(B.navV('saylor', LAST, v)) === cents(B.nav('saylor', LAST)), '');
  }

  // 5. Dividend rule: first settled STRC event — same cash, different buy price.
  // Berkshire, first event (record 2026-01-15, pay rolled to a session).
  for (const v of ['SPOT', 'IBIT', 'FBTC']) {
    const ev = B.eventsV('berkshire', v)[0];
    console.log('INFO first STRC event ' + v + ': payTd=' + ev.payTd + ' cash=$' + cents(ev.cash) +
      ' buy=' + JSON.stringify(ev.buy));
  }
  const evSpot = B.eventsV('berkshire', 'SPOT')[0];
  const evIbit = B.eventsV('berkshire', 'IBIT')[0];
  check('dividend cash identical across modes', cents(evSpot.cash) === cents(evIbit.cash), '$' + cents(evSpot.cash));
  check('ETF dividend buys ETF at vehicle close',
    evIbit.buy.BTC && evIbit.buy.BTC.px === vehicle.vehicles.IBIT.find((p) => p[0] === evIbit.payTd)[1],
    'px $' + (evIbit.buy.BTC && evIbit.buy.BTC.px));
  check('spot dividend buys spot at spot close',
    evSpot.buy.BTC && evSpot.buy.BTC.px === history.closes[evSpot.payTd].BTC,
    'px $' + (evSpot.buy.BTC && evSpot.buy.BTC.px));
  // Hedge Fund 50/50 split preserved in ETF mode.
  const hfIbit = B.eventsV('hf', 'IBIT')[0];
  check('hedge fund ETF split 50/50', !!hfIbit.buy.BTC && !!hfIbit.buy.MSTR &&
    cents(hfIbit.buy.BTC.units * hfIbit.buy.BTC.px) === cents(hfIbit.cash / 2), JSON.stringify(hfIbit.buy));

  // 6. Weekend flat rule: Sat/Sun after a Friday session price at Friday close.
  const fri = '2026-01-02'; // Friday session in the series
  check('weekend flat Sat', B.vehiclePriceOnOrBefore('IBIT', '2026-01-03') === vehicle.vehicles.IBIT.find((p) => p[0] === fri)[1], '');
  check('weekend flat Sun', B.vehiclePriceOnOrBefore('FBTC', '2026-01-04') === vehicle.vehicles.FBTC.find((p) => p[0] === fri)[1], '');

  // 7. A partial vehicle series must throw, never silently misprice.
  const bad = JSON.parse(JSON.stringify(vehicle));
  bad.vehicles.FBTC = bad.vehicles.FBTC.slice(0, -1);
  let threw = false;
  try { B.loadVehicleData(bad); } catch (e) { threw = true; console.log('INFO partial series threw as designed: ' + e.message); }
  check('partial series throws', threw, '');
  B.loadVehicleData(vehicle); // restore good data

  console.log(failures === 0 ? 'ALL CHECKS PASSED' : failures + ' CHECK(S) FAILED');
  process.exit(failures === 0 ? 0 : 1);
})().catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
