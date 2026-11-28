/* Chart chrome follows data-theme. Dark mode keeps the original color strings.
   Since 20 Nov 2026 every chart on the site is native canvas (Chart.js was
   removed), so this file only provides the psC(dark, light) colour helper
   the native charts read at draw time. */
(function () {
  window.psC = window.psC || function (dark, light) {
    return document.documentElement.getAttribute("data-theme") === "light" ? light : dark;
  };
})();
