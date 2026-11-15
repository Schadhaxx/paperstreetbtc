import json,glob,os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
SH=Path("shots")
BG=(5,7,15);LAB=(11,18,36);ACC=(34,211,238);WH=(232,238,247);MU=(148,163,184);OK=(34,197,94);BAD=(248,113,113);YEL=(250,204,21)
def F(s,b=False):
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf"%("-Bold" if b else ""),s)
NAMES={"A":"A · Range-row tail","B":"B · One swipe lane","C":"C · Compact chart-type picker","D":"D · Third toolbar row"}
TAG={"A":"TA pinned at the end of the range row (1D…Max); row 2 untouched; zero height cost.",
     "B":"Chart type + asset chips share one swipe lane; TA pinned at its end; zero height cost.",
     "C":"Line/Candles/size collapse into one 'Line ▾' pill; row 2 = assets + type + TA; zero height cost.",
     "D":"Chart type moves to its own third row with TA at the end (+ active chips); costs ~38px."}
PROT=["BTC price","Keep screen on","Exit full screen","Light/Dark pill","Full-screen buttons"]
def inter(a,b):
    if not a or not b: return 0
    w=min(a["r"],b["r"])-max(a["x"],b["x"]);h=min(a["b"],b["b"])-max(a["y"],b["y"])
    return max(0,w)*max(0,h)
def check(name):
    p=SH/name[0]/(name+".json")
    if not p.exists(): return None
    d=json.load(open(p));out={"panel":bool(d["panel"])}
    hits=[];
    for k in PROT:
        r=d["prot"].get(k)
        if d["panel"] and r and d["vis"].get(k):
            a=inter(d["panel"],r)
            if a>0: hits.append(f"{k} ({a:.0f}px²)")
    out["hits"]=hits
    if d["panel"]:
        P=d["panel"];out["inview"]=P["x"]>=0 and P["y"]>=0 and P["r"]<=d["vw"] and P["b"]<=d["vh"];out["pvis"]=d.get("panelVisible");S_=d.get("stage");out["inview"]=out["inview"] and (not S_ or (P["y"]>=S_["y"]-0.5 and P["b"]<=S_["b"]+0.5 and P["x"]>=S_["x"]-0.5 and P["r"]<=S_["r"]+0.5))
    out["vis"]=[k for k in PROT if d["vis"].get(k)]
    return out,d
def mark(im,d,name):
    """dashed outline of reserved slot for 'today' shots"""
    r=d.get("reserved")
    if not r: return im
    s=im.width/d["vw"];dr=ImageDraw.Draw(im)
    x0,y0,x1,y1=[int(v*s) for v in (r["x"]-2,r["y"]-2,r["r"]+2,r["b"]+2)]
    for x in range(x0,x1,12): dr.line([(x,y0),(min(x+6,x1),y0)],fill=YEL,width=3);dr.line([(x,y1),(min(x+6,x1),y1)],fill=YEL,width=3)
    for y in range(y0,y1,12): dr.line([(x0,y),(x0,min(y+6,y1))],fill=YEL,width=3);dr.line([(x1,y),(x1,min(y+6,y1))],fill=YEL,width=3)
    return im
def cell(name,maxw,maxh,annot=True):
    p=SH/name[0]/(name+".png")
    im=Image.open(p).convert("RGB")
    c=check(name)
    if c and annot and name.endswith("today"): im=mark(im,c[1],name)
    im.thumbnail((maxw,maxh),Image.Resampling.LANCZOS)
    return im,c
def grid(title,sub,rows,out,colw=300):
    # rows: list of (rowlabel, [(caption,name,maxw,maxh)])
    pad=20;gap=14;head=96
    rowimgs=[]
    for rl,items in rows:
        ims=[(cap,)+cell(n,mw,mh) for cap,n,mw,mh in items]
        rowimgs.append((rl,ims))
    W=max(pad*2+sum(i[1].width for i in ims)+gap*(len(ims)-1) for rl,ims in rowimgs)
    W=max(W,1100)
    H=head+sum(34+max(i[1].height for i in ims)+50+gap for rl,ims in rowimgs)+pad
    cv=Image.new("RGB",(W,H),BG);dr=ImageDraw.Draw(cv)
    dr.text((pad,18),title,font=F(30,True),fill=WH);dr.text((pad,58),sub,font=F(15),fill=MU)
    y=head
    for rl,ims in rowimgs:
        dr.text((pad,y+6),rl,font=F(17,True),fill=ACC);y+=34;x=pad;mh=max(i[1].height for i in ims)
        for cap,im,c in ims:
            cv.paste(im,(x,y));dr.rectangle([x,y,x+im.width-1,y+im.height-1],outline=(30,41,59))
            dr.text((x,y+im.height+6),cap,font=F(13,True),fill=WH)
            if c:
                o,_=c
                if o["panel"]:
                    t="no overlap ✓" if not o["hits"] and o["inview"] and o["pvis"] else ("panel hidden!" if not o["pvis"] else "") if False else "no overlap ✓" if not o["hits"] and o["inview"] and o["pvis"] else ("OVERLAP: "+", ".join(o["hits"]) if o["hits"] else "panel off-screen")
                    dr.text((x,y+im.height+24),t,font=F(12),fill=OK if t.startswith("no") else BAD)
            x+=im.width+gap
        y+=mh+50+gap
    cv.save(out);print(out,cv.size)
P=(250,540);L=(470,220);SE=(230,410)
for a in "ABCD":
    rows=[]
    for th in ["dark","light"]:
        rows.append((f"iPhone 15 portrait 393×852 · {th}",[("1 Today (room reserved)",f"{a}-{th}-p-today",*P),("2 Menu closed (2 on)",f"{a}-{th}-p-closed",*P),("3 Menu open",f"{a}-{th}-p-open",*P),("4 RSI on",f"{a}-{th}-p-rsi",*P),("5 Candles, worst-case row",f"{a}-{th}-p-candles",*P),("6 Candles + menu open",f"{a}-{th}-p-open-candles",*P)]))
    for th in ["dark","light"]:
        rows.append((f"iPhone 15 landscape 852×393 · {th}",[("Today",f"{a}-{th}-l-today",*L),("Menu open",f"{a}-{th}-l-open",*L),("RSI on",f"{a}-{th}-l-rsi",*L)]))
        rows.append((f"Full-screen chart, landscape · {th}",[("Full-screen chart + menu open",f"{a}-{th}-l-fsopen",*L),("Full-screen chart + RSI on",f"{a}-{th}-l-fsrsi",*L)]+([("Full-screen price (TA hidden)",f"{a}-dark-l-fsprice",*L)] if th=="dark" else [])))
    rows.append(("Checks · dark",[("SE 375×667 menu open",f"{a}-dark-se-open",*SE),("SE RSI on",f"{a}-dark-se-rsi",*SE),("SE candles + menu",f"{a}-dark-se-open-candles",*SE),("Portrait FS chart + menu",f"{a}-dark-p-fsopen",*SE),("RSI collapsed",f"{a}-dark-p-rsicol",*SE)]))
    grid(NAMES[a],TAG[a]+"   Yellow dashes = space reserved today. Mockup only — not on the site.",rows,SH/f"sheet-{a}.png")
# overview
rows=[]
for a in "ABCD":
    rows.append((NAMES[a]+" — "+TAG[a],[("Today",f"{a}-dark-p-today",200,433),("Candles (worst case)",f"{a}-dark-p-candles",200,433),("Menu open",f"{a}-dark-p-open",200,433),("RSI on",f"{a}-light-p-rsi",200,433),("Landscape menu open",f"{a}-dark-l-open",440,206),("Landscape RSI on",f"{a}-light-l-rsi",440,206)]))
grid("TA pill on the Live BTC chart — iPhone layout options","Four ways to reserve room now. Same TA panel in all four; they differ in where the pill lives. Mockup only, nothing on the site changed.",rows,SH/"overview.png")
# overlap table
res={}
for p in sorted(glob.glob("shots/*/*.json")):
    n=Path(p).stem;o,d=check(n);res[n]={"panel":o["panel"],"panel_visible":o.get("pvis"),"overlaps":o["hits"],"in_view":o.get("inview"),"protected_visible":o["vis"],"viewport":f'{d["vw"]}x{d["vh"]}'}
json.dump(res,open(SH/"overlap-check.json","w"),indent=1)
withp=[k for k,v in res.items() if v["panel"]];bad=[k for k in withp if res[k]["overlaps"] or not res[k]["in_view"] or not res[k]["panel_visible"]]
print("panel shots",len(withp),"bad",bad)
