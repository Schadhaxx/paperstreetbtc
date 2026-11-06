/* Pre-computed stats display (Python supercharge, slice 3 — proposal).
   The numbers come from stats.json on the data branch, pre-computed by
   tools/stats.py. This file only DISPLAYS them; it never re-derives a
   stat in JS. If the fetch fails (stats.json is not published yet) the
   section stays hidden. PSStats.render(S) is pure — it takes the stats
   object and returns the HTML string — so it can be tested without a
   browser. */
window.PSStats = (function () {
  var ORDER = ['berkshire', 'hodlr', 'hf', 'saylor',
               'btc', 'spy', 'qqq', 'brk', 'mstr', 'gold'];
  var NAMES = {berkshire: 'Berkshire Killer', hodlr: 'Hodler Jam Sandwich',
    hf: 'Hedge Fund Killer', saylor: 'Saylor Moon', btc: 'Spot BTC',
    spy: 'S&P 500', qqq: 'QQQ', brk: 'Berkshire', mstr: 'MSTR', gold: 'Gold'};
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function pc(x) {
    if (x == null || !isFinite(x)) return '—';
    return (x >= 0 ? '+' : '') + x.toFixed(2) + '%';
  }
  function usd(x) {
    if (x == null || !isFinite(x)) return '—';
    return (x < 0 ? '-$' : '$') + Math.abs(x).toLocaleString('en-US',
      {maximumFractionDigits: 0});
  }
  function usd2(x) {
    if (x == null || !isFinite(x)) return '—';
    return '$' + x.toFixed(2);
  }
  function cls(x) { return x == null ? '' : (x >= 0 ? 'pos' : 'neg'); }
  function mon(d) { // '2026-11-05' -> 'Nov 5'
    var M = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep',
      'Oct', 'Nov', 'Dec'];
    var p = d.split('-');
    return M[+p[1] - 1] + ' ' + (+p[2]);
  }
  function monShort(mo) { // '2026-11' -> 'Nov'
    var M = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep',
      'Oct', 'Nov', 'Dec'];
    return M[+mo.slice(5, 7) - 1];
  }
  function render(S) {
    if (!S || !S.series) return '';
    var h = '';
    // badges, only when one is active
    if (S.badges && S.badges.length) {
      h += '<p class="pv-stats-badges">' + S.badges.map(function (b) {
        return '<span class="pv-badge">' + esc(b.text) + ' · ' +
          esc(mon(b.date)) + '</span>';
      }).join(' ') + '</p>';
    }
    // summary table: sleeves, then benchmarks
    h += '<div class="pv-stats-scroll"><table class="pv-stats"><thead><tr>' +
      '<th>Series</th><th>YTD</th><th>' + esc(monShort(S.series.berkshire.mtd_month)) +
      '</th><th>Best day</th><th>Worst day</th><th>Drawdown</th><th>Vol</th>' +
      '</tr></thead><tbody>';
    ORDER.forEach(function (k) {
      var s = S.series[k];
      if (!s) return;
      h += '<tr><td class="pv-sname">' + esc(s.name || NAMES[k] || k) + '</td>' +
        '<td class="' + cls(s.ytd_pct) + '">' + pc(s.ytd_pct) + '</td>' +
        '<td class="' + cls(s.mtd_pct) + '">' + pc(s.mtd_pct) + '</td>' +
        '<td>' + (s.best_day ? '<span class="pos">' + pc(s.best_day.pct) +
          '</span> <span class="note">' + esc(mon(s.best_day.date)) + '</span>' : '—') + '</td>' +
        '<td>' + (s.worst_day ? '<span class="neg">' + pc(s.worst_day.pct) +
          '</span> <span class="note">' + esc(mon(s.worst_day.date)) + '</span>' : '—') + '</td>' +
        '<td class="' + cls(s.drawdown_pct) + '">' + pc(s.drawdown_pct) + '</td>' +
        '<td>' + pc(s.vol_ann_pct) + '</td></tr>';
    });
    h += '</tbody></table></div>';
    h += '<p class="note">Pre-computed from the daily closes — YTD and ' +
      esc(monShort(S.series.berkshire.mtd_month)) +
      ' are % change from the 31 Dec 2025 close; drawdown is vs the peak; ' +
      'vol is annualised daily volatility. Benchmarks are indexed to 100.</p>';
    // monthly returns, sleeves only
    var months = Object.keys(S.series.berkshire.monthly || {}).sort();
    if (months.length) {
      h += '<div class="pv-stats-scroll"><table class="pv-stats"><thead><tr>' +
        '<th>Month</th><th>Berkshire</th><th>Hodler</th><th>HF</th>' +
        '<th>Saylor</th></tr></thead><tbody>';
      months.forEach(function (mo) {
        var isMtd = mo === S.as_of.slice(0, 7);
        h += '<tr><td>' + esc(monShort(mo)) + (isMtd ? ' *' : '') + '</td>';
        ['berkshire', 'hodlr', 'hf', 'saylor'].forEach(function (k) {
          var v = S.series[k] && S.series[k].monthly[mo];
          h += '<td class="' + cls(v) + '">' + pc(v) + '</td>';
        });
        h += '</tr>';
      });
      h += '</tbody></table></div>';
      h += '<p class="note">* ' + esc(monShort(S.as_of.slice(0, 7))) +
        ' is month-to-date through ' + esc(mon(S.as_of)) + '.</p>';
    }
    // Pulse context, per sleeve
    if (S.pulse) {
      h += '<p class="pv-pulse-ctx">';
      h += ['berkshire', 'hodlr', 'hf', 'saylor'].map(function (k) {
        var p = S.pulse[k];
        if (!p) return '';
        var start = p.above_start >= 0
          ? usd(p.above_start) + ' above the Jan 1 start'
          : usd(-p.above_start) + ' below the Jan 1 start';
        var peak = p.below_peak <= 0.005
          ? 'at its peak'
          : usd(p.below_peak) + ' below its peak (' + usd(p.peak_value) +
            ' on ' + esc(mon(p.peak_date)) + ')';
        return '<strong>' + esc(NAMES[k]) + ':</strong> ' + usd(p.value) +
          ' today, ' + start + ', ' + peak + '.';
      }).filter(Boolean).join('<br>');
      h += '</p>';
    }
    // dividend calendar: next payment + the month total
    if (S.dividends && S.dividends.upcoming && S.dividends.upcoming.length) {
      var nx = S.dividends.upcoming[0];
      var mo = nx.record.slice(0, 7);
      var mt = S.dividends.month_totals && S.dividends.month_totals[mo];
      h += '<p class="pv-div-cal"><strong>Next STRC payment:</strong> ' +
        esc(mon(nx.pay)) + ' — $' + (+nx.per_share).toFixed(4) + '/share' +
        ' (Berkshire ' + usd2(nx.cash.berkshire) + ' · Hodler ' +
        usd2(nx.cash.hodlr) + ' · HF ' + usd2(nx.cash.hf) + ' · Saylor ' +
        usd2(nx.cash.saylor) + '). ' +
        S.dividends.upcoming.length + ' daily payments left in ' +
        esc(monShort(mo)) +
        (mt ? ' — ' + esc(monShort(mo)) + ' total $' +
          mt.per_share.toFixed(2) + '/share declared.' : '') + '</p>';
    }
    // CSV export
    h += '<p class="note"><a href="https://raw.githubusercontent.com/' +
      'Schadhaxx/paperstreetbtc/data/history.csv">Download the full ' +
      'history as CSV</a> (daily closes, 31 Dec 2025 to ' +
      esc(mon(S.as_of)) + ').</p>';
    return h;
  }
  // loader: fetch stats.json from the data branch; stay hidden on failure.
  function load() {
    var el = document.getElementById('pvStats');
    if (!el) return;
    fetch('https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/' +
      'stats.json?t=' + Date.now(), {cache: 'no-store'})
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (S) {
        var html = render(S);
        if (html) el.innerHTML = html;
      })
      .catch(function () { /* stats not published yet: leave hidden */ });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else { load(); }
  return {render: render, load: load};
})();
