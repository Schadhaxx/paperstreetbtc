"""Bars/Day float-label fix — verification test (6 Nov 2026).

Bug: with only the default 2 stocks selected (MSTR + IBIT), the Bars/Day
x-axis labels showed unrounded floats ("-0.35000000000000003%").
Fix: the Bars x-axis tick callback (and the line-chart y-axis callback,
same pattern) now use CmpMath.fmtPct, which rounds to 2 decimals.

Serves two trees over HTTP and compares them:
  BEFORE: a pristine main checkout (old screener-chart.js, cmp5)
  AFTER:  this branch (fixed screener-chart.js, cmp6)
Checks, at desktop 1280px and phone 390px:
  1. Bars/Day with 2 stocks: no axis label has >2 decimal places.
  2. Bars/Day with all 7 stocks: axis still clean.
  3. Bar values (datasets) are identical before vs after (fix is
     label-only, no data/bar change).
  4. No console errors on the screener.
Usage: python3 tests/test_bars_float_labels.py
  (expects ~/workspace/ps-bars-before to exist as a main checkout;
   creates it if missing by cloning main.)
"""
import http.server
import functools
import json
import os
import re
import subprocess
import sys
import threading

from playwright.sync_api import sync_playwright

HOME = os.path.expanduser("~")
BRANCH_DIR = os.path.join(HOME, "workspace", "ps-bars-float")
BEFORE_DIR = os.path.join(HOME, "workspace", "ps-bars-before")
SHOTS = os.path.join(HOME, "workspace", "your_files", "bars-float-shots")

LONG_FLOAT = re.compile(r"-?\d+\.\d{3,}")


def serve(directory, port):
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=directory)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def ensure_before():
    if os.path.isfile(os.path.join(BEFORE_DIR, "screener.html")):
        return
    subprocess.run(["git", "clone", "-q", "--branch", "main",
                    "https://github.com/Schadhaxx/paperstreetbtc.git",
                    BEFORE_DIR], check=True)
    subprocess.run(["git", "-C", BEFORE_DIR, "checkout", "-q",
                    "a4a0a76fa57296f0c343f737e24dbc06ef19f52e"], check=True)


def read_bars_axis(page):
    """Return (tick labels, bar values, callback outputs) for Bars/Day."""
    page.wait_for_selector("#cmp-tab-bars", timeout=15000)
    page.click("#cmp-tab-bars")
    page.wait_for_timeout(1200)
    out = page.evaluate("""() => {
      const cv = document.getElementById('screener-chart');
      const ch = window.Chart && Chart.getChart ? Chart.getChart(cv) : null;
      if (!ch) return {error: 'no chart instance'};
      const ticks = (ch.scales.x && ch.scales.x.ticks || []).map(t => String(t.label));
      const data = (ch.data.datasets[0] && ch.data.datasets[0].data || []).map(v => Number(v));
      // Deterministic proof: feed the exact float-tail values from the
      // bug report straight through the live tick callback.
      const cb = ch.options.scales.x.ticks.callback;
      const probe = [-0.35000000000000003, -0.11666666666666668, 0.3333333333333333, 2.66]
        .map(v => cb.call(ch.scales.x, v));
      return {ticks, data, probe};
    }""")
    return out


def select_all_stocks(page):
    for sym in ["TSLA", "PLTR", "MSTR", "IBIT", "MU", "META", "SPCX"]:
        btn = page.query_selector(f'[data-cmp-symbol="{sym}"]')
        if btn and btn.get_attribute("aria-pressed") != "true":
            btn.click()
    page.wait_for_timeout(1200)


def main():
    ensure_before()
    os.makedirs(SHOTS, exist_ok=True)
    serve(BRANCH_DIR, 8101)
    serve(BEFORE_DIR, 8102)
    results = []

    def check(name, ok, detail=""):
        results.append((name, ok, detail))
        print(("PASS " if ok else "FAIL ") + name + ((" — " + detail) if detail else ""))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width, tag in [(1280, "desktop"), (390, "phone")]:
            for label, port in [("BEFORE", 8102), ("AFTER", 8101)]:
                ctx = browser.new_context(viewport={"width": width, "height": 900})
                page = ctx.new_page()
                errors = []
                # Sandbox artifact: the screener's live-price feeds
                # (CoinGecko/Coinbase) can't reach the internet here, so
                # their failed loads are expected and identical before/after.
                # Only count real JS page errors, not resource-load failures.
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{port}/screener.html", timeout=30000)
                page.wait_for_timeout(2500)
                # 1. Bars/Day, default 2 stocks
                r = read_bars_axis(page)
                if "error" in r:
                    check(f"{tag} {tag} bars render ({width}px)", False, r["error"])
                    ctx.close()
                    continue
                bad = [t for t in r["ticks"] if LONG_FLOAT.search(t)]
                check(f"{tag} 2-stock Bars/Day axis rounded ({width}px)",
                      not bad, f"ticks={r['ticks']}" + (f" BAD={bad}" if bad else ""))
                # Deterministic: feed the exact float-tail values from the
                # bug report through the live tick callback.
                # BEFORE must show the raw floats (bug reproduced);
                # AFTER must round them to 2 decimals (bug fixed).
                expected_probe = ["-0.35%", "-0.12%", "+0.33%", "+2.66%"]
                if label == "BEFORE":
                    has_tails = any(LONG_FLOAT.search(x) for x in (r.get("probe") or []))
                    check(f"{tag} bug reproduced on old code ({width}px)",
                          has_tails, f"probe={r.get('probe')}")
                else:
                    check(f"{tag} tick callback rounds float tails ({width}px)",
                          r.get("probe") == expected_probe, f"probe={r.get('probe')}")
                if label == "BEFORE":
                    before_data = r["data"]
                    page.screenshot(path=os.path.join(SHOTS, f"before-{tag}.png"))
                else:
                    after_data = r["data"]
                    check("bar values unchanged before vs after",
                          before_data == after_data,
                          f"before={before_data} after={after_data}")
                    page.screenshot(path=os.path.join(SHOTS, f"after-{tag}.png"))
                # 2. All 7 stocks
                select_all_stocks(page)
                r7 = read_bars_axis(page)
                bad7 = [t for t in r7["ticks"] if LONG_FLOAT.search(t)] if "ticks" in r7 else ["no chart"]
                check(f"{tag} 7-stock Bars/Day axis rounded ({width}px)",
                      not bad7, f"ticks={r7.get('ticks')}" + (f" BAD={bad7}" if bad7 else ""))
                check(f"{tag} no console errors ({width}px)", not errors, "; ".join(errors[:2]))
                ctx.close()
        browser.close()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
