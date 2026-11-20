/* TA Stage 1 (20 Nov 2026): chart-type pill + menu, TA pill, floating panel,
   RSI strip container. Loaded lazily from btcchart-panel.js (loadTA), own pin.
   All overlays are OFF by default and NOTHING IS DRAWN YET — the toggles only
   set state (saved per device) and the after-draw hook keeps the strip in
   sync. Drawing lands in Stage 2. No Chart.js references anywhere. */
(function(){
if(window.__BTTA)return;
var API=window.__BCTA;
if(!API)return;
var LSKEY='ps-ta-v1';
var DEF={tl:false,bb:false,ma:false,maKind:'sma',maPer:50,rsi:false,rsiCol:false,last1DSize:'1h'};
var S={};
function loadS(){try{var raw=window.localStorage.getItem(LSKEY);if(raw){var o=JSON.parse(raw);for(var k in DEF)S[k]=(k in o)?o[k]:DEF[k];return;}}catch(e){}for(var k2 in DEF)S[k2]=DEF[k2];}
function saveS(){try{window.localStorage.setItem(LSKEY,JSON.stringify(S));}catch(e){}}
loadS();
var CHEV='<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2 3.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
var COL={tl:'#22c55e',bb:'#a78bfa',ma:'#f472b6',rsi:'#a78bfa'};
var dlg=null,typBtn=null,taBtn=null,rsiEl=null,menuEl=null,panelEl=null,inited=false;
var menuOpen=false,panelOpen=false;

function $(s,r){return (r||document).querySelector(s);}
function el(id){return document.getElementById(id);}
function isPriceMode(){try{return document.documentElement.classList.contains('v4-fs-price');}catch(e){return false;}}
function stageEl(){try{var st=API.stage();if(st)return st;}catch(e){}return dlg;}
/* The floating layer (menu / panel) lives in the stage on the clock page and
   in the dialog in the popover, so it renders inside the Fullscreen-API
   element in both full-screen modes. Never body. */
function floatParent(){return API.inline()?stageEl():dlg;}
function nOn(){return (S.tl?1:0)+(S.bb?1:0)+(S.ma?1:0)+(S.rsi?1:0);}

/* ---------- positioning: place a float under an anchor, clamped inside its
   offsetParent (the stage or the dialog), with a capped height ---------- */
function placeFloat(anchor,fl){
  var op=fl.offsetParent||document.body;
  var ar=anchor.getBoundingClientRect(),pr=op.getBoundingClientRect();
  var ox=op.clientLeft||0,oy=op.clientTop||0;
  var pw=fl.offsetWidth,ph=fl.offsetHeight;
  var left=Math.min(ar.right-pr.left-ox,pr.right-pr.left-ox)-pw;
  if(left<0)left=0;
  var top=(ar.bottom-pr.top-oy)+6;
  fl.style.left=left+'px';fl.style.top=top+'px';
  var maxH=window.innerHeight-6-(ar.bottom+6);
  if(top+ph>window.innerHeight-6&&maxH>120){fl.style.maxHeight=maxH+'px';fl.style.overflowY='auto';}
  else{fl.style.maxHeight='';fl.style.overflowY='';}
}

/* ---------- TA pill (count badge) + RSI strip ---------- */
function syncPill(){
  if(!taBtn)return;
  var n=nOn();
  taBtn.classList.toggle('act',n>0);
  taBtn.innerHTML='<span>TA</span>'+(n?'<i class="ta-n">'+n+'</i>':CHEV);
  taBtn.setAttribute('aria-label','Technical analysis'+(n?', '+n+' on':''));
}
function syncRsi(){
  if(!rsiEl||!dlg)return;
  rsiEl.hidden=!S.rsi;
  dlg.classList.toggle('ta-rsi-on',!!S.rsi);
  if(S.rsi){
    rsiEl.classList.toggle('col',!!S.rsiCol);
    var t=rsiEl.querySelector('.ta-rsi-t');
    if(t)t.setAttribute('aria-expanded',S.rsiCol?'false':'true');
  }
}

/* ---------- chart-type menu ---------- */
function allowedSizes(rng){
  if(rng==='1D')return ['1h','4h'];
  if(rng==='1W')return ['daily','4h'];
  if(rng==='1M')return ['weekly','daily'];
  if(rng==='3M'||rng==='6M'||rng==='YTD'||rng==='1Y')return ['monthly','weekly'];
  return [];
}
function sizeLabel(sz){
  return sz==='1h'?'1H candles':sz==='4h'?'4H candles':sz==='daily'?'Daily':sz==='weekly'?'Weekly':'Monthly';
}
function typeLabel(st){
  if(st.rng==='1D')return st.CT==='line'?'Line':(st.CT==='1h'?'1H candles':'4H candles');
  if(st.RGCT!=='candles')return 'Line';
  return st.RGGRAN==='4h'?'4H candles':'Candles \u00b7 '+sizeLabel(st.RGGRAN);
}
function clickHidden(sel){
  if(!dlg)return false;
  var b=dlg.querySelector(sel);
  if(!b)return false;
  b.click();
  return true;
}
function pickType(kind){
  /* Drives the hidden buttons, so picking behaves exactly like tapping them. */
  var st=API.state();
  if(kind==='line'){
    if(st.rng==='1D')clickHidden('#bcCt button[data-ct="line"]');
    else clickHidden('#bcCg button[data-cg="line"]');
  }else{
    if(st.rng==='1D')clickHidden('#bcCt button[data-ct="'+S.last1DSize+'"]');
    else clickHidden('#bcCg button[data-cg="candles"]');
  }
}
function pickSize(sz){
  var st=API.state();
  if(st.rng==='1D'){
    S.last1DSize=sz;saveS();
    clickHidden('#bcCt button[data-ct="'+sz+'"]');
  }else{
    clickHidden('#bcCg button[data-cg="candles"]');
    clickHidden('#bcCg button[data-cggran="'+sz+'"]');
  }
}
function buildMenu(){
  if(menuEl)return menuEl;
  var m=document.createElement('div');
  m.className='ta-menu';m.setAttribute('role','menu');m.setAttribute('aria-label','Chart type');
  m.hidden=true;
  floatParent().appendChild(m);
  menuEl=m;
  return m;
}
function openMenu(){
  if(isPriceMode())return;
  var st=API.state();
  if(/^(5Y|10Y|Max)$/.test(st.rng))return; /* no menu on long ranges: Line only */
  var m=buildMenu();
  var sizes=allowedSizes(st.rng);
  var isCandles=st.rng==='1D'?st.CT!=='line':st.RGCT==='candles';
  var curSize=st.rng==='1D'?st.CT:st.RGGRAN;
  var h='<div class="ta-mh">Type</div>';
  h+='<button type="button" role="menuitem" class="ta-mo'+(!isCandles?' on':'')+'" data-ta-pick="line">Line<span class="ta-ck">\u2713</span></button>';
  h+='<button type="button" role="menuitem" class="ta-mo'+(isCandles?' on':'')+'" data-ta-pick="candles">Candles<span class="ta-ck">\u2713</span></button>';
  if(sizes.length){
    h+='<div class="ta-md"></div><div class="ta-mh">Size</div>';
    sizes.forEach(function(sz){
      h+='<button type="button" role="menuitem" class="ta-mo'+(isCandles&&curSize===sz?' on':'')+'" data-ta-size="'+sz+'">'+sizeLabel(sz)+'<span class="ta-ck">\u2713</span></button>';
    });
  }
  m.innerHTML=h;
  m.hidden=false;menuOpen=true;
  typBtn.classList.add('open');typBtn.setAttribute('aria-expanded','true');
  placeFloat(typBtn,m);
  var first=m.querySelector('.ta-mo.on')||m.querySelector('.ta-mo');
  if(first)first.focus();
}
function closeMenu(focusTyp){
  if(!menuOpen)return;
  menuOpen=false;
  if(menuEl)menuEl.hidden=true;
  if(typBtn){typBtn.classList.remove('open');typBtn.setAttribute('aria-expanded','false');}
  if(focusTyp&&typBtn)typBtn.focus();
}

/* ---------- floating TA panel ---------- */
function swRow(key,label,sub,col){
  return '<div class="ta-it"><div class="nm"><span><i style="background:'+col+'"></i>'+label+'</span><small>'+sub+'</small></div>'
    +'<button type="button" class="ta-sw'+(S[key]?' on':'')+'" role="switch" aria-checked="'+(!!S[key])+'" data-ta-key="'+key+'" aria-label="'+label+'"></button></div>';
}
function buildPanel(){
  if(panelEl)return panelEl;
  var p=document.createElement('div');
  p.className='ta-panel';p.setAttribute('role','dialog');p.setAttribute('aria-label','Technical analysis');
  p.hidden=true;
  floatParent().appendChild(p);
  panelEl=p;
  return p;
}
function renderPanel(){
  var p=buildPanel();
  var seg=function(opts,cur){return '<span class="ta-seg">'+opts.map(function(o){return '<button type="button" class="'+(String(o).toLowerCase()===String(cur).toLowerCase()?'on':'')+'" data-ta-seg="'+o+'">'+o+'</button>';}).join('')+'</span>';};
  p.innerHTML='<div class="ta-ph"><b>Technical analysis</b><button type="button" data-ta-clear>Clear all</button></div>'
    +swRow('tl','Smart Trendlines','auto support / resistance',COL.tl)
    +swRow('bb','Bollinger Bands','20 \u00b7 2\u03c3',COL.bb)
    +swRow('ma','Moving average','one at a time',COL.ma)
    +'<div class="ta-ma'+(S.ma?'':' off')+'">'+seg(['SMA','EMA'],S.maKind)+seg([20,50,200],S.maPer)+'</div>'
    +swRow('rsi','RSI','14 \u00b7 strip under chart',COL.rsi);
  syncPanel();
}
/* Targeted sync (no innerHTML replacement): re-rendering the panel would
   detach the very button being clicked, and the document outside-click
   handler would then read it as an outside click and close the panel. */
function syncPanel(){
  if(!panelEl)return;
  var sws=panelEl.querySelectorAll('[data-ta-key]');
  for(var i=0;i<sws.length;i++){var k=sws[i].getAttribute('data-ta-key');sws[i].classList.toggle('on',!!S[k]);sws[i].setAttribute('aria-checked',S[k]?'true':'false');}
  var ma=panelEl.querySelector('.ta-ma');
  if(ma)ma.classList.toggle('off',!S.ma);
  var segs=panelEl.querySelectorAll('[data-ta-seg]');
  for(var j=0;j<segs.length;j++){var v=segs[j].getAttribute('data-ta-seg');var on=(v==='SMA'||v==='EMA')?S.maKind===v.toLowerCase():S.maPer===parseInt(v,10);segs[j].classList.toggle('on',on);}
}
function openPanel(){
  if(isPriceMode())return;
  renderPanel();
  panelEl.hidden=false;panelOpen=true;
  taBtn.classList.add('open');taBtn.setAttribute('aria-expanded','true');
  placeFloat(taBtn,panelEl);
  var first=panelEl.querySelector('.ta-sw');
  if(first)first.focus();
}
function closePanel(focusPill){
  if(!panelOpen)return;
  panelOpen=false;
  if(panelEl)panelEl.hidden=true;
  if(taBtn){taBtn.classList.remove('open');taBtn.setAttribute('aria-expanded','false');}
  if(focusPill&&taBtn)taBtn.focus();
}
function setToggle(key,val){
  S[key]=!!val;saveS();
  syncPanel();
  syncPill();syncRsi();
}

/* ---------- overlap check (Playwright / handback) ---------- */
function rect(el){
  if(!el)return null;
  var r=el.getBoundingClientRect();
  if(!r.width||!r.height)return null;
  return {x:r.left,y:r.top,w:r.width,h:r.height,r:r.right,b:r.bottom};
}
function union(a,b){
  if(!a)return b;if(!b)return a;
  var x=Math.min(a.x,b.x),y=Math.min(a.y,b.y),r=Math.max(a.r,b.r),bb=Math.max(a.b,b.b);
  return {x:x,y:y,w:r-x,h:bb-y,r:r,b:bb};
}
function visible(el){
  if(!el)return false;
  var r=el.getBoundingClientRect();
  if(!r.width||!r.height)return false;
  var pn=panelEl,mn=menuEl,pd=pn&&pn.style.display,md=mn&&mn.style.display;
  if(pn)pn.style.display='none';if(mn)mn.style.display='none';
  var pts=[[.5,.5],[.15,.5],[.85,.5]],hit=false;
  pts.forEach(function(q){
    var x=r.left+r.width*q[0],y=r.top+r.height*q[1];
    if(x<0||y<0||x>innerWidth||y>innerHeight)return;
    var h=document.elementFromPoint(x,y);
    if(h&&(h===el||el.contains(h)))hit=true;
  });
  if(pn)pn.style.display=pd||'';if(mn)mn.style.display=md||'';
  return hit;
}
function overlap(a,b){
  if(!a||!b)return false;
  return a.x<b.r&&b.x<a.r&&a.y<b.b&&b.y<a.b;
}
window.__taRects=function(){
  var pnEl=(panelEl&&!panelEl.hidden)?panelEl:null;
  var panelVisible=false;
  if(pnEl){var q=pnEl.getBoundingClientRect(),h=document.elementFromPoint(q.left+q.width/2,q.top+q.height/2);panelVisible=!!(h&&pnEl.contains(h));}
  var mnEl=(menuEl&&!menuEl.hidden)?menuEl:null;
  var menuVisible=false;
  if(mnEl){var q2=mnEl.getBoundingClientRect(),h2=document.elementFromPoint(q2.left+q2.width/2,q2.top+q2.height/2);menuVisible=!!(h2&&mnEl.contains(h2));}
  var prot={
    'BTC price':union(rect(el('price')),rect($('.v4-chg')))||rect(dlg?dlg.querySelector('.bc-px'):null),
    'Keep screen on':rect(el('wakeBtn')),
    'Exit full screen':rect($('.v4-fs-exit')),
    'Light/Dark pill':rect(el('psThemePill')),
    'Full-screen buttons':rect($('.v4-fs')),
    'Price clock':rect($('.v4-fs-toprice')),
    'Switch to chart':rect($('.v4-fs-tochart')),
    'Theme dot':rect(el('themeDot')),
    'Price pill':rect(el('pxPill')),
    'Close':rect(dlg?dlg.querySelector('.bc-x'):null)
  };
  var vis={};
  Object.keys(prot).forEach(function(k){
    var sel={'BTC price':el('price')||(dlg&&dlg.querySelector('.bc-px')),'Keep screen on':el('wakeBtn'),'Exit full screen':$('.v4-fs-exit'),'Light/Dark pill':el('psThemePill'),'Full-screen buttons':$('.v4-fs'),'Price clock':$('.v4-fs-toprice'),'Switch to chart':$('.v4-fs-tochart'),'Theme dot':el('themeDot'),'Price pill':el('pxPill'),'Close':dlg&&dlg.querySelector('.bc-x')}[k];
    vis[k]=visible(sel);
  });
  var pn=rect(pnEl),mn=rect(mnEl),tp=rect(taBtn),rs=rect(rsiEl&&!rsiEl.hidden?rsiEl:null),bx=rect(dlg?dlg.querySelector('.bc-box'):null);
  var overlaps=[];
  [['panel',pn],['menu',mn]].forEach(function(pair){
    if(!pair[1])return;
    Object.keys(prot).forEach(function(k){if(overlap(pair[1],prot[k]))overlaps.push(pair[0]+' x '+k);});
  });
  return {stage:rect(el('hero'))||rect(dlg),panelVisible:panelVisible,menuVisible:menuVisible,vw:innerWidth,vh:innerHeight,
    panel:pn,menu:mn,pill:tp,rsi:rs,box:bx,prot:prot,vis:vis,overlaps:overlaps,
    lane:rect(dlg?dlg.querySelector('.bc-row2'):null),scrollY:scrollY};
};

/* ---------- init ---------- */
function init(api){
  if(inited)return;
  if(!api)return;
  dlg=api.dlg();
  if(!dlg)return;
  inited=true;
  typBtn=dlg.querySelector('#taTyp');
  taBtn=dlg.querySelector('#taPill');
  rsiEl=dlg.querySelector('#taRsi');
  if(!typBtn||!taBtn)return;
  /* Type pill: opens the menu. The panel keeps the label in sync on draw. */
  typBtn.addEventListener('click',function(e){
    e.stopPropagation();
    if(menuOpen)closeMenu(false);else{closePanel(false);openMenu();}
  });
  taBtn.addEventListener('click',function(e){
    e.stopPropagation();
    if(panelOpen)closePanel(false);else{closeMenu(false);openPanel();}
  });
  /* Menu picks drive the hidden buttons. */
  document.addEventListener('click',function(e){
    if(!menuOpen)return;
    if(menuEl&&menuEl.contains(e.target))return;
    if(typBtn&&typBtn.contains(e.target))return;
    closeMenu(false);
  });
  document.addEventListener('click',function(e){
    if(!panelOpen)return;
    if(panelEl&&panelEl.contains(e.target))return;
    if(taBtn&&taBtn.contains(e.target))return;
    closePanel(false);
  });
  document.addEventListener('keydown',function(e){
    if(e.key!=='Escape')return;
    if(menuOpen){e.preventDefault();closeMenu(true);}
    else if(panelOpen){e.preventDefault();closePanel(true);}
  });
  /* Escape in the popover closes the TA panel/menu first (and stops the
     keypress reaching the dialog's own Escape handler, which would close
     the whole dialog). A second Escape then closes the dialog as before. */
  dlg.addEventListener('keydown',function(e){
    if(e.key!=='Escape')return;
    if(menuOpen||panelOpen){e.preventDefault();e.stopPropagation();if(menuOpen)closeMenu(true);else closePanel(true);}
  });
  if(menuEl===null)buildMenu();
  if(panelEl===null)buildPanel();
  /* Delegated clicks inside the floating layers. */
  floatParent().addEventListener('click',function(e){
    var b=e.target.closest('[data-ta-pick]');
    if(b){var k=b.getAttribute('data-ta-pick');closeMenu(false);pickType(k);return;}
    var sz=e.target.closest('[data-ta-size]');
    if(sz){closeMenu(false);pickSize(sz.getAttribute('data-ta-size'));return;}
    var sw=e.target.closest('[data-ta-key]');
    if(sw){setToggle(sw.getAttribute('data-ta-key'),!S[sw.getAttribute('data-ta-key')]);return;}
    var sg=e.target.closest('[data-ta-seg]');
    if(sg){
      var v=sg.getAttribute('data-ta-seg');
      if(v==='SMA'||v==='EMA')S.maKind=v.toLowerCase();
      else S.maPer=parseInt(v,10);
      if(!S.ma)S.ma=true;
      saveS();syncPanel();syncPill();syncRsi();
      return;
    }
    if(e.target.closest('[data-ta-clear]')){
      S.tl=false;S.bb=false;S.ma=false;S.rsi=false;saveS();syncPanel();syncPill();syncRsi();
      return;
    }
  });
  /* RSI strip collapse toggle. */
  if(rsiEl){
    var t=rsiEl.querySelector('.ta-rsi-t');
    if(t)t.addEventListener('click',function(){
      S.rsiCol=!S.rsiCol;saveS();syncRsi();
    });
  }
  /* After every native draw: Stage 1 draws nothing. Keep the menu closed
     (its options are stale after a state change) and the strip in sync. */
  api.afterDraw=function(kind){
    if(menuOpen)closeMenu(false);
    syncRsi();
  };
  syncPill();syncRsi();
  if(api.syncTypePill)api.syncTypePill();
}

window.__BTTA={init:init,typeLabel:typeLabel};
if(API&&API.dlg)init(API);
})();
