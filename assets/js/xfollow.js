/* Floating Follow-on-X button: one follow call-to-action at a time; never over card content on phone */
(function(){
  var fab=document.querySelector('.xfab');if(!fab)return;
  /* 13 Nov 2026: the pill always stays pinned at the bottom of the viewport.
     The phone-only "start under the header" move (place() / .xtop) is gone. */
  var inView={},guard=false,ty=0;
  function upd(){
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
