(function(){
  var URL='https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true';
  var $=function(i){return document.getElementById(i);};
  var box=$('btcLive'); if(!box) return;
  var fmt=function(n,c){return n.toLocaleString('en-US',{style:'currency',currency:c,maximumFractionDigits:0});};
  var timer;
  function schedule(ms){clearTimeout(timer);timer=setTimeout(load,ms);}
  var FB='https://api.coinbase.com/v2/prices/BTC-USD/spot';
  function tfetch(u,ms){var c=window.AbortController?new AbortController():null,t=c?setTimeout(function(){c.abort();},ms):0;
    return fetch(u,{cache:'no-store',signal:c?c.signal:undefined}).then(function(r){clearTimeout(t);if(!r.ok) throw new Error(r.status);return r.json();},function(e){clearTimeout(t);throw e;});}
  function getBtc(){return tfetch(URL,8000).then(function(d){var b=d&&d.bitcoin;if(!b||typeof b.usd!=='number')throw new Error('bad data');return b;})
    .catch(function(){return tfetch(FB,8000).then(function(d){var a=d&&d.data&&parseFloat(d.data.amount);if(!(a>0))throw new Error('bad data');return {usd:a,usd_24h_change:null,src:'Coinbase'};});});}
  document.addEventListener('visibilitychange',function(){if(!document.hidden)schedule(0);});
  function load(){
    if(document.hidden){schedule(60000);return;}
    getBtc()
    .then(function(b){
      $('btcUsd').textContent=fmt(b.usd,'USD');
      var hp=$('hdrPx'),hc=$('hdrChg'); if(hp){hp.textContent=fmt(b.usd,'USD');
        if(typeof b.usd_24h_change==='number'){var hcv=b.usd_24h_change;hc.textContent=(hcv>=0?'▲':'▼')+Math.abs(hcv).toFixed(1)+'%';hc.className='hdr-chg '+(hcv>=0?'up':'down');}}
      var c=b.usd_24h_change, el=$('btcChg');
      if(typeof c!=='number'){el.textContent='24h change n/a';el.className='btc-live-chg';}
      if(typeof c==='number'){el.textContent=(c>=0?'▲ +':'▼ ')+c.toFixed(2)+'% 24h';el.className='btc-live-chg '+(c>=0?'up':'down');}
      $('btcTime').textContent='Updated '+ET.time();$('btcTime').title='Eastern Time ('+ET.abbr()+')';
      box.classList.remove('err'); window.dispatchEvent(new CustomEvent('btcprice',{detail:{usd:b.usd,chg:b.usd_24h_change,src:b.src||'CoinGecko',time:$('btcTime').textContent.replace('Updated ','')}})); schedule(60000);
    }).catch(function(){
      box.classList.add('err');
      if(!/\$/.test($('btcUsd').textContent)) $('btcUsd').textContent='Price unavailable';
      $('btcTime').textContent='Retrying…'; schedule(90000);
    });
  }
  load();
})();
