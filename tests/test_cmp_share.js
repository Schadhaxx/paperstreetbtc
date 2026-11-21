#!/usr/bin/env node
/* Shareable calculator links (enhancements 4): PsShare encode/decode
   round-trips, defaults collapse to no hash, invalid fields fall back
   instead of breaking the link. Pure block evalled out of compare.js,
   same pattern as CmpMath in test_cmp.js. */
const fs = require('fs'), path = require('path');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } };
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const src = fs.readFileSync(path.join(R, 'assets/js/compare.js'), 'utf8');
const start = src.indexOf('var PsShare = (function () {');
const end = src.indexOf('})();', start);
if (start < 0 || end < 0) { console.log('FAIL PsShare block missing'); process.exit(1); }
const PsShare = eval(src.slice(start + 'var PsShare = '.length, end + 5));
const { validDate, validAmount, decodeHash, encodeSetup } = PsShare;
const SLEEVES = ['berkshire', 'hodlr', 'hf', 'saylor'];
const DEFS = { s: 'berkshire', d: '2026-01-01', a: 10000, v: 'SPOT' };

chk('validDate accepts a 2026 date', validDate('2026-03-02') === true);
chk('validDate rejects bad format', validDate('03/02/2026') === false);
chk('validDate rejects a pre-2026 date', validDate('2025-12-31') === false);
chk('validDate rejects garbage', validDate('not-a-date') === false && validDate('') === false && validDate(null) === false);
chk('validAmount accepts positive', validAmount(100) === true && validAmount(10000.5) === true);
chk('validAmount rejects zero/negative/NaN', validAmount(0) === false && validAmount(-5) === false && validAmount(NaN) === false && validAmount(Infinity) === false);

chk('decode empty hash is null', decodeHash('', SLEEVES) === null && decodeHash(null, SLEEVES) === null);
const full = decodeHash('s=hodlr&d=2026-03-02&a=25000&v=IBIT&x=1000@2026-04-01,500@2026-06-01', SLEEVES);
chk('decode full hash', eq(full, { s: 'hodlr', d: '2026-03-02', a: 25000, v: 'IBIT', x: [{ amt: 1000, dt: '2026-04-01' }, { amt: 500, dt: '2026-06-01' }] }), full);
chk('decode all-invalid params is null', decodeHash('s=bogus&d=2025-01-01&a=-5&v=XXX', SLEEVES) === null);
chk('decode drops bad contributions, keeps good ones', eq(decodeHash('x=0@2026-04-01,1000@2025-01-01,250@2026-05-01', SLEEVES), { s: null, d: null, a: null, v: null, x: [{ amt: 250, dt: '2026-05-01' }] }));
chk('decode garbage hash is null', decodeHash('s=???&d=!!', SLEEVES) === null);
chk('decode partial hash', eq(decodeHash('s=saylor&a=5000', SLEEVES), { s: 'saylor', d: null, a: 5000, v: null, x: [] }));

chk('encode defaults is empty', encodeSetup({ s: 'berkshire', d: '2026-01-01', a: 10000, v: 'SPOT', x: [] }, SLEEVES, DEFS) === '');
chk('encode defaults with nulls is empty', encodeSetup({ s: null, d: null, a: null, v: null, x: null }, SLEEVES, DEFS) === '');
chk('encode sleeve only', encodeSetup({ s: 'hodlr', d: null, a: null, v: null, x: [] }, SLEEVES, DEFS) === 's=hodlr&d=2026-01-01&a=10000&v=SPOT');
chk('encode full setup', encodeSetup({ s: 'hodlr', d: '2026-03-02', a: 25000, v: 'IBIT', x: [{ amt: 1000, dt: '2026-04-01' }, { amt: 500, dt: '2026-06-01' }] }, SLEEVES, DEFS) === 's=hodlr&d=2026-03-02&a=25000&v=IBIT&x=1000@2026-04-01,500@2026-06-01');
chk('encode falls back on invalid fields', encodeSetup({ s: 'bogus', d: '2025-01-01', a: -5, v: 'XXX', x: [{ amt: 0, dt: '2026-04-01' }] }, SLEEVES, DEFS) === '');

const setup = { s: 'hf', d: '2026-02-10', a: 42000, v: 'FBTC', x: [{ amt: 1200, dt: '2026-03-03' }] };
chk('round-trip decode(encode(x)) is x', eq(decodeHash(encodeSetup(setup, SLEEVES, DEFS), SLEEVES), setup), decodeHash(encodeSetup(setup, SLEEVES, DEFS), SLEEVES));
chk('round-trip defaults stays empty', decodeHash(encodeSetup(DEFS, SLEEVES, DEFS), SLEEVES) === null);

chk('page has the copy button', fs.readFileSync(path.join(R, 'compare/index.html'), 'utf8').indexOf('id="pvCopyLink"') !== -1);
chk('compare.js wires shareSync into calc', src.indexOf('shareSync();}') !== -1 || src.indexOf('shareSync();') !== -1);
chk('compare.js applies the hash before the first calc', src.indexOf('shareApply();calc();') !== -1);

console.log('cmp share checks', n, 'fail', f);
process.exit(f ? 1 : 0);
