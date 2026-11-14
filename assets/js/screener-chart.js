window.psC=window.psC||function(d,l){return document.documentElement.getAttribute('data-theme')==='light'?l:d;};
// Comparison heat map for the Maple Leaf screener.
// Day-change and YTD tiles read the merged rows from screener.js, so they
// cannot drift from the cards. Daily history (assets/data/cmp-daily.json)
// is still loaded for as-of labels, a price fallback, and SPCX's
// since-listing figure. The last point of a stock series uses the merged
// row when that row is the same session or a newer one.
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

  var STOCKS = ['TSLA', 'PLTR', 'MSTR', 'IBIT', 'MU', 'META', 'SPCX', 'BRK.B', 'AAPL', 'AMZN', 'MSFT', 'NFLX', 'SPOT', 'XYZ', 'GOOGL', 'NVDA'];
  var COLOR = {
    TSLA: psC('#22d3ee','#0891b2'), PLTR: psC('#a78bfa','#7c3aed'), MSTR: psC('#fb923c','#ea580c'), IBIT: psC('#38bdf8','#0284c7'),
    MU: psC('#facc15','#ca8a04'), META: psC('#fb7185','#e11d48'), SPCX: psC('#2dd4bf','#0d9488'),
    'BRK.B': psC('#c084fc','#7e22ce'), AAPL: psC('#60a5fa','#2563eb'), AMZN: psC('#fbbf24','#d97706'),
    MSFT: psC('#34d399','#059669'), NFLX: psC('#f87171','#dc2626'), SPOT: psC('#4ade80','#16a34a'),
    XYZ: psC('#e879f9','#a21caf'), GOOGL: psC('#38bdf8','#0369a1'), NVDA: psC('#a3e635','#65a30d'),
    BTC: psC('#94a3b8','#475569'), SPY: psC('#64748b','#334155'), QQQ: psC('#cbd5e1','#64748b')
  };
  var CMP_V = '20261031a';
  var MN = { Jan: '01', Feb: '02', Mar: '03', Apr: '04', May: '05', Jun: '06', Jul: '07', Aug: '08', Sep: '09', Oct: '10', Nov: '11', Dec: '12' };

  var daily = null;
  var dailyError = false;
  var rows = [];
  var barMetric = 'day';
  var on = {};
  var hi = null;
  STOCKS.forEach(function (s) { on[s] = (s === 'IBIT' || s === 'MSTR'); });

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
  function metricPct(sym) {
    if (barMetric === 'ytd') return sym === 'SPCX' ? listingPct(sym) : ytdPct(sym);
    return dayPct(sym);
  }
  function boardPct(sym) {
    if (barMetric === 'ytd') return ytdPct(sym);
    return dayPct(sym);
  }

  function heatColor(v, mode) {
    if (!CmpMath.isNum(v)) return psC('rgba(255,255,255,.06)','rgba(15,23,42,.06)');
    var t = Math.tanh(v / (mode === 'ytd' ? 25 : 2.5));
    if (t > 0) return 'rgba(34,197,94,' + (0.16 + t * 0.74).toFixed(3) + ')';
    if (t < 0) return 'rgba(239,68,68,' + (0.16 + (-t) * 0.74).toFixed(3) + ')';
    return psC('rgba(255,255,255,.06)','rgba(15,23,42,.06)');
  }
  function renderHeat() {
    var box = document.getElementById('cmp-heat');
    if (!box) return;
    box.hidden = false;
    box.innerHTML = selectedStocks().map(function (sym) {
      var listing = sym === 'SPCX';
      var v = metricPct(sym);
      var cap = barMetric === 'day' ? 'Day' : (listing ? 'Since listing' : 'YTD');
      var cls = 'cmp-tile' + (sym === hi ? ' is-hi' : '');
      return '<button type="button" class="' + cls + '" data-cmp-hit="' + sym + '" style="background:' + heatColor(v, barMetric) + '">' +
        '<span class="cmp-sym">' + sym + '</span>' +
        '<span class="cmp-px">' + CmpMath.cmpMoney(priceOf(sym)) + '</span>' +
        '<span class="cmp-ret ' + CmpMath.sign(v) + '">' + CmpMath.fmtPct(v) + '</span>' +
        '<span class="cmp-px">' + cap + '</span></button>';
    }).join('');
  }

  function renderBoard() {
    var board = document.getElementById('cmp-board');
    if (!board) return;
    var names = barMetric === 'ytd' ? selectedStocks().filter(function (s) { return s !== 'SPCX'; }) : selectedStocks();
    var items = CmpMath.rankDesc(names.map(function (sym) { return { sym: sym, pct: boardPct(sym) }; }));
    var dayTwice = barMetric === 'day';
    board.innerHTML = items.map(function (it) {
      var day = dayPct(it.sym);
      return '<li class="cmp-row' + (it.sym === hi ? ' is-hi' : '') + '"><button type="button" data-cmp-hit="' + it.sym + '">' +
        '<i class="cmp-swatch" style="background:' + (COLOR[it.sym] || psC('#94a3b8','#475569')) + '"></i>' +
        '<span class="cmp-sym">' + it.sym + '</span>' +
        '<span class="cmp-ret ' + CmpMath.sign(it.pct) + '">' + CmpMath.fmtPct(it.pct) + '</span>' +
        (dayTwice ? '<span class="cmp-day"></span>' : '<span class="cmp-day ' + CmpMath.sign(day) + '">' + CmpMath.fmtPct(day) + '</span>') +
        '</button></li>';
    }).join('');
  }

  function renderStats() {
    var box = document.getElementById('cmp-stats');
    if (!box) return;
    var stocks = selectedStocks().map(function (sym) {
      return { sym: sym, pct: boardPct(sym) };
    }).filter(function (m) { return CmpMath.isNum(m.pct); });
    var ranked = CmpMath.rankDesc(stocks);
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

  function renderNote() {
    var note = document.getElementById('cmp-note');
    if (!note) return;
    if (dailyError) {
      note.textContent = 'Daily history did not load. The heat map still uses the cards.';
      return;
    }
    note.textContent = barMetric === 'ytd'
      ? 'YTD vs 31 Dec 2025. SPCX is since 12 Jun 2026, not YTD. Closes through ' + asOfLabel() + '.'
      : 'Day change vs the prior close. Closes through ' + asOfLabel() + '.';
  }

  function renderSummary() {
    var el = document.getElementById('cmp-summary');
    if (!el) return;
    var stocks = selectedStocks().map(function (sym) {
      return { sym: sym, pct: metricPct(sym) };
    }).filter(function (m) { return CmpMath.isNum(m.pct); });
    var ranked = CmpMath.rankDesc(stocks);
    if (!ranked.length) {
      el.textContent = 'Comparison chart, as of ' + asOfLabel() + '.';
      return;
    }
    var best = ranked[0], worst = ranked[ranked.length - 1];
    el.textContent = 'Best: ' + best.sym + ' ' + CmpMath.fmtPct(best.pct) + ', worst: ' + worst.sym + ' ' + CmpMath.fmtPct(worst.pct) + ', as of ' + asOfLabel() + '.';
  }

  function render() {
    paintChips();
    if (!selectedStocks().length) {
      var heat0 = document.getElementById('cmp-heat');
      if (heat0) { heat0.hidden = true; heat0.innerHTML = ''; }
      renderStats();
      renderNote();
      renderSummary();
      var board0 = document.getElementById('cmp-board');
      if (board0) board0.innerHTML = '<li class="cmp-fail">Pick at least one stock above to compare.</li>';
      return;
    }
    renderStats();
    renderNote();
    renderBoard();
    renderSummary();
    renderHeat();
  }

  function paintChips() {
    document.querySelectorAll('[data-cmp-symbol]').forEach(function (b) {
      var sym = b.getAttribute('data-cmp-symbol');
      var onS = !!on[sym];
      b.classList.toggle('is-on', onS);
      b.setAttribute('aria-pressed', onS ? 'true' : 'false');
      var dot = b.querySelector('.cmp-dot');
      if (dot) dot.style.background = COLOR[sym] || psC('#94a3b8','#475569');
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
    hi = sym;
    highlightCard(sym, scrollCard);
    render();
  }

  function loadDaily() {
    dailyError = false;
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
    document.querySelectorAll('[data-cmp-symbol]').forEach(function (b) {
      b.addEventListener('click', function () {
        var sym = b.getAttribute('data-cmp-symbol');
        on[sym] = !on[sym];
        if (!on[sym] && hi === sym) hi = null;
        render();
      });
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
