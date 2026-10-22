/* Ledger engine: holdings/cash as of any date from PSLEDGER + the site's own daily closes (history.json). No stored NAVs or snapshots. */
(function(){
  var L=window.PSLEDGER, RAW='https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/';
  /* Local testing override: ?psdata=/some/local/dir/ (same-origin relative path only) */
  var q=(location.search.match(/[?&]psdata=([^&]+)/)||[])[1], DATA=RAW;
  if(q){q=decodeURIComponent(q);if(/^\/[\w\/.-]*\/$/.test(q)&&q.indexOf('..')<0)DATA=q;}
  var B={DATA:DATA,KEYS:['berkshire','hodlr','hf','saylor'],H:null,dates:[],last:null,ev:[]};
  function sessOnOrAfter(d){for(var i=0;i<B.dates.length;i++)if(B.dates[i]>=d)return B.dates[i];return null;}
  function build(){
    var C=B.H.closes; B.dates=Object.keys(C).sort(); B.last=B.dates[B.dates.length-1];
    B.ev=L.strc.filter(function(e){return e[1]>L.base;}).map(function(e){return {record:e[0],ex:e[1],pay:e[2],dps:e[3],payTd:sessOnOrAfter(e[2])};});
    B.tl={};
    B.KEYS.forEach(function(k){var s=L.sleeves[k],b=C[L.base],init={},hist=[],evs=[];
      Object.keys(s.w).forEach(function(a){init[a]=L.start*s.w[a]/b[a];});
      var cur=JSON.parse(JSON.stringify(init));
      function heldOn(d){var x=init;hist.forEach(function(st){if(st.d<=d)x=st.h;});return x;}
      /* events in pay order; STRC shares counted at the ex-date (STRC is never traded, computed generally anyway) */
      B.ev.slice().sort(function(x,y){return (x.payTd||'9')<(y.payTd||'9')?-1:1;}).forEach(function(e){
        var r={record:e.record,ex:e.ex,pay:e.pay,payTd:e.payTd,dps:e.dps,strc:heldOn(e.ex).STRC||0};r.cash=r.strc*e.dps;
        if(e.payTd){var p=C[e.payTd];r.buy={};Object.keys(s.div).forEach(function(a){var n=r.cash*s.div[a]/p[a];cur[a]=(cur[a]||0)+n;r.buy[a]={units:n,px:p[a]};});
          hist.push({d:e.payTd,h:JSON.parse(JSON.stringify(cur))});}
        evs.push(r);});
      B.tl[k]={init:init,hist:hist,evs:evs};});
  }
  /* holdings + receivable cash as of date d (ISO). Events whose pay session is not in history yet stay receivable. */
  B.at=function(k,d){var t=B.tl[k],h=t.init;t.hist.forEach(function(st){if(st.d<=d)h=st.h;});var cash=0;
    t.evs.forEach(function(e){if(e.ex<=d&&(!e.payTd||d<e.payTd))cash+=e.cash;});return {h:h,cash:cash};};
  B.events=function(k){return B.tl[k].evs;};
  B.close=function(d){return B.H.closes[d];};
  B.value=function(k,d,px){var s=B.at(k,d),v=s.cash;Object.keys(s.h).forEach(function(a){v+=s.h[a]*px(a);});return v;};
  B.nav=function(k,d){var c=B.H.closes[d];return B.value(k,d,function(a){return c[a];});};
  /* benchmarks: index (100 = base close). SPY/QQQ total return (distributions reinvested at the ex-date close). Gold = GLD ETF close (price return). */
  var BM={btc:'BTC',spy:'SPY',qqq:'QQQ',brk:'BRK.B',mstr:'MSTR',gold:'GLD'};
  B.BM=BM;
  B.bench=function(k,d){var C=B.H.closes,b=C[L.base][BM[k]];
    if(k==='spy'||k==='qqq'){var sh=1/b,dv=(B.H.divs||{})[BM[k]]||{};B.dates.forEach(function(x){if(x>L.base&&x<=d&&dv[x])sh+=sh*dv[x]/C[x][BM[k]];});return 100*sh*C[d][BM[k]];}
    return 100*C[d][BM[k]]/b;};
  /* chart points: base, last session of each completed month, latest close */
  B.points=function(){var out=[L.base],lm=B.last.slice(0,7);
    for(var i=1;i<B.dates.length;i++){var d=B.dates[i],nx=B.dates[i+1];if(d.slice(0,7)<lm&&(!nx||nx.slice(0,7)!==d.slice(0,7)))out.push(d);}
    if(out[out.length-1]!==B.last)out.push(B.last);return out;};
  B.ready=fetch(DATA+'history.json?t='+Date.now(),{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();})
    .then(function(h){B.H=h;build();return B;});
  window.PSBook=B;
})();
