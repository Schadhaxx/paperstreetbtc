// Stock Screener — Maple Leaf Pack
// Renders the table from assets/data/screener-pack.json ONLY.
// No live price API, no other data source, no buy/sell action.
(function () {
  var state = { q: '', filter: 'all', sortKey: 'symbol', sortDir: 1 };
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
      // Rows with no price sort last on price sorts.
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
  }

  function sortBy(key) {
    if (state.sortKey === key) state.sortDir = -state.sortDir;
    else { state.sortKey = key; state.sortDir = key === 'symbol' ? 1 : -1; }
    render();
  }

  document.addEventListener('DOMContentLoaded', function () {
    fetch('assets/data/screener-pack.json?v=2')
      .then(function (res) { return res.json(); })
      .then(function (data) { rows = data.rows || []; render(); })
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
