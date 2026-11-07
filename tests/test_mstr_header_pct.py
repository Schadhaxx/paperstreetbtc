"""MSTR header % in the screener BTC popover — verification.

Bug: toggling MSTR on in the BTC popover drew the orange MSTR line but the
header summary (#bcRr) never showed the MSTR % (S&P 500 and Gold did).
Fix (assets/js/btcchart.js, drawDaily): compute mpc alongside spc/gpc and
append ' · MSTR <pct>' to the header, plus the MSTR source clause in the
note. Run: python tests/test_mstr_header_pct.py  (serves the repo root
locally, blocks external feeds so the run is offline-deterministic).
Screenshots land in ~/workspace/your_files/mstr-header-shots/.
"""
import http.server, functools, os, re, socketserver, sys, threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.expanduser("~/workspace/your_files/mstr-header-shots")
os.makedirs(SHOTS, exist_ok=True)

PORT = 8971
URL = "http://127.0.0.1:%d/screener.html" % PORT

def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
    class S(socketserver.TCPServer):
        allow_reuse_address = True
    with S(("127.0.0.1", PORT), h) as httpd:
        httpd.serve_forever()

def main():
    from playwright.sync_api import sync_playwright
    t = threading.Thread(target=serve, daemon=True); t.start()
    fails = []
    def check(name, cond, extra=""):
        print(("PASS " if cond else "FAIL ") + name + (" | " + extra if extra else ""))
        if not cond:
            fails.append(name)

    with sync_playwright() as pw:
        for label, width in (("desktop", 1280), ("phone", 390)):
            b = pw.chromium.launch(executable_path=os.path.expanduser(
                "~/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome"),
                args=["--no-sandbox"])
            pg = b.new_page(viewport={"width": width, "height": 900},
                            has_touch=(width == 390), is_mobile=(width == 390))
            # Block external feeds: offline-deterministic, local data files only.
            pg.route("**://api.coingecko.com/**", lambda r: r.abort())
            pg.route("**://api.exchange.coinbase.com/**", lambda r: r.abort())
            pg.route("**://raw.githubusercontent.com/**", lambda r: r.abort())
            pg.route("**://mempool.space/**", lambda r: r.abort())
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            # Console "Failed to load resource" for the deliberately blocked
            # external feeds is the stub working, not a page error — ignore it.
            def _cerr(m):
                if m.type == "error" and "Failed to load resource" not in m.text:
                    errors.append(m.text)
            pg.on("console", _cerr)
            pg.goto(URL, wait_until="domcontentloaded")
            pg.click("#hdrTick")
            pg.wait_for_selector(".bc-w:not([hidden])", timeout=15000)
            # Wait for the chart to draw (header leaves "Loading…").
            pg.wait_for_function(
                "() => { var el = document.querySelector('#bcRr'); "
                "return el && el.textContent && el.textContent.indexOf('Loading') !== 0; }",
                timeout=20000)
            pg.wait_for_timeout(800)
            hdr = lambda: pg.inner_text("#bcRr")
            # 1M range so the % changes are meaningful (1D has ~1 point).
            pg.click('#bcRg [data-r="1M"]')
            pg.wait_for_timeout(800)
            base = hdr()
            check(label + ": baseline header has BTC %", "BTC" in base and "%" in base, base)
            check(label + ": baseline header has no compare % yet",
                  "S&P 500" not in base and "Gold" not in base and "MSTR" not in base, base)
            pg.screenshot(path=os.path.join(SHOTS, "after-%s-base.png" % label))
            # S&P on -> header shows its %.
            pg.click("#bcSpx")
            pg.wait_for_timeout(600)
            h1 = hdr()
            check(label + ": S&P on -> header shows S&P 500 %",
                  re.search(r"S&P 500 [+-][\d.]+%", h1) is not None, h1)
            # Gold on -> header shows its %.
            pg.click("#bcGld")
            pg.wait_for_timeout(600)
            h2 = hdr()
            check(label + ": Gold on -> header shows Gold %",
                  re.search(r"Gold [+-][\d.]+%", h2) is not None, h2)
            # MSTR on -> header shows its % (THE FIX) and the toggle goes active.
            pg.click("#bcMstr")
            pg.wait_for_timeout(600)
            h3 = hdr()
            check(label + ": MSTR on -> header shows MSTR %",
                  re.search(r"MSTR [+-][\d.]+%", h3) is not None, h3)
            check(label + ": MSTR on -> header keeps S&P + Gold",
                  "S&P 500" in h3 and "Gold" in h3, h3)
            check(label + ": MSTR toggle active (MSTR x)",
                  pg.inner_text("#bcMstrT").strip() == "MSTR ✕",
                  pg.inner_text("#bcMstrT"))
            check(label + ": note mentions MSTR source",
                  "MSTR session closes" in pg.inner_text("#bcNt"),
                  pg.inner_text("#bcNt")[:160])
            pg.screenshot(path=os.path.join(SHOTS, "after-%s-all-on.png" % label))
            # MSTR off -> its % leaves the header, others stay.
            pg.click("#bcMstr")
            pg.wait_for_timeout(600)
            h4 = hdr()
            check(label + ": MSTR off -> header drops MSTR %",
                  "MSTR" not in h4, h4)
            check(label + ": MSTR off -> S&P + Gold % stay",
                  "S&P 500" in h4 and "Gold" in h4, h4)
            check(label + ": no console/page errors", not errors, "; ".join(errors[:3]))
            # No horizontal overflow at phone width.
            if width == 390:
                sw = pg.evaluate("document.documentElement.scrollWidth")
                iw = pg.evaluate("window.innerWidth")
                check(label + ": no horizontal overflow", sw == iw, "scrollWidth=%s innerWidth=%s" % (sw, iw))
            b.close()
    print("\n%d check(s) failed" % len(fails) if fails else "\nALL CHECKS PASSED")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
