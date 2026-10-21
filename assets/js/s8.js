(function(){var ids=['principles','sleeves','tracker','rules','articles','benchmarks'];if(!('IntersectionObserver' in window))return;
var links=document.querySelectorAll('.mininav a, .header nav a, .mnav-menu a');var vis={};
function mark(id){links.forEach(function(a){var on=a.getAttribute('href')==='#'+id;a.classList.toggle('is-active',on);if(on)a.setAttribute('aria-current','true');else a.removeAttribute('aria-current');});
var a=document.querySelector('.mininav a[href="#'+id+'"]'),n=document.getElementById('miniNav');if(a&&n&&n.offsetParent){var l=a.offsetLeft-12;if(l<n.scrollLeft||a.offsetLeft+a.offsetWidth>n.scrollLeft+n.clientWidth)n.scrollTo({left:l,behavior:'smooth'});}}
var io=new IntersectionObserver(function(es){es.forEach(function(e){vis[e.target.id]=e.isIntersecting;});var c=null;for(var i=0;i<ids.length;i++){if(vis[ids[i]])c=ids[i];}
mark(pick()||c||'');},{rootMargin:'-120px 0px -55% 0px',threshold:0});
function pick(){var best=null,bt=-1e9,lim=Math.min(window.innerHeight*0.4,200);ids.forEach(function(id){var el=document.getElementById(id);if(!el)return;var t=el.getBoundingClientRect().top;if(t<=lim&&t>bt){bt=t;best=id;}});return best;}
var tk=0;window.addEventListener('scroll',function(){if(tk)return;tk=requestAnimationFrame(function(){tk=0;var b=pick();if(b)mark(b);});},{passive:true});
ids.forEach(function(id){var el=document.getElementById(id);if(el)io.observe(el);});})();
