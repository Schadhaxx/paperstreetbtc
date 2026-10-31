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
// 10Y <- ^TNX, VIX <- ^VIX, GOLD <- GC=F (COMEX futures)).
// CLOCK SPLIT (30 Oct 2026, Sunil): the two boxes no longer share one
// clock. Stocks are Live only in US stock hours (Mon-Fri 9:30 a.m.-
// 4:00 p.m. ET). Indicators split by instrument: WTI and GOLD (COMEX
// futures) are Live in CME Globex futures hours (Sun 6:00 p.m. ET
// through Fri 5:00 p.m. ET, excluding the daily 5:00-6:00 p.m. ET
// maintenance break); US10Y and VIX stay on stock hours. A row is Live
// only when its own pipeline quote is fresh (<30 min, by that symbol's
// own pipeline timestamp where present, else the file stamp); otherwise
// it shows the latest pipeline value with a dated close label, never
// labelled Live. Each table still has ONE status line below it, and the
// indicators line names which rows are Live and which are dated, so it
// never claims the whole indicators table is Live when it is not.
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
  var noteBySymbol = {};
  var openNotePill = null;
  var openNoteBtn = null;

  function escapeHtml(v) {
    return String(v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function closeNotePill() {
    if (openNotePill && openNotePill.parentNode) openNotePill.parentNode.removeChild(openNotePill);
    openNotePill = null; openNoteBtn = null;
  }
  function toggleNotePill(btn) {
    var symbol = btn.getAttribute('data-symbol');
    var text = noteBySymbol[symbol];
    if (!text) return;
    if (openNoteBtn === btn) { closeNotePill(); return; }
    closeNotePill();
    var pill = document.createElement('div');
    pill.className = 'note-pill';
    pill.setAttribute('role', 'button');
    pill.setAttribute('tabindex', '0');
    pill.setAttribute('aria-label', 'Dismiss note about ' + symbol);
    pill.textContent = text;
    pill.addEventListener('click', function () { closeNotePill(); });
    pill.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); closeNotePill(); } });
    document.body.appendChild(pill);
    var rect = btn.getBoundingClientRect();
    var w = Math.min(320, window.innerWidth - 32);
    var left = Math.max(16, Math.min(rect.left, window.innerWidth - w - 16));
    pill.style.width = w + 'px';
    pill.style.left = left + 'px';
    pill.style.top = (rect.bottom + 6) + 'px';
    openNotePill = pill; openNoteBtn = btn;
  }

  function money(v) {
    if (v === null || v === undefined || typeof v !== 'number' || !isFinite(v)) return '—';
    return (v < 0 ? '-$' : '$') + Math.abs(v).toFixed(2);
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
    return (r.dayChange < 0 ? '-$' : sign + '$') + Math.abs(r.dayChange).toFixed(2) + ' (' + pct(r.dayChangePct) + ')';
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
  // CME Globex futures hours (ET): Sun 6:00 p.m. through Fri 5:00 p.m.,
  // excluding the daily 5:00-6:00 p.m. maintenance break. Saturday is
  // fully closed; Sunday daytime (before 6:00 p.m.) is closed.
  function futuresOpenNow() {
    var p = etParts(new Date());
    var weekday = p.weekday;
    var mins = (+p.hour % 24) * 60 + (+p.minute);
    if (weekday === 'Sat') return false;
    if (weekday === 'Sun') return mins >= 1080;
    if (weekday === 'Fri') return mins < 1020;
    return !(mins >= 1020 && mins < 1080);
  }

  // isLiveFn(r): clock rule for this list's rows. Stocks pass nothing
  // (stock hours for every row); indicators pass a per-symbol split
  // (futures hours for WTI/GOLD, stock hours for US10Y/VIX).
  function mergeList(srcRows, prices, isLiveFn) {
    var out = srcRows.map(function (r) {
      var copy = {};
      Object.keys(r).forEach(function (k) { copy[k] = r[k]; });
      copy._src = 'snapshot';
      copy._closeDate = null;
      return copy;
    });
    if (!prices || !prices.stocks) return out;
    var updated = Date.parse(prices.updated);
    var fileFresh = !isNaN(updated) && (Date.now() - updated) < 30 * 60 * 1000;
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
      // Freshness by the symbol's own pipeline timestamp where present
      // (Finnhub quote time / Yahoo regularMarketTime); otherwise the
      // file stamp. A stale quote never reads Live, even in hours.
      var qt = Number(q.t);
      var fresh = (qt > 0) ? (Date.now() - qt * 1000) < 30 * 60 * 1000 : fileFresh;
      var inHours = isLiveFn ? isLiveFn(r) : marketOpenNow();
      if (fresh && inHours) {
        r._src = 'live';
      } else {
        r._src = 'close';
        // Date the quote itself belongs to, not the file-write date:
        // a morning file carrying yesterday's closes must say yesterday.
        r._closeDate = (qt > 0) ? etDateLabel(new Date(qt * 1000))
          : (!isNaN(updated) ? etDateLabel(new Date(updated)) : fmtIso(packAsOf));
      }
    });
    return out;
  }
  function indicatorLiveFn(r) {
    return (r.symbol === 'WTI' || r.symbol === 'GOLD') ? futuresOpenNow() : marketOpenNow();
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
    if (close.length === list.length) {
      // Dated rows may belong to different dates now (e.g. futures break
      // today vs stock close yesterday): group by close date instead of
      // lumping every dated row under the first row's date.
      var groups = {};
      close.forEach(function (r) { var d = r._closeDate || fmtIso(packAsOf); (groups[d] = groups[d] || []).push(r.symbol); });
      var gs = Object.keys(groups).map(function (d) { return d + ' close for ' + groups[d].join(', '); });
      return gs.join(' · ') + ' — site pipeline, not a live quote.';
    }
    if (snap.length === list.length) return fmtIso(packAsOf) + ' closes from the data pack — not live quotes.';
    var parts = [];
    if (live.length) parts.push('Live for ' + live.join(', '));
    if (close.length) {
      var groups2 = {};
      close.forEach(function (r) { var d = r._closeDate || fmtIso(packAsOf); (groups2[d] = groups2[d] || []).push(r.symbol); });
      Object.keys(groups2).forEach(function (d) { parts.push(d + ' close for ' + groups2[d].join(', ')); });
    }
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

  // JAZZED REDESIGN (30 Oct 2026, from the mockup Sunil approved): the
  // live data, merge, clock split, status lines, pills, search/filter/
  // sort and chart feed are all unchanged — only the presentation
  // changed, from tables to cards (stocks) and KPI tiles (indicators).
  // Cards are iPhone-first (one column at 390px, no horizontal scroll);
  // the move bar shows only the size of today's move, never history.
  // A card gets the 'loser' highlight when its day change is -5% or
  // worse (the mockup's biggest-faller rule, applied to live values).
  function unitLabel(r) {
    if (r.symbol === 'WTI') return '$/barrel';
    if (r.symbol === 'GOLD') return '$/troy oz';
    if (r.symbol === 'US10Y') return '%';
    if (r.symbol === 'VIX') return 'points';
    return '';
  }
  function render() {
    var body = document.getElementById('screener-body');
    if (body) {
      var list = visible();
      noteBySymbol = {};
      var maxAbs = 0;
      list.forEach(function (r) { if (r.dayChangePct !== null && r.dayChangePct !== undefined) maxAbs = Math.max(maxAbs, Math.abs(r.dayChangePct)); });
      body.innerHTML = list.map(function (r) {
        if (r.note) noteBySymbol[r.symbol] = r.note;
        var noteBtn = r.note ? ' <button type="button" class="note-btn" data-symbol="' + escapeHtml(r.symbol) + '" aria-label="More about ' + escapeHtml(r.symbol) + '">+</button>' : '';
        var cls = signCls(r.dayChangePct);
        var barW = maxAbs ? Math.round(Math.abs(r.dayChangePct || 0) / maxAbs * 100) : 0;
        var barCol = cls === 'up' ? '#22c55e' : (cls === 'down' ? '#ef4444' : '#94a3b8');
        return '<article class="card' + ((r.dayChangePct !== null && r.dayChangePct !== undefined && r.dayChangePct <= -5) ? ' loser' : '') + '" data-symbol="' + escapeHtml(r.symbol) + '">'
          + '<div class="top"><div><div class="sym">' + escapeHtml(r.symbol) + '</div><div class="nm">' + escapeHtml(r.name) + noteBtn + '</div></div>'
          + '<div><div class="price">' + money(r.price) + '</div><span class="day-pill ' + cls + '">' + dayText(r) + '</span></div></div>'
          + '<div class="meta"><span class="ytd">' + (r.ytdBasis === 'listing' ? 'Since listing' : 'YTD') + ' <b class="' + signCls(r.ytdPct) + '">' + pct(r.ytdPct) + '</b>'
          + (r.ytdBasis === 'listing' ? '<div class="row-note">Since listing 12 Jun 2026</div>' : '') + '</span>'
          + '<span class="move">Day move only <span class="bar"><i style="width:' + barW + '%;background:' + barCol + '"></i></span></span></div></article>';
      }).join('');
      var count = document.getElementById('screener-count');
      if (count) count.textContent = list.length + ' of ' + rows.length + ' shown';
    }
    var itbody = document.getElementById('indicators-body');
    if (itbody) {
      itbody.innerHTML = indRows.map(function (r) {
        if (r.note) noteBySymbol[r.symbol] = r.note;
        var noteBtn = r.note ? ' <button type="button" class="note-btn" data-symbol="' + escapeHtml(r.symbol) + '" aria-label="More about ' + escapeHtml(r.symbol) + '">+</button>' : '';
        var cls = signCls(r.dayChangePct);
        return '<div class="tile" data-symbol="' + escapeHtml(r.symbol) + '"><div class="k">' + escapeHtml(r.name) + ' · ' + unitLabel(r) + '</div>'
          + '<div class="v">' + formatValue(r) + '</div><div class="d ' + cls + '">' + dayText(r) + '</div>'
          + '<div class="u">' + unitLabel(r) + ' ' + noteBtn + '</div></div>';
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
      indRows = mergeList(packIndicators, prices, indicatorLiveFn);
      render();
      notifyChart();
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    fetch('assets/data/screener-pack.json?v=8')
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
        indRows = mergeList(packIndicators, prices, indicatorLiveFn);
        render();
        notifyChart();
        setInterval(refreshLive, 5 * 60 * 1000);
      })
      .catch(function () {
        var b = document.getElementById('screener-body');
        if (b) b.innerHTML = '<tr><td colspan="5">Screener data could not be loaded.</td></tr>';
        var ib = document.getElementById('indicators-body');
        if (ib) ib.innerHTML = '<tr><td colspan="4">Screener data could not be loaded.</td></tr>';
      });
    document.addEventListener('click', function (e) {
      var btn = e.target.closest ? e.target.closest('.note-btn') : null;
      if (btn) { toggleNotePill(btn); return; }
      if (openNotePill && !(e.target.closest && e.target.closest('.note-pill'))) closeNotePill();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeNotePill();
    });
    window.addEventListener('scroll', closeNotePill, true);
    window.addEventListener('resize', closeNotePill);
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
      th.addEventListener('click', function () {
        document.querySelectorAll('[data-sort]').forEach(function (b) { b.classList.toggle('active', b === th); });
        sortBy(th.getAttribute('data-sort'));
      });
    });
  });
})();
