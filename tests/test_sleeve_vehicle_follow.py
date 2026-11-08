"""Verify the 'Your sleeve' custom line follows the vehicle toggle (Spot/IBIT/FBTC),
Grok Bot review #2 rework.
Serves the branch clone locally; the page fetches live history.json from the data
branch (same as production) and vehicle-daily.json + opens.json locally.
The vehicle is switched ONLY by real clicks on the scoped Compare selector
(#pvVeh [data-pvveh=...]) — no sessionStorage manipulation anywhere in this file.
Checks: real-click switching Spot -> IBIT -> FBTC -> Spot; contributions (incl. an
extra contribution) in ETF mode; calculator 'Sleeve today' agreeing with the
custom-line endpoint in every mode; Spot BTC today unchanged in every mode
(hurdle stays Spot); one-session vehicle gaps carry the prior close forward
(book rule, disclosed); 2+-session gaps and a stale tail REJECT the vehicle file
(page stays Spot, ETF buttons disabled, reason shown); 390px has no overflow.
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

def money(s):
    return float(s.replace("$", "").replace(",", "")) if s else None

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
        """Read calculator numbers, custom-line endpoint, notes, selector state."""
        return page.evaluate("""() => {
          const q = s => { const el = document.querySelector(s); return el ? el.textContent.trim() : null; };
          const chart = Chart.getChart(document.getElementById('pvChart'));
          const ds = chart ? chart.data.datasets : [];
          const custom = ds.find(d => d.label === 'Your sleeve');
          const berk = ds.find(d => d.label === 'Hodler Jam Sandwich');
          const last = a => { for (let i = a.length - 1; i >= 0; i--) if (a[i] != null) return a[i]; return null; };
          const sel = m => { const b = document.querySelector(`#pvVeh [data-pvveh="${m}"]`);
            return b ? {on: b.classList.contains('on'), pressed: b.getAttribute('aria-pressed'), disabled: b.disabled} : null; };
          return {
            sleeveToday: q('#pvRS'), sleevePct: q('#pvRSp'),
            spotToday: q('#pvRB'), spotPct: q('#pvRBp'),
            note: q('#pvChartNote'), vehNote: q('#pvVehNote'), summary: q('#pvRN'),
            customLast: custom ? last(custom.raw) : null,
            berkPctLast: berk ? last(berk.data) : null,
            selSpot: sel('SPOT'), selIBIT: sel('IBIT'), selFBTC: sel('FBTC'),
            scrollW: document.documentElement.scrollWidth,
            innerW: window.innerWidth,
          };
        }""")

    def wait_vehicle_ready(page):
        """Vehicle file loaded + validated: IBIT button enabled."""
        page.wait_for_function(
            "!document.querySelector('#pvVeh [data-pvveh=\"IBIT\"]').disabled", timeout=15000)

    def click_vehicle(page, mode):
        """REAL CLICK on the scoped selector, then wait for the mode to apply."""
        page.click(f"#pvVeh [data-pvveh='{mode}']")
        if mode == "SPOT":
            page.wait_for_function(
                "document.getElementById('pvVehNote').textContent.includes('Spot BTC — the hurdle')",
                timeout=10000)
        else:
            page.wait_for_function(
                f"document.getElementById('pvVehNote').textContent.includes('You are in {mode} mode')",
                timeout=10000)
        page.wait_for_timeout(600)

    def agrees(st):
        return (st["customLast"] is not None and st["sleeveToday"]
                and abs(st["customLast"] - money(st["sleeveToday"])) < 1.0)

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        # Spot-with-contribution reference FIRST: fresh page, same $1000 / 2026-06-01
        # row, Spot mode. The Spot BTC hurdle scales with the invested amount (the
        # extra $1000 also buys Spot BTC, at its trading-day open), so post-
        # contribution hurdle values must be compared against THIS, not the
        # no-contribution baseline.
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(BASE, wait_until="load")
        pg.wait_for_selector("#pvRS:not(:empty)", timeout=20000)
        wait_vehicle_ready(pg)
        pg.click("#pvXAdd")
        pg.wait_for_selector(".pvx-row", timeout=5000)
        pg.fill(".pvx-row .pvx-a", "1000")
        pg.fill(".pvx-row .pvx-d", "2026-06-01")
        pg.wait_for_timeout(800)
        spot_x = state(pg)
        spot_x_row = pg.evaluate("() => document.querySelector('.pvx-n').textContent")
        pg.close()

        # ---------------- desktop, real clicks ----------------
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append("PAGEERROR: " + str(e)))
        pg.on("console", lambda m: errs.append("CONSOLE: " + m.text) if m.type == "error" and "Failed to load resource" not in m.text and "ERR_" not in m.text else None)
        pg.goto(BASE, wait_until="load")
        pg.wait_for_selector("#pvRS:not(:empty)", timeout=20000)
        wait_vehicle_ready(pg)
        pg.wait_for_timeout(800)
        spot = state(pg)
        print("SPOT  :", json.dumps(spot, indent=None))
        pg.screenshot(path=str(SHOTS / "spot-desktop-r2.png"))
        check("Selector exists: 3 buttons, Spot on, IBIT/FBTC enabled",
              spot["selSpot"] and spot["selSpot"]["on"] and spot["selSpot"]["pressed"] == "true"
              and spot["selIBIT"] and not spot["selIBIT"]["disabled"]
              and spot["selFBTC"] and not spot["selFBTC"]["disabled"],
              json.dumps({"spot": spot["selSpot"], "ibit": spot["selIBIT"], "fbtc": spot["selFBTC"]}))
        check("Spot: selector note says Spot is the hurdle",
              spot["vehNote"] == "Spot BTC — the hurdle", spot["vehNote"])
        check("Spot: sleeve today is a $ value", spot["sleeveToday"] and spot["sleeveToday"].startswith("$"), spot["sleeveToday"])
        check("Spot: custom line endpoint equals sleeve today",
              agrees(spot), f"line={spot['customLast']} calc={spot['sleeveToday']}")
        check("Spot: note has no vehicle-following claim",
              "follows the IBIT vehicle" not in (spot["note"] or "") and "follows the FBTC vehicle" not in (spot["note"] or ""),
              (spot["note"] or "")[:160])

        click_vehicle(pg, "IBIT")
        ibit = state(pg)
        print("IBIT  :", json.dumps(ibit, indent=None))
        pg.screenshot(path=str(SHOTS / "ibit-desktop-r2.png"))
        check("IBIT (real click): selector shows IBIT on, Spot off",
              ibit["selIBIT"]["on"] and ibit["selIBIT"]["pressed"] == "true" and not ibit["selSpot"]["on"],
              json.dumps({"spot": ibit["selSpot"], "ibit": ibit["selIBIT"]}))
        check("IBIT: sleeve today CHANGED vs Spot", ibit["sleeveToday"] != spot["sleeveToday"],
              f"{spot['sleeveToday']} -> {ibit['sleeveToday']}")
        check("IBIT: spot today UNCHANGED (hurdle stays Spot)", ibit["spotToday"] == spot["spotToday"],
              f"{spot['spotToday']} vs {ibit['spotToday']}")
        check("IBIT: custom line endpoint equals sleeve today", agrees(ibit),
              f"line={ibit['customLast']} calc={ibit['sleeveToday']}")
        check("IBIT: note says line follows IBIT",
              "follows the IBIT vehicle" in (ibit["note"] or ""), (ibit["note"] or "")[:200])
        check("IBIT: Hodler sleeve line also moved (no regression)",
              ibit["berkPctLast"] != spot["berkPctLast"],
              f"{spot['berkPctLast']} -> {ibit['berkPctLast']}")

        # extra contribution in IBIT mode: add $1000 on 2026-06-01 (real clicks/typing)
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
        check("IBIT: contribution line endpoint still equals sleeve today", agrees(ibit_x),
              f"line={ibit_x['customLast']} calc={ibit_x['sleeveToday']}")
        check("IBIT: summary discloses vehicle-close pricing for the BTC leg",
              "BTC leg is priced at the vehicle close" in (ibit_x["summary"] or ""), ibit_x["summary"])
        check("IBIT: spot today equals Spot-mode hurdle for the SAME contribution",
              ibit_x["spotToday"] == spot_x["spotToday"],
              f"IBIT+x {ibit_x['spotToday']} vs Spot+x {spot_x['spotToday']}")
        check("IBIT: hurdle scales with the contribution (as designed)",
              spot_x["spotToday"] != spot["spotToday"],
              f"no-row {spot['spotToday']} vs with-row {spot_x['spotToday']}")

        click_vehicle(pg, "FBTC")
        fbtc = state(pg)
        print("FBTC  :", json.dumps(fbtc, indent=None))
        pg.screenshot(path=str(SHOTS / "fbtc-desktop-r2.png"))
        check("FBTC (real click): selector shows FBTC on",
              fbtc["selFBTC"]["on"] and fbtc["selFBTC"]["pressed"] == "true" and not fbtc["selIBIT"]["on"])
        check("FBTC: sleeve today CHANGED vs Spot", fbtc["sleeveToday"] != spot["sleeveToday"],
              f"{spot['sleeveToday']} -> {fbtc['sleeveToday']}")
        check("FBTC: sleeve today DIFFERS from IBIT (with contribution)",
              fbtc["sleeveToday"] != ibit_x["sleeveToday"],
              f"IBIT+x {ibit_x['sleeveToday']} vs FBTC {fbtc['sleeveToday']}")
        check("FBTC: spot today equals Spot-mode hurdle for the SAME contribution",
              fbtc["spotToday"] == spot_x["spotToday"],
              f"FBTC {fbtc['spotToday']} vs Spot+x {spot_x['spotToday']}")
        check("FBTC: custom line endpoint equals sleeve today", agrees(fbtc),
              f"line={fbtc['customLast']} calc={fbtc['sleeveToday']}")
        check("FBTC: note says line follows FBTC",
              "follows the FBTC vehicle" in (fbtc["note"] or ""))
        check("FBTC: contribution row now cites FBTC close",
              "BTC leg at the FBTC close" in (pg.evaluate("() => document.querySelector('.pvx-n').textContent") or ""))

        click_vehicle(pg, "SPOT")
        back = state(pg)
        print("BACK  :", json.dumps(back, indent=None))
        check("Back to Spot (real click): selector shows Spot on",
              back["selSpot"]["on"] and back["selSpot"]["pressed"] == "true")
        check("Back to Spot: custom line endpoint equals sleeve today", agrees(back),
              f"line={back['customLast']} calc={back['sleeveToday']}")
        check("Back to Spot: spot today equals Spot-mode hurdle for the SAME contribution",
              back["spotToday"] == spot_x["spotToday"])
        check("Back to Spot: sleeve today returns to Spot value (same contribution)",
              back["sleeveToday"] == spot_x["sleeveToday"],
              f"back {back['sleeveToday']} vs Spot+same-row {spot_x['sleeveToday']}")
        check("No console/page errors on desktop", not errs, "; ".join(errs[:3]))
        pg.close()

        check("Spot+contribution: line endpoint equals sleeve today", agrees(spot_x))
        check("Spot+contribution: row does NOT claim a vehicle close",
              "BTC leg at the" not in (spot_x_row or ""), spot_x_row)
        check("Spot+contribution: summary does NOT promise vehicle-close pricing",
              "vehicle close" not in (spot_x["summary"] or ""), spot_x["summary"])

        # ---------------- phone 390px, real click ----------------
        pg = b.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        errs = []
        pg.on("pageerror", lambda e: errs.append("PAGEERROR: " + str(e)))
        pg.on("console", lambda m: errs.append("CONSOLE: " + m.text) if m.type == "error" and "Failed to load resource" not in m.text and "ERR_" not in m.text else None)
        pg.goto(BASE, wait_until="load")
        pg.wait_for_selector("#pvRS:not(:empty)", timeout=20000)
        wait_vehicle_ready(pg)
        pg.wait_for_timeout(800)
        p_spot = state(pg)
        pg.screenshot(path=str(SHOTS / "spot-390-r2.png"))
        check("390px Spot: no horizontal overflow", p_spot["scrollW"] == p_spot["innerW"],
              f"scrollW={p_spot['scrollW']} innerW={p_spot['innerW']}")
        check("390px Spot: sleeve today present", bool(p_spot["sleeveToday"] and p_spot["sleeveToday"].startswith("$")), p_spot["sleeveToday"])
        click_vehicle(pg, "IBIT")
        p_ibit = state(pg)
        pg.screenshot(path=str(SHOTS / "ibit-390-r2.png"))
        check("390px IBIT (real click): sleeve today CHANGED vs Spot", p_ibit["sleeveToday"] != p_spot["sleeveToday"],
              f"{p_spot['sleeveToday']} -> {p_ibit['sleeveToday']}")
        check("390px IBIT: spot today UNCHANGED", p_ibit["spotToday"] == p_spot["spotToday"])
        check("390px IBIT: no horizontal overflow", p_ibit["scrollW"] == p_ibit["innerW"],
              f"scrollW={p_ibit['scrollW']} innerW={p_ibit['innerW']}")
        check("390px IBIT: line endpoint equals sleeve today", agrees(p_ibit),
              f"line={p_ibit['customLast']} calc={p_ibit['sleeveToday']}")
        check("No console/page errors on phone", not errs, "; ".join(errs[:3]))
        pg.close()
        b.close()

        # ---------------- vehicle-gap cases (route interception) ----------------
        # The served vehicle-daily.json is replaced per page; the repo file is untouched.
        orig_vd = json.loads((ROOT / "assets/data/vehicle-daily.json").read_text())

        def gapped_vd(drop_dates=None, end=None):
            vd = json.loads(json.dumps(orig_vd))
            for v in vd["vehicles"]:
                pts = vd["vehicles"][v]
                if drop_dates:
                    pts = [p for p in pts if p[0] not in drop_dates]
                if end:
                    pts = [p for p in pts if p[0] <= end]
                vd["vehicles"][v] = pts
            return vd

        def gap_page(pw, vd):
            bb = pw.chromium.launch()
            pg = bb.new_page(viewport={"width": 1280, "height": 900})
            pg.route("**/assets/data/vehicle-daily.json",
                     lambda route: route.fulfill(status=200, content_type="application/json",
                                                 body=json.dumps(vd)))
            return bb, pg

        # 1-session gap: 2026-03-02 missing from both vehicles -> carry-forward, disclosed
        bb, pg = gap_page(pw, gapped_vd(drop_dates=["2026-03-02"]))
        pg.goto(BASE, wait_until="load")
        pg.wait_for_selector("#pvRS:not(:empty)", timeout=20000)
        wait_vehicle_ready(pg)
        g1_spot = state(pg)
        click_vehicle(pg, "IBIT")
        g1 = state(pg)
        print("GAP1  :", json.dumps(g1, indent=None))
        check("1-session gap: IBIT still selectable (carry-forward, book rule)",
              g1["selIBIT"]["on"] and not g1["selIBIT"]["disabled"])
        check("1-session gap: selector discloses the carried-forward session",
              "2 Mar 2026 uses the prior close (one session carried forward)" in (g1["vehNote"] or ""),
              g1["vehNote"])
        check("1-session gap: sleeve today CHANGED vs Spot (not a silent Spot fallback)",
              g1["sleeveToday"] != g1_spot["sleeveToday"],
              f"{g1_spot['sleeveToday']} -> {g1['sleeveToday']}")
        check("1-session gap: spot today UNCHANGED", g1["spotToday"] == g1_spot["spotToday"])
        check("1-session gap: line endpoint equals sleeve today", agrees(g1))
        pg.close(); bb.close()

        # 2-session gap: 2026-03-02 + 2026-03-03 missing -> whole file REJECTED
        bb, pg = gap_page(pw, gapped_vd(drop_dates=["2026-03-02", "2026-03-03"]))
        pg.goto(BASE, wait_until="load")
        pg.wait_for_selector("#pvRS:not(:empty)", timeout=20000)
        pg.wait_for_function(
            "document.getElementById('pvVehNote').textContent.includes('showing Spot BTC')",
            timeout=15000)
        pg.wait_for_timeout(500)
        g2 = state(pg)
        print("GAP2  :", json.dumps(g2, indent=None))
        check("2-session gap: ETF buttons DISABLED (rejected, not silently Spot)",
              g2["selIBIT"]["disabled"] and g2["selFBTC"]["disabled"],
              json.dumps({"ibit": g2["selIBIT"], "fbtc": g2["selFBTC"]}))
        check("2-session gap: note names the gap and says showing Spot",
              "missing 2 sessions" in (g2["vehNote"] or "") and "showing Spot BTC" in (g2["vehNote"] or ""),
              g2["vehNote"])
        check("2-session gap: chart note never claims IBIT mode",
              "IBIT mode" not in (g2["note"] or ""), (g2["note"] or "")[:200])
        check("2-session gap: sleeve today is a $ value (Spot, usable)",
              bool(g2["sleeveToday"] and g2["sleeveToday"].startswith("$")), g2["sleeveToday"])
        check("2-session gap: line endpoint equals sleeve today", agrees(g2))
        pg.close(); bb.close()

        # Stale tail: vehicle file ends 2026-10-19, 2 sessions behind embedded LAST 2026-10-21
        bb, pg = gap_page(pw, gapped_vd(end="2026-10-19"))
        pg.goto(BASE, wait_until="load")
        pg.wait_for_selector("#pvRS:not(:empty)", timeout=20000)
        pg.wait_for_function(
            "document.getElementById('pvVehNote').textContent.includes('showing Spot BTC')",
            timeout=15000)
        pg.wait_for_timeout(500)
        g3 = state(pg)
        print("STALE :", json.dumps(g3, indent=None))
        check("Stale tail: ETF buttons DISABLED",
              g3["selIBIT"]["disabled"] and g3["selFBTC"]["disabled"])
        check("Stale tail: note says out of date with last close",
              "out of date" in (g3["vehNote"] or "") and "19 Oct 2026" in (g3["vehNote"] or ""),
              g3["vehNote"])
        check("Stale tail: chart note never claims IBIT mode",
              "IBIT mode" not in (g3["note"] or ""))
        check("Stale tail: line endpoint equals sleeve today", agrees(g3))
        pg.close(); bb.close()

    print(f"\n{len(failures)} FAILURES" if failures else "\nALL CHECKS PASSED")
    if failures:
        print("Failed:", failures)
finally:
    srv.terminate()

sys.exit(1 if failures else 0)
