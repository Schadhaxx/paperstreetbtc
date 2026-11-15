(function(){
  var URL='https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true';
  var $=function(i){return document.getElementById(i);};
  var box=$('btcLive'); if(!box) return;
  var fmt=function(n,c){return n.toLocaleString('en-US',{style:'currency',currency:c,maximumFractionDigits:0});};
  var timer;
  function schedule(ms){clearTimeout(timer);timer=setTimeout(load,ms);}
  /* Nov 15 r2: sequence counter — returning to the tab can start a second
     update while one is still running, and the older one can paint last.
     Each load() takes a sequence number; a result is painted only if no
     newer load has started since. */
  var seq=0;
  var FB='https://api.coinbase.com/v2/prices/BTC-USD/spot';
  /* CF-2: Cloudflare live-quote Worker — single configurable URL. */
  var WORKER='https://paperstreet-quotes.schadha08.workers.dev/';
  function tfetch(u,ms){var c=window.AbortController?new AbortController():null,t=c?setTimeout(function(){c.abort();},ms):0;
    return fetch(u,{cache:'no-store',signal:c?c.signal:undefined}).then(function(r){clearTimeout(t);if(!r.ok) throw new Error(r.status);return r.json();},function(e){clearTimeout(t);throw e;});}
  function getWorkerBtc(){return tfetch(WORKER,8000).then(function(d){var b=d&&d.btc;if(!b||typeof b.usd!=='number')throw new Error('bad data');return {usd:b.usd,usd_24h_change:typeof b.chg24h==='number'?b.chg24h:null,src:b.src||'Cloudflare'};});}
  /* Nov 15: the Worker can return a price with a null 24h change (both of
     its change sources failed). Keep the Worker price and fetch only the
     change from CoinGecko — do not re-fetch the price, do not treat the
     Worker answer as a failure. If CoinGecko also fails, keep the price
     and show no change (same as today's fallback). */
  function fillChgFromCoinGecko(w){return tfetch(URL,8000).then(function(d){var b=d&&d.bitcoin;if(b&&typeof b.usd_24h_change==='number')w.usd_24h_change=b.usd_24h_change;return w;},function(){return w;});}
  function getBtc(){return getWorkerBtc()
    .then(function(w){if(typeof w.usd_24h_change==='number')return w;return fillChgFromCoinGecko(w);})
    .catch(function(){return tfetch(URL,8000).then(function(d){var b=d&&d.bitcoin;if(!b||typeof b.usd!=='number')throw new Error('bad data');return b;});})
    .catch(function(){return tfetch(FB,8000).then(function(d){var a=d&&d.data&&parseFloat(d.data.amount);if(!(a>0))throw new Error('bad data');return {usd:a,usd_24h_change:null,src:'Coinbase'};});});}
  document.addEventListener('visibilitychange',function(){if(!document.hidden)schedule(0);});
  function load(){
    if(document.hidden){schedule(60000);return;}
    var my=++seq;
    getBtc()
    .then(function(b){
      if(my!==seq)return; /* a newer load started; ignore this stale result */
      $('btcUsd').textContent=fmt(b.usd,'USD');
      var hp=$('hdrPx'),hc=$('hdrChg'); if(hp){hp.textContent=fmt(b.usd,'USD');
        if(typeof b.usd_24h_change==='number'){var hcv=b.usd_24h_change;hc.textContent=(hcv>=0?'▲':'▼')+Math.abs(hcv).toFixed(1)+'%';hc.className='hdr-chg '+(hcv>=0?'up':'down');}
        /* Nov 15 r2: when a new poll has no change, clear the header change
           text — otherwise the old change stays on screen as if current. */
        else if(hc){hc.textContent='';hc.className='hdr-chg';}}
      var c=b.usd_24h_change, el=$('btcChg');
      if(typeof c!=='number'){el.textContent='24h change n/a';el.className='btc-live-chg';}
      if(typeof c==='number'){el.textContent=(c>=0?'▲ +':'▼ ')+c.toFixed(2)+'% 24h';el.className='btc-live-chg '+(c>=0?'up':'down');}
      $('btcTime').textContent='Updated '+ET.time();$('btcTime').title='Eastern Time ('+ET.abbr()+')';
      box.classList.remove('err'); window.dispatchEvent(new CustomEvent('btcprice',{detail:{usd:b.usd,chg:b.usd_24h_change,src:b.src||'CoinGecko',time:$('btcTime').textContent.replace('Updated ','')}})); schedule(60000);
    }).catch(function(){
      if(my!==seq)return; /* a newer load started; let it schedule the retry */
      box.classList.add('err');
      if(!/\$/.test($('btcUsd').textContent)) $('btcUsd').textContent='Price unavailable';
      $('btcTime').textContent='Retrying…'; schedule(90000);
    });
  }
  load();
})();
