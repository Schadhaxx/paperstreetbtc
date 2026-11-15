/* TA pill mockup driver (13 Nov 2026). Mockup only, not a patch.
   URL params: a=A|B|C|D  s=today|closed|open|rsi|rsicol  r=<range> ct=candles  fs=chart|price  ma=sma|ema  p=20|50|200 */
(function(){
var Q=new URLSearchParams(location.search);
var A=(Q.get('a')||'A').toUpperCase(), S=Q.get('s')||'closed', R=Q.get('r'), CT=Q.get('ct'), FS=Q.get('fs');
var MA=Q.get('ma')||'sma', PER=+(Q.get('p')||50);
var root=document.documentElement;
var $=function(s){return document.querySelector(s)};
var sleep=function(ms){return new Promise(function(r){setTimeout(r,ms)})};
var chev='<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2 3.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
var COL={sma:'#f472b6',bb:'#a78bfa',up:'#22c55e',dn:'#f87171',rsi:'#a78bfa'};
var light=function(){return root.getAttribute('data-theme')==='light'};
/* what's on, per state */
var ON={today:{},closed:{bb:1,ma:1},candles:{},open:{bb:1,ma:1},rsi:{tl:1,ma:1,rsi:1},rsicol:{tl:1,ma:1,rsi:1}}[S]||{};
var nOn=Object.keys(ON).length;

function painted(){var c=$('#bcC');if(!c||!c.width)return false;try{var d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;for(var i=3;i<d.length;i+=4*97)if(d[i]>200)return true;}catch(e){}return false;}
async function waitPaint(){for(var i=0;i<80;i++){if(painted())return;await sleep(250);}}
function click(sel){var b=$(sel);if(b)b.click();}

function pill(){var b=document.createElement('button');b.type='button';b.className='ta-pill'+(nOn?' act':'')+(S==='open'?' open':'');
  b.setAttribute('aria-haspopup','dialog');b.setAttribute('aria-expanded',S==='open'?'true':'false');b.setAttribute('aria-label','Technical analysis'+(nOn?', '+nOn+' on':''));
  b.innerHTML='<span>TA</span>'+(nOn?'<i class="ta-n">'+nOn+'</i>':chev);return b;}
function slot(){var b=document.createElement('span');b.className='ta-slot';b.setAttribute('aria-hidden','true');b.innerHTML='<span>TA</span>'+chev;return b;}
function tap(){return S==='today'?slot():pill();}

function layout(){
  root.classList.add('ta-'+A,'ta-fade');
  var inl=$('.bc-inline'), rg=$('#bcRg'), rgs=$('#bcRgs'), lg=$('#bcLg'), ct=$('#bcCt'), cg=$('#bcCg');
  if(A==='A'){rgs.classList.add('ta-fade-lane');rg.appendChild(tap());}
  if(A==='B'){var lane=document.createElement('div');lane.className='ta-lane ta-fade-lane';inl.insertBefore(lane,lg);
    lane.appendChild(ct);lane.appendChild(cg);var dv=document.createElement('span');dv.className='ta-div';lane.appendChild(dv);lane.appendChild(lg);
    var e=tap();e.classList.add('ta-end');inl.insertBefore(e,$('.bc-box'));}
  if(A==='C'){var t=document.createElement('button');t.type='button';t.className='ta-typ';
    var on=[].slice.call(document.querySelectorAll('#bcCt button.on,#bcCg button.on')).filter(function(b){return b.offsetParent!==null||b.closest('.bc-ct').style.display!=='none'});
    var vis=[ct,cg].filter(function(x){return x.style.display!=='none'})[0];
    var ob=vis&&vis.querySelector('button.on[data-ct],button.on[data-cg]');var lab=ob?ob.textContent:'Line';
    if(lab==='1H'||lab==='4H')lab=lab+' candles';
    t.innerHTML='<span>'+(lab||'Line')+'</span>'+chev;t.setAttribute('aria-label','Chart type: '+lab);inl.insertBefore(t,$('.bc-box'));
    var e2=tap();e2.classList.add('ta-end');inl.insertBefore(e2,$('.bc-box'));}
  if(A==='D'){var row=document.createElement('div');row.className='ta-row';var l2=document.createElement('div');l2.className='ta-lane2 ta-fade-lane';
    l2.appendChild(ct);l2.appendChild(cg);row.appendChild(l2);
    if(nOn&&S!=='open'){[['ma',(MA==='ema'?'EMA ':'SMA ')+PER,COL.sma],['bb','Bollinger',COL.bb],['tl','Trendlines',COL.up],['rsi','RSI',COL.rsi]].forEach(function(c){if(ON[c[0]]){var s=document.createElement('span');s.className='ta-chip';s.innerHTML='<i style="background:'+c[2]+'"></i>'+c[1];l2.appendChild(s);}});}
    row.appendChild(tap());inl.insertBefore(row,$('.bc-box'));}
}

/* ---- read the drawn price path off the real chart canvas (illustrative overlays) ---- */
function path(){
  var c=$('#bcC'),W=c.width,H=c.height,dpr=W/c.clientWidth,d=c.getContext('2d').getImageData(0,0,W,H).data,ys=[],x0=-1,x1=-1;
  var cw=Math.floor(c.clientWidth);
  for(var cx=0;cx<cw;cx++){var px=Math.round(cx*dpr),mn=-1,mx=-1;
    for(var y=0;y<H;y++){var i=(y*W+px)*4,r=d[i],g=d[i+1],b=d[i+2],a=d[i+3];if(a<170)continue;var M=Math.max(r,g,b),m=Math.min(r,g,b);if(M-m<70)continue;
      if(mn<0)mn=y;mx=y; if(!CANDLE&&mx-mn>2*dpr)break;}
    if(mn>=0){var v=CANDLE?(mn+mx)/2:mn;ys[cx]=v/dpr;if(x0<0)x0=cx;x1=cx;}}
  // drop the right-edge live label/marker region a bit, interpolate holes
  var out=[];for(var x=x0;x<=x1;x++){if(ys[x]==null){var a=x-1,b=x+1;while(b<=x1&&ys[b]==null)b++;ys[x]=ys[a]+(ys[b]-ys[a])*(x-a)/(b-a);}out.push(ys[x]);}
  return {x0:x0,ys:out};
}
var CANDLE=false;
function sma(a,w){var o=[],s=0;for(var i=0;i<a.length;i++){s+=a[i];if(i>=w)s-=a[i-w];o.push(i>=w-1?s/w:null);}return o;}
function ema(a,w){var o=[],k=2/(w+1),e=null;for(var i=0;i<a.length;i++){e=e==null?a[i]:a[i]*k+e*(1-k);o.push(i>=w-1?e:null);}return o;}
function sd(a,w,m){var o=[];for(var i=0;i<a.length;i++){if(m[i]==null){o.push(null);continue;}var s=0;for(var j=i-w+1;j<=i;j++)s+=(a[j]-m[i])*(a[j]-m[i]);o.push(Math.sqrt(s/w));}return o;}
function sm3(a){var k=5;return a.map(function(v,i){if(v==null)return null;var t=0,n=0;for(var j=i-k;j<=i+k;j++)if(a[j]!=null){t+=a[j];n++;}return t/n;});}
function line(x,pts,x0,col,wd,dash){x.save();x.strokeStyle=col;x.lineWidth=wd;x.setLineDash(dash||[]);x.lineJoin='round';x.beginPath();var st=false;
  for(var i=0;i<pts.length;i++){if(pts[i]==null){st=false;continue;}if(!st){x.moveTo(x0+i,pts[i]);st=true;}else x.lineTo(x0+i,pts[i]);}x.stroke();x.restore();}

function overlays(){
  var box=$('.bc-box'),old=box.querySelector('.ta-ov');if(old)old.remove();
  if(!ON.bb&&!ON.ma&&!ON.tl)return;
  var P=path(),ys=P.ys,L=ys.length;if(L<20)return;
  var cv=document.createElement('canvas');cv.className='ta-ov';var dpr=window.devicePixelRatio||1;cv.width=box.clientWidth*dpr;cv.height=box.clientHeight*dpr;box.appendChild(cv);
  var x=cv.getContext('2d');x.scale(dpr,dpr);
  var win=function(p){return Math.max(4,Math.round(L*(p===20?0.05:p===50?0.12:0.42)));};
  if(ON.bb){var w=Math.max(6,Math.round(L*0.08)),m=sma(ys,w),s0=sd(ys,w,m),s=sm3(s0),u=sm3(m.map(function(v,i){return v==null?null:v-2*s[i]})),l=sm3(m.map(function(v,i){return v==null?null:v+2*s[i]}));
    x.save();x.fillStyle=light()?'rgba(124,58,237,.07)':'rgba(167,139,250,.09)';x.beginPath();var f=-1;
    for(var i=0;i<L;i++)if(u[i]!=null){if(f<0){f=i;x.moveTo(P.x0+i,u[i]);}else x.lineTo(P.x0+i,u[i]);}
    for(i=L-1;i>=f;i--)x.lineTo(P.x0+i,l[i]);x.closePath();x.fill();x.restore();
    var bc=light()?'#7c3aed':COL.bb;line(x,u,P.x0,bc,1,[]);line(x,l,P.x0,bc,1,[]);line(x,m,P.x0,bc,1,[3,3]);}
  if(ON.ma){var mm=(MA==='ema'?ema:sma)(ys,win(PER));line(x,mm,P.x0,light()?'#db2777':COL.sma,1.8,[]);}
  if(ON.tl){var sm=sma(ys,Math.max(3,Math.round(L*0.02))),k=Math.max(6,Math.round(L*0.07)),hi=[],lo=[];
    for(var i2=k;i2<L-k/2;i2++){if(sm[i2]==null)continue;var isH=true,isL=true;for(var j=i2-k;j<=Math.min(L-1,i2+k);j++){if(sm[j]==null)continue;if(sm[j]<sm[i2])isH=false;if(sm[j]>sm[i2])isL=false;}
      if(isH)hi.push(i2);if(isL)lo.push(i2);}
    function tl(pv,col,lab){if(pv.length<2)return;var a=pv[pv.length-2],b=pv[pv.length-1];var ya=ys[a],yb=ys[b];
      // snap to the extreme raw value near each pivot
      var sl=(yb-ya)/(b-a),xe=L-1,ye=yb+sl*(xe-b);
      x.save();x.strokeStyle=col;x.lineWidth=1.4;x.setLineDash([5,4]);x.beginPath();x.moveTo(P.x0+a,ya);x.lineTo(P.x0+xe,ye);x.stroke();
      x.setLineDash([]);x.fillStyle=col;[a,b].forEach(function(p){x.beginPath();x.arc(P.x0+p,ys[p],2.6,0,7);x.fill();});x.restore();}
    tl(hi,COL.dn);tl(lo,COL.up);}
}

function rsiStrip(){
  var inl=$('.bc-inline'),st=document.createElement('div');st.className='ta-rsi'+(S==='rsicol'?' col':'');
  st.innerHTML='<button type="button" class="ta-rsi-t" aria-expanded="'+(S!=='rsicol')+'">RSI 14 <b>—</b>'+chev+'</button><canvas></canvas>';
  inl.appendChild(st);root.classList.add('ta-rsi-on');return st;}
function drawRsi(st){
  var P=path(),ys=P.ys,L=ys.length,step=Math.max(1,Math.round(L/40)),pr=[];for(var i=0;i<L;i+=step)pr.push(-ys[i]);
  var n=14,g=0,l=0,r=[];for(i=1;i<pr.length;i++){var ch=pr[i]-pr[i-1],up=Math.max(ch,0),dn=Math.max(-ch,0);
    if(i<=n){g+=up/n;l+=dn/n;r.push(null);continue;}g=(g*(n-1)+up)/n;l=(l*(n-1)+dn)/n;r.push(100-100/(1+g/(l||1e-9)));}
  var last=r[r.length-1];st.querySelector('b').textContent=last==null?'—':Math.round(last);
  if(st.classList.contains('col'))return;
  var cv=st.querySelector('canvas'),dpr=window.devicePixelRatio||1,W=st.clientWidth,H=st.clientHeight;cv.width=W*dpr;cv.height=H*dpr;var x=cv.getContext('2d');x.scale(dpr,dpr);
  var top=4,bot=H-3,yv=function(v){return bot-(v/100)*(bot-top)};
  x.fillStyle=light()?'rgba(124,58,237,.06)':'rgba(167,139,250,.07)';x.fillRect(P.x0,yv(70),L,yv(30)-yv(70));
  x.strokeStyle=light()?'#cbd5e1':'rgba(148,163,184,.28)';x.setLineDash([3,3]);x.lineWidth=1;[70,30].forEach(function(v){x.beginPath();x.moveTo(P.x0,yv(v));x.lineTo(P.x0+L,yv(v));x.stroke();});x.setLineDash([]);
  x.fillStyle=light()?'#64748b':'#64748b';x.font='600 9px Inter,sans-serif';x.textAlign='right';x.fillText('70',P.x0-4,yv(70)+3);x.fillText('30',P.x0-4,yv(30)+3);
  x.strokeStyle=light()?'#7c3aed':COL.rsi;x.lineWidth=1.5;x.beginPath();var s=false;
  for(i=0;i<r.length;i++){if(r[i]==null)continue;var xx=P.x0+(i+1)*step;if(!s){x.moveTo(xx,yv(r[i]));s=true;}else x.lineTo(xx,yv(r[i]));}x.stroke();
}

function panel(){
  var p=document.createElement('div');p.className='ta-panel';p.setAttribute('role','dialog');p.setAttribute('aria-label','Technical analysis');
  var sw=function(on){return '<span class="ta-sw'+(on?' on':'')+'" role="switch" aria-checked="'+(!!on)+'"></span>'};
  var seg=function(opts,cur){return '<span class="ta-seg">'+opts.map(function(o){return '<button type="button" class="'+(String(o).toLowerCase()===String(cur).toLowerCase()?'on':'')+'">'+o+'</button>'}).join('')+'</span>'};
  p.innerHTML='<div class="ta-ph"><b>Technical analysis</b><button type="button">Clear all</button></div>'
   +'<div class="ta-it"><div class="nm"><span><i style="background:'+COL.up+'"></i>Smart Trendlines</span><small>auto support / resistance</small></div>'+sw(ON.tl)+'</div>'
   +'<div class="ta-it"><div class="nm"><span><i style="background:'+COL.bb+'"></i>Bollinger Bands</span><small>20 · 2σ</small></div>'+sw(ON.bb)+'</div>'
   +'<div class="ta-it"><div class="nm"><span><i style="background:'+COL.sma+'"></i>Moving average</span><small>one at a time</small></div>'+sw(ON.ma)+'</div>'
   +'<div class="ta-ma'+(ON.ma?'':' off')+'">'+seg(['SMA','EMA'],MA)+seg([20,50,200],PER)+'</div>'
   +'<div class="ta-it"><div class="nm"><span><i style="background:'+COL.rsi+'"></i>RSI</span><small>14 · strip under chart</small></div>'+sw(ON.rsi)+'</div>';
  var stg=$('#hero');stg.appendChild(p);
  var t=$('.ta-pill').getBoundingClientRect(),box=$('.bc-box').getBoundingClientRect(),pw=p.offsetWidth,ph=p.offsetHeight;
  var left=Math.min(t.right,box.right)-pw;left=Math.max(box.left,left);
  var top=t.bottom+6;
  var sr=stg.getBoundingClientRect();p.style.left=(left-sr.left-stg.clientLeft)+'px';p.style.top=(top-sr.top-stg.clientTop)+'px';if(top+ph>innerHeight-6){p.style.maxHeight=(innerHeight-6-top)+'px';p.style.overflowY='auto';p.classList.add('ta-scroll');}
  return p;
}

function rect(el){if(!el)return null;var r=el.getBoundingClientRect();if(!r.width||!r.height)return null;return {x:r.left,y:r.top,w:r.width,h:r.height,r:r.right,b:r.bottom};}
function union(a,b){if(!a)return b;if(!b)return a;var x=Math.min(a.x,b.x),y=Math.min(a.y,b.y),r=Math.max(a.r,b.r),bb=Math.max(a.b,b.b);return {x:x,y:y,w:r-x,h:bb-y,r:r,b:bb};}
function visible(el){if(!el)return false;var r=el.getBoundingClientRect();if(!r.width||!r.height)return false;var pn=$('.ta-panel'),pd=pn&&pn.style.display;if(pn)pn.style.display='none';
  var pts=[[.5,.5],[.15,.5],[.85,.5]],hit=false;pts.forEach(function(q){var x=r.left+r.width*q[0],y=r.top+r.height*q[1];if(x<0||y<0||x>innerWidth||y>innerHeight)return;var h=document.elementFromPoint(x,y);if(h&&(h===el||el.contains(h)))hit=true;});
  if(pn)pn.style.display=pd||'';return hit;}
window.__taRects=function(){
  var pnEl=$('.ta-panel'),panelVisible=false;if(pnEl){var q=pnEl.getBoundingClientRect(),h=document.elementFromPoint(q.left+q.width/2,q.top+q.height/2);panelVisible=!!(h&&pnEl.contains(h));}
  var prot={
    'BTC price':union(rect($('#price')),rect($('.v4-chg'))),
    'Keep screen on':rect($('#wakeBtn')),
    'Exit full screen':rect($('.v4-fs-exit')),
    'Light/Dark pill':rect($('#psThemePill')),
    'Full-screen buttons':rect($('.v4-fs'))
  };
  var vis={'BTC price':visible($('#price')),'Keep screen on':visible($('#wakeBtn')),'Exit full screen':visible($('.v4-fs-exit')),'Light/Dark pill':visible($('#psThemePill')),'Full-screen buttons':visible($('.v4-fs'))};
  var pn=rect($('.ta-panel')),tp=rect($('.ta-pill'))||rect($('.ta-slot')),rs=rect($('.ta-rsi')),bx=rect($('.bc-box'));
  return {stage:rect($('#hero')),panelVisible:panelVisible,vw:innerWidth,vh:innerHeight,panel:pn,pill:tp,rsi:rs,box:bx,prot:prot,vis:vis,
    reserved:rect($('.ta-slot')),lane:rect($('.ta-lane'))||rect($('.ta-row')),scrollY:scrollY};
};

async function go(){
  for(var i=0;i<80&&!$('#bcRgs');i++)await sleep(150);
  await waitPaint();
  if(R){click('#bcRgs button[data-r="'+R+'"]');await sleep(900);await waitPaint();}
  if(CT==='candles'){CANDLE=true;click('#bcCg button[data-cg="candles"]');click('#bcCt button[data-ct="1h"]');await sleep(1200);await waitPaint();}
  layout();
  if(FS&&window.__psClockFs)window.__psClockFs.enter(FS);
  window.dispatchEvent(new Event('resize'));await sleep(900);
  var st=null;if(ON.rsi){st=rsiStrip();window.dispatchEvent(new Event('resize'));await sleep(900);}
  await waitPaint();await sleep(300);
  if(FS!=='price'){overlays();if(st)drawRsi(st);}
  if(S==='open'&&FS!=='price'&&$('.ta-pill'))panel();
  window.__taReady=true;
}
go();
})();
