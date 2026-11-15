import time
from playwright.sync_api import sync_playwright
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/usr/bin/google-chrome")
    for name,(w,h) in {"portrait":(393,852),"landscape":(852,393)}.items():
      for mode in ["dark","light"]:
        c=b.new_context(viewport={"width":w,"height":h},device_scale_factor=2,is_mobile=True,has_touch=True,user_agent=UA)
        pg=c.new_page()
        if mode=="light":
            pg.add_init_script("try{localStorage.setItem('ps-theme','light');localStorage.setItem('theme','light')}catch(e){}")
        pg.goto(f"https://paperstreetbtc.com/clock/?cb={int(time.time())}",wait_until="networkidle")
        time.sleep(4)
        pg.screenshot(path=f"shots/live/live-{name}-{mode}.png")
        if name=="portrait" and mode=="dark":
            open("src/live-clock.html","w").write(pg.content())
        c.close()
    b.close()
