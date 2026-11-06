"""Verify logo home links on clock + screener (branch pepper-logo-home-link).
Serves the branch and a main worktree locally; checks the logo is a link to
home, clicking it navigates home, and the look is identical (no underline,
same colours/layout). Screenshots at 390px before/after."""
import json, os, subprocess, sys, time
from playwright.sync_api import sync_playwright

BRANCH_DIR = "/home/hatch/workspace/ps-logo-link"
MAIN_DIR = "/tmp/ps-logo-main"
SHOTS = "/home/hatch/workspace/your_files/logo-link-shots"
os.makedirs(SHOTS, exist_ok=True)

def serve(port, directory):
    return subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=directory, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def check(page, url, logo_sel, expect_href_suffix, label):
    out = {"label": label}
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    logo = page.locator(logo_sel)
    out["tag"] = page.evaluate("(s)=>document.querySelector(s).tagName", logo_sel)
    out["href"] = page.evaluate("(s)=>document.querySelector(s).getAttribute('href')", logo_sel)
    out["href_ok"] = out["href"] is not None and out["href"].endswith(expect_href_suffix)
    cs = page.evaluate("""(s)=>{
        const el=document.querySelector(s); const c=getComputedStyle(el);
        const txt=el.querySelector('span'); const tc=txt?getComputedStyle(txt).color:null;
        return {textDecoration:c.textDecorationLine, color:c.color, display:c.display,
                fontFamily:c.fontFamily, txtColor:tc}; }""", logo_sel)
    out["style"] = cs
    out["no_underline"] = cs["textDecoration"] in ("none", "")
    # click the logo and confirm we land on the homepage
    with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
        logo.click()
    out["after_click_url"] = page.url
    out["lands_home"] = page.url.rstrip("/").endswith("index.html") or page.url.rstrip("/").endswith(":8001") or page.url.rstrip("/").endswith(":8002")
    return out

def shot(page, url, path, width):
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    page.screenshot(path=path)

results = []
servers = [serve(8001, BRANCH_DIR), serve(8002, MAIN_DIR)]
time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/home/hatch/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome")
        # desktop + 390px checks on the branch
        for width in (1280, 390):
            pg = b.new_page(viewport={"width": width, "height": 900})
            results.append(check(pg, "http://127.0.0.1:8001/clock/index.html", "a.brand",
                                 "index.html", f"clock {width}px"))
            results.append(check(pg, "http://127.0.0.1:8001/screener.html", "a.brand-row",
                                 "index.html", f"screener {width}px"))
            pg.close()
        # before/after screenshots at 390px
        pg = b.new_page(viewport={"width": 390, "height": 900})
        shot(pg, "http://127.0.0.1:8002/clock/index.html", f"{SHOTS}/clock-before-390.png", 390)
        shot(pg, "http://127.0.0.1:8001/clock/index.html", f"{SHOTS}/clock-after-390.png", 390)
        shot(pg, "http://127.0.0.1:8002/screener.html", f"{SHOTS}/screener-before-390.png", 390)
        shot(pg, "http://127.0.0.1:8001/screener.html", f"{SHOTS}/screener-after-390.png", 390)
        pg.close()
        b.close()
finally:
    for s in servers:
        s.terminate()

fails = [r for r in results if not (r["tag"] == "A" and r["href_ok"] and r["no_underline"] and r["lands_home"])]
print(json.dumps(results, indent=2))
print(f"\nCHECKS: {len(results)} total, {len(fails)} failed")
print("PASS" if not fails else "FAIL")
