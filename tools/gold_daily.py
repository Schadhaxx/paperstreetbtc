"""Build assets/data/gold-daily.json: Yahoo Finance GC=F (COMEX gold front-month futures) daily closes, ET dates.
Empty closes are skipped (never filled). Same shape as spx-daily.json. The chart extends newer sessions with GLD % moves from history.json."""
import json, datetime as dt, urllib.request
from zoneinfo import ZoneInfo
u='https://query1.finance.yahoo.com/v8/finance/chart/GC=F?period1=1281916800&period2=%d&interval=1d'%(int(dt.datetime.now().timestamp())+86400)
r=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=30))['chart']['result'][0]
et=ZoneInfo('America/New_York');m={}
for t,v in zip(r['timestamp'],r['indicators']['quote'][0]['close']):
    if v is None: continue
    m[dt.datetime.fromtimestamp(t,et).date().isoformat()]=round(v,2)
d=[[k,m[k]] for k in sorted(m) if k>='2010-08-17']
today=dt.datetime.now(et).date().isoformat()
d=[p for p in d if p[0]<today]
json.dump({'v':1,'source':'Yahoo Finance GC=F daily close (COMEX gold futures, USD/oz, ET dates)','end':d[-1][0],'d':d},open('assets/data/gold-daily.json','w'),separators=(',',':'))
print(d[0],d[-1],len(d))
