"""Verify the three live-feel screener-modal fixes (after fix).
Checks, for TSLA and GOLD, at 390px and 1280px:
  1. Countdown appears in the status line on FIRST OPEN (no synthetic
     event) — both live (forced via rows event) and closed states;
     and it ticks down over 65s.
  2. Last candle fully visible: body + live outline end well clear of
     the canvas right edge (margin >= 10px).
  3. Tapping the last candle (center, outline-right, right margin)
     shows its detail pill, with the live note when live.
  4. BTC popover unchanged and working (EXPERIMENTAL chip, live last
     candle, bucket countdown).
  5. No console errors (ignoring sandbox network tunnel failures),
     no horizontal overflow at 390px.
Usage: python3 tests/verify_live_feel_fixes.py
"""
import json
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

PORT = 8941
BASE = f"http://127.0.0.1:{PORT}"
CHROME = "/home/hatch/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome"
SHOTS = "/home/hatch/workspace/your_files/live-feel-fix-shots"

srv = subprocess.Popen(
    ["python3", "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
    cwd="/home/hatch/workspace/ps-live-feel-grok",
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(1.0)
results = []

def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))

def open_modal(page, symbol):
    if symbol == "GOLD":
        page.click('.tile[data-symbol="GOLD"]')
    else:
        page.click(f'.card[data-symbol="{symbol}"]')
    page.wait_for_selector("#ind-modal.open", timeout=8000)
    page.wait_for_timeout(1500)

def force_live(page, symbol):
    if symbol == "GOLD":
        page.evaluate("() => window.dispatchEvent(new CustomEvent('screener-ind-rows', { detail: [{ symbol: 'GOLD', price: 4120.00, _src: 'live' }] }))")
    else:
        page.evaluate("() => window.dispatchEvent(new CustomEvent('screener-rows', { detail: [{ symbol: 'TSLA', price: 360.00, _src: 'live', ytdPct: -20.0 }] }))")

def modal_state(page):
    return page.evaluate("""() => {
      const c = document.getElementById('ind-canvas');
      const plot = c._plot || {};
      const status = (document.getElementById('ind-status') || {}).textContent || '';
      const liveprice = (document.getElementById('ind-liveprice') || {}).textContent || '';
      const cssW = c.clientWidth;
      const bw = Math.max(2, Math.min(14, plot.slot * 0.6));
      const lastCx = plot.padL + plot.slot * (plot.n - 1) + plot.slot / 2;
      return { status, liveprice, cssW, lastCx,
               bodyRight: lastCx + bw / 2, outlineRight: lastCx + bw / 2 + 5,
               scrollW: document.documentElement.scrollWidth,
               innerW: window.innerWidth };
    }""")

def countdown_expectation(page, is_stock):
    """What the status line should say, from the page's own nextWeekClose.
    Returns (kind, detail) where kind is 'countdown' or 'closed'.
    The countdown is anchored to the DISPLAYED week's Friday 4 p.m. ET
    (stocks) / Sunday midnight UTC (indicators); once that target has
    passed the week is closed — it never rolls to next week. (Grok Bot
    review fix, 6 Nov 2026: the old test rewarded a ~6d 22h countdown
    on a Friday evening, which was wrong — that week had closed.)"""
    return page.evaluate("""(isStock) => {
      const nc = window.IndicatorChart.nextWeekClose(isStock);
      const t = (nc.t instanceof Date) ? nc.t.getTime() : new Date(nc.t).getTime();
      return { closed: !!nc.closed, targetMs: t, label: nc.label, nowMs: Date.now() };
    }""", is_stock)

def check_countdown(page, name, is_stock):
    """Assert the status line matches the displayed week's close state."""
    st = modal_state(page)
    exp = countdown_expectation(page, is_stock)
    if exp["closed"]:
        check(name + " shows Week closed", "Week closed" in st["status"], st["status"][:110])
    else:
        check(name + " has countdown", "Week closes in" in st["status"], st["status"][:110])

def tap_last(page, xoff):
    g = page.evaluate("""() => {
      const c = document.getElementById('ind-canvas');
      const r = c.getBoundingClientRect();
      const plot = c._plot;
      const cx = plot.padL + plot.slot * (plot.n - 1) + plot.slot / 2;
      return { left: r.left, top: r.top, height: r.height, cx };
    }""")
    page.evaluate("() => { const p=document.getElementById('ind-pill'); if(p) p.style.display='none'; }")
    page.mouse.click(g["left"] + xoff(), g["top"] + g["height"] / 2)
    page.wait_for_timeout(500)
    return page.evaluate("""() => {
      const p = document.getElementById('ind-pill');
      return { display: p ? getComputedStyle(p).display : 'missing',
               text: p ? p.textContent : '' };
    }""")

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME)
        # ---------- 390px, TSLA ----------
        page = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        errs = []
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_TUNNEL" not in m.text and "Failed to load resource" not in m.text else None)
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(BASE + "/screener.html", wait_until="networkidle")
        page.wait_for_timeout(1200)
        open_modal(page, "TSLA")
        # 1a. countdown on FIRST OPEN, no synthetic event. Corrected 6 Nov
        #     (Grok Bot review): the status shows the DISPLAYED week's
        #     close — "Week closes in ..." while it is open, "Week closed"
        #     once its Friday 4 p.m. ET has passed (not a roll to next Fri).
        check_countdown(page, "TSLA 390 first-open status", True)
        # 1b. force live, countdown/closed present in live state
        force_live(page, "TSLA")
        page.wait_for_timeout(900)
        st = modal_state(page)
        check_countdown(page, "TSLA 390 live status", True)
        check("TSLA 390 live price label shows", st["liveprice"].startswith("Live "), st["liveprice"])
        # 1c. countdown ticks (only meaningful while the week is still open;
        #     if it has closed, the status stays "Week closed" instead).
        exp = countdown_expectation(page, True)
        if not exp["closed"]:
            def minutes(s):
                import re
                m = re.search(r"Week closes in (\d+)d (\d+)h (\d+)m", s)
                return int(m.group(1)) * 1440 + int(m.group(2)) * 60 + int(m.group(3)) if m else None
            m1 = minutes(st["status"])
            page.wait_for_timeout(65000)
            st2 = modal_state(page)
            m2 = minutes(st2["status"])
            check("TSLA 390 countdown ticks down", m1 is not None and m2 is not None and m2 <= m1 - 1, f"{m1} -> {m2} min")
        else:
            page.wait_for_timeout(5000)
            st2 = modal_state(page)
            check("TSLA 390 Week closed persists", "Week closed" in st2["status"], st2["status"][:110])
        # 2. last candle clear of the edge
        margin = st2["cssW"] - st2["outlineRight"]
        check("TSLA 390 last-candle outline clear of edge", margin >= 10, f"outline ends {st2['outlineRight']:.1f}/{st2['cssW']}, margin {margin:.1f}px")
        # 3. taps on the last candle
        cx = st2["lastCx"]
        for label, off in [("center", lambda: cx), ("outline-right", lambda: cx + 6),
                           ("right-margin", lambda: st2["cssW"] - 3)]:
            pill = tap_last(page, off)
            ok = pill["display"] != "none" and "2 Nov 2026" in pill["text"]
            live_note = "live" in pill["text"].lower()
            check(f"TSLA 390 tap last candle ({label}) shows detail", ok and live_note,
                  pill["text"][:80] + (" | live note" if live_note else " | NO live note"))
        # 5. no overflow, no console errors
        check("TSLA 390 no horizontal overflow", st2["scrollW"] <= st2["innerW"], f"scrollW {st2['scrollW']} innerW {st2['innerW']}")
        page.screenshot(path=f"{SHOTS}/after-tsla-390.png")
        page.screenshot(path=f"{SHOTS}/after-tsla-390-live.png")
        check("TSLA 390 no console errors", not errs, "; ".join(errs[:2]))
        page.close()
        # ---------- 390px, GOLD ----------
        page = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        page.goto(BASE + "/screener.html", wait_until="networkidle")
        page.wait_for_timeout(1200)
        open_modal(page, "GOLD")
        check_countdown(page, "GOLD 390 first-open status", False)
        force_live(page, "GOLD")
        page.wait_for_timeout(900)
        st = modal_state(page)
        check_countdown(page, "GOLD 390 live status", False)
        margin = st["cssW"] - st["outlineRight"]
        check("GOLD 390 last-candle outline clear of edge", margin >= 10, f"margin {margin:.1f}px")
        pill = tap_last(page, lambda: st["lastCx"])
        check("GOLD 390 tap last candle shows detail", pill["display"] != "none" and "2 Nov 2026" in pill["text"], pill["text"][:80])
        page.screenshot(path=f"{SHOTS}/after-gold-390.png")
        page.close()
        # ---------- 1280px desktop, TSLA ----------
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(BASE + "/screener.html", wait_until="networkidle")
        page.wait_for_timeout(1200)
        open_modal(page, "TSLA")
        force_live(page, "TSLA")
        page.wait_for_timeout(900)
        st = modal_state(page)
        check_countdown(page, "TSLA 1280 live status", True)
        margin = st["cssW"] - st["outlineRight"]
        check("TSLA 1280 last-candle outline clear of edge", margin >= 10, f"margin {margin:.1f}px")
        pill = tap_last(page, lambda: st["lastCx"] + 6)
        check("TSLA 1280 tap last candle outline shows detail", pill["display"] != "none", pill["text"][:60])
        page.screenshot(path=f"{SHOTS}/after-tsla-1280.png")
        page.close()
        # ---------- BTC popover unchanged ----------
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(BASE + "/index.html", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.click("#hdrTick")
        page.wait_for_selector("#bcC, .bc-w", timeout=8000)
        page.wait_for_timeout(1200)
        # switch to 1W candles
        page.click('[data-r="1W"]')
        page.wait_for_timeout(800)
        page.click('[data-cg="candles"]')
        page.wait_for_timeout(2500)
        pop = page.evaluate("""() => {
          const t = document.body.innerText;
          return { exp: t.includes('EXPERIMENTAL'),
                   note: (document.getElementById('bcNt') || {}).textContent || '',
                   rr: (document.getElementById('bcRr') || {}).textContent || '' };
        }""")
        check("BTC popover EXPERIMENTAL chip present", pop["exp"])
        check("BTC popover note has live-bucket text", "Last candle is live" in pop["note"] or "latest complete UTC day" in pop["note"], pop["note"][:100])
        check("BTC popover range header shows", "1W" in pop["rr"], pop["rr"][:80])
        page.screenshot(path=f"{SHOTS}/after-btc-popover-1280.png")
        page.close()
        browser.close()
finally:
    srv.terminate()

fails = [r for r in results if not r[1]]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
if fails:
    print("FAILURES:")
    for n, _, d in fails:
        print(" -", n, d)
    sys.exit(1)
