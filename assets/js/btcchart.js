/* Live BTC pill (header + phone menu panel) and the BTC chart popover/bottom sheet.
   Data: assets/data/btc-daily.json (2010-08-18..2014-09-16 blockchain.info, then Yahoo BTC-USD UTC-day closes),
   extended with newer BTC closes from the data branch history.json and Coinbase daily candles (weekends included),
   plus the live price from the same feed as the header pill (CoinGecko, Coinbase fallback). */
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
if(menu){var wrap=document.createElement('div');wrap.className='mnav-live';
  mp=document.createElement('button');mp.type='button';mp.className='hdr-tick';mp.setAttribute('aria-haspopup','dialog');mp.setAttribute('aria-expanded','false');mp.setAttribute('aria-label','Live BTC price. Open BTC chart');
  mp.innerHTML='<span class="lp-lab"><span class="lp-dot" aria-hidden="true"></span>Live BTC</span><span><span class="hdr-sym">₿</span> <span class="mpPx">—</span> <span class="hdr-chg mpChg"></span> <span class="lp-cv" aria-hidden="true">▾</span></span>';
  wrap.appendChild(mp);menu.insertBefore(wrap,menu.firstChild);}
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
var DATA=null,PROV=false,dataP=null;
function getData(){if(dataP)return dataP;
  var st=fetch(U('../data/btc-daily.json')).then(function(r){return r.json();});
  var hj=fetch(RAW+'?t='+Date.now(),{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
  var cb=fetch('https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400',{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
  dataP=Promise.all([st,hj,cb]).then(function(r){var m={},s=r[0].d,end=r[0].end;s.forEach(function(p){m[p[0]]=p[1];});
    var today=new Date().toISOString().slice(0,10);
    if(Array.isArray(r[2]))r[2].forEach(function(c){var d=new Date(c[0]*1000).toISOString().slice(0,10);if(d>end&&d<today)m[d]=c[4];});
    if(r[1]&&r[1].closes){for(var d in r[1].closes){var v=r[1].closes[d].BTC;if(d>end&&v!=null)m[d]=v;}PROV=(r[1].btc_provisional||[]).length>0;}
    DATA=Object.keys(m).sort().map(function(d){return [d,m[d]];});return DATA;});
  dataP.catch(function(){dataP=null;});return dataP;}
/* dialog */
var RANGES=['1W','1M','3M','YTD','1Y','5Y','10Y','Max'],DAYS={'1W':7,'1M':31,'3M':92,'1Y':366,'5Y':1827,'10Y':3653};
var rng='1M',LOG=false,dlg=null,dim=null,ch=null,opener=null;
function isPhone(){return window.innerWidth<=640;}
function build(){dim=document.createElement('div');dim.className='bc-dim';dim.hidden=true;
  dlg=document.createElement('div');dlg.className='bc-w';dlg.hidden=true;dlg.setAttribute('role','dialog');dlg.setAttribute('aria-modal','true');dlg.setAttribute('aria-labelledby','bcTitle');
  dlg.innerHTML='<div class="bc-grab" aria-hidden="true"></div><div class="bc-h"><div><span class="lp-lab" id="bcTitle"><span class="lp-dot" aria-hidden="true"></span>Live BTC · BTC/USD</span><div class="bc-px"><span id="bcPx">—</span><span id="bcChg" class="hdr-chg"></span></div><div class="bc-rr" id="bcRr"></div></div><button type="button" class="bc-x" id="bcX" aria-label="Close BTC chart">✕</button></div>'
   +'<div class="bc-rg" id="bcRg"><div class="bc-rgs" id="bcRgs" role="group" aria-label="Chart range">'+RANGES.map(function(r){return '<button type="button" data-r="'+r+'">'+r+'</button>';}).join('')+'</div><span class="bc-sc" id="bcSc" role="group" aria-label="Scale"><button type="button" data-s="lin">Linear</button><button type="button" data-s="log">Log</button></span></div>'
   +'<div class="bc-box"><canvas id="bcC" aria-label="BTC price chart" role="img"></canvas></div><div class="bc-nt" id="bcNt"></div><a class="bc-cl" href="'+U('../../compare/index.html')+'">See full Compare →</a>';
  document.body.appendChild(dim);document.body.appendChild(dlg);
  dim.addEventListener('click',close);$('bcX').addEventListener('click',close);
  $('bcRg').addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;if(b.dataset.r){rng=b.dataset.r;LOG=/^(5Y|10Y|Max)$/.test(rng);}else if(b.dataset.s){LOG=b.dataset.s==='log';}draw();});
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
function draw(){if(!DATA||!window.Chart)return;head();var d=series(),big=/^(5Y|10Y|Max)$/.test(rng),hasLive=live.usd!=null;
  [].forEach.call($('bcRg').querySelectorAll('[data-r]'),function(b){b.classList.toggle('on',b.dataset.r===rng);b.setAttribute('aria-pressed',b.dataset.r===rng);});
  var onb=$('bcRgs').querySelector('.on'),rs=$('bcRgs');if(onb&&rs.scrollWidth>rs.clientWidth){var L=onb.offsetLeft-rs.offsetLeft,R=L+onb.offsetWidth;if(L<rs.scrollLeft+16||R>rs.scrollLeft+rs.clientWidth-16)rs.scrollTo({left:Math.max(0,L-(rs.clientWidth-onb.offsetWidth)/2),behavior:'smooth'});}
  $('bcSc').style.display=big?'':'none';[].forEach.call($('bcSc').children,function(b){var on=(b.dataset.s==='log')===LOG;b.classList.toggle('on',on);b.setAttribute('aria-pressed',on);});
  var a=d[0][1],b=d[d.length-1][1],pc=(b/a-1)*100,pa=a<1?'$'+a.toFixed(2):fmt(a);
  $('bcRr').textContent=rng==='Max'?'Max · from '+d[0][0]+' ('+pa+')':rng+': '+(pc>=0?'+':'')+(Math.abs(pc)>=1e4?Math.round(pc).toLocaleString('en-US'):pc.toFixed(1))+'% · from '+d[0][0]+' ('+pa+')';
  $('bcNt').textContent='Daily closes (UTC day, weekends included)'+(hasLive?'; last point is the live price.':'.')+(PROV?" Today's close is provisional until 8 PM ET.":'')+(LOG?' Log scale.':'');
  var c=$('bcC').getContext('2d'),H=$('bcC').parentNode.clientHeight||300,g=c.createLinearGradient(0,0,0,H);g.addColorStop(0,'rgba(34,211,238,.28)');g.addColorStop(1,'rgba(34,211,238,0)');
  var n=d.length,cfg={labels:d.map(function(p){return p[0];}),datasets:[{data:d.map(function(p){return p[1];}),borderColor:'#22d3ee',backgroundColor:g,fill:!LOG,borderWidth:2,tension:.15,
    pointRadius:d.map(function(p,i){return i===n-1&&hasLive?4:0;}),pointHoverRadius:3,pointBackgroundColor:'#22d3ee'}]};
  var yTick=function(v){if(LOG){var l=Math.log10(v);if(Math.abs(l-Math.round(l))>1e-6)return null;}return v>=1000?'$'+(v/1000).toLocaleString('en-US')+'k':'$'+v;};
  var opts={animation:false,responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:false},
    tooltip:{displayColors:false,callbacks:{title:function(i){var k=i[0].dataIndex;return k===n-1&&hasLive?'Now (live)':i[0].label;},label:function(i){return fmt(i.parsed.y);}}}},
    scales:{x:{grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#9aa6bc',autoSkip:true,maxTicksLimit:isPhone()?5:7,maxRotation:0,callback:function(v){var s=this.getLabelForValue(v);return n>400?s.slice(0,4):s.slice(5);}}},
      y:{type:LOG?'logarithmic':'linear',grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#9aa6bc',callback:yTick}}}};
  if(ch)ch.destroy();ch=new Chart(c,{type:'line',data:cfg,options:opts});}
function needChart(){return window.Chart?Promise.resolve():new Promise(function(ok,no){var s=document.createElement('script');s.src=U('../vendor/chart.umd.min.js');s.onload=ok;s.onerror=no;document.head.appendChild(s);});}
function open(from){if(!dlg)build();opener=from||pill;if(menu&&!menu.hidden){var mb=$('mnavBtn');if(mb)mb.click();}
  rng='1M';LOG=false;dim.hidden=false;dlg.hidden=false;place();head();[pill,mp].forEach(function(e){e&&e.setAttribute('aria-expanded','true');});
  $('bcRr').textContent='Loading…';$('bcX').focus();
  Promise.all([getData(),needChart()]).then(draw).catch(function(){$('bcRr').textContent='Chart data unavailable right now.';});}
function close(){if(!dlg||dlg.hidden)return;dlg.hidden=true;dim.hidden=true;[pill,mp].forEach(function(e){e&&e.setAttribute('aria-expanded','false');});
  var o=opener&&opener.offsetParent?opener:pill;if(o&&o.offsetParent)o.focus();}
pill.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();dlg&&!dlg.hidden?close():open(pill);});
if(mp)mp.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();open(pill);});
})();
/* re-land on #section after async content shifts layout (e.g. /#benchmarks, /#rules from other pages) */
window.addEventListener('load',function(){var h=location.hash.slice(1);if(!h)return;var el=document.getElementById(h);if(!el)return;
  [400,1500].forEach(function(t){setTimeout(function(){if(location.hash.slice(1)===h&&Math.abs(el.getBoundingClientRect().top)>120)el.scrollIntoView();},t);});});
