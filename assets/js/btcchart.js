/* Live BTC pill (header). Heavy chart panel loads on first open (btcchart-panel.js). */
(function(){
var SRC=(document.currentScript&&document.currentScript.src)||location.href;
var U=function(p){return new URL(p,SRC).href;};
var $=function(i){return document.getElementById(i);};
var pill=$('hdrTick'),menu=$('mnavMenu');if(!pill)return;
var live={usd:null,chg:null};
var fmt=function(n){return n.toLocaleString('en-US',{style:'currency',currency:'USD',maximumFractionDigits:n<1?2:0});};
function decorate(el){if(el.querySelector('.lp-cv'))return;
  el.insertAdjacentHTML('afterbegin','<span class="lp-lab"><span class="lp-dot" aria-hidden="true"></span>Live BTC</span>');
  el.insertAdjacentHTML('beforeend','<span class="lp-cv" aria-hidden="true">▾</span>');}
decorate(pill);
pill.setAttribute('aria-haspopup','dialog');pill.setAttribute('aria-expanded','false');
if(!pill.getAttribute('aria-label'))pill.setAttribute('aria-label','Live BTC price. Open BTC chart');
var mp=null;
function chgTxt(c){return typeof c==='number'?(c>=0?'▲':'▼')+Math.abs(c).toFixed(1)+'%':'';}
function paint(){if(live.usd==null)return;var cls='hdr-chg '+(live.chg>=0?'up':'down');
  var hp=$('hdrPx'),hc=$('hdrChg');if(hp){hp.textContent=fmt(live.usd);}if(hc&&typeof live.chg==='number'){hc.textContent=chgTxt(live.chg);hc.className=cls;}
  if(mp){mp.querySelector('.mpPx').textContent=fmt(live.usd);var m=mp.querySelector('.mpChg');m.textContent=chgTxt(live.chg);m.className=cls+' mpChg';}
  if(P.onLive)P.onLive();}
var P=window.__BTCP={$,U,pill,menu,live,fmt,mp:null,onLive:null,open:null,close:null,panelReady:false,panelP:null,pendingFrom:null};
function hideErr(){var el=$('btcChartErr');if(el){el.hidden=true;el.textContent='';}}
function showErr(){
  var el=$('btcChartErr');
  if(!el){
    el=document.createElement('div');
    el.id='btcChartErr';
    el.setAttribute('role','alert');
    el.setAttribute('aria-live','assertive');
    el.style.cssText='position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:10000;max-width:min(420px,92vw);padding:12px 14px;border-radius:10px;background:#121a2e;color:#e8eef7;border:1px solid rgba(255,255,255,.16);font:14px Inter,system-ui,sans-serif;box-shadow:0 8px 28px rgba(0,0,0,.45)';
    document.body.appendChild(el);
  }
  el.hidden=false;
  el.innerHTML='Chart unavailable; <button type="button" id="btcChartRetry" style="margin-left:6px;font:inherit;color:#22d3ee;background:transparent;border:0;text-decoration:underline;cursor:pointer;padding:0">try again</button>';
  var btn=$('btcChartRetry');
  if(btn)btn.onclick=function(){hideErr();doOpen(P.pendingFrom||pill);};
  try{el.focus();}catch(e){}
}
function loadPanel(){
  if(P.panelReady)return Promise.resolve();
  if(P.panelP)return P.panelP;
  P.panelP=new Promise(function(ok,no){
    var s=document.createElement('script');
    s.src=U('btcchart-panel.js?v=et7');
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
  /* Single shared load promise: repeated clicks only refresh pendingFrom, then open once. */
  loadPanel().then(function(){
    if(P.open&&!isOpen())P.open(P.pendingFrom||pill);
  }).catch(function(){showErr();});
}
function doToggle(from){
  if(P.panelReady&&P.close&&isOpen()){P.close();return;}
  doOpen(from);
}
window.addEventListener('btcprice',function(e){live.usd=e.detail.usd;live.chg=e.detail.chg;paint();});
if(!$('btcLive')){
  var tf=function(u){return fetch(u,{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();});};
  var load=function(){tf('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true').then(function(d){var b=d.bitcoin;if(!b||typeof b.usd!=='number')throw 0;return {usd:b.usd,chg:b.usd_24h_change};})
    .catch(function(){return tf('https://api.coinbase.com/v2/prices/BTC-USD/spot').then(function(d){var a=parseFloat(d.data.amount);if(!(a>0))throw 0;return {usd:a,chg:null};});})
    .then(function(b){live.usd=b.usd;live.chg=b.chg;paint();setTimeout(load,60000);},function(){setTimeout(load,90000);});};
  load();}
pill.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();doToggle(pill);});
if(mp)mp.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();doOpen(pill);});
var bc=document.getElementById('btcLive');
if(bc){var bo=function(e){e.preventDefault();e.stopPropagation();if(P.panelReady&&P.close&&isOpen()){P.close();bc.setAttribute('aria-expanded','false');}else{doOpen(bc);bc.setAttribute('aria-expanded','true');}};bc.addEventListener('click',bo);bc.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '||e.key==='Spacebar')bo(e);});}
})();
/* re-land on #section after async content shifts layout (e.g. /#benchmarks, /#rules from other pages) */
window.addEventListener('load',function(){var h=location.hash.slice(1);if(!h)return;var el=document.getElementById(h);if(!el)return;
  [400,1500].forEach(function(t){setTimeout(function(){if(location.hash.slice(1)===h&&Math.abs(el.getBoundingClientRect().top)>120)el.scrollIntoView();},t);});});
