/* Floating Light/Dark pill beside the Top button.
   Only mounts on pages that have #backToTop (today: index.html). Other
   pages keep the footer "Light version" / "Back to dark" links.
   Opt-in only: no prefers-color-scheme. Text label only — no sun/moon icon.
   The pill is ALWAYS visible. Top keeps its own scroll show/hide (s3.js).
   Top is shifted right by --ps-theme-pill-slot so they sit side by side
   when Top appears, with no layout jump while Top is hidden. */
(function () {
  window.psC = window.psC || function (d, l) {
    return document.documentElement.getAttribute("data-theme") === "light" ? l : d;
  };
  function isLight() {
    return document.documentElement.getAttribute("data-theme") === "light";
  }
  function sync(btn) {
    var on = isLight();
    btn.textContent = on ? "Dark" : "Light";
    btn.setAttribute("aria-label", on ? "Switch to dark mode" : "Switch to light mode");
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  }
  function go() {
    var u = new URL(location.href);
    u.searchParams.set("theme", isLight() ? "dark" : "light");
    location.href = u.toString();
  }
  function sizeSlot(btn) {
    var gap = 0.6 * 16;
    var w = Math.ceil(btn.getBoundingClientRect().width + gap);
    document.documentElement.style.setProperty("--ps-theme-pill-slot", w + "px");
  }
  function mount() {
    if (document.getElementById("psThemePill")) return;
    /* Alongside Top only — do not collide with recap Home / All-recaps fabs. */
    if (!document.getElementById("backToTop")) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ps-theme-pill";
    btn.id = "psThemePill";
    sync(btn);
    btn.addEventListener("click", go);
    document.body.appendChild(btn);
    sizeSlot(btn);
    window.addEventListener("resize", function () { sizeSlot(btn); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
  else mount();
})();
