window.psC=window.psC||function(d,l){return document.documentElement.getAttribute('data-theme')==='light'?l:d;};
/* Live BTC chart panel (lazy). Loaded on first open by btcchart.js
   (loadPanel) or on page load on /clock/ (inline mode). Forked from
   btcchart.js et15, 7 Nov 2026 (rebuilt from current main c9340ef7, pin et17): keeps live-feel, 1W 4H candles, FLIP
   morph, CAD via the __BTCP bridge fmt, and inline mount. Shares the
   pill's live price / fmt / CAD state via window.__BTCP — never its
   own USD-only formatter. */
(function(){
var P=window.__BTCP;if(!P||P.panelReady)return;
var $=P.$,U=P.U,RAW=P.RAW,pill=P.pill,menu=P.menu,live=P.live,fmt=P.fmt,curVal=P.curVal,curSym=P.curSym,cadTag=P.cadTag,CUR=P.CUR,mp=P.mp;
var INLINEHOST=document.getElementById('bcInline');
var INLINE=!!INLINEHOST;
/* data */
var DATA=null,PROV=false,dataP=null,SPX=null,SPXK=[],SHOWSPX=false,GOLD=null,GOLDK=[],SHOWGLD=false,MSTR=null,MSTRK=[],SHOWMSTR=false,CBDAILY=null;
/* Test branch 26 Oct 2026: 1D chart type Line | 1H | 4H, default Line. Only shown when 1D is selected. */
var CT='line';
/* Job 5: last 1D candle size picked (1h default), so a trip to a range
   and back to 1D restores the 1D candles instead of dropping to Line. */
var last1DCT='1h';
/* Intraday 1D (deployed 26 Oct 2026, Part 1): Coinbase 15-min candles, last 24h.
   Fallback chain: Coinbase 15-min -> CoinGecko 1-day market chart -> daily closes (in draw1D).
   S&P 500 / Gold toggles are off for 1D only; SHOWSPX/SHOWGLD are preserved for other ranges. */
var INTRA=null,INTRA_AT=0,intraP=null;
function etTime(ms){try{return new Date(ms).toLocaleString('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit',hour12:true});}catch(e){return new Date(ms).toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'});}}
function etDateTime(ms){try{return new Date(ms).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',hour12:true});}catch(e){return new Date(ms).toLocaleString('en-US');}}
/* Screener fix, 2 Nov 2026: drawDaily used to call ET.btcCloseLabel() unguarded, so on any page
   without et.js (screener.html was the only one) a provisional BTC close threw here, after the
   header was set but before the chart was created — labels/header updated, chart never redrew.
   Use ET when present, otherwise compute the same 00:00 UTC close in ET directly. */
function provCloseLabel(){if(window.ET&&ET.btcCloseLabel)return ET.btcCloseLabel();try{return new Date(Date.UTC(new Date().getUTCFullYear(),new Date().getUTCMonth(),new Date().getUTCDate()+1)).toLocaleTimeString('en-US',{timeZone:'America/New_York',hour:'numeric'})+' ET';}catch(e){return '7 PM ET';}}
/* Batch B bug 12: 8s-timeout fetch, same pattern as the price path
   (btcchart.js tf). A stalled external fetch must fail fast so the
   fallbacks run — without a timeout the first paint waits on the network
   stack (~30-60s) and the chart stays blank. */
function tf8(u,o){var c=window.AbortController?new AbortController():null,t=c?setTimeout(function(){c.abort();},8000):0;o=o||{};if(c)o.signal=c.signal;return fetch(u,o).then(function(r){clearTimeout(t);return r;},function(e){clearTimeout(t);throw e;});}
function getIntraday(){
  if(intraP)return intraP;
  var now=Date.now();
  if(INTRA&&now-INTRA_AT<60000)return Promise.resolve(INTRA);
  var end=new Date(now).toISOString(),start=new Date(now-24*3600*1000).toISOString();
  var cb=tf8('https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=900&start='+start+'&end='+end,{cache:'no-store'}) /* Batch B bug 12: 8s abort */.then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(function(j){
    if(!Array.isArray(j))throw new Error('bad candles');
    var pts=j.map(function(c){return {t:c[0]*1000,o:c[3],h:c[2],l:c[1],v:c[4]};}).filter(function(p){return isFinite(p.v)&&p.v>0&&p.t>now-24*3600*1000;}).sort(function(a,b){return a.t-b.t;});
    if(pts.length<2)throw new Error('too few candles');
    return {pts:pts.slice(-96),src:'coinbase'};
  });
  var cg=cb.catch(function(){return tf8('https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=1',{cache:'no-store'}) /* Batch B bug 12: 8s abort */.then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(function(j){
    if(!j||!Array.isArray(j.prices))throw new Error('bad market chart');
    var pts=j.prices.map(function(pr){return {t:pr[0],v:pr[1]};}).filter(function(p){return isFinite(p.v)&&p.v>0;}).sort(function(a,b){return a.t-b.t;});
    if(pts.length<2)throw new Error('too few prices');
    return {pts:pts,src:'coingecko'};
  });});
  intraP=cg.then(function(d){INTRA=d;INTRA_AT=Date.now();intraP=null;return d;},function(e){intraP=null;INTRA=null;throw e;});
  return intraP;
}
/* Job 10 (22 Nov 2026): 1D Line comparison — the pure intraday-compare
   maths, kept in a delimited block so tests/test_cmp_intraday.js can
   extract and unit-test it in Node (same pattern as CmpMath in
   screener-chart.js / test_cmp.js). No DOM, no window: every function
   takes plain data plus `nowMs`. The panel calls these from draw1D /
   draw1DNative; the cmp-intraday job (tools/cmp_intraday.py) builds the
   file they consume. */
var CmpIntraMath = (function () {
  var OPEN_MIN = 570, CLOSE_MIN = 960, CLOSE_END_MIN = 975, CLOSE_END_EARLY_MIN = 795; /* 9:30 AM / 4:00 PM / 4:15 PM ET / 1:15 PM ET on an early-close day */
  /* NYSE holidays and early closes (1:00 PM ET) — the SAME lists as
     tools/stock_weekly.py HOLIDAYS and tools/desk_intraday.py
     EARLY_CLOSES (and assets/js/et.js HOL/EARLY), 2026-2028. They
     live here, inside this block, because the node tests extract this
     block standalone — it cannot read window.ET. Keep the four copies
     in sync when the lists are extended (the et.js expiry guard in
     tests/test_et.js is the reminder). */
  var HOLIDAYS = {'2026-01-01':1,'2026-01-19':1,'2026-02-16':1,'2026-04-03':1,'2026-05-25':1,'2026-06-19':1,'2026-07-03':1,'2026-09-07':1,'2026-11-26':1,'2026-12-25':1,
    '2027-01-01':1,'2027-01-18':1,'2027-02-15':1,'2027-03-26':1,'2027-05-31':1,'2027-06-18':1,'2027-07-05':1,'2027-09-06':1,'2027-11-25':1,'2027-12-24':1,
    '2028-01-17':1,'2028-02-21':1,'2028-04-14':1,'2028-05-29':1,'2028-06-19':1,'2028-07-04':1,'2028-09-04':1,'2028-11-23':1,'2028-12-25':1};
  var EARLY_CLOSES = {'2026-11-27':1,'2026-12-24':1,'2027-11-26':1,'2028-07-03':1,'2028-11-24':1};
  function etParts(ms){
    /* (ET date ISO, minutes after midnight ET). Intl is available in
       the browser and in Node; on any failure fall back to UTC (never
       throw — a wrong zone only mis-trims, it never breaks the draw). */
    try{
      var p = new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).formatToParts(new Date(ms));
      var g = {};
      p.forEach(function(x){ g[x.type] = x.value; });
      var hh = +g.hour; if(hh === 24) hh = 0;
      return {date: g.year + '-' + g.month + '-' + g.day, mins: hh*60 + (+g.minute)};
    }catch(e){
      var d = new Date(ms);
      return {date: d.toISOString().slice(0,10), mins: d.getUTCHours()*60 + d.getUTCMinutes()};
    }
  }
  function etOffsetMs(dateISO){
    /* ET offset (ms) on an ET date: format noon UTC on that date in ET
       and compare. Noon UTC is never near the 2 AM DST transition, so
       the offset is unambiguous for the day. */
    try{
      var noon = Date.parse(dateISO + 'T12:00:00Z');
      var p = new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'numeric',hour12:false}).formatToParts(new Date(noon));
      var g = {};
      p.forEach(function(x){ g[x.type] = x.value; });
      var hh = +g.hour; if(hh === 24) hh = 0;
      return (hh*60 + (+g.minute) - 12*60)*60*1000;
    }catch(e){ return -5*3600*1000; }
  }
  function sessionOpenMs(dateISO){ return Date.parse(dateISO + 'T00:00:00Z') - etOffsetMs(dateISO) + OPEN_MIN*60*1000; }
  function sessionCloseEndMs(dateISO){ /* 4:15 PM ET, or 1:15 PM ET on an early-close day (the tick that picks up the 1:00 PM bar) */
    var endMin = EARLY_CLOSES[dateISO] ? CLOSE_END_EARLY_MIN : CLOSE_END_MIN;
    return Date.parse(dateISO + 'T00:00:00Z') - etOffsetMs(dateISO) + endMin*60*1000; }
  function isEarlyClose(dateISO){ return !!EARLY_CLOSES[dateISO]; }
  function sessionDateET(nowMs){ return etParts(nowMs).date; }
  function trimToSession(pts, session){
    /* BTC 15-min points inside the session window (9:30 AM-4 PM ET on
       the session date). Coinbase buckets are UTC-aligned and 9:30 AM
       ET is a 15-min boundary in both EST and EDT, so the window edges
       land on bucket opens. Points are {t, v} (v = bucket close). */
    if(!pts || !session) return [];
    var out = [];
    for(var i = 0; i < pts.length; i++){
      var p = pts[i];
      if(p == null || !isFinite(p.t) || !isFinite(p.v)) continue;
      var e = etParts(p.t);
      if(e.date === session && e.mins >= OPEN_MIN && e.mins <= CLOSE_MIN) out.push(p);
    }
    return out;
  }
  function alignToPts(pts, bars){
    /* Compare bars ([t_ms, o, h, l, c]) aligned to the trimmed BTC
       points: value-or-null per point, by exact bar-open timestamp.
       A missing slot is null (the renderer bridges or gaps it, same
       as the range views); a bar whose close is not finite is null. */
    var out = [];
    if(!pts) return out;
    var byT = {};
    (bars || []).forEach(function(b){
      if(b && isFinite(b[0]) && isFinite(b[4])) byT[b[0]] = b[4];
    });
    for(var i = 0; i < pts.length; i++){
      var v = byT[pts[i].t];
      out.push(v == null ? null : v);
    }
    return out;
  }
  function firstValue(values){
    if(!values) return null;
    for(var i = 0; i < values.length; i++){ if(values[i] != null && isFinite(values[i])) return values[i]; }
    return null;
  }
  function holdFlat(values){
    /* Trailing nulls hold the last finite value flat. A compare series
       ends at the session close, but BTC runs to 4 PM ET — on an
       early-close day the bars end at 1 PM, so without this the line
       stops at ~1 PM instead of running flat to the right edge.
       Interior nulls are untouched (the renderer bridges or gaps them,
       as before). Returns a new array; the input is not mutated. */
    var out = (values || []).slice(), last = null, lastIdx = -1;
    for(var i = 0; i < out.length; i++){ if(out[i] != null && isFinite(out[i])){ last = out[i]; lastIdx = i; } }
    if(last == null || lastIdx === out.length - 1) return out;
    for(var j = lastIdx + 1; j < out.length; j++) out[j] = last;
    return out;
  }
  function rebaseTo100(values, base){
    /* Every value as 100*v/base (the range views' convention: 100 at
       the first close in range). Nulls stay null; a missing base
       returns all nulls, never NaN. */
    var out = [];
    if(!values) return out;
    for(var i = 0; i < values.length; i++){
      var v = values[i];
      out.push(v == null || !isFinite(v) || !base || !isFinite(base) ? null : 100*v/base);
    }
    return out;
  }
  function isFresh(doc, nowMs){
    /* The stale rule (settled in the build; tools/cmp_intraday.py
       documents it too). Returns {ok, reason}. Session == today:
       fresh while the session is open only if asOf is under 30 min
       old; after the close (4:15 PM ET, or 1:15 PM ET on an
       early-close day) the session is complete and the file is final
       for the day. Session < today: the last session, usable before
       today's 9:30 AM open (or all day when today has no session — a
       weekend OR an NYSE holiday) and only while asOf is under 4 days
       old. Anything else (bad shape, future session, old file) is stale. */
    if(!doc || doc.v !== 1 || doc.kind !== 'cmp-intraday') return {ok:false, reason:'bad document'};
    if(typeof doc.session !== 'string' || !/^\d{4}-\d\d-\d\d$/.test(doc.session)) return {ok:false, reason:'bad session'};
    var asOf = Date.parse(doc.asOf);
    if(!isFinite(asOf)) return {ok:false, reason:'bad asOf'};
    if(!doc.symbols || typeof doc.symbols !== 'object') return {ok:false, reason:'no symbols'};
    var today = etParts(nowMs).date;
    if(doc.session === today){
      if(nowMs < sessionCloseEndMs(today)) return (nowMs - asOf < 30*60*1000) ? {ok:true, reason:'live session'} : {ok:false, reason:'stale: live session, asOf over 30 min old'};
      return {ok:true, reason:'completed session'};
    }
    if(doc.session < today){
      var wd = new Date(today + 'T12:00:00Z').getUTCDay();
      /* No session today: a weekend, or an NYSE holiday — the last
         session stays usable all day (before, a holiday after the
         9:30 AM open read as stale and 1D compare stayed off). */
      var noSessionToday = (wd === 0 || wd === 6 || !!HOLIDAYS[today]);
      if((noSessionToday || nowMs < sessionOpenMs(today)) && nowMs - asOf < 4*86400*1000) return {ok:true, reason:'last session'};
      return {ok:false, reason:'stale: not today and past the open'};
    }
    return {ok:false, reason:'stale: future session'};
  }
  return {etParts:etParts, sessionDateET:sessionDateET, sessionOpenMs:sessionOpenMs, sessionCloseEndMs:sessionCloseEndMs, isEarlyClose:isEarlyClose, trimToSession:trimToSession, alignToPts:alignToPts, firstValue:firstValue, holdFlat:holdFlat, rebaseTo100:rebaseTo100, isFresh:isFresh};
})();
/* Job 10: the cmp-intraday.json fetch. Same data-branch read as
   history.json (RAW base); cached 5 min (the file ticks every 15 min).
   A failed fetch is remembered for 5 min (CMPINTRA_FAIL_AT) so a stale
   or missing file is not re-fetched on every draw — the chart falls
   back to BTC-only until the next retry. */
var CMPINTRA=null,CMPINTRA_AT=0,CMPINTRA_FAIL_AT=0,cmpIntraP=null;
function cmpIntraUrl(){return RAW.replace(/history\.json$/,'cmp-intraday.json');}
function getCmpIntraday(){
  if(cmpIntraP)return cmpIntraP;
  var now=Date.now();
  if(CMPINTRA&&now-CMPINTRA_AT<5*60*1000)return Promise.resolve(CMPINTRA);
  if(CMPINTRA_FAIL_AT&&now-CMPINTRA_FAIL_AT<5*60*1000)return Promise.reject(new Error('cmp-intraday unavailable (recent failure)'));
  cmpIntraP=tf8(cmpIntraUrl()+'?t='+Date.now(),{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(function(d){
    var f=CmpIntraMath.isFresh(d,Date.now());
    if(!f.ok)throw new Error('stale cmp-intraday: '+f.reason);
    CMPINTRA=d;CMPINTRA_AT=Date.now();CMPINTRA_FAIL_AT=0;cmpIntraP=null;return d;
  },function(e){cmpIntraP=null;CMPINTRA=null;CMPINTRA_FAIL_AT=Date.now();throw e;});
  return cmpIntraP;
}

function aggCandles(pts,per){
  var out=[],i;
  for(i=0;i<pts.length;i+=per){
    var seg=pts.slice(i,i+per);if(!seg.length)continue;
    var o=seg[0].o!=null?seg[0].o:seg[0].v, c=seg[seg.length-1].v;
    var h=Math.max.apply(null,seg.map(function(p){return p.h!=null?p.h:p.v;})), l=Math.min.apply(null,seg.map(function(p){return p.l!=null?p.l:p.v;}));
    out.push({t:seg[0].t,o:o,h:h,l:l,c:c});
  }
  return out;
}
/* Minimalist interactive candle chart (27 Oct 2026): same dark, clean canvas, plus an interaction layer.
   - Tap / click a candle (or hover on desktop) to select it: it gets a white outline + soft glow, a thin vertical guide, and its O/H/L/C + change are shown in the info line under the chart.
   - Labels cleaned up: 4 price gridlines, times evenly spaced and inset so first/last do not clip, and the date is shown when the day changes overnight.
   - Razzle, kept minimal: a short fade-in when the candle view first draws, no bounce, no new colours. */
var CAND=null,CANDGEOM=[],CANDSEL=-1,CANDHOV=-1,CANDLBL='',CANDPER=4;
/* EXPERIMENTAL LIVE FEEL (branch pepper-live-feel-exp, Nov 2026, NOT live):
   range candle views gain a live last candle (daily/weekly/monthly buckets
   that contain today only: close = live CoinGecko price, high/low extended),
   a dashed live price line + tag, a tick flash on the popover price, a
   countdown to the bucket close, and an EXPERIMENTAL chip in the header.
   1D intraday and range line views already carried the live price; 1D
   candle views (1H/4H complete buckets) and the 1W 4H view are unchanged.
   See proposals/live-feel-experimental/REVIEW.md.
/* Candle ranges, Day 1 (test branch only, NOT live): 1W daily candles + 1M weekly/daily choice.
   RGCT is the chart type for 1W/1M only (default Line, so the existing line view is unchanged
   unless the visitor opts into candles). RGGRAN is the candle size for the range view.
   CANDRANGE marks that the shared candle canvas + pill are currently showing range candles,
   so the shared listeners and pill dismiss redraw the range view, not the 1D view. */
var CANDRANGE=false,CANDGRAN='daily',RGCAND=null,RGLBL='',RGLIVE=false;
/* Per-range default candle size: the EARLIEST (finest) size offered for
   the range — the first size button in the list. Daily beats Weekly,
   Weekly beats Monthly, Monthly beats Yearly (Sunil, 21 Nov 2026). 1M,
   3M/6M/YTD, 5Y and 10Y default to Daily; 1Y defaults to Weekly; 1W
   defaults to 4H (Sunil, 21 Nov 2026 — the intraday size; Daily is the
   fallback if 4H is unavailable). Job 9 (22 Nov 2026): 3M/6M/YTD gained
   Daily, so their default moved from Weekly to Daily (finest-first). */
function defaultGran(r){return (r==='1W')?'4h':(r==='1Y')?'weekly':'daily';}
var RGCT='line',RGGRAN=defaultGran('1M'),RGSEEN={};
/* Candle ranges, Day 2: 3M/6M/YTD/1Y join 1W/1M. Granularity choices:
   1W daily|4h (default 4h); 1M weekly|daily (default daily); 3M/6M/YTD/1Y monthly|weekly
   (default weekly). Job 9 (22 Nov 2026): 3M/6M/YTD gain daily (default
   daily); 5Y joins with daily|weekly|monthly and 10Y with
   daily|monthly|yearly (both default daily). Job 11 (22 Nov 2026): Max
   joins with daily|weekly|monthly|yearly (default daily) — no longer
   Line-only; its candles come from the same batched extended fetch,
   back to the first daily close (2010-08-18). */
var CANDLE_RANGES=['1W','1M','3M','6M','YTD','1Y','5Y','10Y','Max'];
/* Fix 29 Oct 2026 (browser test, Day 1): the pill + canvas listeners are shared
   between the 1D candle view and the 1W/1M range candle view, and the old code
   let them resurrect a stale candle canvas after switching to a line view:
   switching to Line left the pill visible, and dismissing it called
   redrawCandles(), which repainted the old 4H candles over the line chart.
   Rule from now on: switching chart type ALWAYS clears pill + selection +
   guide; dismissing a pill NEVER changes the chart type and NEVER touches
   the canvas unless a candle view is currently active. */
function candViewActive(){return (rng==='1D'&&CT!=='line')||(CANDLE_RANGES.indexOf(rng)>=0&&RGCT==='candles');}
function hideCandPill(){var el=$('bcSel');if(el)el.style.display='none';}
function clearCandState(){CANDSEL=-1;CANDHOV=-1;hideCandPill();}
function dismissCandInfo(){clearCandState();if(candViewActive()&&((rng==='1D'&&CAND&&CAND.length)||(CANDLE_RANGES.indexOf(rng)>=0&&RGCAND&&RGCAND.length)))redrawCandles();}
function redrawCandles(){if(!candViewActive()){hideCandPill();return;}if(CANDRANGE)drawCandlesRange();else drawCandles1D(CAND,CANDLBL,CANDPER);}
/* True pill bubble for a selected candle (v5, user: "more like a pill"):
   fully rounded ends (999px radius), centred text, compact, no arrow — the white outline + dashed guide
   on the selected candle already points at it, so the pill can float cleanly over the chart.
   The pill body does NOT intercept taps (pointer-events:none), so candles beneath it stay tappable —
   tapping a candle under the pill selects that candle instead of dismissing the pill. Dismiss is via
   the ✕ inside the pill (the only tappable part), tapping the same candle again, or tapping empty
   chart space / a non-interactive part of the popover. */
function candInfoEl(){
  var el=$('bcSel');if(el)return el;
  var box=$('bcC')&&$('bcC').parentNode;if(!box)return null;
  el=document.createElement('div');el.id='bcSel';
  el.style.cssText='display:none;position:absolute;z-index:5;width:280px;max-width:calc(100% - 24px);background:'+psC('linear-gradient(180deg,#0e1730,#0a1122)','#ffffff')+';border:1px solid '+psC('rgba(34,211,238,.30)','#e2e8f0')+';border-radius:999px;padding:16px 24px;color:'+psC('#e8eef7','#0f172a')+';font:13px/1.5 Inter, sans-serif;text-align:center;box-shadow:'+psC('0 20px 50px rgba(0,0,0,.6)','0 12px 32px rgba(15,23,42,.12)')+';pointer-events:none;';
  box.style.position='relative';box.appendChild(el);
  return el;
}
function showCandInfo(i,geomX,geomTop){
  var el=candInfoEl();if(!el)return;
  if(!CAND||i<0||i>=CAND.length){el.style.display='none';return;}
  var k=CAND[i],dur=CANDPER===4?3600000:14400000,chg=k.c-k.o,pct=k.o?(chg/k.o*100):0;
  var col=k.c>=k.o?psC('#22c55e','#15803d'):psC('#ef4444','#b91c1c');
  el.innerHTML='';
  /* pill content, centred, four short lines — no table rows, no arrow, no bottom line:
     line 1: when (small grey) · line 2: High / Low · line 3: Open / Close · line 4: Change in green/red.
     A ✕ sits inside the pill at the top-right (44px touch target); it is the pill's
     only tappable part — the pill body lets taps through to the chart beneath, so
     dismiss is via this ✕, tapping the same candle again, or tapping empty space.
     Round 2 (8 Nov 2026): Sunil could not SEE the ✕ — it was a small muted-grey
     glyph with no background, invisible against the pill. It is now a solid
     cyan circle with a bold dark ✕: unmistakable as a close button in both
     themes. The date line gets right padding so its text never runs under it. */
  var cl=document.createElement('button');cl.type='button';cl.textContent='✕';cl.setAttribute('aria-label','Close candle details');
  cl.style.cssText='pointer-events:auto;position:absolute;top:8px;right:8px;width:44px;height:44px;min-width:44px;min-height:44px;padding:0;border:none;border-radius:50%;background:#22d3ee;color:#0a1122;font-size:22px;font-weight:700;line-height:44px;cursor:pointer;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,.4);';
  cl.addEventListener('click',function(ev){ev.stopPropagation();dismissCandInfo();});
  el.appendChild(cl);
  var tm=document.createElement('div');tm.style.cssText='color:'+psC('#9aa6bc','#475569')+';font-size:12px;padding-right:48px;';
  /* Fix 29 Oct 2026 (browser test, Day 2): range candles are UTC days /
     weeks / months, so their labels must be UTC too. ET formatting shifted
     every UTC-midnight timestamp back a day — and a month-boundary candle
     back a whole month — so the October monthly candle (t = Oct 1 00:00
     UTC) read "September 2026" in its pill and "Sep 30" on the axis, and
     looked like no October candle existed. The bucket was never dropped;
     it was mislabelled. 1D intraday pills below keep ET, which is right
     for intraday times. */
  if(CANDRANGE){if(CANDGRAN==='4h'){var d4=new Date(k.t).toLocaleDateString('en-US',{timeZone:'UTC',month:'short',day:'numeric'}),t4s=new Date(k.t).toLocaleTimeString('en-US',{timeZone:'UTC',hour:'numeric',minute:'2-digit'}),t4e=new Date(k.end).toLocaleTimeString('en-US',{timeZone:'UTC',hour:'numeric',minute:'2-digit'});tm.textContent='4-hour candle · '+d4+' '+t4s+' – '+t4e+' UTC';}else if(CANDGRAN==='monthly'){tm.textContent='Monthly candle · '+new Date(k.t).toLocaleDateString('en-US',{timeZone:'UTC',month:'long',year:'numeric'})+' UTC';}else{var sd=new Date(k.t).toLocaleDateString('en-US',{timeZone:'UTC',month:'short',day:'numeric'}),ed=new Date(k.end).toLocaleDateString('en-US',{timeZone:'UTC',month:'short',day:'numeric'});tm.textContent=(CANDGRAN==='weekly'?'Weekly':'Daily')+' candle · '+sd+(ed!==sd?' – '+ed:'')+' UTC';}}
  else tm.textContent=(CANDPER===4?'1-hour':'4-hour')+' · '+etDateTime(k.t)+' – '+etTime(k.t+dur)+' ET';
  el.appendChild(tm);
  var hl=document.createElement('div');hl.style.cssText='font-size:14px;font-weight:600;color:'+psC('#e8eef7','#0f172a')+';font-variant-numeric:tabular-nums;margin:2px 0;';hl.textContent='High '+fmt(k.h)+'  ·  Low '+fmt(k.l);el.appendChild(hl);
  var oc=document.createElement('div');oc.style.cssText='font-size:14px;font-weight:600;color:'+psC('#e8eef7','#0f172a')+';font-variant-numeric:tabular-nums;margin:2px 0;';oc.textContent='Open '+fmt(k.o)+'  ·  Close '+fmt(k.c);el.appendChild(oc);
  var ch=document.createElement('div');ch.style.cssText='font-size:14px;font-weight:600;color:'+col+';font-variant-numeric:tabular-nums;';ch.textContent=(chg>=0?'▲ +':'▼ -')+curSym()+Math.abs(curVal(chg)).toLocaleString('en-US',{maximumFractionDigits:0})+' ('+(pct>=0?'+':'')+pct.toFixed(2)+'%)';el.appendChild(ch);
  /* TA Stage 2: indicator values for this candle, when overlays are on. */
  try{var _ta3=window.__BCTA&&window.__BCTA.taTip;if(_ta3){var _tl3=_ta3(CANDRANGE?'candles-range':'candles-1d',i);if(_tl3&&_tl3.length){var _td=document.createElement('div');_td.style.cssText='font-size:13px;font-weight:600;color:'+psC('#9aa6bc','#475569')+';font-variant-numeric:tabular-nums;margin:2px 0;';_td.textContent=_tl3.map(function(o){return o.t;}).join('  ·  ');el.appendChild(_td);}}}catch(e){}
  /* position: floating pill over the chart, centred horizontally, never at the bottom, never off-screen */
  el.style.display='block';
  var box=$('bcC').parentNode,bw=box.clientWidth||640,bh=box.clientHeight||300;
  var ew=el.offsetWidth||280,eh=el.offsetHeight||110;
  var left=Math.max(12,(bw-ew)/2),top=12;
  if(geomX!=null&&bw>640){left=geomX-ew/2;if(left<8)left=8;if(left+ew>bw-8)left=bw-ew-8;top=geomTop!=null?Math.max(8,geomTop-eh-16):12;}
  el.style.left=left+'px';el.style.top=top+'px';
}
function drawCandles1D(candles,label,per){
  if(!candles.length)return false;
  CANDRANGE=false;
  var prevCAND=CAND; CAND=candles;CANDLBL=label;CANDPER=per||4;
  if(CANDSEL<0){var _b=$('bcSel');if(_b)_b.style.display='none';}
  var c=$('bcC'),ctx=c.getContext('2d'),W=c.parentNode.clientWidth||640,H=c.parentNode.clientHeight||300;
  var dpr=window.devicePixelRatio||1;c.width=W*dpr;c.height=H*dpr;c.style.width=W+'px';c.style.height=H+'px';ctx.setTransform(dpr,0,0,dpr,0,0);
  /* short fade-in for the razzle layer, only when the candle set changes (not on hover redraws, or it would flicker) */
  if(!prevCAND || prevCAND.length!==candles.length || prevCAND[0].t!==candles[0].t || prevCAND!==candles){ /* first draw of a new set fades in; hover redraws reuse the same array object, so they skip the fade */ if(prevCAND!==candles){c.style.transition='opacity .3s ease';c.style.opacity='0';requestAnimationFrame(function(){c.style.opacity='1';});} }
  ctx.clearRect(0,0,W,H);
  var lo=Math.min.apply(null,candles.map(function(k){return k.l;})), hi=Math.max.apply(null,candles.map(function(k){return k.h;}));
  var pad=(hi-lo)*0.08||1;lo-=pad;hi+=pad;
  /* Job 12: widen the axis for an overlay that runs outside the candle
     range (1W daily: the 200s sat below the visible range and drew
     nothing), unbounded — the values come from the data. The 2% margin
     keeps the line off the plot edge — candles have no nice ticks for the
     headroom rule. */
  try{if(window.__BTTA&&window.__BTTA.ovExpandRange){var _ovC=window.__BTTA.ovExpandRange(window.__BCTA.state(),'candles-1d',candles.map(function(k){return k.c;}),lo,hi);if(_ovC&&isFinite(_ovC.lo)&&isFinite(_ovC.hi)&&_ovC.hi>_ovC.lo){var _spC=_ovC.hi-_ovC.lo;if(_ovC.lo<lo)lo=_ovC.lo-_spC*0.02;if(_ovC.hi>hi)hi=_ovC.hi+_spC*0.02;}}}catch(e){}
  /* Must-fix (27 Nov 2026): a price axis never goes below $0 — the 8%
     pad (and an overlay expansion) could push lo negative on long
     ranges (10Y monthly read $-17,147). */
  if(lo<0)lo=0;
  var L=62,R=12,T=18,B=44,iw=W-L-R,ih=H-T-B;
  /* TA Stage 1, candle inset (item 1): half a slot at each end, so the first
     and last candles sit fully inside the plot instead of on its edges.
     CANDGEOM carries these x positions, so later stages reuse the same inset. */
  var X=function(i){return L+iw*(i+0.5)/candles.length;};
  var Y=function(v){return T+ih*(1-(v-lo)/(hi-lo));};
  ctx.strokeStyle=psC('rgba(255,255,255,.08)','rgba(15,23,42,.10)');ctx.fillStyle=psC('#9aa6bc','#475569');ctx.font='11px Inter, sans-serif';ctx.textAlign='right';
  [0,0.33,0.66,1].forEach(function(f){var v=lo+(hi-lo)*f,y=Y(v);ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(W-R,y);ctx.stroke();ctx.fillText(curSym()+Math.round(curVal(v)).toLocaleString('en-US'),L-6,y+4);});
  ctx.textAlign='center';CANDGEOM=[];drawCandles1D._lastTx=null;
  candles.forEach(function(k,i){
    var x=X(i),col=k.c>=k.o?'#22c55e':'#ef4444',bw=Math.max(4,Math.min(28,iw/candles.length*0.55));
    var top=Y(Math.max(k.o,k.c)),bot=Y(Math.min(k.o,k.c));
    CANDGEOM.push({x:x,bw:bw,top:top,bot:bot,wickTop:Y(k.h),wickBot:Y(k.l)});
    ctx.strokeStyle=col;ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(x,Y(k.h));ctx.lineTo(x,Y(k.l));ctx.stroke();
    ctx.fillStyle=col;ctx.fillRect(x-bw/2,top,bw,Math.max(2,bot-top));
    /* X-axis, iPhone-first, two clean rows so date and time never overlap and never overlap each other:
       - bottom row (H-8): time only, at most 4 labels on a phone (step 6 for 24 candles = ~82px apart on a 390px phone, time label ~55px wide, so no overlap), at most 6 on desktop
       - upper row (H-24): date only ("Oct 27"), only at the first candle and when the day changes, clamped inside the chart
       - labels are also spaced by measured width: a label is skipped if it would come within 62px of the previous one */
    var phoneW=W<=640;
    var step=phoneW?Math.max(1,Math.ceil(candles.length/4)):Math.max(1,Math.floor(candles.length/6));
    if(i%step===0&&x>L+32&&x<W-R-32){
      /* Must-fix (27 Nov 2026): the time row is a neutral slate, like the
         date row — it used to inherit the candle's green/red fillStyle
         set two lines earlier for the body. */
      var _prevX=drawCandles1D._lastTx;if(_prevX==null||x-_prevX>=62){ctx.fillStyle=psC('#9aa6bc','#475569');ctx.fillText(etTime(k.t),x,H-8);drawCandles1D._lastTx=x;}
    }
    var prev=candles[i-1],dayChange=!prev||new Date(prev.t).toLocaleDateString('en-US',{timeZone:'America/New_York'})!==new Date(k.t).toLocaleDateString('en-US',{timeZone:'America/New_York'});
    if(dayChange){
      var dx=Math.max(L+30,Math.min(W-R-30,x));
      ctx.fillStyle=psC('#64748b','#475569');ctx.fillText(new Date(k.t).toLocaleDateString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric'}),dx,H-24);
      ctx.fillStyle=psC('#9aa6bc','#475569');
    }
  });
  /* selected / hovered candle: white outline + glow + vertical guide, drawn last so it sits on top */
  [CANDHOV,CANDSEL].forEach(function(idx,layer){
    if(idx<0||idx>=candles.length)return;var g=CANDGEOM[idx],k=candles[idx],col=k.c>=k.o?'#22c55e':'#ef4444';
    if(layer===0){ctx.strokeStyle=psC('rgba(255,255,255,.25)','rgba(15,23,42,.35)');ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(g.x,T);ctx.lineTo(g.x,H-B);ctx.stroke();ctx.setLineDash([]);}
    else{ctx.save();ctx.shadowColor=col;ctx.shadowBlur=12;ctx.strokeStyle=psC('#ffffff','#0f172a');ctx.lineWidth=1.5;ctx.strokeRect(g.x-g.bw/2-2,g.top-2,g.bw+4,Math.max(4,g.bot-g.top)+4);ctx.restore();}
  });
  ctx.fillStyle=psC('#9aa6bc','#475569');ctx.textAlign='left';ctx.fillText(label, L, 12);
  /* TA Stage 2: publish the geometry (inset x positions from CANDGEOM) and
     draw the overlays — here, not at the call site, so hover redraws
     (redrawCandles) repaint the overlays too. */
  TAGEOM={kind:'candles-1d',xs:CANDGEOM.map(function(g){return g.x;}),yFor:Y,log:false,closes:candles.map(function(k){return k.c;}),times:candles.map(function(k){return k.t;}),n:candles.length,W:W,H:H,pad:{l:L,r:R,t:T,b:B},plotW:iw,plotH:ih};
  taAfterDraw('candles-1d');
  /* interaction listeners, attached once (shared with the range candle view) */
  bindCandListeners(c);
  FALLBACK_NOTE='';
  return true;
}
function bindCandListeners(c){
  if(c._candBound)return;
  c._candBound=true;
  var pick=function(evt){var r=c.getBoundingClientRect(),x=(evt.clientX-r.left);var best=-1,bd=1e9;CANDGEOM.forEach(function(g,i){var d=Math.abs(g.x-x);if(d<bd){bd=d;best=i;}});return best;};
  /* Guard: in a line view this canvas holds the native line chart, not candles.
     Without the guard, hover/click here used stale CANDGEOM and repainted
     old candles over the line chart. */
  /* Pointer scrub (mirrors the screener): drag across the chart and the pill follows
     candle by candle. pointerdown only ARMS the scrub — it does not select: a clean tap
     still goes through the press-end handler below, and selecting on pointerdown would make
     that trailing press toggle the just-selected candle straight back off.
     Tap-vs-scrub, round 3 (8 Nov 2026): rounds 1-2 put the dismiss in the
     CLICK handler, but a diagnostic (diag_touch_events.py) proved the click
     often NEVER FIRES for a real finger tap: a diagonal/vertical tap of
     ~12px+ makes the browser take the gesture over as a scroll
     (touch-action: pan-y) and fire pointercancel with no click, and a
     horizontal tap of ~20px+ gets pointerup but no click either. So the pill
     could never dismiss however the thresholds were tuned — the handler
     simply never ran. The tap logic now runs on PRESS END (pointerup AND
     pointercancel), using the pointerdown position (downCandle — where the
     finger LANDED, the best signal of intent) and the max movement during
     the press (maxMove). (Round 2's rule was that a press only counts as
     a drag/scroll when it moved more than SCRUB_PX (24px) or the scrub
     actually moved the selection; anything less is a tap and dismisses
     (same candle) or selects (another candle). Round 3 below changed
     that rule — see below.) The click handler is now only a fallback for clicks with no
     preceding pointer press, suppressed whenever a press-end already handled
     the press (pressDone). A real drag still ends with the pill on the final
     candle instead of dismissing it.
     Round 3 (8 Nov 2026): the press-end fix STILL failed on Sunil's real
     iPhone — re-tapping the selected candle did not dismiss, though the
     pill tap and the X did. A diagnostic (probe_round3_diag.py) proved
     two things on the live code. (1) Re-taps with 25-40px of finger
     movement dismiss only 3/6: endPress classified them as drags because
     maxMove exceeded SCRUB_PX (24px), and no click ever fired to rescue
     them. Real finger taps move that far; the probe had only tested up
     to 20px. (2) The tap logic ran only on pointerup/pointercancel/click,
     all of which iOS Safari can swallow for a real finger tap. So round 3
     changes the dismiss in three ways, none of them a threshold tune:
     (a) a press counts as a drag ONLY when the scrub actually moved the
     selection (scrubChanged) — how far the finger moved no longer
     matters, so a tap that moves 40px but stays on one candle still
     dismisses; (b) the tap logic now also runs on touchend AND
     touchcancel (the Touch Events API, iOS Safari's native one, which
     always fires), plus the pointer events, so at least one press-end
     path runs; (c) endPress is idempotent (pressDone guard at entry) so
     the tap is never applied twice when several press-end events fire
     for one press. The press is also armed on touchstart as well as
     pointerdown, so the down position is recorded even if pointerdown
     is ever dropped. */
  var scrubbing=false,scrubChanged=false,downX=0,downY=0,downCandle=-1,pressDone=false,SCRUB_PX=24;
  function endPress(){
    if(pressDone)return;
    if(!candViewActive())return;
    pressDone=true;
    var isDrag=scrubChanged;
    scrubChanged=false;
    if(isDrag)return;
    var r=c.getBoundingClientRect(),y=downY-r.top;
    if(CANDGEOM.length){var pt=1e9,pb=-1e9;CANDGEOM.forEach(function(g){if(g.wickTop<pt)pt=g.wickTop;if(g.wickBot>pb)pb=g.wickBot;});if(y<pt-6||y>pb+6){dismissCandInfo();return;}}
    if(downCandle>=0){if(downCandle===CANDSEL){dismissCandInfo();return;}CANDSEL=downCandle;redrawCandles();var g=CANDSEL>=0?CANDGEOM[CANDSEL]:null;showCandInfo(CANDSEL,g?g.x:null,g?g.top:null);return;}
  }
  function armPress(x,y){if(!candViewActive())return;scrubbing=true;scrubChanged=false;pressDone=false;downX=x;downY=y;downCandle=pick({clientX:x});}
  c.addEventListener('pointerdown',function(e){armPress(e.clientX,e.clientY);});
  c.addEventListener('touchstart',function(e){if(!e.touches||!e.touches.length)return;var t=e.touches[0];armPress(t.clientX,t.clientY);},{passive:true});
  c.addEventListener('pointermove',function(e){if(!scrubbing||!candViewActive())return;var d=Math.max(Math.abs(e.clientX-downX),Math.abs(e.clientY-downY));if(d<=SCRUB_PX)return;var i=pick(e);if(i<0||i===CANDSEL)return;CANDSEL=i;scrubChanged=true;redrawCandles();var g=CANDSEL>=0?CANDGEOM[CANDSEL]:null;showCandInfo(CANDSEL,g?g.x:null,g?g.top:null);});
  c.addEventListener('pointerup',function(){scrubbing=false;endPress();});
  c.addEventListener('pointercancel',function(){scrubbing=false;endPress();});
  c.addEventListener('touchend',function(){scrubbing=false;endPress();},{passive:true});
  c.addEventListener('touchcancel',function(){scrubbing=false;endPress();},{passive:true});
  c.addEventListener('mousemove',function(e){if(!candViewActive())return;var i=pick(e);if(i!==CANDHOV){CANDHOV=i;redrawCandles();}});
  c.addEventListener('mouseleave',function(){if(!candViewActive())return;CANDHOV=-1;redrawCandles();});
  /* Click fallback only: a click with no preceding pointer press (e.g. a
     keyboard/synthetic click). Normal presses are already handled by the
     press-end handler above, and their click is suppressed via pressDone so
     the tap is never applied twice. A tap on empty chart space (above the
     highest wick / below the lowest, e.g. the label strips) dismisses the
     pill instead of selecting a candle. */
  c.addEventListener('click',function(e){if(!candViewActive())return;if(pressDone){pressDone=false;return;}var r=c.getBoundingClientRect(),y=e.clientY-r.top;if(CANDGEOM.length){var pt=1e9,pb=-1e9;CANDGEOM.forEach(function(g){if(g.wickTop<pt)pt=g.wickTop;if(g.wickBot>pb)pb=g.wickBot;});if(y<pt-6||y>pb+6){dismissCandInfo();return;}}var i=pick(e);if(i===CANDSEL){dismissCandInfo();return;}CANDSEL=i;redrawCandles();var g=CANDSEL>=0?CANDGEOM[CANDSEL]:null;showCandInfo(CANDSEL,g?g.x:null,g?g.top:null);});
}
/* Candle ranges, Day 1: aggregate Coinbase daily candles into range candles.
   Daily mode is identity (one candle per UTC day). Weekly mode buckets by the
   Monday-start calendar week in UTC — deliberately UTC, not ET: the daily
   candles themselves are UTC days, and bucketing them by ET weekdays would
   split weeks wrongly (a UTC Monday is still Sunday evening in ET, so it
   would land in the previous ET week). ET is display only (popver labels).
   A weekly candle's open is its first day's open, its close is its last
   day's close, its high is the max of its days' highs and its low is the min
   of its days' lows. Partial weeks at the window edges stay partial — they
   are never padded or invented. Monthly aggregation is the same shape with
   calendar-month buckets; yearly (Job 9, 22 Nov 2026) with calendar-year
   buckets. */
function aggDailyCandles(daily,mode){
  if(!Array.isArray(daily)||!daily.length)return [];
  if(mode!=='weekly'&&mode!=='monthly'&&mode!=='yearly')return daily.map(function(p){return {t:p.t,end:p.t,o:p.o,h:p.h,l:p.l,c:p.c};});
  if(mode==='yearly'){
    /* Job 9 (22 Nov 2026): calendar-year buckets (UTC), same shape as
       monthly — a yearly candle's open is its first day's open, its close
       is its last day's close, its high is the max of its days' highs and
       its low is the min of its days' lows. Partial years at the window
       edges stay partial — they are never padded or invented. */
    var outY=[],curY=null,curKeyY=null;
    daily.forEach(function(p){
      var d=new Date(p.t),key=d.getUTCFullYear();
      if(key!==curKeyY){if(curY)outY.push(curY);curKeyY=key;curY={t:p.t,end:p.t,o:p.o,h:p.h,l:p.l,c:p.c};}
      else{curY.h=Math.max(curY.h,p.h);curY.l=Math.min(curY.l,p.l);curY.c=p.c;curY.end=p.t;}
    });
    if(curY)outY.push(curY);
    return outY;
  }
  if(mode==='monthly'){
    var outM=[],curM=null,curKeyM=null;
    daily.forEach(function(p){
      var d=new Date(p.t),key=d.getUTCFullYear()*12+d.getUTCMonth();
      if(key!==curKeyM){if(curM)outM.push(curM);curKeyM=key;curM={t:p.t,end:p.t,o:p.o,h:p.h,l:p.l,c:p.c};}
      else{curM.h=Math.max(curM.h,p.h);curM.l=Math.min(curM.l,p.l);curM.c=p.c;curM.end=p.t;}
    });
    if(curM)outM.push(curM);
    return outM;
  }
  var out=[],cur=null,curKey=null;
  daily.forEach(function(p){
    var d=new Date(p.t),dow=d.getUTCDay();
    var mon=Date.UTC(d.getUTCFullYear(),d.getUTCMonth(),d.getUTCDate()-(dow===0?6:dow-1));
    var key=mon;
    if(key!==curKey){if(cur)out.push(cur);curKey=key;cur={t:p.t,end:p.t,o:p.o,h:p.h,l:p.l,c:p.c};}
    else{cur.h=Math.max(cur.h,p.h);cur.l=Math.min(cur.l,p.l);cur.c=p.c;cur.end=p.t;}
  });
  if(cur)out.push(cur);
  return out;
}
/* Range-candle x-axis label indices: evenly spaced, first and last always
   included, at most one label per ~64px of plot width so labels never
   collide. This replaces the old first-candle-plus-month-change rule, which
   on 1M Daily produced only "Sep 28" (Oct 1 was skipped by the 62px guard,
   and the last candle failed its own x test) — a blank axis. */
function rangeLabelIndices(n,iw){
  if(!n||n<=0)return [];
  var maxLabels=Math.max(2,Math.floor(iw/64));
  var count=Math.min(n,maxLabels);
  if(count<=1)return [0];
  var out=[];
  for(var k=0;k<count;k++){
    var idx=Math.round(k*(n-1)/(count-1));
    if(out.indexOf(idx)<0)out.push(idx);
  }
  return out;
}
/* Experimental live feel: time left until the current bucket closes
   (daily -> midnight UTC, weekly -> Monday 00:00 UTC, monthly -> 1st,
   yearly -> 1 Jan). */
function bucketCloseCountdown(gran){
  var now=new Date(), target;
  if(gran==='weekly'){
    var d=(8-now.getUTCDay())%7;
    target=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate()+d,0,0,0));
    if(target<=now)target=new Date(target.getTime()+7*86400000);
  }else if(gran==='monthly'){
    target=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth()+1,1,0,0,0));
  }else if(gran==='yearly'){
    target=new Date(Date.UTC(now.getUTCFullYear()+1,0,1,0,0,0));
  }else{
    target=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate()+1,0,0,0));
  }
  var ms=Math.max(0,target-Date.now());
  var dd=Math.floor(ms/86400000),hh=Math.floor(ms/3600000)%24,mm=Math.floor(ms/60000)%60;
  return (dd?dd+'d ':'')+hh+'h '+mm+'m';
}
function drawCandlesRange(){
  var candles=RGCAND;if(!candles||!candles.length)return false;
  CANDRANGE=true;CANDGRAN=RGGRAN;CAND=candles;CANDLBL=RGLBL;
  if(CANDSEL<0){var _b=$('bcSel');if(_b)_b.style.display='none';}
  var c=$('bcC'),ctx=c.getContext('2d'),W=c.parentNode.clientWidth||640,H=c.parentNode.clientHeight||300;
  var dpr=window.devicePixelRatio||1;c.width=W*dpr;c.height=H*dpr;c.style.width=W+'px';c.style.height=H+'px';ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,W,H);
  var lo=Math.min.apply(null,candles.map(function(k){return k.l;})), hi=Math.max.apply(null,candles.map(function(k){return k.h;}));
  var pad=(hi-lo)*0.08||1;lo-=pad;hi+=pad;
  /* Job 12: widen the axis for an overlay that runs outside the candle
     range (1W daily: the 200s sat below the visible range and drew
     nothing), unbounded — the values come from the data. The 2% margin
     keeps the line off the plot edge — candles have no nice ticks for the
     headroom rule. */
  try{if(window.__BTTA&&window.__BTTA.ovExpandRange){var _ovR=window.__BTTA.ovExpandRange(window.__BCTA.state(),'candles-range',candles.map(function(k){return k.c;}),lo,hi);if(_ovR&&isFinite(_ovR.lo)&&isFinite(_ovR.hi)&&_ovR.hi>_ovR.lo){var _spR=_ovR.hi-_ovR.lo;if(_ovR.lo<lo)lo=_ovR.lo-_spR*0.02;if(_ovR.hi>hi)hi=_ovR.hi+_spR*0.02;}}}catch(e){}
  /* Must-fix (27 Nov 2026): a price axis never goes below $0 — the 8%
     pad (and an overlay expansion) could push lo negative on long
     ranges (10Y monthly read $-17,147). */
  if(lo<0)lo=0;
  var L=62,T=18,B=44;
  /* TA Stage 1, CAD live-tag fix (item 8): the LIVE tag was sized at USD width
     (R=78), so in CAD the wider tag ran off the canvas edge. Measure the tag
     in the displayed currency first and size the right margin to fit it.
     When the tag will not be drawn (no live price) keep today's R=78. */
  var R=12;
  if(typeof RGLIVE!=='undefined'&&RGLIVE){
    if(live.usd!=null){ctx.font='bold 11px Inter, sans-serif';R=Math.ceil(ctx.measureText('LIVE '+fmt(live.usd)).width)+16;}
    else{R=78;}
  }
  var iw=W-L-R,ih=H-T-B;
  /* TA Stage 1, candle inset (item 1): half a slot at each end — see drawCandles1D. */
  var X=function(i){return L+iw*(i+0.5)/candles.length;};
  var Y=function(v){return T+ih*(1-(v-lo)/(hi-lo));};
  ctx.strokeStyle=psC('rgba(255,255,255,.08)','rgba(15,23,42,.10)');ctx.fillStyle=psC('#9aa6bc','#475569');ctx.font='11px Inter, sans-serif';ctx.textAlign='right';
  [0,0.33,0.66,1].forEach(function(f){var v=lo+(hi-lo)*f,y=Y(v);ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(W-R,y);ctx.stroke();ctx.fillText(curSym()+Math.round(curVal(v)).toLocaleString('en-US'),L-6,y+4);});
  ctx.textAlign='center';CANDGEOM=[];
  var lastTx=null,lastMd=null,labIdx=rangeLabelIndices(candles.length,iw);
  candles.forEach(function(k,i){
    var x=X(i),col=k.c>=k.o?'#22c55e':'#ef4444',bw=Math.max(4,Math.min(28,iw/candles.length*0.55));
    var top=Y(Math.max(k.o,k.c)),bot=Y(Math.min(k.o,k.c));
    CANDGEOM.push({x:x,bw:bw,top:top,bot:bot,wickTop:Y(k.h),wickBot:Y(k.l)});
    ctx.strokeStyle=col;ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(x,Y(k.h));ctx.lineTo(x,Y(k.l));ctx.stroke();
    ctx.fillStyle=col;ctx.fillRect(x-bw/2,top,bw,Math.max(2,bot-top));
    /* X-axis: date only (month + day), evenly spaced via rangeLabelIndices
       (first and last included, ~64px apart). The 62px guard stays as a
       safety net — it now rarely fires, instead of swallowing every label
       after the first, as the old first-plus-month-change rule did. The old
       separate last-candle label on a second row is gone: the last candle
       is in this row, so it is no longer skipped by its own x test.
       Must-fix (27 Nov 2026): multi-year ranges print the year
       ("Nov 20, 21") so labels never repeat, and a date that already
       drew is skipped — 1W 4H printed each date twice (two 4-hour
       buckets land on the same day). */
    if(labIdx.indexOf(i)>=0){
      var _long=(rng==='5Y'||rng==='10Y'||rng==='Max');
      var md=new Date(k.t).toLocaleDateString('en-US',_long?{timeZone:'UTC',month:'short',day:'numeric',year:'2-digit'}:{timeZone:'UTC',month:'short',day:'numeric'});
      var dx=Math.max(24,Math.min(W-24,x));
      if(md!==lastMd&&(lastTx==null||dx-lastTx>=56)){ctx.fillStyle=psC('#64748b','#475569');ctx.fillText(md,dx,H-24);ctx.fillStyle=psC('#9aa6bc','#475569');lastTx=dx;lastMd=md;}
    }
  });
  if(typeof RGLIVE!=='undefined'&&RGLIVE&&live.usd!=null&&candles.length){
    var lg=CANDGEOM[candles.length-1], ly2=Y(live.usd);
    ctx.save();
    // Live-overlay colors are theme-aware via psC (the bright dark-theme
    // cyan/green wash out on a light chart background).
    ctx.strokeStyle=psC('#22d3ee','#0891b2');ctx.lineWidth=1.5;ctx.setLineDash([6,4]);
    ctx.beginPath();ctx.moveTo(L,ly2);ctx.lineTo(W-R,ly2);ctx.stroke();ctx.setLineDash([]);
    ctx.strokeStyle=psC('#22d3ee','#0891b2');ctx.setLineDash([4,4]);
    ctx.strokeRect(lg.x-lg.bw/2-4,lg.wickTop-8,lg.bw+8,lg.wickBot-lg.wickTop+16);ctx.setLineDash([]);
    ctx.font='bold 11px Inter, sans-serif';ctx.textAlign='left';
    ctx.fillStyle=psC('#22c55e','#15803d');ctx.fillText('LIVE',lg.x-13,lg.wickTop-14);
    var tag='LIVE '+fmt(live.usd), tw2=ctx.measureText(tag).width;
    ctx.fillStyle=psC('#22d3ee','#0891b2');ctx.fillRect(W-R+4,ly2-8,tw2+8,16);
    ctx.fillStyle=psC('#0b1226','#ffffff');ctx.fillText(tag,W-R+8,ly2+4);
    ctx.restore();
  }
  [CANDHOV,CANDSEL].forEach(function(idx,layer){
    if(idx<0||idx>=candles.length)return;var g=CANDGEOM[idx],k=candles[idx],col=k.c>=k.o?'#22c55e':'#ef4444';
    if(layer===0){ctx.strokeStyle=psC('rgba(255,255,255,.25)','rgba(15,23,42,.35)');ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(g.x,T);ctx.lineTo(g.x,H-B);ctx.stroke();ctx.setLineDash([]);}
    else{ctx.save();ctx.shadowColor=col;ctx.shadowBlur=12;ctx.strokeStyle=psC('#ffffff','#0f172a');ctx.lineWidth=1.5;ctx.strokeRect(g.x-g.bw/2-2,g.top-2,g.bw+4,Math.max(4,g.bot-g.top)+4);ctx.restore();}
  });
  ctx.fillStyle=psC('#9aa6bc','#475569');ctx.textAlign='left';ctx.fillText(RGLBL, L, 12);
  /* TA Stage 2: publish the geometry (inset x positions from CANDGEOM) and
     draw the overlays — here, not at the call site, so hover redraws
     (redrawCandles) repaint the overlays too. */
  TAGEOM={kind:'candles-range',xs:CANDGEOM.map(function(g){return g.x;}),yFor:Y,log:false,closes:candles.map(function(k){return k.c;}),times:candles.map(function(k){return k.t;}),n:candles.length,W:W,H:H,pad:{l:L,r:R,t:T,b:B},plotW:iw,plotH:ih};
  taAfterDraw('candles-range');
  bindCandListeners(c);
  FALLBACK_NOTE='';
  return true;
}
/* Candle ranges, Day 2: extended daily candles for YTD and 1Y.
   Coinbase's no-window daily fetch returns only ~300 candles, but YTD late
   in the year needs up to 365 days and 1Y needs 366 — so those two ranges
   fetch in batched windows (<=250 days each, start/end params), deduped by
   timestamp and sorted oldest-first. If ANY window fails, the whole extended
   fetch fails and the view falls back to the line (never a partial window
   silently presented as the full range). CBEXT_ERR is sticky for the session
   so a failed fetch is not hammered on every redraw. */
var CBEXT=null,CBEXT_P=null,CBEXT_P_DAYS=0,CBEXT_ERR=false,CBEXT_DAYS=0;
function fetchDailyWindow(startMs,endMs){
  var s=new Date(startMs).toISOString(),e=new Date(endMs).toISOString();
  return fetch('https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400&start='+s+'&end='+e,{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(function(j){
    if(!Array.isArray(j))throw new Error('bad candles');
    return j.map(function(c){return {t:c[0]*1000,o:c[3],h:c[2],l:c[1],c:c[4]};}).filter(function(p){return isFinite(p.c)&&p.c>0&&isFinite(p.o)&&isFinite(p.h)&&isFinite(p.l);});
  });
}
/* Pure merge for batched daily windows: dedupe by timestamp (later window
   wins on a shared boundary day), sort oldest-first. Extracted so the
   headless harness can check it without fetching anything. */
function mergeDailyCandles(chunks){
  var m={};chunks.forEach(function(arr){arr.forEach(function(p){m[p.t]=p;});});
  return Object.keys(m).sort(function(a,b){return a-b;}).map(function(k){return m[k];});
}
function loadExtendedDaily(days){
  if(CBEXT&&CBEXT_DAYS>=days)return Promise.resolve(CBEXT);
  /* Fix 29 Oct 2026 (browser test, Day 2): a smaller extended fetch already
     in flight must NOT satisfy a larger request — previously drawRange
     never re-called this once CBEXT existed at all, so a YTD-sized set was
     silently presented as 1Y. If a smaller fetch is pending, chain onto it
     and then fetch the larger window; the chained handler runs after the
     original settle handler has cleared CBEXT_P, so the second call starts
     a real fetch instead of returning the small promise. */
  if(CBEXT_P){
    if(CBEXT_P_DAYS>=days)return CBEXT_P;
    return CBEXT_P.then(function(){return loadExtendedDaily(days);});
  }
  var now=Date.now(),chunk=250*864e5,parts=[],s=now-days*864e5;
  while(s<now){var e=Math.min(now,s+chunk);parts.push(fetchDailyWindow(s,e));s=e;}
  CBEXT_P_DAYS=days;
  CBEXT_P=Promise.all(parts).then(function(chunks){
    CBEXT=mergeDailyCandles(chunks);
    CBEXT_DAYS=days;CBEXT_P=null;CBEXT_P_DAYS=0;return CBEXT;
  },function(e){CBEXT_P=null;CBEXT_P_DAYS=0;CBEXT_ERR=true;throw e;});
  return CBEXT_P;
}
/* Rollover fix (21 Nov 2026): the daily candle sets (CBDAILY, CBEXT) were
   fetched once per page load, so a page left open across the UTC midnight
   (day close, Monday 00:00 UTC week close, 1st-of-month close) kept showing
   the old last bucket: live feel stopped (it only extends the CURRENT
   calendar bucket) and no new bucket ever appeared until a reload. When the
   newest daily candle is older than today (UTC), fetch the days since then
   (one small request) and merge them in; the new bucket then comes from
   Coinbase's own candle and live feel follows it as usual. Nothing is
   invented. If Coinbase has not published today's candle yet, retry at most
   every 2 minutes until it has; once it has, no more requests until the
   next UTC midnight. A failed refetch keeps the current candles. */
var ROLL_AT=0,ROLL_P=false;
function rollStale(a){return !!(a&&a.length)&&Math.floor(a[a.length-1].t/864e5)<Math.floor(Date.now()/864e5);}
function rollRefetch(){
  if(ROLL_P||Date.now()-ROLL_AT<120000)return;
  var lasts=[CBDAILY,CBEXT].filter(function(a){return a&&a.length;}).map(function(a){return a[a.length-1].t;});
  if(!lasts.length)return;
  ROLL_AT=Date.now();ROLL_P=true;
  var e=Date.now(),s=Math.max(e-250*864e5,Math.min.apply(null,lasts));
  tf8('https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400&start='+new Date(s).toISOString()+'&end='+new Date(e).toISOString(),{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(function(j){
    ROLL_P=false;
    if(!Array.isArray(j))return;
    var fresh=j.map(function(c){return {t:c[0]*1000,o:c[3],h:c[2],l:c[1],c:c[4]};}).filter(function(p){return isFinite(p.c)&&p.c>0&&isFinite(p.o)&&isFinite(p.h)&&isFinite(p.l);});
    if(!fresh.length)return;
    var cur=(rng==='YTD'||rng==='1Y'||rng==='5Y'||rng==='10Y'||rng==='Max')?CBEXT:CBDAILY,before=cur&&cur.length?cur[cur.length-1].t:0;
    if(CBDAILY)CBDAILY=mergeDailyCandles([CBDAILY,fresh]);
    if(CBEXT)CBEXT=mergeDailyCandles([CBEXT,fresh]);
    cur=(rng==='YTD'||rng==='1Y'||rng==='5Y'||rng==='10Y'||rng==='Max')?CBEXT:CBDAILY;
    if(dlg&&!dlg.hidden&&CANDLE_RANGES.indexOf(rng)>=0&&RGCT==='candles'&&!(rng==='1W'&&RGGRAN==='4h')&&cur&&cur.length&&cur[cur.length-1].t>before)draw();
  }).catch(function(){ROLL_P=false;});
}
/* 4-hour candles for 1W (4 Nov 2026): Coinbase does NOT offer a 4h
   granularity (it rejects 14400 as unsupported — verified 4 Nov),
   so this fetches 1h bars (8 days, 192 bars, under the 300-bar
   limit) and aggregates them into UTC-aligned 4h buckets, keeping
   only complete buckets, last 42 (= 7 days). Same candle array
   shape as the daily fetch: [time, low, high, open, close, volume].
   Cache is 5 minutes; a failed fetch is sticky for the session (CB4H_ERR)
   so a dead feed falls back once to the line instead of being hammered
   on every redraw — same pattern as the YTD extended fetch. */
var CB4H=null,CB4H_AT=0,CB4H_ERR=false;
function agg4hFromHourly(hourly){
  var buckets={},order=[];
  hourly.forEach(function(b){
    var key=Math.floor(b.t/14400000)*14400000;
    if(!buckets[key]){buckets[key]=[];order.push(key);}
    buckets[key].push(b);
  });
  var out=[];
  order.sort(function(a,b){return a-b;}).forEach(function(key){
    var seg=buckets[key];
    if(seg.length<4)return;
    out.push({t:key,end:key+14400000,o:seg[0].o,h:Math.max.apply(null,seg.map(function(x){return x.h;})),l:Math.min.apply(null,seg.map(function(x){return x.l;})),c:seg[seg.length-1].c});
  });
  return out.slice(-42);
}
function load4h(){
  var now=Date.now(),start=new Date(now-8*864e5).toISOString(),end=new Date(now).toISOString();
  return fetch('https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600&start='+start+'&end='+end,{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(function(j){
    if(!Array.isArray(j))throw new Error('bad candles');
    var hourly=j.map(function(c){return {t:c[0]*1000,o:c[3],h:c[2],l:c[1],c:c[4]};}).filter(function(p){return isFinite(p.c)&&p.c>0&&isFinite(p.o)&&isFinite(p.h)&&isFinite(p.l);}).sort(function(a,b){return a.t-b.t;});
    var bars=agg4hFromHourly(hourly);
    if(bars.length<2)throw new Error('too few candles');
    CB4H=bars;CB4H_AT=Date.now();return bars;
  }).catch(function(e){CB4H_ERR=true;throw e;});
}
function syncCg(){
  var cg=$('bcCg');if(!cg)return;
  var candlesOn=CANDLE_RANGES.indexOf(rng)>=0&&RGCT==='candles';
  [].forEach.call(cg.querySelectorAll('[data-cg]'),function(b){b.classList.toggle('on',b.dataset.cg===RGCT);b.setAttribute('aria-pressed',b.dataset.cg===RGCT);});
  var granAllowed=rng==='1M'?['weekly','daily']:(rng==='3M'||rng==='6M'||rng==='YTD')?['monthly','weekly','daily']:(rng==='1Y')?['monthly','weekly']:(rng==='1W'?['daily','4h']:(rng==='5Y'?['yearly','monthly','weekly','daily']:(rng==='10Y'?['yearly','monthly','daily']:(rng==='Max'?['yearly','monthly','weekly','daily']:[]))));
  var gl=$('bcCgGranLab');if(gl)gl.style.display=candlesOn&&granAllowed.length?'':'none';
  [].forEach.call(cg.querySelectorAll('[data-cggran]'),function(b){var show=candlesOn&&granAllowed.indexOf(b.dataset.cggran)>=0;b.style.display=show?'':'none';b.classList.toggle('on',b.dataset.cggran===RGGRAN);b.setAttribute('aria-pressed',b.dataset.cggran===RGGRAN);});
}
/* Must-fix (27 Nov 2026): the reason for a candle→Line fallback, kept
   across redraws — drawDaily rewrites bcRr/bcNt on every draw, so a
   one-off append vanished on the next live tick and the reset looked
   silent. Set by fallback() (and the 1D intraday catch); cleared when
   the range changes or a candle draw succeeds. */
var FALLBACK_NOTE='';
function drawRange(){
  head();
  [].forEach.call($('bcRg').querySelectorAll('[data-r]'),function(b){b.classList.toggle('on',b.dataset.r===rng);b.setAttribute('aria-pressed',b.dataset.r===rng);});
  $('bcSc').style.display='none';
  /* Candles are BTC-only, same rule as the 1D view: the S&P 500 / Gold / MSTR
     buttons are greyed for the candle view and their line behaviour is untouched. */
  var sb=$('bcSpx');if(sb){sb.setAttribute('aria-pressed','false');sb.classList.add('off');$('bcSpxT').textContent='+ S&P 500';sb.setAttribute('aria-label','S&P 500 unavailable for candle view');}
  var gb=$('bcGld');if(gb){gb.setAttribute('aria-pressed','false');gb.classList.add('off');$('bcGldT').textContent='+ Gold';gb.setAttribute('aria-label','Gold unavailable for candle view');}
  var mb=$('bcMstr');if(mb){mb.setAttribute('aria-pressed','false');mb.classList.add('off');$('bcMstrT').textContent='+ MSTR';mb.setAttribute('aria-label','MSTR unavailable for candle view');}
  /* First-time candles for a range must use that range's default, even if
     RGGRAN was left over from another range or from the initial load.
     (History: the 29 Oct 2026 fix added this backstop when 1M's default
     was Weekly — a stale 'daily' initial value survived the Line->Candles
     switch and won. Since 21 Nov 2026 the default IS the finest size,
     so a first-visit Daily on 1M is correct, not stale.)
     This first-visit rule is the backstop: the first candle draw for a range
     in this session always uses that range's default, whatever RGGRAN
     was before. After that first draw RGSEEN[rng] is set, so a
     user-picked valid size is preserved across Line<->Candles switches;
     range-tab clicks reset to the default independently. */
  var allowed=rng==='1M'?['weekly','daily']:(rng==='3M'||rng==='6M'||rng==='YTD')?['monthly','weekly','daily']:(rng==='1Y')?['monthly','weekly']:(rng==='1W'?['daily','4h']:(rng==='5Y'?['yearly','monthly','weekly','daily']:(rng==='10Y'?['yearly','monthly','daily']:(rng==='Max'?['yearly','monthly','weekly','daily']:[]))));
  if(!RGSEEN[rng]){RGGRAN=defaultGran(rng);RGSEEN[rng]=true;}
  if(allowed.length&&allowed.indexOf(RGGRAN)<0)RGGRAN=defaultGran(rng);
  syncCg();
  var fallback=function(msg){/* Job 5: the chart falls back to Line here,
    so the type state must say Line too — before, RGCT stayed 'candles'
    while the chart showed Line, and the menu/pill ticks lied about the
    current type. The user can re-pick Candles to retry the load.
    Must-fix (27 Nov 2026): the reason is stored (FALLBACK_NOTE) and
    re-appended by drawDaily on every draw, to the note AND to the header
    (bcRr), which is always in view — the old one-off append to bcNt
    vanished on the next live tick, and bcNt sits below the fold in the
    popover, so the reset looked silent. */
    FALLBACK_NOTE=msg;RGCT='line';drawDaily();syncCg();};
  if(rng==='1W'&&RGGRAN==='4h'){
    if(!CB4H||Date.now()-CB4H_AT>5*60*1000){
      if(CB4H_ERR){RGGRAN='daily';clearCandState();fallback('Coinbase 4-hour candles unavailable — showing daily closes. Re-pick Candles to retry.');return;}
      $('bcRr').textContent='Loading 4-hour candles…';
      load4h().then(function(){if(dlg&&!dlg.hidden&&rng==='1W'&&RGCT==='candles')draw();}).catch(function(){if(dlg&&!dlg.hidden)draw();});
      return;
    }
    var cand4=CB4H.slice();
    if(cand4.length<2){RGGRAN='daily';clearCandState();fallback('Not enough 4-hour candles — showing daily closes. Re-pick Candles to retry.');return;}
    RGCAND=cand4;RGLBL='1W · 4-hour candles';
    var a04=cand4[0].o,b04=cand4[cand4.length-1].c,pc04=(b04/a04-1)*100;
    $('bcRr').textContent='1W: BTC '+((pc04>=0?'+':'')+pc04.toFixed(2)+'%')+' · '+cand4.length+' 4-hour candles, from '+new Date(cand4[0].t).toLocaleDateString('en-US',{timeZone:'UTC',month:'short',day:'numeric'})+' ('+fmt(a04)+')';
    $('bcNt').textContent='Coinbase 4-hour candles (UTC), in 4-hour blocks. Green = close above open, Red = below. Tap a candle for its High, Low and Change. Last candle is the latest complete 4-hour block; today\'s live price is not a candle. S&P 500, Gold and MSTR toggles are off for candle view.';
    clearLineChart();
    CANDSEL=-1;CANDHOV=-1;drawCandlesRange();return;
  }

  var win,cut;
  if(rng==='YTD'||rng==='1Y'||rng==='5Y'||rng==='10Y'||rng==='Max'){
    /* Day 2: these ranges need MORE than Coinbase's ~300-candle default
       window (YTD late in the year needs up to 365 days, 1Y needs 366), so
       they use the batched extended fetch, not CBDAILY. Job 9 (22 Nov
       2026): 5Y (1827 days, 8 windows) and 10Y (3653 days, 15 windows)
       join them — same batched pattern, just more windows. Job 11
       (22 Nov 2026): Max joins them too — days back to the first daily
       close (2010-08-18, ~24 windows), the whole history.
       Fix 29 Oct 2026 (browser test): coverage is checked against the
       RANGE, not just "is CBEXT set". Previously, visiting YTD first left
       CBEXT holding only the ~302-day YTD window, and switching to 1Y then
       skipped the load entirely (CBEXT was truthy) and filtered that YTD
       window by the 1Y cut — presenting the YTD set as 1Y, with no loading
       state and no Oct–Dec 2025 candles. A set that is too short for the
       requested range is now treated exactly like no set: it loads the
       larger window (with its own "Loading 1-year candles…" state), and if
       the larger fetch has failed it falls back to the line rather than
       silently presenting the short set as the full range. */
    /* Job 11 (22 Nov 2026): Max needs days back to the first daily
       close in DATA (2010-08-18), not a DAYS entry — and no cut, so
       the window is the whole extended set. */
    var need;
    if(rng==='YTD')need=Math.ceil((Date.now()-Date.UTC(new Date().getUTCFullYear(),0,1))/864e5);
    else if(rng==='Max'){var firstDay=(DATA&&DATA.length)?DATA[0][0]:'2010-08-18';need=Math.ceil((Date.now()-Date.parse(firstDay+'T00:00:00Z'))/864e5);}
    else need=DAYS[rng];
    if(!CBEXT||CBEXT_DAYS<need){
      if(CBEXT_ERR){fallback('Extended Coinbase candles unavailable — showing daily closes. Re-pick Candles to retry.');return;}
      loadExtendedDaily(need).then(function(){if(dlg&&!dlg.hidden&&(rng==='YTD'||rng==='1Y'||rng==='5Y'||rng==='10Y'||rng==='Max')&&RGCT==='candles')draw();}).catch(function(){if(dlg&&!dlg.hidden)draw();});
      $('bcRr').textContent='Loading '+(rng==='YTD'?'year-to-date':rng==='1Y'?'1-year':rng==='5Y'?'5-year':rng==='10Y'?'10-year':'all-time')+' candles…';return;
    }
    cut=rng==='YTD'?Date.UTC(new Date().getUTCFullYear(),0,1):rng==='Max'?0:Date.now()-need*864e5;
    win=CBEXT.filter(function(p){return p.t>=cut;});
  }else{
    if(!CBDAILY||CBDAILY.length<2){fallback('Coinbase daily candles unavailable — showing daily closes. Re-pick Candles to retry.');return;}
    var days=rng==='1W'?7:(rng==='1M'?31:(rng==='3M'?92:183));
    cut=Date.now()-days*864e5;
    win=CBDAILY.filter(function(p){return p.t>=cut;});
  }
  /* Rollover fix: page open past UTC midnight -> fetch the new day(s). */
  if(rollStale((rng==='YTD'||rng==='1Y'||rng==='5Y'||rng==='10Y'||rng==='Max')?CBEXT:CBDAILY))rollRefetch();
  var cand=aggDailyCandles(win,RGGRAN);
  if(cand.length<2){fallback('Not enough daily candles — showing daily closes. Re-pick Candles to retry.');return;}
  // EXPERIMENTAL LIVE FEEL: when the last bucket IS the current calendar
  // bucket (daily: today's bar; weekly: this calendar week; monthly: this
  // calendar month), its close follows the live CoinGecko price and its
  // high/low extend to it — for display only. The current bucket is
  // detected by CALENDAR boundaries, not by the last constituent bar: a
  // stale feed whose last daily bar is Monday must still extend the
  // current week on Wednesday, and a last bar from last week must never
  // extend into a new week. Buckets that are not the current calendar
  // bucket are never extended and no new candle is invented (no rollover
  // candle). The 1D/4H candle views (complete buckets only) are unchanged.
  var disp=cand.slice(), RGLIVE2=false;
  if(live.usd!=null&&disp.length){
    var lb=disp[disp.length-1], nd=new Date();
    var contains=false;
    if(RGGRAN==='daily'){
      var todayUTC=Date.UTC(nd.getUTCFullYear(),nd.getUTCMonth(),nd.getUTCDate());
      contains=(lb.t===todayUTC);
    }else if(RGGRAN==='weekly'){
      // Calendar week (Monday-start, UTC) of today vs of the bucket's
      // first day. The bucket's first day is in the same calendar week
      // as its last day (weekly buckets never span weeks).
      var dow=nd.getUTCDay();
      var todayMon=Date.UTC(nd.getUTCFullYear(),nd.getUTCMonth(),nd.getUTCDate()-(dow===0?6:dow-1));
      var lbD=new Date(lb.t), lbDow=lbD.getUTCDay();
      var lbMon=Date.UTC(lbD.getUTCFullYear(),lbD.getUTCMonth(),lbD.getUTCDate()-(lbDow===0?6:lbDow-1));
      contains=(lbMon===todayMon);
    }else if(RGGRAN==='monthly'){
      // Calendar month of the bucket's first day vs today. Monthly
      // buckets never span months, so the first day's month is the
      // bucket's month.
      var lbM=new Date(lb.t);
      contains=(lbM.getUTCFullYear()===nd.getUTCFullYear()&&lbM.getUTCMonth()===nd.getUTCMonth());
    }else if(RGGRAN==='yearly'){
      // Calendar year of the bucket's first day vs today. Yearly
      // buckets never span years, so the first day's year is the
      // bucket's year. (Job 9, 22 Nov 2026.)
      var lbY=new Date(lb.t);
      contains=(lbY.getUTCFullYear()===nd.getUTCFullYear());
    }
    if(contains){
      disp[disp.length-1]={t:lb.t,end:lb.end,o:lb.o,h:Math.max(lb.h,live.usd),l:Math.min(lb.l,live.usd),c:live.usd};
      RGLIVE2=true;
    }
  }
  RGLIVE=RGLIVE2;
  RGCAND=disp;RGLBL=rng+' · '+RGGRAN+' candles';
  var a0=disp[0].o,b0=disp[disp.length-1].c,pc0=(b0/a0-1)*100;
  $('bcRr').textContent=rng+': BTC '+((pc0>=0?'+':'')+pc0.toFixed(2)+'%')+' · '+disp.length+' '+RGGRAN+' candles, from '+new Date(disp[0].t).toLocaleDateString('en-US',{timeZone:'UTC',month:'short',day:'numeric'})+' ('+fmt(a0)+')'+cadTag();
  var aggTxt=RGGRAN==='monthly'?'by calendar month (UTC)':(RGGRAN==='weekly'?'by Monday-start UTC week':RGGRAN==='yearly'?'by calendar year (UTC)':'by day');
  $('bcNt').textContent='Coinbase daily candles (UTC days), aggregated '+aggTxt+'. Green = close above open, Red = below. Tap a candle for its Open, High, Low, Close and Change. '+(RGLIVE?'Last candle is live — its close is the live price; this bucket closes in '+bucketCloseCountdown(RGGRAN)+'.':'Last candle is the latest complete UTC day; today\'s live price is not a candle.')+' S&P 500, Gold and MSTR toggles are off for candle view only.';
  clearLineChart();
  CANDSEL=-1;CANDHOV=-1;
  var cc=$('bcC');if(cc){cc.style.transition='opacity .3s ease';cc.style.opacity='0';requestAnimationFrame(function(){cc.style.opacity='1';});}
  drawCandlesRange();
}
function draw1D(){
  head();
  [].forEach.call($('bcRg').querySelectorAll('[data-r]'),function(b){b.classList.toggle('on',b.dataset.r===rng);b.setAttribute('aria-pressed',b.dataset.r===rng);});
  $('bcSc').style.display='none';
  /* Job 10: the compare toggles work on 1D Line (intraday compare);
     they stay off on 1D candles (BTC-only, same as the range candle
     views). The SHOW* state is preserved across ranges, so a toggle
     left on for a range view carries into 1D Line. */
  if(CT==='line'){
    var sb=$('bcSpx');if(sb){sb.setAttribute('aria-pressed',SHOWSPX?'true':'false');sb.classList.toggle('off',!SHOWSPX);$('bcSpxT').textContent=SHOWSPX?'S&P 500 ✕':'+ S&P 500';sb.setAttribute('aria-label',SHOWSPX?'Hide S&P 500':'Show S&P 500');}
    var gb=$('bcGld');if(gb){gb.setAttribute('aria-pressed',SHOWGLD?'true':'false');gb.classList.toggle('off',!SHOWGLD);$('bcGldT').textContent=SHOWGLD?'Gold ✕':'+ Gold';gb.setAttribute('aria-label',SHOWGLD?'Hide Gold':'Show Gold');}
    var mb=$('bcMstr');if(mb){mb.setAttribute('aria-pressed',SHOWMSTR?'true':'false');mb.classList.toggle('off',!SHOWMSTR);$('bcMstrT').textContent=SHOWMSTR?'MSTR ✕':'+ MSTR';mb.setAttribute('aria-label',SHOWMSTR?'Hide MSTR':'Show MSTR');}
  }else{
    var sb=$('bcSpx');if(sb){sb.setAttribute('aria-pressed','false');sb.classList.add('off');$('bcSpxT').textContent='+ S&P 500';sb.setAttribute('aria-label','S&P 500 unavailable for 1D candles');}
    var gb=$('bcGld');if(gb){gb.setAttribute('aria-pressed','false');gb.classList.add('off');$('bcGldT').textContent='+ Gold';gb.setAttribute('aria-label','Gold unavailable for 1D candles');}
    var mb=$('bcMstr');if(mb){mb.setAttribute('aria-pressed','false');mb.classList.add('off');$('bcMstrT').textContent='+ MSTR';mb.setAttribute('aria-label','MSTR unavailable for 1D candles');}
  }
  var ct=$('bcCt');if(ct){[].forEach.call(ct.querySelectorAll('[data-ct]'),function(b){b.classList.toggle('on',b.dataset.ct===CT);b.setAttribute('aria-pressed',b.dataset.ct===CT);});}
  var cg1=$('bcCg');if(cg1)syncCg();
  if(!INTRA){
    $('bcRr').textContent='Loading intraday…';
    getIntraday().then(function(){if(dlg&&!dlg.hidden&&rng==='1D')draw1D();}).catch(function(){if(dlg&&!dlg.hidden){/* Job 5: intraday failed, the chart falls back to Line — the type state must say Line too, so the menu/pill ticks match the drawing. Must-fix (27 Nov 2026): the reason is stored (FALLBACK_NOTE) and re-appended by drawDaily, so it survives the next redraw. */CT='line';FALLBACK_NOTE='Intraday unavailable — showing daily closes.';drawDaily();}});
    return;
  }
  if(Date.now()-INTRA_AT>5*60*1000&&!intraP){getIntraday().then(function(){if(dlg&&!dlg.hidden&&rng==='1D')draw1D();}).catch(function(){});}
  var pts=INTRA.pts.slice(),hasLive=live.usd!=null;
  if(CT!=='line'){
    var per=CT==='1h'?4:16, cand=aggCandles(pts,per);
    if(cand.length>=2 && cand[0].o!=null){
      var a0=cand[0].o, b0=cand[cand.length-1].c, pc0=(b0/a0-1)*100;
      $('bcRr').textContent='1D: BTC '+((pc0>=0?'+':'')+pc0.toFixed(2)+'%')+' · last 24 hours, '+CT+' candles, from '+etTime(cand[0].t)+' ET ('+fmt(a0)+')'+cadTag();
      $('bcNt').textContent='Coinbase '+CT+' candles, last 24 hours (ET). Green = close above open, Red = below. Tap a candle for its Open, High, Low, Close and Change. S&P 500, Gold and MSTR toggles are off for 1D candles.';
      clearLineChart();
      CANDSEL=-1;CANDHOV=-1;drawCandles1D(cand, CT==='1h'?'1-hour candles':'4-hour candles', per);
      return;
    }
  }
  /* Line view: any open candle pill/selection from the candle view is gone,
     and nothing here repaints candles (see fix note at candViewActive).
     Job 5: if we got here with CT set to candles, too few candles formed
     to draw — the chart is Line, so the type state must say Line too,
     or the menu/pill ticks lie about the current type. */
  if(CT!=='line')CT='line';
  clearCandState();
  /* Job 10: 1D Line compare — a toggle on draws the intraday compare
     when the file is ready; while it loads (or when it is stale) the
     chart is BTC-only this pass and redraws when the file lands. */
  if(SHOWSPX||SHOWGLD||SHOWMSTR){
    if(!CMPINTRA){
      getCmpIntraday().then(function(){if(dlg&&!dlg.hidden&&rng==='1D'&&CT==='line')draw1D();}).catch(function(){});
    }else if(draw1DCmp(pts)){
      return;
    }
  }
  if(hasLive&&pts.length&&Date.now()>pts[pts.length-1].t)pts.push({t:Date.now(),v:live.usd,live:true});
  var n=pts.length,a=pts[0].v,b=pts[n-1].v,pc=(b/a-1)*100;
  var fp=function(x){return (x>=0?'+':'')+(Math.abs(x)>=1e4?Math.round(x).toLocaleString('en-US'):x.toFixed(1))+'%';};
  $('bcRr').textContent='1D: BTC '+fp(pc)+' · last 24 hours, from '+etTime(pts[0].t)+' ET ('+fmt(a)+')'+cadTag();
  $('bcNt').textContent='Intraday '+(INTRA.src==='coingecko'?'CoinGecko 1-day chart (Coinbase unavailable)':'Coinbase 15-minute candles')+', last 24 hours (ET); last point is the live price.'+((SHOWSPX||SHOWGLD||SHOWMSTR)?' Compare data unavailable — showing BTC only.':'');
  /* Native 1D line (Chart.js removed 20 Nov 2026; no fallback library). */
  var nativeOK=draw1DNative(pts);lineDrawn=nativeOK;
  if(nativeOK)lineRetry=false;else lineFail();
}

/* Job 10: the 1D Line compare draw. Trims BTC to the session window,
   aligns the three series, rebases all to 100 at the window open, and
   draws via draw1DNative. No live point (complete 15-min buckets only,
   for all four series). Returns true when it drew, false when the
   caller should draw BTC-only instead (too few points, or no usable
   compare series). */
function draw1DCmp(pts){
  var doc=CMPINTRA;
  if(!doc)return false;
  var fresh=CmpIntraMath.isFresh(doc,Date.now());
  if(!fresh.ok)return false;
  var session=doc.session;
  var tpts=CmpIntraMath.trimToSession(pts,session);
  if(tpts.length<2)return false;
  var btcV=tpts.map(function(p){return p.v;});
  var b0=CmpIntraMath.firstValue(btcV);
  var S=SHOWSPX?CmpIntraMath.alignToPts(tpts,(doc.symbols.SPX||{}).bars):null;
  var G=SHOWGLD?CmpIntraMath.alignToPts(tpts,(doc.symbols.GOLD||{}).bars):null;
  var M=SHOWMSTR?CmpIntraMath.alignToPts(tpts,(doc.symbols.MSTR||{}).bars):null;
  /* Must-fix (27 Nov 2026): the compare bars end at the session close
     (1 PM on an early-close day) but BTC runs to 4 PM — hold each
     series flat from its last bar to the right edge, so the line does
     not stop at ~1 PM. */
  S=S?CmpIntraMath.holdFlat(S):null;
  G=G?CmpIntraMath.holdFlat(G):null;
  M=M?CmpIntraMath.holdFlat(M):null;
  var s0=CmpIntraMath.firstValue(S),g0=CmpIntraMath.firstValue(G),m0=CmpIntraMath.firstValue(M);
  var sx=(S&&s0)||(G&&g0)||(M&&m0);
  if(!sx||!b0)return false;
  var fp=function(x){return (x>=0?'+':'')+(Math.abs(x)>=1e4?Math.round(x).toLocaleString('en-US'):x.toFixed(1))+'%';};
  /* A series whose last slot is null (a missing bar) reports its last
     available value instead of null. */
  function lastPct(arr,base){if(!arr||!base)return null;for(var i=arr.length-1;i>=0;i--){if(arr[i]!=null)return (arr[i]/base-1)*100;}return null;}
  var n=tpts.length,pc=(btcV[n-1]/b0-1)*100;
  var spc=lastPct(S,s0),gpc=lastPct(G,g0),mpc=lastPct(M,m0);
  var lastSession=fresh.reason==='last session';
  $('bcRr').textContent='1D: BTC '+fp(pc)+(spc!=null?' · S&P 500 '+fp(spc):'')+(gpc!=null?' · Gold '+fp(gpc):'')+(mpc!=null?' · MSTR '+fp(mpc):'')+' · '+(CmpIntraMath.isEarlyClose(session)?'9:30 AM-1 PM ET':'9:30 AM-4 PM ET')+(lastSession?' (last session '+session+')':'')+cadTag();
  $('bcNt').textContent='1D compare: % change from the 9:30 AM ET open (BTC Coinbase 15-minute candles; S&P 500 ^GSPC, Gold GC=F, MSTR — Yahoo 15-minute bars, rebased to 100 at the open). All lines are complete 15-minute closes; the live price is not plotted while comparing.'+(lastSession?' Showing the last session ('+session+').':'');
  var nativeOK=draw1DNative(tpts,{sx:true,S:S,G:G,M:M,s0:s0,g0:g0,m0:m0,hasLive:false});lineDrawn=nativeOK;
  if(nativeOK)lineRetry=false;else lineFail();
  return nativeOK;
}

/* Range-row scroll hint, 29 Oct 2026: tabs run shortest (1D) to longest (Max) left to right, so on a phone the longer ranges sit off-screen to the right and are reached by swiping left. The hint shows only while there is still more to the right. */
function syncRgHint(){var rs=$('bcRgs'),h=$('bcRgHint');if(!rs||!h)return;var moreRight=rs.scrollWidth-rs.clientWidth-rs.scrollLeft>8;h.style.display=moreRight?'':'none';}
function draw(){if(rng==='1D'){draw1D();}else if(CANDLE_RANGES.indexOf(rng)>=0&&RGCT==='candles'){drawRange();}else{drawDaily();}syncTypePill();syncRgHint();}

function onK(K,M,d){var lo=0,hi=K.length-1,a=-1;while(lo<=hi){var mid=(lo+hi)>>1;if(K[mid]<=d){a=mid;lo=mid+1;}else hi=mid-1;}return a<0?null:M[K[a]];}
function spxOn(d){return onK(SPXK,SPX,d);}function gldOn(d){return onK(GOLDK,GOLD,d);}function mstrOn(d){return onK(MSTRK,MSTR,d);}
function getData(){if(dataP)return dataP;
  var st=tf8(U('../data/btc-daily.json')).then(function(r){return r.json();}); /* Batch B bug 12: 8s abort */
  var sx=tf8(U('../data/spx-daily.json')).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
  var gx=tf8(U('../data/gold-daily.json')).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
  var mx=tf8(U('../data/mstr-daily.json')).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
  var hj=tf8(RAW+'?t='+Date.now(),{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
  var cb=tf8('https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400',{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
  dataP=Promise.all([st,hj,cb,sx,gx,mx]).then(function(r){var m={},s=r[0].d,end=r[0].end;s.forEach(function(p){m[p[0]]=p[1];});
    var today=new Date().toISOString().slice(0,10);
    if(Array.isArray(r[2]))r[2].forEach(function(c){var d=new Date(c[0]*1000).toISOString().slice(0,10);if(d>end&&d<today)m[d]=c[4];});
    if(r[1]&&r[1].closes){for(var d in r[1].closes){var v=r[1].closes[d].BTC;if(d>end&&v!=null)m[d]=v;}PROV=(r[1].btc_provisional||[]).length>0;}
    DATA=Object.keys(m).sort().map(function(d){return [d,m[d]];});
    /* Candle ranges, Day 1: keep the Coinbase daily OHLC this time, not just the
       close — getData already fetched it, and the range candle view needs it.
       Coinbase returns [time, low, high, open, close, volume]; sorted oldest first. */
    if(Array.isArray(r[2]))CBDAILY=r[2].map(function(c){return {t:c[0]*1000,o:c[3],h:c[2],l:c[1],c:c[4]};}).filter(function(p){return isFinite(p.c)&&p.c>0&&isFinite(p.o)&&isFinite(p.h)&&isFinite(p.l);}).sort(function(a,b){return a.t-b.t;});else CBDAILY=null;
    /* S&P 500: ^GSPC static closes; newer sessions extended by SPY % moves from history.json (used only for % change) */
    SPX={};if(r[3]&&r[3].d){var sd=r[3].d,se=r[3].end,lv=sd[sd.length-1][1];sd.forEach(function(p){SPX[p[0]]=p[1];});
      var hc=r[1]&&r[1].closes,spy0=hc&&hc[se]&&hc[se].SPY;if(spy0){Object.keys(hc).sort().forEach(function(d){if(d>se&&hc[d].SPY!=null)SPX[d]=lv*hc[d].SPY/spy0;});}
      SPXK=Object.keys(SPX).sort();}
    /* Gold: GC=F static closes; newer sessions extended by GLD % moves from history.json (used only for % change) */
    GOLD={};if(r[4]&&r[4].d){var gd=r[4].d,ge=r[4].end,gl=gd[gd.length-1][1];gd.forEach(function(p){GOLD[p[0]]=p[1];});
      var hc2=r[1]&&r[1].closes,g0=hc2&&hc2[ge]&&hc2[ge].GLD;if(g0){Object.keys(hc2).sort().forEach(function(d){if(d>ge&&hc2[d].GLD!=null)GOLD[d]=gl*hc2[d].GLD/g0;});}
      GOLDK=Object.keys(GOLD).sort();}
    /* MSTR: static daily closes (Yahoo, split-adjusted, back to 2010-08-17); newer sessions extended by history.json MSTR actual closes */
    MSTR={};if(r[5]&&r[5].d){var md=r[5].d,me=r[5].end;md.forEach(function(p){MSTR[p[0]]=p[1];});
      var hc3=r[1]&&r[1].closes;if(hc3){Object.keys(hc3).sort().forEach(function(d){if(d>me&&hc3[d].MSTR!=null)MSTR[d]=hc3[d].MSTR;});}
    }else if(r[1]&&r[1].closes){Object.keys(r[1].closes).sort().forEach(function(d){if(r[1].closes[d].MSTR!=null)MSTR[d]=r[1].closes[d].MSTR;});}
    MSTRK=Object.keys(MSTR).sort();
    return DATA;});
  dataP.catch(function(){dataP=null;});return dataP;}
/* dialog */
var RANGES=['1D','1W','1M','3M','6M','YTD','1Y','5Y','10Y','Max'],DAYS={'1D':1,'1W':7,'1M':31,'3M':92,'6M':183,'1Y':366,'5Y':1827,'10Y':3653};
var rng='1D',LOG=false,dlg=null,dim=null,opener=null;
function isPhone(){return window.innerWidth<=640;}
/* Popover chart is Spot BTC only (owner decision 29 Oct 2026):
   the vehicle toggle was removed from this popover. The tracker
   BITCOIN VEHICLE toggle (vehicle.js, under the BTC live pill) remains
   the sole vehicle control; it is not touched here. */
/* TA Stage 1 (20 Nov 2026): bridge for btcchart-ta.js. The TA module reads
   panel state through window.__BCTA and registers its after-draw hook there;
   the panel calls the hook after each native draw. Stage 1 draws nothing.
   The chart-type pill label is synced here (the panel owns the state), so it
   is right even before the TA script finishes loading. */
/* TA Stage 2 (20 Nov 2026): geometry + warm-up closes for the TA module.
   TAGEOM is set by each native renderer (x positions, y mapping, closes);
   the TA module reads it in afterDraw and draws the overlays on the same
   canvas, with the same mapping — so log scale is respected for free. */
var TAGEOM=null;
window.__BCTA={
  state:function(){return {rng:rng,CT:CT,RGCT:RGCT,RGGRAN:RGGRAN,CANDLE_RANGES:CANDLE_RANGES.slice(),defaultGran:defaultGran,candViewActive:candViewActive()};},
  dlg:function(){return dlg;},
  inline:function(){return INLINE;},
  stage:function(){try{return dlg&&dlg.closest?dlg.closest('.v4-stage'):null;}catch(e){return null;}},
  draw:draw,
  syncTypePill:syncTypePill,
  afterDraw:null,
  taTip:null,
  geom:function(){return TAGEOM;},
  cmp:function(){
    /* Job 10: a comparison is drawn on 1D Line too, when a toggle is on
       and the cmp-intraday file is loaded and fresh — TA hides there,
       as on the ranges. On 1D candles the toggles stay off, so no
       comparison is ever drawn and TA stays available. While the file
       loads the chart is BTC-only this pass, so cmp() is false until
       the compare actually draws (a sub-second loading state). */
    if(rng==='1D')return CT==='line'&&(SHOWSPX||SHOWGLD||SHOWMSTR)&&!!(CMPINTRA&&CmpIntraMath.isFresh(CMPINTRA,Date.now()).ok);
    if(CANDLE_RANGES.indexOf(rng)>=0&&RGCT==='candles')return false;
    return SHOWSPX||SHOWGLD||SHOWMSTR;
  },
  warmSync:taWarmSync,
  warmFetch:taWarmFetch
};
function taAfterDraw(kind){try{var h=window.__BCTA&&window.__BCTA.afterDraw;if(typeof h==='function')h(kind);}catch(e){}}
/* TA Stage 2 warm-up closes. Rule: draw each indicator only from its first
   valid point — never a wrong value. The warm-up is the closes BEFORE the
   visible window, so the first visible candle already has a valid value.
   - Range views: synchronous, from DATA (daily closes back to 2010, already
     in memory — zero extra fetch, zero first-load impact). Daily is
     identity; weekly/monthly aggregate DATA the same way aggDailyCandles
     does (Monday-start UTC weeks, calendar months), so the buckets line up
     with the visible candles exactly.
   - Intraday views (1D line, 1D 1h/4h candles, 1W 4h): lazy background
     fetch, only when TA is on (never blocks first paint). Until it lands,
     the overlays draw from the valid point inside the visible window; when
     it lands the fetch callback redraws. Cached per kind for the session;
     a failed fetch is sticky (closes=[]) so a dead feed is not hammered. */
function taWarmSync(){
  if(!DATA||!DATA.length)return [];
  if(rng==='1D')return [];
  var cut=null,gran=null;
  if(CANDLE_RANGES.indexOf(rng)>=0&&RGCT==='candles'){
    if(RGGRAN==='4h')return [];
    if(!RGCAND||!RGCAND.length)return [];
    cut=RGCAND[0].t;gran=RGGRAN;
  }else{
    var s=series();if(!s.length)return [];
    cut=Date.parse(s[0][0]+'T00:00:00Z');gran='daily';
  }
  /* Job 12: memoize — the DATA map/filter below re-parses the whole
     daily history (thousands of closes) on every call, and the panel
     now asks for the warm-up twice per draw (once for the axis
     expansion, once for the overlay draw), which pushed the phone
     all-on frame time over the 4 ms budget. The result only changes
     when the window (range/type/gran/cut) or the data moves, so cache
     it on those. Callers only read the array (computeVals concats it),
     so returning the same array is safe. */
  var _key=[rng,RGCT,RGGRAN,cut,DATA.length,DATA[DATA.length-1][1]].join('|');
  if(taWarmSync._k===_key&&taWarmSync._v)return taWarmSync._v;
  var daily=DATA.map(function(p){return {t:Date.parse(p[0]+'T00:00:00Z'),c:p[1]};}).filter(function(p){return p.t<cut;});
  if(!daily.length)return [];
  var out;
  if(gran==='daily')out=daily.slice(-250).map(function(p){return p.c;});
  else{var flat=daily.map(function(p){return {t:p.t,o:p.c,h:p.c,l:p.c,c:p.c};});out=aggDailyCandles(flat,gran).slice(-250).map(function(p){return p.c;});}
  taWarmSync._k=_key;taWarmSync._v=out;
  return out;
}
/* 4h bucketing for warm-up: mirrors agg4hFromHourly exactly (UTC-aligned
   4h buckets, complete buckets only) but returns ALL complete buckets,
   not just the last 42 — the warm-up needs up to 200. agg4hFromHourly
   itself is untouched (test_speed_option2 asserts its slice(-42)). */
function agg4hWarm(hourly){
  var buckets={},order=[];
  hourly.forEach(function(b){
    var key=Math.floor(b.t/14400000)*14400000;
    if(!buckets[key]){buckets[key]=[];order.push(key);}
    buckets[key].push(b);
  });
  var out=[];
  order.sort(function(a,b){return a-b;}).forEach(function(key){
    var seg=buckets[key];
    if(seg.length<4)return;
    out.push({t:key,end:key+14400000,o:seg[0].o,h:Math.max.apply(null,seg.map(function(x){return x.h;})),l:Math.min.apply(null,seg.map(function(x){return x.l;})),c:seg[seg.length-1].c});
  });
  return out;
}
var TAW={},TAW_H1=null,TAW_H1_P=null,TAW_RETRIED={}; /* TAW_RETRIED: kinds that already used their one Job 2 retry. */
function fetchHourlyWarm(){
  if(TAW_H1)return Promise.resolve(TAW_H1);
  if(TAW_H1_P)return TAW_H1_P;
  /* 50 days of 1h bars (5 x 10-day windows, 240 bars each, under the
     300-bar limit): enough for 200+ 4h warm-up closes even for the 1W 4h
     view, whose visible window already covers the last 7 days. */
  var now=Date.now(),parts=[],s=now-50*864e5;
  while(s<now){var e=Math.min(now,s+10*864e5);parts.push(tf8('https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600&start='+new Date(s).toISOString()+'&end='+new Date(e).toISOString(),{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}));s=e;}
  TAW_H1_P=Promise.all(parts).then(function(chunks){
    var all=[];
    chunks.forEach(function(j){if(Array.isArray(j))j.forEach(function(c){all.push({t:c[0]*1000,o:c[3],h:c[2],l:c[1],c:c[4]});});});
    all=all.filter(function(p){return isFinite(p.c)&&p.c>0&&isFinite(p.o)&&isFinite(p.h)&&isFinite(p.l);});
    TAW_H1=mergeDailyCandles([all]);TAW_H1_P=null;return TAW_H1;
  },function(e){TAW_H1_P=null;throw e;});
  return TAW_H1_P;
}
function taWarmFetch(kind,cb){
  var e=TAW[kind];
  if(e&&e.done){cb(e.closes);return;}
  if(e){e.cbs.push(cb);return;}
  e=TAW[kind]={cbs:[cb]};
  var finish=function(closes){
    TAW[kind]={done:true,closes:closes||[]};
    e.cbs.forEach(function(f){try{f(TAW[kind].closes);}catch(_){}});
  };
  var fail=function(){
    /* Job 2 (Indicator windows): a failed warm-up used to be sticky-empty
       for the session, so one transient failure (rate limit, network
       blip) left the indicators computed from the visible window alone
       until reload. Retry once after 10s; if that fails too, leave it
       empty. Bounded: at most two attempts per kind per session. On a
       successful retry, redraw so the corrected lines appear promptly. */
    finish([]);
    if(!TAW_RETRIED[kind]){
      TAW_RETRIED[kind]=true;
      setTimeout(function(){
        var e2=TAW[kind];
        if(e2&&e2.done&&(!e2.closes||!e2.closes.length)){
          delete TAW[kind];
          try{taWarmFetch(kind,function(c){if(c&&c.length){try{if(typeof draw==='function')draw();}catch(_){}}});}catch(_){}
        }
      },10000);
    }
  };
  if(kind==='1d-line'){
    /* 15-min closes for the 3 days before the visible 24h window (one
       request, 288 bars under the 300-bar limit). */
    var now=Date.now(),s=new Date(now-96*3600*1000).toISOString(),en=new Date(now-24*3600*1000).toISOString();
    tf8('https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=900&start='+s+'&end='+en,{cache:'no-store'})
      .then(function(r){if(!r.ok)throw new Error(r.status);return r.json();})
      .then(function(j){
        if(!Array.isArray(j))throw new Error('bad candles');
        var pts=j.map(function(c){return {t:c[0]*1000,c:c[4]};}).filter(function(p){return isFinite(p.c)&&p.c>0;}).sort(function(a,b){return a.t-b.t;});
        finish(pts.map(function(p){return p.c;}));
      }).catch(fail);
  }else{
    /* 1h bars for the last 50 days (paged, shared cache) — the 1h warm-up
       for 1D 1h candles, and the 4h warm-up (aggregated) for 1D 4h and
       1W 4h candles. Warm-up buckets must END before the visible window
       starts, so no hour is counted twice. */
    fetchHourlyWarm().then(function(hourly){
      var cut;
      if(kind==='candles-1d-1h'||kind==='candles-1d-4h')cut=Date.now()-24*3600*1000;
      else cut=(RGCAND&&RGCAND.length)?RGCAND[0].t:Date.now()-7*864e5;
      if(kind==='candles-1d-1h'){
        finish(hourly.filter(function(b){return b.t+3600000<=cut;}).map(function(b){return b.c;}).slice(-250));
      }else{
        var bars=agg4hWarm(hourly);
        finish(bars.filter(function(b){return b.end<=cut;}).map(function(b){return b.c;}).slice(-250));
      }
    }).catch(fail);
  }
}
function syncTypePill(){
  var b=$('taTyp');if(!b)return;
  var lab,dis=false;
  /* Job 11 (22 Nov 2026): Max is no longer Line-only — candles
     arrived there, so the pill works like any other range. */
  if(rng==='1D'){lab=CT==='line'?'Line':(CT==='1h'?'1H candles':'4H candles');}
  else if(RGCT!=='candles'){lab='Line';}
  else{lab=RGGRAN==='4h'?'4H candles':(RGGRAN==='daily'?'Candles \u00b7 Daily':RGGRAN==='weekly'?'Candles \u00b7 Weekly':RGGRAN==='yearly'?'Candles \u00b7 Yearly':'Candles \u00b7 Monthly');}
  var s=b.querySelector('span');if(s)s.textContent=lab;
  b.disabled=dis;b.setAttribute('aria-disabled',dis?'true':'false');
  b.setAttribute('aria-label','Chart type: '+lab);
}
var taLoaded=false;
function loadTA(){
  if(taLoaded)return;taLoaded=true;
  try{
    var l=document.createElement('link');l.rel='stylesheet';l.href=U('../css/btcchart-ta.css?v=ta18');document.head.appendChild(l);
    var s=document.createElement('script');s.src=U('btcchart-ta.js?v=ta18');
    s.onload=function(){try{if(window.__BTTA&&window.__BTTA.init)window.__BTTA.init(window.__BCTA);}catch(e){}};
    s.onerror=function(){taLoaded=false;};
    document.head.appendChild(s);
  }catch(e){taLoaded=false;}
}
function build(){dim=document.createElement('div');dim.className='bc-dim';dim.hidden=true;
  dlg=document.createElement('div');dlg.className=INLINE?'bc-w bc-inline':'bc-w';dlg.hidden=true;dlg.setAttribute('role','dialog');if(!INLINE)dlg.setAttribute('aria-modal','true');dlg.setAttribute('aria-labelledby','bcTitle');
  dlg.innerHTML='<div class="bc-grab" aria-hidden="true"></div><div class="bc-h"><div><span class="lp-lab" id="bcTitle"><span class="lp-dot" aria-hidden="true"></span>Live BTC · BTC/'+CUR.code+'</span><div class="bc-px"><span id="bcPx">—</span><span id="bcChg" class="hdr-chg"></span></div><div class="bc-rr" id="bcRr"></div></div><button type="button" class="bc-x" id="bcX" aria-label="Close BTC chart">✕</button></div>'
   +'<div class="bc-rg" id="bcRg"><div class="bc-rgs" id="bcRgs" role="group" aria-label="Chart range">'+RANGES.map(function(r){return '<button type="button" data-r="'+r+'">'+r+'</button>';}).join('')+'</div><span class="bc-rg-hint" id="bcRgHint" aria-hidden="true">\u2190 Swipe for longer ranges</span><span class="bc-sc" id="bcSc" role="group" aria-label="Scale"><button type="button" data-s="lin">Linear</button><button type="button" data-s="log">Log</button></span></div>'
   +'<div class="bc-row2" id="bcRow2"><div class="bc-lg" id="bcLg"><span class="bc-k bc-k-btc"><i aria-hidden="true"></i>BTC</span><button type="button" class="bc-k bc-k-spx" id="bcSpx" aria-pressed="false"><i aria-hidden="true"></i><span id="bcSpxT">+ S&amp;P 500</span></button><button type="button" class="bc-k bc-k-spx bc-k-gld" id="bcGld" aria-pressed="false"><i aria-hidden="true"></i><span id="bcGldT">+ Gold</span></button><button type="button" class="bc-k bc-k-spx bc-k-mstr" id="bcMstr" aria-pressed="false"><i aria-hidden="true"></i><span id="bcMstrT">+ MSTR</span></button></div><button type="button" class="ta-typ" id="taTyp" aria-haspopup="true" aria-expanded="false" aria-label="Chart type: Line"><span>Line</span><svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2 3.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button><button type="button" class="ta-pill" id="taPill" aria-haspopup="dialog" aria-expanded="false" aria-label="Technical analysis"><span>TA</span><svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2 3.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button></div><div class="bc-ct" id="bcCt" role="group" aria-label="1D chart type" style="display:none"><span class="bc-ct-lab">Chart</span><button type="button" data-ct="line">Line</button><button type="button" data-ct="1h">1H</button><button type="button" data-ct="4h">4H</button></div>'
   +'<div class="bc-ct" id="bcCg" role="group" aria-label="Range chart type" style="display:none"><span class="bc-ct-lab">Chart</span><button type="button" data-cg="line">Line</button><button type="button" data-cg="candles">Candles</button><span class="bc-ct-lab" id="bcCgGranLab" style="display:none">Size</span><button type="button" data-cggran="4h" style="display:none">4H</button><button type="button" data-cggran="daily" style="display:none">Daily</button><button type="button" data-cggran="weekly" style="display:none">Weekly</button><button type="button" data-cggran="monthly" style="display:none">Monthly</button><button type="button" data-cggran="yearly" style="display:none">Yearly</button></div>'
   +'<div class="bc-box"><canvas id="bcC" aria-label="BTC price chart" role="img"></canvas></div><div class="ta-rsi" id="taRsi" hidden><button type="button" class="ta-rsi-t" aria-expanded="true">RSI 14 <b>—</b><svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2 3.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button><canvas></canvas></div><div class="bc-nt" id="bcNt"></div><a class="bc-cl" href="'+U('../../clock/index.html')+'">Live BTC chart →</a><a class="bc-cl" href="'+U('../../screener.html')+'">The Desk →</a>';
  if(INLINE)INLINEHOST.appendChild(dlg);else{document.body.appendChild(dim);document.body.appendChild(dlg);}
  /* Secret link, 4 Nov 2026: double-clicking anywhere on the Bitcoin price
     in this popover opens the block clock page in a new tab. No visible
     link or hint anywhere on the site points to it; the clock page itself
     is not linked from any header, footer, or nav. */
  var pxEl=dlg.querySelector('.bc-px');
  /* V2: on the clock page itself the double-click would open the clock from
     the clock, so it is skipped in inline mode. */
  if(pxEl&&!INLINE)pxEl.addEventListener('dblclick',function(e){e.preventDefault();window.open(U('../../clock/index.html'),'_blank','noopener');});
  dim.addEventListener('click',close);
  $('bcSpx').addEventListener('click',function(){SHOWSPX=!SHOWSPX;draw();});$('bcGld').addEventListener('click',function(){SHOWGLD=!SHOWGLD;draw();});$('bcMstr').addEventListener('click',function(){SHOWMSTR=!SHOWMSTR;draw();});$('bcCt').addEventListener('click',function(e){var b=e.target.closest('[data-ct]');if(!b)return;CT=b.dataset.ct;if(CT==='1h'||CT==='4h')last1DCT=CT;draw();});
  $('bcCg').addEventListener('click',function(e){var b=e.target.closest('[data-cg]');if(b){RGCT=b.dataset.cg;draw();return;}var g=e.target.closest('[data-cggran]');if(g){RGGRAN=g.dataset.cggran;draw();}});
  $('bcX').addEventListener('click',close);
  /* Tapping a non-interactive part of the popover (header, note, gaps) dismisses
     the candle pill — a way out of candle-select without closing the graph.
     Canvas taps, buttons and links are excluded: the canvas has its own handler,
     buttons/links do their own thing, and the pill ✕ stops propagation. */
  dlg.addEventListener('click',function(e){if(!candViewActive())return;if(e.target.closest('canvas,button,a'))return;dismissCandInfo();});
  $('bcRg').addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;if(b.dataset.r){
    /* Job 5: the chart type survives a range switch. CT (1D) and RGCT
       (ranges) are separate state, so 1D Candles used to silently become
       Line on 1W, and a candles range back to 1D came back Line. Carry
       the type over: a candles view stays candles, a line view stays
       line. RGGRAN still resets to the new range's default (1W 4H is the
       sensible size for a 1D 4H carry; 1D 1H has no 1W equivalent). */
    var wasCandles=candViewActive(),wasGran=RGGRAN;
    rng=b.dataset.r;FALLBACK_NOTE='';if(!/^(5Y|10Y|Max)$/.test(rng))LOG=false;RGGRAN=defaultGran(rng);
    if(rng==='1D'){if(wasCandles&&CT==='line')CT=(wasGran==='4h')?'4h':last1DCT;else if(!wasCandles)CT='line';}
    else{if(wasCandles)RGCT='candles';else RGCT='line';}
  }else if(b.dataset.s){LOG=b.dataset.s==='log';}draw();});
  document.addEventListener('keydown',function(e){if(INLINE||dlg.hidden)return;if(e.key==='Escape'){e.preventDefault();close();}
    if(e.key==='Tab'){var f=[].slice.call(dlg.querySelectorAll('button,a[href]'));var a=f[0],z=f[f.length-1];if(e.shiftKey&&document.activeElement===a){e.preventDefault();z.focus();}else if(!e.shiftKey&&document.activeElement===z){e.preventDefault();a.focus();}}});
  var y0=null;dlg.addEventListener('touchstart',function(e){y0=(dlg.classList.contains('sheet')&&dlg.scrollTop<=0&&!e.target.closest('canvas'))?e.touches[0].clientY:null;},{passive:true});
  dlg.addEventListener('touchend',function(e){if(y0!=null&&e.changedTouches[0].clientY-y0>80)close();y0=null;},{passive:true});
  window.addEventListener('resize',function(){if(!dlg.hidden){dlg.classList.remove('bc-morph');dlg.style.transform='';dlg.style.borderRadius='';place();syncRgHint();if(candViewActive())redrawCandles();nativeResize();}});$('bcRgs').addEventListener('scroll',syncRgHint,{passive:true});loadTA();}
function place(){if(INLINE)return;var ph=isPhone();dlg.classList.toggle('sheet',ph);dlg.classList.toggle('pop',!ph);dlg.querySelector('.bc-grab').style.display=ph?'':'none';
  if(ph){dlg.style.top=dlg.style.left='';}else{var r=pill.getBoundingClientRect(),isLand=window.innerWidth>window.innerHeight,shortLand=isLand&&window.innerHeight<500,wide=isLand&&(window.innerWidth>=900||window.innerHeight<500),wCap=wide?900:640,w=Math.min(wCap,window.innerWidth-32);
  /* Short landscape (iPhone landscape, viewport <500px tall, 8 Nov 2026,
     round 3): the popover goes full width and docks to the top of the
     viewport (12px) instead of anchoring below the pill, so the wide
     chart fits without scrolling. The width cap (900px) matches the CSS:
     wide when landscape and (width>=900 or height<500). */
  if(shortLand){dlg.style.top='12px';dlg.style.left=Math.max(16,(window.innerWidth-w)/2)+'px';}
  else{dlg.style.top=(r.bottom+10)+'px';dlg.style.left=Math.max(16,Math.min(r.left-20,window.innerWidth-w-16))+'px';}}}
function head(){$('bcPx').textContent=live.usd!=null?fmt(live.usd):'—';var c=$('bcChg');c.textContent=typeof live.chg==='number'?(live.chg>=0?'+':'')+live.chg.toFixed(1)+'% 24h':'';c.className='hdr-chg '+(live.chg>=0?'up':'down');}
function series(){var d=DATA.slice(),today=new Date().toISOString().slice(0,10);
  if(live.usd!=null){if(d.length&&d[d.length-1][0]>=today)d.pop();d.push([today,live.usd]);}
  var last=new Date(d[d.length-1][0]+'T00:00:00Z'),st;
  if(rng==='Max')st='0000';else if(rng==='YTD')st=(last.getUTCFullYear()-1)+'-12-31';else st=new Date(last-DAYS[rng]*864e5).toISOString().slice(0,10);
  return d.filter(function(p){return p[0]>=st;});}
function drawDaily(){if(!DATA)return;clearCandState();lineDrawn=false;lineHover=-1;linePts=null;lineGeom=null;head();var _cg=$('bcCg');if(_cg)syncCg();
var d=series(),big=/^(5Y|10Y|Max)$/.test(rng),hasLive=live.usd!=null,sxo=SHOWSPX&&SPXK.length>0,gxo=SHOWGLD&&GOLDK.length>0,mxo=SHOWMSTR&&MSTRK.length>0,sx=sxo||gxo||mxo;
  [].forEach.call($('bcRg').querySelectorAll('[data-r]'),function(b){b.classList.toggle('on',b.dataset.r===rng);b.setAttribute('aria-pressed',b.dataset.r===rng);});
  var onb=$('bcRgs').querySelector('.on'),rs=$('bcRgs');if(onb&&rs.scrollWidth>rs.clientWidth){var L=onb.offsetLeft-rs.offsetLeft,R=L+onb.offsetWidth;if(L<rs.scrollLeft+16||R>rs.scrollLeft+rs.clientWidth-16)rs.scrollTo({left:Math.max(0,L-(rs.clientWidth-onb.offsetWidth)/2),behavior:'smooth'});}
  $('bcSc').style.display=big?'':'none';
  var mb=$('bcMstr');if(mb){var mxo2=SHOWMSTR&&MSTRK.length>0;mb.setAttribute('aria-pressed',mxo2?'true':'false');mb.classList.toggle('off',!mxo2);$('bcMstrT').textContent=mxo2?'MSTR ✕':'+ MSTR';mb.setAttribute('aria-label',mxo2?'Hide MSTR':'Show MSTR');}
  var sb=$('bcSpx');sb.setAttribute('aria-pressed',sxo?'true':'false');sb.classList.toggle('off',!sxo);$('bcSpxT').textContent=sxo?'S&P 500 ✕':'+ S&P 500';sb.setAttribute('aria-label',sxo?'Hide S&P 500':'Show S&P 500');
  var gb=$('bcGld');gb.setAttribute('aria-pressed',gxo?'true':'false');gb.classList.toggle('off',!gxo);$('bcGldT').textContent=gxo?'Gold ✕':'+ Gold';gb.setAttribute('aria-label',gxo?'Hide Gold':'Show Gold');
  var n=d.length,a=d[0][1],b=d[n-1][1],pc=(b/a-1)*100,pa=a<1?curSym()+curVal(a).toFixed(2):fmt(a),fp=function(x){return (x>=0?'+':'')+(Math.abs(x)>=1e4?Math.round(x).toLocaleString('en-US'):x.toFixed(1))+'%';};
  var S=sxo?d.map(function(p){return spxOn(p[0]);}):null,s0=S&&S[0];if(S&&!s0){var k0=S.findIndex(function(v){return v!=null;});s0=k0>=0?S[k0]:null;}
  var spc=S&&s0?(S[n-1]/s0-1)*100:null;
  var G=gxo?d.map(function(p){return gldOn(p[0]);}):null,g0=G&&G[0],gk0=0;if(G&&!g0){gk0=G.findIndex(function(v){return v!=null;});g0=gk0>=0?G[gk0]:null;}
  var gpc=G&&g0?(G[n-1]/g0-1)*100:null,gLate=G&&g0&&gk0>0?d[gk0][0]:null;
  var M=mxo?d.map(function(p){return mstrOn(p[0]);}):null,m0=M&&M[0];if(M&&!m0){var mk0=M.findIndex(function(v){return v!=null;});m0=mk0>=0?M[mk0]:null;}
  var mpc=M&&m0?(M[n-1]/m0-1)*100:null;
  /* Job 12: auto-log in compare mode when the rebased span is extreme
     (10Y/Max) — the BTC-only axis flattened the compared lines, so the
     chart switches to log scale and the scale buttons follow. The
     threshold is hi/lo > 50: Max is ~1.8M, 10Y ~180, nothing else
     exceeds it (5Y ~7, YTD ~3, 1Y ~2). LOG itself is untouched — the
     user's toggle is preserved for the BTC-only view and shorter
     ranges. When the data forces log, the Linear button is disabled:
     clicking it would be overridden by the data on the next draw, so
     it must not look clickable. */
  var effLog=LOG,_autoLog=false;
  if(sx){
    var _clo=Infinity,_chi=-Infinity;
    d.forEach(function(p,i){
      var rb=100*p[1]/a;if(rb<_clo)_clo=rb;if(rb>_chi)_chi=rb;
      if(S&&s0&&S[i]!=null){var _rs=100*S[i]/s0;if(_rs<_clo)_clo=_rs;if(_rs>_chi)_chi=_rs;}
      if(G&&g0&&G[i]!=null){var _rg=100*G[i]/g0;if(_rg<_clo)_clo=_rg;if(_rg>_chi)_chi=_rg;}
      if(M&&m0&&M[i]!=null){var _rm=100*M[i]/m0;if(_rm<_clo)_clo=_rm;if(_rm>_chi)_chi=_rm;}
    });
    if(isFinite(_clo)&&_clo>0&&isFinite(_chi)&&_chi/_clo>50){effLog=true;_autoLog=!LOG;}
  }
  [].forEach.call($('bcSc').children,function(b){var on=(b.dataset.s==='log')===effLog;b.classList.toggle('on',on);b.setAttribute('aria-pressed',on);if(b.dataset.s==='lin')b.disabled=_autoLog;});
  $('bcRr').textContent=rng==='Max'?'Max · from '+d[0][0]+' ('+pa+')':rng+': BTC '+fp(pc)+(spc!=null?' · S&P 500 '+fp(spc):'')+(gpc!=null?' · Gold '+fp(gpc):'')+(mpc!=null?' · MSTR '+fp(mpc):'')+' · from '+d[0][0]+' ('+pa+')'+cadTag()+(FALLBACK_NOTE?' · '+FALLBACK_NOTE:'');
  $('bcNt').textContent=(sx?((((sxo?1:0)+(gxo?1:0)+(mxo?1:0))>1)?'All lines':'Both lines')+': % change from the first close in range (BTC daily UTC closes incl. weekends'+(sxo?'; S&P 500 ^GSPC session closes':'')+(gxo?'; Gold GC=F futures session closes':'')+(mxo?'; MSTR session closes':'')+', carried over weekends/holidays). '+(gLate?'Gold data starts '+gLate+'. ':''):'Daily closes (UTC day, weekends included)'+(hasLive?'; ':'. '))+(hasLive?(sx?'Last BTC point is the live price.':'last point is the live price.'):'')+(PROV?" Today's close is provisional until "+provCloseLabel()+".":'')+(effLog?' Log scale.':'')+(FALLBACK_NOTE?' '+FALLBACK_NOTE:'');
  /* Native range line (Chart.js removed 20 Nov 2026; no fallback library). */
  var nativeOK=drawDailyNative(d,{sx:sx,S:S,G:G,M:M,s0:s0,g0:g0,m0:m0,hasLive:hasLive,log:effLog});lineDrawn=nativeOK;
  if(nativeOK)lineRetry=false;else lineFail();
  syncTypePill();}
/* ===== Stage 2 native line renderer — Step 2: 1D line (8 Nov 2026) =====
   draw1DNative implements the 1D intraday line natively (smooth curve,
   cyan gradient fill, axes, labels, live "Now" point, tap/hover tooltip).
   drawDailyNative implements the range daily line natively (Step 3).
   The native renderer replaces
   ONLY the two Chart.js line constructions (draw1D, drawDaily); everything
   else in this file stays. Design note (flags F1–F8):
   ~/workspace/ps-stage2-step1/design-note.md
   F5 — DPR: uncapped, matching the candle pattern in this file (the line
   and candle views share this canvas; a cap would make the line view
   blurrier than the candle view on a 3x phone).
   F6 — Colours: the hardcoded dark Chart.js values, not "improved".
   The native line is the only line renderer: Chart.js and its fallback were
   removed on 20 Nov 2026 (draw*Native returns false on any failure; the
   caller then runs lineFail() and a later resize retries the draw). */
var lineDrawn=false; /* F1: true while the native 1D line is on the canvas. */
var linePts=null; /* pts array last drawn by draw1DNative (tooltip + redraw). */
var lineHover=-1; /* index of the hovered/tapped point, -1 = none. */
var lineGeom=null; /* layout of the last native 1D draw (hit-testing + parity). */
var lineRetry=false; /* true after a failed native line draw: a resize or live tick retries it. */
/* F1: clear the line chart — clears the native line state. Call this
   before drawing candles (the line view is leaving the canvas). */
function clearLineChart(){lineRetry=false;lineDrawn=false;lineHover=-1;linePts=null;lineGeom=null;window.__BTC_LINE_LAYOUT=null;window.__BTC_LINE_HOVER=-1;cancelNativeResize();}
/* Failed native line draw (no fallback library): clear the line state but
   keep a pending retry so the next resize or live tick draws again.
   Stage 2 analytics (27 Nov 2026): report the failure once per lineFail
   call through the ps-err.js hook, guarded so a missing hook can never
   break the draw. The hook's own rate limit (5/load, 10 s apart) stops
   resize retries from flooding the Worker. */
function lineFail(){lineDrawn=false;lineHover=-1;linePts=null;lineGeom=null;window.__BTC_LINE_LAYOUT=null;window.__BTC_LINE_HOVER=-1;lineRetry=true;try{if(typeof window.__psErr==='function'){var d=null;try{d=window.__BTC_DRAWERR;}catch(_){}window.__psErr('lineFail',d&&d.msg?d.msg:'native line draw failed','btcchart-panel.js',0);}}catch(_){}}
/* F1: redraw the native line at the current size (Chart.js responsive:true
   replacement — flag F4). No-op unless the native line is showing or a
   failed line draw is waiting for a retry. */
function redrawLine(){if(lineDrawn||lineRetry)draw();}
/* Resize coalescing: iOS fires many resize events while the toolbar collapses
   during scroll; redraw at most once per animation frame. Teardown
   (clearLineChart) and close() cancel a pending frame. */
var nrRaf=0;
function cancelNativeResize(){if(nrRaf){if(window.cancelAnimationFrame)window.cancelAnimationFrame(nrRaf);else clearTimeout(nrRaf);nrRaf=0;}}
function nativeResize(){if(nrRaf)return;var f=function(){nrRaf=0;redrawLine();};nrRaf=window.requestAnimationFrame?window.requestAnimationFrame(f):setTimeout(f,16);}
/* Redraw the native line with the current hover state (tooltip show/hide).
   Dispatches on the layout kind: the 1D line or the range daily line.
   Guarded on lineDrawn so a scroll after a failed line draw cannot
   repaint a stale native line. */
function redrawNativeLine(){
  if(!lineDrawn||!lineGeom)return;
  if(lineGeom.kind==='daily'&&linePts&&linePts.d)drawDailyNative(linePts.d,linePts.cmp);
  else if(linePts&&linePts.cmp)draw1DNative(linePts.pts,linePts.cmp);
  else if(linePts)draw1DNative(linePts);
}

function chartNiceNum(x){
  /* Chart.js 4 niceNum (from the formerly vendored Chart.js build, function B): round to the
     nearest integer when within x/1000, then a 1/2/5/10 step at the decade
     below x (thresholds <=1 / <=2 / <=5). */
  var r=Math.round(x);
  if(Math.abs(x-r)<x/1e3)x=r;
  var p=Math.pow(10,Math.floor(Math.log10(x)));
  var s=x/p;
  return (s<=1?1:s<=2?2:s<=5?5:10)*p;
}
function nativeNiceTicks(min,max,plotH){
  /* Chart.js linear-scale tick generation, replicated exactly (formerly
     vendored Chart.js 4 build: getTickLimit + the buildTicks tick function).
     maxTicks = min(11, ceil(plotH/14.4)): 11 is Chart.js's default
     maxTicksLimit; computeTickLimit = ceil(plot height / tick-font
     lineHeight), the default 12px tick font at lineHeight 1.2 = 14.4px.
     The step is niceNum(span/(maxTicks-1)); if the tick count then
     exceeds maxTicks-1 intervals the step is recomputed as
     niceNum(count*step/(maxTicks-1)). Ticks run from
     floor(min/step)*step to ceil(max/step)*step, so the top tick covers
     the data max. (The old target-of-4 gave $1,000 steps on 1W and
     $2,000 on 1M where Chart.js uses $500 / $1,000 — Step 4 (a).) */
  if(!(max>min)){max=min+1;}
  var mt=Math.min(11,Math.ceil((plotH||320)/14.4));
  if(mt<2)mt=2;
  var g=mt-1,span=max-min,step=chartNiceNum(span/g);
  var k=Math.ceil(max/step)-Math.floor(min/step);
  if(k>g)step=chartNiceNum(k*step/g);
  var t0=Math.floor(min/step)*step,t1=Math.ceil(max/step)*step,out=[];
  for(var v=t0;v<=t1+step*0.01;v+=step)out.push(Math.round(v*1000)/1000);
  return out;
}
function nativeHeadroomTicks(ticks,loData,hiData){
  /* Job 12: guarantee at least half a tick step of headroom above the
     highest drawn value and below the lowest, so a peak (1D) or a
     comparison low (YTD MSTR) never sits on the plot edge or under the
     top tick label. Extends the axis by one nice tick per side when
     needed; the axis labels stay nice tick values. Returns the
     extended {lo,hi,ticks} or null when the headroom is already
     enough. loData/hiData are the pre-tick extremes (data + overlay
     + trendline expansions), so the guarantee covers everything drawn. */
  if(!ticks||ticks.length<2)return null;
  var step=ticks[1]-ticks[0];
  if(!(step>0))return null;
  var lo=ticks[0],hi=ticks[ticks.length-1],t=ticks.slice(),moved=false;
  if(hi-hiData<step/2){hi+=step;t.push(hi);moved=true;}
  if(loData-lo<step/2){lo-=step;t.unshift(lo);moved=true;}
  if(!moved)return null;
  return {lo:lo,hi:hi,ticks:t};
}
var LOG_SIG=[1,2,3,4,5,6,7,8,9,10,15,20];
function logGridCeil(v){
  /* Smallest Chart.js log-scale tick-grid value >= v (the wo grid:
     significands 1..10, 15, 20 per decade). The 15/20 of one decade spill
     into the next decade's range (15e4 = 150,000), so start a decade low. */
  if(!(v>0))return 1;
  var o=Math.floor(Math.log10(v))-1;
  for(var j=0;j<4;j++){
    var pw=Math.pow(10,o+j);
    for(var i=0;i<LOG_SIG.length;i++){var tv=LOG_SIG[i]*pw;if(tv>=v*(1-1e-9))return tv;}
  }
  return Math.pow(10,Math.floor(Math.log10(v))+1);
}
function logGridFloor(v){
  /* Largest Chart.js log-scale tick-grid value <= v. */
  if(!(v>0))return 1;
  var o=Math.floor(Math.log10(v));
  for(var j=0;j<4;j++){
    var pw=Math.pow(10,o-j);
    for(var i=LOG_SIG.length-1;i>=0;i--){var tv=LOG_SIG[i]*pw;if(tv<=v*(1+1e-9))return tv;}
  }
  return Math.pow(10,Math.floor(Math.log10(v)));
}
function nativeTraceLine(ctx,xs,ys,tension,bounds){
  /* Chart.js splineCurve (Catmull-Rom), matching the vendored Chart.js
     _updateBezierControlPoints exactly: each point's cp1 (before) and cp2
     (after) come from splineCurve(prev, curr, next, tension); the segment
     from point i to i+1 uses i.cp2 -> (i+1).cp1. Control points are clamped
     to the plot bounds (capBezierPoints, on by default). The YTD backup's
     horizontal-handle version is close but visibly different on steep
     sections, so it is NOT reused here. */
  var n=xs.length;
  if(n<1)return;
  ctx.moveTo(xs[0],ys[0]);
  if(n===1)return;
  if(!tension||n===2){for(var i=1;i<n;i++)ctx.lineTo(xs[i],ys[i]);return;}
  function spline(pX,pY,cX,cY,nX,nY,t){
    var d01=Math.sqrt(Math.pow(cX-pX,2)+Math.pow(cY-pY,2));
    var d12=Math.sqrt(Math.pow(nX-cX,2)+Math.pow(nY-cY,2));
    var s01=d01/(d01+d12),s12=d12/(d01+d12);
    if(isNaN(s01))s01=0;
    if(isNaN(s12))s12=0;
    var fa=t*s01,fb=t*s12;
    return{prev:{x:cX-fa*(nX-pX),y:cY-fa*(nY-pY)},
           next:{x:cX+fb*(nX-pX),y:cY+fb*(nY-pY)}};
  }
  function clamp(v,lo,hi){return Math.max(Math.min(v,hi),lo);}
  var cp1x=[],cp1y=[],cp2x=[],cp2y=[],j;
  for(j=0;j<n;j++){
    var p=Math.max(0,j-1),q=Math.min(n-1,j+1);
    var c=spline(xs[p],ys[p],xs[j],ys[j],xs[q],ys[q],tension);
    cp1x[j]=c.prev.x;cp1y[j]=c.prev.y;cp2x[j]=c.next.x;cp2y[j]=c.next.y;
  }
  if(bounds){
    for(j=0;j<n;j++){
      cp1x[j]=clamp(cp1x[j],bounds.l,bounds.r);cp1y[j]=clamp(cp1y[j],bounds.t,bounds.b);
      cp2x[j]=clamp(cp2x[j],bounds.l,bounds.r);cp2y[j]=clamp(cp2y[j],bounds.t,bounds.b);
    }
  }
  for(var i=0;i<n-1;i++){
    ctx.bezierCurveTo(cp2x[i],cp2y[i],cp1x[i+1],cp1y[i+1],xs[i+1],ys[i+1]);
  }
}
function nativeGradientFill(ctx,x,y,w,h){
  /* Cyan gradient, same stops as the Chart.js 1D fill (rgba(34,211,238,.28) -> transparent). */
  var g=ctx.createLinearGradient(x,y,x,y+h);
  g.addColorStop(0,'rgba(34,211,238,.28)');
  g.addColorStop(1,'rgba(34,211,238,0)');
  return g;
}
function drawLineTooltip(ctx,p,px,py,W,padT,plotH,cmpT){
  /* Tooltip content = the Chart.js 1D tooltip (title: 'Now (live)' or ET date;
     label: 'BTC ' + fmt(price)). Positioned above the point, flipping below
     if it would run off the top — Chart.js's default placement.
     Job 10: in compare mode (cmpT) each line is price + % vs the window
     open, same format as drawDailyTooltip, for BTC and every visible
     compare series at the hovered index. */
  var title=p.live?'Now (live)':etDateTime(p.t);
  var lines=[title,'BTC '+fmt(p.v)];
  if(cmpT){
    var fp=function(x){return (x>=0?'+':'')+(Math.abs(x)>=1e4?Math.round(x).toLocaleString('en-US'):x.toFixed(1))+'%';};
    var i=cmpT.i,reb=cmpT.reb;
    lines=[title,'BTC '+fmt(p.v)+' ('+fp(reb.btc[i]-100)+')'];
    if(cmpT.S&&cmpT.S[i]!=null&&cmpT.s0)lines.push('S&P 500 '+cmpT.S[i].toLocaleString('en-US',{maximumFractionDigits:0})+' ('+fp(reb.spx[i]-100)+')');
    if(cmpT.G&&cmpT.G[i]!=null&&cmpT.g0)lines.push('Gold '+curSym()+curVal(cmpT.G[i]).toLocaleString('en-US',{maximumFractionDigits:0})+' ('+fp(reb.gld[i]-100)+')');
    if(cmpT.M&&cmpT.M[i]!=null&&cmpT.m0)lines.push('MSTR '+curSym()+curVal(cmpT.M[i]).toLocaleString('en-US',{maximumFractionDigits:0})+' ('+fp(reb.mstr[i]-100)+')');
  }
  /* TA Stage 2: indicator values for the hovered point, when overlays are on. */
  try{var _ta=window.__BCTA&&window.__BCTA.taTip;if(_ta){var _tl=_ta('1d-line',lineHover);if(_tl)lines=lines.concat(_tl.map(function(o){return o.t;}));}}catch(e){}
  ctx.font='11px Inter, sans-serif';
  var tw=0;lines.forEach(function(t){tw=Math.max(tw,ctx.measureText(t).width);});tw+=16;
  var th=lines.length*14+10;
  var tx=px-tw/2,ty=py-th-10;
  if(ty<padT)ty=py+10;
  if(ty+th>padT+plotH)ty=padT+plotH-th;
  if(tx<4)tx=4;
  if(tx+tw>W-4)tx=W-4-tw;
  ctx.fillStyle=psC('rgba(15,23,42,.92)','#ffffff');
  ctx.strokeStyle=psC('#334155','#e2e8f0');ctx.lineWidth=1;
  ctx.beginPath();ctx.rect(tx,ty,tw,th);ctx.fill();ctx.stroke();
  ctx.textAlign='left';ctx.textBaseline='top';
  /* H1: theme colours as chart-theme.js gives Chart.js (light: title #0f172a, body #334155; dark unchanged). */
  lines.forEach(function(t,i){ctx.fillStyle=i===0?psC('#e2e8f0','#0f172a'):psC('#e2e8f0','#334155');ctx.fillText(t,tx+8,ty+6+i*14);});
}
function nativeXLabels(ctx,texts,xs,L,R,W,y){
  /* X-axis labels. Edge labels keep the usual clamp (L+30 / W-R-30), so
     nothing moves where labels already fit. M1: where the clamped first
     (or last) label would run into its neighbour, it moves back toward its
     tick as Chart.js places it (staying on the canvas); any label that
     still overlaps the previous one is skipped. */
  var m=texts.length,pos=[],w=[],GAP=1,k; /* skip only labels that would touch or overlap */
  for(k=0;k<m;k++){w[k]=ctx.measureText(texts[k]).width;pos[k]=Math.max(L+30,Math.min(W-R-30,xs[k]));}
  if(m>1&&pos[0]+w[0]/2+GAP>pos[1]-w[1]/2)pos[0]=Math.max(w[0]/2+2,Math.min(pos[0],xs[0]));
  if(m>1&&pos[m-1]-w[m-1]/2-GAP<pos[m-2]+w[m-2]/2)pos[m-1]=Math.min(W-w[m-1]/2-2,Math.max(pos[m-1],xs[m-1]));
  var lastR=-1e9;
  for(k=0;k<m;k++){
    if(pos[k]-w[k]/2<lastR+GAP)continue;
    ctx.fillText(texts[k],pos[k],y);lastR=pos[k]+w[k]/2;
  }
}
function nativeThemeWatch(){
  /* H1: colours come from psC at draw time; redraw the native line when
     data-theme changes so a theme toggle repaints it. */
  if(nativeThemeWatch._on||!window.MutationObserver)return;
  nativeThemeWatch._on=true;
  try{new MutationObserver(function(){if(lineDrawn&&lineGeom){lineHover=-1;redrawNativeLine();}}).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});}catch(e){}
}
function nativeTooltipBind(c){
  nativeThemeWatch();
  if(c._lineTipBound)return;
  c._lineTipBound=true;
  /* F3 — SCROLL SAFETY (Speed Option 2 rollback + round-3 pill lesson):
     NEVER set touch-action 'none' and NEVER capture the pointer on this
     canvas (that trapped vertical page scroll on iPhone/iPad). The canvas
     already has touch-action: pan-y in CSS; these listeners never change it.
     The listeners do NOTHING while a candle view is active (candViewActive)
     — the candle pill owns the canvas then. */
  var downX=0,downY=0,downIdx=-1,pressMoved=false,pressDone=false;
  function pick(ev){
    if(!lineGeom||!linePts)return -1;
    var r=c.getBoundingClientRect();
    var cx=(ev.clientX!=null)?ev.clientX:((ev.touches&&ev.touches[0])?ev.touches[0].clientX:((ev.changedTouches&&ev.changedTouches[0])?ev.changedTouches[0].clientX:null));
    if(cx==null)return -1;
    var x=cx-r.left,L=lineGeom.pad.l,iw=lineGeom.plotW,n=lineGeom.n;
    /* M2: the live Now dot sits on the right plot edge; accept taps a little
       outside the plot (8px left, 12px right = the right margin) and clamp. */
    if(x<L-8||x>L+iw+12)return -1;
    x=Math.max(L,Math.min(L+iw,x));
    var t=(x-L)/iw;
    return Math.max(0,Math.min(n-1,Math.round(t*Math.max(1,n-1))));
  }
  function show(i){if(i===lineHover)return;lineHover=i;redrawNativeLine();}
  function hide(){if(lineHover===-1)return;lineHover=-1;redrawNativeLine();}
  /* Mouse hover follows the pointer (desktop). */
  c.addEventListener('pointermove',function(e){
    if(e.pointerType!=='mouse')return;
    if(candViewActive()||!lineDrawn)return;
    show(pick(e));
  });
  c.addEventListener('pointerleave',function(e){
    if(e.pointerType!=='mouse')return;
    hide();
  });
  /* Touch/pen tap: arm on press down, decide on press end (round-3 model).
     A tap shows the tooltip at the down point; tapping the same point again
     dismisses it; tapping empty space dismisses it. A press that moved far
     (a scroll/drag) does not show a tooltip — the scroll dismisses it. */
  c.addEventListener('pointerdown',function(e){
    if(candViewActive()||!lineDrawn)return;
    var r=c.getBoundingClientRect();
    downX=e.clientX-r.left;downY=e.clientY-r.top;downIdx=pick(e);pressMoved=false;pressDone=false;
    window.__BTC_LINE_PRESS={downIdx:downIdx,pressMoved:false,hover:lineHover};
  });
  c.addEventListener('touchstart',function(e){
    if(candViewActive()||!lineDrawn)return;
    if(!e.touches||!e.touches.length)return;
    var r=c.getBoundingClientRect(),t=e.touches[0];
    downX=t.clientX-r.left;downY=t.clientY-r.top;downIdx=pick(e);pressMoved=false;pressDone=false;
  },{passive:true});
  c.addEventListener('pointermove',function(e){
    if(e.pointerType==='mouse')return;
    if(downIdx<0)return;
    var r=c.getBoundingClientRect();
    var dx=Math.abs(e.clientX-r.left-downX),dy=Math.abs(e.clientY-r.top-downY);
    if(Math.max(dx,dy)>40)pressMoved=true;
  });
  function endLinePress(){
    if(pressDone)return;
    if(candViewActive()||!lineDrawn)return;
    pressDone=true;
    window.__BTC_LINE_PRESS={downIdx:downIdx,pressMoved:pressMoved,hover:lineHover,ended:true};
    if(downIdx<0){hide();return;}
    if(pressMoved)return;
    if(downIdx===lineHover){hide();return;}
    show(downIdx);
  }
  c.addEventListener('pointerup',function(){endLinePress();});
  c.addEventListener('pointercancel',function(){pressMoved=true;endLinePress();}); /* iOS fires pointercancel when the browser takes over a pan: treat as a move, no tooltip. */
  c.addEventListener('touchend',function(){endLinePress();},{passive:true});
  c.addEventListener('touchcancel',function(){endLinePress();},{passive:true});
  /* Dismiss the sticky tooltip when the page scrolls. */
  window.addEventListener('scroll',function(){hide();},{passive:true,capture:true});
  document.addEventListener('touchmove',function(e){if(!c.contains(e.target))hide();},{passive:true});
}
function nativeTooltipHide(){
  if(lineHover===-1)return;
  lineHover=-1;
  redrawNativeLine();
}
function draw1DNative(pts,cmp){
  /* Stage 2 Step 2 — implemented. The 1D intraday line, drawn natively.
     Same data, same labels, same colours as the old Chart.js draw1D. Returns
     true on success, false on failure (caller runs lineFail()).
     Job 10: cmp {sx, S, G, M, s0, g0, m0, hasLive} (prepared by
     draw1DCmp) — when cmp.sx the BTC line and the compare lines are all
     rebased to 100 at the first close, and the y-axis reads % change,
     exactly like drawDailyNative in compare mode. */
  try{
    if(!pts||pts.length<2)return false;
    var c=$('bcC');if(!c)return false;
    var ctx=c.getContext('2d');
    var W=c.parentNode.clientWidth||640,H=c.parentNode.clientHeight||300;
    var dpr=window.devicePixelRatio||1; /* F5: uncapped, matching the candles on this shared canvas. */
    c.width=Math.round(W*dpr);c.height=Math.round(H*dpr);
    c.style.width=W+'px';c.style.height=H+'px';
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.clearRect(0,0,W,H);
    var hasLive=pts[pts.length-1].live===true;
    var vals=pts.map(function(p){return p.v;});
    var rawVals=vals.slice();
    /* Job 10: rebase everything to 100 at the first close when
       comparing (the range views' convention). The compare arrays are
       aligned to pts (same length, nulls for missing slots). */
    var sx=!!(cmp&&cmp.sx),spxY=null,gldY=null,mstrY=null;
    if(sx){
      var b0=vals[0];
      vals=vals.map(function(v){return 100*v/b0;});
      spxY=cmp.S?cmp.S.map(function(v){return v!=null&&cmp.s0?100*v/cmp.s0:null;}):null;
      gldY=cmp.G?cmp.G.map(function(v){return v!=null&&cmp.g0?100*v/cmp.g0:null;}):null;
      mstrY=cmp.M?cmp.M.map(function(v){return v!=null&&cmp.m0?100*v/cmp.m0:null;}):null;
    }
    var lo=Math.min.apply(null,vals),hi=Math.max.apply(null,vals);
    if(sx){[spxY,gldY,mstrY].forEach(function(arr){if(!arr)return;for(var i=0;i<arr.length;i++){var v=arr[i];if(v!=null&&isFinite(v)){if(v<lo)lo=v;if(v>hi)hi=v;}}});}
    if(!(hi>lo)){lo=(lo===Infinity?0:lo);hi=lo+1;}
    /* Job 1 (Line-view trendlines): when trendlines are on and the file
       is cached, extend the y-range to include the drawn lines' prices
       (bounded to one span per side), so they draw instead of being
       clipped outside the plot. Falls back to the tight range when the
       TA module or the file is not ready yet. */
    var _tlR=null;
    try{if(window.__BTTA&&window.__BTTA.tlExpandRange)_tlR=window.__BTTA.tlExpandRange(window.__BCTA.state(),vals[vals.length-1],pts[pts.length-1].t,lo,hi);}catch(e){}
    if(_tlR&&isFinite(_tlR.lo)&&isFinite(_tlR.hi)&&_tlR.hi>_tlR.lo){lo=_tlR.lo;hi=_tlR.hi;}
    /* Job 12: same for the overlays — a Bollinger band or MA line that
       runs outside the price range widens the axis instead of being
       clipped off the plot. */
    var _ovR=null;
    try{if(window.__BTTA&&window.__BTTA.ovExpandRange)_ovR=window.__BTTA.ovExpandRange(window.__BCTA.state(),'1d-line',vals,lo,hi);}catch(e){}
    if(_ovR&&isFinite(_ovR.lo)&&isFinite(_ovR.hi)&&_ovR.hi>_ovR.lo){lo=_ovR.lo;hi=_ovR.hi;}
    /* No explicit pad: Chart.js does not pad the data range — its nice
       ticks provide the padding. An 8% pad (the candle pattern) would
       extend the axis below Chart.js (e.g. $74k instead of $75k). The
       Job 12 headroom rule below is narrower: it only steps the axis
       out by one nice tick when a drawn extreme sits within half a
       tick of the edge, so a 1D peak never flattens against the top. */
    var L=62,R=12,T=18,B=44,iw=W-L-R,ih=H-T-B;
    var ticks=nativeNiceTicks(lo,hi,ih);
    var _hr=nativeHeadroomTicks(ticks,lo,hi);if(_hr)ticks=_hr.ticks;
    /* Must-fix (27 Nov 2026): a price axis never goes below $0. A
       comparison % axis may go negative — it is not a price. */
    if(!sx){ticks=ticks.filter(function(t){return t>=0;});if(!ticks.length)ticks=[0];}
    if(ticks.length){lo=Math.min(lo,ticks[0]);hi=Math.max(hi,ticks[ticks.length-1]);}
    var n=pts.length;
    var X=function(i){return L+iw*(n===1?0.5:i/(n-1));};
    var Y=function(v){return T+ih*(1-(v-lo)/(hi-lo));};
    var xs=pts.map(function(p,i){return X(i);}),ys=vals.map(function(v){return Y(v);});
    /* TA Stage 2: publish the geometry for the overlay draw. */
    TAGEOM={kind:'1d-line',xs:xs,yFor:Y,log:false,closes:rawVals,times:pts.map(function(p){return p.t;}),n:n,W:W,H:H,pad:{l:L,r:R,t:T,b:B},plotW:iw,plotH:ih};
    /* Y gridlines + labels (same format as the Chart.js yTick callback). */
    ctx.strokeStyle=psC('rgba(255,255,255,.05)','rgba(15,23,42,.08)');ctx.fillStyle=psC('#9aa6bc','#475569');
    ctx.font='11px Inter, sans-serif';ctx.textAlign='right';ctx.textBaseline='middle';ctx.lineWidth=1;
    var prevLab=null; /* Must-fix (27 Nov 2026): never draw the same %-label twice in a row. */
    ticks.forEach(function(v){
      var y=Y(v);
      ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(L+iw,y);ctx.stroke();
      /* Job 10: % change on the axis in compare mode (yTickDaily with
         sx), dollars otherwise — same as drawDailyNative. */
      if(sx){var s=yTickDaily(v,true,false);if(s!=null&&s!==prevLab){ctx.fillText(s,L-6,y);prevLab=s;}}
      else{var vv=curVal(v);ctx.fillText(Math.abs(vv)>=1000?curSym()+(vv/1000).toLocaleString('en-US')+'k':curSym()+Math.round(vv).toLocaleString('en-US'),L-6,y);}
    });
    /* X labels: Chart.js autoSkip uses a fixed step (ceil(n/maxTicksLimit))
       and does NOT force-include the last label — so 'Now (live)' never
       appears on its x-axis. Same step here, so the labels land on the
       same points Chart.js picks. */
    var maxX=isPhone()?5:7,step=Math.max(1,Math.ceil(n/maxX)),xIdx=[];
    for(var i=0;i<n;i+=step)xIdx.push(i);
    var lab=pts.map(function(p){return p.live?'Now (live)':etTime(p.t);});
    /* Vertical gridlines at each x tick (Chart.js scales.x.grid). */
    xIdx.forEach(function(i){
      var x=X(i);
      ctx.beginPath();ctx.moveTo(x,T);ctx.lineTo(x,T+ih);ctx.stroke();
    });
    ctx.textAlign='center';ctx.textBaseline='top';ctx.fillStyle=psC('#9aa6bc','#475569');
    nativeXLabels(ctx,xIdx.map(function(i){return lab[i];}),xIdx.map(function(i){return X(i);}),L,R,W,T+ih+6);
    /* Fill under the line, then the line (tension .15, same as Chart.js).
       Job 10: no fill when comparing (same as drawDailyNative); the
       compare traces draw on top of BTC, in dataset order. */
    var traceDS1D=function(ysArr,bridge){
      /* A compare trace (same shape as traceDS in drawDailyNative):
         null slots are bridged (SPX/MSTR) or gapped (Gold). */
      var started=false;
      ctx.beginPath();
      for(var i=0;i<n;i++){
        var yv=ysArr[i];
        if(yv==null){if(!bridge&&started){ctx.stroke();ctx.beginPath();started=false;}continue;}
        if(!started){ctx.moveTo(xs[i],yv);started=true;}
        else ctx.lineTo(xs[i],yv);
      }
      ctx.stroke();
    };
    if(!sx){
      ctx.beginPath();
      nativeTraceLine(ctx,xs,ys,.15,{l:L,t:T,r:L+iw,b:T+ih});
      ctx.lineTo(xs[n-1],T+ih);ctx.lineTo(xs[0],T+ih);ctx.closePath();
      ctx.fillStyle=nativeGradientFill(ctx,0,0,W,H);
      ctx.fill();
    }
    ctx.beginPath();
    nativeTraceLine(ctx,xs,ys,.15,{l:L,t:T,r:L+iw,b:T+ih});
    ctx.strokeStyle='#22d3ee';ctx.lineWidth=2;ctx.stroke();
    var spxYs=sx&&spxY?spxY.map(function(v){return v==null?null:Y(v);}):null;
    var gldYs=sx&&gldY?gldY.map(function(v){return v==null?null:Y(v);}):null;
    var mstrYs=sx&&mstrY?mstrY.map(function(v){return v==null?null:Y(v);}):null;
    if(sx){
      if(spxYs){ctx.strokeStyle='#c4b5fd';ctx.lineWidth=1.6;traceDS1D(spxYs,true);}
      if(gldYs){ctx.strokeStyle='#facc15';ctx.lineWidth=1.6;traceDS1D(gldYs,false);}
      if(mstrYs){ctx.strokeStyle='#f97316';ctx.lineWidth=1.6;traceDS1D(mstrYs,true);}
    }
    /* Live "Now" dot (4px, same as Chart.js pointRadius) + hovered dot (3px, same as pointHoverRadius).
       Job 10: no live dot in compare mode (complete buckets only); the
       hovered dots draw on every visible dataset. */
    if(hasLive&&!sx){ctx.beginPath();ctx.arc(xs[n-1],ys[n-1],4,0,Math.PI*2);ctx.fillStyle='#22d3ee';ctx.fill();}
    if(lineHover>=0&&lineHover<n){
      if(sx){
        [['#22d3ee',ys],['#c4b5fd',spxYs],['#facc15',gldYs],['#f97316',mstrYs]].forEach(function(dp){var ys2=dp[1];if(ys2&&ys2[lineHover]!=null){ctx.beginPath();ctx.arc(xs[lineHover],ys2[lineHover],3,0,Math.PI*2);ctx.fillStyle=dp[0];ctx.fill();}});
        drawLineTooltip(ctx,pts[lineHover],xs[lineHover],ys[lineHover],W,T,ih,{i:lineHover,S:cmp.S,G:cmp.G,M:cmp.M,s0:cmp.s0,g0:cmp.g0,m0:cmp.m0,reb:{btc:vals,spx:spxY,gld:gldY,mstr:mstrY}});
      }else{
        ctx.beginPath();ctx.arc(xs[lineHover],ys[lineHover],3,0,Math.PI*2);ctx.fillStyle='#22d3ee';ctx.fill();
        drawLineTooltip(ctx,pts[lineHover],xs[lineHover],ys[lineHover],W,T,ih);
      }
    }
    linePts=sx?{pts:pts,cmp:cmp}:pts;
    lineGeom={kind:'1d',pad:{l:L,r:R,t:T,b:B},plotW:iw,plotH:ih,n:n,xs:xs,ys:ys,hasLive:hasLive};
    window.__BTC_LINE_LAYOUT={w:W,h:H,padL:L,padR:R,padT:T,padB:B,plotW:iw,plotH:ih,n:n,yTicks:ticks,xLabels:xIdx.map(function(i){return lab[i];}),hasLive:hasLive,livePrice:hasLive?pts[n-1].v:null};
    window.__BTC_LINE_HOVER=lineHover;
    nativeTooltipBind(c);
    /* Redraw once Inter loads, so canvas text sharpens (YTD backup pattern). */
    if(!draw1DNative._fonts&&document.fonts&&document.fonts.load){
      draw1DNative._fonts=true;
      document.fonts.load('11px Inter').then(function(){if(lineDrawn&&linePts){if(linePts.cmp)draw1DNative(linePts.pts,linePts.cmp);else draw1DNative(linePts);}}).catch(function(){});
    }
    /* TA Stage 2: overlays draw here (not at the call site) so tooltip
       hover redraws (redrawNativeLine) repaint them too. */
    taAfterDraw('1d-line');
    return true;
  }catch(e){
    try{window.__BTC_DRAWERR={where:'draw1DNative',msg:String(e&&e.message||e)};}catch(_){}
    return false;
  }
}
function yTickDaily(v,sx,log){
  /* The Chart.js drawDaily yTick callback, replicated exactly (label text
     for a y value; null = no label and no gridline — Chart.js autoSkip
     removes such log ticks entirely). */
  if(sx){
    if(log){var m=v/Math.pow(10,Math.floor(Math.log10(v)+1e-9));if([1,2,5].indexOf(Math.round(m*1000)/1000)<0)return null;}
    /* Must-fix (27 Nov 2026): one decimal, so neighbouring nice ticks
       do not round to the same label (+3%, +3%, +1%, +1%, 0%, 0%).
       Nice steps are >= 0.1, so one decimal keeps every label distinct. */
    var q=v-100;return (q>0?'+':'')+(Math.abs(q)>=1000?Math.round(q).toLocaleString('en-US'):q.toFixed(1))+'%';
  }
  if(log){var l=Math.log10(v);if(Math.abs(l-Math.round(l))>1e-6)return null;}
  /* Must-fix (27 Nov 2026): a negative price formats with its sign and
     thousands separator ("$-20k"), not "$-20000" — the old vv>=1000 test
     sent every negative value to the unformatted branch. */
  var vv=curVal(v);return Math.abs(vv)>=1000?curSym()+(vv/1000).toLocaleString('en-US')+'k':curSym()+Math.round(vv).toLocaleString('en-US');
}
function drawDailyTooltip(ctx,i,d,cmp,reb,xs,ysMap,W,padT,plotH){
  /* Tooltip content = the Chart.js drawDaily tooltip (title: 'Now (live) · date'
     or the date; labels: BTC price (+ % in compare mode), S&P/Gold/MSTR price
     (+ %) when shown and non-null). In compare mode each label line gets the
     dataset's colour chip, as Chart.js does (displayColors). Positioned above
     the hovered index's average point height, flipping below if it would run
     off the top — Chart.js's default placement. */
  var n=d.length,hasLive=!!cmp.hasLive,sx=!!cmp.sx;
  var fp=function(x){return (x>=0?'+':'')+(Math.abs(x)>=1e4?Math.round(x).toLocaleString('en-US'):x.toFixed(1))+'%';};
  var title=(i===n-1&&hasLive)?'Now (live) · '+d[i][0]:d[i][0];
  var lines=[{t:title,c:null}];
  if(!sx){
    lines.push({t:fmt(d[i][1]),c:null}); /* L1: Chart.js drawDaily label is fmt(raw), no 'BTC ' prefix. */
  }else{
    lines.push({t:'BTC '+fmt(d[i][1])+' ('+fp(reb.btc[i]-100)+')',c:'#22d3ee'});
    if(cmp.S&&cmp.S[i]!=null&&cmp.s0)lines.push({t:'S&P 500 '+cmp.S[i].toLocaleString('en-US',{maximumFractionDigits:0})+' ('+fp(reb.spx[i]-100)+')',c:'#c4b5fd'});
    if(cmp.G&&cmp.G[i]!=null&&cmp.g0)lines.push({t:'Gold '+curSym()+curVal(cmp.G[i]).toLocaleString('en-US',{maximumFractionDigits:0})+' ('+fp(reb.gld[i]-100)+')',c:'#facc15'});
    if(cmp.M&&cmp.M[i]!=null&&cmp.m0)lines.push({t:'MSTR '+curSym()+curVal(cmp.M[i]).toLocaleString('en-US',{maximumFractionDigits:0})+' ('+fp(reb.mstr[i]-100)+')',c:'#f97316'});
  }
  /* TA Stage 2: indicator values for the hovered index, when overlays are on. */
  try{var _ta2=window.__BCTA&&window.__BCTA.taTip;if(_ta2){var _tl2=_ta2('daily-line',i);if(_tl2)lines=lines.concat(_tl2);}}catch(e){}
  ctx.font='11px Inter, sans-serif';
  var tw=0;lines.forEach(function(L){var w=ctx.measureText(L.t).width+(L.c?14:0);if(w>tw)tw=w;});tw+=16;
  var th=lines.length*14+10;
  var ysAt=[];['btc','spx','gld','mstr'].forEach(function(k){var a=ysMap[k];if(a&&a[i]!=null)ysAt.push(a[i]);});
  var ay=ysAt.length?ysAt.reduce(function(s,v){return s+v;},0)/ysAt.length:ysMap.btc[i];
  var tx=xs[i]-tw/2,ty=ay-th-10;
  if(ty<padT)ty=ay+10;
  if(ty+th>padT+plotH)ty=padT+plotH-th;
  if(tx<4)tx=4;
  if(tx+tw>W-4)tx=W-4-tw;
  ctx.fillStyle=psC('rgba(15,23,42,.92)','#ffffff');
  ctx.strokeStyle=psC('#334155','#e2e8f0');ctx.lineWidth=1;
  ctx.beginPath();ctx.rect(tx,ty,tw,th);ctx.fill();ctx.stroke();
  ctx.textAlign='left';ctx.textBaseline='top';
  lines.forEach(function(L,j){
    var lx=tx+8;
    if(L.c){ctx.fillStyle=L.c;ctx.fillRect(lx,ty+6+j*14+2,8,8);lx+=14;}
    ctx.fillStyle=j===0?psC('#e2e8f0','#0f172a'):psC('#e2e8f0','#334155');ctx.fillText(L.t,lx,ty+6+j*14);
  });
}
function drawDailyNative(d,cmp){
  /* Stage 2 Step 3 — implemented. The range daily line, drawn natively.
     Same data, same labels, same colours as the old Chart.js drawDaily.
     cmp: {sx, S, G, M, s0, g0, m0, hasLive, log} (prepared by drawDaily;
     S/G/M are the raw comparison closes, s0/g0/m0 their first non-null
     values). Returns true on success, false on failure (caller runs
     lineFail()). */
  try{
    if(!d||d.length<2||!cmp)return false;
    var c=$('bcC');if(!c)return false;
    var ctx=c.getContext('2d');
    var W=c.parentNode.clientWidth||640,H=c.parentNode.clientHeight||300;
    var dpr=window.devicePixelRatio||1; /* F5: uncapped, matching the candles on this shared canvas. */
    c.width=Math.round(W*dpr);c.height=Math.round(H*dpr);
    c.style.width=W+'px';c.style.height=H+'px';
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.clearRect(0,0,W,H);
    var n=d.length,hasLive=!!cmp.hasLive,sx=!!cmp.sx,LOG=!!cmp.log;
    var a=d[0][1];
    /* Plotted values: dollars when alone, rebased to 100 at the first close
       when comparing (Chart.js drawDaily datasets). */
    var btcY,spxY,gldY,mstrY;
    if(sx){
      btcY=d.map(function(p){return 100*p[1]/a;});
      spxY=cmp.S?cmp.S.map(function(v){return v!=null&&cmp.s0?100*v/cmp.s0:null;}):null;
      gldY=cmp.G?cmp.G.map(function(v){return v!=null&&cmp.g0?100*v/cmp.g0:null;}):null;
      mstrY=cmp.M?cmp.M.map(function(v){return v!=null&&cmp.m0?100*v/cmp.m0:null;}):null;
    }else{
      btcY=d.map(function(p){return p[1];});
      spxY=gldY=mstrY=null;
    }
    /* Y range over all plotted (non-null) values. */
    var lo=Infinity,hi=-Infinity;
    [btcY,spxY,gldY,mstrY].forEach(function(arr){
      if(!arr)return;
      for(var i=0;i<arr.length;i++){var v=arr[i];if(v!=null&&isFinite(v)){if(v<lo)lo=v;if(v>hi)hi=v;}}
    });
    if(!(hi>lo)){lo=(lo===Infinity?0:lo);hi=lo+1;}
    var R=12,T=18,B=44,ih=H-T-B;
    var Y,yTicks=[];
    if(LOG){
      /* Log scale: Chart.js extends the axis to the first/last ticks of
         its tick generation (wo) — the axis min is the largest tick-grid
         value <= the data min, the axis max the smallest tick-grid value
         >= the data max (e.g. data max $124,752 -> axis max $150,000;
         data min $15,787 -> axis min $10,000). Without this the line
         sits ~4px low at the top and the top compare tick ($200M) is
         missing. Ticks at 1/2/5 x 10^k within the extended range; labels
         only where the yTick callback passes. */
      if(!(lo>0))lo=1;
      lo=logGridFloor(lo);hi=logGridCeil(hi);
      var llo=Math.log10(lo),lhi=Math.log10(hi);
      if(!(lhi>llo))lhi=llo+1;
      Y=function(v){return T+ih*(1-(Math.log10(v)-llo)/(lhi-llo));};
      var k0=Math.floor(Math.log10(lo)),k1=Math.ceil(Math.log10(hi));
      for(var k=k0;k<=k1;k++){
        var pw=Math.pow(10,k);
        [1,2,5].forEach(function(m){var tv=m*pw;if(tv>=lo*(1-1e-9)&&tv<=hi*(1+1e-9))yTicks.push(tv);});
      }
    }else{
      /* Job 1: on 1W Line only, extend the y-range for trendlines
         (bounded, same as draw1DNative). Other Line ranges are not
         gated and already show their lines. */
      if(rng==='1W'){
        var _tlR2=null;
        try{if(window.__BTTA&&window.__BTTA.tlExpandRange)_tlR2=window.__BTTA.tlExpandRange(window.__BCTA.state(),d[d.length-1][1],Date.parse(d[d.length-1][0]+'T00:00:00Z'),lo,hi);}catch(e){}
        if(_tlR2&&isFinite(_tlR2.lo)&&isFinite(_tlR2.hi)&&_tlR2.hi>_tlR2.lo){lo=_tlR2.lo;hi=_tlR2.hi;}
      }
      /* Job 12: same for the overlays, on every Line range — a Bollinger
         band or MA line that runs outside the price range widens the
         axis instead of being clipped off the plot. No-op on compare
         (TA hides there). */
      var _ovR2=null;
      try{if(window.__BTTA&&window.__BTTA.ovExpandRange)_ovR2=window.__BTTA.ovExpandRange(window.__BCTA.state(),'daily-line',d.map(function(p){return p[1];}),lo,hi);}catch(e){}
      if(_ovR2&&isFinite(_ovR2.lo)&&isFinite(_ovR2.hi)&&_ovR2.hi>_ovR2.lo){lo=_ovR2.lo;hi=_ovR2.hi;}
      var ticks=nativeNiceTicks(lo,hi,ih);
      /* Job 12: half a tick step of headroom above the highest drawn
         value and below the lowest — a comparison low (YTD MSTR) never
         sits on the plot bottom, and the axis steps out by one nice
         tick when an extreme is within half a step of the edge. */
      var _hr2=nativeHeadroomTicks(ticks,lo,hi);if(_hr2)ticks=_hr2.ticks;
      /* Must-fix (27 Nov 2026): a price axis never goes below $0 (the
         10Y Line floor read $-20000, unformatted). A comparison % axis
         may go negative — it is not a price. */
      if(!sx){ticks=ticks.filter(function(t){return t>=0;});if(!ticks.length)ticks=[0];}
      if(ticks.length){lo=Math.min(lo,ticks[0]);hi=Math.max(hi,ticks[ticks.length-1]);}
      yTicks=ticks;
      Y=function(v){return T+ih*(1-(v-lo)/(hi-lo));};
    }
    /* Chart.js sizes the left margin to fit the widest y-axis label; a fixed
       62px clips long labels (Max + comparisons: '+179,999,900%'). Measure
       the labels and widen the margin when they need it; short labels keep
       the usual 62px. */
    ctx.font='11px Inter, sans-serif';
    var maxLabW=0;
    yTicks.forEach(function(v){var s=yTickDaily(v,sx,LOG);if(s!=null)maxLabW=Math.max(maxLabW,ctx.measureText(s).width);});
    var L=Math.max(62,Math.ceil(maxLabW)+12),iw=W-L-R;
    var X=function(i){return L+iw*(n===1?0.5:i/(n-1));};
    var xs=d.map(function(p,i){return X(i);});
    var btcYs=btcY.map(function(v){return Y(v);});
    /* TA Stage 2: publish the geometry for the overlay draw. closes are the
       raw BTC closes (not the rebased compare values — TA hides on compare). */
    TAGEOM={kind:'daily-line',xs:xs,yFor:Y,log:LOG,closes:d.map(function(p){return p[1];}),times:d.map(function(p){return Date.parse(p[0]+'T00:00:00Z');}),n:n,W:W,H:H,pad:{l:L,r:R,t:T,b:B},plotW:iw,plotH:ih,sx:sx};
    var spxYs=spxY?spxY.map(function(v){return v==null?null:Y(v);}):null;
    var gldYs=gldY?gldY.map(function(v){return v==null?null:Y(v);}):null;
    var mstrYs=mstrY?mstrY.map(function(v){return v==null?null:Y(v);}):null;
    /* Y gridlines + labels. A tick is drawn (gridline + label) only where
       the yTick callback returns a label: Chart.js's autoSkip removes the
       other log ticks entirely, gridlines included — for a non-compare log
       view that leaves only the powers of 10 (7 gridlines on Max, not the
       19 the 1/2/5 set would draw), and for a compare log view the 1/2/5
       set. (Linear ticks always get a label, so this changes nothing
       there.) The drawn ticks are what the layout hook reports. */
    ctx.strokeStyle=psC('rgba(255,255,255,.05)','rgba(15,23,42,.08)');ctx.fillStyle=psC('#9aa6bc','#475569');
    ctx.font='11px Inter, sans-serif';ctx.textAlign='right';ctx.textBaseline='middle';ctx.lineWidth=1;
    var drawnY=[];
    var prevLab=null; /* Must-fix (27 Nov 2026): never draw the same label twice in a row. */
    yTicks.forEach(function(v){
      var s=yTickDaily(v,sx,LOG);
      if(s==null)return;
      drawnY.push(v);
      var y=Y(v);
      ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(L+iw,y);ctx.stroke();
      if(s!==prevLab){ctx.fillText(s,L-6,y);prevLab=s;}
    });
    /* X labels: Chart.js autoSkip step (ceil(n/maxTicksLimit), 7 desktop /
       5 phone); the callback shows the year for n>400, else month-day.
       Must-fix (27 Nov 2026): on multi-year views the step landed twice
       in the same year and skipped others (5Y read 2024 twice with a
       blank gap; 10Y skipped 2017 and 2020) — so xIdx is the first point
       of each year instead: one label per year, evenly spaced in time. */
    var lab=d.map(function(p){return p[0];});
    var maxX=isPhone()?5:7,step=Math.max(1,Math.ceil(n/maxX)),xIdx=[];
    if(n>400){
      var _seenY={};
      for(var _yi=0;_yi<n;_yi++){var _y=lab[_yi].slice(0,4);if(!_seenY[_y]){_seenY[_y]=1;xIdx.push(_yi);}}
    }else{
      for(var i=0;i<n;i+=step)xIdx.push(i);
    }
    xIdx.forEach(function(i){
      var x=X(i);
      ctx.beginPath();ctx.moveTo(x,T);ctx.lineTo(x,T+ih);ctx.stroke();
    });
    ctx.textAlign='center';ctx.textBaseline='top';ctx.fillStyle=psC('#9aa6bc','#475569');
    /* Job 12: dedupe consecutive identical year labels — a safety net
       now that xIdx is the first point of each year (it used to blank
       the duplicate 2024 on 5Y). A duplicate is blanked (its gridline
       stays, only the label goes), so each year appears once. The
       same array feeds the drawn labels and the layout hook. */
    var xLab=xIdx.map(function(i){return n>400?lab[i].slice(0,4):lab[i].slice(5);});
    var _lastLab='';for(var _di=0;_di<xLab.length;_di++){if(xLab[_di]&&xLab[_di]===_lastLab)xLab[_di]='';else if(xLab[_di])_lastLab=xLab[_di];}
    nativeXLabels(ctx,xLab,xIdx.map(function(i){return X(i);}),L,R,W,T+ih+6);
    /* Trace a dataset's line. spanGaps bridges nulls into one path
       (S&P, MSTR); without it the line breaks at nulls (Gold). */
    function traceDS(ys,spanGaps){
      if(spanGaps){
        var fx=[],fy=[];
        for(var i=0;i<n;i++){if(ys[i]!=null){fx.push(xs[i]);fy.push(ys[i]);}}
        if(fx.length<2)return;
        ctx.beginPath();nativeTraceLine(ctx,fx,fy,.15,{l:L,t:T,r:L+iw,b:T+ih});ctx.stroke();
      }else{
        var run=[];
        function flush(){
          if(run.length>=2){ctx.beginPath();nativeTraceLine(ctx,run.map(function(p){return p.x;}),run.map(function(p){return p.y;}),.15,{l:L,t:T,r:L+iw,b:T+ih});ctx.stroke();}
          run=[];
        }
        for(var j=0;j<n;j++){
          if(ys[j]!=null)run.push({x:xs[j],y:ys[j]});
          else flush();
        }
        flush();
      }
    }
    /* Fill under the BTC line (non-compare, linear only — Chart.js
       fill:!LOG in the single-dataset case, fill:false when comparing). */
    if(!sx&&!LOG){
      ctx.beginPath();
      nativeTraceLine(ctx,xs,btcYs,.15,{l:L,t:T,r:L+iw,b:T+ih});
      ctx.lineTo(xs[n-1],T+ih);ctx.lineTo(xs[0],T+ih);ctx.closePath();
      ctx.fillStyle=nativeGradientFill(ctx,0,0,W,H);
      ctx.fill();
    }
    /* Lines, in dataset order (BTC first, then comparisons on top). */
    ctx.strokeStyle='#22d3ee';ctx.lineWidth=2;traceDS(btcYs,true);
    if(sx){
      if(spxYs){ctx.strokeStyle='#c4b5fd';ctx.lineWidth=1.6;traceDS(spxYs,true);}
      if(gldYs){ctx.strokeStyle='#facc15';ctx.lineWidth=1.6;traceDS(gldYs,false);}
      if(mstrYs){ctx.strokeStyle='#f97316';ctx.lineWidth=1.6;traceDS(mstrYs,true);}
    }
    /* Live "Now" dot (4px, same as Chart.js pointRadius) on the BTC line. */
    if(hasLive){ctx.beginPath();ctx.arc(xs[n-1],btcYs[n-1],4,0,Math.PI*2);ctx.fillStyle='#22d3ee';ctx.fill();}
    /* Hovered dots (3px, same as pointHoverRadius) on every visible
       dataset with a value at the hovered index. */
    if(lineHover>=0&&lineHover<n){
      var dots=[['#22d3ee',btcYs],['#c4b5fd',spxYs],['#facc15',gldYs],['#f97316',mstrYs]];
      dots.forEach(function(dp){
        var ys=dp[1];
        if(ys&&ys[lineHover]!=null){ctx.beginPath();ctx.arc(xs[lineHover],ys[lineHover],3,0,Math.PI*2);ctx.fillStyle=dp[0];ctx.fill();}
      });
      drawDailyTooltip(ctx,lineHover,d,cmp,{btc:btcY,spx:spxY,gld:gldY,mstr:mstrY},xs,{btc:btcYs,spx:spxYs,gld:gldYs,mstr:mstrYs},W,T,ih);
    }
    linePts={d:d,cmp:cmp};
    lineGeom={kind:'daily',pad:{l:L,r:R,t:T,b:B},plotW:iw,plotH:ih,n:n,xs:xs,ys:btcYs,ysSPX:spxYs,ysGLD:gldYs,ysMSTR:mstrYs,hasLive:hasLive,sx:sx,log:LOG};
    window.__BTC_LINE_LAYOUT={kind:'daily',w:W,h:H,padL:L,padR:R,padT:T,padB:B,plotW:iw,plotH:ih,n:n,yTicks:drawnY,xLabels:xLab,hasLive:hasLive,livePrice:hasLive?d[n-1][1]:null,sx:sx,log:LOG};
    window.__BTC_LINE_HOVER=lineHover;
    nativeTooltipBind(c);
    /* Redraw once Inter loads, so canvas text sharpens (YTD backup pattern). */
    if(!drawDailyNative._fonts&&document.fonts&&document.fonts.load){
      drawDailyNative._fonts=true;
      document.fonts.load('11px Inter').then(function(){if(lineDrawn&&linePts&&linePts.d)drawDailyNative(linePts.d,linePts.cmp);}).catch(function(){});
    }
    /* TA Stage 2: overlays draw here (not at the call site) so tooltip
       hover redraws (redrawNativeLine) repaint them too. */
    taAfterDraw('daily-line');
    return true;
  }catch(e){
    try{window.__BTC_DRAWERR={where:'drawDailyNative',msg:String(e&&e.message||e)};}catch(_){}
    return false;
  }
}

/* ===== end Stage 2 Step 2 native 1D line ===== */

/* Pill-expand morph, 3 Nov 2026: the dialog grows out of the pill that opened it (FLIP:
   measure the pill rect and the dialog's final rect, start the dialog scaled/translated
   to the pill rect, then animate transform + border-radius to the final rect). Reduced
   motion skips the animation entirely and the dialog appears at final size, as before.
   Chart content is drawn at final size throughout; the transform only scales it visually,
   and the chart is resized once the grow finishes. */
function reducedMotion(){try{return window.matchMedia('(prefers-reduced-motion: reduce)').matches;}catch(e){return false;}}
function morphToPill(el){
  var pr=el.getBoundingClientRect(),fr=dlg.getBoundingClientRect();
  if(!pr.width||!pr.height||!fr.width||!fr.height)return null;
  return {dx:pr.left-fr.left,dy:pr.top-fr.top,sx:pr.width/fr.width,sy:pr.height/fr.height};}
function open(from){if(INLINE)return;if(!dlg)build();opener=from||pill;if(menu&&!menu.hidden){var mb=$('mnavBtn');if(mb)mb.click();}
  rng='1D';CT='line';RGCT='line';RGGRAN=defaultGran(rng);LOG=false;clearCandState();dim.hidden=false;dlg.hidden=false;
  var morph=null;
  if(!reducedMotion()&&opener&&opener.getBoundingClientRect){
    dlg.style.visibility='hidden';place();morph=morphToPill(opener);
    if(morph){dlg.classList.add('bc-morph');dlg.style.transformOrigin='top left';
      dlg.style.transform='translate('+morph.dx+'px,'+morph.dy+'px) scale('+morph.sx+','+morph.sy+')';
      dlg.style.borderRadius='999px';dlg.style.visibility='';
      void dlg.offsetWidth;
      /* Double rAF: the scaled start state must actually paint before the
         transform is cleared, otherwise the browser coalesces the two
         states into one frame and the grow is never seen. */
      requestAnimationFrame(function(){requestAnimationFrame(function(){dlg.style.transform='';dlg.style.borderRadius='';});});
      var done=function(){dlg.removeEventListener('transitionend',done);dlg.classList.remove('bc-morph');nativeResize();};
      dlg.addEventListener('transitionend',done);}
    else{dlg.style.visibility='';place();}
  } else {place();}
  head();[pill,mp,document.getElementById('btcLive')].forEach(function(e){e&&e.setAttribute('aria-expanded','true');});
  $('bcRr').textContent='Loading…';$('bcX').focus();
  getData().then(draw).catch(function(){$('bcRr').textContent='Chart data unavailable right now.';});}
function close(){if(INLINE)return;if(!dlg||dlg.hidden)return;
  var finish=function(){cancelNativeResize();dlg.hidden=true;dim.hidden=true;dlg.classList.remove('bc-morph');dlg.style.transform='';dlg.style.borderRadius='';
    [pill,mp,document.getElementById('btcLive')].forEach(function(e){e&&e.setAttribute('aria-expanded','false');}); /* Batch B bug 2: open() sets btcLive true; close() must reset it */
    var o=opener&&opener.offsetParent?opener:pill;if(o&&o.offsetParent)o.focus();};
  if(!reducedMotion()&&opener&&opener.getBoundingClientRect){
    var m=morphToPill(opener);
    if(m){dlg.classList.add('bc-morph');dlg.style.transformOrigin='top left';
      dlg.style.transform='translate('+m.dx+'px,'+m.dy+'px) scale('+m.sx+','+m.sy+')';
      dlg.style.borderRadius='999px';
      var done=false,fin=function(){if(done)return;done=true;dlg.removeEventListener('transitionend',fin);finish();};
      dlg.addEventListener('transitionend',fin);setTimeout(fin,550);return;}}
  finish();}
/* Wire live-price refresh + open/close into the eager pill bridge.
   onLive mirrors the old paint() tail: head + tick flash on the popover
   price, then redraw when a chart is showing. */
var lastPaintUsdPanel=null;
P.onLive=function(){if(!dlg||dlg.hidden)return;head();
  var px=$('bcPx');
  if(px&&lastPaintUsdPanel!==null&&live.usd!==lastPaintUsdPanel){
    px.style.color=live.usd>=lastPaintUsdPanel?'#22c55e':'#ef4444';
    (function(el){setTimeout(function(){el.style.color='';},700);})(px);
  }
  lastPaintUsdPanel=live.usd;
  if(lineDrawn||lineRetry||candViewActive())draw();};
P.redraw=function(){if(dlg&&!dlg.hidden)draw();};
P.isOpen=function(){return !!dlg&&!dlg.hidden;};
P.remount=mountInline;
P.open=open;P.close=close;P.panelReady=true;
/* V2 6 Nov 2026: inline mount. On a page with a #bcInline host, build the
   chart once and show it there on page load — no pill, no dialog, no dim.
   Same data, same ranges (1D..Max), same candles, same compare toggles. */
function mountInline(){if(!INLINE)return;if(!dlg)build();dlg.hidden=false;
  getData().then(draw).catch(function(){$('bcRr').textContent='Chart data unavailable right now.';});}
if(INLINE)mountInline();
})();
/* re-land on #section after async content shifts layout (e.g. /#benchmarks, /#rules from other pages) */
window.addEventListener('load',function(){var h=location.hash.slice(1);if(!h)return;var el=document.getElementById(h);if(!el)return;
  [400,1500].forEach(function(t){setTimeout(function(){if(location.hash.slice(1)===h&&Math.abs(el.getBoundingClientRect().top)>120)el.scrollIntoView();},t);});});
