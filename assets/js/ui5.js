/* v5 UI: Rules "Details +" pop-up card, scroll-reveal for homepage sections. Without JS the detail rules stay inline and nothing is hidden. */
(function(){
var W={BTC:'#f7931a',MSTR:'#22d3ee',STRC:'#a78bfa',TSLA:'#f43f5e',PLTR:'#94a3b8'};
function bar(ws){return '<div class="prx-bar" aria-hidden="true">'+ws.map(function(w){return '<i style="flex:'+w[0]+';background:'+W[w[1]]+'"></i>';}).join('')+'</div><div class="prx-chips">'+ws.map(function(w){return '<span><b style="background:'+W[w[1]]+'"></b>'+w[0]+'% '+w[1]+'</span>';}).join('')+'</div>';}
var d=document.getElementById('prDetails');
if(d){
  var host=d.parentNode,btn=document.createElement('button');btn.type='button';btn.className='prd-btn';btn.id='prBtn';
  btn.setAttribute('aria-haspopup','dialog');btn.setAttribute('aria-expanded','false');btn.setAttribute('aria-controls','prDetails');btn.innerHTML='Details <span aria-hidden="true">+</span>';
  btn.setAttribute('aria-label','Portfolio rules in detail');
  var sr=document.querySelector('#rules ul.rules');if(sr){var bw=document.createElement('div');bw.className='prd-btn-wrap';bw.appendChild(btn);sr.parentNode.insertBefore(bw,sr.nextSibling);}else host.insertBefore(btn,d);
  var dim=document.createElement('div');dim.className='prd-dim';dim.hidden=true;document.body.appendChild(dim);
  var card=document.createElement('div');card.className='prd-card';card.hidden=true;card.setAttribute('role','dialog');card.setAttribute('aria-modal','true');card.setAttribute('aria-label','Portfolio rules in detail');card.tabIndex=-1;
  var x=document.createElement('button');x.type='button';x.className='prd-x';x.setAttribute('aria-label','Close');x.textContent='✕';
  function pf(ps,route,wide){return '<div class="prx-pf'+(wide?' prx-wide':'')+'">'+ps.map(function(q){return '<div class="prx-one"><div class="prx-pfn">'+q[0]+'</div>'+bar(q[1])+'</div>';}).join('')+'<div class="prx-route">'+route+'</div></div>';}
  var body=document.createElement('div');body.className='prx';
  function al(n,ws){return '<div class="prx-pf"><div class="prx-pfn">'+n+'</div>'+bar(ws)+'</div>';}
  body.innerHTML='<header class="prx-hd"><span class="prx-kick">PaperStreet BTC</span><h2 id="prxTitle">Portfolio rules in detail</h2></header>'+
   '<section class="prx-rule" id="prx-weights"><span class="prx-n">01</span><div><h3>Weights are the book.</h3><p>They do not get rewritten mid-year because a tape looks ugly.</p></div></section>'+
   '<section class="prx-rule" id="prx-dividends"><span class="prx-n">02</span><div><h3>Dividends move on issue day</h3><p>— not when it feels clever.</p><ul class="prx-routes"><li>Berkshire Killer and Hodler Jam Sandwich: STRC → BTC.</li><li>Hedge Fund Killer: STRC → BTC and MSTR at 50/50.</li><li>Saylor Moon: STRC → MSTR.</li></ul></div></section>'+
   '<section class="prx-rule prx-dca" id="prx-dca"><span class="prx-n">03</span><div><h3>DCA is monthly.</h3><p>That is the strategy. The point of the book is to stop helping people time the market.</p></div></section>'+
   '<section class="prx-alloc" id="prx-alloc" aria-label="Allocations"><div class="prx-grid">'+
     al('Berkshire Killer',[[40,'BTC'],[20,'STRC'],[30,'TSLA'],[10,'PLTR']])+al('Hodler Jam Sandwich',[[70,'BTC'],[10,'STRC'],[20,'MSTR']])+
     al('Hedge Fund Killer',[[55,'BTC'],[35,'MSTR'],[10,'STRC']])+al('Saylor Moon',[[50,'MSTR'],[50,'STRC']])+'</div></section>';
  card.removeAttribute('aria-label');card.setAttribute('aria-labelledby','prxTitle');
  var grab=document.createElement('div');grab.className='prx-grab';grab.setAttribute('aria-hidden','true');
  card.appendChild(grab);card.appendChild(x);card.appendChild(body);card.appendChild(d);d.hidden=true;document.body.appendChild(card);d.classList.add('in-card');card.classList.add('prx-card');
  var RM=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  var opener=null,sy=0;
  function open(target,from){opener=from||btn;dim.hidden=false;card.hidden=false;void card.offsetWidth;card.classList.add('prx-on');dim.classList.add('prx-on');btn.setAttribute('aria-expanded','true');
    sy=window.scrollY;document.documentElement.classList.add('prd-lock');
    card.scrollTop=0;var t=target&&document.getElementById(target);if(t&&card.contains(t)){card.scrollTop=Math.max(0,t.offsetTop-24);t.classList.add('prd-hl');setTimeout(function(){t.classList.remove('prd-hl');},1600);}
        x.focus({preventScroll:true});}
  function close(){if(card.hidden||!card.classList.contains('prx-on'))return;card.classList.remove('prx-on');dim.classList.remove('prx-on');setTimeout(function(){card.hidden=true;dim.hidden=true;},RM?0:220);btn.setAttribute('aria-expanded','false');document.documentElement.classList.remove('prd-lock');
    window.scrollTo(0,sy);(opener||btn).focus({preventScroll:true});}
  btn.addEventListener('click',function(){open(null,btn);});x.addEventListener('click',close);dim.addEventListener('click',close);
  document.addEventListener('keydown',function(e){if(card.hidden)return;if(e.key==='Escape'){e.preventDefault();close();return;}
    if(e.key==='Tab'){var f=[].slice.call(card.querySelectorAll('button,a[href]'));if(!f.length)return;var a=f[0],z=f[f.length-1];
      if(e.shiftKey&&(document.activeElement===a||document.activeElement===card)){e.preventDefault();z.focus();}else if(!e.shiftKey&&document.activeElement===z){e.preventDefault();a.focus();}}});
  document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[href^="#rule-"]');if(!a||card.contains(a))return;e.preventDefault();open('prx-'+a.getAttribute('href').slice(6),a);});
  var h=location.hash.slice(1);if(/^rule-/.test(h))setTimeout(function(){open('prx-'+h.slice(5),btn);},300);
}
/* scroll reveal */
if('IntersectionObserver' in window&&!(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches)){
  var els=[].slice.call(document.querySelectorAll('body > section, main > section')).filter(function(s){return !s.classList.contains('hero')&&s.getBoundingClientRect().top>window.innerHeight;});
  if(location.hash)els=[];
  var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('rv-in');io.unobserve(e.target);}});},{rootMargin:'0px 0px -8% 0px',threshold:0.04});
  els.forEach(function(s){s.classList.add('rv');io.observe(s);});
  setTimeout(function(){els.forEach(function(s){var r=s.getBoundingClientRect();if(r.bottom<0)s.classList.add('rv-in');});},50);
}

/* CR-013: tap a sleeve's weights line to pop up its allocation bar (reuses the rules pop-up bar + chips) */
(function(){var ws=[].slice.call(document.querySelectorAll('#sleeves p.weights'));if(!ws.length)return;
  var dim=document.createElement('div');dim.className='prd-dim slv-dim';dim.hidden=true;document.body.appendChild(dim);
  var pop=document.createElement('div');pop.className='slv-pop';pop.hidden=true;pop.setAttribute('role','dialog');pop.setAttribute('aria-modal','true');pop.setAttribute('aria-labelledby','slvT');pop.tabIndex=-1;document.body.appendChild(pop);
  var op=null,RM=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  function parse(t){return t.split('·').map(function(x){var m=x.trim().match(/^(\d+)%\s+(\S+)$/);return m?[+m[1],m[2]]:null;}).filter(Boolean);}
  function place(){if(window.innerWidth<=640){pop.style.left=pop.style.top='';return;}var r=op.getBoundingClientRect(),w=pop.offsetWidth,h=pop.offsetHeight;
    var l=Math.max(16,Math.min(r.left,window.innerWidth-w-16)),t=r.bottom+10;if(t+h>window.innerHeight-16)t=Math.max(16,r.top-h-10);pop.style.left=l+'px';pop.style.top=t+'px';}
  function open(p){op=p;var n=p.closest('.card').querySelector('h4').textContent;
    pop.innerHTML='<button type="button" class="prd-x slv-x" aria-label="Close">✕</button><div class="prx-pf"><div class="prx-pfn" id="slvT">'+n+'</div>'+bar(parse(p.textContent))+'</div>';
    pop.querySelector('.slv-x').addEventListener('click',close);
    dim.hidden=false;pop.hidden=false;place();void pop.offsetWidth;pop.classList.add('prx-on');dim.classList.add('prx-on');p.setAttribute('aria-expanded','true');pop.querySelector('.slv-x').focus({preventScroll:true});}
  function close(){if(pop.hidden||!pop.classList.contains('prx-on'))return;pop.classList.remove('prx-on');dim.classList.remove('prx-on');op.setAttribute('aria-expanded','false');
    setTimeout(function(){pop.hidden=true;dim.hidden=true;},RM?0:200);op.focus({preventScroll:true});}
  ws.forEach(function(p){p.setAttribute('role','button');p.tabIndex=0;p.setAttribute('aria-haspopup','dialog');p.setAttribute('aria-expanded','false');p.classList.add('slv-trg');
    p.setAttribute('aria-label','Show allocation: '+p.closest('.card').querySelector('h4').textContent);
    p.addEventListener('click',function(e){e.stopPropagation();open(p);});
    var cd=p.closest('.card');if(cd){cd.classList.add('slv-card');cd.addEventListener('click',function(e){if(e.target.closest('a,button,input,select,textarea,summary,label,[role=button]'))return;if(window.getSelection&&String(window.getSelection()).length)return;open(p);});}p.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();open(p);}});});
  dim.addEventListener('click',close);window.addEventListener('resize',function(){if(!pop.hidden)place();});
  document.addEventListener('keydown',function(e){if(pop.hidden)return;if(e.key==='Escape'){e.preventDefault();close();}else if(e.key==='Tab'){e.preventDefault();pop.querySelector('.slv-x').focus();}});
})();

/* CR-015: Benchmarks + button opens the benchmarks block in the same modal pattern as the rules pop-up */
(function(){var bm=document.getElementById('benchmarks'),bw=document.querySelector('.prd-btn-wrap');if(!bm||!bw)return;
  var btn=document.createElement('button');btn.type='button';btn.className='prd-btn';btn.id='bmBtn';btn.setAttribute('aria-haspopup','dialog');btn.setAttribute('aria-expanded','false');btn.setAttribute('aria-controls','bmCard');btn.innerHTML='Benchmarks <span aria-hidden="true">+</span>';
  bw.appendChild(btn);bw.classList.add('prd-btn-row');
  var dim=document.createElement('div');dim.className='prd-dim bm-dim';dim.hidden=true;document.body.appendChild(dim);
  var card=document.createElement('div');card.className='prd-card prx-card bm-card';card.id='bmCard';card.hidden=true;card.setAttribute('role','dialog');card.setAttribute('aria-modal','true');card.tabIndex=-1;
  var grab=document.createElement('div');grab.className='prx-grab';grab.setAttribute('aria-hidden','true');
  var x=document.createElement('button');x.type='button';x.className='prd-x';x.setAttribute('aria-label','Close');x.textContent='✕';
  var body=document.createElement('div');body.className='prx bm-body';
  var h=bm.querySelector('h3');if(h){h.id='bmTitle';card.setAttribute('aria-labelledby','bmTitle');}
  card.appendChild(grab);card.appendChild(x);card.appendChild(body);body.appendChild(bm);document.body.appendChild(card);
  var sec=document.getElementById('portfolio-rules');if(sec&&!sec.querySelector('.container').children.length)sec.classList.add('bm-empty');
  var opener=null;
  function open(from){opener=from||btn;card.classList.remove('bm-closing');dim.classList.remove('bm-closing');dim.hidden=false;card.hidden=false;void card.offsetWidth;card.classList.add('prx-on');dim.classList.add('prx-on');btn.setAttribute('aria-expanded','true');
    document.documentElement.classList.add('prd-lock');card.scrollTop=0;window.dispatchEvent(new Event('resize'));x.focus({preventScroll:true});}
  function close(){if(card.hidden||!card.classList.contains('prx-on'))return;card.classList.remove('prx-on');dim.classList.remove('prx-on');btn.setAttribute('aria-expanded','false');
    document.documentElement.classList.remove('prd-lock');card.classList.add('bm-closing');dim.classList.add('bm-closing');
    var done=false,fin=function(e){if(done||(e&&(e.target!==card||e.propertyName!=='transform'&&e.propertyName!=='opacity')))return;done=true;card.removeEventListener('transitionend',fin);clearTimeout(tm);card.hidden=true;dim.hidden=true;card.classList.remove('bm-closing');dim.classList.remove('bm-closing');};
    card.addEventListener('transitionend',fin);var tm=setTimeout(fin,400);(opener||btn).focus({preventScroll:true});}
  btn.addEventListener('click',function(){open(btn);});x.addEventListener('click',close);dim.addEventListener('click',close);
  document.addEventListener('keydown',function(e){if(card.hidden)return;if(e.key==='Escape'){e.preventDefault();close();return;}
    if(e.key==='Tab'){var f=[].slice.call(card.querySelectorAll('button,a[href]'));var a=f[0],z=f[f.length-1];if(e.shiftKey&&document.activeElement===a){e.preventDefault();z.focus();}else if(!e.shiftKey&&document.activeElement===z){e.preventDefault();a.focus();}else if(!card.contains(document.activeElement)){e.preventDefault();a.focus();}}});
  document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[href$="#benchmarks"]');if(!a||card.contains(a))return;e.preventDefault();open(a);});
  if(location.hash==='#benchmarks')setTimeout(function(){bw.scrollIntoView({block:'center'});open(btn);},300);
})();
})();
