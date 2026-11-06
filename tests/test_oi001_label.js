#!/usr/bin/env node
/* OI-001 frontend label rule: keyed on history.json fallback_sources (btc_daily.py:74 pattern).
   Fixtures A/B/C from OPEN_ITEMS; hostile inputs per REVIEW_CHECKLIST (cheap). */
const fs = require('fs'), path = require('path');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } else console.log('PASS', name); };

const BACKUP_LBL = "Spot BTC (close from backup source until Yahoo's final bar)";

/* Same rule as s2.js isBtcFb + fbDates / compare.js isBtcFb + fbDate */
function isBtcFb(fs, d) {
  const base = String((fs && fs[d] && fs[d].BTC) || 'yahoo').split('-')[0];
  return base !== 'yahoo' && base !== 'ffill';
}
function backupDate(fallback_sources) {
  const fs = fallback_sources || {};
  const dates = Object.keys(fs).filter(d => isBtcFb(fs, d)).sort();
  return dates.length ? dates[dates.length - 1] : null;
}
function spotLabel(fallback_sources) {
  return backupDate(fallback_sources) ? BACKUP_LBL : 'Spot BTC';
}
function noteFor(fallback_sources) {
  const d = backupDate(fallback_sources);
  return d ? ('BTC close ' + d + ' from backup source until Yahoo\'s final bar') : null;
}

/* A: Coinbase/fallback day shows backup-source label */
const A = { '2026-10-23': { BTC: 'coinbase' } };
chk('A Coinbase day -> backup label', spotLabel(A) === BACKUP_LBL, spotLabel(A));
chk('A note names 2026-10-23', noteFor(A) === 'BTC close 2026-10-23 from backup source until Yahoo\'s final bar', noteFor(A));

/* B: Yahoo-final day with no fallback entry shows none */
chk('B missing fallback_sources -> no label', spotLabel(undefined) === 'Spot BTC');
chk('B empty fallback_sources -> no label', spotLabel({}) === 'Spot BTC');
chk('B yahoo entry -> no label', spotLabel({ '2026-10-23': { BTC: 'yahoo' } }) === 'Spot BTC');
chk('B yahoo-unchecked -> no label (base=yahoo)', spotLabel({ '2026-10-23': { BTC: 'yahoo-unchecked' } }) === 'Spot BTC');
chk('B ffill -> no label', spotLabel({ '2026-10-23': { BTC: 'ffill' } }) === 'Spot BTC');
chk('B stock-only fallback (no BTC) -> no label', spotLabel({ '2026-10-23': { MSTR: 'yahoo-meta' } }) === 'Spot BTC');

/* C: after Yahoo replacement + reload, label clears */
let live = { '2026-10-23': { BTC: 'coinbase' } };
chk('C before heal -> backup label', spotLabel(live) === BACKUP_LBL);
live = {}; /* Yahoo replaced: entry removed from fallback_sources */
chk('C after Yahoo replacement reload -> cleared', spotLabel(live) === 'Spot BTC' && noteFor(live) === null);

/* Hostile / edge (REVIEW_CHECKLIST cheap) */
chk('null BTC src treated as yahoo', spotLabel({ '2026-10-23': { BTC: null } }) === 'Spot BTC');
chk('empty string BTC src falsy -> treated as yahoo (no label)', spotLabel({ '2026-10-23': { BTC: '' } }) === 'Spot BTC');
chk('finnhub backup -> label', spotLabel({ '2026-10-23': { BTC: 'finnhub' } }) === BACKUP_LBL);
chk('coingecko-unchecked -> label (base=coingecko)', spotLabel({ '2026-10-23': { BTC: 'coingecko-unchecked' } }) === BACKUP_LBL);
chk('per-date: older coinbase + newer yahoo -> names older date', (() => {
  const fs = { '2026-10-22': { BTC: 'coinbase' }, '2026-10-23': { BTC: 'yahoo' } };
  return backupDate(fs) === '2026-10-22' && spotLabel(fs) === BACKUP_LBL;
})());
chk('compare fetch-failure default empty -> no false backup', spotLabel({}) === 'Spot BTC');

/* Production source contracts (s2.js + compare.js) */
const s2 = fs.readFileSync(path.join(R, 'assets/js/s2.js'), 'utf8');
const cmp = fs.readFileSync(path.join(R, 'assets/js/compare.js'), 'utf8');
chk('s2.js uses fallback_sources', /fallback_sources/.test(s2));
chk('s2.js has BACKUP_LBL wording', /close from backup source until Yahoo\\?'s final bar/.test(s2));
chk('s2.js drops time-window-only BTCPROV assignment', !/BTCPROV = \(B\.H\.btc_provisional \|\| \[\]\)\.indexOf\(B\.last\) >= 0 && Date\.now\(\)/.test(s2));
chk('s2.js isBtcFb excludes yahoo and ffill', /base !== 'yahoo' && base !== 'ffill'/.test(s2));
chk('compare.js loads BFB from fallback_sources', /BFB\s*=\s*h\.fallback_sources\s*\|\|\s*\{\}/.test(cmp));
chk('compare.js fetch failure clears BFB', /\.catch\(e\s*=>\s*\{\s*BFB\s*=\s*\{\}/.test(cmp));
chk('compare.js BACKUP_LBL wording', /close from backup source until Yahoo\\?'s final bar/.test(cmp));
chk('compare.js note names backup date', /BTC close '\+fd\+' from backup source/.test(cmp));
chk('no price/NAV mutation in s2 OI-001 block', !/closes\[|nav\(|VAL\[/.test(s2.slice(s2.indexOf('OI-001'), s2.indexOf('OI-001') + 500)));


/* Scope fix: BPROV/BFB must be declared in init() before function run (shared with fetch) */
chk('compare.js declares BPROV/BFB before function run', (() => {
  const iDecl = cmp.indexOf('let BPROV=[],BFB={}');
  const iRun = cmp.indexOf('function run(){');
  return iDecl >= 0 && iRun > iDecl;
})());
chk('compare.js has exactly one BPROV/BFB declaration', (cmp.match(/let BPROV=\[\],BFB=\{\}/g) || []).length === 1);
chk('compare.js helpers before function run', (() => {
  const iRun = cmp.indexOf('function run(){');
  return cmp.indexOf('const isBtcFb=') < iRun && cmp.indexOf('const fbDate=') < iRun && cmp.indexOf('const BACKUP_LBL=') < iRun && cmp.indexOf('const prov=') < iRun;
})());

/* Cache-busters bumped with this revision */
const idx = fs.readFileSync(path.join(R, 'index.html'), 'utf8');
const cmpHtml = fs.readFileSync(path.join(R, 'compare/index.html'), 'utf8');
const customHtml = fs.readFileSync(path.join(R, 'custom/index.html'), 'utf8');
chk('index.html s2.js cache-buster >= p4', /s2\.js\?v=p4/.test(idx));
chk('compare/index.html compare.js cache-buster >= et2', /compare\.js\?v=et2/.test(cmpHtml));
chk('custom/index.html compare.js cache-buster >= et2', /compare\.js\?v=et2/.test(customHtml));

console.log('OI-001 LABEL TESTS', n, 'FAIL', f);
process.exit(f ? 1 : 0);
