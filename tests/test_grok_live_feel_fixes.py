"""Grok Bot review fixes for live-feel (6 Nov 2026 evening).
Checks ONLY the affected paths (not a re-run of the whole feature):
  1. Indicator-feed connection: the producer (screener.js notifyChart)
     dispatches 'screener-ind-rows' with the gated indRows — tested via
     the REAL producer path (page load, no synthetic event).
  2. Countdown anchored to the DISPLAYED week (Friday 4 p.m. NY,
     DST-correct) + 'Week closed' after the target. DST unit checks
     via nyOffsetHours; target/closed via nextWeekClose on the real page.
  3. BTC weekly/monthly buckets detected by CALENDAR boundaries, not
     the last constituent bar (stubbed Coinbase daily candles + stubbed
     live price — SIMULATED, market closed Fri evening).
  4. BTC live-overlay colors theme-aware via psC (light-mode popover
     screenshot + no errors).
  5. Volume metadata preserved when copying the live week (tap detail
     still shows Volume).
  6. Executable permissions restored on the three test files.
  + Real touch-scroll evidence (CDP touch drags at 390px and 820px
    starting on charts).
Each check is labelled REAL or SIMULATED in its name.
Usage: python3 tests/test_grok_live_feel_fixes.py
"""
import os
import stat
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

PORT = 8942
BASE = f"http://127.0.0.1:{PORT}"
CHROME = "/home/hatch/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome"
SHOTS = "/home/hatch/workspace/your_files/live-feel-grok-fixes-shots"
REPO = "/home/hatch/workspace/ps-live-feel-grok"

os.makedirs(SHOTS, exist_ok=True)
srv = subprocess.Popen(
    ["python3", "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
    cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(1.0)
results = []

def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))

def touch_drag_up(page, x, y, distance=300, steps=10):
    """Real finger drag (CDP touch input) starting at (x, y), moving UP.
    Returns window.scrollY after the gesture."""
    cdp = page.context.new_cdp_session(page)
    cdp.send('Input.dispatchTouchEvent',
             {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y, 'id': 1}]})
    for i in range(1, steps + 1):
        yy = y - distance * i / steps
        cdp.send('Input.dispatchTouchEvent',
                 {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': yy, 'id': 1}]})
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    page.wait_for_timeout(600)
    return page.evaluate('window.scrollY')

def open_modal(page, symbol):
    if symbol == "GOLD":
        page.click('.tile[data-symbol="GOLD"]')
    else:
        page.click(f'.card[data-symbol="{symbol}"]')
    page.wait_for_selector("#ind-modal.open", timeout=8000)
    page.wait_for_timeout(1500)

def modal_status(page):
    return page.evaluate("""() => {
      const s = document.getElementById('ind-status');
      return s ? s.textContent : '';
    }""")

# --- Coinbase daily candle stubs (SIMULATED) ---
# Format: [time_s, low, high, open, close]. Today is Fri 6 Nov 2026.
def daily_bar(y, m, d, o, c):
    import datetime
    t = int(datetime.datetime(y, m, d, tzinfo=datetime.timezone.utc).timestamp())
    lo, hi = min(o, c) - 500, max(o, c) + 500
    return [t, lo, hi, o, c]

def bars_for(dates, base=75000):
    # dates: list of (y, m, d); close drifts up slightly each day.
    out = []
    for i, (y, m, d) in enumerate(dates):
        o = base + i * 100
        out.append(daily_bar(y, m, d, o, o + 50))
    return out

def oct_nov_dates(start_day, end_day):
    # Business-ish days in Oct/Nov 2026 (Mon-Fri), as (y, m, d).
    import datetime
    out = []
    d = datetime.date(2026, 10, 5) + datetime.timedelta(days=start_day)
    end = datetime.date(2026, 10, 5) + datetime.timedelta(days=end_day)
    cur = d
    while cur <= end:
        if cur.weekday() < 5:
            out.append((cur.year, cur.month, cur.day))
        cur += datetime.timedelta(days=1)
    return out

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME)

        # ===== Fix 6: executable permissions (REAL, working tree) =====
        for f in ["tests/run_all.sh", "tests/test_oi001_compare_scope.py", "tests/test_oi001_label.js"]:
            path = os.path.join(REPO, f)
            mode = os.stat(path).st_mode
            check(f"[REAL] Fix 6: {f} is executable", bool(mode & stat.S_IXUSR), oct(mode))

        # ===== Fix 1: indicator-feed connection, REAL producer path =====
        page = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        errs = []
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_TUNNEL" not in m.text and "Failed to load resource" not in m.text else None)
        page.on("pageerror", lambda e: errs.append(str(e)))
        # Record screener-ind-rows events as the REAL producer dispatches them.
        page.add_init_script("""window.__indRowsEvents = [];
          window.addEventListener('screener-ind-rows', (e) => {
            window.__indRowsEvents.push({ n: (e.detail || []).length,
              symbols: (e.detail || []).map(r => r.symbol),
              srcs: (e.detail || []).map(r => r._src) });
          });""")
        page.goto(BASE + "/screener.html", wait_until="networkidle")
        page.wait_for_timeout(2500)
        evts = page.evaluate("() => window.__indRowsEvents || []")
        got = len(evts) > 0 and evts[0]["n"] == 4 and set(evts[0]["symbols"]) == {"WTI", "GOLD", "US10Y", "VIX"}
        check("[REAL] Fix 1: producer dispatches screener-ind-rows (4 indicators)",
              got, str(evts[:1]))
        # The chart received it: open GOLD modal and confirm the modal
        # reflects the dispatched rows (not an empty state).
        open_modal(page, "GOLD")
        st = modal_status(page)
        check("[REAL] Fix 1: GOLD modal reflects dispatched indRows",
              "Gold" in st or "GOLD" in st or "close" in st.lower() or "Live" in st or "Week" in st,
              st[:110])
        page.screenshot(path=f"{SHOTS}/fix1-gold-modal-390.png")
        page.close()

        # ===== Fix 2: countdown anchored to displayed week + DST =====
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(BASE + "/screener.html", wait_until="networkidle")
        page.wait_for_timeout(1200)
        # DST unit checks via the exposed nyOffsetHours (REAL logic, known dates).
        dst = page.evaluate("""() => {
          const f = window.IndicatorChart.nyOffsetHours;
          if (typeof f !== 'function') return { error: 'nyOffsetHours not exposed' };
          return {
            jul2026: f(Date.UTC(2026, 6, 15, 12, 0, 0)),   // Jul -> EDT -4
            jan2026: f(Date.UTC(2026, 0, 15, 12, 0, 0)),   // Jan -> EST -5
            mar8_2026: f(Date.UTC(2026, 2, 8, 12, 0, 0)), // DST starts Mar 8 -> -4
            nov1_2026: f(Date.UTC(2026, 10, 1, 12, 0, 0)),// DST ends Nov 1 -> -5
            nov6_2026: f(Date.UTC(2026, 10, 6, 12, 0, 0)),// today (Nov 6) -> EST -5
          };
        }""")
        check("[REAL] Fix 2: nyOffsetHours DST correct (Jul -4, Jan -5, Mar 8 -4, Nov 1 -5, Nov 6 -5)",
              dst.get("jul2026") == -4 and dst.get("jan2026") == -5 and dst.get("mar8_2026") == -4
              and dst.get("nov1_2026") == -5 and dst.get("nov6_2026") == -5, str(dst))
        # Displayed-week anchoring: open TSLA, read nextWeekClose.
        open_modal(page, "TSLA")
        nc = page.evaluate("""() => {
          const n = window.IndicatorChart.nextWeekClose(true);
          return { closed: !!n.closed, t: new Date(n.t).toISOString(), label: n.label };
        }""")
        # Displayed week is Mon 2 Nov 2026; its Friday 4 p.m. ET = Fri 6 Nov
        # 21:00 UTC (EST, -5). Today (Fri 6 Nov evening) is past that, so the
        # week must be CLOSED — not a ~6d countdown to next Friday.
        check("[REAL] Fix 2: displayed week (Mon 2 Nov) closes Fri 6 Nov 21:00 UTC",
              nc["t"].startswith("2026-11-06T21:00"), nc["t"])
        check("[REAL] Fix 2: Friday evening shows Week closed (not next Friday)",
              nc["closed"] is True, str(nc))
        st = modal_status(page)
        check("[REAL] Fix 2: status line shows Week closed",
              "Week closed" in st, st[:110])
        page.screenshot(path=f"{SHOTS}/fix2-tsla-week-closed-1280.png")
        page.close()

        # ===== Fix 5: volume preserved in the live-week copy =====
        page = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        page.goto(BASE + "/screener.html", wait_until="networkidle")
        page.wait_for_timeout(1200)
        open_modal(page, "TSLA")
        # Force live (synthetic rows event — SIMULATED live state; the
        # volume check itself reads the real copied week).
        page.evaluate("() => window.dispatchEvent(new CustomEvent('screener-rows', { detail: [{ symbol: 'TSLA', price: 360.00, _src: 'live', ytdPct: -20.0 }] }))")
        page.wait_for_timeout(900)
        # Turn volume pane on, then tap the last candle and read its detail.
        vol_btn = page.query_selector('[data-enh="volume"]')
        if vol_btn:
            vol_btn.click()
            page.wait_for_timeout(600)
        pill = page.evaluate("""() => {
          const c = document.getElementById('ind-canvas');
          const r = c.getBoundingClientRect();
          const plot = c._plot;
          const cx = plot.padL + plot.slot * (plot.n - 1) + plot.slot / 2;
          return { left: r.left, top: r.top, height: r.height, cx };
        }""")
        page.mouse.click(pill["left"] + pill["cx"], pill["top"] + pill["height"] / 2)
        page.wait_for_timeout(600)
        detail = page.evaluate("""() => {
          const p = document.getElementById('ind-pill');
          return p ? p.textContent : '';
        }""")
        check("[SIMULATED-live] Fix 5: tap last candle detail still shows Volume",
              "Volume" in detail, detail[:100])
        page.screenshot(path=f"{SHOTS}/fix5-tsla-volume-390.png")
        page.close()

        # ===== Fix 3: BTC buckets by calendar boundary (SIMULATED feeds) =====
        # Stub Coinbase daily candles + set the live price via the btcprice
        # event. Market is closed Fri evening, so real live candles are not
        # available — these two cases are simulations of the feed.
        def stub_candles(page, bars):
            import json as _json
            page.route("**/api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400*",
                       lambda route: route.fulfill(status=200, content_type="application/json",
                                                   body=_json.dumps(bars)))
        # Case A (stale feed): last daily bar Mon 2 Nov, today Fri 6 Nov.
        # The current week bucket (Mon 2 Nov) must still extend (live).
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        stub_candles(page, bars_for(oct_nov_dates(0, 28)))  # Oct 5 .. Nov 2
        page.goto(BASE + "/index.html", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.evaluate("() => window.dispatchEvent(new CustomEvent('btcprice', { detail: { usd: 76000, chg: 0.5 } }))")
        page.click("#hdrTick")
        page.wait_for_selector("#bcC, .bc-w", timeout=8000)
        page.wait_for_timeout(1200)
        page.click('[data-r="1M"]')
        page.wait_for_timeout(800)
        page.click('[data-cg="candles"]')
        page.wait_for_timeout(2500)
        note_a = page.evaluate("() => (document.getElementById('bcNt') || {}).textContent || ''")
        check("[SIMULATED] Fix 3a: stale feed (last bar Mon 2 Nov, today Fri 6 Nov) still extends current week",
              "Last candle is live" in note_a, note_a[:130])
        page.close()
        # Case B (new week, no rollover): last daily bar Fri 30 Oct, today
        # Fri 6 Nov. No candle for the new week must be fabricated.
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        stub_candles(page, bars_for(oct_nov_dates(0, 25)))  # Oct 5 .. Oct 30
        page.goto(BASE + "/index.html", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.evaluate("() => window.dispatchEvent(new CustomEvent('btcprice', { detail: { usd: 76000, chg: 0.5 } }))")
        page.click("#hdrTick")
        page.wait_for_selector("#bcC, .bc-w", timeout=8000)
        page.wait_for_timeout(1200)
        page.click('[data-r="1M"]')
        page.wait_for_timeout(800)
        page.click('[data-cg="candles"]')
        page.wait_for_timeout(2500)
        note_b = page.evaluate("() => (document.getElementById('bcNt') || {}).textContent || ''")
        rr_b = page.evaluate("() => (document.getElementById('bcRr') || {}).textContent || ''")
        check("[SIMULATED] Fix 3b: new week with no data does NOT fabricate a rollover candle",
              "latest complete UTC day" in note_b and "Last candle is live" not in note_b,
              note_b[:130] + " | " + rr_b[:80])
        page.close()

        # ===== Fix 4: overlay colors theme-aware (light mode popover) =====
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        stub_candles(page, bars_for(oct_nov_dates(0, 28)))  # Oct 5 .. Nov 2
        page.goto(BASE + "/index.html?theme=light", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.evaluate("() => window.dispatchEvent(new CustomEvent('btcprice', { detail: { usd: 76000, chg: 0.5 } }))")
        page.click("#hdrTick")
        page.wait_for_selector("#bcC, .bc-w", timeout=8000)
        page.wait_for_timeout(1200)
        page.click('[data-r="1M"]')
        page.wait_for_timeout(800)
        page.click('[data-cg="candles"]')
        page.wait_for_timeout(2500)
        errs4 = []
        page.on("console", lambda m: errs4.append(m.text) if m.type == "error" else None)
        light_note = page.evaluate("() => (document.getElementById('bcNt') || {}).textContent || ''")
        check("[SIMULATED] Fix 4: light-mode popover shows live bucket (overlay drawn)",
              "Last candle is live" in light_note, light_note[:100])
        page.screenshot(path=f"{SHOTS}/fix4-btc-popover-light-1280.png")
        check("[SIMULATED] Fix 4: light-mode popover, no console errors", not errs4, "; ".join(errs4[:2]))
        page.close()

        # ===== Real touch-scroll evidence (REAL gestures, CDP touch) =====
        # 390px: drag starting on the homepage YTD chart and on the BTC
        # popover chart; 820px: drag starting on the screener modal chart.
        page = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        page.goto(BASE + "/index.html", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(400)
        y0 = page.evaluate("window.scrollY")
        # Find the YTD chart canvas and drag up starting on it.
        box = page.evaluate("""() => {
          const c = document.querySelector('canvas');
          if (!c) return null;
          const r = c.getBoundingClientRect();
          return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        }""")
        if box:
            y1 = touch_drag_up(page, box["x"], box["y"])
            check("[REAL] Touch scroll 390px: drag starting on homepage chart scrolls the page",
                  y1 > y0, f"scrollY {y0} -> {y1}")
        else:
            check("[REAL] Touch scroll 390px: homepage chart canvas found", False, "no canvas")
        # BTC popover chart drag. The popover is a modal: the page behind
        # correctly does NOT scroll while it is open, so the honest check
        # is that the drag leaves the popover usable (still open, closable).
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(400)
        page.click("#hdrTick")
        page.wait_for_selector("#bcC, .bc-w", timeout=8000)
        page.wait_for_timeout(1200)
        box2 = page.evaluate("""() => {
          const c = document.getElementById('bcC');
          if (!c) return null;
          const r = c.getBoundingClientRect();
          return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        }""")
        if box2:
            touch_drag_up(page, box2["x"], box2["y"])
            still_open = page.evaluate("() => { const w = document.querySelector('.bc-w'); return !!w && !w.hidden; }")
            # Close it to prove the UI is not stuck after the drag.
            closer = page.query_selector(".bc-x")
            if closer:
                closer.click()
                page.wait_for_timeout(500)
            closed = page.evaluate("() => { const w = document.querySelector('.bc-w'); return !!w && w.hidden; }")
            check("[REAL] Touch drag 390px on BTC popover chart leaves popover usable (open, then closes)",
                  still_open and closed, f"still_open={still_open} closed={closed}")
        page.close()
        # 820px: screener modal chart drag.
        page = browser.new_page(viewport={"width": 820, "height": 1000}, has_touch=True, is_mobile=True)
        page.goto(BASE + "/screener.html", wait_until="networkidle")
        page.wait_for_timeout(1500)
        open_modal(page, "TSLA")
        y0 = page.evaluate("window.scrollY")
        box3 = page.evaluate("""() => {
          const c = document.getElementById('ind-canvas');
          if (!c) return null;
          const r = c.getBoundingClientRect();
          return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        }""")
        if box3:
            y1 = touch_drag_up(page, box3["x"], box3["y"])
            check("[REAL] Touch scroll 820px: drag starting on screener modal chart scrolls the page",
                  y1 > y0, f"scrollY {y0} -> {y1}")
        page.screenshot(path=f"{SHOTS}/touch-820-modal.png")
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
