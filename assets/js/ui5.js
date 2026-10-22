/* v5 UI: Rules "Details +" pop-up card, scroll-reveal for homepage sections. Without JS the detail rules stay inline and nothing is hidden. */
(function(){
var d=document.getElementById('prDetails');
if(d){
  var host=d.parentNode,btn=document.createElement('button');btn.type='button';btn.className='prd-btn';btn.id='prBtn';
  btn.setAttribute('aria-haspopup','dialog');btn.setAttribute('aria-expanded','false');btn.setAttribute('aria-controls','prDetails');btn.innerHTML='Details <span aria-hidden="true">+</span>';
  btn.setAttribute('aria-label','Portfolio rules in detail');
  var sr=document.querySelector('#rules ul.rules');if(sr){var bw=document.createElement('div');bw.className='prd-btn-wrap';bw.appendChild(btn);sr.parentNode.insertBefore(bw,sr.nextSibling);}else host.insertBefore(btn,d);
  var dim=document.createElement('div');dim.className='prd-dim';dim.hidden=true;document.body.appendChild(dim);
  var card=document.createElement('div');card.className='prd-card';card.hidden=true;card.setAttribute('role','dialog');card.setAttribute('aria-modal','true');card.setAttribute('aria-label','Portfolio rules in detail');card.tabIndex=-1;
  var x=document.createElement('button');x.type='button';x.className='prd-x';x.setAttribute('aria-label','Close');x.textContent='✕';
  var fig=document.createElement('div');fig.className='prd-img';fig.innerHTML='<picture><source type="image/webp" srcset="assets/img/rules-detail-3.webp"><img src="assets/img/rules-detail-3.png" width="1500" height="366" alt="Portfolio rules in detail. Weights are the book. They do not get rewritten mid-year because a tape looks ugly. Dividends move on issue day — not when it feels clever. Berkshire Killer and Hodler Jam Sandwich: STRC → BTC. Hedge Fund Killer: STRC → BTC and MSTR at 50/50. Saylor Moon: STRC → MSTR. DCA is monthly. That is the strategy. The point of the book is to stop helping people time the market."></picture>';
  card.appendChild(x);card.appendChild(fig);card.appendChild(d);d.hidden=true;document.body.appendChild(card);d.classList.add('in-card');card.classList.add('has-img');
  var opener=null,sy=0;
  function open(target,from){opener=from||btn;dim.hidden=false;card.hidden=false;btn.setAttribute('aria-expanded','true');
    sy=window.scrollY;document.documentElement.classList.add('prd-lock');
    card.scrollTop=0;var t=target&&document.getElementById(target);if(t&&card.contains(t)){card.scrollTop=Math.max(0,t.offsetTop-70);t.classList.add('prd-hl');setTimeout(function(){t.classList.remove('prd-hl');},1600);}
    var pi=card.querySelector('.prd-img');if(pi&&pi.scrollWidth>pi.clientWidth)pi.scrollLeft=Math.round(pi.scrollWidth*0.335);
    x.focus({preventScroll:true});}
  function close(){if(card.hidden)return;card.hidden=true;dim.hidden=true;btn.setAttribute('aria-expanded','false');document.documentElement.classList.remove('prd-lock');
    window.scrollTo(0,sy);(opener||btn).focus({preventScroll:true});}
  btn.addEventListener('click',function(){open(null,btn);});x.addEventListener('click',close);dim.addEventListener('click',close);
  document.addEventListener('keydown',function(e){if(card.hidden)return;if(e.key==='Escape'){e.preventDefault();close();return;}
    if(e.key==='Tab'){var f=[].slice.call(card.querySelectorAll('button,a[href]'));if(!f.length)return;var a=f[0],z=f[f.length-1];
      if(e.shiftKey&&(document.activeElement===a||document.activeElement===card)){e.preventDefault();z.focus();}else if(!e.shiftKey&&document.activeElement===z){e.preventDefault();a.focus();}}});
  document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[href^="#rule-"]');if(!a||card.contains(a))return;e.preventDefault();open(null,a);});
  var h=location.hash.slice(1);if(/^rule-/.test(h))setTimeout(function(){open(null,btn);},300);
}
/* scroll reveal */
if('IntersectionObserver' in window&&!(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches)){
  var els=[].slice.call(document.querySelectorAll('body > section, main > section')).filter(function(s){return !s.classList.contains('hero')&&s.getBoundingClientRect().top>window.innerHeight;});
  if(location.hash)els=[];
  var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('rv-in');io.unobserve(e.target);}});},{rootMargin:'0px 0px -8% 0px',threshold:0.04});
  els.forEach(function(s){s.classList.add('rv');io.observe(s);});
  setTimeout(function(){els.forEach(function(s){var r=s.getBoundingClientRect();if(r.bottom<0)s.classList.add('rv-in');});},50);
}
})();
