/* Live BTC pill (header + phone menu panel) and the BTC chart popover/bottom sheet.
   Data: assets/data/btc-daily.json (2010-08-18..2014-09-16 blockchain.info, then Yahoo BTC-USD UTC-day closes),
   extended with newer BTC closes from the data branch history.json and Coinbase daily candles (weekends included),
   plus the live price from the same feed as the header pill (CoinGecko, Coinbase fallback).
   1D only: true intraday chart from Coinbase 15-minute candles (last 24h, ET), CoinGecko fallback, daily fallback. */
(function(){
var SRC=(document.currentScript&&document.currentScript.src)||location.href;
var U=function(p){return new URL(p,SRC).href;};
var RAW='https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/history.json';
var $=function(i){return document.getElementById(i);};
var pill=$('hdrTick'),menu=$('mnavMenu');if(!pill)return;
var live={usd:null,chg:null};
var fmt=function(n){return n.toLocaleString('en-US',{style:'currency',currency:'USD',maximumFractionDigits:n<1?2:0});};
/* pill markup */
function decorate(el,full){if(el.querySelector('.lp-cv'))return;
  el.insertAdjacentHTML('afterbegin','<span class="lp-lab"><span class="lp-dot" aria-hidden="true"></span>Live BTC</span>');
  el.insertAdjacentHTML('beforeend','<span class="lp-cv" aria-hidden="true">▾</span>');}
decorate(pill);
pill.setAttribute('aria-haspopup','dialog');pill.setAttribute('aria-expanded','false');
if(!pill.getAttribute('aria-label'))pill.setAttribute('aria-label','Live BTC price. Open BTC chart');
var mp=null;
/* phone menu panel has no price (the header pill is the only price) */
function chgTxt(c){return typeof c==='number'?(c>=0?'▲':'▼')+Math.abs(c).toFixed(1)+'%':'';}
function paint(){if(live.usd==null)return;var cls='hdr-chg '+(live.chg>=0?'up':'down');
  var hp=$('hdrPx'),hc=$('hdrChg');if(hp){hp.textContent=fmt(live.usd);}if(hc&&typeof live.chg==='number'){hc.textContent=chgTxt(live.chg);hc.className=cls;}
  if(mp){mp.querySelector('.mpPx').textContent=fmt(live.usd);var m=mp.querySelector('.mpChg');m.textContent=chgTxt(live.chg);m.className=cls+' mpChg';}
  if(dlg&&!dlg.hidden)head();}
window.addEventListener('btcprice',function(e){live.usd=e.detail.usd;live.chg=e.detail.chg;paint();if(dlg&&!dlg.hidden&&ch)draw();});
/* pages without the homepage price widget fetch the same feed themselves */
if(!$('btcLive')){
  var tf=function(u){return fetch(u,{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();});};
  var load=function(){tf('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true').then(function(d){var b=d.bitcoin;if(!b||typeof b.usd!=='number')throw 0;return {usd:b.usd,chg:b.usd_24h_change};})
    .catch(function(){return tf('https://api.coinbase.com/v2/prices/BTC-USD/spot').then(function(d){var a=parseFloat(d.data.amount);if(!(a>0))throw 0;return {usd:a,chg:null};});})
    .then(function(b){live.usd=b.usd;live.chg=b.chg;paint();if(dlg&&!dlg.hidden&&ch)draw();setTimeout(load,60000);},function(){setTimeout(load,90000);});};
  load();}
/* data */
var DATA=null,PROV=false,dataP=null,SPX=null,SPXK=[],SHOWSPX=false,GOLD=null,GOLDK=[],SHOWGLD=false,MSTR=null,MSTRK=[],SHOWMSTR=false,CBDAILY=null;
/* Test branch 26 Oct 2026: 1D chart type Line | 1H | 4H, default Line. Only shown when 1D is selected. */
var CT='line';
/* Intraday 1D (deployed 26 Oct 2026, Part 1): Coinbase 15-min candles, last 24h.
   Fallback chain: Coinbase 15-min -> CoinGecko 1-day market chart -> daily closes (in draw1D).
   S&P 500 / Gold toggles are off for 1D only; SHOWSPX/SHOWGLD are preserved for other ranges. */
var INTRA=null,INTRA_AT=0,intraP=null;
function etTime(ms){try{return new Date(ms).toLocaleString('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit',hour12:true});}catch(e){return new Date(ms).toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'});}}
function etDateTime(ms){try{return new Date(ms).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',hour12:true});}catch(e){return new Date(ms).toLocaleString('en-US');}}
function getIntraday(){
  if(intraP)return intraP;
  var now=Date.now();
  if(INTRA&&now-INTRA_AT<60000)return Promise.resolve(INTRA);
  var end=new Date(now).toISOString(),start=new Date(now-24*3600*1000).toISOString();
  var cb=fetch('https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=900&start='+start+'&end='+end,{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(function(j){
    if(!Array.isArray(j))throw new Error('bad candles');
    var pts=j.map(function(c){return {t:c[0]*1000,o:c[3],h:c[2],l:c[1],v:c[4]};}).filter(function(p){return isFinite(p.v)&&p.v>0&&p.t>now-24*3600*1000;}).sort(function(a,b){return a.t-b.t;});
    if(pts.length<2)throw new Error('too few candles');
    return {pts:pts.slice(-96),src:'coinbase'};
  });
  var cg=cb.catch(function(){return fetch('https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=1',{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(function(j){
    if(!j||!Array.isArray(j.prices))throw new Error('bad market chart');
    var pts=j.prices.map(function(pr){return {t:pr[0],v:pr[1]};}).filter(function(p){return isFinite(p.v)&&p.v>0;}).sort(function(a,b){return a.t-b.t;});
    if(pts.length<2)throw new Error('too few prices');
    return {pts:pts,src:'coingecko'};
  });});
  intraP=cg.then(function(d){INTRA=d;INTRA_AT=Date.now();intraP=null;return d;},function(e){intraP=null;INTRA=null;throw e;});
  return intraP;
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
/* Candle ranges, Day 1 (test branch only, NOT live): 1W daily candles + 1M weekly/daily choice.
   RGCT is the chart type for 1W/1M only (default Line, so the existing line view is unchanged
   unless the visitor opts into candles). RGGRAN is the candle size for the range view.
   CANDRANGE marks that the shared candle canvas + pill are currently showing range candles,
   so the shared listeners and pill dismiss redraw the range view, not the 1D view. */
var CANDRANGE=false,CANDGRAN='daily',RGCAND=null,RGLBL='';
var RGCT='line',RGGRAN='daily';
/* Candle ranges, Day 3 (exploration only, NOT a decided build): SMA 20 /
   EMA 20 / Bollinger (20, 2σ) overlays on range candles, ported from the
   playground prototype. All three are OFF by default, visible only in
   candle view, and calculated on the DISPLAYED candle closes only — so
   "20" means 20 candles of whatever size is shown (a weekly chart's
   SMA 20 is a 20-week SMA, not a 20-day SMA). Buttons say so plainly.
   The first 19 candles have no overlay value: nothing is padded or
   invented for them. 1D intraday is untouched. */
var OV={sma:false,ema:false,bb:false};
/* Candle ranges, Day 2: 3M/6M/YTD/1Y join 1W/1M. Granularity choices:
   1W daily only; 1M weekly|daily (default weekly); 3M/6M/YTD/1Y monthly|weekly
   (default monthly, the first-listed choice in the confirmed spec). */
var CANDLE_RANGES=['1W','1M','3M','6M','YTD','1Y'];
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
   Tapping the pill itself also dismisses it, so the ✕ is a small circle inside the pill, not a corner button. */
function candInfoEl(){
  var el=$('bcSel');if(el)return el;
  var box=$('bcC')&&$('bcC').parentNode;if(!box)return null;
  el=document.createElement('div');el.id='bcSel';
  el.style.cssText='display:none;position:absolute;z-index:5;width:280px;max-width:calc(100% - 24px);background:linear-gradient(180deg,#0e1730,#0a1122);border:1px solid rgba(34,211,238,.30);border-radius:999px;padding:16px 24px;color:#e8eef7;font:13px/1.5 Inter, sans-serif;text-align:center;box-shadow:0 20px 50px rgba(0,0,0,.6);pointer-events:auto;cursor:pointer;';
  box.style.position='relative';box.appendChild(el);
  el.addEventListener('click',function(ev){ev.stopPropagation();dismissCandInfo();});
  return el;
}
function showCandInfo(i,geomX,geomTop){
  var el=candInfoEl();if(!el)return;
  if(!CAND||i<0||i>=CAND.length){el.style.display='none';return;}
  var k=CAND[i],dur=CANDPER===4?3600000:14400000,chg=k.c-k.o,pct=k.o?(chg/k.o*100):0;
  var col=k.c>=k.o?'#22c55e':'#ef4444';
  el.innerHTML='';
  /* pill content, centred, three short lines — no table rows, no arrow, no bottom line:
     line 1: when (small grey) · line 2: High / Low · line 3: Change in green/red.
     Small ✕ sits inside the pill at the top-right; tapping the pill itself also closes it. */
  var cl=document.createElement('button');cl.type='button';cl.textContent='✕';cl.setAttribute('aria-label','Close candle details');
  cl.style.cssText='position:absolute;top:10px;right:16px;background:none;border:none;color:#9aa6bc;font-size:14px;line-height:1;cursor:pointer;padding:8px;';
  cl.addEventListener('click',function(ev){ev.stopPropagation();dismissCandInfo();});
  el.appendChild(cl);
  var tm=document.createElement('div');tm.style.cssText='color:#9aa6bc;font-size:12px;';
  /* Fix 29 Oct 2026 (browser test, Day 2): range candles are UTC days /
     weeks / months, so their labels must be UTC too. ET formatting shifted
     every UTC-midnight timestamp back a day — and a month-boundary candle
     back a whole month — so the October monthly candle (t = Oct 1 00:00
     UTC) read "September 2026" in its pill and "Sep 30" on the axis, and
     looked like no October candle existed. The bucket was never dropped;
     it was mislabelled. 1D intraday pills below keep ET, which is right
     for intraday times. */
  if(CANDRANGE){if(CANDGRAN==='monthly'){tm.textContent='Monthly candle · '+new Date(k.t).toLocaleDateString('en-US',{timeZone:'UTC',month:'long',year:'numeric'})+' UTC';}else{var sd=new Date(k.t).toLocaleDateString('en-US',{timeZone:'UTC',month:'short',day:'numeric'}),ed=new Date(k.end).toLocaleDateString('en-US',{timeZone:'UTC',month:'short',day:'numeric'});tm.textContent=(CANDGRAN==='weekly'?'Weekly':'Daily')+' candle · '+sd+(ed!==sd?' – '+ed:'')+' UTC';}}
  else tm.textContent=(CANDPER===4?'1-hour':'4-hour')+' · '+etDateTime(k.t)+' – '+etTime(k.t+dur)+' ET';
  el.appendChild(tm);
  var hl=document.createElement('div');hl.style.cssText='font-size:14px;font-weight:600;color:#e8eef7;font-variant-numeric:tabular-nums;margin:2px 0;';hl.textContent='High '+fmt(k.h)+'  ·  Low '+fmt(k.l);el.appendChild(hl);
  var ch=document.createElement('div');ch.style.cssText='font-size:14px;font-weight:600;color:'+col+';font-variant-numeric:tabular-nums;';ch.textContent=(chg>=0?'▲ +$':'▼ -$')+Math.abs(chg).toLocaleString('en-US',{maximumFractionDigits:0})+' ('+(pct>=0?'+':'')+pct.toFixed(2)+'%)';el.appendChild(ch);
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
  var L=62,R=12,T=18,B=44,iw=W-L-R,ih=H-T-B;
  var X=function(i){return L+iw*(candles.length===1?0.5:i/(candles.length-1));};
  var Y=function(v){return T+ih*(1-(v-lo)/(hi-lo));};
  ctx.strokeStyle='rgba(255,255,255,.08)';ctx.fillStyle='#9aa6bc';ctx.font='11px Inter, sans-serif';ctx.textAlign='right';
  [0,0.33,0.66,1].forEach(function(f){var v=lo+(hi-lo)*f,y=Y(v);ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(W-R,y);ctx.stroke();ctx.fillText('$'+Math.round(v).toLocaleString('en-US'),L-6,y+4);});
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
      var _prevX=drawCandles1D._lastTx;if(_prevX==null||x-_prevX>=62){ctx.fillText(etTime(k.t),x,H-8);drawCandles1D._lastTx=x;}
    }
    var prev=candles[i-1],dayChange=!prev||new Date(prev.t).toLocaleDateString('en-US',{timeZone:'America/New_York'})!==new Date(k.t).toLocaleDateString('en-US',{timeZone:'America/New_York'});
    if(dayChange){
      var dx=Math.max(L+30,Math.min(W-R-30,x));
      ctx.fillStyle='#64748b';ctx.fillText(new Date(k.t).toLocaleDateString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric'}),dx,H-24);
      ctx.fillStyle='#9aa6bc';
    }
  });
  /* selected / hovered candle: white outline + glow + vertical guide, drawn last so it sits on top */
  [CANDHOV,CANDSEL].forEach(function(idx,layer){
    if(idx<0||idx>=candles.length)return;var g=CANDGEOM[idx],k=candles[idx],col=k.c>=k.o?'#22c55e':'#ef4444';
    if(layer===0){ctx.strokeStyle='rgba(255,255,255,.25)';ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(g.x,T);ctx.lineTo(g.x,H-B);ctx.stroke();ctx.setLineDash([]);}
    else{ctx.save();ctx.shadowColor=col;ctx.shadowBlur=12;ctx.strokeStyle='#ffffff';ctx.lineWidth=1.5;ctx.strokeRect(g.x-g.bw/2-2,g.top-2,g.bw+4,Math.max(4,g.bot-g.top)+4);ctx.restore();}
  });
  ctx.fillStyle='#9aa6bc';ctx.textAlign='left';ctx.fillText(label, L, 12);
  /* interaction listeners, attached once (shared with the range candle view) */
  bindCandListeners(c);
  return true;
}
function bindCandListeners(c){
  if(c._candBound)return;
  c._candBound=true;
  var pick=function(evt){var r=c.getBoundingClientRect(),x=(evt.clientX-r.left);var best=-1,bd=1e9;CANDGEOM.forEach(function(g,i){var d=Math.abs(g.x-x);if(d<bd){bd=d;best=i;}});return best;};
  /* Guard: in a line view this canvas is a Chart.js line chart, not candles.
     Without the guard, hover/click here used stale CANDGEOM and repainted
     old candles over the line chart. */
  c.addEventListener('mousemove',function(e){if(!candViewActive())return;var i=pick(e);if(i!==CANDHOV){CANDHOV=i;redrawCandles();}});
  c.addEventListener('mouseleave',function(){if(!candViewActive())return;CANDHOV=-1;redrawCandles();});
  c.addEventListener('click',function(e){if(!candViewActive())return;var i=pick(e);if(i===CANDSEL){dismissCandInfo();return;}CANDSEL=i;redrawCandles();var g=CANDSEL>=0?CANDGEOM[CANDSEL]:null;showCandInfo(CANDSEL,g?g.x:null,g?g.top:null);});
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
   are never padded or invented. Monthly aggregation (for 3M/6M/YTD/1Y) is
   the same shape with calendar-month buckets and is a later step, not here. */
function aggDailyCandles(daily,mode){
  if(!Array.isArray(daily)||!daily.length)return [];
  if(mode!=='weekly'&&mode!=='monthly')return daily.map(function(p){return {t:p.t,end:p.t,o:p.o,h:p.h,l:p.l,c:p.c};});
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
/* Candle ranges, Day 3 (exploration): overlay maths, pure functions so a
   headless harness can extract and check them without a DOM. Playground
   semantics preserved exactly: SMA = mean of the last 20 closes; EMA is
   seeded on the first close with k = 2/(20+1) and only returned from the
   20th candle on; Bollinger = SMA ± 2 × population standard deviation
   (divide by 20) of the same 20 closes. Indices before the 20th candle
   are null, never padded. */
function calcSMA(closes,n){
  n=n||20;var out=[];
  closes.forEach(function(v,i){
    if(i<n-1){out.push(null);return;}
    var s=0,j;for(j=i-n+1;j<=i;j++)s+=closes[j];
    out.push(s/n);
  });
  return out;
}
function calcEMA(closes,n){
  n=n||20;var k=2/(n+1),e=null,out=[];
  closes.forEach(function(v,i){
    if(i===0)e=v;else e=v*k+e*(1-k);
    out.push(i>=n-1?e:null);
  });
  return out;
}
function calcBollinger(closes,n,mult){
  n=n||20;mult=mult||2;
  var sma=calcSMA(closes,n),out=[];
  closes.forEach(function(v,i){
    if(i<n-1){out.push(null);return;}
    var m=sma[i],s=0,j;
    for(j=i-n+1;j<=i;j++)s+=(closes[j]-m)*(closes[j]-m);
    var sd=Math.sqrt(s/n);
    out.push({mid:m,upper:m+mult*sd,lower:m-mult*sd});
  });
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
function drawCandlesRange(){
  var candles=RGCAND;if(!candles||!candles.length)return false;
  CANDRANGE=true;CANDGRAN=RGGRAN;CAND=candles;CANDLBL=RGLBL;
  if(CANDSEL<0){var _b=$('bcSel');if(_b)_b.style.display='none';}
  var c=$('bcC'),ctx=c.getContext('2d'),W=c.parentNode.clientWidth||640,H=c.parentNode.clientHeight||300;
  var dpr=window.devicePixelRatio||1;c.width=W*dpr;c.height=H*dpr;c.style.width=W+'px';c.style.height=H+'px';ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,W,H);
  var lo=Math.min.apply(null,candles.map(function(k){return k.l;})), hi=Math.max.apply(null,candles.map(function(k){return k.h;}));
  /* Day 3 overlays: extend the price range to include overlay values so
     overlay lines are never clipped by the candle-only range. */
  var OVCL=candles.map(function(k){return k.c;});
  var OVSMA=OV.sma?calcSMA(OVCL,20):null;
  var OVEMA=OV.ema?calcEMA(OVCL,20):null;
  var OVBB=OV.bb?calcBollinger(OVCL,20,2):null;
  [OVSMA,OVEMA].forEach(function(arr){if(!arr)return;arr.forEach(function(v){if(v!=null){if(v<lo)lo=v;if(v>hi)hi=v;}});});
  if(OVBB)OVBB.forEach(function(b){if(!b)return;if(b.lower<lo)lo=b.lower;if(b.upper>hi)hi=b.upper;});
  var pad=(hi-lo)*0.08||1;lo-=pad;hi+=pad;
  var L=62,R=12,T=18,B=44,iw=W-L-R,ih=H-T-B;
  var X=function(i){return L+iw*(candles.length===1?0.5:i/(candles.length-1));};
  var Y=function(v){return T+ih*(1-(v-lo)/(hi-lo));};
  ctx.strokeStyle='rgba(255,255,255,.08)';ctx.fillStyle='#9aa6bc';ctx.font='11px Inter, sans-serif';ctx.textAlign='right';
  [0,0.33,0.66,1].forEach(function(f){var v=lo+(hi-lo)*f,y=Y(v);ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(W-R,y);ctx.stroke();ctx.fillText('$'+Math.round(v).toLocaleString('en-US'),L-6,y+4);});
  ctx.textAlign='center';CANDGEOM=[];
  var lastTx=null,labIdx=rangeLabelIndices(candles.length,iw);
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
       is in this row, so it is no longer skipped by its own x test. */
    if(labIdx.indexOf(i)>=0){
      var md=new Date(k.t).toLocaleDateString('en-US',{timeZone:'UTC',month:'short',day:'numeric'});
      var dx=Math.max(24,Math.min(W-24,x));
      if(lastTx==null||dx-lastTx>=56){ctx.fillStyle='#64748b';ctx.fillText(md,dx,H-24);ctx.fillStyle='#9aa6bc';lastTx=dx;}
    }
  });
  /* Day 3 overlays, drawn after the candles and before the selection
     outline, so the outline stays on top. Lines skip nulls (the first 19
     candles) by starting a new path segment at the first real value.
     Bollinger is a filled band plus upper/lower lines plus a faint mid. */
  var drawLine=function(arr,col){
    ctx.strokeStyle=col;ctx.lineWidth=1.6;ctx.beginPath();var started=false;
    arr.forEach(function(v,i){if(v==null)return;if(!started){ctx.moveTo(X(i),Y(v));started=true;}else ctx.lineTo(X(i),Y(v));});
    ctx.stroke();ctx.lineWidth=1;
  };
  if(OVBB){
    ctx.beginPath();var bs=false;
    OVBB.forEach(function(b,i){if(!b)return;if(!bs){ctx.moveTo(X(i),Y(b.upper));bs=true;}else ctx.lineTo(X(i),Y(b.upper));});
    for(var bi=OVBB.length-1;bi>=0;bi--){if(OVBB[bi])ctx.lineTo(X(bi),Y(OVBB[bi].lower));}
    ctx.closePath();ctx.fillStyle='rgba(248,113,113,0.10)';ctx.fill();
    drawLine(OVBB.map(function(b){return b?b.upper:null;}),'rgba(248,113,113,0.8)');
    drawLine(OVBB.map(function(b){return b?b.lower:null;}),'rgba(248,113,113,0.8)');
    drawLine(OVBB.map(function(b){return b?b.mid:null;}),'rgba(248,113,113,0.45)');
  }
  if(OVSMA)drawLine(OVSMA,'#facc15');
  if(OVEMA)drawLine(OVEMA,'#22d3ee');
  [CANDHOV,CANDSEL].forEach(function(idx,layer){
    if(idx<0||idx>=candles.length)return;var g=CANDGEOM[idx],k=candles[idx],col=k.c>=k.o?'#22c55e':'#ef4444';
    if(layer===0){ctx.strokeStyle='rgba(255,255,255,.25)';ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(g.x,T);ctx.lineTo(g.x,H-B);ctx.stroke();ctx.setLineDash([]);}
    else{ctx.save();ctx.shadowColor=col;ctx.shadowBlur=12;ctx.strokeStyle='#ffffff';ctx.lineWidth=1.5;ctx.strokeRect(g.x-g.bw/2-2,g.top-2,g.bw+4,Math.max(4,g.bot-g.top)+4);ctx.restore();}
  });
  ctx.fillStyle='#9aa6bc';ctx.textAlign='left';ctx.fillText(RGLBL+((OV.sma||OV.ema||OV.bb)?' · '+[OV.sma?'SMA 20':null,OV.ema?'EMA 20':null,OV.bb?'Bollinger':null].filter(function(s){return s;}).join(' · '):''), L, 12);
  bindCandListeners(c);
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
function syncCg(){
  var cg=$('bcCg');if(!cg)return;
  var candlesOn=CANDLE_RANGES.indexOf(rng)>=0&&RGCT==='candles';
  [].forEach.call(cg.querySelectorAll('[data-cg]'),function(b){b.classList.toggle('on',b.dataset.cg===RGCT);b.setAttribute('aria-pressed',b.dataset.cg===RGCT);});
  var granAllowed=rng==='1M'?['weekly','daily']:(rng==='3M'||rng==='6M'||rng==='YTD'||rng==='1Y')?['monthly','weekly']:[];
  var gl=$('bcCgGranLab');if(gl)gl.style.display=candlesOn&&granAllowed.length?'':'none';
  [].forEach.call(cg.querySelectorAll('[data-cggran]'),function(b){var show=candlesOn&&granAllowed.indexOf(b.dataset.cggran)>=0;b.style.display=show?'':'none';b.classList.toggle('on',b.dataset.cggran===RGGRAN);b.setAttribute('aria-pressed',b.dataset.cggran===RGGRAN);});
}
/* Day 3 overlays: the toggle row is visible only in range candle view,
   never in line view and never in 1D. Toggling re-runs draw(), which
   repaints the range candles with the new overlay set; switching to
   Line or to 1D hides the row and the canvas repaint drops the lines
   with it (same clear-state rule as the Day 1 fix). */
function syncOv(){
  var ov=$('bcOv');if(!ov)return;
  var on=CANDLE_RANGES.indexOf(rng)>=0&&RGCT==='candles';
  ov.style.display=on?'':'none';
  [].forEach.call(ov.querySelectorAll('[data-ov]'),function(b){b.classList.toggle('on',!!OV[b.dataset.ov]);b.setAttribute('aria-pressed',OV[b.dataset.ov]?'true':'false');});
}
function drawRange(){
  head();
  [].forEach.call($('bcRg').querySelectorAll('[data-r]'),function(b){b.classList.toggle('on',b.dataset.r===rng);b.setAttribute('aria-pressed',b.dataset.r===rng);});
  $('bcSc').style.display='none';var _ct=$('bcCt');if(_ct)_ct.style.display='none';
  var cg=$('bcCg');if(cg)cg.style.display='';syncOv();
  /* Candles are BTC-only, same rule as the 1D view: the S&P 500 / Gold / MSTR
     buttons are greyed for the candle view and their line behaviour is untouched. */
  var sb=$('bcSpx');if(sb){sb.setAttribute('aria-pressed','false');sb.classList.add('off');$('bcSpxT').textContent='+ S&P 500';sb.setAttribute('aria-label','S&P 500 unavailable for candle view');}
  var gb=$('bcGld');if(gb){gb.setAttribute('aria-pressed','false');gb.classList.add('off');$('bcGldT').textContent='+ Gold';gb.setAttribute('aria-label','Gold unavailable for candle view');}
  var mb=$('bcMstr');if(mb){mb.setAttribute('aria-pressed','false');mb.classList.add('off');$('bcMstrT').textContent='+ MSTR';mb.setAttribute('aria-label','MSTR unavailable for candle view');}
  syncCg();
  var fallback=function(msg){drawDaily();var nt=$('bcNt');if(nt)nt.textContent+=' '+msg;if(cg)cg.style.display='';syncCg();};
  var win,cut;
  if(rng==='YTD'||rng==='1Y'){
    /* Day 2: these two ranges need MORE than Coinbase's ~300-candle default
       window (YTD late in the year needs up to 365 days, 1Y needs 366), so
       they use the batched extended fetch, not CBDAILY.
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
    var need=rng==='YTD'?Math.ceil((Date.now()-Date.UTC(new Date().getUTCFullYear(),0,1))/864e5):366;
    if(!CBEXT||CBEXT_DAYS<need){
      if(CBEXT_ERR){fallback('Extended Coinbase candles unavailable — showing daily closes.');return;}
      loadExtendedDaily(need).then(function(){if(dlg&&!dlg.hidden&&(rng==='YTD'||rng==='1Y')&&RGCT==='candles')draw();}).catch(function(){if(dlg&&!dlg.hidden)draw();});
      $('bcRr').textContent='Loading '+(rng==='YTD'?'year-to-date':'1-year')+' candles…';return;
    }
    cut=rng==='YTD'?Date.UTC(new Date().getUTCFullYear(),0,1):Date.now()-366*864e5;
    win=CBEXT.filter(function(p){return p.t>=cut;});
  }else{
    if(!CBDAILY||CBDAILY.length<2){fallback('Coinbase daily candles unavailable — showing daily closes.');return;}
    var days=rng==='1W'?7:(rng==='1M'?31:(rng==='3M'?92:183));
    cut=Date.now()-days*864e5;
    win=CBDAILY.filter(function(p){return p.t>=cut;});
  }
  var cand=aggDailyCandles(win,RGGRAN);
  if(cand.length<2){fallback('Not enough daily candles — showing daily closes.');return;}
  RGCAND=cand;RGLBL=rng+' · '+RGGRAN+' candles';
  var a0=cand[0].o,b0=cand[cand.length-1].c,pc0=(b0/a0-1)*100;
  $('bcRr').textContent=rng+': BTC '+((pc0>=0?'+':'')+pc0.toFixed(2)+'%')+' · '+cand.length+' '+RGGRAN+' candles, from '+new Date(cand[0].t).toLocaleDateString('en-US',{timeZone:'UTC',month:'short',day:'numeric'})+' ('+fmt(a0)+')';
  var aggTxt=RGGRAN==='monthly'?'by calendar month (UTC)':(RGGRAN==='weekly'?'by Monday-start UTC week':'by day');
  $('bcNt').textContent='Coinbase daily candles (UTC days), aggregated '+aggTxt+'. Green = close above open, Red = below. Tap a candle for its High, Low and Change. Last candle is the latest complete UTC day; today\'s live price is not a candle. S&P 500, Gold and MSTR toggles are off for candle view only.'+((OV.sma||OV.ema||OV.bb)?' Overlays are calculated on the candles shown: 20 means 20 candles of the size shown, not 20 days, unless the size is daily.':'');
  if(ch){ch.destroy();ch=null;}
  CANDSEL=-1;CANDHOV=-1;drawCandlesRange();
}
function draw1D(){
  if(!window.Chart)return;
  head();
  [].forEach.call($('bcRg').querySelectorAll('[data-r]'),function(b){b.classList.toggle('on',b.dataset.r===rng);b.setAttribute('aria-pressed',b.dataset.r===rng);});
  $('bcSc').style.display='none';
  var sb=$('bcSpx');if(sb){sb.setAttribute('aria-pressed','false');sb.classList.add('off');$('bcSpxT').textContent='+ S&P 500';sb.setAttribute('aria-label','S&P 500 unavailable for 1D intraday');}
  var gb=$('bcGld');if(gb){gb.setAttribute('aria-pressed','false');gb.classList.add('off');$('bcGldT').textContent='+ Gold';gb.setAttribute('aria-label','Gold unavailable for 1D intraday');}
  var mb=$('bcMstr');if(mb){mb.setAttribute('aria-pressed','false');mb.classList.add('off');$('bcMstrT').textContent='+ MSTR';mb.setAttribute('aria-label','MSTR unavailable for 1D intraday');}
  var ct=$('bcCt');if(ct){ct.style.display='';[].forEach.call(ct.querySelectorAll('[data-ct]'),function(b){b.classList.toggle('on',b.dataset.ct===CT);b.setAttribute('aria-pressed',b.dataset.ct===CT);});}
  var cg1=$('bcCg');if(cg1)cg1.style.display='none';syncOv();
  if(!INTRA){
    $('bcRr').textContent='Loading intraday…';
    getIntraday().then(function(){if(dlg&&!dlg.hidden&&rng==='1D')draw1D();}).catch(function(){if(dlg&&!dlg.hidden){drawDaily();var nt=$('bcNt');if(nt)nt.textContent+=' Intraday unavailable — showing daily closes.';}});
    return;
  }
  if(Date.now()-INTRA_AT>5*60*1000&&!intraP){getIntraday().then(function(){if(dlg&&!dlg.hidden&&rng==='1D')draw1D();}).catch(function(){});}
  var pts=INTRA.pts.slice(),hasLive=live.usd!=null;
  if(CT!=='line'){
    var per=CT==='1h'?4:16, cand=aggCandles(pts,per);
    if(cand.length>=2 && cand[0].o!=null){
      var a0=cand[0].o, b0=cand[cand.length-1].c, pc0=(b0/a0-1)*100;
      $('bcRr').textContent='1D: BTC '+((pc0>=0?'+':'')+pc0.toFixed(2)+'%')+' · last 24 hours, '+CT+' candles, from '+etTime(cand[0].t)+' ET ('+fmt(a0)+')';
      $('bcNt').textContent='Coinbase '+CT+' candles, last 24 hours (ET). Green = close above open, Red = below. Tap a candle for its O/H/L/C. S&P 500, Gold and MSTR toggles are off for 1D only.';
      if(ch){ch.destroy();ch=null;}
      CANDSEL=-1;CANDHOV=-1;drawCandles1D(cand, CT==='1h'?'1-hour candles':'4-hour candles', per);
      return;
    }
  }
  /* Line view: any open candle pill/selection from the candle view is gone,
     and nothing here repaints candles (see fix note at candViewActive). */
  clearCandState();
  if(hasLive&&pts.length&&Date.now()>pts[pts.length-1].t)pts.push({t:Date.now(),v:live.usd,live:true});
  var n=pts.length,a=pts[0].v,b=pts[n-1].v,pc=(b/a-1)*100;
  var fp=function(x){return (x>=0?'+':'')+(Math.abs(x)>=1e4?Math.round(x).toLocaleString('en-US'):x.toFixed(1))+'%';};
  $('bcRr').textContent='1D: BTC '+fp(pc)+' · last 24 hours, from '+etTime(pts[0].t)+' ET ('+fmt(a)+')';
  $('bcNt').textContent='Intraday '+(INTRA.src==='coingecko'?'CoinGecko 1-day chart (Coinbase unavailable)':'Coinbase 15-minute candles')+', last 24 hours (ET); last point is the live price. S&P 500 and Gold toggles are off for 1D only (daily closes only).';
  var c=$('bcC').getContext('2d'),H=$('bcC').parentNode.clientHeight||300,g=c.createLinearGradient(0,0,0,H);g.addColorStop(0,'rgba(34,211,238,.28)');g.addColorStop(1,'rgba(34,211,238,0)');
  var lab=pts.map(function(p){return p.live?'Now (live)':etTime(p.t);});
  var ds=[{label:'BTC',data:pts.map(function(p){return p.v;}),borderColor:'#22d3ee',backgroundColor:g,fill:true,borderWidth:2,tension:.15,pointRadius:pts.map(function(p,i){return i===n-1&&hasLive?4:0;}),pointHoverRadius:3,pointBackgroundColor:'#22d3ee'}];
  var opts={animation:false,responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:false},
    tooltip:{displayColors:false,callbacks:{title:function(i){var k=i[0].dataIndex,p=pts[k];return p.live?'Now (live)':etDateTime(p.t);},
      label:function(i){return 'BTC '+fmt(i.parsed.y);}}}},
    scales:{x:{grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#9aa6bc',autoSkip:true,maxTicksLimit:isPhone()?5:7,maxRotation:0}},
      y:{grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#9aa6bc',callback:function(v){return v>=1000?'$'+(v/1000).toLocaleString('en-US')+'k':'$'+v;}}}}};
  if(ch)ch.destroy();ch=new Chart(c,{type:'line',data:{labels:lab,datasets:ds},options:opts});
}
function draw(){if(rng==='1D'){draw1D();}else if(CANDLE_RANGES.indexOf(rng)>=0&&RGCT==='candles'){drawRange();}else{drawDaily();}}

function onK(K,M,d){var lo=0,hi=K.length-1,a=-1;while(lo<=hi){var mid=(lo+hi)>>1;if(K[mid]<=d){a=mid;lo=mid+1;}else hi=mid-1;}return a<0?null:M[K[a]];}
function spxOn(d){return onK(SPXK,SPX,d);}function gldOn(d){return onK(GOLDK,GOLD,d);}function mstrOn(d){return onK(MSTRK,MSTR,d);}
function getData(){if(dataP)return dataP;
  var st=fetch(U('../data/btc-daily.json')).then(function(r){return r.json();});
  var sx=fetch(U('../data/spx-daily.json')).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
  var gx=fetch(U('../data/gold-daily.json')).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
  var mx=fetch(U('../data/mstr-daily.json')).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
  var hj=fetch(RAW+'?t='+Date.now(),{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
  var cb=fetch('https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400',{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
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
var rng='1M',LOG=false,dlg=null,dim=null,ch=null,opener=null;
function isPhone(){return window.innerWidth<=640;}
/* Vehicle toggle, Day 3: the popover carries the same shared toggle.
   It changes the shared mode (tracker / Pulse / holdings / Compare);
   this chart itself stays Spot BTC, and the note above says so.
   On pages without vehicle.js (Compare), the click falls back to
   sessionStorage + the 'psvehicle' event, which compare.js listens to. */
function syncVehBtns(){if(!dlg)return;var cur='SPOT',failed=false;
  try{cur=(window.PSVehicle&&window.PSVehicle.get())||sessionStorage.getItem('psVehicle')||'SPOT';failed=!!(window.PSVehicle&&window.PSVehicle.failed&&window.PSVehicle.failed());}catch(e){}
  [].forEach.call(dlg.querySelectorAll('#bcVeh [data-veh]'),function(b){var on=b.dataset.veh===cur;b.classList.toggle('on',on);b.setAttribute('aria-pressed',on);if(b.dataset.veh!=='SPOT'){b.disabled=failed;if(failed)b.title='Vehicle data unavailable';}});
  var nt=$('bcVehNt');if(nt)nt.style.display=(cur!=='SPOT')?'':'none';}
function build(){dim=document.createElement('div');dim.className='bc-dim';dim.hidden=true;
  dlg=document.createElement('div');dlg.className='bc-w';dlg.hidden=true;dlg.setAttribute('role','dialog');dlg.setAttribute('aria-modal','true');dlg.setAttribute('aria-labelledby','bcTitle');
  dlg.innerHTML='<div class="bc-grab" aria-hidden="true"></div><div class="bc-h"><div><span class="lp-lab" id="bcTitle"><span class="lp-dot" aria-hidden="true"></span>Live BTC · BTC/USD</span><div class="bc-px"><span id="bcPx">—</span><span id="bcChg" class="hdr-chg"></span></div><div class="bc-rr" id="bcRr"></div></div><button type="button" class="bc-x" id="bcX" aria-label="Close BTC chart">✕</button></div>'
   +'<div class="bc-veh" id="bcVeh" role="group" aria-label="Bitcoin vehicle"><span class="bc-ct-lab">Vehicle</span><button type="button" data-veh="SPOT">Spot BTC</button><button type="button" data-veh="IBIT">IBIT</button><button type="button" data-veh="FBTC">FBTC</button></div><div class="bc-veh-nt" id="bcVehNt" style="display:none">Vehicle mode applies to Pulse, tracker, holdings and Compare. This chart stays Spot BTC.</div>'
   +'<div class="bc-rg" id="bcRg"><div class="bc-rgs" id="bcRgs" role="group" aria-label="Chart range">'+RANGES.map(function(r){return '<button type="button" data-r="'+r+'">'+r+'</button>';}).join('')+'</div><span class="bc-sc" id="bcSc" role="group" aria-label="Scale"><button type="button" data-s="lin">Linear</button><button type="button" data-s="log">Log</button></span></div>'
   +'<div class="bc-lg" id="bcLg"><span class="bc-k bc-k-btc"><i aria-hidden="true"></i>BTC</span><button type="button" class="bc-k bc-k-spx" id="bcSpx" aria-pressed="false"><i aria-hidden="true"></i><span id="bcSpxT">+ S&amp;P 500</span></button><button type="button" class="bc-k bc-k-spx bc-k-gld" id="bcGld" aria-pressed="false"><i aria-hidden="true"></i><span id="bcGldT">+ Gold</span></button><button type="button" class="bc-k bc-k-spx bc-k-mstr" id="bcMstr" aria-pressed="false"><i aria-hidden="true"></i><span id="bcMstrT">+ MSTR</span></button></div><div class="bc-ct" id="bcCt" role="group" aria-label="1D chart type" style="display:none"><span class="bc-ct-lab">Chart</span><button type="button" data-ct="line">Line</button><button type="button" data-ct="1h">1H</button><button type="button" data-ct="4h">4H</button></div>'
   +'<div class="bc-ct" id="bcCg" role="group" aria-label="Range chart type" style="display:none"><span class="bc-ct-lab">Chart</span><button type="button" data-cg="line">Line</button><button type="button" data-cg="candles">Candles</button><span class="bc-ct-lab" id="bcCgGranLab" style="display:none">Size</span><button type="button" data-cggran="monthly" style="display:none">Monthly</button><button type="button" data-cggran="weekly" style="display:none">Weekly</button><button type="button" data-cggran="daily" style="display:none">Daily</button></div>'
   +'<div class="bc-ct" id="bcOv" role="group" aria-label="Candle overlays" style="display:none"><span class="bc-ct-lab">Overlays</span><button type="button" data-ov="sma">SMA 20 (candles shown)</button><button type="button" data-ov="ema">EMA 20 (candles shown)</button><button type="button" data-ov="bb">Bollinger (20, 2σ)</button></div>'
   +'<div class="bc-box"><canvas id="bcC" aria-label="BTC price chart" role="img"></canvas></div><div class="bc-nt" id="bcNt"></div><a class="bc-cl" href="'+U('../../compare/index.html')+'">See full Compare →</a>';
  document.body.appendChild(dim);document.body.appendChild(dlg);
  dim.addEventListener('click',close);$('bcVeh').addEventListener('click',function(e){var b=e.target.closest('[data-veh]');if(!b||b.disabled)return;var v=b.dataset.veh;
    if(window.PSVehicle&&window.PSVehicle.set){window.PSVehicle.set(v);}else{try{sessionStorage.setItem('psVehicle',v);}catch(err){}window.dispatchEvent(new CustomEvent('psvehicle',{detail:{vehicle:v,loaded:false}}));}
    syncVehBtns();});window.addEventListener('psvehicle',syncVehBtns);
  $('bcSpx').addEventListener('click',function(){SHOWSPX=!SHOWSPX;draw();});$('bcGld').addEventListener('click',function(){SHOWGLD=!SHOWGLD;draw();});$('bcMstr').addEventListener('click',function(){SHOWMSTR=!SHOWMSTR;draw();});$('bcCt').addEventListener('click',function(e){var b=e.target.closest('[data-ct]');if(!b)return;CT=b.dataset.ct;draw();});
  $('bcCg').addEventListener('click',function(e){var b=e.target.closest('[data-cg]');if(b){RGCT=b.dataset.cg;draw();return;}var g=e.target.closest('[data-cggran]');if(g){RGGRAN=g.dataset.cggran;draw();}});
  $('bcOv').addEventListener('click',function(e){var b=e.target.closest('[data-ov]');if(!b)return;OV[b.dataset.ov]=!OV[b.dataset.ov];syncOv();draw();});
  $('bcX').addEventListener('click',close);
  $('bcRg').addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;if(b.dataset.r){rng=b.dataset.r;if(!/^(5Y|10Y|Max)$/.test(rng))LOG=false;RGGRAN=(rng==='1M'?'weekly':(rng==='3M'||rng==='6M'||rng==='YTD'||rng==='1Y')?'monthly':'daily');}else if(b.dataset.s){LOG=b.dataset.s==='log';}draw();});
  document.addEventListener('keydown',function(e){if(dlg.hidden)return;if(e.key==='Escape'){e.preventDefault();close();}
    if(e.key==='Tab'){var f=[].slice.call(dlg.querySelectorAll('button,a[href]'));var a=f[0],z=f[f.length-1];if(e.shiftKey&&document.activeElement===a){e.preventDefault();z.focus();}else if(!e.shiftKey&&document.activeElement===z){e.preventDefault();a.focus();}}});
  var y0=null;dlg.addEventListener('touchstart',function(e){y0=(dlg.classList.contains('sheet')&&dlg.scrollTop<=0&&!e.target.closest('canvas'))?e.touches[0].clientY:null;},{passive:true});
  dlg.addEventListener('touchend',function(e){if(y0!=null&&e.changedTouches[0].clientY-y0>80)close();y0=null;},{passive:true});
  window.addEventListener('resize',function(){if(!dlg.hidden)place();});}
function place(){var ph=isPhone();dlg.classList.toggle('sheet',ph);dlg.classList.toggle('pop',!ph);dlg.querySelector('.bc-grab').style.display=ph?'':'none';
  if(ph){dlg.style.top=dlg.style.left='';}else{var r=pill.getBoundingClientRect(),w=Math.min(640,window.innerWidth-32);dlg.style.top=(r.bottom+10)+'px';dlg.style.left=Math.max(16,Math.min(r.left-20,window.innerWidth-w-16))+'px';}}
function head(){$('bcPx').textContent=live.usd!=null?fmt(live.usd):'—';var c=$('bcChg');c.textContent=typeof live.chg==='number'?(live.chg>=0?'+':'')+live.chg.toFixed(1)+'% 24h':'';c.className='hdr-chg '+(live.chg>=0?'up':'down');}
function series(){var d=DATA.slice(),today=new Date().toISOString().slice(0,10);
  if(live.usd!=null){if(d.length&&d[d.length-1][0]>=today)d.pop();d.push([today,live.usd]);}
  var last=new Date(d[d.length-1][0]+'T00:00:00Z'),st;
  if(rng==='Max')st='0000';else if(rng==='YTD')st=(last.getUTCFullYear()-1)+'-12-31';else st=new Date(last-DAYS[rng]*864e5).toISOString().slice(0,10);
  return d.filter(function(p){return p[0]>=st;});}
function drawDaily(){if(!DATA||!window.Chart)return;clearCandState();head();var _ct=$('bcCt');if(_ct)_ct.style.display='none';var _cg=$('bcCg');if(_cg){if(CANDLE_RANGES.indexOf(rng)>=0){_cg.style.display='';syncCg();}else _cg.style.display='none';}
/* Day 3: drawDaily is the line view (including the candle-failure fallback,
   where RGCT is still 'candles' but no candles are drawn), so the overlay
   row is hidden outright here rather than via syncOv(). */
var _ov=$('bcOv');if(_ov)_ov.style.display='none';var d=series(),big=/^(5Y|10Y|Max)$/.test(rng),hasLive=live.usd!=null,sxo=SHOWSPX&&SPXK.length>0,gxo=SHOWGLD&&GOLDK.length>0,mxo=SHOWMSTR&&MSTRK.length>0,sx=sxo||gxo||mxo;
  [].forEach.call($('bcRg').querySelectorAll('[data-r]'),function(b){b.classList.toggle('on',b.dataset.r===rng);b.setAttribute('aria-pressed',b.dataset.r===rng);});
  var onb=$('bcRgs').querySelector('.on'),rs=$('bcRgs');if(onb&&rs.scrollWidth>rs.clientWidth){var L=onb.offsetLeft-rs.offsetLeft,R=L+onb.offsetWidth;if(L<rs.scrollLeft+16||R>rs.scrollLeft+rs.clientWidth-16)rs.scrollTo({left:Math.max(0,L-(rs.clientWidth-onb.offsetWidth)/2),behavior:'smooth'});}
  $('bcSc').style.display=big?'':'none';[].forEach.call($('bcSc').children,function(b){var on=(b.dataset.s==='log')===LOG;b.classList.toggle('on',on);b.setAttribute('aria-pressed',on);});
  var mb=$('bcMstr');if(mb){var mxo2=SHOWMSTR&&MSTRK.length>0;mb.setAttribute('aria-pressed',mxo2?'true':'false');mb.classList.toggle('off',!mxo2);$('bcMstrT').textContent=mxo2?'MSTR ✕':'+ MSTR';mb.setAttribute('aria-label',mxo2?'Hide MSTR':'Show MSTR');}
  var sb=$('bcSpx');sb.setAttribute('aria-pressed',sxo?'true':'false');sb.classList.toggle('off',!sxo);$('bcSpxT').textContent=sxo?'S&P 500 ✕':'+ S&P 500';sb.setAttribute('aria-label',sxo?'Hide S&P 500':'Show S&P 500');
  var gb=$('bcGld');gb.setAttribute('aria-pressed',gxo?'true':'false');gb.classList.toggle('off',!gxo);$('bcGldT').textContent=gxo?'Gold ✕':'+ Gold';gb.setAttribute('aria-label',gxo?'Hide Gold':'Show Gold');
  var n=d.length,a=d[0][1],b=d[n-1][1],pc=(b/a-1)*100,pa=a<1?'$'+a.toFixed(2):fmt(a),fp=function(x){return (x>=0?'+':'')+(Math.abs(x)>=1e4?Math.round(x).toLocaleString('en-US'):x.toFixed(1))+'%';};
  var S=sxo?d.map(function(p){return spxOn(p[0]);}):null,s0=S&&S[0];if(S&&!s0){var k0=S.findIndex(function(v){return v!=null;});s0=k0>=0?S[k0]:null;}
  var spc=S&&s0?(S[n-1]/s0-1)*100:null;
  var G=gxo?d.map(function(p){return gldOn(p[0]);}):null,g0=G&&G[0],gk0=0;if(G&&!g0){gk0=G.findIndex(function(v){return v!=null;});g0=gk0>=0?G[gk0]:null;}
  var gpc=G&&g0?(G[n-1]/g0-1)*100:null,gLate=G&&g0&&gk0>0?d[gk0][0]:null;
  $('bcRr').textContent=rng==='Max'?'Max · from '+d[0][0]+' ('+pa+')':rng+': BTC '+fp(pc)+(spc!=null?' · S&P 500 '+fp(spc):'')+(gpc!=null?' · Gold '+fp(gpc):'')+' · from '+d[0][0]+' ('+pa+')';
  $('bcNt').textContent=(sx?((sxo&&gxo)?'All lines':'Both lines')+': % change from the first close in range (BTC daily UTC closes incl. weekends'+(sxo?'; S&P 500 ^GSPC session closes':'')+(gxo?'; Gold GC=F futures session closes':'')+', carried over weekends/holidays). '+(gLate?'Gold data starts '+gLate+'. ':''):'Daily closes (UTC day, weekends included)'+(hasLive?'; ':'. '))+(hasLive?(sx?'Last BTC point is the live price.':'last point is the live price.'):'')+(PROV?" Today's close is provisional until "+ET.btcCloseLabel()+".":'')+(LOG?' Log scale.':'');
  var c=$('bcC').getContext('2d'),H=$('bcC').parentNode.clientHeight||300,g=c.createLinearGradient(0,0,0,H);g.addColorStop(0,'rgba(34,211,238,.28)');g.addColorStop(1,'rgba(34,211,238,0)');
  var lab=d.map(function(p){return p[0];}),pr=function(i){return i===n-1&&hasLive?4:0;},ds;
  if(sx){var bi=d.map(function(p){return 100*p[1]/a;}),si=(S||[]).map(function(v){return v!=null&&s0?100*v/s0:null;});
    ds=[{label:'BTC',data:bi,raw:d.map(function(p){return p[1];}),borderColor:'#22d3ee',backgroundColor:'#22d3ee',fill:false,borderWidth:2,tension:.15,pointRadius:d.map(function(p,i){return pr(i);}),pointHoverRadius:3,pointBackgroundColor:'#22d3ee'},
        ];if(sxo)ds.push({label:'S&P 500',data:si,raw:S,borderColor:'#c4b5fd',backgroundColor:'#c4b5fd',fill:false,borderWidth:1.6,tension:.15,pointRadius:0,pointHoverRadius:3,spanGaps:true});
    if(gxo)ds.push({label:'Gold',data:G.map(function(v){return v!=null&&g0?100*v/g0:null;}),raw:G,borderColor:'#facc15',backgroundColor:'#facc15',fill:false,borderWidth:1.6,tension:.15,pointRadius:0,pointHoverRadius:3,spanGaps:false});
    if(mxo){var M=d.map(function(p){return mstrOn(p[0]);}),m0=M.find(function(v){return v!=null;});ds.push({label:'MSTR',data:M.map(function(v){return v!=null&&m0?100*v/m0:null;}),raw:M,borderColor:'#f97316',backgroundColor:'#f97316',fill:false,borderWidth:1.6,tension:.15,pointRadius:0,pointHoverRadius:3,spanGaps:true});}}
  else ds=[{label:'BTC',data:d.map(function(p){return p[1];}),borderColor:'#22d3ee',backgroundColor:g,fill:!LOG,borderWidth:2,tension:.15,pointRadius:d.map(function(p,i){return pr(i);}),pointHoverRadius:3,pointBackgroundColor:'#22d3ee'}];
  var yTick=function(v){if(sx){if(LOG){var m=v/Math.pow(10,Math.floor(Math.log10(v)+1e-9));if([1,2,5].indexOf(Math.round(m*1000)/1000)<0)return null;}var q=v-100;return (q>0?'+':'')+(Math.abs(q)>=1000?Math.round(q).toLocaleString('en-US'):Math.round(q))+'%';}
    if(LOG){var l=Math.log10(v);if(Math.abs(l-Math.round(l))>1e-6)return null;}return v>=1000?'$'+(v/1000).toLocaleString('en-US')+'k':'$'+v;};
  var opts={animation:false,responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:false},
    tooltip:{displayColors:sx,callbacks:{title:function(i){var k=i[0].dataIndex;return k===n-1&&hasLive?'Now (live) · '+i[0].label:i[0].label;},
      label:function(i){var raw=i.dataset.raw?i.dataset.raw[i.dataIndex]:i.parsed.y;if(!sx)return fmt(raw);if(raw==null)return null;var q=i.parsed.y-100;
        return i.dataset.label==='BTC'?'BTC '+fmt(raw)+' ('+fp(q)+')':i.dataset.label==='Gold'?'Gold $'+raw.toLocaleString('en-US',{maximumFractionDigits:0})+' ('+fp(q)+')':i.dataset.label==='MSTR'?'MSTR $'+raw.toLocaleString('en-US',{maximumFractionDigits:0})+' ('+fp(q)+')':'S&P 500 '+raw.toLocaleString('en-US',{maximumFractionDigits:0})+' ('+fp(q)+')';}}}},
    scales:{x:{grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#9aa6bc',autoSkip:true,maxTicksLimit:isPhone()?5:7,maxRotation:0,callback:function(v){var s=this.getLabelForValue(v);return n>400?s.slice(0,4):s.slice(5);}}},
      y:{type:LOG?'logarithmic':'linear',grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#9aa6bc',callback:yTick}}}};
  if(ch)ch.destroy();ch=new Chart(c,{type:'line',data:{labels:lab,datasets:ds},options:opts});}
function needChart(){return window.Chart?Promise.resolve():new Promise(function(ok,no){var s=document.createElement('script');s.src=U('../vendor/chart.umd.min.js');s.onload=ok;s.onerror=no;document.head.appendChild(s);});}
function open(from){if(!dlg)build();opener=from||pill;if(menu&&!menu.hidden){var mb=$('mnavBtn');if(mb)mb.click();}
  rng='1M';LOG=false;dim.hidden=false;dlg.hidden=false;place();head();syncVehBtns();[pill,mp,document.getElementById('btcLive')].forEach(function(e){e&&e.setAttribute('aria-expanded','true');});
  $('bcRr').textContent='Loading…';$('bcX').focus();
  Promise.all([getData(),needChart()]).then(draw).catch(function(){$('bcRr').textContent='Chart data unavailable right now.';});}
function close(){if(!dlg||dlg.hidden)return;dlg.hidden=true;dim.hidden=true;[pill,mp].forEach(function(e){e&&e.setAttribute('aria-expanded','false');});
  var o=opener&&opener.offsetParent?opener:pill;if(o&&o.offsetParent)o.focus();}
pill.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();dlg&&!dlg.hidden?close():open(pill);});
if(mp)mp.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();open(pill);});
var bc=document.getElementById('btcLive');if(bc){var bo=function(e){e.preventDefault();e.stopPropagation();dlg&&!dlg.hidden?close():(open(bc),bc.setAttribute('aria-expanded','true'));};bc.addEventListener('click',bo);bc.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '||e.key==='Spacebar')bo(e);});}
})();
/* re-land on #section after async content shifts layout (e.g. /#benchmarks, /#rules from other pages) */
window.addEventListener('load',function(){var h=location.hash.slice(1);if(!h)return;var el=document.getElementById(h);if(!el)return;
  [400,1500].forEach(function(t){setTimeout(function(){if(location.hash.slice(1)===h&&Math.abs(el.getBoundingClientRect().top)>120)el.scrollIntoView();},t);});});
