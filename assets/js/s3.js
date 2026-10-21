
// Back to top
const topBtn = document.getElementById('backToTop');
window.addEventListener('scroll', () => {
  topBtn.style.opacity = window.scrollY > 400 ? '1' : '0';
  topBtn.style.pointerEvents = window.scrollY > 400 ? 'auto' : 'none';
});
topBtn?.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
