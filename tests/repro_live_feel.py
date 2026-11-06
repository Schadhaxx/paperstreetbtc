"""Reproduce the three live-feel screener-modal niggles (before fix).
Serves the branch locally, opens the TSLA modal, forces the live state
by dispatching a screener-rows event with a live row, then checks:
  1. status line has a week-close countdown in the live state
  2. last candle fully visible (not clipped at the right edge)
  3. tapping the last candle shows its detail pill
Usage: python3 tests/repro_live_feel.py [tsla|gold]
"""
import json
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

SYMBOL = (sys.argv[1] if len(sys.argv) > 1 else "tsla").upper()
PORT = 8931
BASE = f"http://127.0.0.1:{PORT}"

# start a static server rooted at the branch
srv = subprocess.Popen(
    ["python3", "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
    cwd="/home/hatch/workspace/ps-live-feel",
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(1.0)

def force_live(page):
    """Dispatch the rows event the modal listens to, with a live row."""
    if SYMBOL == "GOLD":
        page.evaluate(
            "() => window.dispatchEvent(new CustomEvent('screener-ind-rows',"
            " { detail: [{ symbol: 'GOLD', price: 4120.00, _src: 'live' }] }))"
        )
    else:
        page.evaluate(
            "() => window.dispatchEvent(new CustomEvent('screener-rows',"
            " { detail: [{ symbol: 'TSLA', price: 360.00, _src: 'live',"
            " ytdPct: -20.0, ytdBasis: 'ytd' }] }))"
        )

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/home/hatch/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome")
        page = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE + "/screener.html", wait_until="networkidle")
        page.wait_for_timeout(1200)
        # open the modal: click the TSLA card / GOLD tile
        if SYMBOL == "GOLD":
            page.click('.tile[data-symbol="GOLD"]')
        else:
            page.click('.card[data-symbol="TSLA"]')
        page.wait_for_selector("#ind-modal.open", timeout=8000)
        page.wait_for_timeout(1500)
        # force the live state
        force_live(page)
        page.wait_for_timeout(1200)
        # --- check 1: countdown in the live state ---
        status = page.text_content("#ind-status") or ""
        liveprice = page.text_content("#ind-liveprice") or ""
        print("STATUS:", json.dumps(status))
        print("LIVEPRICE:", json.dumps(liveprice))
        print("CHECK1 countdown present:", "Week closes in" in status)
        # --- check 2: last candle clipping (geometry + pixels) ---
        geo = page.evaluate("""() => {
          const c = document.getElementById('ind-canvas');
          const plot = c._plot;
          if (!plot) return { plot: null };
          const cssW = c.clientWidth;
          const slot = plot.slot, n = plot.n, padL = plot.padL;
          const bw = Math.max(2, Math.min(14, slot * 0.6));
          const cx = padL + slot * (n - 1) + slot / 2;
          // sample the canvas pixels: any non-background pixel in the
          // rightmost 3 columns of the candle band?
          const ctx = c.getContext('2d');
          const dpr = window.devicePixelRatio || 1;
          const img = ctx.getImageData(Math.round((cssW - 3) * dpr), 0, Math.round(3 * dpr), c.height).data;
          let edgePx = 0;
          for (let i = 0; i < img.length; i += 4) {
            const r = img[i], g = img[i+1], b = img[i+2];
            if (!(r === 11 && g === 18 && b === 38)) edgePx++;
          }
          return { cssW, padL, slot, n, bw, lastCx: cx,
                   bodyRight: cx + bw / 2, outlineRight: cx + bw / 2 + 5,
                   edgePx };
        }""")
        print("GEO:", json.dumps(geo))
        print("CHECK2 body inside canvas:", geo.get("bodyRight", 999) <= geo.get("cssW", 0))
        print("CHECK2 outline inside canvas:", geo.get("outlineRight", 999) <= geo.get("cssW", 0))
        # --- check 3: tap the last candle ---
        tap = page.evaluate("""() => {
          const c = document.getElementById('ind-canvas');
          const plot = c._plot;
          const rect = c.getBoundingClientRect();
          const cx = plot.padL + plot.slot * (plot.n - 1) + plot.slot / 2;
          const cy = rect.top + rect.height / 2;
          return { x: rect.left + cx, y: cy, rectLeft: rect.left, rectTop: rect.top };
        }""")
        page.mouse.click(tap["x"], tap["y"])
        page.wait_for_timeout(600)
        pill = page.evaluate("""() => {
          const p = document.getElementById('ind-pill');
          return { display: p ? getComputedStyle(p).display : 'missing',
                   text: p ? p.textContent.slice(0, 120) : '' };
        }""")
        print("PILL:", json.dumps(pill))
        print("CHECK3 pill visible after last-candle tap:", pill["display"] != "none")
        # screenshots
        page.screenshot(path=f"/home/hatch/workspace/your_files/live-feel-fix-shots/repro-{SYMBOL.lower()}-390.png")
        print("CONSOLE ERRORS:", errors if errors else "none")
        browser.close()
finally:
    srv.terminate()
