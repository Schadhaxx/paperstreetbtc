/* Monthly recap chart (enhancements 5, 21 Nov 2026): a line of the
   month's BTC daily closes on each recap page, drawn from the page's
   own embedded CL (the same closes the sleeve cards use), PM -> ME.
   Native canvas only (no Chart.js); psC theming like the other native
   charts. The generator (tools/recap_gen.py) emits the canvas inside
   the Bitcoin section; completed months were backfilled the same way.
   CL/ME/PM are the page's top-level consts (global lexical scope, not
   window props), so they are read as bare identifiers with typeof
   guards — a page without them simply draws nothing. */
var RecapChart = (function () {
  var psC = (typeof window !== 'undefined' && typeof window.psC === 'function')
    ? window.psC : function (d) { return d; };
  var MN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function fmtD(iso) {
    var p = (iso || '').split('-');
    if (p.length !== 3) return iso;
    return MN[+p[1] - 1] + ' ' + (+p[2]);
  }
  /* The month's BTC closes, PM (previous month-end anchor) through ME,
     in date order. Dates missing from CL (e.g. a weekend close the
     history has not published yet) are skipped, never invented. */
  function monthSeries(CL, PM, ME) {
    if (!CL || typeof CL !== 'object' || !PM || !ME || PM > ME) return [];
    var out = [];
    Object.keys(CL).sort().forEach(function (d) {
      if (d < PM || d > ME) return;
      var row = CL[d], v = row && row.BTC;
      if (typeof v === 'number' && isFinite(v)) out.push({ d: d, v: v });
    });
    return out;
  }
  function niceNum(x) {
    var r = Math.round(x);
    if (Math.abs(x - r) < x / 1e3) x = r;
    var p = Math.pow(10, Math.floor(Math.log10(x)));
    var s = x / p;
    return (s <= 1 ? 1 : s <= 2 ? 2 : s <= 5 ? 5 : 10) * p;
  }
  function niceTicks(min, max) {
    if (!(max > min)) max = min + 1;
    var step = niceNum((max - min) / 4);
    var t0 = Math.floor(min / step) * step, t1 = Math.ceil(max / step) * step, out = [];
    for (var v = t0; v <= t1 + step * 0.01; v += step) out.push(Math.round(v * 1000) / 1000);
    return out;
  }
  function drawChart(cv, series) {
    if (!cv || !series || series.length < 2) return false;
    var ctx = cv.getContext && cv.getContext('2d');
    if (!ctx) return false;
    var dpr = (typeof window !== 'undefined' && window.devicePixelRatio) || 1;
    var cssW = cv.clientWidth || 560, cssH = cv.clientHeight || 260;
    cv.width = Math.round(cssW * dpr); cv.height = Math.round(cssH * dpr);
    ctx.scale(dpr, dpr); ctx.clearRect(0, 0, cssW, cssH);
    var vals = series.map(function (p) { return p.v; });
    var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals);
    var span = mx - mn || 1, lo = mn - span * 0.08, hi = mx + span * 0.08;
    var padL = 64, padR = 10, padT = 12, padB = 26;
    var plotW = cssW - padL - padR, plotH = cssH - padT - padB;
    var X = function (i) { return padL + (series.length === 1 ? plotW / 2 : i / (series.length - 1) * plotW); };
    var Y = function (v) { return padT + (hi - v) / (hi - lo) * plotH; };
    ctx.font = '11px -apple-system, system-ui, sans-serif';
    ctx.fillStyle = psC('#9aa6bc', '#475569');
    ctx.strokeStyle = psC('rgba(255,255,255,.08)', 'rgba(15,23,42,.10)');
    niceTicks(mn, mx).forEach(function (t) {
      var y = Y(t);
      ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(cssW - padR, y); ctx.stroke();
      ctx.fillText('$' + Math.round(t).toLocaleString('en-US'), 4, y + 4);
    });
    var line = psC('#22d3ee', '#0369a1');
    ctx.strokeStyle = line; ctx.lineWidth = 2; ctx.lineJoin = 'round'; ctx.beginPath();
    series.forEach(function (p, i) { if (i === 0) ctx.moveTo(X(i), Y(p.v)); else ctx.lineTo(X(i), Y(p.v)); });
    ctx.stroke();
    var last = series[series.length - 1];
    ctx.fillStyle = line; ctx.beginPath(); ctx.arc(X(series.length - 1), Y(last.v), 3, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = psC('#9aa6bc', '#475569');
    ctx.fillText(fmtD(series[0].d), padL, cssH - 8);
    var lastLbl = fmtD(last.d);
    ctx.fillText(lastLbl, cssW - padR - ctx.measureText(lastLbl).width, cssH - 8);
    return true;
  }
  function init() {
    if (typeof document === 'undefined') return false;
    var cv = document.getElementById('recapChart');
    if (!cv) return false;
    var cl = (typeof CL !== 'undefined') ? CL : null; /* page consts, global lexical scope */
    var me = (typeof ME !== 'undefined') ? ME : null;
    var pm = (typeof PM !== 'undefined') ? PM : null;
    var series = monthSeries(cl, pm, me);
    if (series.length < 2) return false;
    var ok = drawChart(cv, series);
    if (ok && typeof window !== 'undefined' && window.addEventListener) {
      var t = 0;
      window.addEventListener('resize', function () {
        clearTimeout(t);
        t = setTimeout(function () { drawChart(cv, series); }, 150);
      });
    }
    return ok;
  }
  return { monthSeries: monthSeries, niceTicks: niceTicks, fmtD: fmtD, drawChart: drawChart, init: init };
})();
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', RecapChart.init);
  else RecapChart.init();
}
