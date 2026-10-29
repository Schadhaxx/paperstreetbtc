// Stock Screener — Maple Leaf Pack
// Renders the table from assets/data/screener-pack.json, then overlays
// genuinely live pipeline quotes on top of it for the symbols the site's
// own pipeline covers (TSLA, PLTR, MSTR, IBIT — see PRICES_URL).
// Live source = the same data-branch prices.json the main site reads
// (GitHub Actions writes it every ~5 min on weekdays from Finnhub,
// server-side; visitors never call the quote API and no key is in here).
// Symbols with no pipeline quote (MU, SPCX, META) keep their pack value
// and are labelled with that close's date — never "Live".
// No buy/sell action.
(function () {
  var PRICES_URL = 'https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/prices.json';
  var PACK_ASOF = '2026-10-28';
  var state = { q: '', filter: 'all', sortKey: 'symbol', sortDir: 1 };
  var packRows = [];
  var packAsOf = PACK_ASOF;
  var rows = [];

  function money(v) {
    return v === null || v === undefined ? '—' : '$' + v.toFixed(2);
  }
  function pct(v) {
    if (v === null || v === undefined) return 'n/a';
    return (v > 0 ? '+' : '') + v.toFixed(2) + '%';
  }
  function dayText(r) {
    if (r.dayChange === null || r.dayChange === undefined) return '—';
    var sign = r.dayChange > 0 ? '+' : '';
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

  function mergeLive(prices) {
    var out = packRows.map(function (r) {
      var copy = {};
      Object.keys(r).forEach(function (k) { copy[k] = r[k]; });
      copy.status = fmtIso(packAsOf) + ' close';
      copy._src = 'snapshot';
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
        r.status = 'Live';
        r._src = 'live';
      } else {
        r.status = (!isNaN(updated) ? etDateLabel(new Date(updated)) : fmtIso(packAsOf)) + ' close';
        r._src = 'close';
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

  function updateAsof() {
    var el = document.getElementById('screener-asof');
    if (!el) return;
    var liveSyms = rows.filter(function (r) { return r._src === 'live'; }).map(function (r) { return r.symbol; });
    var snapSyms = rows.filter(function (r) { return r._src === 'snapshot'; }).map(function (r) { return r.symbol; });
    if (liveSyms.length) {
      el.textContent = 'Live for ' + liveSyms.join(', ') + ' (site pipeline, market hours)'
        + (snapSyms.length ? ' · ' + fmtIso(packAsOf) + ' closes for ' + snapSyms.join(', ') + ' (no pipeline quote — see Status column).' : '.');
    } else {
      el.textContent = 'Pipeline quotes unavailable on this load — rows show their latest close (see Status column).';
    }
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
    if (gv && gainer) gv.textContent = gainer.symbol + ' ' + pct(gainer.dayChangePct);
    if (lv && loser) lv.textContent = loser.symbol + ' ' + pct(loser.dayChangePct);
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
    if (!tbody) return;
    var list = visible();
    tbody.innerHTML = list.map(function (r) {
      var cls = r.dayChangePct > 0 ? 'up' : (r.dayChangePct < 0 ? 'down' : '');
      var note = r.note ? '<div class="row-note">' + r.note + '</div>' : '';
      return '<tr><td><strong>' + r.symbol + '</strong></td><td>' + r.name + note + '</td>'
        + '<td>' + money(r.price) + '</td>'
        + '<td class="' + cls + '">' + dayText(r) + '</td>'
        + '<td class="' + cls + '">' + pct(r.ytdPct) + '</td>'
        + '<td>' + r.status + '</td></tr>';
    }).join('');
    document.getElementById('screener-count').textContent = list.length + ' of ' + rows.length + ' shown';
    updatePills();
    updateAsof();
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
      rows = mergeLive(prices);
      render();
      notifyChart();
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    fetch('assets/data/screener-pack.json?v=3')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        packRows = data.rows || [];
        packAsOf = data.asOf || PACK_ASOF;
        return fetchPrices();
      })
      .then(function (prices) {
        rows = mergeLive(prices);
        render();
        notifyChart();
        setInterval(refreshLive, 5 * 60 * 1000);
      })
      .catch(function () {
        document.getElementById('screener-body').innerHTML =
          '<tr><td colspan="6">Screener data could not be loaded.</td></tr>';
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
