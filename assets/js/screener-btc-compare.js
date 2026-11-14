window.psC = window.psC || function (d, l) { return document.documentElement.getAttribute('data-theme') === 'light' ? l : d; };
// Desk "Spot Bitcoin comparison": native canvas only (no Chart.js).
// Independent of screener-indicator-chart.js and btcchart-panel.js.
// Scale: each series is close / firstClose (1× at its own start), drawn on
// a log-y axis. Linear % would collapse every 2026-only line against
// Bitcoin's ~1,000,000× rise since 18 Aug 2010 (btc-daily.json).
(function () {
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var COLOR = {
    BTC: psC('#f8fafc', '#0f172a'),
    TSLA: psC('#22d3ee', '#0891b2'), PLTR: psC('#a78bfa', '#7c3aed'), MSTR: psC('#fb923c', '#ea580c'), IBIT: psC('#38bdf8', '#0284c7'),
    MU: psC('#facc15', '#ca8a04'), META: psC('#fb7185', '#e11d48'), SPCX: psC('#2dd4bf', '#0d9488'),
    'BRK.B': psC('#c084fc', '#7e22ce'), AAPL: psC('#60a5fa', '#2563eb'), AMZN: psC('#fbbf24', '#d97706'),
    MSFT: psC('#34d399', '#059669'), NFLX: psC('#f87171', '#dc2626'), SPOT: psC('#4ade80', '#16a34a'),
    XYZ: psC('#e879f9', '#a21caf'), GOOGL: psC('#38bdf8', '#0369a1'), NVDA: psC('#a3e635', '#65a30d'),
    WTI: psC('#94a3b8', '#475569'), GOLD: psC('#eab308', '#a16207'), US10Y: psC('#64748b', '#334155'),
    VIX: psC('#c084fc', '#6b21a8'), DIA: psC('#67e8f9', '#0e7490'), QQQ: psC('#cbd5e1', '#64748b'),
    USDCAD: psC('#fdba74', '#c2410c'), DXY: psC('#86efac', '#15803d')
  };
  // Longest existing files already in the repo. Later files only extend
  // or refresh the tail. No new feeds.
  var FILES = {
    BTC: ['assets/data/btc-daily.json'],
    GOLD: ['assets/data/gold-daily.json', 'assets/data/ind-daily-gold.json'],
    MSTR: ['assets/data/mstr-daily.json', 'assets/data/stock-daily-MSTR.json'],
    TSLA: ['assets/data/stock-daily-TSLA.json'], PLTR: ['assets/data/stock-daily-PLTR.json'],
    IBIT: ['assets/data/stock-daily-IBIT.json'], MU: ['assets/data/stock-daily-MU.json'],
    META: ['assets/data/stock-daily-META.json'], SPCX: ['assets/data/stock-daily-SPCX.json'],
    'BRK.B': ['assets/data/stock-daily-BRK.B.json'], AAPL: ['assets/data/stock-daily-AAPL.json'],
    AMZN: ['assets/data/stock-daily-AMZN.json'], MSFT: ['assets/data/stock-daily-MSFT.json'],
    NFLX: ['assets/data/stock-daily-NFLX.json'], SPOT: ['assets/data/stock-daily-SPOT.json'],
    XYZ: ['assets/data/stock-daily-XYZ.json'], GOOGL: ['assets/data/stock-daily-GOOGL.json'],
    NVDA: ['assets/data/stock-daily-NVDA.json'],
    WTI: ['assets/data/ind-daily-wti.json'], US10Y: ['assets/data/ind-daily-us10y.json'],
    VIX: ['assets/data/ind-daily-vix.json'], DIA: ['assets/data/ind-daily-dia.json'],
    QQQ: ['assets/data/qqq-weekly.json'], USDCAD: ['assets/data/usdcad-weekly.json'],
    DXY: ['assets/data/dxy-weekly.json']
  };
  var PIN = 'bbc1';
  var BTC_START = '2010-08-18';
  var cache = {};
  var pending = {};
  var on = { BTC: true, MSTR: true, IBIT: true };
  var hoverIdx = null;
  var layout = null;

  function isNum(v) { return typeof v === 'number' && isFinite(v); }
  function pretty(iso) {
    if (!iso || iso.length < 10) return iso || '';
    return (+iso.slice(8, 10)) + ' ' + MONTHS[+iso.slice(5, 7) - 1] + ' ' + iso.slice(0, 4);
  }
  function fmtMult(v) {
    if (!isNum(v) || v <= 0) return '—';
    if (v >= 1000000) return (v / 1000000).toFixed(v >= 10000000 ? 0 : 2) + 'M×';
    if (v >= 1000) return Math.round(v).toLocaleString('en-US') + '×';
    if (v >= 10) return v.toFixed(1) + '×';
    return v.toFixed(2) + '×';
  }
  function fmtPct(v) {
    if (!isNum(v)) return '—';
    var pct = (v - 1) * 100;
    var t = pct >= 1000 ? Math.round(pct).toLocaleString('en-US') : pct.toFixed(1);
    return (pct > 0 ? '+' : '') + t + '%';
  }
  function parseDoc(doc) {
    var out = [];
    if (!doc) return out;
    if (doc.d && doc.d.length) {
      doc.d.forEach(function (row) {
        var c = +row[1];
        if (row[0] && isNum(c) && c > 0) out.push({ date: row[0], close: c });
      });
      return out;
    }
    if (doc.days && doc.days.length) {
      doc.days.forEach(function (row) {
        var c = +row.close;
        if (row.date && isNum(c) && c > 0) out.push({ date: row.date, close: c });
      });
      return out;
    }
    if (doc.weeks && doc.weeks.length) {
      doc.weeks.forEach(function (w) {
        var c = +w.close;
        var date = w.sunday || w.monday;
        if (date && isNum(c) && c > 0) out.push({ date: date, close: c });
      });
    }
    return out;
  }
  function mergeParts(parts) {
    var map = {};
    parts.forEach(function (rows) {
      (rows || []).forEach(function (p) { map[p.date] = p.close; });
    });
    return Object.keys(map).sort().map(function (d) { return { date: d, close: map[d] }; });
  }
  function normalize(rows) {
    if (!rows || !rows.length) return null;
    var base = rows[0].close;
    if (!isNum(base) || !(base > 0)) return null;
    return {
      start: rows[0].date,
      end: rows[rows.length - 1].date,
      base: base,
      points: rows.map(function (r) { return { date: r.date, close: r.close, mult: r.close / base }; })
    };
  }
  function loadSym(sym) {
    if (cache[sym]) return Promise.resolve(cache[sym]);
    if (pending[sym]) return pending[sym];
    var urls = FILES[sym];
    if (!urls) return Promise.resolve(null);
    pending[sym] = Promise.all(urls.map(function (u) {
      return fetch(u + '?v=' + PIN, { cache: 'no-cache' }).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(parseDoc).catch(function () { return []; });
    })).then(function (parts) {
      var rows = mergeParts(parts);
      var series = normalize(rows);
      cache[sym] = series;
      delete pending[sym];
      return series;
    });
    return pending[sym];
  }

  function selected() {
    return Object.keys(on).filter(function (s) { return on[s]; });
  }
  function colorOf(sym) { return COLOR[sym] || psC('#94a3b8', '#475569'); }

  function paintChips() {
    document.querySelectorAll('[data-btc-cmp]').forEach(function (b) {
      var sym = b.getAttribute('data-btc-cmp');
      var isOn = !!on[sym];
      b.classList.toggle('is-on', isOn);
      b.setAttribute('aria-pressed', isOn ? 'true' : 'false');
      var dot = b.querySelector('.cmp-dot');
      if (dot) dot.style.background = colorOf(sym);
    });
  }

  function renderLegend(seriesMap) {
    var box = document.getElementById('btc-cmp-legend');
    if (!box) return;
    var late = false;
    box.innerHTML = selected().map(function (sym) {
      var s = seriesMap[sym];
      if (!s) return '<span><i class="cmp-dot" style="background:' + colorOf(sym) + '"></i>' + sym + ' (loading)</span>';
      var lateStart = s.start > BTC_START;
      if (lateStart) late = true;
      var cls = lateStart ? ' late' : '';
      var extra = lateStart ? ' · 1× at ' + pretty(s.start) : ' · since ' + pretty(s.start);
      return '<span class="' + cls + '"><i class="cmp-dot" style="background:' + colorOf(sym) + '"></i>' + sym + extra + '</span>';
    }).join('');
  }

  function dayNum(iso) { return Date.parse(iso + 'T00:00:00Z') / 86400000; }

  function buildLayout(seriesMap, cssW, cssH) {
    var names = selected().filter(function (s) { return seriesMap[s] && seriesMap[s].points.length; });
    if (!names.length) return null;
    var x0 = dayNum(BTC_START), x1 = x0;
    var yMin = 1, yMax = 1;
    names.forEach(function (sym) {
      seriesMap[sym].points.forEach(function (p) {
        var x = dayNum(p.date);
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (p.mult < yMin) yMin = p.mult;
        if (p.mult > yMax) yMax = p.mult;
      });
    });
    if (x1 <= x0) x1 = x0 + 1;
    yMin = Math.max(0.05, yMin * 0.8);
    yMax = yMax * 1.15;
    if (yMax <= yMin) yMax = yMin * 10;
    var padL = 58, padR = 12, padT = 10, padB = 28;
    var iw = Math.max(40, cssW - padL - padR);
    var ih = Math.max(40, cssH - padT - padB);
    var logMin = Math.log10(yMin), logMax = Math.log10(yMax);
    function X(iso) { return padL + (dayNum(iso) - x0) / (x1 - x0) * iw; }
    function Y(mult) {
      var v = Math.max(yMin, Math.min(yMax, mult));
      return padT + (logMax - Math.log10(v)) / (logMax - logMin) * ih;
    }
    return { names: names, x0: x0, x1: x1, yMin: yMin, yMax: yMax, padL: padL, padR: padR, padT: padT, padB: padB, iw: iw, ih: ih, X: X, Y: Y, cssW: cssW, cssH: cssH };
  }

  function logTicks(yMin, yMax) {
    var ticks = [];
    var startExp = Math.floor(Math.log10(yMin));
    var endExp = Math.ceil(Math.log10(yMax));
    for (var e = startExp; e <= endExp; e++) {
      var v = Math.pow(10, e);
      if (v >= yMin * 0.98 && v <= yMax * 1.02) ticks.push(v);
    }
    if (!ticks.length) ticks.push(1);
    return ticks;
  }

  function yearTicks(x0, x1, cssW) {
    var years = [];
    var y0 = 2010, y1 = 2026;
    try {
      y0 = parseInt(new Date(x0 * 86400000).toISOString().slice(0, 4), 10);
      y1 = parseInt(new Date(x1 * 86400000).toISOString().slice(0, 4), 10);
    } catch (e) {}
    var step = cssW && cssW < 560 ? 4 : ((y1 - y0) > 10 ? 2 : 1);
    for (var y = y0; y <= y1; y += step) years.push(y + '-01-01');
    if (years[0] && dayNum(years[0]) < x0) years[0] = BTC_START;
    return years;
  }

  function draw(seriesMap) {
    var canvas = document.getElementById('btc-cmp-canvas');
    var wrap = document.getElementById('btc-cmp-wrap');
    if (!canvas || !wrap) return;
    var cssW = Math.max(120, wrap.clientWidth || canvas.clientWidth || 300);
    var cssH = Math.max(160, wrap.clientHeight || 280);
    var dpr = Math.max(1, window.devicePixelRatio || 1);
    if (canvas.width !== Math.round(cssW * dpr) || canvas.height !== Math.round(cssH * dpr)) {
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
      canvas.style.width = cssW + 'px';
      canvas.style.height = cssH + 'px';
    }
    var ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);
    var L = buildLayout(seriesMap, cssW, cssH);
    layout = L;
    if (!L) {
      ctx.fillStyle = psC('#94a3b8', '#64748b');
      ctx.font = '13px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif';
      ctx.fillText('Loading comparison…', 16, cssH / 2);
      return;
    }
    var ink = psC('#94a3b8', '#64748b');
    var grid = psC('rgba(148,163,184,.16)', 'rgba(15,23,42,.10)');
    var zero = psC('rgba(238,242,251,.42)', 'rgba(15,23,42,.35)');
    ctx.font = '11px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif';
    ctx.textBaseline = 'middle';
    logTicks(L.yMin, L.yMax).forEach(function (v) {
      var y = L.Y(v);
      ctx.strokeStyle = v === 1 ? zero : grid;
      ctx.lineWidth = 1;
      ctx.setLineDash(v === 1 ? [] : [2, 4]);
      ctx.beginPath();
      ctx.moveTo(L.padL, y);
      ctx.lineTo(L.padL + L.iw, y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = ink;
      ctx.textAlign = 'right';
      ctx.fillText(fmtMult(v), L.padL - 6, y);
    });
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    yearTicks(L.x0, L.x1, cssW).forEach(function (iso) {
      var x = L.X(iso);
      if (x < L.padL - 2 || x > L.padL + L.iw + 2) return;
      ctx.strokeStyle = grid;
      ctx.setLineDash([2, 4]);
      ctx.beginPath();
      ctx.moveTo(x, L.padT);
      ctx.lineTo(x, L.padT + L.ih);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = ink;
      ctx.fillText(iso.slice(0, 4), x, L.padT + L.ih + 8);
    });

    L.names.forEach(function (sym) {
      var pts = seriesMap[sym].points;
      if (!pts.length) return;
      ctx.strokeStyle = colorOf(sym);
      ctx.lineWidth = sym === 'BTC' ? 2.4 : 1.7;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.beginPath();
      var started = false;
      pts.forEach(function (p) {
        var x = L.X(p.date), y = L.Y(p.mult);
        if (!started) { ctx.moveTo(x, y); started = true; }
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    });

    if (hoverIdx && hoverIdx.iso) {
      var hx = L.X(hoverIdx.iso);
      if (hx >= L.padL && hx <= L.padL + L.iw) {
        ctx.strokeStyle = psC('rgba(148,163,184,.55)', 'rgba(15,23,42,.35)');
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(hx, L.padT);
        ctx.lineTo(hx, L.padT + L.ih);
        ctx.stroke();
        ctx.setLineDash([]);
        L.names.forEach(function (sym) {
          var hit = valueAt(seriesMap[sym], hoverIdx.iso);
          if (!hit) return;
          ctx.fillStyle = colorOf(sym);
          ctx.beginPath();
          ctx.arc(L.X(hit.date), L.Y(hit.mult), 3.2, 0, Math.PI * 2);
          ctx.fill();
        });
      }
    }
  }

  function valueAt(series, iso) {
    if (!series || !series.points.length) return null;
    var found = null;
    for (var i = 0; i < series.points.length; i++) {
      if (series.points[i].date <= iso) found = series.points[i];
      else break;
    }
    if (!found || found.date > iso) return null;
    // Do not extend a short series past its last date.
    if (iso > series.end) return null;
    return found;
  }

  function nearestDate(seriesMap, isoGuess, xPix) {
    if (!layout) return null;
    var best = null, bestD = Infinity;
    layout.names.forEach(function (sym) {
      (seriesMap[sym].points || []).forEach(function (p) {
        var d = Math.abs(layout.X(p.date) - xPix);
        if (d < bestD) { bestD = d; best = p.date; }
      });
    });
    return best;
  }

  function showTip(seriesMap, iso) {
    var tip = document.getElementById('btc-cmp-tip');
    if (!tip) return;
    if (!iso) { tip.hidden = true; return; }
    var rows = [];
    selected().forEach(function (sym) {
      var hit = valueAt(seriesMap[sym], iso);
      if (!hit) return;
      rows.push({ sym: sym, mult: hit.mult, date: hit.date });
    });
    if (!rows.length) { tip.hidden = true; return; }
    rows.sort(function (a, b) { return b.mult - a.mult; });
    var html = '<div class="btc-cmp-tip-row"><b>' + pretty(iso) + '</b><span>vs own start</span></div>';
    rows.forEach(function (r) {
      html += '<div class="btc-cmp-tip-row"><span><i class="cmp-dot" style="background:' + colorOf(r.sym) + '"></i> ' + r.sym +
        (r.date !== iso ? ' · last ' + pretty(r.date) : '') +
        '</span><b>' + fmtMult(r.mult) + '  ' + fmtPct(r.mult) + '</b></div>';
    });
    tip.innerHTML = html;
    tip.hidden = false;
  }

  var lastMap = {};
  function render() {
    paintChips();
    var names = selected();
    Promise.all(names.map(function (s) { return loadSym(s).then(function (ser) { return [s, ser]; }); }))
      .then(function (pairs) {
        var map = {};
        pairs.forEach(function (p) { map[p[0]] = p[1]; });
        lastMap = map;
        renderLegend(map);
        draw(map);
        if (hoverIdx && hoverIdx.iso) showTip(map, hoverIdx.iso);
      });
  }

  function onPointer(ev) {
    if (!layout) return;
    var canvas = document.getElementById('btc-cmp-canvas');
    var rect = canvas.getBoundingClientRect();
    var x = ev.clientX - rect.left;
    if (x < layout.padL || x > layout.padL + layout.iw) return;
    var iso = nearestDate(lastMap, null, x);
    hoverIdx = iso ? { iso: iso } : null;
    draw(lastMap);
    showTip(lastMap, iso);
  }

  function refreshColors() {
    COLOR.BTC = psC('#f8fafc', '#0f172a');
    COLOR.TSLA = psC('#22d3ee', '#0891b2'); COLOR.PLTR = psC('#a78bfa', '#7c3aed');
    COLOR.MSTR = psC('#fb923c', '#ea580c'); COLOR.IBIT = psC('#38bdf8', '#0284c7');
    COLOR.MU = psC('#facc15', '#ca8a04'); COLOR.META = psC('#fb7185', '#e11d48');
    COLOR.SPCX = psC('#2dd4bf', '#0d9488'); COLOR['BRK.B'] = psC('#c084fc', '#7e22ce');
    COLOR.AAPL = psC('#60a5fa', '#2563eb'); COLOR.AMZN = psC('#fbbf24', '#d97706');
    COLOR.MSFT = psC('#34d399', '#059669'); COLOR.NFLX = psC('#f87171', '#dc2626');
    COLOR.SPOT = psC('#4ade80', '#16a34a'); COLOR.XYZ = psC('#e879f9', '#a21caf');
    COLOR.GOOGL = psC('#38bdf8', '#0369a1'); COLOR.NVDA = psC('#a3e635', '#65a30d');
    COLOR.WTI = psC('#94a3b8', '#475569'); COLOR.GOLD = psC('#eab308', '#a16207');
    COLOR.US10Y = psC('#64748b', '#334155'); COLOR.VIX = psC('#c084fc', '#6b21a8');
    COLOR.DIA = psC('#67e8f9', '#0e7490'); COLOR.QQQ = psC('#cbd5e1', '#64748b');
    COLOR.USDCAD = psC('#fdba74', '#c2410c'); COLOR.DXY = psC('#86efac', '#15803d');
  }

  document.addEventListener('DOMContentLoaded', function () {
    paintChips();
    document.querySelectorAll('[data-btc-cmp]').forEach(function (b) {
      b.addEventListener('click', function () {
        var sym = b.getAttribute('data-btc-cmp');
        if (sym === 'BTC') return;
        on[sym] = !on[sym];
        render();
      });
    });
    var canvas = document.getElementById('btc-cmp-canvas');
    if (canvas) {
      canvas.addEventListener('pointermove', onPointer);
      canvas.addEventListener('pointerdown', onPointer);
      canvas.addEventListener('pointerleave', function () {
        hoverIdx = null;
        draw(lastMap);
        var tip = document.getElementById('btc-cmp-tip');
        if (tip) tip.hidden = true;
      });
    }
    if (window.ResizeObserver) {
      var wrap = document.getElementById('btc-cmp-wrap');
      if (wrap) new ResizeObserver(function () { if (lastMap) draw(lastMap); }).observe(wrap);
    } else {
      window.addEventListener('resize', function () { if (lastMap) draw(lastMap); });
    }
    if (window.MutationObserver) {
      new MutationObserver(function () {
        refreshColors();
        paintChips();
        renderLegend(lastMap);
        draw(lastMap);
      }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    }
    render();
  });
})();
