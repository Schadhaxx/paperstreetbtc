/* Stage 3 light event analytics (27 Nov 2026): counts seven key actions
   (Desk open, Portfolio Lab model pick, chart range switch, live BTC chart
   open, X follow click, screener use, Compare use) via POST /ev on the
   paperstreet-quotes Worker, which writes them to Workers Analytics Engine.
   Counts only: event name + page + the ?src= tag. No cookies, no personal
   data, no dashboard. Fire-and-forget: a failed send is invisible.
   Respects the /me/ opt-out flag (localStorage 'ps-no-count' = '1', set by
   the hidden /me/ page in Stage 2) and skips automated browsers. The ?src=
   tag is kept for the tab session (sessionStorage 'ps-src'). Loaded with
   defer on the 16 public pages, right after chart-theme.js. */
(function(){
  try{
    var EV_URL='https://paperstreet-quotes.schadha08.workers.dev/ev';
    var EVENTS={desk_open:1,lab_model:1,range_switch:1,btc_chart_open:1,xfollow:1,screener_use:1,compare_use:1};
    var OPT_KEY='ps-no-count', SRC_KEY='ps-src';
    var SRC_RE=/^[A-Za-z0-9._-]{1,40}$/;
    // Opt-out (/me/ page, Stage 2) or automated browser: send nothing.
    var optedOut=false;
    try{ optedOut=window.localStorage && window.localStorage.getItem(OPT_KEY)==='1'; }catch(e){ optedOut=false; }
    var ua=(navigator.userAgent||'');
    var automated=!!navigator.webdriver || /HeadlessChrome|PhantomJS|Headless/i.test(ua);
    if(optedOut||automated) return;
    // ?src= tag: capture on arrival, keep for the tab session.
    var src='';
    try{
      var q=null;
      if(window.URLSearchParams) q=new URLSearchParams(location.search).get('src');
      if(q && SRC_RE.test(q)){ src=q; sessionStorage.setItem(SRC_KEY,q); }
      else{
        src=sessionStorage.getItem(SRC_KEY)||'';
        if(!SRC_RE.test(src)) src='';
      }
    }catch(e){ src=''; }
    var sent=0, lastAt={};
    // key distinguishes the action (e.g. which range pill), so two
    // different actions in quick succession both count, while rapid
    // repeats of the SAME action (double-click, one keystroke per
    // input event while typing) collapse to one.
    function send(ev,key){
      if(!EVENTS[ev]) return;
      if(sent>=100) return; // safety cap per page load
      var now=Date.now();
      var k=ev+'|'+(key||'');
      if(lastAt[k] && now-lastAt[k]<500) return; // dedupe rapid repeats
      lastAt[k]=now; sent++;
      var body;
      try{ body=JSON.stringify({event:ev,page:location.pathname,src:src}); }catch(e){ return; }
      try{
        if(navigator.sendBeacon){
          var blob=new Blob([body],{type:'text/plain'});
          if(navigator.sendBeacon(EV_URL,blob)) return;
        }
      }catch(e){ /* fall through to fetch */ }
      try{
        fetch(EV_URL,{method:'POST',mode:'cors',credentials:'omit',keepalive:true,headers:{'Content-Type':'text/plain'},body:body}).catch(function(){});
      }catch(e){ /* fire-and-forget: never throw */ }
    }
    window.__psEv=send;
    // Page-open events.
    function pageOpens(){
      var p=location.pathname;
      if(p==='/screener.html') send('desk_open','load');
      if(p==='/clock/'||p==='/clock/index.html') send('btc_chart_open','load');
    }
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',pageOpens);
    else pageOpens();
    // Delegated clicks (elements may be added late, e.g. the lazy BTC panel
    // range pills and the Compare series/range buttons, both built by JS).
    document.addEventListener('click',function(e){
      var t=e.target&&e.target.closest?e.target.closest('a,button,[data-filter],[data-sort]'):null;
      if(!t) return;
      // X follow button / link (homepage): any link to the X profile.
      var a=t.closest('a[href^="https://x.com/PaperstreetBTC"]');
      if(a){ send('xfollow','x'); return; }
      if(t.id==='hdrTick'){ send('btc_chart_open','pill'); return; }
      if(t.closest('#bcRgs') && t.getAttribute('data-r')){ send('range_switch','rg:'+t.getAttribute('data-r')); return; }
      if(t.closest('#pvSeries') && t.getAttribute('data-k')){ send('compare_use','sp:'+t.getAttribute('data-k')); return; }
      if(t.closest('#pvRange') && t.getAttribute('data-r')){ send('compare_use','rp:'+t.getAttribute('data-r')); return; }
      if(t.getAttribute('data-filter')){ send('screener_use','f:'+t.getAttribute('data-filter')); return; }
      if(t.getAttribute('data-sort')){ send('screener_use','s:'+t.getAttribute('data-sort')); return; }
    });
    // Portfolio Lab model pick: the sleeve select on /compare/.
    document.addEventListener('change',function(e){
      var t=e.target;
      if(t && t.id==='pvS'){ send('lab_model','pvs'); }
    });
    // Screener search typing.
    document.addEventListener('input',function(e){
      var t=e.target;
      if(t && t.id==='screener-search'){ send('screener_use','search'); }
    });
  }catch(e){ /* never throw, never block the page */ }
})();
