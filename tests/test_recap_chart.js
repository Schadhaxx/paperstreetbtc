#!/usr/bin/env node
/* Monthly recap chart (enhancements 5): monthSeries slices the page's
   CL from PM through ME, the drawer paints a line on a stub canvas,
   and every shipped recap page carries the canvas + the script. */
const fs = require('fs'), path = require('path'), vm = require('vm');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } };
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const src = fs.readFileSync(path.join(R, 'assets/js/recap-chart.js'), 'utf8');

function stubCtx() {
  const calls = [];
  return {
    calls,
    set fillStyle(v) {}, set strokeStyle(v) {}, set lineWidth(v) {}, set lineJoin(v) {}, set font(v) {},
    scale() { calls.push('scale'); }, clearRect() { calls.push('clearRect'); },
    beginPath() { calls.push('begin'); }, moveTo(x, y) { calls.push(['moveTo', Math.round(x), Math.round(y)]); },
    lineTo(x, y) { calls.push(['lineTo', Math.round(x), Math.round(y)]); },
    stroke() { calls.push('stroke'); }, fillText(t) { calls.push(['text', t]); },
    arc(x, y) { calls.push(['arc', Math.round(x), Math.round(y)]); }, fill() { calls.push('fill'); },
    measureText() { return { width: 30 }; }
  };
}
function runWith(CL, ME, PM, withCanvas) {
  const ctx = stubCtx();
  const canvas = withCanvas ? { clientWidth: 560, clientHeight: 260, getContext: () => ctx } : null;
  const sandbox = {
    console, Math, JSON, Object, isFinite, isNaN,
    window: { psC: (d) => d, devicePixelRatio: 1, addEventListener() {} },
    document: {
      readyState: 'complete',
      getElementById: (id) => (id === 'recapChart' ? canvas : null),
      addEventListener() {}
    },
    CL, ME, PM
  };
  sandbox.window.window = sandbox.window;
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox);
  return { RC: sandbox.RecapChart, ctx, sandbox };
}

const CL = {
  '2026-10-30': { BTC: 77198.21 }, '2026-11-02': { BTC: 76677.30 },
  '2026-11-03': { BTC: 77345.05 }, '2026-11-04': { BTC: 80405.29 },
  '2026-11-20': { BTC: 58814.99 }, '2026-12-01': { BTC: 60000 }
};
const { RC, ctx } = runWith(CL, '2026-11-20', '2026-10-30', true);
chk('RecapChart loads', !!RC);
chk('monthSeries slices PM..ME in order', eq(RC.monthSeries(CL, '2026-10-30', '2026-11-20').map((p) => p.d),
  ['2026-10-30', '2026-11-02', '2026-11-03', '2026-11-04', '2026-11-20']));
chk('monthSeries drops dates outside the range', RC.monthSeries(CL, '2026-11-02', '2026-11-04').length === 3);
chk('monthSeries skips a date with no BTC close', RC.monthSeries({ '2026-11-02': {}, '2026-11-03': { BTC: 1 } }, '2026-11-02', '2026-11-03').length === 1);
chk('monthSeries empty on PM>ME / no CL', RC.monthSeries(CL, '2026-11-20', '2026-10-30').length === 0 && RC.monthSeries(null, '2026-10-30', '2026-11-20').length === 0);
chk('fmtD shortens an ISO date', RC.fmtD('2026-11-20') === 'Nov 20' && RC.fmtD('2026-10-30') === 'Oct 30');
const ticks = RC.niceTicks(58814, 80405);
chk('niceTicks covers the range with round steps', ticks.length >= 3 && ticks[0] <= 58814 && ticks[ticks.length - 1] >= 80405, ticks);
chk('init drew a line on load', ctx.calls.some((c) => c[0] === 'lineTo') && ctx.calls.indexOf('stroke') !== -1, ctx.calls.length);
chk('init labelled first and last dates', ctx.calls.some((c) => c[0] === 'text' && c[1] === 'Oct 30') && ctx.calls.some((c) => c[0] === 'text' && c[1] === 'Nov 20'));

const noCanvas = runWith(CL, '2026-11-20', '2026-10-30', false);
chk('init is false with no canvas', noCanvas.RC.init() === false);
const noData = runWith({}, '2026-11-20', '2026-10-30', true);
chk('init is false with no series', noData.RC.init() === false);

/* Shipped pages: every recap month carries the canvas (inside the
   Bitcoin section) and loads recap-chart.js. */
const months = fs.readdirSync(path.join(R, 'recap')).filter((m) => /^\d{4}-\d\d$/.test(m)).sort();
chk('recap months found', months.length >= 11, months);
months.forEach((m) => {
  const s = fs.readFileSync(path.join(R, 'recap', m, 'index.html'), 'utf8');
  const btc = s.indexOf('<h2>Bitcoin in');
  const slv = s.indexOf('<h2>Sleeves vs spot BTC</h2>');
  const cv = s.indexOf('<canvas id="recapChart"');
  chk(m + ' canvas inside the Bitcoin section', btc !== -1 && slv !== -1 && cv > btc && cv < slv);
  chk(m + ' loads recap-chart.js', s.indexOf('assets/js/recap-chart.js?v=rcp1') !== -1);
});

console.log('recap chart checks', n, 'fail', f);
process.exit(f ? 1 : 0);
