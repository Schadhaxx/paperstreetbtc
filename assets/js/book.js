/* Ledger engine: holdings/cash as of any date from PSLEDGER + the site's own daily closes (history.json). No stored NAVs or snapshots. */
(function(){
  var L=window.PSLEDGER, RAW='https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/';
  /* Local testing override: ?psdata=/some/local/dir/ (same-origin relative path only) */
  var q=(location.search.match(/[?&]psdata=([^&]+)/)||[])[1], DATA=RAW;
  if(q){q=decodeURIComponent(q);if(/^\/[\w\/.-]*\/$/.test(q)&&q.indexOf('..')<0)DATA=q;}
  var B={DATA:DATA,KEYS:['berkshire','hodlr','hf','saylor'],H:null,dates:[],last:null,ev:[]};
  function sessOnOrAfter(d){for(var i=0;i<B.dates.length;i++)if(B.dates[i]>=d)return B.dates[i];return null;}
  /* Vehicle toggle, Day 2: one engine, parameterised by price series.
     priceAt(asset, isoDate) returns the price of that asset on that session.
     Spot: history.json closes for every asset (unchanged behaviour).
     ETF (IBIT/FBTC): BTC is priced from vehicle-daily.json, every other asset
     from history.json. Crucially the BTC slice is RE-BASED in vehicle units:
     init BTC units = $weight / vehicle base close, NOT spot units x vehicle
     price. Keeping spot units and swapping the price would collapse the
     $100,000 start (e.g. Berkshire's BTC slice would read ~$24k at base
     instead of $40k), breaking the weights/start rule. Re-basing preserves
     weights and the $100k start exactly, and the sleeve then tracks the
     vehicle return. Dividend buys follow the same rule: STRC cash buys the
     selected vehicle at the pay session's vehicle close in ETF mode
     (locked 29 Oct 2026), spot at the spot close in spot mode. */
  function buildTimeline(priceAt){
    var tl={};
    B.KEYS.forEach(function(k){var s=L.sleeves[k],init={},hist=[],evs=[];
      Object.keys(s.w).forEach(function(a){init[a]=L.start*s.w[a]/priceAt(a,L.base);});
      var cur=JSON.parse(JSON.stringify(init));
      function heldOn(d){var x=init;hist.forEach(function(st){if(st.d<=d)x=st.h;});return x;}
      /* events in pay order; STRC shares counted at the ex-date (STRC is never traded, computed generally anyway) */
      B.ev.slice().sort(function(x,y){return (x.payTd||'9')<(y.payTd||'9')?-1:1;}).forEach(function(e){
        var r={record:e.record,ex:e.ex,pay:e.pay,payTd:e.payTd,dps:e.dps,strc:heldOn(e.ex).STRC||0};r.cash=r.strc*e.dps;
        if(e.payTd){r.buy={};Object.keys(s.div).forEach(function(a){var px=priceAt(a,e.payTd),n=r.cash*s.div[a]/px;cur[a]=(cur[a]||0)+n;r.buy[a]={units:n,px:px};});
          hist.push({d:e.payTd,h:JSON.parse(JSON.stringify(cur))});}
        evs.push(r);});
      tl[k]={init:init,hist:hist,evs:evs};});
    return tl;
  }
  function build(){
    var C=B.H.closes; B.dates=Object.keys(C).sort(); B.last=B.dates[B.dates.length-1];
    B.ev=L.strc.filter(function(e){return e[1]>L.base;}).map(function(e){return {record:e[0],ex:e[1],pay:e[2],dps:e[3],payTd:sessOnOrAfter(e[2])};});
    B.tl=buildTimeline(function(a,d){return C[d][a];});
    B.tlV={SPOT:B.tl}; B.vehicleMaps={}; B.vehicleDates={};
  }
  /* Load vehicle-daily.json (parsed object) and build one timeline per vehicle.
     Throws if a vehicle series does not cover every history session, so a
     partial series can never silently value a session at the wrong price. */
  B.loadVehicleData=function(vd){
    if(!B.H)throw new Error('history not loaded');
    ['IBIT','FBTC'].forEach(function(v){
      var m={};(vd.vehicles[v]||[]).forEach(function(p){m[p[0]]=p[1];});
      B.dates.forEach(function(d){if(!(m[d]>0))throw new Error('vehicle '+v+' missing session '+d);});
      B.vehicleMaps[v]=m; B.vehicleDates[v]=Object.keys(m).sort();
      B.tlV[v]=buildTimeline(function(a,d){return a==='BTC'?m[d]:B.H.closes[d][a];});
    });
    B.vehicleData=vd; return B.tlV;
  };
  /* Browser load of the static vehicle file (main-branch asset, same origin).
     Day 3 wires this in; Day 2 tests call loadVehicleData directly. */
  B.loadVehicle=function(){return fetch('assets/data/vehicle-daily.json',{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(function(j){return B.loadVehicleData(j);});};
  /* Last vehicle close on or before d: the weekend/holiday flat rule — an ETF
     part is flat at the Friday close through the weekend, spot keeps moving. */
  B.vehiclePriceOnOrBefore=function(v,d){var ds=B.vehicleDates[v],out=null;if(!ds)throw new Error('vehicle not loaded: '+v);
    for(var i=0;i<ds.length;i++){if(ds[i]<=d)out=B.vehicleMaps[v][ds[i]];else break;}return out;};
  function atFrom(t,k,d){var x=t[k],h=x.init;x.hist.forEach(function(st){if(st.d<=d)h=st.h;});var cash=0;
    x.evs.forEach(function(e){if(e.ex<=d&&(!e.payTd||d<e.payTd))cash+=e.cash;});return {h:h,cash:cash};}
  function valueFrom(t,k,d,px){var s=atFrom(t,k,d),v=s.cash;Object.keys(s.h).forEach(function(a){v+=s.h[a]*px(a);});return v;}
  /* holdings + receivable cash as of date d (ISO). Events whose pay session is not in history yet stay receivable. */
  B.at=function(k,d){return atFrom(B.tl,k,d);};
  /* Vehicle-aware holdings: vehicle 'SPOT' (default) is the unchanged book.
     IBIT/FBTC require loadVehicleData first; Saylor Moon has no BTC slice,
     so its vehicle timeline is identical to spot by construction. */
  B.atV=function(k,d,vehicle){vehicle=vehicle||'SPOT';var t=vehicle==='SPOT'?B.tl:B.tlV[vehicle];if(!t)throw new Error('vehicle not loaded: '+vehicle);return atFrom(t,k,d);};
  B.events=function(k){return B.tl[k].evs;};
  B.eventsV=function(k,vehicle){vehicle=vehicle||'SPOT';var t=vehicle==='SPOT'?B.tl:B.tlV[vehicle];if(!t)throw new Error('vehicle not loaded: '+vehicle);return t[k].evs;};
  B.close=function(d){return B.H.closes[d];};
  B.value=function(k,d,px){return valueFrom(B.tl,k,d,px);};
  B.nav=function(k,d){var c=B.H.closes[d];return B.value(k,d,function(a){return c[a];});};
  /* Vehicle NAV at a session close. pxFn, if given, supplies live prices
     (for BTC: the live vehicle quote in ETF mode, the live spot price in
     spot mode); without it, the session close is used for every asset. */
  B.navV=function(k,d,vehicle,pxFn){vehicle=vehicle||'SPOT';
    if(vehicle==='SPOT')return pxFn?B.value(k,d,pxFn):B.nav(k,d);
    var t=B.tlV[vehicle];if(!t)throw new Error('vehicle not loaded: '+vehicle);
    if(pxFn)return valueFrom(t,k,d,pxFn);
    var c=B.H.closes[d],m=B.vehicleMaps[vehicle];
    return valueFrom(t,k,d,function(a){return a==='BTC'?m[d]:c[a];});};
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
