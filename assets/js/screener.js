// Stock Screener — Maple Leaf Pack
// Two boxes, one page: Stocks (7 rows) and Market Indicators (WTI, Gold,
// 10-Year Treasury Yield, VIX). Each box has its own table and ONE status
// line below that table — there is no per-row Status column, and no
// per-row status is rendered anywhere. The table status line is computed
// from the per-row feed flags (_src / _closeDate), which are internal only
// and are never displayed; they exist solely so a mixed table can say so
// plainly instead of claiming Live for all rows.
// Live source = the same data-branch prices.json the main site reads
// (GitHub Actions writes it every ~5 min on weekdays; visitors never call
// a quote API and no key is in here). Stocks: Finnhub quotes via the
// pipeline. Indicators: Yahoo chart quotes via the pipeline (WTI <- CL=F,
// 10Y <- ^TNX, VIX <- ^VIX) once the pipeline block lands; Gold spot has
// NO pipeline quote yet, so it stays on its dated pack close — never Live.
// Signed-number colours (Sunil's rule): positive green #22c55e,
// negative red #ef4444, signed zero black #000000 (.flat). NOTE: pure
// black on this page's dark background (#070b18 / #121a2e) is
// near-invisible — that conflict is flagged in the delivery report; the
// rule is applied literally here, not silently replaced. 'n/a' is not a
// signed number, so it keeps the default light text, not black.
// No buy/sell action.
(function () {
  var PRICES_URL = 'https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/prices.json';
  var PACK_ASOF = '2026-10-28';
  var state = { q: '', filter: 'all', sortKey: 'symbol', sortDir: 1 };
  var packRows = [];
  var packIndicators = [];
  var packAsOf = PACK_ASOF;
  var rows = [];
  var indRows = [];
  var pricesFailed = false;

  function money(v) {
    return v === null || v === undefined ? '—' : '$' + v.toFixed(2);
  }
  function formatValue(r) {
    var v = r.price;
    if (v === null || v === undefined) return '—';
    if (r.unit === 'pct') return v.toFixed(2) + '%';
    if (r.unit === 'points') return v.toFixed(2);
    return money(v);
  }
  function pct(v) {
    if (v === null || v === undefined) return 'n/a';
    return (v > 0 ? '+' : '') + v.toFixed(2) + '%';
  }
  function signCls(v) {
    if (v === null || v === undefined) return '';
    if (v > 0) return 'up';
    if (v < 0) return 'down';
    return 'flat';
  }
  function dayText(r) {
    if (r.dayChange === null || r.dayChange === undefined) return '—';
    var sign = r.dayChange > 0 ? '+' : '';
    if (r.unit === 'pct') return sign + r.dayChange.toFixed(2) + ' pp (' + pct(r.dayChangePct) + ')';
    if (r.unit === 'points') return sign + r.dayChange.toFixed(2) + ' pts (' + pct(r.dayChangePct) + ')';
    return sign + '$' + r.dayChange.toFixed(2) + ' (' + pct(r.dayChangePct) + ')';
  }
  function fmtIso(iso) {
    var p = (iso || '').split('-');
    var MN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    if (p.length !== 3) return iso;
    return (+p[2]) + ' ' + MN[+p[1] - 1] + ' ' + p[0];
  }
  function etParts(d) {
    var parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York', weekday: 'short', month: 'short',
      day: 'numeric', year: 'numeric', hour: 'numeric', minute: 'numeric', hour12: false
    }).formatToParts(d);
    var o = {};
    parts.forEach(function (x) { o[x.type] = x.value; });
    return o;
  }
  function etDateLabel(d) {
    var p = etParts(d);
    return p.day + ' ' + p.month + ' ' + p.year;
  }
  function marketOpenNow() {
    var p = etParts(new Date());
    var weekday = p.weekday;
    if (weekday === 'Sat' || weekday === 'Sun') return false;
    var mins = (+p.hour % 24) * 60 + (+p.minute);
    return mins >= 570 && mins < 960;
  }

  function mergeList(srcRows, prices) {
    var out = srcRows.map(function (r) {
      var copy = {};
      Object.keys(r).forEach(function (k) { copy[k] = r[k]; });
      copy._src = 'snapshot';
      copy._closeDate = null;
      return copy;
    });
    if (!prices || !prices.stocks) return out;
    var updated = Date.parse(prices.updated);
    var fresh = !isNaN(updated) && (Date.now() - updated) < 30 * 60 * 1000;
    var live = fresh && marketOpenNow();
    out.forEach(function (r) {
      var q = prices.stocks[r.symbol];
      if (!q || typeof q.c !== 'number' || !(q.c > 0) ||
          typeof q.pc !== 'number' || !(q.pc > 0)) return;
      r.price = q.c;
      r.prevClose = q.pc;
      r.dayChange = q.c - q.pc;
      r.dayChangePct = (q.c / q.pc - 1) * 100;
      if (r.baseClose !== null && r.baseClose !== undefined) {
        r.ytdPct = (q.c / r.baseClose - 1) * 100;
      }
      if (live) {
        r._src = 'live';
      } else {
        r._src = 'close';
        r._closeDate = !isNaN(updated) ? etDateLabel(new Date(updated)) : fmtIso(packAsOf);
      }
    });
    return out;
  }

  function notifyChart() {
    if (typeof window.ScreenerChartUpdate === 'function') {
      window.ScreenerChartUpdate(rows);
    }
    if (typeof CustomEvent !== 'undefined') {
      window.dispatchEvent(new CustomEvent('screener-rows', { detail: rows }));
    }
  }

  function statusLine(list) {
    if (pricesFailed) return 'Pipeline quotes unavailable on this load — rows show their 28 Oct 2026 closes, not live quotes.';
    var live = list.filter(function (r) { return r._src === 'live'; }).map(function (r) { return r.symbol; });
    var close = list.filter(function (r) { return r._src === 'close'; });
    var snap = list.filter(function (r) { return r._src === 'snapshot'; }).map(function (r) { return r.symbol; });
    if (live.length === list.length) return 'Live — site pipeline, market hours.';
    if (close.length === list.length) return (close[0]._closeDate || fmtIso(packAsOf)) + ' close — site pipeline, not a live quote.';
    if (snap.length === list.length) return fmtIso(packAsOf) + ' closes from the data pack — not live quotes.';
    var parts = [];
    if (live.length) parts.push('Live for ' + live.join(', '));
    if (close.length) parts.push((close[0]._closeDate || fmtIso(packAsOf)) + ' close for ' + close.map(function (r) { return r.symbol; }).join(', '));
    if (snap.length) parts.push(fmtIso(packAsOf) + ' closes for ' + snap.join(', ') + ' (no pipeline quote)');
    return parts.join(' · ') + '.';
  }

  function renderStatus() {
    var s = document.getElementById('stocks-status');
    if (s) s.textContent = statusLine(rows);
    var i = document.getElementById('indicators-status');
    if (i) i.textContent = statusLine(indRows);
  }

  function updatePills() {
    var gainer = null, loser = null;
    rows.forEach(function (r) {
      if (r.dayChangePct === null || r.dayChangePct === undefined) return;
      if (!gainer || r.dayChangePct > gainer.dayChangePct) gainer = r;
      if (!loser || r.dayChangePct < loser.dayChangePct) loser = r;
    });
    var gv = document.getElementById('pill-gainer-val');
    var lv = document.getElementById('pill-loser-val');
    if (gv && gainer) { gv.textContent = gainer.symbol + ' ' + pct(gainer.dayChangePct); gv.className = signCls(gainer.dayChangePct); }
    if (lv && loser) { lv.textContent = loser.symbol + ' ' + pct(loser.dayChangePct); lv.className = signCls(loser.dayChangePct); }
  }

  function visible() {
    var q = state.q.trim().toLowerCase();
    var out = rows.filter(function (r) {
      if (state.filter === 'gainers' && !(r.dayChangePct > 0)) return false;
      if (state.filter === 'losers' && !(r.dayChangePct < 0)) return false;
      if (q && (r.symbol + ' ' + r.name).toLowerCase().indexOf(q) === -1) return false;
      return true;
    });
    var key = state.sortKey, dir = state.sortDir;
    out.sort(function (a, b) {
      if (key === 'price') {
        if (a.price === null) return 1;
        if (b.price === null) return -1;
      }
      var av = a[key], bv = b[key];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return 1;
      if (typeof av === 'string') return av.localeCompare(bv) * dir;
      return (av - bv) * dir;
    });
    return out;
  }

  function render() {
    var tbody = document.getElementById('screener-body');
    if (tbody) {
      var list = visible();
      tbody.innerHTML = list.map(function (r) {
        var note = r.note ? '<div class="row-note">' + r.note + '</div>' : '';
        return '<tr><td><strong>' + r.symbol + '</strong></td><td>' + r.name + note + '</td>'
          + '<td>' + money(r.price) + '</td>'
          + '<td class="' + signCls(r.dayChangePct) + '">' + dayText(r) + '</td>'
          + '<td class="' + signCls(r.ytdPct) + '">' + pct(r.ytdPct) + (r.ytdBasis === 'listing' ? '<div class="row-note">Since listing 12 Jun 2026</div>' : '') + '</td></tr>';
      }).join('');
      var count = document.getElementById('screener-count');
      if (count) count.textContent = list.length + ' of ' + rows.length + ' shown';
    }
    var itbody = document.getElementById('indicators-body');
    if (itbody) {
      itbody.innerHTML = indRows.map(function (r) {
        var note = r.note ? '<div class="row-note">' + r.note + '</div>' : '';
        return '<tr><td><strong>' + r.symbol + '</strong></td><td>' + r.name + note + '</td>'
          + '<td>' + formatValue(r) + '</td>'
          + '<td class="' + signCls(r.dayChangePct) + '">' + dayText(r) + '</td>'
          + '<td class="' + signCls(r.ytdPct) + '">' + pct(r.ytdPct) + (r.ytdBasis === 'listing' ? '<div class="row-note">Since listing 12 Jun 2026</div>' : '') + '</td></tr>';
      }).join('');
    }
    updatePills();
    renderStatus();
  }

  function sortBy(key) {
    if (state.sortKey === key) state.sortDir = -state.sortDir;
    else { state.sortKey = key; state.sortDir = key === 'symbol' ? 1 : -1; }
    render();
  }

  function fetchPrices() {
    var c = window.AbortController ? new AbortController() : null;
    var t = c ? setTimeout(function () { c.abort(); }, 8000) : 0;
    return fetch(PRICES_URL + '?t=' + Date.now(), { cache: 'no-store', signal: c ? c.signal : undefined })
      .then(function (res) { if (t) clearTimeout(t); if (!res.ok) throw new Error(res.status); return res.json(); })
      .catch(function () { if (t) clearTimeout(t); return null; });
  }

  function refreshLive() {
    if (!packRows.length) return;
    fetchPrices().then(function (prices) {
      pricesFailed = !prices;
      rows = mergeList(packRows, prices);
      indRows = mergeList(packIndicators, prices);
      render();
      notifyChart();
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    fetch('assets/data/screener-pack.json?v=5')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        packRows = data.rows || [];
        packIndicators = data.indicators || [];
        packAsOf = data.asOf || PACK_ASOF;
        return fetchPrices();
      })
      .then(function (prices) {
        pricesFailed = !prices;
        rows = mergeList(packRows, prices);
        indRows = mergeList(packIndicators, prices);
        render();
        notifyChart();
        setInterval(refreshLive, 5 * 60 * 1000);
      })
      .catch(function () {
        var b = document.getElementById('screener-body');
        if (b) b.innerHTML = '<tr><td colspan="5">Screener data could not be loaded.</td></tr>';
        var ib = document.getElementById('indicators-body');
        if (ib) ib.innerHTML = '<tr><td colspan="5">Screener data could not be loaded.</td></tr>';
      });
    var search = document.getElementById('screener-search');
    if (search) search.addEventListener('input', function (e) { state.q = e.target.value; render(); });
    document.querySelectorAll('[data-filter]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.filter = btn.getAttribute('data-filter');
        document.querySelectorAll('[data-filter]').forEach(function (b) { b.classList.toggle('active', b === btn); });
        render();
      });
    });
    document.querySelectorAll('[data-sort]').forEach(function (th) {
      th.addEventListener('click', function () { sortBy(th.getAttribute('data-sort')); });
    });
  });
})();
