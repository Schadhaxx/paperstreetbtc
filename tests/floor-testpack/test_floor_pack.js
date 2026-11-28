#!/usr/bin/env node
/* BTC trend-support (floor) test pack.
   Always checks the reference against fixtures/. With --impl / --panel /
   --repo (or FLOOR_IMPL / FLOOR_PANEL / FLOOR_REPO), also asserts
   Pepper's implementation matches.
   usage:
     node test_floor_pack.js --impl reference_floor.js
     node test_floor_pack.js --repo /path/to/paperstreetbtc
     node test_floor_pack.js --panel /path/to/assets/js/btcchart-panel.js
   exit 0 = all pass
*/
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const HERE = __dirname;
const FIX = path.join(HERE, 'fixtures');
const REF = require(path.join(HERE, 'reference_floor.js'));

let n = 0, f = 0, TARGET = 'reference';
const chk = (name, ok, info) => {
  n++;
  if (ok) console.log('PASS', '[' + TARGET + ']', name);
  else {
    f++;
    const extra = info === undefined || info === '' ? '' : ('  ' + (typeof info === 'string' ? info : JSON.stringify(info)));
    console.log('FAIL', '[' + TARGET + ']', name + extra);
  }
};
const close = (a, b, tol) => (a == null && b == null) || (a != null && b != null && Math.abs(Number(a) - Number(b)) <= (tol || 0.005));
const load = (name) => JSON.parse(fs.readFileSync(path.join(FIX, name), 'utf8'));

function parseArgs(argv) {
  const out = { impl: process.env.FLOOR_IMPL, panel: process.env.FLOOR_PANEL, repo: process.env.FLOOR_REPO, refOnly: false };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--ref-only') out.refOnly = true;
    else if (a === '--impl') out.impl = argv[++i];
    else if (a === '--panel') out.panel = argv[++i];
    else if (a === '--repo') out.repo = argv[++i];
  }
  return out;
}

function discoverRepo(cli) {
  if (cli) return path.resolve(cli);
  const cands = [
    path.join(HERE, 'assets', 'js', 'btcchart-panel.js'),
    path.join(HERE, '..', 'assets', 'js', 'btcchart-panel.js'),
    path.join(HERE, '..', '..', 'assets', 'js', 'btcchart-panel.js')
  ];
  for (const c of cands) {
    if (fs.existsSync(c) && fs.existsSync(path.join(path.dirname(c), '..', 'data'))) {
      return path.resolve(path.dirname(c), '..', '..');
    }
  }
  return null;
}

function loadImpl(implPath) {
  const resolved = path.resolve(implPath);
  const absRef = path.resolve(path.join(HERE, 'reference_floor.js'));
  if (resolved === absRef) return REF;
  return require(resolved);
}

function loadPanel(panelPath) {
  const src = fs.readFileSync(panelPath, 'utf8');
  const doc = {
    addEventListener() {}, documentElement: { getAttribute: () => 'dark' },
    getElementById: () => null, querySelectorAll: () => [], querySelector: () => null,
    createElement: () => ({ appendChild() {}, setAttribute() {}, style: {} }),
    createTextNode: () => ({}), body: { appendChild() {} }
  };
  const P = {
    $: () => null, U: (p) => p, RAW: '', pill: null, menu: null,
    live: { usd: null, chg: null }, fmt: (v) => '$' + Math.round(v),
    curVal: (v) => v, curSym: () => '$', cadTag: () => '',
    CUR: { code: 'USD', rate: 1 }, mp: null, panelReady: false
  };
  const sb = { window: null, document: doc, console, fetch: () => Promise.reject(new Error('no net')), addEventListener() {} };
  sb.window = sb; sb.window.__BTCP = P;
  vm.createContext(sb); vm.runInContext(src, sb);
  if (!P._floor) throw new Error('panel does not expose P._floor');
  return wrapPanel(P._floor);
}

/* Adapt P._floor (at, broken, and after the redo: isWeekComplete, evaluateBreak, display)
   to the reference API names used by this pack. */
function wrapPanel(F) {
  return {
    evaluate_break: F.evaluateBreak || F.evaluate_break || null,
    evaluateBreak: F.evaluateBreak || F.evaluate_break || null,
    floor_broken: (j, asOf) => {
      if (typeof F.broken === 'function') {
        try { return F.broken.length >= 2 ? F.broken(j, asOf) : F.broken(j); }
        catch (e) { return F.broken(j, asOf); }
      }
      return undefined;
    },
    broken: F.broken,
    display_copy: F.display || F.display_copy || F.displayCopy || null,
    display: F.display || F.display_copy || F.displayCopy || null,
    is_week_complete: F.isWeekComplete || F.is_week_complete || null,
    isWeekComplete: F.isWeekComplete || F.is_week_complete || null,
    week_monday: F.weekMonday || F.week_monday || null,
    weekMonday: F.weekMonday || F.week_monday || null,
    at: F.at,
    floor_at_payload: F.at || F.floorAtPayload,
    floorAt: F.at
  };
}

function evOf(mod, payload, asOf) {
  const fn = mod.evaluate_break || mod.evaluateBreak;
  if (typeof fn !== 'function') return null;
  try { return fn.length >= 2 ? fn(payload, asOf) : fn(payload); }
  catch (e) { return fn(payload, asOf); }
}
function brokenOf(mod, payload, asOf) {
  const ev = evOf(mod, payload, asOf);
  if (ev && typeof ev.broken === 'boolean') return ev.broken;
  const fn = mod.floor_broken || mod.broken;
  if (typeof fn !== 'function') return undefined;
  try { return fn.length >= 2 ? fn(payload, asOf) : fn(payload); }
  catch (e) { return fn(payload, asOf); }
}
function displayOf(mod, payload, asOf) {
  const fn = mod.display_copy || mod.display || mod.floor_display || mod.displayCopy;
  if (typeof fn !== 'function') return null;
  try { return fn.length >= 2 ? fn(payload, asOf) : fn(payload); }
  catch (e) { return fn(payload, asOf); }
}
function completeOf(mod, week, asOf) {
  const fn = mod.is_week_complete || mod.isWeekComplete;
  if (typeof fn !== 'function') return { err: 'missing is_week_complete' };
  return { val: fn(week, asOf) };
}
function mondayOf(mod, ts) {
  const fn = mod.week_monday || mod.weekMonday;
  if (typeof fn !== 'function') return { err: 'missing week_monday' };
  const val = fn(ts);
  if (val instanceof Date) {
    return { val: REF.isoDate(val) };
  }
  return { val: String(val).slice(0, 10) };
}
function floorAtOf(mod, payload, ds) {
  if (typeof mod.at === 'function') return mod.at(payload, ds);
  if (typeof mod.floor_at_payload === 'function') return mod.floor_at_payload(payload, ds);
  if (typeof mod.floorAt === 'function') return mod.floorAt(payload, ds);
  return 'MISSING';
}

const KEYS = [
  'broken', 'lastCompletedWeek', 'lastCompletedSunday', 'lastCompletedClose',
  'floorAtLastCompleted', 'pctAtLastCompleted', 'inProgressWeek',
  'inProgressClose', 'inProgressPct', 'inProgressTriggersBreak',
  'maxUnderPct', 'floorNow', 'breakTrigger', 'dashInProgress', 'lineIsRed'
];

function chkEval(label, got, exp) {
  if (!got) { chk(label + ': evaluate_break present', false, 'missing evaluate_break'); return; }
  chk(label + ': broken', got.broken === exp.broken, 'got ' + got.broken + ' want ' + exp.broken);
  for (const key of KEYS) {
    if (key === 'broken' || !(key in exp)) continue;
    const want = exp[key], have = got[key];
    if (typeof want === 'boolean' || want == null || have == null) {
      chk(label + ': ' + key, have === want, 'got ' + have + ' want ' + want);
    } else if (typeof want === 'number') {
      const tol = /Pct$/.test(key) || key === 'maxUnderPct' ? 0.05 : 0.005;
      chk(label + ': ' + key, close(have, want, tol), 'got ' + have + ' want ' + want);
    } else {
      chk(label + ': ' + key, have === want, 'got ' + have + ' want ' + want);
    }
  }
}

function chkDisplay(label, got, exp) {
  if (!got) { chk(label + ': display present', false, 'missing display / display_copy'); return; }
  for (const key of ['label', 'asOf', 'source', 'breakRule', 'brokenNote']) {
    chk(label + ': display.' + key, got[key] === exp[key], 'got ' + JSON.stringify(got[key]) + ' want ' + JSON.stringify(exp[key]));
  }
}

function runAgainst(mod, real, completed, inprog, boundary, weekb) {
  let ev = evOf(mod, real, real.asOf);
  if (!ev && mod === REF) ev = REF.evaluateBreak(real, real.asOf);
  chkEval('real_26nov', ev, real.expected);
  const br = brokenOf(mod, real, real.asOf);
  chk('real_26nov: floor_broken is False (in-progress Thu close must not break)', br === false, 'got ' + br);
  const stale = Object.assign({}, real, { broken: true });
  const brStale = brokenOf(mod, stale, real.asOf);
  chk('real_26nov: stale broken=true flag is ignored', brStale === false, 'got ' + brStale);
  chkDisplay('real_26nov', displayOf(mod, real, real.asOf), real.expected.display);
  for (const ds of Object.keys(real.expected.floorAt)) {
    const want = real.expected.floorAt[ds];
    const have = floorAtOf(mod, real, ds);
    if (have === 'MISSING') { chk('real_26nov: floor_at(' + ds + ')', false, 'missing floor_at'); break; }
    if (want == null) chk('real_26nov: floor_at(' + ds + ') is null', have == null, have);
    else chk('real_26nov: floor_at(' + ds + ')', close(have, want, 0.05), 'got ' + have + ' want ' + want);
  }

  ev = evOf(mod, completed, completed.asOf) || (mod === REF ? REF.evaluateBreak(completed) : null);
  chkEval('completed_week_break', ev, completed.expected);
  chk('completed_week_break: floor_broken is True', brokenOf(mod, completed, completed.asOf) === true, 'got ' + brokenOf(mod, completed, completed.asOf));
  const d1 = displayOf(mod, completed, completed.asOf);
  chkDisplay('completed_week_break', d1, completed.expected.display);
  if (d1) chk('completed_week_break: visible broken note (not only a colour change)', typeof d1.brokenNote === 'string' && d1.brokenNote.length > 0, d1.brokenNote);

  ev = evOf(mod, inprog, inprog.asOf) || (mod === REF ? REF.evaluateBreak(inprog) : null);
  chkEval('in_progress_only_dip', ev, inprog.expected);
  chk('in_progress_only_dip: floor_broken is False', brokenOf(mod, inprog, inprog.asOf) === false, 'got ' + brokenOf(mod, inprog, inprog.asOf));
  chkDisplay('in_progress_only_dip', displayOf(mod, inprog, inprog.asOf), inprog.expected.display);

  boundary.cases.forEach((c, i) => {
    const payload = Object.assign({}, boundary, { asOf: c.asOf, weeks: c.weeks });
    ev = evOf(mod, payload, c.asOf) || (mod === REF ? REF.evaluateBreak(payload, c.asOf) : null);
    const tag = 'boundary[' + i + ' close=' + c.weeks[c.weeks.length - 1][1] + ' asOf=' + c.asOf + ']';
    chk(tag + ': broken', ev && ev.broken === c.expected.broken, ev ? ev.broken : 'missing evaluate_break');
  });

  weekb.cases.forEach((c) => {
    const payload = Object.assign({}, weekb, { asOf: c.asOf, weeks: c.weeks });
    const comp = completeOf(mod, weekb.weekUnderTest, c.asOf);
    chk('week_boundary asOf=' + c.asOf + ': is_week_complete', !comp.err && comp.val === c.expectedComplete, comp.err || ('got ' + comp.val + ' want ' + c.expectedComplete));
    const mon = mondayOf(mod, c.asOf);
    chk('week_boundary asOf=' + c.asOf + ': week_monday', !mon.err && mon.val === c.expectedMondayOfAsOf, mon.err || ('got ' + mon.val + ' want ' + c.expectedMondayOfAsOf));
    const brw = brokenOf(mod, payload, c.asOf);
    chk('week_boundary asOf=' + c.asOf + ': broken', brw === c.expected.broken, 'got ' + brw + ' want ' + c.expected.broken);
  });
}

function main() {
  const args = parseArgs(process.argv);
  const real = load('real_26nov.json');
  const completed = load('completed_week_break.json');
  const inprog = load('in_progress_only_dip.json');
  const boundary = load('boundary_minus_2pct.json');
  const weekb = load('week_boundary_sun_mon.json');

  TARGET = 'reference';
  runAgainst(REF, real, completed, inprog, boundary, weekb);

  if (args.refOnly) {
    console.log('FLOOR PACK JS TESTS', n, 'FAIL', f, '(reference only)');
    process.exit(f ? 1 : 0);
  }

  const repo = discoverRepo(args.repo);
  let implPath = args.impl ? path.resolve(args.impl) : null;
  let panelPath = args.panel ? path.resolve(args.panel) : null;
  if (!implPath && !panelPath && repo) {
    const p = path.join(repo, 'assets', 'js', 'btcchart-panel.js');
    if (fs.existsSync(p)) panelPath = p;
  }

  if (!implPath && !panelPath) {
    console.log('FLOOR PACK JS TESTS', n, 'FAIL', f, '(reference only; pass --impl, --panel or --repo to check Pepper)');
    process.exit(f ? 1 : 0);
  }

  if (implPath) {
    TARGET = implPath;
    try {
      runAgainst(loadImpl(implPath), real, completed, inprog, boundary, weekb);
    } catch (e) {
      chk('import ' + implPath, false, String(e && e.stack || e));
    }
  }
  if (panelPath) {
    TARGET = panelPath;
    try {
      runAgainst(loadPanel(panelPath), real, completed, inprog, boundary, weekb);
    } catch (e) {
      chk('load panel ' + panelPath, false, String(e && e.stack || e));
    }
  }

  console.log('FLOOR PACK JS TESTS', n, 'FAIL', f);
  process.exit(f ? 1 : 0);
}

main();
