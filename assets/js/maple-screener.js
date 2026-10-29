// Maple Leaf Screener — leaf double-click ONLY.
// This file changes no existing site logic. It only opens the screener
// page when the footer Canadian maple leaf is double-clicked, and adds
// a title hint to the leaf box. Removing this file's script tag from
// index.html returns the leaf to doing nothing on double-click.
(function () {
  function bind() {
    var box = document.querySelector('.ca-leaf-box') || document.querySelector('.ca-leaf');
    if (!box) return;
    box.title = 'Double-click for the stock screener';
    box.addEventListener('dblclick', function () {
      window.open('screener.html', '_blank');
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind);
  else bind();
})();
