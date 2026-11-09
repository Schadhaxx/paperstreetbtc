(function(){var b=document.getElementById('mnavBtn'),m=document.getElementById('mnavMenu');if(!b||!m)return;
function set(o){m.hidden=!o;b.setAttribute('aria-expanded',o?'true':'false');b.setAttribute('aria-label',o?'Close section menu':'Open section menu');document.body.classList.toggle('mnav-open',o);document.documentElement.classList.toggle('mnav-open',o);}
b.addEventListener('click',function(e){e.stopPropagation();set(m.hidden);});
m.addEventListener('click',function(e){if(e.target.closest('a'))set(false);});
document.addEventListener('click',function(e){if(!m.hidden&&!m.contains(e.target)&&!b.contains(e.target))set(false);});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!m.hidden){set(false);b.focus();}});
window.addEventListener('resize',function(){if(window.innerWidth>1000&&!m.hidden)set(false);});})();

/* Menu reorg (8 Nov 2026, v3): Sleeves dropdowns — desktop click-to-open
   (.desk-drop) and hamburger tap-to-expand (.mnav-drop). Sleeves only
   opens/closes its menu; it never navigates. */
(function(){
function closeDesk(){document.querySelectorAll('.desk-drop.open').forEach(function(x){x.classList.remove('open');});document.querySelectorAll('.desk-tab').forEach(function(x){x.setAttribute('aria-expanded','false');});}
document.querySelectorAll('.desk-tab').forEach(function(b){
  b.addEventListener('click',function(e){
    e.stopPropagation();
    var d=b.closest('.desk-drop');if(!d)return;
    var wasOpen=d.classList.contains('open');
    closeDesk();
    if(!wasOpen){d.classList.add('open');b.setAttribute('aria-expanded','true');}
  });
});
document.querySelectorAll('.desk-panel a').forEach(function(a){a.addEventListener('click',closeDesk);});
document.addEventListener('click',function(e){if(!e.target.closest('.desk-drop'))closeDesk();});
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeDesk();});
document.querySelectorAll('.mnav-tab').forEach(function(b){
  b.addEventListener('click',function(){
    var d=b.closest('.mnav-drop');if(!d)return;
    var wasOpen=d.classList.contains('open');
    document.querySelectorAll('.mnav-drop.open').forEach(function(x){x.classList.remove('open');});
    document.querySelectorAll('.mnav-tab').forEach(function(x){x.setAttribute('aria-expanded','false');});
    if(!wasOpen){d.classList.add('open');b.setAttribute('aria-expanded','true');}
  });
});
})();
