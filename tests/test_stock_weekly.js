#!/usr/bin/env node
/* Shipped stock-weekly JSON invariants (brief section 4.6). No network.
   Week bounds are UTC calendar dates. Pack numbers are compared, not copied. */
const fs = require('fs'), path = require('path');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } else console.log('PASS', name); };
const pack = JSON.parse(fs.readFileSync(path.join(R, 'assets/data/screener-pack.json'), 'utf8'));
const rows = {};
pack.rows.forEach((r) => { rows[r.symbol] = r; });
const SYMS = ['TSLA', 'PLTR', 'MSTR', 'IBIT', 'MU', 'META', 'SPCX'];
const YTD = SYMS.filter((s) => s !== 'SPCX');
const HOLIDAYS = new Set(['2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07', '2026-11-26', '2026-12-25']);
const NAMED = { '2026-01-19': 4, '2026-02-16': 4, '2026-03-30': 4, '2026-05-25': 4, '2026-06-15': 4, '2026-06-29': 4, '2026-09-07': 4 };
function utc(iso) { return new Date(iso + 'T00:00:00Z'); }
function iso(d) { return d.toISOString().slice(0, 10); }
function addDays(isoStr, n) { return iso(new Date(utc(isoStr).getTime() + n * 86400000)); }
function isSession(isoStr) {
  const day = utc(isoStr).getUTCDay();
  return day !== 0 && day !== 6 && !HOLIDAYS.has(isoStr);
}
function expectedDays(mon, asof, firstSession) {
  const sun = addDays(mon, 6);
  const last = sun < asof ? sun : asof;
  const start = firstSession > mon ? firstSession : mon;
  let c = 0;
  for (let d = start; d <= last; d = addDays(d, 1)) if (isSession(d)) c++;
  return c;
}
SYMS.forEach((sym) => {
  const p = path.join(R, 'assets/data', 'stock-weekly-' + sym + '.json');
  const doc = JSON.parse(fs.readFileSync(p, 'utf8'));
  const row = rows[sym];
  chk(sym + ' unit usd', doc.unit === 'usd');
  chk(sym + ' weeks present', Array.isArray(doc.weeks) && doc.weeks.length > 1, doc.weeks && doc.weeks.length);
  const weeks = doc.weeks;
  let prev = null;
  weeks.forEach((w, i) => {
    const mon = utc(w.monday);
    chk(sym + ' ' + w.monday + ' is Monday', mon.getUTCDay() === 1);
    chk(sym + ' ' + w.monday + ' sunday is +6', w.sunday === addDays(w.monday, 6) && utc(w.sunday).getUTCDay() === 0);
    if (prev) chk(sym + ' ' + w.monday + ' contiguous', w.monday === addDays(prev, 7) && w.monday > prev, [prev, w.monday]);
    prev = w.monday;
    ['open', 'high', 'low', 'close'].forEach((k) => {
      chk(sym + ' ' + w.monday + ' ' + k + ' finite', typeof w[k] === 'number' && isFinite(w[k]));
    });
    chk(sym + ' ' + w.monday + ' high/low vs open/close', w.high >= Math.max(w.open, w.close) && w.low <= Math.min(w.open, w.close) && w.low <= w.high, w);
    chk(sym + ' ' + w.monday + ' days', Number.isInteger(w.days) && w.days >= 1 && w.days <= 5, w.days);
  });
  chk(sym + ' baseClose within 0.01 of pack', Math.abs(doc.baseClose - row.baseClose) <= 0.01, [doc.baseClose, row.baseClose]);
  const last = weeks[weeks.length - 1].close;
  if (doc.asOf === pack.asOf) {
    chk(sym + ' last close equals pack price (shared asOf)', Math.abs(last - row.price) <= 0.01, [last, row.price]);
  } else {
    console.log('NOTE', sym, 'chart close', last, 'as of', doc.asOf, 'vs pack price', row.price, 'as of', pack.asOf, '(dates differ)');
    chk(sym + ' asOf differs from pack so price is not forced equal', doc.asOf !== pack.asOf);
  }
  const firstSession = sym === 'SPCX' ? '2026-06-12' : '2026-01-02';
  weeks.slice(1).forEach((w) => {
    const exp = expectedDays(w.monday, doc.asOf, firstSession);
    chk(sym + ' ' + w.monday + ' session count ' + exp, w.days === exp, w.days);
  });
  Object.keys(NAMED).forEach((mon) => {
    const w = weeks.find((x) => x.monday === mon);
    if (!w) return;
    chk(sym + ' holiday week ' + mon + ' has ' + NAMED[mon] + ' days', w.days === NAMED[mon], w.days);
  });
});
YTD.forEach((sym) => {
  const doc = JSON.parse(fs.readFileSync(path.join(R, 'assets/data', 'stock-weekly-' + sym + '.json'), 'utf8'));
  const w0 = doc.weeks[0];
  chk(sym + ' basis ytd', doc.basis === 'ytd' && doc.baseSession === '2025-12-31' && doc.baseLabel === '31 Dec close');
  chk(sym + ' first week partial 29 Dec x1', w0.monday === '2025-12-29' && w0.days === 1 && w0.sunday === '2026-01-04');
  chk(sym + ' 31 Dec close is not the first candle close', w0.close !== doc.baseClose, [w0.close, doc.baseClose]);
});
const sp = JSON.parse(fs.readFileSync(path.join(R, 'assets/data/stock-weekly-SPCX.json'), 'utf8'));
chk('SPCX basis listing', sp.basis === 'listing' && sp.baseLabel === 'Listing close' && sp.baseSession === '2026-06-12');
chk('SPCX starts week of 8 Jun, one day, x-axis has no earlier week', sp.weeks[0].monday === '2026-06-08' && sp.weeks[0].days === 1 && sp.weeks.every((w) => w.monday >= '2026-06-08'));
chk('SPCX first candle close is the listing close', Math.abs(sp.weeks[0].close - 160.95) <= 0.01 && Math.abs(sp.baseClose - rows.SPCX.baseClose) <= 0.01);
chk('SPCX first-trade open is kept and is not the listing close', typeof sp.weeks[0].open === 'number' && Math.abs(sp.weeks[0].open - sp.baseClose) > 0.01, sp.weeks[0]);
console.log('NOTE SPCX first-trade open', sp.weeks[0].open, 'listing close', sp.baseClose);
chk('no inProgress on a finished Friday close', SYMS.every((sym) => {
  const doc = JSON.parse(fs.readFileSync(path.join(R, 'assets/data', 'stock-weekly-' + sym + '.json'), 'utf8'));
  const asof = utc(doc.asOf);
  return asof.getUTCDay() === 5 && doc.inProgress === null && doc.lastSession === doc.asOf;
}));
console.log('STOCK_WEEKLY_JS', n, 'FAIL', f);
process.exit(f ? 1 : 0);
