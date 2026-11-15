import time,json,sys,os
from playwright.sync_api import sync_playwright
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
BASE="http://127.0.0.1:"+os.environ.get("PORT","8790")+"/clock/ta.html"
VP={"p":(393,852),"l":(852,393),"se":(375,667)}
def jobs_all():
    J=[]
    for a in "ABCD":
        for th in ["dark","light"]:
            for s in ["today","closed","open","rsi"]:
                J.append((a,th,"p",s,{}))
            J.append((a,th,"p","candles",{"r":"1Y","ct":"candles"}))
            J.append((a,th,"p","open-candles",{"r":"1Y","ct":"candles"}))
            for s in ["today","open","rsi"]:
                J.append((a,th,"l",s,{}))
            J.append((a,th,"l","fsopen",{"fs":"chart"}))
            J.append((a,th,"l","fsrsi",{"fs":"chart"}))
        J.append((a,"dark","l","fsprice",{"fs":"price"}))
        J.append((a,"dark","p","fsopen",{"fs":"chart"}))
        J.append((a,"dark","p","rsicol",{}))
        for s in ["open","rsi","open-candles"]:
            J.append((a,"dark","se",s,{"r":"1Y","ct":"candles"} if s=="open-candles" else {}))
    return J
STATE={"fsopen":"open","fsrsi":"rsi","fsprice":"open","open-candles":"open"}
def main(only=None):
    jobs=jobs_all()
    if only: jobs=[j for j in jobs if any(o in "-".join([j[0],j[1],j[2],j[3]]) for o in only)]
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path="/usr/bin/google-chrome")
        for a,th,vp,s,extra in jobs:
            w,h=VP[vp]
            c=b.new_context(viewport={"width":w,"height":h},device_scale_factor=2,is_mobile=True,has_touch=True,user_agent=UA)
            c.add_init_script("localStorage.setItem('ps-theme','%s')"%th)
            pg=c.new_page(); pg.on("pageerror",lambda e:print("ERR",e))
            q={"a":a,"s":STATE.get(s,s)}; q.update(extra)
            url=BASE+"?"+"&".join(f"{k}={v}" for k,v in q.items())
            pg.goto(url,wait_until="networkidle")
            try: pg.wait_for_function("window.__taReady===true",timeout=40000)
            except Exception as e: print("TIMEOUT",url)
            time.sleep(.4)
            name=f"{a}-{th}-{vp}-{s}"
            os.makedirs(f"shots/{a}",exist_ok=True)
            pg.screenshot(path=f"shots/{a}/{name}.png")
            rr=pg.evaluate("window.__taRects()"); rr["url"]=url.replace(BASE,"clock/ta.html")
            json.dump(rr,open(f"shots/{a}/{name}.json","w"))
            print(name,flush=True)
            c.close()
        b.close()
if __name__=="__main__": main(sys.argv[1:])
