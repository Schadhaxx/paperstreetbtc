
// Back to top
const topBtn = document.getElementById('backToTop');
const topOwl = document.getElementById('topOwl');
function sizeTopOwl() {
  if (!topBtn || !topOwl) return;
  topOwl.style.setProperty('--top-btn-w', topBtn.offsetWidth + 'px');
  topOwl.style.setProperty('--top-btn-h', topBtn.offsetHeight + 'px');
}
sizeTopOwl();
window.addEventListener('resize', sizeTopOwl);
window.addEventListener('load', sizeTopOwl);
window.addEventListener('scroll', () => {
  const on = window.scrollY > 400;
  topBtn.style.opacity = on ? '1' : '0';
  topBtn.style.pointerEvents = on ? 'auto' : 'none';
  if (topOwl) { topOwl.style.opacity = on ? '1' : '0'; topOwl.style.pointerEvents = on ? 'auto' : 'none'; }
});
topOwl?.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
topBtn?.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
