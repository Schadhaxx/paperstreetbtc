#!/usr/bin/env python3
"""Browser verification for the daily Bollinger Weekly/Daily switch
(Sat 7 Nov 2026). Serves this checkout on 127.0.0.1 and drives the
real screener modal in Chromium.

Checks (all REAL, on the served branch files):
  1. Bollinger toggle on -> weekly bands + note shows weekly SMA.
  2. Weekly/Daily switch hidden until Bollinger is on, visible after.
  3. Daily -> daily file loads, note shows the DAILY SMA (380.42 for
     TSLA last week) and the bands actually change vs weekly.
  4. SPCX (22 weeks) daily bands render.
  5. Phone 390px: no horizontal overflow, switch tappable, bands render.
  6. Missing daily file (route-aborted) -> falls back to weekly with a
     note, modal does not break.
  7. BETA chip still present, no range-stats toggle (fast items intact).
Screenshots to ~/workspace/your_files/daily-bollinger-shots/.

Usage: DB_REPO=<checkout> python3 tests/test_daily_bollinger_browser.py
"""
import os, subprocess, sys, time
from playwright.sync_api import sync_playwright

PORT = 8943
BASE = f"http://127.0.0.1:{PORT}"
CHROME = "/home/hatch/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome"
SHOTS = "/home/hatch/workspace/your_files/daily-bollinger-shots"
REPO = os.environ.get("DB_REPO", "/home/hatch/workspace/ps-daily-boll")

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

def open_modal(page, symbol):
    page.click(f'.card[data-symbol="{symbol}"]')
    page.wait_for_selector("#ind-modal.open", timeout=8000)
    page.wait_for_timeout(1200)

def enh_note(page):
    return page.evaluate("() => { const n = document.getElementById('ind-enh-note'); return n ? n.textContent : ''; }")

def switch_visible(page):
    return page.evaluate("() => { const s = document.getElementById('ind-boll-mode'); return !!s && getComputedStyle(s).display !== 'none'; }")

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME)
        errs = []

        # ===== Desktop 1280px: TSLA weekly -> daily =====
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(BASE + "/screener.html", wait_until="networkidle")
        page.wait_for_timeout(2000)
        check("BETA chip present (fast items intact)",
              page.evaluate("() => !!document.querySelector('.ind-beta')"))
        check("no Range stats toggle (fast items intact)",
              page.evaluate("() => ![...document.querySelectorAll('#ind-enh button')].some(b => /range stats/i.test(b.textContent))"))
        open_modal(page, "TSLA")
        check("switch hidden before Bollinger is on", not switch_visible(page))
        page.click('[data-enh="boll"]')
        page.wait_for_timeout(800)
        check("switch visible once Bollinger is on", switch_visible(page))
        note_w = enh_note(page)
        check("weekly note shows weekly SMA 362.40", "362.40" in note_w, note_w[:120])
        check("weekly note labels mode weekly", "weekly, 20 weeks" in note_w, note_w[:120])
        page.screenshot(path=f"{SHOTS}/tsla-weekly-1280.png")
        page.click('[data-bollmode="daily"]')
        page.wait_for_function(
            "() => { const n = document.getElementById('ind-enh-note'); return n && n.textContent.includes('daily, 20 closes'); }",
            timeout=8000)
        page.wait_for_timeout(500)
        note_d = enh_note(page)
        check("daily note shows daily SMA 380.42", "380.42" in note_d, note_d[:140])
        check("daily note differs from weekly note", note_d != note_w)
        check("daily upper 417.67 in note", "417.67" in note_d, note_d[:140])
        check("daily lower 343.18 in note", "343.18" in note_d, note_d[:140])
        check("Daily button aria-pressed true", page.evaluate(
            "() => document.querySelector('[data-bollmode=\"daily\"]').getAttribute('aria-pressed') === 'true'"))
        page.screenshot(path=f"{SHOTS}/tsla-daily-1280.png")
        # Switch back to weekly: note returns to the weekly values.
        page.click('[data-bollmode="weekly"]')
        page.wait_for_function(
            "() => { const n = document.getElementById('ind-enh-note'); return n && n.textContent.includes('weekly, 20 weeks'); }",
            timeout=5000)
        check("back to weekly restores weekly SMA", "362.40" in enh_note(page))
        page.close()

        # ===== SPCX: 22 weeks, daily bands render =====
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(BASE + "/screener.html", wait_until="networkidle")
        page.wait_for_timeout(2000)
        open_modal(page, "SPCX")
        page.click('[data-enh="boll"]')
        page.wait_for_timeout(600)
        page.click('[data-bollmode="daily"]')
        page.wait_for_function(
            "() => { const n = document.getElementById('ind-enh-note'); return n && n.textContent.includes('daily, 20 closes'); }",
            timeout=8000)
        note_spcx = enh_note(page)
        check("SPCX daily note shows daily SMA 145.24", "145.24" in note_spcx, note_spcx[:140])
        page.screenshot(path=f"{SHOTS}/spcx-daily-1280.png")
        page.close()

        # ===== Phone 390px: TSLA daily, no overflow =====
        page = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(BASE + "/screener.html", wait_until="networkidle")
        page.wait_for_timeout(2000)
        open_modal(page, "TSLA")
        page.click('[data-enh="boll"]')
        page.wait_for_timeout(600)
        check("phone: switch visible once Bollinger is on", switch_visible(page))
        page.click('[data-bollmode="daily"]')
        page.wait_for_function(
            "() => { const n = document.getElementById('ind-enh-note'); return n && n.textContent.includes('daily, 20 closes'); }",
            timeout=8000)
        check("phone: daily note shows daily SMA 380.42", "380.42" in enh_note(page))
        overflow = page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check("phone: no horizontal overflow with daily bands", overflow <= 1, f"overflow {overflow}px")
        page.screenshot(path=f"{SHOTS}/tsla-daily-390.png")
        page.close()

        # ===== Missing daily file: falls back to weekly, modal intact =====
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.route("**/stock-daily-TSLA.json*", lambda route: route.abort())
        page.goto(BASE + "/screener.html", wait_until="networkidle")
        page.wait_for_timeout(2000)
        open_modal(page, "TSLA")
        page.click('[data-enh="boll"]')
        page.wait_for_timeout(600)
        page.click('[data-bollmode="daily"]')
        page.wait_for_function(
            "() => { const n = document.getElementById('ind-enh-note'); return n && n.textContent.includes('Daily data could not be loaded'); }",
            timeout=8000)
        note_fb = enh_note(page)
        check("missing daily file: fallback note shown", "Daily data could not be loaded" in note_fb, note_fb[:140])
        check("missing daily file: weekly bands shown instead", "weekly, 20 weeks" in note_fb, note_fb[:140])
        check("missing daily file: Weekly button re-pressed", page.evaluate(
            "() => document.querySelector('[data-bollmode=\"weekly\"]').getAttribute('aria-pressed') === 'true'"))
        check("missing daily file: modal still open", page.evaluate(
            "() => document.getElementById('ind-modal').classList.contains('open')"))
        page.screenshot(path=f"{SHOTS}/tsla-daily-missing-1280.png")
        page.close()

        browser.close()
        check("no page errors during the whole run", not errs, "; ".join(errs[:3]))
finally:
    srv.terminate()

fails = [r for r in results if not r[1]]
print(f"\n{len(results) - len(fails)}/{len(results)} PASS")
sys.exit(1 if fails else 0)
