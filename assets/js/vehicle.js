/* Vehicle toggle, Day 3 — ONE shared toggle component.
   State lives in sessionStorage ('psVehicle') so it is session-only by
   default (approved Day 1) and shared across pages in the same tab, and
   every toggle on the page (tracker toggle, BTC chart popover toggle)
   is driven by the same 'psvehicle' window event.
   - Default: Spot BTC. Spot BTC remains the hurdle/benchmark everywhere.
   - IBIT/FBTC buttons stay disabled until the vehicle data file has
     loaded, so a vehicle can never be selected with no data behind it.
   - Until the prices.yml live-quote change lands, ETF prices are the
     latest vehicle closes from vehicle-daily.json — never a live spot
     price dressed up as an ETF price. The mode label says so.
   - If vehicle-daily.json fails to load, the toggle falls back to Spot
     and the ETF buttons stay disabled with an explanatory label. It
     never silently shows spot values while claiming ETF mode. */
(function(){
  var KEY='psVehicle', vehicle='SPOT', loaded=false, failed=false;
  try{var s=sessionStorage.getItem(KEY);if(s==='IBIT'||s==='FBTC')vehicle=s;}catch(e){}
  function dispatch(){try{window.dispatchEvent(new CustomEvent('psvehicle',{detail:{vehicle:vehicle,loaded:loaded,failed:failed}}));}catch(e){}}
  function modeText(){
    if(failed)return 'Vehicle data unavailable — showing Spot BTC';
    if(vehicle==='SPOT')return 'Spot BTC — the hurdle';
    return 'You are in '+vehicle+' mode · ETF priced at its latest close (live ETF quotes arrive with the prices.yml change)';
  }
  function updateLabel(){var el=document.getElementById('vehicleMode');if(el)el.textContent=modeText();}
  function syncButtons(){
    document.querySelectorAll('[data-veh]').forEach(function(b){
      var on=b.dataset.veh===vehicle;
      b.classList.toggle('on',on);b.classList.toggle('active',on);
      b.setAttribute('aria-pressed',on?'true':'false');
      if(b.dataset.veh!=='SPOT'){b.disabled=!loaded;if(!loaded)b.title=failed?'Vehicle data unavailable':'Loading vehicle data…';else b.title='';}
    });
    updateLabel();
  }
  function set(v){
    if(v!=='SPOT'&&v!=='IBIT'&&v!=='FBTC')return;
    if(v!=='SPOT'&&!loaded)return; /* no data yet: refuse, do not fall back silently */
    vehicle=v;
    try{sessionStorage.setItem(KEY,v);}catch(e){}
    syncButtons();dispatch();
  }
  window.PSVehicle={get:function(){return vehicle;},loaded:function(){return loaded;},failed:function(){return failed;},set:set,sync:syncButtons};
  function buildUI(){
    var pill=document.getElementById('btcLive');if(!pill||document.getElementById('vehicleToggle'))return;
    var wrap=document.createElement('div');wrap.className='vehicle-toggle';wrap.id='vehicleToggle';
    wrap.setAttribute('role','group');wrap.setAttribute('aria-label','Bitcoin vehicle');
    wrap.innerHTML='<span class="bench-label">Bitcoin vehicle</span>'+
      '<button type="button" class="bench-btn" data-veh="SPOT">Spot BTC</button>'+
      '<button type="button" class="bench-btn" data-veh="IBIT" disabled title="Loading vehicle data…">IBIT</button>'+
      '<button type="button" class="bench-btn" data-veh="FBTC" disabled title="Loading vehicle data…">FBTC</button>'+
      '<span class="vehicle-mode" id="vehicleMode" aria-live="polite"></span>';
    var anchor=document.getElementById('pfLive');
    if(anchor)anchor.parentNode.insertBefore(wrap,anchor);else pill.parentNode.insertBefore(wrap,pill.nextSibling);
    wrap.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-veh]');if(!b||b.disabled)return;set(b.dataset.veh);});
    syncButtons();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',buildUI);else buildUI();
  if(window.PSBook){
    PSBook.ready.then(function(BK){
      return BK.loadVehicle().then(function(){
        loaded=true;failed=false;syncButtons();dispatch();
      }).catch(function(){
        /* Vehicle file unavailable: stay in Spot, ETF buttons disabled. */
        failed=true;loaded=false;vehicle='SPOT';
        try{sessionStorage.setItem(KEY,'SPOT');}catch(e){}
        syncButtons();dispatch();
      });
    }).catch(function(){failed=true;syncButtons();dispatch();});
  }else{
    syncButtons();
  }
})();
