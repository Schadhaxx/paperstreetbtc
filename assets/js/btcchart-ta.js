/* TA Stage 1 (20 Nov 2026): chart-type pill + menu, TA pill, floating panel,
   RSI strip container. Loaded lazily from btcchart-panel.js (loadTA), own pin.
   All overlays are OFF by default and NOTHING IS DRAWN YET — the toggles only
   set state (saved per device) and the after-draw hook keeps the strip in
   sync. Drawing lands in Stage 2 (indicators) and Stage 4 (trendlines).
   No Chart.js references anywhere. */
(function(){
/* ---------- Stage 2: pure indicator maths (no window refs) — unit-tested
   in tests/test_ta_indicators.js against reference values computed
   independently in Python (ps-ta-stage1/ref_values.py). Every function
   returns an array the same length as the input, with null before the
   first valid point. NEVER draw a wrong value: null means "not valid yet".
   SMA/EMA seed: the first value is the SMA of the first `per` closes.
   RSI: Wilder smoothing; first value at index `per` (needs `per` changes).
   Bollinger: middle = SMA, bands = middle +/- mult * population stddev. */
function taSMA(closes,per){
  var n=closes.length,out=new Array(n),i,s;
  for(i=0;i<n;i++)out[i]=null;
  if(!(per>=1)||n<per)return out;
  s=0;for(i=0;i<per;i++)s+=closes[i];
  out[per-1]=s/per;
  for(i=per;i<n;i++){s+=closes[i]-closes[i-per];out[i]=s/per;}
  return out;
}
function taEMA(closes,per){
  var n=closes.length,out=new Array(n),i,s,k;
  for(i=0;i<n;i++)out[i]=null;
  if(!(per>=1)||n<per)return out;
  s=0;for(i=0;i<per;i++)s+=closes[i];
  out[per-1]=s/per;k=2/(per+1);
  for(i=per;i<n;i++)out[i]=closes[i]*k+out[i-1]*(1-k);
  return out;
}
function taBB(closes,per,mult){
  var n=closes.length,mid=taSMA(closes,per),up=new Array(n),lo=new Array(n),i,j,mu,va,d;
  for(i=0;i<n;i++){up[i]=null;lo[i]=null;}
  if(!(per>=1)||n<per)return {mid:mid,up:up,lo:lo};
  mult=(mult==null?2:mult);
  for(i=per-1;i<n;i++){
    mu=mid[i];va=0;
    for(j=i-per+1;j<=i;j++){d=closes[j]-mu;va+=d*d;}
    va=Math.sqrt(va/per);
    up[i]=mu+mult*va;lo[i]=mu-mult*va;
  }
  return {mid:mid,up:up,lo:lo};
}
function taRSI(closes,per){
  var n=closes.length,out=new Array(n),i,ag=0,al=0,dd,g,l;
  for(i=0;i<n;i++)out[i]=null;
  if(!(per>=1)||n<=per)return out;
  for(i=1;i<=per;i++){dd=closes[i]-closes[i-1];if(dd>0)ag+=dd;else al-=dd;}
  ag/=per;al/=per;
  out[per]=al===0?100:(ag===0?0:100-100/(1+ag/al));
  for(i=per+1;i<n;i++){
    dd=closes[i]-closes[i-1];g=dd>0?dd:0;l=dd<0?-dd:0;
    ag=(ag*(per-1)+g)/per;al=(al*(per-1)+l)/per;
    out[i]=al===0?100:(ag===0?0:100-100/(1+ag/al));
  }
  return out;
}
/* ---------- Stage 4: Smart Trendlines drawing (pure, unit-tested) ----------
   The job (tools/ta_lines.py) emits schema-1 ta-lines.json:
   {v:1, kind:'ta-lines', asOf, timeframes:{'1h'|'4h'|'1d': {asOf, atr,
   lastClose, levels[], sloped[], missingSupport, missingResistance}}}.
   Per-timeframe asOf is the LAST BAR'S OPEN (job: asOf=iso_ms(bars[-1][0])):
   the 1h asOf is the forming hour's open (0-60 min old at generation),
   the 4h asOf is the last COMPLETE 4h bucket's open (4-8 h old — agg4h
   only keeps complete buckets), the 1d asOf is the forming day's open
   (0-24 h old). A fresh file's asOf is therefore already hours old, so
   the stale windows below are measured from the bar open, not the job
   run. levels: at most 3 ranked + at most 1 range-extreme slot
   (extreme:true, mixed into levels, NOT a separate array) — the caps are
   the JOB's validate(); the front end draws what's in the file and never
   pads a side (rule 2). sloped: at most 2, each {kind, slope (price per
   candle index of the line's timeframe), anchor:{t,price}, priceNow}.
   missingSupport/missingResistance only mean "no ranked horizontal and
   no EXT on that side" — sloped lines on that side still draw (rule 1). */
var TL_STALE_MS={'1h':2*3600*1000+20*60*1000,'4h':2*4*3600*1000+30*60*1000,'1d':2*24*3600*1000+2*3600*1000};
var TL_INTERVAL_MS={'1h':3600*1000,'4h':4*3600*1000,'1d':24*3600*1000};
var TL_RANK={'1h':0,'4h':1,'1d':2};
var TL_URL='https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/ta-lines.json';
function tlFin(v){return typeof v==='number'&&isFinite(v);}
function tlPlainFmt(v){return '$'+Math.round(v).toLocaleString('en-US');}
function tlTimeMs(v){
  /* The pack ref's _t_ms: ms numbers as-is, seconds numbers x1000, ISO
     strings parsed, Date objects via getTime. Anything else -> NaN. */
  if(v instanceof Date)return v.getTime();
  if(typeof v==='number')return v>1e11?v:v*1000;
  if(typeof v==='string'){var m=Date.parse(v);return isFinite(m)?m:NaN;}
  return NaN;
}
function tlBarT(b){
  /* One candle's open time (ms): [t,...] arrays or {t}/{time} objects. */
  if(Array.isArray(b))return tlTimeMs(b[0]);
  if(b&&typeof b==='object')return tlTimeMs(b.t!==undefined?b.t:b.time);
  return tlTimeMs(b);
}
function tlIsoMs(ms){
  /* "2026-11-20T21:00:00Z" — the ref's iso_ms (no milliseconds). */
  var d=new Date(ms);
  if(!isFinite(d.getTime()))return '';
  return d.toISOString().replace(/\.\d{3}Z$/,'Z');
}
function tlRound2(v){return Math.round(v*100)/100;}
function tlTfOk(t){
  /* Mirror of the pack ref's _tf_ok (and the job's validate() key check):
     the five keys must be present and levels/sloped must be arrays.
     missingSupport/missingResistance are NOT required (validate() does
     not require them either). Caps and price finiteness are the job's
     validate(); a bad LINE is skipped by the selector, never fatal to
     its timeframe. */
  if(!t||typeof t!=='object')return false;
  var keys=['asOf','lastClose','atr','levels','sloped'],i;
  for(i=0;i<keys.length;i++)if(!(keys[i] in t))return false;
  if(!Array.isArray(t.levels)||!Array.isArray(t.sloped))return false;
  return true;
}
function tlValidate(data){
  /* Header only: v 1, kind 'ta-lines', a timeframes object. A partial
     file (one timeframe missing or bad) is NOT a bad file — the selector
     fails closed PER TIMEFRAME and still draws the present, fresh ones
     (pack case partial_file_missing_4h). The job's own validate() does
     require all three timeframes at publish time; the front end is the
     forgiving reader. */
  if(!data||typeof data!=='object')return {ok:false,reason:'not an object'};
  if(data.v!==1||data.kind!=='ta-lines')return {ok:false,reason:'bad schema'};
  if(!data.timeframes||typeof data.timeframes!=='object')return {ok:false,reason:'no timeframes'};
  return {ok:true,reason:''};
}
function tlIsStale(tf,asOf,now){
  /* Stale is per timeframe, measured from that timeframe's own asOf
     (last bar OPEN, not the document asOf). Stale after 2x the bar
     interval + grace (pack rule 6, adopted): 1h 2h20m, 4h 8h30m, 1d 50h.
     The approved plan's 3x rule (1h 45m, 4h 3h, 1d 36h) is unworkable
     against the real asOf: a FRESH 1h file is already 0-60 min old at
     generation (forming bar) and a fresh 4h file 4-8 h old (last complete
     bucket), so 3x would hide a fresh file's 1h lines on arrival and its
     4h lines always — the pack's own today cases (asOf 55 min old, lines
     expected to draw) prove it. 2x+grace covers one missed job run plus
     skew; 1d 50h matches the job's own DAILY_MAX_AGE_DAYS=2. Bad or
     unknown input is stale. */
  var after=TL_STALE_MS[tf];
  if(!after)return true;
  var aMs=tlTimeMs(asOf),nMs=tlTimeMs(now);
  if(!isFinite(aMs)||!isFinite(nMs))return true;
  return (nMs-aMs)>after;
}
function tlChartTf(st){
  /* The chart's OWN timeframe. 5Y/10Y/Max: none ("Not available on this
     range"). Every other view uses its own timeframe's lines PLUS the
     higher ones (rule 5, same-or-higher — see tlSelectLinesForChart). */
  if(!st||typeof st.rng!=='string')return null;
  if(/^(5Y|10Y|Max)$/.test(st.rng))return null;
  if(st.rng==='1D')return st.CT==='4h'?'4h':'1h';
  if(st.rng==='1W')return (st.RGCT==='candles'&&st.RGGRAN==='4h')?'4h':'1d';
  return '1d';
}
/* ---------- Drawing fixes Stage 1 (21 Nov 2026): per-view gating ----------
   Some overlays do not work on some views (live scan, 21 Nov 2026). On a
   gated view the toggle stays visible but disabled (greyed out) and the
   overlay does not draw; the same toggle works normally on other views.
   The saved state (S) is untouched — gating only gates the interaction
   and the drawing, so the overlay comes back on a view where it works.
   Comparison-on behaviour is unchanged (TA hides while a comparison is
   on, the note shows). Pure functions, unit-tested in
   tests/test_ta_gating.js. Corrected lists (Sunil, 21 Nov ~19:16):
   Bollinger gated on EVERY range; SMA 200 kept on YTD/1Y, gated only
   on 1D/1W; EMA 50 gated on 1W, EMA 200 on 1D/1W (same as the SMAs).
   Job 1 (21 Nov 2026): trendlines are NO LONGER gated on Line 1D/1W —
   the Line y-range expands to include the drawn lines (tlExpandRange),
   so the toggle is back on there.
   Job 2 (21 Nov 2026): Bollinger is NO LONGER gated anywhere, and the
   200s (SMA 200, EMA 200) are NO LONGER gated on 1D/1W — the warm-up
   is now pre-fetched at TA init (preWarm) and retried on failure, so
   the indicators are computed from history before the visible window
   instead of from the window alone. SMA 20/50 and EMA 50 stay gated
   on 1W, per the settled lists.
   Job 3 (22 Nov 2026): RSI is NO LONGER gated anywhere — the strip now
   has a scale, shaded 30/70 bands and a live value, and Job 2's
   pre-warm gives it its 14 closes on every view.
   Job 8 (22 Nov 2026): SMA 200 on 6M is DECIDED — it reads right on
   6M Line (200-day MA) and 6M weekly candles (200-week MA): valid from
   index 0, matches an independent recomputation, smooth, draws a full
   line. It stays ungated there. But the 200s (SMA 200, EMA 200) are
   NOW gated on monthly-granularity candle views: a 200-month average
   needs 200 months of BTC history and only ~195 exist (Aug 2010–
   Nov 2026), so the lines can never compute there — the toggle used
   to promise a line that never appears. Line views are unaffected
   (daily closes) and so are daily/weekly/4h candles.
   Job 9 (22 Nov 2026): Bollinger + ALL six MAs are gated on yearly-
   granularity candle views (10Y yearly): the shortest, SMA/EMA 20,
   needs 20 yearly closes and only 17 exist (2010–2026), so none of
   them can ever compute there. RSI is NOT gated — its 14 closes are
   covered by the warm-up (6 yearly closes before the window) + the
   11 visible ones, so it draws from visible index 7. */
var TA_GATE_BB_RANGES=[];
var TA_GATE_MA={sma20:[],sma50:[],sma200:[],ema50:[],ema200:[]};
/* Job 12 (22 Nov 2026): SMA 20/50 + EMA 50 are no longer gated on 1W —
   the values already computed correctly there (Job 8 measured SMA 20
   $81,325 vs EMA 20 $80,964, 0.4% apart; the 1W probe shows all six MAs
   valid from index 0 after Job 2's pre-warm), so only the gate was
   hiding them. The 200s were ungated on 1D/1W by Job 2 the same way. */
function taIsLineView(st){
  /* Line view: 1D uses CT, every other range uses RGCT. Max gained
     candles in Job 11 (22 Nov 2026), so it is a line view only while
     RGCT is not candles — the generic check below already says that.
     Trendlines on Max stay off by design (tlChartTf returns null),
     so gating never applies to them. */
  if(!st||typeof st.rng!=='string')return false;
  return st.rng==='1D'?st.CT==='line':st.RGCT!=='candles';
}
function taGated(key,st){
  /* The four panel switches. 'ma' (the group switch) is never gated —
     the per-chip gating below covers the MAs that don't. Unknown keys
     and unknown views are not gated (fail open: the draw path already
     guards on geometry/state). Bollinger is no longer gated anywhere
     (Job 2, 21 Nov 2026 — the warm-up is pre-fetched, so it is computed
     from history before the visible window on every range). */
  if(!st||typeof st.rng!=='string')return false;
  if(key==='tl')return false; /* Job 1 (21 Nov 2026): trendlines are no longer gated on Line 1D/1W — the Line y-range now expands to include the drawn lines (tlExpandRange), so they draw there. */
  if(key==='bb'){
    /* Job 9 (22 Nov 2026): Bollinger is gated on yearly-granularity
       candle views — a 20-period band needs 20 yearly closes and only
       17 exist (2010–2026), so it can never compute there. */
    if(st.RGCT==='candles'&&st.RGGRAN==='yearly')return true;
    return TA_GATE_BB_RANGES.indexOf(st.rng)>=0;
  }
  if(key==='rsi')return false; /* Job 3 (22 Nov 2026): RSI is no longer gated anywhere — the strip now has a scale, shaded 30/70 bands and a live value, and Job 2's pre-warm gives it its 14 closes on every view. */
  return false;
}
function taMaGated(maKey,st){
  /* Per-MA-chip gating. SMA 200 on 6M is DECIDED (Job 8, 22 Nov 2026) —
     it reads right on 6M Line and 6M weekly candles, so it stays ungated
     there; SMA 200 on YTD/1Y is KEPT (Sunil, 21 Nov ~19:16).
     EMA 20 is never gated; EMA 50 follows its SMA twin. Job 2
     (21 Nov 2026): the 200s (SMA 200, EMA 200) are no longer gated on
     1D/1W — the warm-up is pre-fetched, so they are computed from
     history before the visible window there too. Job 8 (22 Nov 2026):
     the 200s ARE gated on monthly-granularity candle views — a
     200-month average needs 200 months of BTC history and only ~195
     exist (Aug 2010–Nov 2026), so the lines can never compute there.
     Line views are unaffected (daily closes, 200-day MA) and the gate
     keys on RGCT==='candles', so a stale RGGRAN on a Line view cannot
     gate anything. */
  if(!st||typeof st.rng!=='string')return false;
  if((maKey==='sma200'||maKey==='ema200')&&st.RGCT==='candles'&&st.RGGRAN==='monthly')return true;
  /* Job 9 (22 Nov 2026): ALL MAs are gated on yearly-granularity
     candle views — the shortest (SMA/EMA 20) needs 20 yearly closes
     and only 17 exist (2010–2026), so none of them can ever compute
     there. (The monthly gate above covers only the 200s; on yearly
     even the 20s fail.) Job 12 (22 Nov 2026): the 1W gate is gone —
     SMA 20/50 + EMA 50 ungated there (see TA_GATE_MA above). */
  if(st.RGCT==='candles'&&st.RGGRAN==='yearly')return true;
  var g=TA_GATE_MA[maKey];
  return !!g&&g.indexOf(st.rng)>=0;
}
function tlSlopedPriceAt(sl,tMs,tf){
  /* Sloped lines live in candle-index space: price = anchor + slope x
     (candles since the anchor). BTC's bars are uniform in wall clock
     (Coinbase 15-min/hourly/daily/4h, no holes), so the candle count is
     the elapsed time divided by the line timeframe's interval — which
     stays correct across gaps in the visible window and across chart
     granularities (15-min points, weekly/monthly candles). The exact
     index math over an explicit candle array (pack rule 8, incl. the
     weekend-hole case) lives in _tlRefSlopedEdge, used by tlSelectLines. */
  var iv=TL_INTERVAL_MS[tf]||3600*1000;
  var aMs=Date.parse(sl.anchor.t);
  return sl.anchor.price+sl.slope*((tMs-aMs)/iv);
}
function tlLabel(line,chartTf){
  /* EXT is labelled "range low" / "range high", never like a ranked line.
     A line from another timeframe than the chart's carries its tf label
     (defensive: the chart only ever draws its own tf's lines).
     Job 4 (22 Nov 2026): the label is ALWAYS the level's own USD price
     (tlPlainFmt), never the display-currency formatter. The old fmtP
     path converted USD->CAD at the LIVE rate (curVal = v * CUR.rate,
     rate = lastCad/lastPrice, recomputed on every live tick), so the
     same fixed level drifted while you watched — C$83,548 -> 83,637 ->
     83,646 as the FX rate ticked, though the level never moved. A
     level's price is fixed in the file, so its label is anchored to it;
     it changes only when the file changes. Sloped lines still use
     edgePrice (which legitimately moves one slope-step per new candle);
     only the FX drift on top of it is gone. */
  var fmt=tlPlainFmt;
  var s='';
  if(line.tf&&chartTf&&line.tf!==chartTf)s=line.tf+' ';
  if(line.extreme)s+=(line.kind==='support'?'range low ':'range high ');
  var p=line.price;
  if(line.type==='sloped'){
    /* Sloped lines carry edgePrice (the price at the chart's right edge,
       the same value the line is drawn to), not price — labelling them
       with line.price prints $NaN. A non-finite edge hides the label
       (''), never the line; tlDrawLines skips empty labels. */
    p=line.edgePrice;
    if(!isFinite(Number(p)))return '';
  }
  return s+fmt(p);
}
function _tlTfLines(tf,timeframe,livePrice,slopedEdge){
  /* Shared per-timeframe selection core (rules 1, 3, 4). slopedEdge(sl)
     returns {edge:number, endpoints:?} or null to omit that sloped line.
     Levels and sloped lines are drawn exactly as the file has them
     (rule 2, no padding); a bad line is skipped, never fatal to its
     timeframe. missingSupport/missingResistance are ignored here
     (rule 1). Rule 3: never draw a support (or "range low") above the
     live chart price, or a resistance (or "range high") below it — judged
     by the live CLOSE, so a wick through with the close still holding is
     fine. Rule 4: a flipped level (broken:true, kind already the new
     side) draws as a normal ranked line of the new kind. Returns
     {drawn:[], omitted:[]} of browser-shaped items. */
  var out={drawn:[],omitted:[]},L,S,r;
  if(!tf||!Array.isArray(tf.levels)||!Array.isArray(tf.sloped)||!isFinite(livePrice))return out;
  tf.levels.forEach(function(lv){
    if(!lv||typeof lv!=='object')return;
    var price=Number(lv.price);
    if(!isFinite(price))return;
    if(lv.kind!=='support'&&lv.kind!=='resistance')return;
    L={type:'level',kind:lv.kind,price:price,extreme:!!lv.extreme,broken:!!lv.broken,tf:timeframe};
    if(lv.kind==='support'&&price>livePrice){L.omit='support above live price';out.omitted.push(L);}
    else if(lv.kind==='resistance'&&price<livePrice){L.omit='resistance below live price';out.omitted.push(L);}
    else out.drawn.push(L);
  });
  tf.sloped.forEach(function(sl){
    if(!sl||typeof sl!=='object')return;
    if(sl.kind!=='support'&&sl.kind!=='resistance')return;
    S={type:'sloped',kind:sl.kind,slope:Number(sl.slope),anchor:sl.anchor,extreme:false,broken:!!sl.broken,tf:timeframe};
    r=slopedEdge(sl);
    if(!r||!isFinite(r.edge)){S.omit='no live edge';out.omitted.push(S);return;}
    S.edgePrice=r.edge;
    if(r.endpoints)S.endpoints=r.endpoints;
    if(sl.kind==='support'&&r.edge>livePrice){S.omit='support above live price';out.omitted.push(S);}
    else if(sl.kind==='resistance'&&r.edge<livePrice){S.omit='resistance below live price';out.omitted.push(S);}
    else out.drawn.push(S);
  });
  return out;
}
function _tlRefSlopedEdge(sl,candles){
  /* Pack rule 8: sloped prices in CANDLE-INDEX space over the passed
     candle array (the line timeframe's own bars). price = anchor +
     slope x (i - i0); a weekend-sized hole is one step, not 48 hours of
     slope. No candles passed -> the file's priceNow is the live-edge
     price (still rule-3 bound). Candles passed and the anchor is NOT in
     them -> OMIT. (The pack's ref falls back to priceNow here; the spec
     says omit — the spec's reading is implemented, flagged in the
     handover. No pack case covers this edge.) */
  if(!candles||!candles.length){
    var pn=Number(sl.priceNow);
    if(!isFinite(pn))return null;
    return {edge:pn,endpoints:null};
  }
  var aMs=tlTimeMs(sl.anchor&&sl.anchor.t),ap=Number(sl.anchor&&sl.anchor.price),slope=Number(sl.slope);
  if(!isFinite(aMs)||!isFinite(ap)||!isFinite(slope))return null;
  var times=candles.map(function(b){return tlBarT(b);});
  var i0=times.indexOf(aMs);
  if(i0<0)return null;
  var lastI=times.length-1;
  var p1=tlRound2(ap+slope*(lastI-i0));
  return {edge:p1,endpoints:[{t:tlIsoMs(aMs),t_ms:aMs,price:tlRound2(ap)},{t:tlIsoMs(times[lastI]),t_ms:times[lastI],price:p1}]};
}
function _tlRefItem(ln,tfLabel){
  /* The ref's draw-item shape: {kind, style, label, tf_label} + price
     (horizontals and the priceNow fallback) or endpoints (sloped, when
     candles are given). */
  var style=ln.extreme?'ext':'ranked';
  var label=ln.extreme?(ln.kind==='support'?'range low':'range high'):'';
  if(ln.type==='sloped'&&ln.endpoints)return {endpoints:ln.endpoints,kind:ln.kind,style:'ranked',label:'',tf_label:tfLabel};
  return {price:ln.type==='sloped'?ln.edgePrice:ln.price,kind:ln.kind,style:style,label:label,tf_label:tfLabel};
}
function tlSelectLines(file,timeframe,chartTf,livePrice,now,candles){
  /* Port of the pack's ref_select_lines.select_lines: the draw list for
     ONE file timeframe on a chart of chartTf. Rule 5: only same-or-higher
     timeframes (lower-TF lines are not drawn); same-TF lines have
     tf_label '', higher-TF lines carry '4h'/'1d'. Rule 6: the pack stale
     windows. Invalid, partial or stale data for this timeframe yields [].
     This is the function the pack's 16 cases run against. */
  if(!file||typeof file!=='object'||file.v!==1||file.kind!=='ta-lines')return [];
  if(!(timeframe in TL_RANK)||!(chartTf in TL_RANK))return [];
  if(TL_RANK[timeframe]<TL_RANK[chartTf])return [];
  var tfs=file.timeframes;
  if(!tfs||typeof tfs!=='object'||!tfs[timeframe])return [];
  var tf=tfs[timeframe];
  if(!tlTfOk(tf))return [];
  if(tlIsStale(timeframe,tf.asOf,now))return [];
  var live=Number(livePrice);
  if(!isFinite(live))return [];
  var tfLabel=timeframe===chartTf?'':timeframe;
  var sel=_tlTfLines(tf,timeframe,live,function(sl){return _tlRefSlopedEdge(sl,candles);});
  return sel.drawn.map(function(ln){return _tlRefItem(ln,tfLabel);});
}
function tlSelectLinesForChart(file,chartTf,livePrice,nowMs,lastMs){
  /* Browser selection (rule 5, same-or-higher): every timeframe at or
     above the chart's own, in rank order, each validated and stale-
     checked on its own asOf (rule 6). A sloped line's live-edge price is
     recomputed from its anchor + slope at the chart's last candle time
     (time-based, which equals the ref's index math on BTC's uniform
     bars — see tlSlopedPriceAt). Returns {drawn, omitted, freshTfs,
     perTf, fileOk, fileReason} for the drawer, the panel and the probe. */
  var out={drawn:[],omitted:[],freshTfs:[],perTf:{},fileOk:false,fileReason:''};
  var v=tlValidate(file);
  if(!v.ok){out.fileReason=v.reason;return out;}
  out.fileOk=true;
  if(!chartTf||!(chartTf in TL_RANK))return out;
  var live=Number(livePrice);
  ['1h','4h','1d'].forEach(function(tf){
    if(TL_RANK[tf]<TL_RANK[chartTf]){out.perTf[tf]='lower';return;}
    var tfd=file.timeframes[tf];
    if(!tfd){out.perTf[tf]='missing';out.omitted.push({type:'tf',tf:tf,omit:'missing timeframe'});return;}
    if(!tlTfOk(tfd)){out.perTf[tf]='bad';out.omitted.push({type:'tf',tf:tf,omit:'bad '+tf});return;}
    if(tlIsStale(tf,tfd.asOf,nowMs)){out.perTf[tf]='stale';out.omitted.push({type:'tf',tf:tf,omit:'stale'});return;}
    out.perTf[tf]='live';
    out.freshTfs.push(tf);
    var sel=_tlTfLines(tfd,tf,live,function(sl){
      var aMs=tlTimeMs(sl.anchor&&sl.anchor.t),ap=Number(sl.anchor&&sl.anchor.price),slope=Number(sl.slope);
      if(!isFinite(aMs)||!isFinite(ap)||!isFinite(slope)||!isFinite(lastMs))return null;
      return {edge:ap+slope*((lastMs-aMs)/(TL_INTERVAL_MS[tf]||3600*1000)),endpoints:null};
    });
    out.drawn.push.apply(out.drawn,sel.drawn);
    out.omitted.push.apply(out.omitted,sel.omitted);
  });
  return out;
}
if(typeof module!=='undefined'&&module.exports){module.exports={sma:taSMA,ema:taEMA,bollinger:taBB,rsi:taRSI,tlValidate:tlValidate,tlTfOk:tlTfOk,tlIsStale:tlIsStale,tlChartTf:tlChartTf,tlSlopedPriceAt:tlSlopedPriceAt,tlSelectLines:tlSelectLines,tlSelectLinesForChart:tlSelectLinesForChart,tlLabel:tlLabel,tlStaleAfterMs:TL_STALE_MS,tlTimeMs:tlTimeMs,taGated:taGated,taMaGated:taMaGated,taIsLineView:taIsLineView,tlExpandLoHi:tlExpandLoHi,tlExpandRange:tlExpandRange,ovExpandRange:ovExpandRange,allowedSizes:allowedSizes,sizeLabel:sizeLabel};return;}
/* ---------- Stage 2: overlay drawing (browser only) ---------- */
function fmtP(v){try{return (window.__BTCP&&window.__BTCP.fmt)?window.__BTCP.fmt(v):('$'+Math.round(v).toLocaleString('en-US'));}catch(e){return '$'+Math.round(v);}}
function psC2(d,l){try{return window.psC?window.psC(d,l):d;}catch(e){return d;}}
function isCmp(){try{return !!(API.cmp&&API.cmp());}catch(e){return false;}}
function viewState(){try{return API.state();}catch(e){return null;}}
var warmCache={},warmAsked={};
function warmAsync(g){
  /* Intraday warm-up: lazy background fetch (panel-side), cached per kind.
     Until it lands, [] — draw from the valid point inside the window. */
  var key=g.kind;
  if(g.kind==='candles-1d')key=API.state().CT==='4h'?'candles-1d-4h':'candles-1d-1h';
  else if(g.kind==='candles-range')key='candles-range-4h';
  /* Re-ask while the cache is empty: a failed fetch must not leave
     warmCache stuck at []. The panel-side retry (10s after a failure)
     heals its own cache, but warmAsked used to block this module from
     ever re-reading it — so a kind asked before the retry stayed empty
     for the session. warmFetch starts only one fetch per kind, so
     re-asking is cheap. The callback redraws only when the data arrived
     asynchronously (async flag): when it was already cached, the
     callback fires synchronously inside the current draw, and a redraw
     there would nest a full render inside it (and inflate the measured
     frame time) — the current draw already has the data, so no redraw
     is needed. */
  if(!warmAsked[key]||!warmCache[key]||!warmCache[key].length){
    warmAsked[key]=true;
    var async=false;
    try{API.warmFetch(key,function(c){warmCache[key]=c||[];if(c&&c.length&&API.draw&&async)API.draw();});}catch(e){}
    async=true;
  }
  return warmCache[key]||[];
}
function warmFor(g){
  try{
    if(g.kind==='daily-line'||g.kind==='candles-range'){
      if(g.kind==='candles-range'&&API.state().RGGRAN==='4h')return warmAsync(g);
      var w=API.warmSync?API.warmSync():[];
      return w||[];
    }
    return warmAsync(g);
  }catch(e){return [];}
}
function preWarm(){
  /* Job 2 (Indicator windows, 21 Nov 2026): the intraday warm-up used to
     start only when an overlay was turned on (afterDraw calls warmFor
     only if something is on), so the user saw the indicators computed
     from the visible window alone — Bollinger starting 19 points late,
     SMA 200 missing entirely — until the fetch landed seconds later,
     and forever if it failed. Kick the four intraday fetches off here,
     at TA init, while the user is still browsing the panel, so the
     history is usually cached before anything is turned on. No-op
     callbacks: nothing is drawn yet, and the normal warmFor path picks
     the cached data up (and redraws when it lands, if an overlay is on
     by then). The range views need no pre-warm: their warm-up is
     synchronous from DATA (taWarmSync). One fetch per kind per session;
     the three hourly/4h kinds share one 50-day fetch (panel-side). */
  try{
    if(!API||!API.warmFetch)return;
    ['1d-line','candles-1d-1h','candles-1d-4h','candles-range-4h'].forEach(function(k){
      try{API.warmFetch(k,function(){});}catch(e){}
    });
  }catch(e){}
}
var valsCache={key:null,vals:null};
function computeVals(g,warm){
  /* Indicators over warm-up + visible closes, sliced to the visible window.
     Cache keyed by kind, length, first/last close (live ticks change the
     last close), warm-up length and settings — so the tooltip hook (called
     mid-draw) and afterDraw share one computation per draw. */
  var mas=maOn();
  var key=[g.kind,g.n,warm.length,g.closes[0],g.closes[g.n-1],mas.join(','),S.ma,S.bb,S.rsi].join('|');
  if(valsCache.key===key&&valsCache.vals)return valsCache.vals;
  var full=warm.concat(g.closes),w=warm.length,vals={n:g.n,w:w};
  if(S.ma&&mas.length){vals.mas={};mas.forEach(function(k){var per=parseInt(k.slice(3),10);vals.mas[k]=(k.indexOf('ema')===0?taEMA(full,per):taSMA(full,per)).slice(w);});}
  if(S.bb){var b=taBB(full,20,2);vals.bbMid=b.mid.slice(w);vals.bbUp=b.up.slice(w);vals.bbLo=b.lo.slice(w);}
  if(S.rsi)vals.rsi=taRSI(full,14).slice(w);
  valsCache={key:key,vals:vals};
  return vals;
}
function traceLine(ctx,vals,xs,yFor,col,width,dash){
  var started=false,i,x,y;
  ctx.beginPath();
  for(i=0;i<vals.length;i++){
    if(vals[i]==null)continue;
    x=xs[i];y=yFor(vals[i]);
    if(!started){ctx.moveTo(x,y);started=true;}
    else ctx.lineTo(x,y);
  }
  if(!started)return;
  ctx.strokeStyle=col;ctx.lineWidth=width;
  if(dash)ctx.setLineDash(dash);else ctx.setLineDash([]);
  ctx.stroke();ctx.setLineDash([]);
}
function drawOverlays(g,vals){
  var c=el('bcC');if(!c)return;
  var ctx=c.getContext('2d');if(!ctx)return;
  var st=viewState();
  /* Must-fix (27 Nov 2026): clip to the plot — the price axis now floors
     at $0, so a Bollinger band that runs below $0 (a 2-sigma band can go
     negative on a wild window) must stop at the plot bottom instead of
     painting over the x labels. The RSI strip is drawn separately by
     afterDraw, outside this clip. */
  ctx.save();
  ctx.beginPath();ctx.rect(g.pad.l,g.pad.t,g.plotW,g.plotH);ctx.clip();
  /* Stage 1 gating: a gated overlay does not draw on this view, even
     though its values are still computed (computeVals stays ungated, so
     the debug probe and the Stage 2 value checks are unaffected). */
  if(S.bb&&vals.bbUp&&!taGated('bb',st)){
    traceLine(ctx,vals.bbUp,g.xs,g.yFor,psC2('#a78bfa','#7c3aed'),1.25);
    traceLine(ctx,vals.bbLo,g.xs,g.yFor,psC2('#a78bfa','#7c3aed'),1.25);
    traceLine(ctx,vals.bbMid,g.xs,g.yFor,psC2('#a78bfa','#7c3aed'),1,[4,3]);
  }
  if(S.ma&&vals.mas)maOn().forEach(function(k){if(vals.mas[k]&&!taMaGated(k,st))traceLine(ctx,vals.mas[k],g.xs,g.yFor,maCol(k),2);});
  ctx.restore();
}
function rsiLastVal(vals){
  /* Last non-null RSI value, for the strip header. */
  if(!vals||!vals.rsi)return null;
  for(var i=vals.rsi.length-1;i>=0;i--)if(vals.rsi[i]!=null)return vals.rsi[i];
  return null;
}
function drawRsiStrip(g,vals){
  if(!rsiEl)return;
  /* Live value in the header (Job 3): the header used to read "RSI 14 —"
     because nothing ever wrote into its <b>. Update it on every draw —
     including when collapsed (the canvas is hidden then, but this
     function still runs) — so the current value is always visible. */
  var lv=rsiLastVal(vals);
  var hb=rsiEl.querySelector('.ta-rsi-t b');
  if(hb)hb.textContent=lv==null?'—':lv.toFixed(1);
  var cv=rsiEl.querySelector('canvas');if(!cv)return;
  var ctx=cv.getContext('2d');if(!ctx)return;
  /* The strip canvas is the same CSS width as the chart box, so the main
     plot xs map 1:1 (scaled defensively if they ever differ). A 30px left
     gutter holds the scale labels; the trace is shifted right by the
     gutter and compressed to fit, so the labels never sit under the line. */
  var W=cv.parentNode.clientWidth||g.W,H=cv.parentNode.clientHeight||76;
  if(!W||!H)return;
  var dpr=window.devicePixelRatio||1;
  cv.width=Math.round(W*dpr);cv.height=Math.round(H*dpr);
  cv.style.width=W+'px';cv.style.height=H+'px';
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,W,H);
  var GUT=30,T=6,B=6,ih=H-T-B;
  var Y=function(v){return T+ih*(1-v/100);};
  var X=function(x){return GUT+x*(W-GUT)/g.W;};
  /* Shaded overbought/oversold bands (Job 3, Sunil 21 Nov ~22:23: shaded
     bands, the most visually available option on iPhone — not just
     stronger lines). Very light tints so the purple line stays readable;
     30 and 70 are the band edges. */
  ctx.fillStyle=psC2('rgba(239,68,68,0.09)','rgba(185,28,28,0.07)');
  ctx.fillRect(GUT,Y(100),W-GUT,Y(70)-Y(100));
  ctx.fillStyle=psC2('rgba(34,197,94,0.09)','rgba(21,128,61,0.07)');
  ctx.fillRect(GUT,Y(30),W-GUT,Y(0)-Y(30));
  /* Band edges, solid and readable (the old 18%-opacity dashes were
     effectively invisible), plus a faint 50 midline. */
  ctx.lineWidth=1;ctx.setLineDash([]);
  ctx.strokeStyle=psC2('rgba(255,255,255,0.32)','rgba(15,23,42,0.32)');
  [30,70].forEach(function(v){var y=Y(v);ctx.beginPath();ctx.moveTo(GUT,y);ctx.lineTo(W,y);ctx.stroke();});
  ctx.strokeStyle=psC2('rgba(255,255,255,0.16)','rgba(15,23,42,0.16)');
  ctx.setLineDash([2,3]);
  var y50=Y(50);ctx.beginPath();ctx.moveTo(GUT,y50);ctx.lineTo(W,y50);ctx.stroke();
  ctx.setLineDash([]);
  /* Scale labels in the gutter (Job 3). Solid slate so they read on
     either theme; 10px, 9px on the short strip. */
  ctx.fillStyle=psC2('#94a3b8','#64748b');
  ctx.font=(H>=70?'10px':'9px')+' Inter, sans-serif';
  ctx.textAlign='right';ctx.textBaseline='middle';
  [0,30,50,70,100].forEach(function(v){ctx.fillText(String(v),GUT-4,Y(v));});
  if(!vals.rsi)return;
  traceLine(ctx,vals.rsi,g.xs.map(X),Y,psC2('#a78bfa','#7c3aed'),1.5);
}
/* ---------- Stage 4: Smart Trendlines drawing (browser only) ----------
   Fetches ta-lines.json only when Trends is on, draws the chart's own
   timeframe's lines on #bcC after the price series (same x/y mapping),
   and reports status to the TA panel. Never Desk: this module only ever
   loads for the BTC charts. */
var tlCache={data:null,ok:false,reason:'',fetchedAt:0,inflight:null};
var tlStatus='off'; /* off | unavailable | gated | updating | live */
var tlLast=null; /* last draw result, for the __TA_TL_DEBUG probe */
var TL_FETCH_MS=10*60*1000;
function tlSetStatus(s){tlStatus=s;syncTlStatus();}
function tlFetch(){
  /* One in-flight fetch at most; at most one fetch per 10 min. A failed
     or invalid fetch is cached as an error, not hammered per draw. */
  if(tlCache.inflight)return tlCache.inflight;
  var now=Date.now();
  if(tlCache.fetchedAt&&now-tlCache.fetchedAt<TL_FETCH_MS)return null;
  var ctl=null;
  try{ctl=window.AbortController?new AbortController():null;}catch(e){}
  var to=0;
  if(ctl)to=setTimeout(function(){try{ctl.abort();}catch(e){}},8000);
  var p=fetch(TL_URL+'?t='+now,ctl?{cache:'no-store',signal:ctl.signal}:{cache:'no-store'}).then(function(r){
    if(to)clearTimeout(to);
    if(!r.ok)throw new Error('http '+r.status);
    return r.json();
  }).then(function(j){
    var v=tlValidate(j);
    tlCache.data=v.ok?j:null;tlCache.ok=v.ok;tlCache.reason=v.ok?'':v.reason;tlCache.fetchedAt=Date.now();tlCache.inflight=null;
    syncTlStatus();
    if(API.draw)API.draw();
    return tlCache.data;
  }).catch(function(e){
    if(to)clearTimeout(to);
    tlCache.data=null;tlCache.ok=false;tlCache.reason='fetch failed';tlCache.fetchedAt=Date.now();tlCache.inflight=null;
    syncTlStatus();
    return null;
  });
  tlCache.inflight=p;
  return p;
}
function tlCol(kind){return kind==='support'?psC2('#22c55e','#15803d'):psC2('#ef4444','#b91c1c');}
function tlDrawLevel(ctx,g,ln){
  var y=g.yFor(ln.price);
  if(!isFinite(y))return;
  ctx.beginPath();
  ctx.moveTo(g.pad.l,y);ctx.lineTo(g.pad.l+g.plotW,y);
  ctx.strokeStyle=tlCol(ln.kind);ctx.lineWidth=1.5;
  if(ln.extreme){ctx.setLineDash([5,4]);ctx.globalAlpha=0.6;}
  else ctx.setLineDash([]);
  ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;
  return y;
}
function tlDrawSloped(ctx,g,ln,tf){
  /* From the anchor forward, in candle-index space: the price at each
     visible candle comes from the anchor + slope x (candles since the
     anchor), so the line stays correct across gaps and granularities. */
  var anchorMs=Date.parse(ln.anchor.t);
  var iv=TL_INTERVAL_MS[tf]||3600*1000;
  var times=g.times||[];
  var i0=0,i;
  if(times.length){
    i0=g.n;
    for(i=0;i<g.n;i++){if(times[i]>=anchorMs){i0=i;break;}}
    if(i0===g.n)return null; /* anchor is past the live edge: nothing to draw */
  }
  var started=false;
  ctx.beginPath();
  for(var j=i0;j<g.n;j++){
    var tMs=times.length?times[j]:anchorMs+(j-i0)*iv;
    var p=ln.anchor.price+ln.slope*((tMs-anchorMs)/iv);
    var y=g.yFor(p);
    if(!isFinite(y))continue;
    var x=g.xs[j];
    if(!started){ctx.moveTo(x,y);started=true;}
    else ctx.lineTo(x,y);
  }
  if(!started)return null;
  ctx.strokeStyle=tlCol(ln.kind);ctx.lineWidth=1.5;ctx.setLineDash([]);
  ctx.stroke();
  return g.yFor(ln.edgePrice);
}
function tlDrawLabels(ctx,g,labels,liveClose){
  /* Right-edge labels, one per drawn line, de-collided so they never
     overlap each other or the live price. Skipped when the line's y is
     off the plot. */
  var T=g.pad.t,B=g.pad.t+g.plotH,liveY=g.yFor(liveClose);
  /* Keep a label when its line is on the plot at all (even just inside
     the edge); clamp the drawn position so the pill stays fully inside
     instead of dropping the label for a line at the edge. */
  var items=labels.filter(function(lb){return lb.y!=null&&isFinite(lb.y)&&lb.y>=T&&lb.y<=B;});
  items.sort(function(a,b){return a.y-b.y;});
  /* Must-fix (27 Nov 2026): pills are 16px tall, so the old 14px
     spacing (12px from the live price) still let neighbours touch, and
     nudging only downward piled ten tags up at the plot bottom on 1D
     (three 4h tags collided there). Spacing is now 17px from everything,
     and the search runs both ways from the ideal spot (down, then up,
     alternating) so a tag keeps its price instead of sliding to the
     bottom; the last resort is the ideal spot itself (an overlap beats
     a dropped label). */
  var SP=17,placed=[];
  items.forEach(function(lb){
    /* Clamp into the plot first, then de-collide — so the clamp can never
       push a label into its neighbour. */
    var y0=Math.min(Math.max(lb.y,T+8),B-8),y=y0;
    var clash=function(yy){
      if(isFinite(liveY)&&Math.abs(yy-liveY)<SP)return true;
      for(var k=0;k<placed.length;k++)if(Math.abs(yy-placed[k])<SP)return true;
      return false;
    };
    if(clash(y0)){
      var found=false;
      for(var s=1;s<=30&&!found;s++){
        var yd=y0+s*SP,yu=y0-s*SP;
        if(yd<=B-8&&!clash(yd)){y=yd;found=true;break;}
        if(yu>=T+8&&!clash(yu)){y=yu;found=true;break;}
      }
      if(!found)y=y0;
    }
    placed.push(y);
    lb.y=y;
  });
  ctx.font='11px Inter, sans-serif';ctx.textAlign='right';ctx.textBaseline='middle';
  items.forEach(function(lb){
    var x=g.pad.l+g.plotW-4;
    var w=ctx.measureText(lb.text).width;
    ctx.fillStyle=psC2('rgba(2,6,23,.72)','rgba(255,255,255,.85)');
    ctx.fillRect(x-w-8,lb.y-8,w+12,16);
    ctx.fillStyle=lb.col;
    ctx.fillText(lb.text,x-2,lb.y);
  });
}
function tlExpandLoHi(drawn,lo,hi){
  /* Job 1 (Line-view trendlines): pure helper — the expanded y-range
     covering the drawn lines' prices, bounded to one span per side
     (total at most 3x the original span) so the price action is never
     squashed into a thin band. Lines beyond the bound stay clipped —
     they belong on wider views. Returns {lo,hi} or null if no change. */
  if(!Array.isArray(drawn)||!drawn.length)return null;
  if(!isFinite(lo)||!isFinite(hi)||!(hi>lo))return null;
  var mn=Infinity,mx=-Infinity;
  drawn.forEach(function(ln){
    var p=ln&&ln.type==='sloped'?ln.edgePrice:ln&&ln.price;
    if(isFinite(p)){if(p<mn)mn=p;if(p>mx)mx=p;}
  });
  if(!isFinite(mn)||!isFinite(mx))return null;
  var span=hi-lo;
  var nlo=Math.min(lo,Math.max(mn,lo-span));
  var nhi=Math.max(hi,Math.min(mx,hi+span));
  if(nlo===lo&&nhi===hi)return null;
  return {lo:nlo,hi:nhi};
}
function tlExpandRange(st,livePrice,lastMs,lo,hi){
  /* Job 1: the range the Line view should use when trendlines are on —
     the drawn lines' prices (same selection as the drawer), bounded by
     tlExpandLoHi. Null when trendlines are off, the file is not cached,
     a comparison is on (TA hides), or nothing needs expanding. The panel
     calls this before computing its y-mapping; when the TA module or the
     file is not ready yet it returns null and the panel keeps the tight
     range, and the file-load redraw picks the expansion up. */
  if(!S.tl)return null;
  if(isCmp())return null;
  if(!tlCache.data||!tlCache.ok)return null;
  var tf=tlChartTf(st);
  if(!tf)return null;
  if(!isFinite(livePrice)||!isFinite(lastMs))return null;
  var sel=tlSelectLinesForChart(tlCache.data,tf,livePrice,Date.now(),lastMs);
  if(!sel.drawn||!sel.drawn.length)return null;
  return tlExpandLoHi(sel.drawn,lo,hi);
}
function ovExpandRange(st,kind,closes,lo,hi){
  /* Job 12 (22 Nov 2026): the range the chart should use when an
     overlay is on — the Bollinger band and MA line extremes over the
     visible window. The panel calls this before computing its
     y-mapping, so a band or MA that runs outside the price range
     widens the axis instead of being clipped off the plot (1W Line:
     the upper band poked above the plot top; 1W daily candles: the
     200s sat below the visible range and drew nothing). Only the
     overlays that will actually draw count (on + not gated); RSI is
     a strip below the chart, not on the plot. Null when overlays are
     off, a comparison is on (TA hides), the data is not ready, or
     nothing needs expanding. The panel falls back to its tight range
     and the warm-up/file-load redraw picks the expansion up.
     Must-fix (27 Nov 2026): the expansion is UNBOUNDED — the old
     one-span bound (via tlExpandLoHi, same as the trendlines) clipped
     a plunging lower band on a crash week (1W: the bound stopped at
     $51,822 while the band reached $51,406). Overlays are computed
     from the data, so they cannot run away the way a hand-placed
     trendline can — those keep the one-span bound. */
  if(!S||(!S.bb&&!S.ma))return null;
  if(isCmp())return null;
  if(!st||!Array.isArray(closes)||!closes.length)return null;
  if(!isFinite(lo)||!isFinite(hi)||!(hi>lo))return null;
  var g={kind:kind,n:closes.length,closes:closes};
  var warm=warmFor(g);
  var vals=computeVals(g,warm);
  var prices=[];
  if(S.bb&&vals.bbUp&&vals.bbLo&&!taGated('bb',st)){
    vals.bbUp.forEach(function(v){if(isFinite(v))prices.push({price:v});});
    vals.bbLo.forEach(function(v){if(isFinite(v))prices.push({price:v});});
  }
  if(S.ma&&vals.mas)maOn().forEach(function(k){
    if(!vals.mas[k]||taMaGated(k,st))return;
    vals.mas[k].forEach(function(v){if(isFinite(v))prices.push({price:v});});
  });
  if(!prices.length)return null;
  /* Unbounded (see the docstring): the values are computed from the
     data, so a band that runs far outside the price range still widens
     the axis to include it. */
  var mn=Infinity,mx=-Infinity;
  prices.forEach(function(p){if(isFinite(p.price)){if(p.price<mn)mn=p.price;if(p.price>mx)mx=p.price;}});
  if(!isFinite(mn)||!isFinite(mx))return null;
  var nlo=Math.min(lo,mn),nhi=Math.max(hi,mx);
  if(nlo===lo&&nhi===hi)return null;
  return {lo:nlo,hi:nhi};
}
function tlDrawLines(g){
  /* Draws this chart's timeframe's lines plus the higher ones (rule 5,
     same-or-higher). Returns the draw result for the debug probe. Draws
     nothing (and never an error over the chart) when Trends is off, the
     file is missing/invalid, every timeframe is stale, or the range has
     no lines. */
  var res={tf:null,liveClose:null,status:'off',lines:[],omitted:[],fileOk:false,stale:false,freshTfs:[],perTf:{}};
  tlLast=res;
  if(!S.tl){tlSetStatus('off');return res;}
  var st=null;
  try{st=API.state();}catch(e){}
  var tf=tlChartTf(st);
  res.tf=tf;
  if(!tf){res.status='unavailable';tlSetStatus('unavailable');return res;}
  tlFetch();
  var liveClose=g.closes[g.n-1];
  res.liveClose=liveClose;
  if(!tlCache.data||!tlCache.ok){res.status='updating';tlSetStatus('updating');return res;}
  res.fileOk=true;
  var lastMs=(g.times&&g.times.length)?g.times[g.n-1]:NaN;
  var sel=tlSelectLinesForChart(tlCache.data,tf,liveClose,Date.now(),lastMs);
  res.freshTfs=sel.freshTfs;res.perTf=sel.perTf;
  res.lines=sel.drawn;res.omitted=sel.omitted;
  /* Stale if any same-or-higher timeframe is stale (the chart is not
     showing its full set); missing/bad timeframes do not set this. */
  res.stale=['1h','4h','1d'].some(function(t2){return TL_RANK[t2]>=TL_RANK[tf]&&sel.perTf[t2]==='stale';});
  if(!sel.freshTfs.length){res.status='updating';tlSetStatus('updating');return res;}
  sel.drawn.forEach(function(ln){ln.label=tlLabel(ln,tf);});
  sel.omitted.forEach(function(ln){if(ln.type==='level'||ln.type==='sloped')ln.label=tlLabel(ln,tf);});
  res.status='live';
  tlSetStatus('live');
  var c=el('bcC');if(!c)return res;
  var ctx=c.getContext('2d');if(!ctx)return res;
  /* Clip to the plot so a line outside the visible price range never
     paints over the axis labels or the x labels. */
  ctx.save();
  ctx.beginPath();ctx.rect(g.pad.l,g.pad.t,g.plotW,g.plotH);ctx.clip();
  var labels=[];
  sel.drawn.forEach(function(ln){
    var y=null;
    if(ln.type==='level')y=tlDrawLevel(ctx,g,ln);
    else y=tlDrawSloped(ctx,g,ln,ln.tf);
    /* An empty label (a sloped line whose edge isn't finite) draws no
       pill — the line itself still draws. */
    if(y!=null&&ln.label)labels.push({y:y,text:ln.label,col:tlCol(ln.kind)});
  });
  ctx.restore();
  tlDrawLabels(ctx,g,labels,liveClose);
  return res;
}
function syncTlStatus(){
  if(!panelEl)return;
  var n=panelEl.querySelector('.ta-tl-status');
  if(!n)return;
  var hidden=true,text='';
  if(S.tl&&!isCmp()){
    hidden=false;
    if(tlStatus==='unavailable')text='Not available on this range';
    else if(tlStatus==='gated')text='Not available on this view';
    else if(tlStatus==='live'){
      var c=tlLast&&tlLast.lines?tlLast.lines.length:0;
      /* The timeframes actually fresh (same-or-higher than the chart's):
         "Live · 1h + 4h + 1d · 12 lines", or "Live · 4h + 1d · 6 lines"
         when the chart's own timeframe is stale but higher ones draw. */
      var tfs=tlLast&&tlLast.freshTfs&&tlLast.freshTfs.length?tlLast.freshTfs.join(' + '):(tlLast&&tlLast.tf?tlLast.tf:'');
      text=c>0?('Live · '+tfs+' · '+c+' line'+(c===1?'':'s')):('Live · '+tfs+' · no lines on this view');
    }
    else text='Trendlines updating…';
  }
  if(n.hidden!==hidden)n.hidden=hidden;
  if(n.textContent!==text)n.textContent=text;
}
function syncCmpNote(){
  if(!panelEl)return;
  var n=panelEl.querySelector('.ta-cmp');
  if(n)n.hidden=!isCmp();
}
/* Job 6: the same note, OUTSIDE the TA panel — a plain line under the
   pills row, so it reads without opening the panel. It shows only when
   a comparison is hiding something that WOULD draw (nPlotDrawing()>0 —
   the plot overlays only; the RSI strip still draws on a comparison,
   so it alone never triggers the note): with TA off there is nothing
   to explain, and with everything gated turning the comparison off
   still would not draw anything, so the note would lie. The panel note
   above keeps its own rule (shows whenever a comparison is on, panel
   open). The element is created once by TA init and lives in the dialog
   flow (popover + clock page share the build). */
/* Must-fix (27 Nov 2026): the RSI strip is a separate pane below the
   chart, computed from the BTC closes alone — it keeps drawing while a
   comparison is on, so the note now says the PLOT overlays hide (the
   old "TA shows on BTC alone" was no longer true for RSI). One string,
   shared by the panel note and the outside note. */
var CMP_NOTE_TEXT='Trendlines, Bollinger and moving averages show on BTC alone. Turn off comparisons to see them — the RSI strip still shows.';
var cmpNoteOutEl=null;
function buildCmpNoteOut(){
  if(cmpNoteOutEl||!dlg)return cmpNoteOutEl;
  var row=dlg.querySelector('#bcRow2');
  var n=document.createElement('div');
  n.className='ta-cmp-out';
  n.textContent=CMP_NOTE_TEXT;
  n.hidden=true;
  if(row&&row.parentNode)row.parentNode.insertBefore(n,row.nextSibling);
  else dlg.appendChild(n);
  cmpNoteOutEl=n;
  return n;
}
function syncCmpNoteOut(){
  if(!cmpNoteOutEl)return;
  var show=isCmp()&&nPlotDrawing()>0;
  cmpNoteOutEl.hidden=!show;
  /* Job 6: the dialog class inserts the note's grid row on the clock
     page (see the .ta-cmp-out-on rules in btcchart-ta.css); harmless in
     the popover, which is not a grid. */
  if(dlg)dlg.classList.toggle('ta-cmp-out-on',show);
}
function taTipLines(kind,i){
  try{
    if(!nOn())return null;
    if(isCmp())return null;
    var g=API.geom?API.geom():null;
    if(!g||g.kind!==kind||!g.closes||i==null||i<0||i>=g.n)return null;
    var warm=warmFor(g);
    var vals=computeVals(g,warm);
    var out=[];
    var st=viewState();
    /* Stage 1 gating: the tooltip lists only the overlays actually drawn
       on this view — a gated overlay's values are computed but not shown. */
    if(S.ma&&vals.mas)maOn().forEach(function(k){if(vals.mas[k]&&vals.mas[k][i]!=null&&!taMaGated(k,st))out.push({t:MA_LBL[k]+' '+fmtP(vals.mas[k][i]),c:maCol(k)});});
    if(S.bb&&!taGated('bb',st)&&vals.bbUp&&vals.bbUp[i]!=null&&vals.bbLo[i]!=null)out.push({t:'BB 20 '+fmtP(vals.bbLo[i])+'\u2013'+fmtP(vals.bbUp[i]),c:psC2('#a78bfa','#7c3aed')});
    if(S.rsi&&!taGated('rsi',st)&&vals.rsi&&vals.rsi[i]!=null)out.push({t:'RSI '+vals.rsi[i].toFixed(1),c:psC2('#a78bfa','#7c3aed')});
    return out.length?out:null;
  }catch(e){return null;}
}
if(window.__BTTA)return;
var API=window.__BCTA;
if(!API)return;
var LSKEY='ps-ta-v1';
var DEF={tl:false,bb:false,ma:false,maSet:{},rsi:false,rsiCol:false,last1DSize:'1h'};
var S={};
function loadS(){try{var raw=window.localStorage.getItem(LSKEY);if(raw){var o=JSON.parse(raw);for(var k in DEF)S[k]=(k in o)?o[k]:DEF[k];
  if(!S.maSet||typeof S.maSet!=='object')S.maSet={};
  else S.maSet=Object.assign({},S.maSet);
  /* Migrate a Stage 2 stored state (maKind/maPer, one at a time) to the
     stacking set: the old single MA becomes the only enabled one. */
  if(!o.maSet&&o.maKind&&o.maPer){S.maSet={};if(o.ma)S.maSet[String(o.maKind).toLowerCase()+o.maPer]=true;}
  return;}}catch(e){}for(var k2 in DEF)S[k2]=DEF[k2];S.maSet={};}
function saveS(){try{window.localStorage.setItem(LSKEY,JSON.stringify(S));}catch(e){}}
loadS();
var CHEV='<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2 3.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
var COL={tl:'#22c55e',bb:'#a78bfa',ma:'#f472b6',rsi:'#a78bfa'};
/* ---------- Stage 3 fix (item 6): stacking moving averages ----------
   SMA/EMA 20, 50 and 200 can be on at the same time, each with its own
   distinct colour (dark / light via psC2). The enabled set is S.maSet
   (keys 'sma20' … 'ema200'); S.ma is the master on/off for the group.
   The six chips in the TA panel are the legend: each chip carries its
   MA's colour dot + label, and the tooltip lists each enabled MA in its
   own colour.
   Must-fix (27 Nov 2026): SMA 200 is near-white / slate, not emerald —
   the old #34d399 was too close to the support-trendline green #22c55e
   to tell apart on the chart. */
var MA_KEYS=['sma20','sma50','sma200','ema20','ema50','ema200'];
var MA_COL={sma20:['#f472b6','#db2777'],sma50:['#fbbf24','#d97706'],sma200:['#e8eef7','#334155'],ema20:['#38bdf8','#0284c7'],ema50:['#fb923c','#ea580c'],ema200:['#a3e635','#65a30d']};
var MA_LBL={sma20:'SMA 20',sma50:'SMA 50',sma200:'SMA 200',ema20:'EMA 20',ema50:'EMA 50',ema200:'EMA 200'};
function maCol(k){var c=MA_COL[k];return c?psC2(c[0],c[1]):psC2('#f472b6','#db2777');}
function maOn(){if(!S.ma)return [];return MA_KEYS.filter(function(k){return S.maSet&&S.maSet[k];});}
function maCount(){return maOn().length;}
var dlg=null,typBtn=null,taBtn=null,rsiEl=null,menuEl=null,panelEl=null,inited=false;
var menuOpen=false,panelOpen=false;

function $(s,r){return (r||document).querySelector(s);}
function el(id){return document.getElementById(id);}
function isPriceMode(){try{return document.documentElement.classList.contains('v4-fs-price');}catch(e){return false;}}
function stageEl(){try{var st=API.stage();if(st)return st;}catch(e){}return dlg;}
/* The floating layer (menu / panel) lives in the stage on the clock page and
   in the dialog in the popover, so it renders inside the Fullscreen-API
   element in both full-screen modes. Never body. */
function floatParent(){return API.inline()?stageEl():dlg;}
function nOn(){return (S.tl?1:0)+(S.bb?1:0)+maCount()+(S.rsi?1:0);}
/* Job 6: the overlays actually DRAWING on this view — what the badge
   shows. nOn() counts toggles; a comparison hides the plot overlays,
   a gated MA on 1W does not draw, and trendlines with no lines on this
   view (5Y/10Y/Max, file still loading) do not draw. The guards match
   the draw path (drawOverlays / drawRsiStrip / tlDrawLines) so the badge
   and the drawing stay in lockstep by construction.
   Must-fix (27 Nov 2026): the RSI strip is a separate pane below the
   chart, so it keeps drawing on a comparison — nDrawing counts it
   there (1), while nPlotDrawing counts only the plot overlays (what a
   comparison hides, and what the outside note's condition uses).
   ignoreCmp answers "what WOULD draw if the comparison were off" (the
   external note's condition); tlLast is only refreshed by a draw, so a
   comparison that was on before the overlays were turned on leaves tl
   unknown — the panel note covers that path. */
function nPlotDrawing(){
  var st=viewState(),n=0;
  if(S.tl&&tlStatus==='live'&&tlLast&&tlLast.lines&&tlLast.lines.length)n++;
  if(S.bb&&!taGated('bb',st))n++;
  if(S.ma)maOn().forEach(function(k){if(!taMaGated(k,st))n++;});
  return n;
}
function nDrawing(ignoreCmp){
  if(!ignoreCmp&&isCmp()){
    /* A comparison hides the plot overlays; the RSI strip still draws. */
    return (S.rsi&&!taGated('rsi',viewState()))?1:0;
  }
  var n=nPlotDrawing();
  if(S.rsi&&!taGated('rsi',viewState()))n++;
  return n;
}

/* ---------- positioning: place a float under an anchor, clamped inside its
   offsetParent (the stage or the dialog), with a capped height ---------- */
function placeFloat(anchor,fl){
  var op=fl.offsetParent||document.body;
  var ar=anchor.getBoundingClientRect(),pr=op.getBoundingClientRect();
  var ox=op.clientLeft||0,oy=op.clientTop||0;
  var pw=fl.offsetWidth,ph=fl.offsetHeight;
  var left=Math.min(ar.right-pr.left-ox,pr.right-pr.left-ox)-pw;
  if(left<0)left=0;
  var top=(ar.bottom-pr.top-oy)+6;
  fl.style.left=left+'px';fl.style.top=top+'px';
  var maxH=window.innerHeight-6-(ar.bottom+6);
  if(top+ph>window.innerHeight-6&&maxH>120){fl.style.maxHeight=maxH+'px';fl.style.overflowY='auto';}
  else{fl.style.maxHeight='';fl.style.overflowY='';}
}

/* ---------- TA pill (count badge) + RSI strip ---------- */
/* Job 6: the pill badge shows the drawing count (nDrawing), not the
   toggle count (nOn) — it was stuck on the toggle count because syncPill
   only ran on TA toggle clicks, never on a draw. It now also runs in
   afterDraw, so a comparison toggle or a range change re-counts at once.
   The write is idempotent (pillN cache): afterDraw runs on every live
   tick, and rewriting the pill's innerHTML each time would churn the DOM
   for a count that has not changed. */
var pillN=null;
function syncPill(){
  if(!taBtn)return;
  var n=nDrawing(false);
  if(n===pillN)return;
  pillN=n;
  taBtn.classList.toggle('act',n>0);
  taBtn.innerHTML='<span>TA</span>'+(n?'<i class="ta-n">'+n+'</i>':CHEV);
  taBtn.setAttribute('aria-label','Technical analysis'+(n?', '+n+' on':''));
}
function syncRsi(){
  if(!rsiEl||!dlg)return;
  /* Must-fix (27 Nov 2026): the strip is a separate pane below the
     chart, computed from the BTC closes alone — it does NOT hide on a
     comparison (only the plot overlays do). The old Stage 2 rule hid
     it with them, so RSI never showed while comparing. */
  rsiEl.hidden=!S.rsi||taGated('rsi',viewState());
  dlg.classList.toggle('ta-rsi-on',!!S.rsi);
  if(S.rsi){
    rsiEl.classList.toggle('col',!!S.rsiCol);
    var t=rsiEl.querySelector('.ta-rsi-t');
    if(t)t.setAttribute('aria-expanded',S.rsiCol?'false':'true');
  }
}

/* ---------- chart-type menu ---------- */
/* Job 11 (22 Nov 2026): Max offers Daily/Weekly/Monthly/Yearly
   (default Daily, the finest size offered). 3M/6M/YTD gain Daily;
   5Y offers Daily/Weekly/Monthly and 10Y Daily/Monthly/Yearly (both
   default Daily, the finest size offered). 1Y keeps Monthly/Weekly
   (default Weekly). Sizes list coarsest first, matching the old
   order (1M Weekly then Daily, 1W Daily then 4H). */
function allowedSizes(rng){
  if(rng==='1D')return ['1h','4h'];
  if(rng==='1W')return ['daily','4h'];
  if(rng==='1M')return ['weekly','daily'];
  if(rng==='3M'||rng==='6M'||rng==='YTD')return ['monthly','weekly','daily'];
  if(rng==='1Y')return ['monthly','weekly'];
  if(rng==='5Y')return ['yearly','monthly','weekly','daily'];
  if(rng==='10Y')return ['yearly','monthly','daily'];
  if(rng==='Max')return ['yearly','monthly','weekly','daily'];
  return [];
}
function sizeLabel(sz){
  return sz==='1h'?'1H candles':sz==='4h'?'4H candles':sz==='daily'?'Daily':sz==='weekly'?'Weekly':sz==='yearly'?'Yearly':'Monthly';
}
function typeLabel(st){
  if(st.rng==='1D')return st.CT==='line'?'Line':(st.CT==='1h'?'1H candles':'4H candles');
  if(st.RGCT!=='candles')return 'Line';
  return st.RGGRAN==='4h'?'4H candles':'Candles \u00b7 '+sizeLabel(st.RGGRAN);
}
function clickHidden(sel){
  if(!dlg)return false;
  var b=dlg.querySelector(sel);
  if(!b)return false;
  b.click();
  return true;
}
function pickType(kind){
  /* Drives the hidden buttons, so picking behaves exactly like tapping them. */
  var st=API.state();
  if(kind==='line'){
    if(st.rng==='1D')clickHidden('#bcCt button[data-ct="line"]');
    else clickHidden('#bcCg button[data-cg="line"]');
  }else{
    if(st.rng==='1D')clickHidden('#bcCt button[data-ct="'+S.last1DSize+'"]');
    else clickHidden('#bcCg button[data-cg="candles"]');
  }
}
function pickSize(sz){
  var st=API.state();
  if(st.rng==='1D'){
    S.last1DSize=sz;saveS();
    clickHidden('#bcCt button[data-ct="'+sz+'"]');
  }else{
    clickHidden('#bcCg button[data-cg="candles"]');
    clickHidden('#bcCg button[data-cggran="'+sz+'"]');
  }
}
function buildMenu(){
  if(menuEl)return menuEl;
  var m=document.createElement('div');
  m.className='ta-menu';m.setAttribute('role','menu');m.setAttribute('aria-label','Chart type');
  m.hidden=true;
  floatParent().appendChild(m);
  menuEl=m;
  return m;
}
function openMenu(){
  if(isPriceMode())return;
  var st=API.state();
  var m=buildMenu();
  var sizes=allowedSizes(st.rng);
  var isCandles=st.rng==='1D'?st.CT!=='line':st.RGCT==='candles';
  var curSize=st.rng==='1D'?st.CT:st.RGGRAN;
  var h='<div class="ta-mh">Type</div>';
  h+='<button type="button" role="menuitem" class="ta-mo'+(!isCandles?' on':'')+'" data-ta-pick="line">Line<span class="ta-ck">\u2713</span></button>';
  h+='<button type="button" role="menuitem" class="ta-mo'+(isCandles?' on':'')+'" data-ta-pick="candles">Candles<span class="ta-ck">\u2713</span></button>';
  if(sizes.length){
    h+='<div class="ta-md"></div><div class="ta-mh">Size</div>';
    sizes.forEach(function(sz){
      h+='<button type="button" role="menuitem" class="ta-mo'+(isCandles&&curSize===sz?' on':'')+'" data-ta-size="'+sz+'">'+sizeLabel(sz)+'<span class="ta-ck">\u2713</span></button>';
    });
  }
  m.innerHTML=h;
  m.hidden=false;menuOpen=true;
  typBtn.classList.add('open');typBtn.setAttribute('aria-expanded','true');
  placeFloat(typBtn,m);
  var first=m.querySelector('.ta-mo.on')||m.querySelector('.ta-mo');
  if(first)first.focus();
}
function closeMenu(focusTyp){
  if(!menuOpen)return;
  menuOpen=false;
  if(menuEl)menuEl.hidden=true;
  if(typBtn){typBtn.classList.remove('open');typBtn.setAttribute('aria-expanded','false');}
  if(focusTyp&&typBtn)typBtn.focus();
}

/* ---------- floating TA panel ---------- */
function swRow(key,label,sub,col){
  return '<div class="ta-it"><div class="nm"><span><i style="background:'+col+'"></i>'+label+'</span><small>'+sub+'</small></div>'
    +'<button type="button" class="ta-sw'+(S[key]?' on':'')+'" role="switch" aria-checked="'+(!!S[key])+'" data-ta-key="'+key+'" aria-label="'+label+'"></button></div>';
}
function buildPanel(){
  if(panelEl)return panelEl;
  var p=document.createElement('div');
  p.className='ta-panel';p.setAttribute('role','dialog');p.setAttribute('aria-label','Technical analysis');
  p.hidden=true;
  floatParent().appendChild(p);
  panelEl=p;
  return p;
}
function renderPanel(){
  var p=buildPanel();
  /* The six MA chips are the legend: each carries its MA's colour dot +
     label; enabled chips are highlighted in their colour. */
  var chips=MA_KEYS.map(function(k){return '<button type="button" class="ta-ma-chip'+(S.maSet&&S.maSet[k]?' on':'')+'" data-ta-ma="'+k+'" style="--mac:'+maCol(k)+'" aria-pressed="'+(!!(S.maSet&&S.maSet[k]))+'"><i></i>'+MA_LBL[k]+'</button>';}).join('');
  p.innerHTML='<div class="ta-ph"><span class="ta-ph-t"><b>Technical analysis</b><span class="ta-beta">Beta</span></span><button type="button" data-ta-clear>Clear all</button></div>'
    +'<div class="ta-cmp" hidden>'+CMP_NOTE_TEXT+'</div>'
    +swRow('tl','Smart Trendlines','auto support / resistance',COL.tl)
    +'<div class="ta-tl-status" hidden></div>'
    +swRow('bb','Bollinger Bands','20 \u00b7 2\u03c3',COL.bb)
    +swRow('ma','Moving averages','stack as many as you like',COL.ma)
    +'<div class="ta-ma'+(S.ma?'':' off')+'">'+chips+'</div>'
    +swRow('rsi','RSI','14 \u00b7 strip under chart',COL.rsi);
  syncPanel();syncCmpNote();
}
/* Targeted sync (no innerHTML replacement): re-rendering the panel would
   detach the very button being clicked, and the document outside-click
   handler would then read it as an outside click and close the panel. */
function syncPanel(){
  if(!panelEl)return;
  var sws=panelEl.querySelectorAll('[data-ta-key]');
  for(var i=0;i<sws.length;i++){var k=sws[i].getAttribute('data-ta-key');sws[i].classList.toggle('on',!!S[k]);sws[i].setAttribute('aria-checked',S[k]?'true':'false');}
  var ma=panelEl.querySelector('.ta-ma');
  if(ma)ma.classList.toggle('off',!S.ma);
  var chips=panelEl.querySelectorAll('[data-ta-ma]');
  /* Job 5: a chip shows on only when its MA is actually drawing — that
     needs the group on AND the chip selected. Before, the chips read
     S.maSet alone, so master-off / Clear all left them looking selected
     while nothing drew. The set itself is preserved across a master
     toggle (turning the group back on restores it); Clear all empties it. */
  for(var j=0;j<chips.length;j++){var k=chips[j].getAttribute('data-ta-ma');var on=!!(S.ma&&S.maSet&&S.maSet[k]);chips[j].classList.toggle('on',on);chips[j].setAttribute('aria-pressed',on?'true':'false');}
  syncTlStatus();
  syncGating();
}
/* ---------- Drawing fixes Stage 1: per-view toggle gating ----------
   A gated toggle renders disabled (greyed out, still visible) with its
   row label dimmed; the same toggle works normally on other views. Runs
   on every panel sync and every draw, so a view change while the panel
   is open re-gates at once. Disabled buttons fire no click events, so
   the delegated handler below never sees a gated toggle — the guards in
   setToggle and the chip handler are belt-and-braces for programmatic
   calls. */
function syncGating(){
  /* No hidden check: renderPanel syncs before the panel is shown, so the
     toggles are already gated when it appears; afterDraw re-gates while
     it is open. The writes are idempotent when nothing changed.
     Revision pass (27 Nov 2026): a comparison on greys the toggles too
     (visible but disabled, back on when comparison goes off) — nothing
     disappears. Must-fix (27 Nov 2026): RSI is exempt — its strip keeps
     drawing on a comparison, so its switch stays usable (the revision
     pass greyed it with the rest, and RSI never showed while comparing). */
  if(!panelEl)return;
  var st=viewState();
  var cmp=isCmp();
  var sws=panelEl.querySelectorAll('[data-ta-key]');
  for(var i=0;i<sws.length;i++){
    var k=sws[i].getAttribute('data-ta-key');
    var g=(k==='rsi')?taGated(k,st):(taGated(k,st)||cmp);
    sws[i].disabled=g;
    sws[i].title=g?(cmp?'Not available while comparing':'Not available on this view'):'';
    var row=sws[i].closest?sws[i].closest('.ta-it'):null;
    if(row)row.classList.toggle('gated',g);
  }
  var chips=panelEl.querySelectorAll('[data-ta-ma]');
  for(var j=0;j<chips.length;j++){
    var mk=chips[j].getAttribute('data-ta-ma');
    var gm=taMaGated(mk,st)||cmp;
    chips[j].disabled=gm;
    chips[j].title=gm?(cmp?'Not available while comparing':'Not available on this view'):'';
  }
}
function openPanel(){
  if(isPriceMode())return;
  renderPanel();
  panelEl.hidden=false;panelOpen=true;
  taBtn.classList.add('open');taBtn.setAttribute('aria-expanded','true');
  placeFloat(taBtn,panelEl);
  var first=panelEl.querySelector('.ta-sw');
  if(first)first.focus();
}
function closePanel(focusPill){
  if(!panelOpen)return;
  panelOpen=false;
  if(panelEl)panelEl.hidden=true;
  if(taBtn){taBtn.classList.remove('open');taBtn.setAttribute('aria-expanded','false');}
  if(focusPill&&taBtn)taBtn.focus();
}
function setToggle(key,val){
  /* Stage 1 gating: a gated overlay cannot turn on for this view.
     Turning it off is always allowed (and Clear all bypasses this). */
  if(val&&taGated(key,viewState()))return;
  S[key]=!!val;
  /* Job 5: no auto-selected MA. Turning the group on used to pre-select
     SMA 50, so a user batch-clicking the chips then toggled SMA 50 OFF
     (it was already on) and ended with it unselected. The set is now
     exactly what the user picked; an empty set draws nothing. */
  saveS();
  syncPanel();
  syncPill();syncRsi();
  /* Stage 2: toggling an overlay redraws the chart so it appears at once. */
  if(API.draw)API.draw();
}

/* ---------- overlap check (Playwright / handback) ---------- */
function rect(el){
  if(!el)return null;
  var r=el.getBoundingClientRect();
  if(!r.width||!r.height)return null;
  return {x:r.left,y:r.top,w:r.width,h:r.height,r:r.right,b:r.bottom};
}
function union(a,b){
  if(!a)return b;if(!b)return a;
  var x=Math.min(a.x,b.x),y=Math.min(a.y,b.y),r=Math.max(a.r,b.r),bb=Math.max(a.b,b.b);
  return {x:x,y:y,w:r-x,h:bb-y,r:r,b:bb};
}
function visible(el){
  if(!el)return false;
  var r=el.getBoundingClientRect();
  if(!r.width||!r.height)return false;
  var pn=panelEl,mn=menuEl,pd=pn&&pn.style.display,md=mn&&mn.style.display;
  if(pn)pn.style.display='none';if(mn)mn.style.display='none';
  var pts=[[.5,.5],[.15,.5],[.85,.5]],hit=false;
  pts.forEach(function(q){
    var x=r.left+r.width*q[0],y=r.top+r.height*q[1];
    if(x<0||y<0||x>innerWidth||y>innerHeight)return;
    var h=document.elementFromPoint(x,y);
    if(h&&(h===el||el.contains(h)))hit=true;
  });
  if(pn)pn.style.display=pd||'';if(mn)mn.style.display=md||'';
  return hit;
}
function overlap(a,b){
  if(!a||!b)return false;
  return a.x<b.r&&b.x<a.r&&a.y<b.b&&b.y<a.b;
}
window.__taRects=function(){
  var pnEl=(panelEl&&!panelEl.hidden)?panelEl:null;
  var panelVisible=false;
  if(pnEl){var q=pnEl.getBoundingClientRect(),h=document.elementFromPoint(q.left+q.width/2,q.top+q.height/2);panelVisible=!!(h&&pnEl.contains(h));}
  var mnEl=(menuEl&&!menuEl.hidden)?menuEl:null;
  var menuVisible=false;
  if(mnEl){var q2=mnEl.getBoundingClientRect(),h2=document.elementFromPoint(q2.left+q2.width/2,q2.top+q2.height/2);menuVisible=!!(h2&&mnEl.contains(h2));}
  var prot={
    'BTC price':union(rect(el('price')),rect($('.v4-chg')))||rect(dlg?dlg.querySelector('.bc-px'):null),
    'Keep screen on':rect(el('wakeBtn')),
    'Exit full screen':rect($('.v4-fs-exit')),
    'Light/Dark pill':rect(el('psThemePill')),
    'Full-screen buttons':rect($('.v4-fs')),
    'Price clock':rect($('.v4-fs-toprice')),
    'Switch to chart':rect($('.v4-fs-tochart')),
    'Theme dot':rect(el('themeDot')),
    'Price pill':rect(el('pxPill')),
    'Close':rect(dlg?dlg.querySelector('.bc-x'):null)
  };
  var vis={};
  Object.keys(prot).forEach(function(k){
    var sel={'BTC price':el('price')||(dlg&&dlg.querySelector('.bc-px')),'Keep screen on':el('wakeBtn'),'Exit full screen':$('.v4-fs-exit'),'Light/Dark pill':el('psThemePill'),'Full-screen buttons':$('.v4-fs'),'Price clock':$('.v4-fs-toprice'),'Switch to chart':$('.v4-fs-tochart'),'Theme dot':el('themeDot'),'Price pill':el('pxPill'),'Close':dlg&&dlg.querySelector('.bc-x')}[k];
    vis[k]=visible(sel);
  });
  var pn=rect(pnEl),mn=rect(mnEl),tp=rect(taBtn),rs=rect(rsiEl&&!rsiEl.hidden?rsiEl:null),bx=rect(dlg?dlg.querySelector('.bc-box'):null);
  var overlaps=[];
  [['panel',pn],['menu',mn]].forEach(function(pair){
    if(!pair[1])return;
    Object.keys(prot).forEach(function(k){if(overlap(pair[1],prot[k]))overlaps.push(pair[0]+' x '+k);});
  });
  return {stage:rect(el('hero'))||rect(dlg),panelVisible:panelVisible,menuVisible:menuVisible,vw:innerWidth,vh:innerHeight,
    panel:pn,menu:mn,pill:tp,rsi:rs,box:bx,prot:prot,vis:vis,overlaps:overlaps,
    lane:rect(dlg?dlg.querySelector('.bc-row2'):null),scrollY:scrollY};
};

/* ---------- init ---------- */
function init(api){
  if(inited)return;
  if(!api)return;
  dlg=api.dlg();
  if(!dlg)return;
  inited=true;
  typBtn=dlg.querySelector('#taTyp');
  taBtn=dlg.querySelector('#taPill');
  rsiEl=dlg.querySelector('#taRsi');
  if(!typBtn||!taBtn)return;
  /* Type pill: opens the menu. The panel keeps the label in sync on draw. */
  typBtn.addEventListener('click',function(e){
    e.stopPropagation();
    if(menuOpen)closeMenu(false);else{closePanel(false);openMenu();}
  });
  taBtn.addEventListener('click',function(e){
    e.stopPropagation();
    if(panelOpen)closePanel(false);else{closeMenu(false);openPanel();}
  });
  /* Menu picks drive the hidden buttons. */
  document.addEventListener('click',function(e){
    if(!menuOpen)return;
    if(menuEl&&menuEl.contains(e.target))return;
    if(typBtn&&typBtn.contains(e.target))return;
    closeMenu(false);
  });
  document.addEventListener('click',function(e){
    if(!panelOpen)return;
    if(panelEl&&panelEl.contains(e.target))return;
    if(taBtn&&taBtn.contains(e.target))return;
    closePanel(false);
  });
  document.addEventListener('keydown',function(e){
    if(e.key!=='Escape')return;
    if(menuOpen){e.preventDefault();closeMenu(true);}
    else if(panelOpen){e.preventDefault();closePanel(true);}
  });
  /* Escape in the popover closes the TA panel/menu first (and stops the
     keypress reaching the dialog's own Escape handler, which would close
     the whole dialog). A second Escape then closes the dialog as before. */
  dlg.addEventListener('keydown',function(e){
    if(e.key!=='Escape')return;
    if(menuOpen||panelOpen){e.preventDefault();e.stopPropagation();if(menuOpen)closeMenu(true);else closePanel(true);}
  });
  if(menuEl===null)buildMenu();
  if(panelEl===null)buildPanel();
  /* Delegated clicks inside the floating layers. */
  floatParent().addEventListener('click',function(e){
    var b=e.target.closest('[data-ta-pick]');
    if(b){var k=b.getAttribute('data-ta-pick');closeMenu(false);pickType(k);return;}
    var sz=e.target.closest('[data-ta-size]');
    if(sz){closeMenu(false);pickSize(sz.getAttribute('data-ta-size'));return;}
    var sw=e.target.closest('[data-ta-key]');
    if(sw){setToggle(sw.getAttribute('data-ta-key'),!S[sw.getAttribute('data-ta-key')]);return;}
    var mc=e.target.closest('[data-ta-ma]');
    if(mc){
      var mk=mc.getAttribute('data-ta-ma');
      /* Stage 1 gating: a gated chip cannot turn on for this view. */
      if(taMaGated(mk,viewState())&&!(S.maSet&&S.maSet[mk]))return;
      if(!S.maSet||typeof S.maSet!=='object')S.maSet={};
      /* Job 5: clicking a chip while the group is off selects it and
         turns the group on. (Before, the click toggled membership in the
         preserved set, so a chip that looked off could silently lose its
         selection and take a second click to come back.) With the group
         on, a click toggles the chip as before. */
      if(!S.ma){S.maSet[mk]=true;S.ma=true;}
      else{if(S.maSet[mk])delete S.maSet[mk];else S.maSet[mk]=true;}
      /* Enabling a chip turns the group on; disabling the last one turns
         it off, so the row switch always matches the set. */
      if(!maCount())S.ma=false;
      saveS();syncPanel();syncPill();syncRsi();
      if(API.draw)API.draw();
      return;
    }
    if(e.target.closest('[data-ta-clear]')){
      /* Job 5: Clear all empties the MA set too. Before, it left maSet
         populated, so the chips still showed on after everything was
         turned off. */
      S.tl=false;S.bb=false;S.ma=false;S.rsi=false;S.maSet={};saveS();syncPanel();syncPill();syncRsi();
      if(API.draw)API.draw();
      return;
    }
  });
  /* RSI strip collapse toggle. */
  if(rsiEl){
    var t=rsiEl.querySelector('.ta-rsi-t');
    if(t)t.addEventListener('click',function(){
      S.rsiCol=!S.rsiCol;saveS();syncRsi();
    });
  }
  /* Stage 2: after every native draw, draw the enabled overlays on #bcC
     (after the price series, same x/y mapping) and the RSI strip; keep the
     comparison note in sync. Live ticks recompute via the normal redraw —
     no refetch, no flicker. When nothing is on, draw nothing; when a
     comparison is on, only the RSI strip draws (the plot overlays hide).
     Must-fix (27 Nov 2026): the RSI strip is a separate pane below the
     chart, computed from the BTC closes alone — it keeps drawing on a
     comparison, where the old early return left it blank. */
  api.afterDraw=function(kind){
    if(menuOpen)closeMenu(false);
    syncRsi();syncCmpNote();syncTlStatus();syncGating();syncPill();syncCmpNoteOut();
    if(!nOn())return;
    if(isCmp()){
      if(S.rsi&&!taGated('rsi',viewState())){
        try{
          var _g=API.geom?API.geom():null;
          if(_g&&_g.xs&&_g.closes&&_g.n>=2){
            var _warm=warmFor(_g);
            var _vals=computeVals(_g,_warm);
            drawRsiStrip(_g,_vals);
          }
        }catch(e){}
      }
      syncPill();
      return;
    }
    var g=null;
    try{g=API.geom?API.geom():null;}catch(e){}
    if(!g||!g.xs||!g.closes||g.n<2)return;
    var t0=0;
    try{t0=window.performance?performance.now():0;}catch(e){}
    try{
      var warm=warmFor(g);
      var vals=computeVals(g,warm);
      drawOverlays(g,vals);
      if(S.rsi&&!taGated('rsi',viewState()))drawRsiStrip(g,vals);
      if(S.tl)tlDrawLines(g);
    }catch(e){}
    syncPill(); /* Job 6: re-sync after the draw — tlLast is fresh now, so the badge counts the lines actually drawn on this view. */
    try{
      if(t0){
        var dt=performance.now()-t0;
        var p=window.__TA_PERF||(window.__TA_PERF={last:0,sum:0,n:0,avg:0});
        p.last=dt;p.sum+=dt;p.n++;p.avg=p.sum/p.n;
      }
    }catch(e2){}
  };
  api.taTip=taTipLines;
  /* Stage 2 debug probe (tests / handback): the current geometry, the
     warm-up + visible closes actually used, the first valid index and last
     value of each indicator, and the perf probe. Per-MA dicts (mas) carry
     every enabled moving average; firstValid.ma is the first index where
     ALL enabled MAs are valid, and last.ma is the first enabled MA's last
     value (canonical order) — prefer last.mas[key] for a specific MA. */
  window.__TA_DEBUG=function(){
    try{
      var g=API.geom?API.geom():null;
      if(!g)return null;
      var warm=warmFor(g);
      var vals=computeVals(g,warm);
      var first=function(a){if(!a)return null;for(var i=0;i<a.length;i++)if(a[i]!=null)return i;return null;};
      var last=function(a){if(!a)return null;for(var i=a.length-1;i>=0;i--)if(a[i]!=null)return a[i];return null;};
      var mas=maOn();
      var firstMas={},lastMas={};
      mas.forEach(function(k){firstMas[k]=vals.mas&&vals.mas[k]?first(vals.mas[k]):null;lastMas[k]=vals.mas&&vals.mas[k]?last(vals.mas[k]):null;});
      var firstMa=null,lastMa=null;
      if(mas.length){
        var mx=-1;mas.forEach(function(k){if(firstMas[k]==null)mx=Infinity;else if(firstMas[k]>mx)mx=firstMas[k];});
        firstMa=isFinite(mx)?mx:null;lastMa=lastMas[mas[0]];
      }
      return {kind:g.kind,n:g.n,warm:warm.length,closes:g.closes,warmCloses:warm,
        firstValid:{ma:firstMa,bb:vals.bbUp?first(vals.bbUp):null,rsi:vals.rsi?first(vals.rsi):null},
        firstValidMas:firstMas,
        last:{ma:lastMa,mas:lastMas,bbUp:vals.bbUp?last(vals.bbUp):null,bbLo:vals.bbLo?last(vals.bbLo):null,bbMid:vals.bbMid?last(vals.bbMid):null,rsi:vals.rsi?last(vals.rsi):null},
        perf:window.__TA_PERF||null};
    }catch(e){return null;}
  };
  syncPill();syncRsi();
  buildCmpNoteOut();syncCmpNoteOut(); /* Job 6: the comparison note outside the panel. */
  if(api.syncTypePill)api.syncTypePill();
  preWarm(); /* Job 2: fetch the intraday indicator history now, so it is cached before the user turns an overlay on. */
}
/* Stage 4 debug probe (tests / handback): the trendline file status, the
   chart's timeframe, the live close, and the lines the drawer computed
   (drawn + omitted with reasons) with their labels. */
window.__TA_TL_DEBUG=function(){
  try{
    var g=API.geom?API.geom():null;
    var st=null;try{st=API.state();}catch(e){}
    return {tlOn:!!S.tl,cmp:isCmp(),tf:tlChartTf(st),status:tlStatus,
      fileOk:tlCache.ok,fileReason:tlCache.reason,
      fetchedAt:tlCache.fetchedAt,
      liveClose:g&&g.closes?g.closes[g.n-1]:null,
      lastMs:g&&g.times?g.times[g.n-1]:null,
      last:tlLast};
  }catch(e){return null;}
};

window.__BTTA={init:init,typeLabel:typeLabel,tlExpandRange:tlExpandRange,ovExpandRange:ovExpandRange};
if(API&&API.dlg)init(API);
})();
