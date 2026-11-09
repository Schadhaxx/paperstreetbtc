window.psC=window.psC||function(d,l){return document.documentElement.getAttribute('data-theme')==='light'?l:d;};
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
/* V2 6 Nov 2026: inline mode. On /clock/ there is no header pill (#hdrTick),
   so the script mounts the whole popover chart into #bcInline instead of
   opening it as a dialog. Nothing else changes: same data, same ranges,
   same candles, same compare toggles. */
var pill=$('hdrTick'),menu=$('mnavMenu');
var INLINEHOST=document.getElementById('bcInline');
if(!pill&&!INLINEHOST)return;
var INLINE=!!INLINEHOST;
var live={usd:null,chg:null};
/* CAD display, 6 Nov 2026 (clock page only): the clock page sets
   window.BC_CUR={code:'CAD',rate:<CAD per USD>} before this script loads
   and calls window.BC_setCurrency(code,rate) on toggle. Every displayed
   $ value is converted at that live rate; the series stays USD internally,
   so the shape never changes and historical CAD values use today's rate
   (approximate — the clock page says so). The popover never sets BC_CUR,
   so USD output is identical to before. */
var CUR=window.BC_CUR||{code:'USD',rate:1};
var curSym=function(){return CUR.code==='CAD'?'C$':'$';};
var curVal=function(v){return v*(CUR.rate||1);};
var cadTag=function(){return CUR.code==='CAD'?' · CAD':'';};
var fmt=function(n){var v=curVal(n);return curSym()+(v<1?v.toLocaleString('en-US',{maximumFractionDigits:2}):Math.round(v).toLocaleString('en-US'));};
var mp=null;

/* __BTCP bridge: the lazy panel (btcchart-panel.js) reads these shared
   values and fills in onLive/open/close/redraw/isOpen when it loads.
   fmt/curVal/curSym/CUR stay here so CAD conversion is shared, never
   re-implemented USD-only in the panel. */
var P=window.__BTCP={$,U,RAW,pill,menu,live,fmt,curVal,curSym,cadTag,CUR,mp:mp,onLive:null,open:null,close:null,redraw:null,panelReady:false,panelP:null,pendingFrom:null,INLINE:INLINE};
window.BC_setCurrency=function(code,rate){CUR.code=code;CUR.rate=rate||1;var t=$('bcTitle');if(t)t.innerHTML='<span class="lp-dot" aria-hidden="true"></span>Live BTC · BTC/'+code+'';if(P.redraw)P.redraw();else if(INLINE&&!P.panelReady)loadPanel().catch(function(){showErr();});};

/* pill markup */
function decorate(el,full){if(el.querySelector('.lp-cv'))return;
  el.insertAdjacentHTML('afterbegin','<span class="lp-lab"><span class="lp-dot" aria-hidden="true"></span>Live BTC</span>');
  el.insertAdjacentHTML('beforeend','<span class="lp-cv" aria-hidden="true"><svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden="true"><path d="M2 10.5L5 7L8 8.5L12 3.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="3.5" r="1.4" fill="currentColor"/></svg>Chart</span>');}
if(pill){decorate(pill);
pill.setAttribute('aria-haspopup','dialog');pill.setAttribute('aria-expanded','false');
if(!pill.getAttribute('aria-label'))pill.setAttribute('aria-label','Live BTC price. Open BTC chart');}
/* phone menu panel has no price (the header pill is the only price) */
function chgTxt(c){return typeof c==='number'?(c>=0?'▲':'▼')+Math.abs(c).toFixed(1)+'%':'';}
function paint(){if(live.usd==null)return;var cls='hdr-chg '+(live.chg>=0?'up':'down');
  var hp=$('hdrPx'),hc=$('hdrChg');if(hp){hp.textContent=fmt(live.usd);}if(hc&&typeof live.chg==='number'){hc.textContent=chgTxt(live.chg);hc.className=cls;}
  if(mp){mp.querySelector('.mpPx').textContent=fmt(live.usd);var m=mp.querySelector('.mpChg');m.textContent=chgTxt(live.chg);m.className=cls+' mpChg';}
  /* Live-price refresh into an open panel (head + tick flash + redraw)
     lives in the panel's onLive; before it loads there is nothing to forward to. */
  if(P.onLive)P.onLive();}
window.addEventListener('btcprice',function(e){live.usd=e.detail.usd;live.chg=e.detail.chg;paint();});
/* pages without the homepage price widget fetch the same feed themselves */
if(!$('btcLive')){
  var tf=function(u){return fetch(u,{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();});};
  var load=function(){tf('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true').then(function(d){var b=d.bitcoin;if(!b||typeof b.usd!=='number')throw 0;return {usd:b.usd,chg:b.usd_24h_change};})
    .catch(function(){return tf('https://api.coinbase.com/v2/prices/BTC-USD/spot').then(function(d){var a=parseFloat(d.data.amount);if(!(a>0))throw 0;return {usd:a,chg:null};});})
    .then(function(b){live.usd=b.usd;live.chg=b.chg;paint();setTimeout(load,60000);},function(){setTimeout(load,90000);});};
  load();}

/* Lazy panel loading (speed, 6 Nov 2026): the chart panel (~67 KB) is
   injected on first open only; the pill above stays eager. Single shared
   promise; repeated clicks only refresh pendingFrom, then open once. */
function hideErr(){var el=$('btcChartErr');if(el){el.hidden=true;el.textContent='';}}
function showErr(){
  var el=$('btcChartErr');
  if(!el){
    el=document.createElement('div');
    el.id='btcChartErr';
    el.setAttribute('role','alert');
    el.setAttribute('aria-live','assertive');
    el.setAttribute('tabindex','-1');
    el.style.cssText='position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:10000;max-width:min(420px,92vw);padding:12px 14px;border-radius:10px;background:#121a2e;color:#e8eef7;border:1px solid rgba(255,255,255,.16);font:14px Inter,system-ui,sans-serif;box-shadow:0 8px 28px rgba(0,0,0,.45)';
    document.body.appendChild(el);
  }
  el.hidden=false;
  el.innerHTML='Chart unavailable &mdash; <button type="button" id="btcChartRetry" style="margin-left:6px;font:inherit;color:#22d3ee;background:transparent;border:0;text-decoration:underline;cursor:pointer;padding:0">try again</button>';
  var btn=$('btcChartRetry');
  /* Retry: if the panel is already loaded, re-run its open (popover) or
     remount (clock inline) directly — doOpen would no-op because the
     dialog is already open. If the panel itself failed to load, doOpen
     retries the panel inject. */
  if(btn)btn.onclick=function(){hideErr();if(P.panelReady&&P.open&&INLINE&&P.remount){P.remount();}else if(P.panelReady&&P.open){P.open(P.pendingFrom||pill);}else{doOpen(P.pendingFrom||pill);}};
  try{el.focus();}catch(e){}
}
P.showErr=showErr;
function loadPanel(){
  if(P.panelReady)return Promise.resolve();
  if(P.panelP)return P.panelP;
  P.panelP=new Promise(function(ok,no){
    var s=document.createElement('script');
    s.src=U('btcchart-panel.js?v=et24');
    s.onload=function(){ok();};
    s.onerror=function(){P.panelP=null;no(new Error('btc panel'));};
    document.head.appendChild(s);
  });
  return P.panelP;
}
function isOpen(){var d=document.querySelector('.bc-w');return d&&!d.hidden;}
function doOpen(from){
  P.pendingFrom=from||pill;
  hideErr();
  if(isOpen())return;
  if(P.panelReady&&P.open){P.open(P.pendingFrom);return;}
  loadPanel().then(function(){
    if(P.open&&!isOpen())P.open(P.pendingFrom||pill);
  }).catch(function(){showErr();});
}
function doToggle(from){
  if(P.panelReady&&P.close&&isOpen()){P.close();return;}
  doOpen(from);
}
if(pill)pill.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();doToggle(pill);});
if(mp)mp.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();doOpen(pill);});
var bc=document.getElementById('btcLive');if(bc){var bo=function(e){e.preventDefault();e.stopPropagation();if(P.panelReady&&P.close&&isOpen()){P.close();bc.setAttribute('aria-expanded','false');}else{doOpen(bc);bc.setAttribute('aria-expanded','true');}};bc.addEventListener('click',bo);bc.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '||e.key==='Spacebar')bo(e);});}
/* /clock/ has no pill, only #bcInline: load the panel on page load so the
   inline chart mounts there. The panel itself calls mountInline(). */
if(INLINE)loadPanel().catch(function(){showErr();});

})();
/* re-land on #section after async content shifts layout (e.g. /#benchmarks, /#rules from other pages) */
window.addEventListener('load',function(){var h=location.hash.slice(1);if(!h)return;var el=document.getElementById(h);if(!el)return;
  [400,1500].forEach(function(t){setTimeout(function(){if(location.hash.slice(1)===h&&Math.abs(el.getBoundingClientRect().top)>120)el.scrollIntoView();},t);});});
