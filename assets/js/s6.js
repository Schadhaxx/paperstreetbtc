(function(){ if(!window.PSBook) return; PSBook.ready.then(function(BK){
  /* Stock quotes come from a cached prices.json written every 5 min by a GitHub Action; visitors never call the quote API. */
  /* No stored values: holdings + receivable cash come from the ledger (ledger.js) via PSBook; ASOF = latest close in the site's own history.json */
  var ASOF=BK.last, START=PSLEDGER.start;
  var CLOSE=BK.close(ASOF);
  var PRIOR=(ASOF===todayET()&&BK.dates.length>1)?BK.dates[BK.dates.length-2]:ASOF; /* yesterday's close once today's row exists */
  function todayET(){return ET.today();}
  var PF=[
    {name:'Berkshire Killer',start:'$40k BTC / $20k STRC / $30k TSLA / $10k PLTR',key:'berkshire'},
    {name:'Hodler Jam Sandwich',start:'$70k BTC / $10k STRC / $20k MSTR',key:'hodlr'},
    {name:'Hedge Fund Killer',start:'$55k BTC / $35k MSTR / $10k STRC',key:'hf'},
    {name:'Saylor Moon',start:'$50k MSTR / $50k STRC',key:'saylor'}
  ];
  var root=document.getElementById('pfLive'); if(!root) return;
  var btcSrc='CoinGecko',live={BTC:null}, src={}, prev={}, open={}, btcTime=null, btcChg=null, stkTime=null, lastTs=0;
  function anyLive(){return !!live.BTC||['MSTR','STRC','TSLA','PLTR'].some(function(k){return !!live[k];});}
  /* Month-end mode: date from prices.json monthEnd (workflow: last actual trading session <= prior ET month's last calendar day); prices = that session's close in history.json
     (prices.json monthEnd closes only if the session is not in history yet). Until prices.json loads: the latest completed month-end in history. */
  var MONTHEND={}, PTS=BK.points(); (function(){var d=PTS.filter(function(x){return x!==PSLEDGER.base&&x!==BK.last;}).pop()||BK.last;MONTHEND[d]=BK.close(d);})();
  var MN=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  /* until prices.json loads, fall back to the latest static month-end */
  var mode='live', ks=Object.keys(MONTHEND).sort(), ME_D=ks[ks.length-1], ME=MONTHEND[ME_D];
  function fmtD(iso){var p=iso.split('-');return MN[+p[1]-1]+' '+(+p[2])+', '+p[0];}
  function meLabel(){return fmtD(ME_D);}
  /* 'today' only on an NYSE session day once today's row exists; otherwise the honest 'since <prior close>' */
  function chgLabel(){return (mode!=='me'&&ASOF===todayET()&&ET.session(ASOF))?'today':'since '+fmtD(PRIOR);}
  /* '(live)' only while stocks are trading or the BTC price is fresh (< 3 min) */
  /* one rule for every label: stock quotes count as live only while the market is open AND prices.json is < 30 min old */
  function stocksFresh(){return mktOpen()&&cacheUpd>0&&Date.now()-cacheUpd<30*60*1000&&Object.keys(src).some(function(k){return src[k];});}
  function isLive(){return mode!=='me'&&(stocksFresh()||(live.BTC&&lastTs&&Date.now()-lastTs<180000));}
  function ytdLabel(){return !isLive()?'YTD':stocksFresh()?'YTD (live)':'YTD (BTC live)';}
  window.PSLiveLabel=function(){return isLive();};window.PSMktOpen=function(){return stocksFresh();};
  function asOfLabel(){if(mode==='me')return 'Month-end close · '+meLabel();
    if(!anyLive()||!(cacheUpd||lastTs))return 'Last close · '+fmtD(ASOF);
    if(!stocksFresh())return 'BTC live · stocks at '+fmtD(ASOF)+' close · updated '+ET.time(new Date(lastTs||cacheUpd));
    return 'Live market value · updated '+ET.time(new Date(cacheUpd||lastTs));}
  function px(a){if(mode==='me'){var hc=BK.close(ME_D);if(hc&&hc[a])return hc[a];if(ME&&ME[a])return ME[a];}return live[a]||CLOSE[a];}
  function lbl(a){if(mode==='me')return 'close '+meLabel().replace(/, \d+$/,'');if(a==='BTC')return live.BTC?'live '+btcSrc:'last close '+fmtD(ASOF).replace(/, \d+$/,'');return src[a]||'last close '+fmtD(ASOF).replace(/, \d+$/,'');}
  function hhmm(t){return ET.time(new Date(t*1000));}
  function mktOpen(){var p=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',hour:'numeric',minute:'numeric',hour12:false}).formatToParts(new Date()),o={};p.forEach(function(x){o[x.type]=x.value;});
    var mins=(+o.hour%24)*60+(+o.minute);var cm=ET.closeMin(ET.today());return cm>0&&mins>=235&&mins<=(cm<960?1020:1215);}   /* pre-market 3:55 AM to after-hours end (8:15 PM; 5:00 PM on early-close days) */
  var stkLoaded=false, cacheUpd=0, JSONURL=BK.DATA+'prices.json';
  function cacheLabel(){if(!cacheUpd)return '';var st=mktOpen()&&(Date.now()-cacheUpd>30*60*1000);
    return 'Stocks: cached · updated '+ET.time(new Date(cacheUpd))+(st?' (stale)':'');}
  function tick(){if(document.hidden)return;if(!stkLoaded||mktOpen())loadStocks();}
  function loadStocks(){
    stkLoaded=true;
    var c=window.AbortController?new AbortController():null,t=c?setTimeout(function(){c.abort();},8000):0;
    fetch(JSONURL+'?t='+Date.now(),{cache:'no-store',signal:c?c.signal:undefined})
    .then(function(r){clearTimeout(t);if(!r.ok)throw new Error(r.status);return r.json();})
    .then(function(d){var u=Date.parse(d&&d.updated);if(u>0)cacheUpd=u;var S=(d&&d.stocks)||{};
      ['MSTR','STRC','TSLA','PLTR','SPY','QQQ','BRK.B','GLD'].forEach(function(T){var q=S[T];if(!q||typeof q.c!=='number'||!(q.c>0))return;
        var qt=q.t?q.t*1000:Date.now();if(qt>Date.now())qt=Date.now();if(['MSTR','STRC','TSLA','PLTR'].indexOf(T)>=0&&qt>lastTs)lastTs=qt;
        live[T]=q.c;prev[T]=(typeof q.pc==='number'&&q.pc>0)?q.pc:null;src[T]='cached '+(q.t?hhmm(q.t):'');});
      stkTime=cacheUpd?ET.time(new Date(cacheUpd)):null;
      var b=d&&d.btc;if(!live.BTC&&b&&b.usd>0){live.BTC=b.usd;btcChg=(typeof b.chg24h==='number')?b.chg24h:null;btcSrc='cached '+(b.src||'');btcTime=b.time?ET.time(new Date(b.time)):null;}
      else if(b&&btcChg===null&&typeof b.chg24h==='number')btcChg=b.chg24h; /* fallback (e.g. Coinbase) price arrived first: use the saved 24h move for % today */
      var me=d&&d.monthEnd;if(me&&me.date&&me.px&&me.px.BTC&&me.v>=3){MONTHEND[me.date]=me.px;ME_D=me.date;ME=me.px;} /* use the saved month-end session date, not a client-computed weekday */
      render();})
    .catch(function(){clearTimeout(t);/* keep last good prices; ASOF close if never loaded */render();});
  }
  function mp(v){return v.toLocaleString('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2});}
  function m(v){return v.toLocaleString('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0});}
  function pct(x){return '<span class="'+(x>=0?'up':'down')+'">'+(x>=0?'+':'')+(x*100).toFixed(2)+'%</span>';}
  /* Shared valuation: used by tracker cards AND the pulse strip */
  /* holdings + receivable actually held: at the month-end session in month-end mode, as of today (ET) in live mode */
  function held(p){return BK.at(p.key,mode==='me'?ME_D:todayET());}
  function compute(p){
    var q=held(p), v=q.cash, y=q.cash;
    Object.keys(q.h).forEach(function(a){var u=q.h[a],c=px(a);v+=u*c;
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
    ORDER.forEach(function(n){var p=PF.filter(function(x){return x.name===n;})[0],r=compute(p),ok=mode!=='me'&&BK.nav(p.key,PRIOR)>0;
      h+='<a class="pulse-card" href="#tracker" data-k="'+p.key+'"><span class="pulse-name">'+n+'</span><span class="pulse-val">'+m(r.v)+'</span><span class="pulse-chg">'+(ok?pct(r.v/BK.nav(p.key,PRIOR)-1)+' '+chgLabel():'—')+'</span></a>';});
    patch(g,h,'.pulse-card','k',['.pulse-val','.pulse-chg']);
    var stk=Object.keys(src).some(function(k){return src[k];});
    if(mode==='me'){document.getElementById('pulseNote').textContent=asOfLabel()+' · all prices at month-end close';return;}
    document.getElementById('pulseNote').textContent=asOfLabel()+' · BTC: '+(live.BTC?btcSrc+' (every 60s)'+(btcChg!==null?', move = since daily close':', move since daily close n/a'):'last close')+' · stocks: '+(stk?'cached (every 5 min), move vs prior close':'last close, move 0')+(cacheLabel()?' · '+cacheLabel():'');
  }
  /* Shared live state for the YTD chart: same compute() as tracker + pulse */
  var KEYS=['berkshire','hodlr','hf','saylor'];
  function liveState(){var o={sleeves:{},btc:live.BTC||null,spy:live.SPY||null,qqq:live.QQQ||null,brk:live['BRK.B']||null,mstr:live.MSTR||null,gold:live.GLD||null,btcTime:live.BTC?btcTime:null,
      stocksLive:['MSTR','STRC','TSLA','PLTR'].some(function(k){return !!src[k];}),stkTime:stkTime,label:asOfLabel(),meLabel:meLabel(),ts:lastTs,mode:mode,meDate:ME_D,me:ME};
    PF.forEach(function(p,i){o.sleeves[KEYS[i]]=compute(p).v;});return o;}
  window.PSLive={state:liveState};
  /* Update text/numbers in place, matching cards by their data key (not position). Rebuild only if the set of keys changes.
     Existing nodes keep focus, hover, open state and in-flight taps. */
  function patch(host,html,sel,key,parts){var t=document.createElement('div');t.innerHTML=html;var nw=t.querySelectorAll(sel),cur={},ks=[],nk=[];
    [].forEach.call(host.querySelectorAll(sel),function(c){cur[c.dataset[key]]=c;ks.push(c.dataset[key]);});
    [].forEach.call(nw,function(c){nk.push(c.dataset[key]);});
    if(ks.join('|')!==nk.join('|')){host.innerHTML=html;return;}
    [].forEach.call(nw,function(b){var a=cur[b.dataset[key]];parts.forEach(function(q){var x=a.querySelector(q),y=b.querySelector(q);if(x&&y&&x.innerHTML!==y.innerHTML)x.innerHTML=y.innerHTML;});});}
  var RM=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  function toggle(c){var i=c.dataset.i;open[i]=!open[i];c.classList.toggle('open',!!open[i]);c.setAttribute('aria-expanded',open[i]?'true':'false');
    if(open[i])setTimeout(function(){var r=c.getBoundingClientRect();if(r.bottom>window.innerHeight||r.top<0)c.scrollIntoView({behavior:RM?'auto':'smooth',block:'nearest'});},RM?0:180);}
  function render(){
    renderPulse();
    try{window.dispatchEvent(new CustomEvent('pslive',{detail:liveState()}));}catch(e){}
    var html='';
    PF.forEach(function(p,i){
      var v=compute(p).v, q=held(p), rows='';
      var ow={};p.start.split(' / ').forEach(function(x){var q=x.match(/\$(\d+)k (\w+)/);if(q)ow[q[2]]=+q[1];});
      Object.keys(q.h).forEach(function(a){var u=q.h[a],val=u*px(a);
        rows+='<tr><td>'+a+'</td><td>'+mp(px(a))+' <em>'+lbl(a)+'</em>'+'</td><td>'+m(val)+'</td><td>'+(ow[a]!=null?ow[a]+'%':'')+'</td><td>'+(val/v*100).toFixed(1)+'%</td></tr>';});
      rows+='<tr><td>STRC div receivable (cash)</td><td></td><td>'+m(q.cash)+'</td><td></td><td>'+(q.cash/v*100).toFixed(1)+'%</td></tr>';
      html+='<div class="pf-card'+(open[i]?' open':'')+'" data-i="'+i+'" role="button" tabindex="0" aria-expanded="'+(open[i]?'true':'false')+'"><div class="pf-head"><span class="pf-name">'+p.name+'</span><span class="pf-val">'+m(v)+'</span>'+
        '<span class="pf-sub">'+chgLabel()+' '+pct(v/BK.nav(p.key,PRIOR)-1)+' &middot; '+ytdLabel()+' '+pct(v/START-1)+'</span></div>'+
        '<table class="pf-tbl"><tr><th>Asset</th><th>Price</th><th>Value</th><th>Original</th><th>Live</th></tr>'+rows+'</table><p class="pf-start">Started with $100k on January 1st, 2026: '+p.start+'.</p><span class="pf-toggle" aria-hidden="true"><svg class="pf-chev" viewBox="0 0 16 16" width="16" height="16"><path d="M8 3v10M3 8h10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></span></div>';
    });
    patch(root.querySelector('.pf-grid'),html,'.pf-card','i',['.pf-val','.pf-sub','.pf-tbl','.pf-start']);
    root.querySelector('.pf-note').textContent=mode==='me'?asOfLabel()+'. All prices at the month-end close; switch to Live for current prices. Holdings computed from the ledger as of the date shown. YTD vs $100,000 start on January 1st, 2026. Tap a portfolio for holdings.':asOfLabel()+'. BTC: '+(live.BTC?btcSrc+', refreshed every 60s':'last close '+fmtD(ASOF))+'. '+(Object.keys(src).some(function(k){return src[k];})?(cacheLabel()||'Stocks: cached'):'Stocks: last close '+fmtD(ASOF))+'. Holdings computed from the ledger as of the date shown. YTD vs $100,000 start on January 1st, 2026. Tap a portfolio for holdings.';
  }
  root.addEventListener('click',function(e){
    var c=e.target.closest('.pf-card'); if(c)toggle(c);
  });
  root.addEventListener('keydown',function(e){
    var c=e.target.closest&&e.target.closest('.pf-card'); if(!c||(e.key!=='Enter'&&e.key!==' '))return;
    e.preventDefault(); toggle(c);
  });
  window.addEventListener('btcprice',function(e){live.BTC=e.detail.usd;btcChg=(typeof e.detail.chg==='number')?e.detail.chg:btcChg;btcTime=e.detail.time;btcSrc=e.detail.src||'CoinGecko';lastTs=Date.now();render();});
  document.querySelectorAll('#modeToggle .bench-btn').forEach(function(b){b.addEventListener('click',function(){mode=b.dataset.mode;
    document.querySelectorAll('#modeToggle .bench-btn').forEach(function(x){x.classList.toggle('active',x.dataset.mode===mode);});
    if(mode==='live')loadStocks();render();});});
  render(); tick(); setInterval(tick,5*60*1000);
  document.addEventListener('visibilitychange',function(){if(!document.hidden&&mktOpen())loadStocks();});
}).catch(function(e){var n=document.getElementById('pulseNote');if(n)n.textContent='Price history unavailable';}); })();
