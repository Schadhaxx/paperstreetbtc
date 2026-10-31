// Comparison chart for the Maple Leaf screener.
// Lines are rebased daily closes (assets/data/cmp-daily.json). The last
// point of a stock uses the merged row from screener.js when that row is
// the same session or a newer one. Older snapshots do not erase a newer
// close. Day-change and YTD bars read those rows directly, so they cannot
// drift from the cards.
// Signed zero stays black (#000000). On this dark card that text is hard
// to see; the choice is deliberate and called out in the proposal.
(function () {
  var CmpMath = (function () {
    var YTD_BASE = '2025-12-31';
    var LISTING = '2026-06-12';
    function isNum(v) { return typeof v === 'number' && isFinite(v); }
    function pad(n) { return (n < 10 ? '0' : '') + n; }
    function fmtPct(v) {
      if (!isNum(v)) return '\u2014';
      return (v > 0 ? '+' : '') + v.toFixed(2) + '%';
    }
    function sign(v) {
      if (!isNum(v)) return '';
      if (v > 0) return 'up';
      if (v < 0) return 'down';
      return 'flat';
    }
    function cmpMoney(v) {
      if (!isNum(v)) return '\u2014';
      var s = Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      return (v < 0 ? '-$' : '$') + s;
    }
    function shiftMonths(iso, months) {
      var y = +iso.slice(0, 4), m = +iso.slice(5, 7) - 1, day = +iso.slice(8, 10);
      var dt = new Date(Date.UTC(y, m + months, 1));
      var dim = new Date(Date.UTC(dt.getUTCFullYear(), dt.getUTCMonth() + 1, 0)).getUTCDate();
      var d = Math.min(day, dim);
      return dt.getUTCFullYear() + '-' + pad(dt.getUTCMonth() + 1) + '-' + pad(d);
    }
    function lastOnOrBefore(dates, iso) {
      var found = null;
      for (var i = 0; i < dates.length; i++) {
        if (dates[i] <= iso) found = dates[i];
        else break;
      }
      return found;
    }
    function commonTarget(range, asOf) {
      if (range === 'ytd') return YTD_BASE;
      if (range === 'listing') return LISTING;
      var months = range === '1M' ? -1 : range === '3M' ? -3 : range === '6M' ? -6 : null;
      if (months === null) return YTD_BASE;
      return shiftMonths(asOf, months);
    }
    // anchorDate is the common start. explicitBase is the 31 Dec close for
    // a YTD name, because that session is not in the daily series. Returns
    // null when the symbol was not listed yet (do not invent a line).
    function cmpRebase(dates, closes, anchorDate, explicitBase) {
      if (!dates || !dates.length || !anchorDate || dates.length !== closes.length) return null;
      var startAt = -1;
      for (var i = 0; i < dates.length; i++) {
        if (dates[i] <= anchorDate) startAt = i;
        else break;
      }
      var outD = [], outP = [], base;
      if (startAt === -1) {
        if (!isNum(explicitBase) || !(explicitBase > 0)) return null;
        base = explicitBase;
        outD.push(anchorDate);
        outP.push(0);
        for (var j = 0; j < dates.length; j++) {
          if (dates[j] <= anchorDate) continue;
          outD.push(dates[j]);
          outP.push((closes[j] / base - 1) * 100);
        }
      } else {
        base = closes[startAt];
        if (!isNum(base) || !(base > 0)) return null;
        for (var k = startAt; k < dates.length; k++) {
          outD.push(dates[k]);
          outP.push((closes[k] / base - 1) * 100);
        }
      }
      if (outD.length < 2) return null;
      if (Math.abs(outP[0]) > 1e-9) return null;
      return { dates: outD, pcts: outP, base: base };
    }
    function rankDesc(rows) {
      return rows.slice().sort(function (a, b) {
        var av = isNum(a.pct) ? a.pct : -Infinity;
        var bv = isNum(b.pct) ? b.pct : -Infinity;
        if (bv !== av) return bv - av;
        return String(a.sym).localeCompare(String(b.sym));
      });
    }
    return {
      YTD_BASE: YTD_BASE, LISTING: LISTING, isNum: isNum, fmtPct: fmtPct, sign: sign,
      cmpMoney: cmpMoney, shiftMonths: shiftMonths, lastOnOrBefore: lastOnOrBefore,
      commonTarget: commonTarget, cmpRebase: cmpRebase, rankDesc: rankDesc
    };
  })();

  var STOCKS = ['TSLA', 'PLTR', 'MSTR', 'IBIT', 'MU', 'META', 'SPCX'];
  var BENCH = ['BTC', 'SPY', 'QQQ'];
  var COLOR = {
    TSLA: '#22d3ee', PLTR: '#a78bfa', MSTR: '#fb923c', IBIT: '#38bdf8',
    MU: '#facc15', META: '#fb7185', SPCX: '#2dd4bf',
    BTC: '#94a3b8', SPY: '#64748b', QQQ: '#cbd5e1'
  };
  var CMP_V = '20261030';
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var MN = { Jan: '01', Feb: '02', Mar: '03', Apr: '04', May: '05', Jun: '06', Jul: '07', Aug: '08', Sep: '09', Oct: '10', Nov: '11', Dec: '12' };

  var daily = null;
  var dailyError = false;
  var rows = [];
  var view = 'lines';
  var range = 'ytd';
  var barMetric = 'day';
  var on = {};
  var benchOn = { BTC: false, SPY: false, QQQ: false };
  var hi = null;
  var chart = null;
  var tipIndex = null;
  STOCKS.forEach(function (s) { on[s] = true; });

  function motionOK() {
    return !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }
  function rowBy(sym) {
    for (var i = 0; i < rows.length; i++) if (rows[i].symbol === sym) return rows[i];
    return null;
  }
  function asOf() { return (daily && daily.asOf) || '2026-10-30'; }
  function asOfLabel() { return (daily && daily.asOfLabel) || '30 Oct 2026'; }
  function todayET() {
    try {
      return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
    } catch (e) { return null; }
  }
  function parsePretty(label) {
    var p = String(label || '').split(' ');
    if (p.length !== 3 || !MN[p[1]] || !/^\d{4}$/.test(p[2])) return null;
    var day = ('0' + p[0]).slice(-2);
    return p[2] + '-' + MN[p[1]] + '-' + day;
  }
  function rowSession(row) {
    if (!row || row._src === 'snapshot') return null;
    if (row._src === 'live') return todayET();
    if (row._closeDate) return parsePretty(row._closeDate);
    return null;
  }
  function seriesFor(sym) {
    var s = daily && daily.symbols && daily.symbols[sym];
    if (!s || !s.dates || !s.closes) return null;
    var dates = s.dates.slice();
    var closes = s.closes.slice();
    var row = rowBy(sym);
    if (row && CmpMath.isNum(row.price) && s.kind === 'stock') {
      var session = rowSession(row);
      var last = dates[dates.length - 1];
      if (session && session > last) {
        dates.push(session);
        closes.push(Math.round(row.price * 100) / 100);
      } else if (session && session === last) {
        closes[closes.length - 1] = Math.round(row.price * 100) / 100;
      }
    }
    return { dates: dates, closes: closes, baseClose: s.baseClose, basis: s.basis, kind: s.kind };
  }
  function selectedStocks() {
    return STOCKS.filter(function (s) { return on[s]; });
  }
  function lineModel() {
    var target = CmpMath.commonTarget(range, asOf());
    var names = selectedStocks().concat(BENCH.filter(function (s) { return benchOn[s]; }));
    var models = [], excluded = [];
    names.forEach(function (sym) {
      var ser = seriesFor(sym);
      if (!ser) { excluded.push(sym); return; }
      var anchor = target, explicit = null;
      if (range === 'ytd') {
        if (ser.basis === 'listing') { excluded.push(sym); return; }
        explicit = ser.baseClose;
      } else {
        var hit = CmpMath.lastOnOrBefore(ser.dates, target);
        if (!hit) { excluded.push(sym); return; }
        anchor = hit;
      }
      var rb = CmpMath.cmpRebase(ser.dates, ser.closes, anchor, explicit);
      if (!rb) { excluded.push(sym); return; }
      models.push({
        sym: sym, kind: ser.kind, dates: rb.dates, pcts: rb.pcts,
        pct: rb.pcts[rb.pcts.length - 1]
      });
    });
    return { models: models, excluded: excluded, target: target };
  }
  function dayPct(sym) {
    var r = rowBy(sym);
    return r && CmpMath.isNum(r.dayChangePct) ? r.dayChangePct : null;
  }
  function ytdPct(sym) {
    var r = rowBy(sym);
    if (!r || !CmpMath.isNum(r.ytdPct)) return null;
    if (r.ytdBasis === 'listing') return null;
    return r.ytdPct;
  }
  function listingPct(sym) {
    var r = rowBy(sym);
    if (r && r.ytdBasis === 'listing' && CmpMath.isNum(r.ytdPct)) return r.ytdPct;
    var ser = seriesFor(sym);
    if (!ser || ser.basis !== 'listing') return null;
    var rb = CmpMath.cmpRebase(ser.dates, ser.closes, ser.dates[0], null);
    return rb ? rb.pcts[rb.pcts.length - 1] : null;
  }
  function priceOf(sym) {
    var r = rowBy(sym);
    if (r && CmpMath.isNum(r.price)) return r.price;
    var s = daily && daily.symbols && daily.symbols[sym];
    if (s && s.closes && s.closes.length) return s.closes[s.closes.length - 1];
    return null;
  }

  function destroyChart() {
    if (chart) { chart.destroy(); chart = null; }
  }
  function hexAlpha(hex, a) {
    var n = parseInt(hex.slice(1), 16);
    return 'rgba(' + ((n >> 16) & 255) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + a + ')';
  }
  function fade(hex, dim) {
    return dim ? hexAlpha(hex, 0.28) : hex;
  }

  var gridPlugin = {
    id: 'cmpGrid',
    beforeDraw: function (c) {
      if (c.options.indexAxis === 'y') return;
      var y = c.scales.y, area = c.chartArea, g = c.ctx;
      if (!y || !area) return;
      g.save();
      g.setLineDash([2, 4]);
      g.lineWidth = 1;
      (y.ticks || []).forEach(function (t) {
        var py = y.getPixelForValue(t.value);
        if (py < area.top - 1 || py > area.bottom + 1) return;
        g.strokeStyle = t.value === 0 ? 'rgba(238,242,251,.42)' : 'rgba(148,163,184,.16)';
        g.beginPath();
        g.moveTo(area.left, py);
        g.lineTo(area.right, py);
        g.stroke();
      });
      g.restore();
    }
  };
  var endPlugin = {
    id: 'cmpEnds',
    afterDatasetsDraw: function (c) {
      if (view !== 'lines') return;
      var area = c.chartArea, g = c.ctx;
      if (!area) return;
      var placed = [];
      var sets = c.data.datasets || [];
      g.save();
      g.font = '700 11px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif';
      g.textBaseline = 'middle';
      sets.forEach(function (ds, di) {
        var meta = c.getDatasetMeta(di);
        if (!meta || meta.hidden) return;
        var last = null;
        for (var i = meta.data.length - 1; i >= 0; i--) {
          var v = ds.data[i];
          if (v === null || v === undefined) continue;
          last = meta.data[i];
          break;
        }
        if (!last) return;
        var label = ds.label + ' ' + CmpMath.fmtPct(ds._end);
        var dim = hi && ds.label !== hi;
        if (dim && area.right - area.left < 520) return;
        var y = last.y;
        for (var p = 0; p < placed.length; p++) if (Math.abs(placed[p] - y) < 13) y = placed[p] - 13;
        y = Math.max(area.top + 6, Math.min(area.bottom - 6, y));
        placed.push(y);
        g.fillStyle = fade(ds.borderColor || '#eef2fb', dim);
        var tw = g.measureText(label).width;
        var x = last.x + 6;
        if (x + tw > c.width - 4) x = Math.max(area.left, last.x - tw - 6);
        g.fillText(label, x, y);
      });
      g.restore();
    }
  };
  var crossPlugin = {
    id: 'cmpCross',
    afterDraw: function (c) {
      if (view !== 'lines' || tipIndex === null) return;
      var meta = c.getDatasetMeta(0);
      if (!meta || !meta.data || !meta.data[tipIndex]) return;
      var x = meta.data[tipIndex].x, area = c.chartArea, g = c.ctx;
      g.save();
      g.strokeStyle = 'rgba(148,163,184,.55)';
      g.setLineDash([3, 3]);
      g.beginPath();
      g.moveTo(x, area.top);
      g.lineTo(x, area.bottom);
      g.stroke();
      g.restore();
    }
  };

  function showTip(labels, idx) {
    var tip = document.getElementById('cmp-tip');
    if (!tip) return;
    if (view !== 'lines' || !chart || idx === null || idx === undefined) { tip.hidden = true; return; }
    var items = [];
    (chart.data.datasets || []).forEach(function (ds) {
      var v = ds.data[idx];
      if (!CmpMath.isNum(v)) return;
      items.push({ sym: ds.label, pct: v, kind: ds._kind });
    });
    if (!items.length) { tip.hidden = true; return; }
    items = CmpMath.rankDesc(items);
    var date = labels[idx] || '';
    var pretty = date.length >= 10 ? (+date.slice(8, 10) + ' ' + MONTHS[+date.slice(5, 7) - 1] + ' ' + date.slice(0, 4)) : date;
    var html = '<div class="cmp-tip-row"><b>' + pretty + '</b><span></span></div>';
    items.forEach(function (it) {
      html += '<div class="cmp-tip-row"><span><i class="cmp-dot" style="background:' + (COLOR[it.sym] || '#94a3b8') + '"></i> ' + it.sym + '</span><b class="' + CmpMath.sign(it.pct) + '">' + CmpMath.fmtPct(it.pct) + '</b></div>';
    });
    tip.innerHTML = html;
    tip.hidden = false;
  }

  function renderLines(model) {
    var canvas = document.getElementById('screener-chart');
    var wrap = document.getElementById('cmp-canvas-wrap');
    if (!canvas || typeof Chart === 'undefined') return;
    if (wrap) wrap.hidden = false;
    if (!model.models.length) {
      destroyChart();
      showTip([], null);
      return;
    }
    var seen = {}, labels = [];
    model.models.forEach(function (m) {
      m.dates.forEach(function (d) { if (!seen[d]) { seen[d] = 1; labels.push(d); } });
    });
    labels.sort();
    var ordered = model.models.slice().sort(function (a, b) {
      if (a.sym === hi) return 1;
      if (b.sym === hi) return -1;
      return 0;
    });
    var datasets = ordered.map(function (m) {
      var map = {};
      m.dates.forEach(function (d, i) { map[d] = m.pcts[i]; });
      var dim = hi && m.sym !== hi;
      var col = COLOR[m.sym] || '#94a3b8';
      return {
        label: m.sym,
        _end: m.pct,
        _kind: m.kind,
        data: labels.map(function (d) { return map[d] === undefined ? null : map[d]; }),
        borderColor: fade(col, dim),
        backgroundColor: function (ctx) {
          if (m.sym !== hi) return 'transparent';
          var area = ctx.chart.chartArea;
          if (!area) return hexAlpha(col, 0.25);
          var g = ctx.chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
          g.addColorStop(0, hexAlpha(col, 0.38));
          g.addColorStop(1, hexAlpha(col, 0));
          return g;
        },
        borderWidth: m.sym === hi ? 3 : (m.kind === 'benchmark' ? 1.5 : 2),
        borderDash: m.kind === 'benchmark' ? [5, 4] : [],
        tension: 0.3,
        spanGaps: true,
        pointRadius: 0,
        pointHitRadius: 8,
        fill: m.sym === hi ? 'origin' : false
      };
    });
    var options = {
      responsive: true,
      maintainAspectRatio: false,
      animation: motionOK() ? { duration: 700, easing: 'easeOutQuart' } : false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: false,
          external: function (ctx) {
            var pts = ctx.tooltip && ctx.tooltip.dataPoints;
            tipIndex = pts && pts.length ? pts[0].dataIndex : null;
            showTip(labels, tipIndex);
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          border: { display: false },
          ticks: {
            color: '#94a3b8', maxRotation: 0, autoSkip: true,
            maxTicksLimit: (wrap && wrap.clientWidth < 520) ? 4 : 7,
            callback: function (value) {
              var lab = this.getLabelForValue(value);
              if (!lab || lab.length < 7) return lab;
              return MONTHS[+lab.slice(5, 7) - 1];
            }
          }
        },
        y: {
          grid: { display: false },
          border: { display: false },
          ticks: {
            color: '#94a3b8', maxTicksLimit: 6,
            callback: function (v) { return (v > 0 ? '+' : '') + v + '%'; }
          }
        }
      },
      layout: { padding: { right: (wrap && wrap.clientWidth < 520) ? 8 : 78, top: 8 } },
      onClick: function (_e, els) {
        if (els && els.length) {
          var ds = chart.data.datasets[els[0].datasetIndex];
          if (ds) setHighlight(ds.label, true);
        }
      }
    };
    if (chart) { chart.destroy(); chart = null; }
    chart = new Chart(canvas, { type: 'line', data: { labels: labels, datasets: datasets }, options: options, plugins: [gridPlugin, endPlugin, crossPlugin] });
    tipIndex = labels.length - 1;
    showTip(labels, tipIndex);
  }

  function renderBars() {
    var canvas = document.getElementById('screener-chart');
    var wrap = document.getElementById('cmp-canvas-wrap');
    if (!canvas || typeof Chart === 'undefined') return;
    if (wrap) wrap.hidden = false;
    var tip = document.getElementById('cmp-tip');
    if (tip) tip.hidden = true;
    var list = [];
    selectedStocks().forEach(function (sym) {
      var v = barMetric === 'ytd' ? ytdPct(sym) : dayPct(sym);
      if (barMetric === 'ytd' && sym === 'SPCX') return;
      if (!CmpMath.isNum(v)) return;
      list.push({ sym: sym, pct: v });
    });
    list = CmpMath.rankDesc(list);
    var labels = list.map(function (r) { return r.sym; });
    var values = list.map(function (r) { return r.pct; });
    var colors = values.map(function (v, i) {
      var base = v > 0 ? '#22c55e' : (v < 0 ? '#ef4444' : '#000000');
      if (hi && labels[i] !== hi) return hexAlpha(base, 0.35);
      return base;
    });
    var data = { labels: labels, datasets: [{ data: values, backgroundColor: colors, borderRadius: 8, barThickness: 16 }] };
    var options = {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      animation: motionOK() ? { duration: 500 } : false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function (item) {
              return (barMetric === 'ytd' ? 'YTD ' : 'Day ') + CmpMath.fmtPct(item.parsed.x);
            }
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          border: { display: false },
          ticks: { color: '#94a3b8', callback: function (v) { return (v > 0 ? '+' : '') + v + '%'; } }
        },
        y: { grid: { display: false }, border: { display: false }, ticks: { color: '#eef2fb', font: { weight: 700 } } }
      },
      onClick: function (_e, els) {
        if (els && els.length) setHighlight(labels[els[0].index], true);
      }
    };
    destroyChart();
    chart = new Chart(canvas, { type: 'bar', data: data, options: options, plugins: [gridPlugin] });
  }

  function heatColor(v, mode) {
    if (!CmpMath.isNum(v)) return 'rgba(255,255,255,.06)';
    var t = Math.tanh(v / (mode === 'ytd' ? 25 : 2.5));
    if (t > 0) return 'rgba(34,197,94,' + (0.16 + t * 0.74).toFixed(3) + ')';
    if (t < 0) return 'rgba(239,68,68,' + (0.16 + (-t) * 0.74).toFixed(3) + ')';
    return 'rgba(255,255,255,.06)';
  }
  function renderHeat() {
    var box = document.getElementById('cmp-heat');
    var wrap = document.getElementById('cmp-canvas-wrap');
    if (wrap) wrap.hidden = true;
    destroyChart();
    var tip = document.getElementById('cmp-tip');
    if (tip) tip.hidden = true;
    if (!box) return;
    box.hidden = false;
    box.innerHTML = selectedStocks().map(function (sym) {
      var listing = sym === 'SPCX';
      var v = barMetric === 'ytd' ? (listing ? listingPct(sym) : ytdPct(sym)) : dayPct(sym);
      var cap = barMetric === 'day' ? 'Day' : (listing ? 'Since listing' : 'YTD');
      var cls = 'cmp-tile' + (sym === hi ? ' is-hi' : '');
      return '<button type="button" class="' + cls + '" data-cmp-hit="' + sym + '" style="background:' + heatColor(v, barMetric) + '">' +
        '<span class="cmp-sym">' + sym + '</span>' +
        '<span class="cmp-px">' + CmpMath.cmpMoney(priceOf(sym)) + '</span>' +
        '<span class="cmp-ret ' + CmpMath.sign(v) + '">' + CmpMath.fmtPct(v) + '</span>' +
        '<span class="cmp-px">' + cap + '</span></button>';
    }).join('');
  }

  function spark(pcts, color) {
    if (!pcts || pcts.length < 2) return '';
    var step = Math.max(1, Math.floor(pcts.length / 28));
    var pts = [];
    for (var i = 0; i < pcts.length; i += step) pts.push(pcts[i]);
    if (pts[pts.length - 1] !== pcts[pcts.length - 1]) pts.push(pcts[pcts.length - 1]);
    var min = Math.min.apply(null, pts), max = Math.max.apply(null, pts);
    var span = (max - min) || 1, w = 72, h = 28;
    var d = pts.map(function (p, i) {
      var x = (i / (pts.length - 1)) * w;
      var y = h - ((p - min) / span) * (h - 4) - 2;
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    return '<svg class="cmp-spark" viewBox="0 0 72 28" aria-hidden="true"><polyline points="' + d + '" fill="none" stroke="' + color + '" stroke-width="1.6" /></svg>';
  }

  function renderBoard(model) {
    var board = document.getElementById('cmp-board');
    if (!board) return;
    var items;
    if (view === 'lines' && model) {
      items = CmpMath.rankDesc(model.models.filter(function (m) { return m.kind !== 'benchmark'; }));
    } else if (barMetric === 'day') {
      items = CmpMath.rankDesc(selectedStocks().map(function (sym) { return { sym: sym, pct: dayPct(sym), dates: [], pcts: [] }; }));
    } else {
      items = CmpMath.rankDesc(selectedStocks().filter(function (s) { return s !== 'SPCX'; }).map(function (sym) {
        return { sym: sym, pct: ytdPct(sym), dates: [], pcts: [] };
      }));
    }
    board.innerHTML = items.map(function (it) {
      var day = dayPct(it.sym);
      return '<li class="cmp-row' + (it.sym === hi ? ' is-hi' : '') + '"><button type="button" data-cmp-hit="' + it.sym + '">' +
        '<i class="cmp-swatch" style="background:' + (COLOR[it.sym] || '#94a3b8') + '"></i>' +
        '<span class="cmp-sym">' + it.sym + '</span>' +
        spark(it.pcts, COLOR[it.sym] || '#94a3b8') +
        '<span class="cmp-ret ' + CmpMath.sign(it.pct) + '">' + CmpMath.fmtPct(it.pct) + '</span>' +
        '<span class="cmp-day ' + CmpMath.sign(day) + '">' + CmpMath.fmtPct(day) + '</span>' +
        '</button></li>';
    }).join('');
  }

  function renderStats(model) {
    var box = document.getElementById('cmp-stats');
    if (!box) return;
    var stocks = (model && view === 'lines')
      ? model.models.filter(function (m) { return m.kind !== 'benchmark'; })
      : selectedStocks().map(function (sym) {
          var pct = barMetric === 'day' ? dayPct(sym) : (sym === 'SPCX' ? null : ytdPct(sym));
          return { sym: sym, pct: pct };
        }).filter(function (m) { return CmpMath.isNum(m.pct); });
    var ranked = CmpMath.rankDesc(stocks.filter(function (m) { return CmpMath.isNum(m.pct); }));
    var best = ranked[0], worst = ranked[ranked.length - 1];
    var spread = best && worst ? best.pct - worst.pct : null;
    var up = 0, known = 0;
    STOCKS.forEach(function (sym) {
      var d = dayPct(sym);
      if (!CmpMath.isNum(d)) return;
      known++;
      if (d > 0) up++;
    });
    function cell(k, text, cls) {
      return '<div class="cmp-stat"><span>' + k + '</span><b class="' + (cls || '') + '">' + text + '</b></div>';
    }
    box.innerHTML =
      cell('Best', best ? best.sym + ' ' + CmpMath.fmtPct(best.pct) : '\u2014', best ? CmpMath.sign(best.pct) : '') +
      cell('Worst', worst ? worst.sym + ' ' + CmpMath.fmtPct(worst.pct) : '\u2014', worst ? CmpMath.sign(worst.pct) : '') +
      cell('Spread', spread === null ? '\u2014' : CmpMath.fmtPct(spread).replace('%', ' pp')) +
      cell('Up today', known ? (up + ' of ' + known) : '\u2014');
  }

  function renderNote(model) {
    var note = document.getElementById('cmp-note');
    if (!note) return;
    if (dailyError) {
      note.textContent = 'Daily history did not load. Bars and the heat map still use the cards.';
      return;
    }
    var spcxOut = model && model.excluded.indexOf('SPCX') !== -1;
    var line;
    if (view !== 'lines') {
      line = barMetric === 'ytd'
        ? 'YTD vs 31 Dec 2025. SPCX is since 12 Jun 2026, not YTD. Closes through ' + asOfLabel() + '.'
        : 'Day change vs the prior close. Closes through ' + asOfLabel() + '.';
    } else if (range === 'ytd' && spcxOut) {
      line = 'SPCX is off this YTD view (since 12 Jun 2026, not 31 Dec 2025). Closes through ' + asOfLabel() + '.';
    } else if (range === 'listing') {
      line = 'Every line starts at 0% on 12 Jun 2026, the day SPCX first traded. Closes through ' + asOfLabel() + '.';
    } else if (spcxOut) {
      line = 'SPCX listed 12 Jun 2026, after this window starts, so it is left off. Closes through ' + asOfLabel() + '.';
    } else {
      line = 'Rebased to 0% at the start of this window. Closes through ' + asOfLabel() + '.';
    }
    note.textContent = line;
  }

  function renderSummary(model) {
    var el = document.getElementById('cmp-summary');
    if (!el) return;
    var stocks = model ? model.models.filter(function (m) { return m.kind !== 'benchmark' && CmpMath.isNum(m.pct); }) : [];
    var ranked = CmpMath.rankDesc(stocks);
    if (!ranked.length) {
      el.textContent = 'Comparison chart, as of ' + asOfLabel() + '.';
      return;
    }
    var best = ranked[0], worst = ranked[ranked.length - 1];
    el.textContent = 'Best: ' + best.sym + ' ' + CmpMath.fmtPct(best.pct) + ', worst: ' + worst.sym + ' ' + CmpMath.fmtPct(worst.pct) + ', as of ' + asOfLabel() + '.';
  }

  function renderFail() {
    var fail = document.getElementById('cmp-fail');
    var heat = document.getElementById('cmp-heat');
    if (fail) fail.hidden = !(dailyError && view === 'lines');
    if (heat && view !== 'heat') heat.hidden = true;
  }

  function render() {
    paintChips();
    var metric = document.getElementById('cmp-metric');
    if (metric) metric.hidden = view === 'lines';
    var model = (!dailyError && daily) ? lineModel() : { models: [], excluded: [], target: null };
    if (!hi && view === 'lines' && model.models.length) {
      var ranked0 = CmpMath.rankDesc(model.models.filter(function (m) { return m.kind !== 'benchmark'; }));
      if (ranked0[0]) hi = ranked0[0].sym;
    }
    renderStats(model);
    renderNote(model);
    renderBoard(model);
    renderSummary(model);
    renderFail();
    var canvasLabel = document.getElementById('screener-chart');
    if (view === 'heat') {
      if (canvasLabel) canvasLabel.setAttribute('aria-label', 'Comparison heat map is shown as tiles');
      renderHeat();
    } else if (view === 'bars') {
      var heat = document.getElementById('cmp-heat');
      if (heat) heat.hidden = true;
      if (canvasLabel) canvasLabel.setAttribute('aria-label', (barMetric === 'ytd' ? 'YTD' : 'Day change') + ' comparison bars');
      renderBars();
    } else {
      var heat2 = document.getElementById('cmp-heat');
      if (heat2) heat2.hidden = true;
      if (canvasLabel) canvasLabel.setAttribute('aria-label', 'Rebased performance comparison, ' + asOfLabel());
      if (dailyError || !daily) {
        destroyChart();
        var wrap = document.getElementById('cmp-canvas-wrap');
        if (wrap) wrap.hidden = true;
      } else renderLines(model);
    }
  }

  function paintChips() {
    document.querySelectorAll('[data-cmp-range]').forEach(function (b) {
      var onR = b.getAttribute('data-cmp-range') === range;
      b.classList.toggle('is-on', onR);
      b.setAttribute('aria-pressed', onR ? 'true' : 'false');
    });
    document.querySelectorAll('[data-cmp-symbol]').forEach(function (b) {
      var sym = b.getAttribute('data-cmp-symbol');
      var onS = !!on[sym];
      b.classList.toggle('is-on', onS);
      b.setAttribute('aria-pressed', onS ? 'true' : 'false');
      var dot = b.querySelector('.cmp-dot');
      if (dot) dot.style.background = COLOR[sym] || '#94a3b8';
    });
    document.querySelectorAll('[data-cmp-bench]').forEach(function (b) {
      var sym = b.getAttribute('data-cmp-bench');
      var onB = !!benchOn[sym];
      b.classList.toggle('is-on', onB);
      b.setAttribute('aria-pressed', onB ? 'true' : 'false');
    });
    document.querySelectorAll('[data-cmp-view]').forEach(function (b) {
      var onV = b.getAttribute('data-cmp-view') === view;
      b.classList.toggle('is-on', onV);
      b.setAttribute('aria-selected', onV ? 'true' : 'false');
    });
    document.querySelectorAll('[data-cmp-metric]').forEach(function (b) {
      var onM = b.getAttribute('data-cmp-metric') === barMetric;
      b.classList.toggle('is-on', onM);
      b.setAttribute('aria-pressed', onM ? 'true' : 'false');
    });
  }

  function highlightCard(sym, scroll) {
    var body = document.getElementById('screener-body');
    if (!body) return;
    var found = null;
    body.querySelectorAll('.card').forEach(function (card) {
      card.classList.remove('row-highlight');
      if (card.getAttribute('data-symbol') === sym) found = card;
    });
    if (found && scroll) {
      found.classList.add('row-highlight');
      found.scrollIntoView({ block: 'center', behavior: motionOK() ? 'smooth' : 'auto' });
    } else if (found) found.classList.add('row-highlight');
  }
  function setHighlight(sym, scrollCard) {
    if (!sym) return;
    if (STOCKS.indexOf(sym) !== -1 && !on[sym]) on[sym] = true;
    if (BENCH.indexOf(sym) !== -1) benchOn[sym] = true;
    hi = sym;
    highlightCard(sym, scrollCard);
    render();
  }

  function loadDaily() {
    dailyError = false;
    var fail = document.getElementById('cmp-fail');
    if (fail) fail.hidden = true;
    fetch('assets/data/cmp-daily.json?v=' + CMP_V, { cache: 'no-cache' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (doc) {
        if (!doc || !doc.symbols || !doc.symbols.TSLA) throw new Error('bad file');
        daily = doc;
        dailyError = false;
        render();
      })
      .catch(function () {
        daily = null;
        dailyError = true;
        render();
      });
  }

  window.ScreenerChartUpdate = function (next) {
    rows = next || [];
    render();
  };
  window.addEventListener('screener-rows', function (e) {
    rows = (e && e.detail) || [];
    render();
  });

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-cmp-range]').forEach(function (b) {
      b.addEventListener('click', function () { range = b.getAttribute('data-cmp-range'); render(); });
    });
    document.querySelectorAll('[data-cmp-symbol]').forEach(function (b) {
      b.addEventListener('click', function () {
        var sym = b.getAttribute('data-cmp-symbol');
        on[sym] = !on[sym];
        if (!on[sym] && hi === sym) hi = null;
        render();
      });
    });
    document.querySelectorAll('[data-cmp-bench]').forEach(function (b) {
      b.addEventListener('click', function () {
        var sym = b.getAttribute('data-cmp-bench');
        benchOn[sym] = !benchOn[sym];
        render();
      });
    });
    document.querySelectorAll('[data-cmp-view]').forEach(function (b) {
      b.addEventListener('click', function () { view = b.getAttribute('data-cmp-view'); render(); });
    });
    document.querySelectorAll('[data-cmp-metric]').forEach(function (b) {
      b.addEventListener('click', function () { barMetric = b.getAttribute('data-cmp-metric'); render(); });
    });
    var chartCard = document.querySelector('.chart-card');
    if (chartCard) chartCard.addEventListener('click', function (e) {
      var hit = e.target.closest && e.target.closest('[data-cmp-hit]');
      if (!hit) return;
      setHighlight(hit.getAttribute('data-cmp-hit'), true);
    });
    var retry = document.getElementById('cmp-retry');
    if (retry) retry.addEventListener('click', loadDaily);
    var body = document.getElementById('screener-body');
    if (body) body.addEventListener('click', function (e) {
      if (e.target.closest && e.target.closest('.note-btn')) return;
      var card = e.target.closest ? e.target.closest('.card') : null;
      if (!card) return;
      var sym = card.getAttribute('data-symbol');
      if (sym) setHighlight(sym, false);
    });
    loadDaily();
  });
})();
