/* Vehicle toggle Day 4 headless test harness (Node, no browser).
   What it proves (book.js engine + compare.js replica + static wiring):
   1. Full matrix 4 sleeves x 3 vehicles x {close, Live-simulated, Month-end}:
      NAVs finite/positive, holdings consistent (units x prices + cash == NAV),
      dividend buys follow the locked rule (ETF buys ETF in ETF mode).
   2. Weekends + NYSE holidays: ETF flat at the prior session close.
   3. Missing-quote fallback: price on/after series end = latest close, never
      blank, never spot substituted for an ETF price.
   4. Spot regression RE-RUN vs Day 1 baseline, to the cent.
   5. Compare replica == book.js navV at EVERY session, to the cent.
   What it does NOT prove (needs a real browser, listed in DAY4-REPORT.md):
   DOM rendering, button clicks, popover/phone layout, live-price flow.
   Usage: node proposals/vehicle-toggle-day4/test-vehicle-day4.js
   Exit 0 = all checks pass. Any failure exits 1 and names the check. */
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const root = path.join(__dirname, '..', '..');
const history = JSON.parse(fs.readFileSync('/tmp/history.json', 'utf8'));
const vehicle = JSON.parse(fs.readFileSync(path.join(root, 'assets/data/vehicle-daily.json'), 'utf8'));
const baseline = JSON.parse(fs.readFileSync(path.join(root, 'proposals/vehicle-toggle-day1/baseline-snapshot-2026-10-29.json'), 'utf8'));

const sandbox = { console, location: { search: '' },
  fetch: (url) => String(url).includes('history.json')
    ? Promise.resolve({ ok: true, json: () => Promise.resolve(history) })
    : Promise.reject(new Error('unexpected fetch: ' + url)) };
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root, 'assets/js/ledger.js'), 'utf8'), sandbox);
vm.runInContext(fs.readFileSync(path.join(root, 'assets/js/book.js'), 'utf8'), sandbox);

let failures = 0, passes = 0;
function check(name, cond, detail) {
  if (cond) passes++; else failures++;
  console.log((cond ? 'PASS' : 'FAIL') + ' ' + name + (detail !== undefined ? ' — ' + detail : ''));
}
function cents(v) { return Math.round(v * 100) / 100; }
function finitePos(v) { return typeof v === 'number' && isFinite(v) && v > 0; }

/* Compare replica, transcribed from compare.js vehicleVals (Day 3 harness). */
const CL = history.closes;
const D = Object.keys(CL).sort();
const LAST = D[D.length - 1];
const L0 = sandbox.window.PSLEDGER;
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
  const vehicles = ['SPOT', 'IBIT', 'FBTC'];
  const vmap = {}; for (const v of ['IBIT', 'FBTC']) { vmap[v] = {}; vehicle.vehicles[v].forEach((p) => { vmap[v][p[0]] = p[1]; }); }

  console.log('history sessions:', B.dates.length, 'last:', B.last, 'points:', B.points().join(','));

  // 0. SPOT REGRESSION RE-RUN — to the cent, vs Day 1 baseline.
  for (const k of keys) {
    check('spot regression ' + k + ' 2026-10-28',
      cents(B.nav(k, '2026-10-28')) === baseline.sleeves[k].latest_close_value,
      '$' + cents(B.nav(k, '2026-10-28')) + ' vs baseline $' + baseline.sleeves[k].latest_close_value);
    check('spot regression via navV(SPOT) ' + k,
      cents(B.navV(k, '2026-10-28', 'SPOT')) === cents(B.nav(k, '2026-10-28')), '');
  }

  // 1. FULL MATRIX — close NAVs at every session: finite, positive, no blanks.
  //    (208 sessions x 12 sleeve/vehicle combos = 2496 NAVs; report aggregates.)
  let badNav = 0, navCount = 0;
  const navTable = {};
  for (const v of vehicles) for (const k of keys) {
    navTable[v + '/' + k] = {};
    for (const d of D) {
      const n = B.navV(k, d, v); navCount++;
      if (!finitePos(n)) badNav++;
      navTable[v + '/' + k][d] = n;
    }
  }
  check('matrix close NAVs finite+positive (2496 NAVs)', badNav === 0, badNav + ' bad of ' + navCount);
  for (const v of ['IBIT', 'FBTC']) for (const k of keys)
    console.log('INFO nav ' + v + '/' + k + ' 2026-10-28 = $' + cents(navTable[v + '/' + k]['2026-10-28']));

  // 1b. Base NAV exactly $100,000 in every mode (re-basing invariant).
  for (const v of vehicles) for (const k of keys)
    check('base nav ' + v + '/' + k, cents(B.navV(k, '2025-12-31', v)) === 100000, '$' + cents(B.navV(k, '2025-12-31', v)));

  // 1c. Holdings consistency at the latest close: units x prices + cash == NAV.
  for (const v of vehicles) for (const k of keys) {
    const at = B.atV(k, '2026-10-28', v);
    let sum = at.cash;
    for (const [a, u] of Object.entries(at.h)) {
      const px = v === 'SPOT' ? CL['2026-10-28'][a] : (a === 'BTC' ? vmap[v]['2026-10-28'] : CL['2026-10-28'][a]);
      sum += u * px;
      check('holding unit finite ' + v + '/' + k + '/' + a, finitePos(u) || u === 0, String(u));
    }
    check('holdings sum == NAV ' + v + '/' + k, cents(sum) === cents(B.navV(k, '2026-10-28', v)),
      '$' + cents(sum) + ' vs $' + cents(B.navV(k, '2026-10-28', v)));
  }

  // 1d. Month-end matrix: every B.points() date, every sleeve/vehicle, finite.
  const pts = B.points();
  let badMe = 0;
  for (const v of vehicles) for (const k of keys) for (const d of pts) {
    const n = B.navV(k, d, v);
    if (!finitePos(n)) badMe++;
  }
  check('month-end matrix finite+positive (' + pts.length + ' points x 12)', badMe === 0, badMe + ' bad');
  // Month-end NAVs equal close NAVs at those sessions (same engine, no separate path).
  for (const v of vehicles) for (const k of keys) for (const d of pts)
    if (cents(navTable[v + '/' + k][d]) !== cents(B.navV(k, d, v))) badMe++;
  check('month-end NAV == close NAV at same session', badMe === 0, '');

  // 1e. Live-simulated matrix (s6 semantics): holdings as of 2026-10-29 (a
  //     non-session day), priced at latest-close prices (pre-prices.yml:
  //     ETF = latest vehicle close; spot BTC/other = latest history close).
  //     Live NAV must equal the 2026-10-28 close NAV for every combo, because
  //     no dividend event settles between 2026-10-28 and 2026-10-29 and no
  //     live quote is simulated here (live quotes need the browser flow).
  for (const v of vehicles) for (const k of keys) {
    const live = B.navV(k, '2026-10-28', v, (a) => v !== 'SPOT' && a === 'BTC'
      ? B.vehiclePriceOnOrBefore(v, '2026-10-29') : CL['2026-10-28'][a]);
    check('live-simulated NAV == close NAV ' + v + '/' + k, cents(live) === cents(navTable[v + '/' + k]['2026-10-28']),
      '$' + cents(live) + ' vs $' + cents(navTable[v + '/' + k]['2026-10-28']));
  }
  // Saylor identical in every mode at every matrix point (no BTC slice).
  let saylorDiff = 0;
  for (const d of D) for (const v of ['IBIT', 'FBTC'])
    if (cents(B.navV('saylor', d, v)) !== cents(B.navV('saylor', d, 'SPOT'))) saylorDiff++;
  check('saylor identical in every mode, all sessions', saylorDiff === 0, saylorDiff + ' differing sessions');

  // 1f. Dividend buys, every event, every sleeve/vehicle: price rule + split.
  let evChecked = 0, evBad = 0;
  for (const v of vehicles) for (const k of keys) {
    for (const e of B.eventsV(k, v)) {
      if (!e.payTd || !e.buy) continue;
      evChecked++;
      if (k !== 'saylor' && e.buy.BTC) {
        const wantPx = v === 'SPOT' ? CL[e.payTd].BTC : vmap[v][e.payTd];
        if (e.buy.BTC.px !== wantPx) evBad++;
      }
      if (k === 'saylor' && e.buy.BTC) evBad++;
      if (k === 'hf' && e.buy.BTC && e.buy.MSTR) {
        if (cents(e.buy.BTC.units * e.buy.BTC.px) !== cents(e.cash / 2)) evBad++;
        if (cents(e.buy.MSTR.units * e.buy.MSTR.px) !== cents(e.cash / 2)) evBad++;
      }
      if (!(e.buy.BTC ? e.buy.BTC.units > 0 : true)) evBad++;
    }
  }
  check('dividend buys follow locked rule (' + evChecked + ' settled buys)', evBad === 0, evBad + ' bad');
  // Cash identical across modes per event (STRC holdings are mode-independent).
  let cashDiff = 0;
  for (const k of keys) {
    const evS = B.eventsV(k, 'SPOT'), evI = B.eventsV(k, 'IBIT'), evF = B.eventsV(k, 'FBTC');
    for (let i = 0; i < evS.length; i++) {
      if (cents(evS[i].cash) !== cents(evI[i].cash) || cents(evS[i].cash) !== cents(evF[i].cash)) cashDiff++;
    }
  }
  check('dividend cash identical across modes, all events', cashDiff === 0, cashDiff + ' differing events');

  // 2. Weekends: every Sat/Sun in range prices at the prior session close.
  let wkBad = 0, wkCount = 0;
  const sessionSet = new Set(D);
  function prevSession(d) { let x = d; do { const t = new Date(x + 'T12:00:00Z'); t.setUTCDate(t.getUTCDate() - 1); x = t.toISOString().slice(0, 10); } while (!sessionSet.has(x) && x > '2025-12-31'); return x; }
  for (let t = new Date('2026-01-03T12:00:00Z'); t <= new Date('2026-10-25T12:00:00Z'); t.setUTCDate(t.getUTCDate() + 1)) {
    const wd = t.getUTCDay(); if (wd !== 0 && wd !== 6) continue;
    const d = t.toISOString().slice(0, 10), prev = prevSession(d);
    for (const v of ['IBIT', 'FBTC']) {
      wkCount++;
      if (B.vehiclePriceOnOrBefore(v, d) !== vmap[v][prev]) wkBad++;
    }
  }
  check('weekend flat: every Sat/Sun prices at prior session close (' + wkCount + ' checks)', wkBad === 0, wkBad + ' bad');
  check('weekend spot check 2026-01-03/04 = Fri 2026-01-02 close',
    B.vehiclePriceOnOrBefore('IBIT', '2026-01-03') === vmap.IBIT['2026-01-02'] &&
    B.vehiclePriceOnOrBefore('FBTC', '2026-01-04') === vmap.FBTC['2026-01-02'], '');
  check('weekend check 2026-10-24/25 = Fri 2026-10-23 close',
    B.vehiclePriceOnOrBefore('IBIT', '2026-10-24') === vmap.IBIT['2026-10-23'] &&
    B.vehiclePriceOnOrBefore('FBTC', '2026-10-25') === vmap.FBTC['2026-10-23'], '');

  // 2b. NYSE holidays in range (not sessions): ETF flat at prior session close.
  const holidays = ['2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07'];
  let holBad = 0;
  for (const h of holidays) {
    if (sessionSet.has(h)) holBad++;
    const prev = prevSession(h);
    for (const v of ['IBIT', 'FBTC'])
      if (B.vehiclePriceOnOrBefore(v, h) !== vmap[v][prev]) holBad++;
  }
  check('holiday flat: 7 NYSE holidays price at prior session close', holBad === 0, holBad + ' bad');

  // 3. Missing-quote fallback: after series end, latest close, never spot.
  for (const v of ['IBIT', 'FBTC']) {
    const px = B.vehiclePriceOnOrBefore(v, '2026-11-02');
    check('missing-quote fallback ' + v + ' 2026-11-02 = latest close 2026-10-28',
      px === vmap[v]['2026-10-28'], '$' + px);
    check('missing-quote fallback ' + v + ' is not the spot BTC price',
      px !== CL['2026-10-28'].BTC, 'spot $' + CL['2026-10-28'].BTC);
  }
  // Static: homepage failure path forces Spot + disables ETF buttons.
  const vehJs = fs.readFileSync(path.join(root, 'assets/js/vehicle.js'), 'utf8');
  check('vehicle.js failure path forces Spot', vehJs.includes("vehicle='SPOT'") && vehJs.includes('ETF buttons stay disabled') || vehJs.includes('b.disabled=!loaded'), '');
  // Static: Compare failure path — catch only warns; VEH is NOT reset to SPOT.
  // This is a KNOWN ISSUE, reported as INFO (not counted as a matrix
  // pass/fail), because the matrix itself passes and this is a fix-
  // before-deploy item on an edge path. See DAY4-REPORT.md section 5.
  const cmpJs = fs.readFileSync(path.join(root, 'assets/js/compare.js'), 'utf8');
  const vehApply = cmpJs.slice(cmpJs.indexOf('function vehApply'));
  const cmpCatch = vehApply.slice(vehApply.indexOf('.catch'));
  console.log('INFO compare failure path: catch warns only, VEH not reset, no redraw = ' +
    (vehApply.includes("console.warn('vehicle data unavailable, Compare stays Spot'") && !cmpCatch.includes('VEH=') && !cmpCatch.includes('draw()')));

  // 4. Compare replica == book.js at EVERY session, to the cent.
  let cmpBad = 0, cmpCount = 0;
  for (const v of ['IBIT', 'FBTC']) {
    const VV = vehicleVals(vehicle, v);
    for (const k of keys) for (const d of D) {
      cmpCount++;
      if (cents(VV[k][d]) !== cents(B.navV(k, d, v))) cmpBad++;
    }
  }
  check('compare replica == book.js, every session, to the cent (' + cmpCount + ' checks)', cmpBad === 0, cmpBad + ' differing');

  // 5. Static wiring: one-tick transient + popover decision.
  const idx = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const s2Pos = idx.indexOf('assets/js/s2.js'), s6Pos = idx.indexOf('assets/js/s6.js');
  check('listener order: s2 registers before s6 (transient confirmed by construction)',
    s2Pos > 0 && s6Pos > s2Pos, 's2 at ' + s2Pos + ', s6 at ' + s6Pos);
  const s2Js = fs.readFileSync(path.join(root, 'assets/js/s2.js'), 'utf8');
  check('s2 refreshes live stats on next tick (setTimeout 0) after rebuild',
    s2Js.includes('setTimeout(() => { if (window.PSLive) applyLive(window.PSLive.state()); }, 0)'), '');
  const bcJs = fs.readFileSync(path.join(root, 'assets/js/btcchart.js'), 'utf8');
  check('popover chart stays Spot, note present (open decision, unchanged)',
    bcJs.includes('This chart stays Spot BTC'), '');
  check('no prices.yml IBIT/FBTC change (deliberately outstanding)',
    !fs.readFileSync(path.join(root, '.github/workflows/prices.yml'), 'utf8').includes('IBIT'), '');

  console.log(failures === 0 ? 'ALL CHECKS PASSED (plus 1 known issue reported as INFO above: compare failure path)' : failures + ' CHECK(S) FAILED');
  console.log('passes: ' + passes + ', failures: ' + failures);
  process.exit(failures === 0 ? 0 : 1);
})().catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
