/* Floating Follow-on-X button: one follow call-to-action at a time; never over card content on phone */
(function(){
  var fab=document.querySelector('.xfab');if(!fab)return;
  var inView={},guard=false;
  function upd(){
    var hide=inView.xrp;
    if(!hide){
      fab.classList.remove('xhide');var r=fab.getBoundingClientRect();
      var els=document.querySelectorAll('.card,.cards,table,.pulse,.chart-wrap,canvas,.tracker,[class*="price"],footer p,footer .ca-leaf-box,footer .footer-logo');
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
})();
