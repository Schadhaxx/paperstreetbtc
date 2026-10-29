// Stock Screener — Comparison chart (Maple Leaf Pack)
// Reads values ONLY from assets/data/screener-pack.json (the same file
// the table renders from). No second copy of the numbers lives here,
// no live price API, no other data source.
(function () {
  var chart = null;
  var allRows = [];
  var metric = 'day'; // 'day' = Day change %, 'ytd' = YTD %

  function chartRows() {
    if (metric === 'ytd') return allRows.filter(function (r) { return r.ytdPct !== null && r.ytdPct !== undefined; });
    return allRows.slice();
  }

  function highlightRow(symbol) {
    var tbody = document.getElementById('screener-body');
    if (!tbody) return;
    var found = null;
    tbody.querySelectorAll('tr').forEach(function (tr) {
      tr.classList.remove('row-highlight');
      var first = tr.querySelector('td');
      if (first && first.textContent.trim() === symbol) found = tr;
    });
    if (found) {
      found.classList.add('row-highlight');
      found.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }

  function highlightBar(symbol) {
    if (!chart) return;
    var labels = chart.data.labels || [];
    var idx = labels.indexOf(symbol);
    if (idx === -1) return;
    chart.setActiveElements([{ datasetIndex: 0, index: idx }]);
    chart.update();
  }

  function build() {
    var canvas = document.getElementById('screener-chart');
    if (!canvas || typeof Chart === 'undefined') return;
    var list = chartRows();
    var labels = list.map(function (r) { return r.symbol; });
    var values = list.map(function (r) { return metric === 'ytd' ? r.ytdPct : r.dayChangePct; });
    var colors = values.map(function (v) { return v >= 0 ? '#22c55e' : '#ef4444'; });
    var note = document.getElementById('screener-chart-note');
    if (note) {
      note.textContent = metric === 'ytd'
        ? 'YTD not shown for MU, SPCX, META — no Dec 31 value in the pack.'
        : 'Day change vs the 27 Oct 2026 close.';
    }
    var data = {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderColor: colors,
        borderWidth: 1
      }]
    };
    var options = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: function (items) {
              var r = list[items[0].dataIndex];
              return r.symbol + ' — ' + r.name;
            },
            label: function (item) {
              var v = item.parsed.y;
              return (metric === 'ytd' ? 'YTD: ' : 'Day change: ') + (v > 0 ? '+' : '') + v.toFixed(2) + '%';
            }
          }
        }
      },
      scales: {
        x: { grid: { color: '#1e293b' }, ticks: { color: '#e8eef7' } },
        y: {
          grid: { color: '#1e293b' },
          ticks: { color: '#94a3b8', callback: function (v) { return v + '%'; } }
        }
      },
      onClick: function (_evt, elements) {
        if (elements.length) highlightRow(list[elements[0].index].symbol);
      }
    };
    if (chart) { chart.data = data; chart.options = options; chart.update(); return; }
    chart = new Chart(canvas, { type: 'bar', data: data, options: options });
  }

  document.addEventListener('DOMContentLoaded', function () {
    fetch('assets/data/screener-pack.json')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        allRows = data.rows || [];
        build();
      })
      .catch(function () {
        var note = document.getElementById('screener-chart-note');
        if (note) note.textContent = 'Chart data could not be loaded.';
      });
    document.querySelectorAll('[data-chart-metric]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        metric = btn.getAttribute('data-chart-metric');
        document.querySelectorAll('[data-chart-metric]').forEach(function (b) { b.classList.toggle('active', b === btn); });
        build();
      });
    });
    // Table row click -> highlight the matching bar (delegated, so it
    // survives the table re-rendering on sort/filter).
    var tbody = document.getElementById('screener-body');
    if (tbody) tbody.addEventListener('click', function (e) {
      var tr = e.target.closest ? e.target.closest('tr') : null;
      if (!tr) return;
      var first = tr.querySelector('td');
      if (first) highlightBar(first.textContent.trim());
    });
  });
})();
