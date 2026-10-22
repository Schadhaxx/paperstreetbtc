/* Floating Follow-on-X button: one follow call-to-action at a time; never over card content on phone */
(function(){
  var fab=document.querySelector('.xfab');if(!fab)return;
  var inView={},guard=false,ty=0;
  var mq=window.matchMedia?matchMedia('(max-width:640px)'):null;
  function place(){
    if(mq&&mq.matches&&window.scrollY<=10){
      var h=document.querySelector('.header');var hb=h?h.getBoundingClientRect().bottom:0;
      ty=Math.round(hb+8-fab.offsetTop);fab.style.setProperty('--xty',ty+'px');fab.classList.add('xtop');
    }else{ty=0;fab.classList.remove('xtop');}
  }
  function upd(){
    place();
    var hide=inView.xrp||!!document.querySelector('.article-modal:not([hidden])');
    if(!hide){
      var r={left:fab.offsetLeft,right:fab.offsetLeft+fab.offsetWidth,top:fab.offsetTop+ty,bottom:fab.offsetTop+ty+fab.offsetHeight};
      var els=document.querySelectorAll('.card,.cards,table,.pulse,.chart-wrap,canvas,.tracker,[class*="price"],footer p,footer .ca-leaf-box,footer .footer-logo,.xpill');
      for(var i=0;i<els.length;i++){var e=els[i];if(e===fab||fab.contains(e)||e.closest('.header,.xfab,.bc-pop,.bc-sheet'))continue;var q=e.getBoundingClientRect();
        if(q.width&&q.height&&q.left<r.right&&q.right>r.left&&q.top<r.bottom&&q.bottom>r.top){hide=true;break;}}
    }
    fab.classList.toggle('xhide',!!hide);
  }
  if('IntersectionObserver'in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){inView.xrp=e.isIntersecting;});upd();});
    ['#xrp'].forEach(function(s){var el=document.querySelector(s);if(el)io.observe(el);});
  }
  function onS(){if(guard)return;guard=true;requestAnimationFrame(function(){guard=false;upd();});}
  addEventListener('scroll',onS,{passive:true});addEventListener('resize',onS);upd();
  if('MutationObserver'in window)new MutationObserver(onS).observe(document.body,{childList:true});
})();
