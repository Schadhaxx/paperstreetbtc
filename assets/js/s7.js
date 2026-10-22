(function(){var b=document.getElementById('mnavBtn'),m=document.getElementById('mnavMenu');if(!b||!m)return;
function set(o){m.hidden=!o;b.setAttribute('aria-expanded',o?'true':'false');b.setAttribute('aria-label',o?'Close section menu':'Open section menu');document.body.classList.toggle('mnav-open',o);}
b.addEventListener('click',function(e){e.stopPropagation();set(m.hidden);});
m.addEventListener('click',function(e){if(e.target.closest('a'))set(false);});
document.addEventListener('click',function(e){if(!m.hidden&&!m.contains(e.target)&&!b.contains(e.target))set(false);});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!m.hidden){set(false);b.focus();}});
window.addEventListener('resize',function(){if(window.innerWidth>1000&&!m.hidden)set(false);});})();
