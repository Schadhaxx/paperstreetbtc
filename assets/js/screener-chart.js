// Stock Screener — Comparison chart (Maple Leaf Pack), STOCKS ONLY.
// Reads values ONLY from the merged stock rows screener.js hands it
// (pack + live pipeline quotes, via ScreenerChartUpdate / 'screener-rows').
// No second copy of the numbers lives here, no separate pack fetch,
// no live price API of its own, no other data source.
// Market Indicators are deliberately NOT charted here: dollars, %,
// and VIX points do not share an axis, so charting them together would
// imply comparability that does not exist.
// Signed-number colours (Sunil's rule): positive green #22c55e,
// negative red #ef4444, signed zero black #000000. NOTE: pure black on
// this dark chart card is near-invisible — flagged in the delivery
// report; applied literally here, not silently replaced.
(function () {
  var chart = null;
  var allRows = [];
  var metric = 'day'; // 'day' = Day change %, 'ytd' = YTD %

  function chartRows() {
    if (metric === 'ytd') return allRows.filter(function (r) { return r.ytdPct !== null && r.ytdPct !== undefined && r.ytdBasis !== 'listing'; });
    return allRows.slice();
  }

  // Cards, not table rows, since the 30 Oct jazzed redesign: highlight
  // the stock card with the matching data-symbol.
  function highlightRow(symbol) {
    var body = document.getElementById('screener-body');
    if (!body) return;
    var found = null;
    body.querySelectorAll('.card').forEach(function (card) {
      card.classList.remove('row-highlight');
      if (card.getAttribute('data-symbol') === symbol) found = card;
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
    var colors = values.map(function (v) { return v > 0 ? '#22c55e' : (v < 0 ? '#ef4444' : '#000000'); });
    var note = document.getElementById('screener-chart-note');
    if (note) {
      note.textContent = metric === 'ytd'
        ? 'YTD vs 31 Dec 2025 (META $660.09, MU $285.41 added 29 Oct 2026). SPCX is not in this YTD chart — its table figure is return since its 12 Jun 2026 first close ($160.95), not YTD. Market Indicators are not charted here — dollars, %, and VIX points do not share an axis.'
        : "Day change vs each stock's prior close (live rows vs the prior session close; snapshot rows vs 27 Oct 2026). Market Indicators are not charted here — dollars, %, and VIX points do not share an axis.";
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

  // Single source of truth: screener.js merges pack + live quotes and
  // hands the merged rows here. No independent pack fetch, so the chart
  // can never show different numbers from the table.
  window.ScreenerChartUpdate = function (rows) {
    allRows = rows || [];
    build();
  };
  window.addEventListener('screener-rows', function (e) {
    allRows = (e && e.detail) || [];
    build();
  });
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-chart-metric]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        metric = btn.getAttribute('data-chart-metric');
        document.querySelectorAll('[data-chart-metric]').forEach(function (b) { b.classList.toggle('active', b === btn); });
        build();
      });
    });
    // Stock card click -> highlight the matching bar (delegated, so it
    // survives the card re-rendering on sort/filter). A tap on a card's
    // "+" note button is a note, not a chart highlight.
    var body = document.getElementById('screener-body');
    if (body) body.addEventListener('click', function (e) {
      if (e.target.closest && e.target.closest('.note-btn')) return;
      var card = e.target.closest ? e.target.closest('.card') : null;
      if (!card) return;
      var sym = card.getAttribute('data-symbol');
      if (sym) highlightBar(sym);
    });
  });
})();
