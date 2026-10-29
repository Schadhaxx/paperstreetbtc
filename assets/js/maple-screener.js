// Maple Leaf Screener — leaf double-click / double-tap ONLY.
// This file changes no existing site logic. It only opens the screener
// page when the footer Canadian maple leaf is double-clicked (desktop)
// or double-tapped (iPhone / iPad / Android), and adds a title hint to
// the leaf box. Removing this file's script tag from index.html returns
// the leaf to doing nothing on double-click / double-tap.
//
// Why manual double-detection as well as the native dblclick handler:
// the native dblclick handler alone did not open a tab in a browser test
// of the first version, so two clicks/taps on the leaf within 400ms are
// also detected here. A cooldown guarantees one gesture opens exactly
// one tab, even if dblclick, click and touchend all fire for it.
(function () {
  function bind() {
    var box = document.querySelector('.ca-leaf-box') || document.querySelector('.ca-leaf');
    if (!box) return;
    box.title = 'Double-click for the stock screener';
    // Root cause fix: nav.css sets .ca-leaf-box { pointer-events:none },
    // which otherwise lets clicks/taps pass straight through the leaf so
    // no handler on it can ever fire. This JS-only override in the
    // removable pack file itself makes the leaf clickable; nav.css,
    // index.html and the leaf SVG are untouched.
    box.style.pointerEvents = 'auto';
    box.style.cursor = 'pointer';

    var DOUBLE_MS = 400;      // two taps/clicks within this window count as a double
    var COOLDOWN_MS = 1000;   // one gesture may open at most one tab
    var lastTap = 0;          // timestamp of the previous tap/click on the leaf
    var openedUntil = 0;      // open() is ignored until after this timestamp
    var suppressClickUntil = 0; // synthetic clicks after a touchend are ignored
    var touchStartX = 0, touchStartY = 0, touchMoved = false;

    function openOnce() {
      var now = Date.now();
      if (now < openedUntil) return;
      openedUntil = now + COOLDOWN_MS;
      var w = window.open('screener.html', '_blank');
      if (!w) window.location.href = 'screener.html';
    }

    // Shared double-detection for click and touchend. A single tap/click
    // only arms the timer; it never opens anything, and scrolling is
    // never hijacked (touchend after a move is ignored, see below).
    function onTap(isTouch) {
      var now = Date.now();
      if (isTouch) suppressClickUntil = now + 600;
      if (now - lastTap < DOUBLE_MS) {
        lastTap = 0;
        openOnce();
      } else {
        lastTap = now;
      }
    }

    // Desktop: native double-click, kept exactly as before.
    box.addEventListener('dblclick', function () {
      openOnce();
    });

    // Desktop fallback + the fix for dblclick not firing: manual double-click.
    box.addEventListener('click', function () {
      if (Date.now() < suppressClickUntil) return;
      onTap(false);
    });

    // Mobile: double-tap. touchstart records position so a scroll that
    // starts on the leaf is not mistaken for a tap.
    box.addEventListener('touchstart', function (e) {
      var t = e.touches && e.touches[0];
      if (t) {
        touchStartX = t.clientX;
        touchStartY = t.clientY;
        touchMoved = false;
      }
    }, { passive: true });

    box.addEventListener('touchmove', function (e) {
      var t = e.touches && e.touches[0];
      if (t && (Math.abs(t.clientX - touchStartX) > 10 || Math.abs(t.clientY - touchStartY) > 10)) {
        touchMoved = true;
      }
    }, { passive: true });

    box.addEventListener('touchend', function () {
      if (touchMoved) {
        lastTap = 0;
        return;
      }
      onTap(true);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind);
  else bind();
})();
