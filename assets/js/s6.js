(function(){
  /* Stock quotes come from a cached prices.json written every 5 min by a GitHub Action; visitors never call the quote API. */
  var ASOF='2026-10-19', START=100000;
  var CLOSE={BTC:81901.5625,MSTR:136.02,STRC:98.62,TSLA:368.06,PLTR:194.15};
  var PF=[
    {name:'Berkshire Killer',start:'$40k BTC / $20k STRC / $30k TSLA / $10k PLTR',base:95130.95,cash:101.22,h:{BTC:0.48338398041189323,STRC:202.43939845819736,TSLA:66.70817379384756,PLTR:56.258790436005626}},
    {name:'Hodler Jam Sandwich',start:'$70k BTC / $10k STRC / $20k MSTR',base:94527.28,cash:50.57,h:{BTC:0.8130629143894886,STRC:101.21969922909868,MSTR:131.62224680275892}},
    {name:'Hedge Fund Killer',start:'$55k BTC / $35k MSTR / $10k STRC',base:93886.04,cash:50.60,h:{BTC:0.6350798268681614,MSTR:234.07669748978063,STRC:101.21969922909868}},
    {name:'Saylor Moon',start:'$50k MSTR / $50k STRC',base:100006.74,cash:253.02,h:{MSTR:366.43327285642204,STRC:506.0984961454934}}
  ];
  var root=document.getElementById('pfLive'); if(!root) return;
  var btcSrc='CoinGecko',live={BTC:null}, src={}, prev={}, open={}, btcTime=null, btcChg=null, stkTime=null, lastTs=0;
  function anyLive(){return !!live.BTC||['MSTR','STRC','TSLA','PLTR'].some(function(k){return !!live[k];});}
  /* Month-end mode: date + closes come from prices.json monthEnd (workflow: last actual trading session <= prior ET month's last calendar day). Static Sep 30 closes are the fallback. */
  var MONTHEND={'2026-09-30':{BTC:83553.85,MSTR:153.09,STRC:99.35,TSLA:354.81,PLTR:187.05,SPY:762.63,QQQ:739.77,'BRK.B':497.95,GOLD:4154.23}};
  var MN=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  /* until prices.json loads, fall back to the latest static month-end */
  var mode='live', ks=Object.keys(MONTHEND).sort(), ME_D=ks[ks.length-1], ME=MONTHEND[ME_D];
  function fmtD(iso){var p=iso.split('-');return MN[+p[1]-1]+' '+(+p[2])+', '+p[0];}
  function meLabel(){return fmtD(ME_D);}
  function asOfLabel(){if(mode==='me')return 'Month-end close · '+meLabel();
    if(!anyLive()||!(cacheUpd||lastTs))return 'Last close · '+fmtD(ASOF);
    return 'Live market value · updated '+new Date(cacheUpd||lastTs).toLocaleTimeString('en-GB',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',hour12:false})+' ET';}
  function px(a){if(mode==='me'&&ME&&ME[a])return ME[a];return live[a]||CLOSE[a];}
  function lbl(a){if(mode==='me')return 'close '+meLabel().replace(/, \d+$/,'');if(a==='BTC')return live.BTC?'live '+btcSrc:'last close '+fmtD(ASOF).replace(/, \d+$/,'');return src[a]||'last close '+fmtD(ASOF).replace(/, \d+$/,'');}
  function hhmm(t){return new Date(t*1000).toLocaleTimeString('en-GB',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',hour12:false})+' ET';}
  function mktOpen(){var p=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',hour:'numeric',minute:'numeric',hour12:false}).formatToParts(new Date()),o={};p.forEach(function(x){o[x.type]=x.value;});
    var mins=(+o.hour%24)*60+(+o.minute);return ['Sat','Sun'].indexOf(o.weekday)<0&&mins>=235&&mins<=1215;}
  var stkLoaded=false, cacheUpd=0, JSONURL='https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/prices.json';
  function cacheLabel(){if(!cacheUpd)return '';var st=mktOpen()&&(Date.now()-cacheUpd>30*60*1000);
    return 'Stocks: cached · updated '+new Date(cacheUpd).toLocaleTimeString('en-GB',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',hour12:false})+' ET'+(st?' (stale)':'');}
  function tick(){if(document.hidden)return;if(!stkLoaded||mktOpen())loadStocks();}
  function loadStocks(){
    stkLoaded=true;
    var c=window.AbortController?new AbortController():null,t=c?setTimeout(function(){c.abort();},8000):0;
    fetch(JSONURL+'?t='+Date.now(),{cache:'no-store',signal:c?c.signal:undefined})
    .then(function(r){clearTimeout(t);if(!r.ok)throw new Error(r.status);return r.json();})
    .then(function(d){var u=Date.parse(d&&d.updated);if(u>0)cacheUpd=u;var S=(d&&d.stocks)||{};
      ['MSTR','STRC','TSLA','PLTR','SPY','QQQ','BRK.B'].forEach(function(T){var q=S[T];if(!q||typeof q.c!=='number'||!(q.c>0))return;
        var qt=q.t?q.t*1000:Date.now();if(qt>Date.now())qt=Date.now();if(['MSTR','STRC','TSLA','PLTR'].indexOf(T)>=0&&qt>lastTs)lastTs=qt;
        live[T]=q.c;prev[T]=(typeof q.pc==='number'&&q.pc>0)?q.pc:null;src[T]='cached '+(q.t?hhmm(q.t):'');});
      stkTime=cacheUpd?new Date(cacheUpd).toLocaleTimeString('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit'})+' ET':null;
      var b=d&&d.btc;if(!live.BTC&&b&&b.usd>0){live.BTC=b.usd;btcChg=(typeof b.chg24h==='number')?b.chg24h:null;btcSrc='cached '+(b.src||'');btcTime=b.time?new Date(b.time).toLocaleTimeString('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit'})+' ET':null;}
      var me=d&&d.monthEnd;if(me&&me.date&&me.px&&me.px.BTC&&me.v>=3){MONTHEND[me.date]=me.px;ME_D=me.date;ME=me.px;} /* use the saved month-end session date, not a client-computed weekday */
      var gd=d&&d.gold;if(gd&&gd.usd>0)live.GOLD=gd.usd;
      render();})
    .catch(function(){clearTimeout(t);/* keep last good prices; ASOF close if never loaded */render();});
  }
  function mp(v){return v.toLocaleString('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2});}
  function m(v){return v.toLocaleString('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0});}
  function pct(x){return '<span class="'+(x>=0?'up':'down')+'">'+(x>=0?'+':'')+(x*100).toFixed(2)+'%</span>';}
  /* Shared valuation: used by tracker cards AND the pulse strip */
  function compute(p){
    var v=p.cash, y=p.cash;
    Object.keys(p.h).forEach(function(a){var u=p.h[a],c=px(a);v+=u*c;
      /* yesterday: BTC from CoinGecko 24h change; stocks from Finnhub prior close (pc); fallback -> move 0 */
      var yc=c;
      if(mode==='me'){y+=u*c;return;}
      if(a==='BTC'){if(live.BTC&&btcChg!==null)yc=c/(1+btcChg/100);}
      else if(live[a]&&prev[a])yc=prev[a];
      y+=u*yc;});
    return {v:v,y:y,move:v/y-1};
  }
  var ORDER=['Hedge Fund Killer','Berkshire Killer','Hodler Jam Sandwich','Saylor Moon'];
  function renderPulse(){
    var g=document.getElementById('pulseGrid'); if(!g) return;
    var h='';
    ORDER.forEach(function(n){var p=PF.filter(function(x){return x.name===n;})[0],r=compute(p),ok=mode!=='me'&&(live.BTC&&btcChg!==null||!p.h.BTC);
      h+='<a class="pulse-card" href="#tracker"><span class="pulse-name">'+n+'</span><span class="pulse-val">'+m(r.v)+'</span><span class="pulse-chg">'+(ok?pct(r.move)+' today':'—')+'</span></a>';});
    g.innerHTML=h;
    var stk=Object.keys(src).some(function(k){return src[k];});
    if(mode==='me'){document.getElementById('pulseNote').textContent=asOfLabel()+' · all prices at month-end close';return;}
    document.getElementById('pulseNote').textContent=asOfLabel()+' · BTC: '+(live.BTC?btcSrc+' (every 60s)'+(btcChg!==null?', move = 24h':', 24h move n/a'):'last close')+' · stocks: '+(stk?'cached (every 5 min), move vs prior close':'last close, move 0')+(cacheLabel()?' · '+cacheLabel():'');
  }
  /* Shared live state for the YTD chart: same compute() as tracker + pulse */
  var KEYS=['berkshire','hodlr','hf','saylor'];
  function liveState(){var o={sleeves:{},btc:live.BTC||null,spy:live.SPY||null,qqq:live.QQQ||null,brk:live['BRK.B']||null,mstr:live.MSTR||null,gold:live.GOLD||null,btcTime:live.BTC?btcTime:null,
      stocksLive:['MSTR','STRC','TSLA','PLTR'].some(function(k){return !!src[k];}),stkTime:stkTime,label:asOfLabel(),meLabel:meLabel(),ts:lastTs,mode:mode,meDate:ME_D,me:ME};
    PF.forEach(function(p,i){o.sleeves[KEYS[i]]=compute(p).v;});return o;}
  window.PSLive={state:liveState};
  function render(){
    renderPulse();
    try{window.dispatchEvent(new CustomEvent('pslive',{detail:liveState()}));}catch(e){}
    var html='';
    PF.forEach(function(p,i){
      var v=compute(p).v, rows='';
      var ow={};p.start.split(' / ').forEach(function(x){var q=x.match(/\$(\d+)k (\w+)/);if(q)ow[q[2]]=+q[1];});
      Object.keys(p.h).forEach(function(a){var u=p.h[a],val=u*px(a);
        rows+='<tr><td>'+a+'</td><td>'+mp(px(a))+' <em>'+lbl(a)+'</em>'+'</td><td>'+m(val)+'</td><td>'+(ow[a]!=null?ow[a]+'%':'')+'</td><td>'+(val/v*100).toFixed(1)+'%</td></tr>';});
      rows+='<tr><td>STRC div receivable (cash)</td><td></td><td>'+m(p.cash)+'</td><td></td><td>'+(p.cash/v*100).toFixed(1)+'%</td></tr>';
      html+='<div class="pf-card'+(open[i]?' open':'')+'" data-i="'+i+'"><div class="pf-head"><span class="pf-name">'+p.name+'</span><span class="pf-val">'+m(v)+'</span>'+
        '<span class="pf-sub">since '+fmtD(ASOF)+' '+pct(v/p.base-1)+' &middot; YTD '+pct(v/START-1)+'</span></div>'+
        '<table class="pf-tbl"><tr><th>Asset</th><th>Price</th><th>Value</th><th>Original</th><th>Live</th></tr>'+rows+'</table><p class="pf-start">Started with $100k on January 1st, 2026: '+p.start+'.</p></div>';
    });
    root.querySelector('.pf-grid').innerHTML=html;
    root.querySelector('.pf-note').textContent=mode==='me'?asOfLabel()+'. All prices at the month-end close; switch to Live for current prices. Holdings set at the '+fmtD(ASOF)+' close. YTD vs $100,000 start on January 1st, 2026. Tap a portfolio for holdings.':asOfLabel()+'. BTC: '+(live.BTC?btcSrc+', refreshed every 60s':'last close '+fmtD(ASOF))+'. '+(Object.keys(src).some(function(k){return src[k];})?cacheLabel():'Stocks: last close '+fmtD(ASOF))+'. Holdings set at the '+fmtD(ASOF)+' close. YTD vs $100,000 start on January 1st, 2026. Tap a portfolio for holdings.';
  }
  root.addEventListener('click',function(e){
    var c=e.target.closest('.pf-card'); if(c){var i=c.dataset.i;open[i]=!open[i];render();}
  });
  window.addEventListener('btcprice',function(e){live.BTC=e.detail.usd;btcChg=(typeof e.detail.chg==='number')?e.detail.chg:null;btcTime=e.detail.time;btcSrc=e.detail.src||'CoinGecko';lastTs=Date.now();render();});
  document.querySelectorAll('#modeToggle .bench-btn').forEach(function(b){b.addEventListener('click',function(){mode=b.dataset.mode;
    document.querySelectorAll('#modeToggle .bench-btn').forEach(function(x){x.classList.toggle('active',x.dataset.mode===mode);});
    if(mode==='live')loadStocks();render();});});
  render(); tick(); setInterval(tick,5*60*1000);
  document.addEventListener('visibilitychange',function(){if(!document.hidden&&mktOpen())loadStocks();});
})();
