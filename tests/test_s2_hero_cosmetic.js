#!/usr/bin/env node
/* YTD hero cosmetic fixes (15 Nov 2026, nice-to-haves): legend wrap +
   light-mode grid + tooltip no-clip. Executes the real drawNativeYTD from
   s2.js in a vm sandbox with a stubbed DOM and a recording 2d context (no
   browser needed), so a regression in the source fails here.
   - At 390px (canvas 314px, the real hero-card width) the long
     backup-source label wraps: every legend line is <= canvas width, and
     it takes 2+ rows. Wording is unchanged.
   - Light mode: the grid is the soft rgba(15,23,42,.08), never the dark
     #1e293b; ticks are #475569, never #9aa6bc.
   - Dark mode is unchanged: grid #1e293b, ticks #9aa6bc.
   - Hover tooltip: the box fits the canvas (x + w <= canvas width) and no
     tooltip text extends past the canvas right edge — the long label wraps
     inside the box instead of clipping.
   - document.fonts.ready hook is registered and fires a redraw once.
   - Pin is p11 (Batch A fix 4 bumped s2.js from p9; hero branch p10 must re-bump on rebase).
*/
const fs = require('fs'), path = require('path'), vm = require('vm');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } else console.log('PASS', name); };

const src = fs.readFileSync(path.join(R, 'assets/js/s2.js'), 'utf8');
const indexHtml = fs.readFileSync(path.join(R, 'index.html'), 'utf8');

/* ---- recording 2d context: ~0.52em average glyph width for Inter ---- */
function makeCtx(){
  const calls = { strokes: [], fills: [], texts: [] };
  let _font = '12px Inter, sans-serif', _fill = '#000', _stroke = '#000', _align = 'left', _baseline = 'alphabetic';
  const ctx = {
    get font(){ return _font; }, set font(v){ _font = v; },
    get fillStyle(){ return _fill; }, set fillStyle(v){ _fill = v; calls.fills.push(v); },
    get strokeStyle(){ return _stroke; }, set strokeStyle(v){ _stroke = v; calls.strokes.push(v); },
    get textAlign(){ return _align; }, set textAlign(v){ _align = v; },
    get textBaseline(){ return _baseline; }, set textBaseline(v){ _baseline = v; },
    lineWidth: 1, lineJoin: 'miter', lineCap: 'butt',
    setTransform(){}, clearRect(){}, save(){}, restore(){},
    beginPath(){}, moveTo(){}, lineTo(){}, arcTo(){}, arc(){}, bezierCurveTo(){}, closePath(){},
    fill(){}, stroke(){}, setLineDash(){}, fillRect(){},
    measureText(t){
      const m = /(\d+(?:\.\d+)?)px/.exec(_font);
      const size = m ? +m[1] : 12;
      return { width: String(t).length * size * 0.52 };
    },
    fillText(t, x, y){
      const w = this.measureText(t).width;
      let right = x + w;
      if (_align === 'right') right = x;
      else if (_align === 'center') right = x + w / 2;
      calls.texts.push({ text: String(t), x: x, right: right, align: _align, fill: _fill });
    }
  };
  return { ctx, calls };
}

function makeCanvas(w, h){
  const rec = makeCtx();
  const cv = {
    clientWidth: w, clientHeight: h,
    width: 0, height: 0,
    style: {},
    getContext: function(){ return rec.ctx; },
    addEventListener: function(){},
    getBoundingClientRect: function(){ return { left: 0, top: 0, width: w, height: h }; }
  };
  return { cv, rec };
}

const elStub = () => ({ textContent: '', className: '',
  classList: { toggle: function(){}, add: function(){}, remove: function(){} },
  dataset: {}, style: {}, addEventListener: function(){} });

let theme = 'dark';
let current = makeCanvas(314, 320);
let fontsCb = null;
const sandbox = {
  console: console,
  devicePixelRatio: 1,
  addEventListener: function(){},
  document: {
    documentElement: { getAttribute: function(a){ return a === 'data-theme' ? theme : null; },
      classList: { add: function(){}, remove: function(){} } },
    getElementById: function(id){ return id === 'ytdChart' ? current.cv : elStub(); },
    querySelectorAll: function(){ return []; },
    addEventListener: function(){},
    fonts: { ready: { then: function(cb){ fontsCb = cb; return { catch: function(){} }; } } }
  }
};
sandbox.window = sandbox;
const ctx = vm.createContext(sandbox);
vm.runInContext(src, ctx);

/* ---- fonts.ready hook ---- */
chk('fonts.ready hook registered', typeof fontsCb === 'function');
chk('s2.js contains the document.fonts.ready redraw', /document\.fonts\.ready\.then/.test(src));
if (typeof fontsCb === 'function'){
  fontsCb();
  chk('fonts.ready callback marks the redraw', sandbox.__S2_FONTS_REDRAW === true);
}

/* ---- fixture data: one sleeve + the long backup-source benchmark label ---- */
const LBLS = ['1 Jan','30 Jan','27 Feb','31 Mar','30 Apr','29 May','30 Jun','31 Jul','31 Aug','30 Sep','30 Oct','30 Nov','11 Dec'];
const LONG = "Spot BTC (close from backup source until Yahoo's final bar)";
sandbox.__T_LBLS = LBLS;
sandbox.__T_DS = [
  { label: 'Berkshire Killer', data: LBLS.map((_, i) => 100 + 1.5 * i),
    borderColor: '#22d3ee', backgroundColor: '#22d3ee18', borderWidth: 2.5, tension: 0.3, fill: true, pointRadius: 3, pointHoverRadius: 5 },
  { label: LONG, data: LBLS.map((_, i) => 100 + 2 * i),
    borderColor: '#64748b', borderWidth: 1.5, borderDash: [5, 4], tension: 0.25, fill: false, pointRadius: 0 }
];
const draw = () => vm.runInContext('drawNativeYTD(__T_LBLS, __T_DS)', ctx);

/* ---- light mode, 390px canvas (314px) ---- */
theme = 'light';
current = makeCanvas(314, 320);
chk('light draw succeeds', draw() === true);
const light = current.rec.calls;
chk('light: grid is the soft rgba(15,23,42,.08)', light.strokes.indexOf('rgba(15,23,42,.08)') >= 0);
chk('light: dark grid #1e293b never drawn', light.strokes.indexOf('#1e293b') === -1);
chk('light: ticks are #475569', light.fills.indexOf('#475569') >= 0);
chk('light: dark tick #9aa6bc never drawn (no hover)', light.fills.indexOf('#9aa6bc') === -1);
const leg = sandbox.__S2_NATIVE_LEGEND;
chk('legend info recorded', !!leg, leg);
chk('legend max line fits the 314px canvas', leg && leg.maxLineW <= leg.canvasW, leg);
chk('legend canvas width is 314', leg && leg.canvasW === 314, leg);
chk('long label wraps to 2+ legend rows', leg && leg.rows >= 2, leg);
chk('tooltip hook is null with no hover', sandbox.__S2_NATIVE_TOOLTIP == null);

/* ---- light-mode hover: tooltip must not clip ---- */
vm.runInContext('s2Hover = 5; drawNativeYTD(__T_LBLS, __T_DS);', ctx);
const tip = sandbox.__S2_NATIVE_TOOLTIP;
chk('tooltip hook recorded on hover', !!tip, tip);
chk('tooltip box fits the canvas (x + w <= 314)', tip && tip.x >= 0 && tip.x + tip.w <= 314, tip);
const tipTexts = current.rec.calls.texts.filter(t => t.fill === '#9aa6bc' || t.fill === '#e8eef7');
chk('tooltip texts present in light-mode hover', tipTexts.length >= 3, tipTexts.length);
chk('no tooltip text extends past the canvas right edge',
  tipTexts.every(t => t.right <= 314.5), tipTexts.filter(t => t.right > 314.5));
chk('tooltip label wording intact (a wrapped line ends with "final bar)")',
  tipTexts.some(t => /final bar\)$/.test(t.text)), tipTexts.map(t => t.text));

/* ---- dark mode is unchanged ---- */
theme = 'dark';
current = makeCanvas(314, 320);
chk('dark draw succeeds', draw() === true);
const dark = current.rec.calls;
chk('dark: grid is #1e293b (unchanged)', dark.strokes.indexOf('#1e293b') >= 0);
chk('dark: light grid rgba never drawn', dark.strokes.indexOf('rgba(15,23,42,.08)') === -1);
chk('dark: ticks are #9aa6bc (unchanged)', dark.fills.indexOf('#9aa6bc') >= 0);
chk('dark: light tick #475569 never drawn', dark.fills.indexOf('#475569') === -1);

/* ---- pin is p11 (Batch A fix 4 bumped it from p9) ---- */
chk('index.html pins s2.js at p11', /s2\.js\?v=p11/.test(indexHtml));
chk('no stale p9 pin for s2.js', !/s2\.js\?v=p9/.test(indexHtml));

console.log('S2 HERO COSMETIC TESTS', n, 'FAIL', f);
process.exit(f ? 1 : 0);
