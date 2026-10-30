// Gold YTD weekly candle chart — Maple Leaf Screener (30 Oct 2026).
// Opens when the GOLD Market Indicator tile itself is tapped/clicked.
// The tile's "+" button keeps its existing job (the note pill) and does
// NOT open this chart: clicks on .note-btn are ignored here.
// Data: Yahoo GC=F (COMEX gold futures, the same series the site
// pipeline uses for the GOLD indicator), fetched live in the visitor's
// browser — no key, no pipeline change, no static snapshot shipped, so
// nothing here can ever be mistaken for a live quote when it is not.
// If the live fetch fails, the modal says so plainly with a Retry
// button; it never invents candles and never labels a failure as live.
// A future static file assets/data/gold-weekly.json, if one ever
// appears, is tried as a fallback only (same weekly shape, dated).
// Weekly candles: UTC Monday-Sunday weeks, like the BTC candle ranges;
// week labels are UTC. YTD only in this first version (1 Jan 2026 to
// the latest week). Candle colours match the site: green #22c55e,
// red #ef4444. Tap a candle for its week + OHLC in a pill.
(function () {
  var YTD_START = 1767225600; // 2026-01-01 00:00 UTC
  var YAHOO_URL = 'https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?period1=' + YTD_START + '&interval=1d';
  var STATIC_URL = 'assets/data/gold-weekly.json?v=1';
  var state = { weeks: [], dataLabel: '', loading: false, selected: -1 };

  function fmtMoney(v) {
    return '$' + v.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }
  function fmtDateUTC(d) {
    var MN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return d.getUTCDate() + ' ' + MN[d.getUTCMonth()] + ' ' + d.getUTCFullYear();
  }
  // Aggregate Yahoo daily OHLC (arrays aligned with timestamps) into
  // UTC Monday-Sunday weekly candles. Days with a null close are
  // skipped, never treated as zero. A week with no usable days is
  // dropped, never drawn as a flat candle.
  function aggregateWeekly(timestamps, quote) {
    var weeks = [];
    var byMonday = {};
    var order = [];
    for (var i = 0; i < timestamps.length; i++) {
      var c = quote.close ? quote.close[i] : null;
      var o = quote.open ? quote.open[i] : null;
      var h = quote.high ? quote.high[i] : null;
      var l = quote.low ? quote.low[i] : null;
      if (c === null || c === undefined || o === null || o === undefined) continue;
      var d = new Date(timestamps[i] * 1000);
      if (d.getTime() < YTD_START * 1000) continue;
      var dow = (d.getUTCDay() + 6) % 7; // Monday = 0
      var mon = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() - dow));
      var key = mon.getTime();
      if (!byMonday[key]) {
        byMonday[key] = { monday: mon, days: [] };
        order.push(key);
      }
      byMonday[key].days.push({ date: d, open: o, high: h, low: l, close: c });
    }
    order.sort(function (a, b) { return a - b; });
    order.forEach(function (key) {
      var w = byMonday[key];
      w.days.sort(function (a, b) { return a.date - b.date; });
      var first = w.days[0], last = w.days[w.days.length - 1];
      var high = -Infinity, low = Infinity;
      w.days.forEach(function (day) {
        if (day.high !== null && day.high !== undefined) high = Math.max(high, day.high);
        if (day.low !== null && day.low !== undefined) low = Math.min(low, day.low);
      });
      if (high === -Infinity) high = Math.max(first.open, last.close);
      if (low === Infinity) low = Math.min(first.open, last.close);
      var sun = new Date(w.monday.getTime() + 6 * 86400000);
      weeks.push({
        monday: w.monday, sunday: sun,
        label: fmtDateUTC(w.monday) + ' – ' + fmtDateUTC(sun),
        days: w.days.length,
        open: first.open, high: high, low: low, close: last.close
      });
    });
    return weeks;
  }

  function el(id) { return document.getElementById(id); }

  function openModal() {
    var m = el('gold-modal');
    if (!m) return;
    m.classList.add('open');
    m.setAttribute('aria-hidden', 'false');
    if (!state.weeks.length && !state.loading) loadData();
    else if (state.weeks.length) draw();
  }
  function closeModal() {
    var m = el('gold-modal');
    if (!m) return;
    m.classList.remove('open');
    m.setAttribute('aria-hidden', 'true');
  }

  function setStatus(text, isError) {
    var s = el('gold-status');
    if (s) { s.textContent = text; s.style.color = isError ? '#ef4444' : '#94a3b8'; }
  }

  function loadData() {
    state.loading = true;
    setStatus('Loading gold weekly candles…');
    fetch(YAHOO_URL)
      .then(function (res) { if (!res.ok) throw new Error('HTTP ' + res.status); return res.json(); })
      .then(function (data) {
        var result = data && data.chart && data.chart.result && data.chart.result[0];
        if (!result || !result.timestamp || !result.indicators || !result.indicators.quote) throw new Error('No Yahoo data');
        state.weeks = aggregateWeekly(result.timestamp, result.indicators.quote[0]);
        if (!state.weeks.length) throw new Error('No usable weeks');
        var last = state.weeks[state.weeks.length - 1];
        state.dataLabel = 'Source: Yahoo GC=F (COMEX futures), fetched ' + fmtDateUTC(new Date()) + ' · latest week ends ' + fmtDateUTC(last.sunday) + ' · ' + state.weeks.length + ' weekly candles, YTD';
        state.loading = false;
        setStatus(state.dataLabel, false);
        draw();
      })
      .catch(function () {
        // Fallback only: a dated static file, if one ever exists.
        fetch(STATIC_URL)
          .then(function (res) { if (!res.ok) throw new Error('no static file'); return res.json(); })
          .then(function (data) {
            if (!data || !data.weeks || !data.weeks.length) throw new Error('no static weeks');
            state.weeks = data.weeks.map(function (w) {
              return { monday: new Date(w.monday), sunday: new Date(w.sunday), label: w.label, days: w.days, open: w.open, high: w.high, low: w.low, close: w.close };
            });
            state.dataLabel = 'Source: dated snapshot ' + (data.asOf || '') + ' — not a live quote.';
            state.loading = false;
            setStatus(state.dataLabel, false);
            draw();
          })
          .catch(function () {
            state.loading = false;
            setStatus('Gold weekly candles could not be loaded. Check your connection and tap Retry — no chart is shown until real data arrives.', true);
            var r = el('gold-retry');
            if (r) r.style.display = 'inline-block';
          });
      });
  }

  function draw() {
    var canvas = el('gold-canvas');
    if (!canvas || !state.weeks.length) return;
    var dpr = window.devicePixelRatio || 1;
    var cssW = canvas.clientWidth || 320;
    var cssH = 280;
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    canvas.style.height = cssH + 'px';
    var ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, cssW, cssH);
    var padL = 62, padR = 8, padT = 10, padB = 30;
    var plotW = cssW - padL - padR, plotH = cssH - padT - padB;
    var lo = Infinity, hi = -Infinity;
    state.weeks.forEach(function (w) { lo = Math.min(lo, w.low); hi = Math.max(hi, w.high); });
    var span = hi - lo || 1;
    lo -= span * 0.05; hi += span * 0.05;
    function y(v) { return padT + (hi - v) / (hi - lo) * plotH; }
    // Gridlines + price labels.
    ctx.font = '11px -apple-system, system-ui, sans-serif';
    ctx.fillStyle = '#94a3b8';
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    for (var g = 0; g <= 4; g++) {
      var v = lo + (hi - lo) * g / 4;
      var yy = y(v);
      ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(cssW - padR, yy); ctx.stroke();
      ctx.fillText(fmtMoney(v), 4, yy + 4);
    }
    var n = state.weeks.length;
    var slot = plotW / n;
    var bw = Math.max(2, Math.min(14, slot * 0.6));
    state.weeks.forEach(function (w, i) {
      var cx = padL + slot * i + slot / 2;
      var up = w.close >= w.open;
      var col = up ? '#22c55e' : '#ef4444';
      ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(cx, y(w.high)); ctx.lineTo(cx, y(w.low)); ctx.stroke();
      var top = y(Math.max(w.open, w.close)), bot = y(Math.min(w.open, w.close));
      ctx.fillRect(cx - bw / 2, top, bw, Math.max(1, bot - top));
      if (i === state.selected) {
        ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 1.5;
        ctx.strokeRect(cx - bw / 2 - 3, y(w.high) - 3, bw + 6, y(w.low) - y(w.high) + 6);
      }
      // Week labels: every 4th week, plus the last, by Monday date.
      if (i % 4 === 0 || i === n - 1) {
        ctx.fillStyle = '#94a3b8';
        var lab = w.monday.getUTCDate() + ' ' + ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][w.monday.getUTCMonth()];
        ctx.fillText(lab, Math.max(padL, Math.min(cx - 12, cssW - padR - 30)), cssH - 10);
      }
    });
    canvas._plot = { padL: padL, slot: slot, n: n };
  }

  function onCanvasTap(e) {
    var canvas = el('gold-canvas');
    if (!canvas || !canvas._plot) return;
    var rect = canvas.getBoundingClientRect();
    var x = (e.clientX - rect.left) - canvas._plot.padL;
    var idx = Math.floor(x / canvas._plot.slot);
    if (idx < 0 || idx >= state.weeks.length) return;
    state.selected = idx;
    var w = state.weeks[idx];
    var chg = (w.close / w.open - 1) * 100;
    var pill = el('gold-pill');
    if (pill) {
      pill.style.display = 'block';
      pill.innerHTML = '<b>Week ' + w.label + ' (UTC, ' + w.days + ' trading day' + (w.days === 1 ? '' : 's') + ')</b><br>'
        + 'Open ' + fmtMoney(w.open) + ' · High ' + fmtMoney(w.high) + ' · Low ' + fmtMoney(w.low) + ' · Close ' + fmtMoney(w.close)
        + '<br>Week change ' + (chg >= 0 ? '+' : '') + chg.toFixed(2) + '%';
    }
    draw();
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('.note-btn') : null;
    if (btn) return; // "+" note button keeps its own job.
    var tile = e.target.closest ? e.target.closest('.tile[data-symbol="GOLD"]') : null;
    if (tile) { openModal(); return; }
    if (e.target.closest && e.target.closest('#gold-close')) { closeModal(); return; }
    if (e.target.closest && e.target.closest('#gold-retry')) {
      var r = el('gold-retry'); if (r) r.style.display = 'none';
      state.weeks = []; loadData(); return;
    }
    var modal = el('gold-modal');
    if (modal && modal.classList.contains('open') && e.target === modal) closeModal();
    var pill = el('gold-pill');
    if (pill && e.target === pill) pill.style.display = 'none';
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeModal();
  });
  window.addEventListener('resize', function () {
    var modal = el('gold-modal');
    if (modal && modal.classList.contains('open')) draw();
  });
  document.addEventListener('DOMContentLoaded', function () {
    var canvas = el('gold-canvas');
    if (canvas) canvas.addEventListener('click', onCanvasTap);
    var pill = el('gold-pill');
    if (pill) pill.addEventListener('click', function () { pill.style.display = 'none'; });
  });

  // Exposed for the headless verification harness only.
  window.ScreenerGold = { aggregateWeekly: aggregateWeekly, YTD_START: YTD_START };
})();
