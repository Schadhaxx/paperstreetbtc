"""Verify the 'Your sleeve' custom line follows the vehicle toggle (Spot/IBIT/FBTC).
Serves the branch clone locally; the page fetches live history.json from the data
branch (same as production) and vehicle-daily.json + opens.json locally.
Checks: calculator 'Sleeve today' + custom-line endpoint change in IBIT/FBTC,
'Spot BTC today' does NOT change (hurdle stays Spot), Spot values return on
switch-back, extra contributions follow the vehicle too, 390px has no overflow.
"""
import json, subprocess, sys, time, urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8471/compare/index.html"
ROOT = Path.home() / "workspace" / "ps-sleeve-veh"
SHOTS = Path.home() / "workspace" / "your_files" / "sleeve-vehicle-shots"
SHOTS.mkdir(parents=True, exist_ok=True)

failures = []
def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(name)

# --- serve the clone -------------------------------------------------------
srv = subprocess.Popen([sys.executable, "-m", "http.server", "8471", "--bind", "127.0.0.1"],
                       cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(30):
        try:
            urllib.request.urlopen(BASE, timeout=2); break
        except Exception:
            time.sleep(0.5)
    else:
        raise RuntimeError("local server did not start")

    from playwright.sync_api import sync_playwright

    def state(page):
        """Read calculator numbers, custom-line endpoint, note, and a sleeve line."""
        return page.evaluate("""() => {
          const q = s => { const el = document.querySelector(s); return el ? el.textContent.trim() : null; };
          const chart = Chart.getChart(document.getElementById('pvChart'));
          const ds = chart ? chart.data.datasets : [];
          const custom = ds.find(d => d.label === 'Your sleeve');
          const berk = ds.find(d => d.label === 'Hodler Jam Sandwich');
          const last = a => { for (let i = a.length - 1; i >= 0; i--) if (a[i] != null) return a[i]; return null; };
          return {
            sleeveToday: q('#pvRS'), sleevePct: q('#pvRSp'),
            spotToday: q('#pvRB'), spotPct: q('#pvRBp'),
            note: q('#pvChartNote'),
            customLast: custom ? last(custom.raw) : null,
            customPctLast: custom ? last(custom.data) : null,
            berkPctLast: berk ? last(berk.data) : null,
            scrollW: document.documentElement.scrollWidth,
            innerW: window.innerWidth,
          };
        }""")

    def set_vehicle(page, mode):
        page.evaluate(f"sessionStorage.setItem('psVehicle','{mode}')")
        page.reload(wait_until="load")
        page.wait_for_selector("#pvRS:not(:empty)", timeout=15000)
        # wait for the vehicle fetch + redraw (note gains the mode sentence, or 4s max)
        try:
            page.wait_for_function(
                f"document.getElementById('pvChartNote').textContent.includes('{mode} mode')",
                timeout=6000)
        except Exception:
            pass
        page.wait_for_timeout(800)

    with sync_playwright() as pw:
        # ---------------- desktop ----------------
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append("PAGEERROR: " + str(e)))
        pg.on("console", lambda m: errs.append("CONSOLE: " + m.text) if m.type == "error" and "Failed to load resource" not in m.text and "ERR_" not in m.text else None)
        pg.goto(BASE, wait_until="load")
        pg.wait_for_selector("#pvRS:not(:empty)", timeout=20000)
        pg.wait_for_timeout(1500)
        spot = state(pg)
        print("SPOT  :", json.dumps(spot, indent=None))
        pg.screenshot(path=str(SHOTS / "spot-desktop.png"))
        check("Spot: sleeve today is a $ value", spot["sleeveToday"] and spot["sleeveToday"].startswith("$"), spot["sleeveToday"])
        check("Spot: custom line endpoint equals sleeve today",
              spot["customLast"] is not None and abs(spot["customLast"] - float(spot["sleeveToday"].replace("$", "").replace(",", ""))) < 1.0,
              f"line={spot['customLast']} calc={spot['sleeveToday']}")
        check("Spot: note has no vehicle-following claim",
              "follows the IBIT vehicle" not in (spot["note"] or "") and "follows the FBTC vehicle" not in (spot["note"] or ""),
              (spot["note"] or "")[:160])

        set_vehicle(pg, "IBIT")
        ibit = state(pg)
        print("IBIT  :", json.dumps(ibit, indent=None))
        pg.screenshot(path=str(SHOTS / "ibit-desktop.png"))
        check("IBIT: sleeve today CHANGED vs Spot", ibit["sleeveToday"] != spot["sleeveToday"],
              f"{spot['sleeveToday']} -> {ibit['sleeveToday']}")
        check("IBIT: spot today UNCHANGED (hurdle stays Spot)", ibit["spotToday"] == spot["spotToday"],
              f"{spot['spotToday']} vs {ibit['spotToday']}")
        check("IBIT: custom line endpoint equals sleeve today",
              ibit["customLast"] is not None and abs(ibit["customLast"] - float(ibit["sleeveToday"].replace("$", "").replace(",", ""))) < 1.0,
              f"line={ibit['customLast']} calc={ibit['sleeveToday']}")
        check("IBIT: note says line follows IBIT",
              "follows the IBIT vehicle" in (ibit["note"] or ""), (ibit["note"] or "")[:200])
        check("IBIT: Hodler sleeve line also moved (no regression)",
              ibit["berkPctLast"] != spot["berkPctLast"],
              f"{spot['berkPctLast']} -> {ibit['berkPctLast']}")

        # extra contribution in IBIT mode: add $1000 on 2026-06-01, note must cite the BTC leg
        pg.click("#pvXAdd")
        pg.wait_for_selector(".pvx-row", timeout=5000)
        pg.fill(".pvx-row .pvx-a", "1000")
        pg.fill(".pvx-row .pvx-d", "2026-06-01")
        pg.wait_for_timeout(800)
        ibit_x = state(pg)
        row_note = pg.evaluate("() => document.querySelector('.pvx-n').textContent")
        print("IBIT+x:", json.dumps(ibit_x, indent=None), "| row:", row_note)
        check("IBIT: contribution row cites BTC leg at IBIT close",
              "BTC leg at the IBIT close" in (row_note or ""), row_note)
        check("IBIT: contribution changes sleeve today",
              ibit_x["sleeveToday"] != ibit["sleeveToday"],
              f"{ibit['sleeveToday']} -> {ibit_x['sleeveToday']}")
        check("IBIT: contribution line endpoint still equals sleeve today",
              ibit_x["customLast"] is not None and abs(ibit_x["customLast"] - float(ibit_x["sleeveToday"].replace("$", "").replace(",", ""))) < 1.0,
              f"line={ibit_x['customLast']} calc={ibit_x['sleeveToday']}")

        set_vehicle(pg, "FBTC")
        fbtc = state(pg)
        print("FBTC  :", json.dumps(fbtc, indent=None))
        pg.screenshot(path=str(SHOTS / "fbtc-desktop.png"))
        check("FBTC: sleeve today CHANGED vs Spot", fbtc["sleeveToday"] != spot["sleeveToday"],
              f"{spot['sleeveToday']} -> {fbtc['sleeveToday']}")
        check("FBTC: sleeve today DIFFERS from IBIT", fbtc["sleeveToday"] != ibit["sleeveToday"],
              f"IBIT {ibit['sleeveToday']} vs FBTC {fbtc['sleeveToday']}")
        check("FBTC: spot today UNCHANGED", fbtc["spotToday"] == spot["spotToday"])
        check("FBTC: custom line endpoint equals sleeve today",
              fbtc["customLast"] is not None and abs(fbtc["customLast"] - float(fbtc["sleeveToday"].replace("$", "").replace(",", ""))) < 1.0,
              f"line={fbtc['customLast']} calc={fbtc['sleeveToday']}")
        check("FBTC: note says line follows FBTC",
              "follows the FBTC vehicle" in (fbtc["note"] or ""))

        set_vehicle(pg, "SPOT")
        back = state(pg)
        print("BACK  :", json.dumps(back, indent=None))
        check("Back to Spot: sleeve today returns to Spot value",
              back["sleeveToday"] == spot["sleeveToday"],
              f"{spot['sleeveToday']} vs {back['sleeveToday']}")
        check("Back to Spot: custom line endpoint returns",
              back["customLast"] == spot["customLast"],
              f"{spot['customLast']} vs {back['customLast']}")
        check("No console/page errors on desktop", not errs, "; ".join(errs[:3]))
        pg.close()

        # ---------------- phone 390px ----------------
        pg = b.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        errs = []
        pg.on("pageerror", lambda e: errs.append("PAGEERROR: " + str(e)))
        pg.on("console", lambda m: errs.append("CONSOLE: " + m.text) if m.type == "error" and "Failed to load resource" not in m.text and "ERR_" not in m.text else None)
        pg.goto(BASE, wait_until="load")
        pg.wait_for_selector("#pvRS:not(:empty)", timeout=20000)
        pg.wait_for_timeout(1200)
        p_spot = state(pg)
        pg.screenshot(path=str(SHOTS / "spot-390.png"))
        check("390px Spot: no horizontal overflow", p_spot["scrollW"] == p_spot["innerW"],
              f"scrollW={p_spot['scrollW']} innerW={p_spot['innerW']}")
        check("390px Spot: sleeve today present", bool(p_spot["sleeveToday"] and p_spot["sleeveToday"].startswith("$")), p_spot["sleeveToday"])
        set_vehicle(pg, "IBIT")
        p_ibit = state(pg)
        pg.screenshot(path=str(SHOTS / "ibit-390.png"))
        check("390px IBIT: sleeve today CHANGED vs Spot", p_ibit["sleeveToday"] != p_spot["sleeveToday"],
              f"{p_spot['sleeveToday']} -> {p_ibit['sleeveToday']}")
        check("390px IBIT: spot today UNCHANGED", p_ibit["spotToday"] == p_spot["spotToday"])
        check("390px IBIT: no horizontal overflow", p_ibit["scrollW"] == p_ibit["innerW"],
              f"scrollW={p_ibit['scrollW']} innerW={p_ibit['innerW']}")
        check("390px IBIT: line endpoint equals sleeve today",
              p_ibit["customLast"] is not None and abs(p_ibit["customLast"] - float(p_ibit["sleeveToday"].replace("$", "").replace(",", ""))) < 1.0)
        check("No console/page errors on phone", not errs, "; ".join(errs[:3]))
        pg.close()
        b.close()

    print(f"\n{len(failures)} FAILURES" if failures else "\nALL CHECKS PASSED")
    if failures:
        print("Failed:", failures)
finally:
    srv.terminate()

sys.exit(1 if failures else 0)
