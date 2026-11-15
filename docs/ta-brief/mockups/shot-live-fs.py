import time,json
from playwright.sync_api import sync_playwright
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/usr/bin/google-chrome")
    c=b.new_context(viewport={"width":852,"height":393},device_scale_factor=2,is_mobile=True,has_touch=True,user_agent=UA)
    pg=c.new_page()
    pg.goto(f"https://paperstreetbtc.com/clock/?cb={int(time.time())}",wait_until="networkidle"); time.sleep(3)
    print(pg.evaluate("""()=>{const o={};for(const s of ['.bc-rg','.bc-lg','.bc-ct','.bc-box','#wakeBtn','.top','.v4-plot','.v4-clock','.wl-btn','#themeToggle','.theme-toggle']){const e=document.querySelector(s);if(e){const r=e.getBoundingClientRect();o[s]=[r.x,r.y,r.width,r.height,e.outerHTML.slice(0,300)]}}return o}"""))
    for m in ["chart","price"]:
        pg.evaluate(f"window.__psClockFs.enter('{m}')"); time.sleep(1.5)
        pg.screenshot(path=f"shots/live/live-fs-{m}-landscape.png")
        print(m, pg.evaluate("""()=>{const o={};for(const s of ['.v4-fs-exit','#wakeBtn','.price','.bc-rg','.bc-lg','.bc-box']){const e=document.querySelector(s);if(e){const r=e.getBoundingClientRect();o[s]=[r.x,r.y,r.width,r.height,getComputedStyle(e).display]}}return o}"""))
        pg.evaluate("window.__psClockFs.exit()"); time.sleep(.5)
    b.close()
