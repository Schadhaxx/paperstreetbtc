// Stock Screener — Maple Leaf Pack
// Two boxes, one page: Stocks (16 rows) and Market Indicators (WTI, Gold,
// 10-Year, VIX, DIA, QQQ, USDCAD, DXY). Each box has its own table and ONE status
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
// HOLIDAY / EARLY-CLOSE (23 Nov 2026): marketOpenNow() is holiday- and
// early-close-aware via et.js (ET.session / ET.closeMin) — on a NYSE
// holiday there is no session, and on an early-close day the session
// ends at 1:00 PM ET, so a stale holiday quote stamped fresh by the
// pipeline cannot read Live. futuresOpenNow() likewise closes on the
// CME Globex full closures (New Year's Day, Good Friday, Thanksgiving,
// Christmas) — on other NYSE holidays Globex energy/metals still trade.
// A quote with a missing, zero, or implausible timestamp can never
// read Live (see mergeList).
// Signed-number colours (Sunil's rule): positive green #22c55e,
// negative red #ef4444, signed zero the muted text colour (.flat) —
// pure black was the original rule, but it is invisible on this page's
// dark background (#070b18 / #121a2e), so dark mode uses the visible
// muted grey; light mode uses near-black #0f172a (light.css). 'n/a' is
// not a signed number, so it keeps the default light text, not black.
// No buy/sell action.
(function () {
  // Scroll restoration (25 Nov 2026, Sunil): own the scroll position
  // across tab eviction instead of relying on the browser's default
  // restore, which saved whatever drifted spot the page had reached
  // (chart / heat map) and put Sunil there on return. 'manual' so the
  // browser does not fight the restore below; if nothing is saved the
  // page simply stays at the top — never the bottom.
  if ('scrollRestoration' in history) { try { history.scrollRestoration = 'manual'; } catch (e) {} }
  var SCROLL_KEY = 'ps-desk-scroll-y';
  var userMoved = false, restoreAt = 0;
  // Read the saved offset ONCE at load. Every restore in this page
  // uses this value: re-reading sessionStorage would pick up a clamped
  // restore position the saver wrote in the meantime. (First version
  // re-read on every restore and the load-time restore clobbered the
  // good value with its own clamped one — see the load listener note
  // below, removed for the same reason.)
  var savedScrollY = null;
  try {
    var _raw = sessionStorage.getItem(SCROLL_KEY);
    var _y = (_raw === null || _raw === '') ? NaN : parseInt(_raw, 10);
    if (!isNaN(_y) && _y > 0) savedScrollY = _y;
  } catch (e) {}
  function modalOpen() {
    var m = document.getElementById('ind-modal');
    return !!(m && m.classList.contains('open'));
  }
  function saveScrollY() {
    // Never save while the chart modal is open: the body is locked
    // then, so scrollY reads 0 and would clobber the real position
    // (the modal saves the pre-modal position itself on open).
    // Also never save within 500ms of a restore: the restore's own
    // scroll event would otherwise write the restored (possibly
    // clamped) position over the user's real one.
    if (modalOpen() || (restoreAt && Date.now() - restoreAt < 500)) return;
    try { sessionStorage.setItem(SCROLL_KEY, String(window.scrollY || window.pageYOffset || 0)); } catch (e) {}
  }
  function restoreScrollY() {
    if (savedScrollY === null) return false;
    var max = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    if (max <= 0) return false;
    restoreAt = Date.now();
    window.scrollTo(0, Math.min(savedScrollY, max));
    return true;
  }
  var PRICES_URL = 'https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/prices.json';
  // CF-3 (Cloudflare Worker, Nov 2026): the Desk pills/tiles take
  // their live quotes from the Cloudflare live-quote Worker first
  // (near-1-min Finnhub quotes, cached ~55s server-side), falling
  // back silently to prices.json per symbol. The Worker covers 18 of
  // the 24 Desk symbols; WTI, GOLD, US10Y, VIX, DXY, USDCAD are not
  // on Finnhub's free /quote endpoint and always come from prices.json.
  // The Worker URL is a single configurable constant.
  var WORKER_URL = 'https://paperstreet-quotes.schadha08.workers.dev/';
  var PACK_ASOF = '2026-11-23';
  var state = { q: '', filter: 'all', sortKey: 'symbol', sortDir: 1 };
  var packRows = [];
  var packIndicators = [];
  var packAsOf = PACK_ASOF;
  var rows = [];
  // Icon-only chart cue (same ↗ SVG as the BTC pill's lp-cv chip in
  // btcchart.js, sized 16px via CSS, cyan). No "Chart" text. Used on the
  // indicator tiles (bottom-right corner) and the stock cards (in place
  // of the removed "Day move only" bar).
  var CHART_ICON = '<svg viewBox="0 0 14 14" fill="none" aria-hidden="true"><path d="M2 10.5L5 7L8 8.5L12 3.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="3.5" r="1.4" fill="currentColor"/></svg>';
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
    if (r.unit === 'fx') return v.toFixed(4);
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
    if (r.unit === 'fx') return sign + r.dayChange.toFixed(4) + ' (' + pct(r.dayChangePct) + ')';
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
    // Holiday / early-close aware (et.js, loaded on this page): on a
    // NYSE holiday there is no session at all, and on an early-close day
    // (e.g. Fri 27 Nov 2026, 1:00 PM ET) the session ends at 780 min.
    // Without this, a stale holiday quote stamped fresh by the pipeline
    // reads Live. Falls back to the plain 9:30-4:00 window if ET is
    // unavailable (script load failure), so the page never breaks.
    if (window.ET && window.ET.today && window.ET.closeMin) {
      var close = window.ET.closeMin(window.ET.today());
      if (!close) return false;
      return mins >= 570 && mins < close;
    }
    return mins >= 570 && mins < 960;
  }
  // CME Globex full closures for energy/metals (WTI/GOLD): the Globex
  // session is closed all day on New Year's Day, Good Friday,
  // Thanksgiving and Christmas Day. On other NYSE holidays (e.g. MLK
  // Day, Presidents Day) Globex energy/metals DO trade, so only these
  // four dates per year close the futures window. Same dates as the
  // NYSE list in et.js (HOL); keep in sync when that list extends.
  // (2027-12-25 and 2028-01-01 are Saturdays, covered by the weekend
  // check; 2027-12-24 is a CME early close, not a full closure — the
  // 30-min freshness gate marks it dated after the last quote ages.)
  var CME_CLOSED = {
    '2026-01-01': 1, '2026-04-03': 1, '2026-11-26': 1, '2026-12-25': 1,
    '2027-01-01': 1, '2027-03-26': 1, '2027-11-25': 1, '2027-12-25': 1,
    '2028-04-14': 1, '2028-11-23': 1, '2028-12-25': 1
  };
  // CME Globex futures hours (ET): Sun 6:00 p.m. through Fri 5:00 p.m.,
  // excluding the daily 5:00-6:00 p.m. maintenance break. Saturday is
  // fully closed; Sunday daytime (before 6:00 p.m.) is closed.
  function futuresOpenNow() {
    var p = etParts(new Date());
    var weekday = p.weekday;
    var mins = (+p.hour % 24) * 60 + (+p.minute);
    if (weekday === 'Sat') return false;
    // Globex is closed all day on the CME full closures (above) — a
    // holiday quote stamped fresh by the pipeline must not read Live.
    if (window.ET && window.ET.today && CME_CLOSED[window.ET.today()]) return false;
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
    // (No fileFresh fallback for Live: a fresh file stamp says nothing
    // about this symbol's quote — see the qtValid note below.)
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
      // A quote with a missing, zero, or implausible timestamp can
      // never read Live: the file stamp is NOT a fallback for Live
      // (prices.yml refreshes `updated` on every run, even one where
      // every fetch failed, so a fresh file says nothing about this
      // symbol's quote). A millisecond timestamp is rejected too — a
      // seconds value times 1000 would land far in the future and read
      // Live forever. An invalid timestamp falls through to 'close'
      // with the file's date, never to Live.
      var qt = Number(q.t);
      var qtValid = (qt > 0 && qt < 1e11);
      var fresh = qtValid ? (Date.now() - qt * 1000) < 30 * 60 * 1000 : false;
      var inHours = isLiveFn ? isLiveFn(r) : marketOpenNow();
      if (fresh && inHours) {
        r._src = 'live';
      } else {
        r._src = 'close';
        // Date the quote itself belongs to, not the file-write date:
        // a morning file carrying yesterday's closes must say yesterday.
        r._closeDate = qtValid ? etDateLabel(new Date(qt * 1000))
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
      // Live-feel (experimental): the candle modal also needs the
      // indicator rows (their _src live/close verdicts), which the stock
      // event above does not carry. indRows is built by mergeList with
      // the same freshness/market-hours gate (indicatorLiveFn), so this
      // dispatch carries the gated rows, not raw quotes.
      window.dispatchEvent(new CustomEvent('screener-ind-rows', { detail: indRows }));
    }
  }

  function statusLine(list) {
    if (pricesFailed) return 'Pipeline quotes unavailable on this load — rows show their ' + fmtIso(packAsOf) + ' closes, not live quotes.';
    var live = list.filter(function (r) { return r._src === 'live'; }).map(function (r) { return r.symbol; });
    var close = list.filter(function (r) { return r._src === 'close'; });
    var snap = list.filter(function (r) { return r._src === 'snapshot'; }).map(function (r) { return r.symbol; });
    if (list.length && live.length === list.length) return 'Live — site pipeline, market hours.';
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
      if (bv === null || bv === undefined) return -1;
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
    if (r.symbol === 'DIA') return 'USD';
    if (r.symbol === 'QQQ') return 'USD';
    if (r.symbol === 'USDCAD') return 'USD per CAD';
    if (r.symbol === 'DXY') return 'points';
    return '';
  }
  function render() {
    var body = document.getElementById('screener-body');
    if (body) {
      var list = visible();
      noteBySymbol = {};
      body.innerHTML = list.map(function (r) {
        if (r.note) noteBySymbol[r.symbol] = r.note;
        var noteBtn = r.note ? ' <button type="button" class="note-btn" data-symbol="' + escapeHtml(r.symbol) + '" aria-label="More about ' + escapeHtml(r.symbol) + '">+</button>' : '';
        var cls = signCls(r.dayChangePct);
        var chartLabel = (r.ytdBasis === 'listing')
          ? ('Open ' + r.symbol + ' chart since listing')
          : ('Open ' + r.symbol + ' YTD chart');
        return '<article class="card' + ((r.dayChangePct !== null && r.dayChangePct !== undefined && r.dayChangePct <= -5) ? ' loser' : '') + '" data-symbol="' + escapeHtml(r.symbol) + '" tabindex="0" aria-label="' + escapeHtml(chartLabel) + '">'
          + '<div class="top"><div><div class="sym">' + escapeHtml(r.symbol) + '</div><div class="nm">' + escapeHtml(r.name) + noteBtn + '</div></div>'
          + '<div><div class="price">' + money(r.price) + '</div><span class="day-pill ' + cls + '">' + dayText(r) + '</span></div></div>'
          + '<div class="meta"><span class="ytd">' + (r.ytdBasis === 'listing' ? 'Since listing' : 'YTD') + ' <b class="' + signCls(r.ytdPct) + '">' + pct(r.ytdPct) + '</b>'
          + (r.ytdBasis === 'listing' ? '<div class="row-note">Since listing 12 Jun 2026</div>' : '') + '</span>'
          + '<span class="card-chart" aria-hidden="true">' + CHART_ICON + '</span></div></article>';
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
        return '<div class="tile" data-symbol="' + escapeHtml(r.symbol) + '" tabindex="0" role="button" aria-label="Open ' + escapeHtml(r.name) + ' chart"><div class="k">' + escapeHtml(r.name) + ' · ' + unitLabel(r) + '</div>'
          + '<div class="v">' + formatValue(r) + '</div><div class="d ' + cls + '">' + dayText(r) + '</div>'
          + '<div class="u">' + noteBtn + '</div>'
          + '<span class="tile-chart" aria-hidden="true">' + CHART_ICON + '</span></div>';
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

  // CF-3: Worker fetch (same 8s abort as fetchPrices). Any failure —
  // network, HTTP error, bad JSON — is null; the caller falls back
  // to prices.json for every symbol.
  function fetchWorker() {
    var c = window.AbortController ? new AbortController() : null;
    var t = c ? setTimeout(function () { c.abort(); }, 8000) : 0;
    return fetch(WORKER_URL, { cache: 'no-store', signal: c ? c.signal : undefined })
      .then(function (res) { if (t) clearTimeout(t); if (!res.ok) throw new Error(res.status); return res.json(); })
      .catch(function () { if (t) clearTimeout(t); return null; });
  }
  // Build the effective prices-shaped object the merge below reads:
  // Worker entries win per symbol, but only when they carry a usable
  // c + pc; prices.json fills every gap, including the 5 symbols the
  // Worker never serves (WTI, GOLD, US10Y, VIX, DXY) and any symbol
  // the Worker omits (e.g. USDCAD if OANDA:USD_CAD returns nothing
  // live). `updated` is the newer of the two sources, for the
  // file-freshness fallback in mergeList when a quote has no t.
  function mergeQuotes(worker, prices) {
    var stocks = {};
    if (prices && prices.stocks && typeof prices.stocks === 'object') {
      Object.keys(prices.stocks).forEach(function (k) { stocks[k] = prices.stocks[k]; });
    }
    var wAsOf = NaN;
    if (worker && worker.stocks && typeof worker.stocks === 'object') {
      Object.keys(worker.stocks).forEach(function (k) {
        var q = worker.stocks[k];
        if (q && typeof q.c === 'number' && q.c > 0 && typeof q.pc === 'number' && q.pc > 0) stocks[k] = q;
      });
      if (typeof worker.asOf === 'string') wAsOf = Date.parse(worker.asOf);
    }
    var updated = (prices && typeof prices.updated === 'string') ? prices.updated : null;
    if (!isNaN(wAsOf) && (!updated || Date.parse(updated) < wAsOf)) updated = new Date(wAsOf).toISOString();
    return { updated: updated, stocks: stocks };
  }
  function hasQuotes(eff) {
    return !!(eff && eff.stocks && typeof eff.stocks === 'object' && Object.keys(eff.stocks).length > 0);
  }

  function refreshLive() {
    if (!packRows.length) return;
    Promise.all([fetchWorker(), fetchPrices()]).then(function (pair) {
      var eff = mergeQuotes(pair[0], pair[1]);
      pricesFailed = !hasQuotes(eff);
      rows = mergeList(packRows, eff);
      indRows = mergeList(packIndicators, eff, indicatorLiveFn);
      setSpyBridge(eff);
      render();
      notifyChart();
      // The comparison chart's desk-live/Worker today-point is fetched
      // once at load; re-fetch it on the same 5-min tick so the point
      // does not go stale ~20 min after load while the cards keep
      // refreshing. No-op if the chart script is not on the page.
      if (typeof window.ScreenerChartRefreshDeskLive === 'function') window.ScreenerChartRefreshDeskLive();
    });
  }

  // SPY bridge for the comparison chart: SPY is a benchmark, not a
  // Desk card row, so the chart cannot read it from `rows`. Stash the
  // merged Finnhub quote here (refreshed every 5 min) for the chart's
  // today-point. The chart checks the quote's own freshness before
  // using it, so a stale bridge never becomes a point.
  function setSpyBridge(eff) {
    var spyQ = eff && eff.stocks && eff.stocks['SPY'];
    window.__psSpy = (spyQ && typeof spyQ.c === 'number' && spyQ.c > 0) ? { c: spyQ.c, t: spyQ.t } : null;
  }

  document.addEventListener('DOMContentLoaded', function () {
    fetch('assets/data/screener-pack.json?v=dia3')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        packRows = data.rows || [];
        packIndicators = data.indicators || [];
        packAsOf = data.asOf || PACK_ASOF;
        return Promise.all([fetchWorker(), fetchPrices()]);
      })
      .then(function (pair) {
        var eff = mergeQuotes(pair[0], pair[1]);
        pricesFailed = !hasQuotes(eff);
        rows = mergeList(packRows, eff);
        indRows = mergeList(packIndicators, eff, indicatorLiveFn);
        setSpyBridge(eff);
        render();
        notifyChart();
        // First render populated the tile grids, so the document is
        // near full height: restore the saved scroll position now.
        // This runs once — a later render() (e.g. the 5-min refresh)
        // must never yank the page.
        restoreScrollY();
        // Second attempt: the comparison-chart section populates after
        // this render (cmp-daily fetch), so the document can still grow
        // after the first restore clamped to the then-max. Re-apply the
        // saved offset once the page is full height — but only if the
        // user has not moved it themselves. Deliberately a timer after
        // the first render, NOT a load listener: load fires before the
        // first render (subresources finish before the data fetches do),
        // so a load-time restore clamped to the short document and the
        // saver then clobbered the good value with it. Once Friday's
        // CLS fix reserves the grid heights, the first restore is
        // already against the full height and this is a no-op.
        setTimeout(function () { if (!userMoved) restoreScrollY(); }, 2000);
        setInterval(refreshLive, 5 * 60 * 1000);
        // Tab return: the chart's today-point goes stale after ~20 min
        // (desk-live/Worker freshness), so re-fetch it when the tab
        // becomes visible again instead of waiting for the next 5-min
        // tick. The cards refresh on the interval; this covers the chart.
        document.addEventListener('visibilitychange', function () {
          if (!document.hidden && typeof window.ScreenerChartRefreshDeskLive === 'function') window.ScreenerChartRefreshDeskLive();
        });
      })
      .catch(function () {
        var b = document.getElementById('screener-body');
        if (b) b.innerHTML = '<p>Screener data could not be loaded.</p>'; /* Batch B finding 7: <tr> in a <div> is dropped by the browser */
        var ib = document.getElementById('indicators-body');
        if (ib) ib.innerHTML = '<p>Screener data could not be loaded.</p>';
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
    /* Batch B bug 5 (revised 24 Nov 2026): the floating 'Live BTC Chart'
       pill overlaps stock tile prices. The old version hid it on any
       scroll and showed it 200ms after scrolling stopped, so it sat on
       the bottom-center tile whenever the user paused. Direction-based:
       it is out of the way while scrolling down and back when the user
       scrolls up (or is at the top). Strengthened 24 Nov 2026 (Sunil:
       FIXED, not half fixed — the pill must NEVER cover a tile): a
       timer alone still leaves it on a tile for the delay after the
       user pauses, and moving it bottom-right cannot guarantee it
       either (at 390px the tile grid is single-column full-width, so
       every bottom position is over a tile). So the guarantee is a
       live overlap check: the pill is only ever visible while its rect
       intersects NO tile rect, in any scroll state. "Tile" means both
       tile kinds — the 16 stock cards (#screener-body .card) and the
       8 indicator tiles (#indicators-body .tile). The direction logic
       decides the intent to show; the overlap check vetoes showing
       whenever a tile is underneath. A 1s timer re-checks after
       scrolling stops, and a resize re-checks too. Tiles render
       asynchronously after the data loads, so the pill state is also
       re-checked whenever either tile container changes (a
       MutationObserver — this covers the initial render and every
       5-minute refresh, filter, sort and search re-render), once
       subresources have loaded, and once webfonts settle — otherwise
       the pill could sit visible over tiles that did not exist when
       the page first evaluated it. 1s, not 2.5s, because the overlap
       check, not the timer, is now the guarantee, so the timer only
       needs to catch layout changes promptly and never hides a pill
       that is safely placed. */
    var clockFloat = document.querySelector('.clock-float'), lastScrollY = window.scrollY || window.pageYOffset || 0, pillHideTimer = null, pillScrollingDown = false;
    function pillOverlapsTile() {
      if (!clockFloat) return false;
      var pr = clockFloat.getBoundingClientRect();
      var tiles = document.querySelectorAll('#screener-body .card[data-symbol], #indicators-body .tile[data-symbol]');
      for (var i = 0; i < tiles.length; i++) {
        var tr = tiles[i].getBoundingClientRect();
        if (tr.bottom <= 0 || tr.top >= window.innerHeight) continue;
        if (pr.left < tr.right && pr.right > tr.left && pr.top < tr.bottom && pr.bottom > tr.top) return true;
      }
      return false;
    }
    function refreshPill() {
      if (!clockFloat) return;
      var show = !pillScrollingDown && !pillOverlapsTile();
      clockFloat.classList.toggle('scroll-hide', !show);
    }
    if (clockFloat) {
      window.addEventListener('scroll', function () {
        var y = window.scrollY || window.pageYOffset || 0;
        if (pillHideTimer) { clearTimeout(pillHideTimer); pillHideTimer = null; }
        pillScrollingDown = (y > lastScrollY && y > 0);
        lastScrollY = y;
        refreshPill();
        pillHideTimer = setTimeout(refreshPill, 1000);
      }, true);
      window.addEventListener('resize', refreshPill);
      window.addEventListener('load', refreshPill);
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(refreshPill);
      if (typeof MutationObserver !== 'undefined') {
        var pillObs = new MutationObserver(refreshPill);
        ['screener-body', 'indicators-body'].forEach(function (id) {
          var el = document.getElementById(id);
          if (el) pillObs.observe(el, { childList: true, subtree: true });
        });
      }
      refreshPill();
    }
    // Scroll-position saving (25 Nov 2026): throttled to once per
    // frame, same pattern as Friday's pill throttle — never on every
    // scroll event. Also saved on pagehide and when the tab hides,
    // which is the 30-min return path (iOS evicts the background tab;
    // the saved offset is what the next load restores). userMoved
    // tracks real user gestures (wheel/touch), not the programmatic
    // restore scrolls, so the delayed second attempt above only runs
    // before the user has moved the page themselves.
    var scrollSaveQueued = false;
    window.addEventListener('scroll', function () {
      if (scrollSaveQueued) return;
      scrollSaveQueued = true;
      (window.requestAnimationFrame || function (f) { setTimeout(f, 16); })(function () {
        scrollSaveQueued = false;
        saveScrollY();
      });
    }, true);
    window.addEventListener('pagehide', saveScrollY);
    document.addEventListener('visibilitychange', function () { if (document.hidden) saveScrollY(); });
    ['wheel', 'touchmove'].forEach(function (ev) {
      window.addEventListener(ev, function () { userMoved = true; }, { passive: true });
    });
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
