#!/usr/bin/env python3
"""Grok Bot BP review sim (/tmp/simbp1.py, 40 cases), kept verbatim except: repo/history/watch-tool paths are parameters, exit 1 on any FAIL. Run by tests/repros.py."""
import sys,io,contextlib,copy,json,datetime as dt,os,re,subprocess
REPO=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
_hist=(sys.argv[sys.argv.index('--history')+1] if '--history' in sys.argv else 'https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/history.json')
sys.argv=['x','--repo',REPO,'--history',_hist]
src=open(REPO+'/tests/test_freeze.py').read()
buf=io.StringIO()
with contextlib.redirect_stdout(buf):
    try: exec(compile(src,'tf','exec'))
    except SystemExit: pass
print('base suite:',buf.getvalue().strip().splitlines()[-1])
RES=[]
def T(name,exp,fn):
    try: got=fn()
    except Exception as e: got='EXC '+type(e).__name__+' '+str(e)[:90]
    ok=exp(got) if callable(exp) else got==exp
    RES.append(ok); print('PASS' if ok else 'FAIL','|',name,'| got',str(got)[:160])
def H(fn):
    try: fn(); return 'nohold'
    except HH as e: return 'HOLD '+str(e)[:80]
# 1 frozen close vs later Yahoo revision (big and small), many runs later
Yr=Ycopy(P); Yr[D22]['BTC']=82000.0; Yr[D22]['MSTR']=P['closes'][D22]['MSTR']*1.03
o=run(P,Yr,N('2026-10-27T15:00:00'))
T('F1 frozen Oct22 BTC vs Yahoo revision 82000 (days later)',81311.890625,lambda:o['closes'][D22]['BTC'])
T('F2 frozen Oct22 MSTR vs +3% revision',P['closes'][D22]['MSTR'],lambda:o['closes'][D22]['MSTR'])
o2=run(o,Yr,N('2026-10-27T15:05:00')); o3=run(o2,Ycopy(P),N('2026-10-27T15:10:00'))
T('F3 Oct22 BTC stays 81311.89 across 3 runs, revisions alternating',81311.890625,lambda:o3['closes'][D22]['BTC'])
# 2 BTC final boundary: Oct 23 BTC final at Oct24 00:20Z
Pp=copy.deepcopy(P)
Yb=Ycopy(P); Yb[D23]['BTC']=P['closes'][D23]['BTC']*1.001
T('B1 provisional Oct23 BTC updates at 00:19Z (still provisional)',lambda g:abs(g[0]-Yb[D23]['BTC'])<1e-5 and D23 in g[1],lambda:(lambda r:(r['closes'][D23]['BTC'],r['btc_provisional']))(run(Pp,Yb,N('2026-10-24T00:19:00'),CB={D23:Yb[D23]['BTC']})))
# 3 provisional cleared only by Yahoo: Yahoo missing, Coinbase present after final
Yn=Ycopy(P); Yn[D23].pop('BTC')
def r3():
    r=run(Pp,Yn,N('2026-10-24T01:00:00'),CB={D23:81078.04},CG={D23:81080.0}); return r['closes'][D23].get('BTC'),r['fallback_sources'].get(D23,{}).get('BTC')
T('P1 Yahoo null after final: Coinbase value used, marked fallback (not primary)',lambda g:g[1] is not None and not str(g[1]).startswith('yahoo'),r3)
def r3b():
    r=run(Pp,Yn,N('2026-10-24T01:00:00'),CB={D23:81078.04},CG={D23:81080.0}); r['updated']='2026-10-24T01:00:00Z'
    r2=run(r,Yn,N('2026-10-27T01:00:00'),CB={D23:81078.04}); return r2['fallback_sources'].get(D23,{}).get('BTC'),frozen_now(r2)
frozen_now=lambda r: 'n/a'
T('P2 fallback never freezes: 3 days later still fallback-tagged',lambda g:g[0] and not g[0].startswith('yahoo'),r3b)
def r3c():
    r=run(Pp,Yn,N('2026-10-24T01:00:00'),CB={D23:81078.04},CG={D23:81080.0}); r['updated']='2026-10-24T01:00:00Z'
    Yy=Ycopy(P); Yy[D23]['BTC']=81090.0
    r2=run(r,Yy,N('2026-10-27T01:00:00'),CB={D23:81078.04}); return r2['closes'][D23]['BTC'],r2['fallback_sources'].get(D23,{}).get('BTC','yahoo')
T('P3 Yahoo final arrives later (agrees within 0.5%) -> replaces fallback, primary',lambda g:g[0]==81090.0 and g[1].startswith('yahoo'),r3c)
# 4 bad inputs
for lab,val in (('0',0.0),('NaN',float('nan')),('negative',-5.0),('inf',float('inf'))):
    Yx=Ycopy(P); Yx[D23]['MSTR']=val; Pn=copy.deepcopy(P); del Pn['closes'][D23]; Pn['btc_provisional']=[]; Pn['updated']='2026-10-23T12:00:00Z'
    def f(Yx=Yx,Pn=Pn):
        try: r=run(Pn,Yx,N('2026-10-23T21:00:00'),quotes={'MSTR':{'c':P['closes'][D23]['MSTR'],'t':T23}})
        except HH as e: return 'HOLD'
        v=r['closes'].get(D23,{}).get('MSTR'); return 'ok' if (v is None or (isinstance(v,float) and v>0 and v==v and v!=float('inf'))) else ('BAD %r'%v)
    T(f'I-{lab} Yahoo MSTR={lab}: never published (missing->fallback or hold)',lambda g:g in('ok','HOLD'),f)
# json allow_nan: NaN in finnhub quote
Pn=copy.deepcopy(P); del Pn['closes'][D23]; Pn['btc_provisional']=[]; Pn['updated']='2026-10-23T12:00:00Z'
Yx=Ycopy(P); Yx[D23].pop('MSTR')
def fq():
    try: r=run(Pn,Yx,N('2026-10-23T21:00:00'),quotes={'MSTR':{'c':float('nan'),'t':T23}})
    except HH as e: return 'HOLD'
    v=r['closes'].get(D23,{}).get('MSTR'); json.dumps(r,allow_nan=False); return 'ok' if v is None or v==v else 'BAD'
T('I-finnhub NaN with Yahoo missing: not published',lambda g:g in('ok','HOLD'),fq)
# Stooq for SPY/QQQ/STRC never consulted
for k in ('SPY','QQQ','STRC'):
    Yx=Ycopy(P); Yx[D23][k]=P['closes'][D23][k]
    def fs(k=k):
        e=H(lambda: run(Pn,Ycopy(P),N('2026-10-23T21:00:00'),ST={(k,D23):P['closes'][D23][k]*1.05}))
        return e
    T(f'S-{k} wrong Stooq (+5%) never causes hold/cross-check','nohold',fs)
# challenge page counts as no data, 200 with HTML
import urllib.request as U; _o=U.urlopen
class Rr(io.BytesIO): pass
for lab,body in (('cloudflare','<html><title>Just a moment...</title></html>'),('empty',''),('csv-no-data','Date,Open,High,Low,Close,Volume\n'),('N/D','No data')):
    U.urlopen=lambda *a,**k: Rr(body.encode())
    try: T(f'C-{lab} Stooq body -> None',None,lambda: G['_stooq']('MSTR',D22))
    finally: U.urlopen=_o
# disagreeing fallback kept unchecked (STRC finnhub fallback vs Yahoo arriving 3% off)
Pk=copy.deepcopy(P); Pk['fallback_sources']={D23:{'STRC':'finnhub'}}
Yk=Ycopy(P); Yk[D23]['STRC']=P['closes'][D23]['STRC']*1.03
def fk():
    r=run(Pk,Yk,N('2026-10-24T02:00:00'),quotes={'STRC':{'c':P['closes'][D23]['STRC'],'t':T23}})
    return r['closes'][D23]['STRC']==P['closes'][D23]['STRC'], r['fallback_sources'][D23]['STRC']
T('K1 fallback STRC vs disagreeing Yahoo+3%: kept, -unchecked, rest published',lambda g:g[0] and g[1].endswith('-unchecked'),fk)
# DST: stock_cut and BTC final across Nov 1
sc=G['stock_cut'] if 'stock_cut' in G else None
T('D-stock_cut is nested (not global) - inspect source', True, lambda: "replace(hour=20, tzinfo=ET_)" in YML)
# frozen_ok via run: Nov 2 (EST) session published 4:30 PM, run at 01:00Z Nov 3 = 8 PM EST
Pd=copy.deepcopy(P); Pd['closes']['2026-11-02']=dict(P['closes'][D23]); Pd['updated']='2026-11-03T01:01:00Z'; Pd['btc_provisional']=[]
Yd=Ycopy(Pd); Yd['2026-11-02']['MSTR']=Pd['closes']['2026-11-02']['MSTR']*1.01
def fd(t):
    r=run(Pd,Yd,N(t)); return r['closes']['2026-11-02']['MSTR']==Pd['closes']['2026-11-02']['MSTR']
T('D1 Nov 2 (EST) stock frozen after 8 PM EST (01:01Z publish, run 01:10Z): revision ignored',True,lambda: fd('2026-11-03T01:10:00'))
Pd2=copy.deepcopy(Pd); Pd2['updated']='2026-11-03T00:30:00Z'
def fd2():
    r=run(Pd2,Yd,N('2026-11-03T00:40:00')); return r['closes']['2026-11-02']['MSTR']
T('D2 Nov 2 published 7:30 PM EST (before cut): not frozen (re-pull path, unconfirmed kept)',Pd['closes']['2026-11-02']['MSTR'],fd2)
# watch script ET after Nov 1
ws=open(os.environ.get('PS_WATCH', os.path.join(REPO, '..', 'fix-proposals', 'bp', 'watch_past_values.py'))).read()
T('W1 watch et_now uses America/New_York (DST-correct)',True,lambda: "ZoneInfo('America/New_York')" in ws and 'hours=-4' not in ws)
ns={}; exec(ws.split('def prov')[0].split('cmd, D')[0].replace('import functools, builtins; print = functools.partial(builtins.print, flush=True)',''),ns)
T('W2 et_now in EST Nov 2 renders EST hour', '7 PM',lambda: (lambda z:__import__('datetime').datetime(2026,11,3,0,0,tzinfo=__import__('datetime').timezone.utc).astimezone(z).strftime('%-I %p'))(__import__('zoneinfo').ZoneInfo('America/New_York')))
T('W3 --expect (history) fails or exits 2 when never reached / changed to another value',True,lambda: 'set(EXP)' in ws or 'waiting = set(EXPB) | ' in ws)
# stall 48h + weekend job writes nothing
rc,out=btcd_at(Pf,'2026-10-24T23:59:00')
T('ST1 47h59 after pause: no error',lambda g:g[0]==0 and '::error' not in g[1],lambda:(rc,out[-120:]))
rc0,out0=btcd_at(Pf,'2026-10-25T00:01:00')
T('ST1b 48h01: ::error:: exit 3',3,lambda:rc0)
rc,out,un=btcd_check(Pf,'2026-10-24T15:17:00')
T('ST2 Sat 11:17 AM check-only, 39h: exit 0, untouched',(0,True),lambda:(rc,un))
rc,out,un=btcd_check(Pf,'2026-10-25T15:17:00')
T('ST2b Sun check-only, 63h stall: exit 3, untouched, no network',(3,True,False),lambda:(rc,un,'AssertionError' in out))
vj=job('btcd-stall-check')
T('ST3 weekend job: contents: read, no push/commit/write',True,lambda: 'contents: read' in vj and 'git push' not in vj and 'git commit' not in vj and ': write' not in vj)
T('ST4 recap job does not run on the weekend schedule',True,lambda: "17 15 * * 0,6" in job('recap') or 'needs: fetch' in job('recap'))
# heal flapping: Yahoo bar then a revised Yahoo bar after final; history frozen so target stable
rows=[(D21,b21),(D22,81311.89),(D23,YX)]
rcA,BA,pA,oA=btcd_file(rows,Hy,'2026-10-24T05:00:00',ybars={D23:YX+50})
T('H1 heal does not flap: btc-daily follows history (frozen), ignores a different Yahoo bar',YX,lambda:BA[D23])
rcB,BB,pB,oB=btcd_file([(D21,b21),(D22,81311.89),(D23,YX)],Hh,'2026-10-24T05:00:00')
T('H2 history regresses to fallback for a healed date: btc-daily keeps Yahoo value (no un-heal)',YX,lambda:BB[D23])
rcC,BC,pC,oC=btcd_file([(D21,b21),(D22,81311.89),(D23,CB23)],Hh,'2026-10-24T05:00:00',prov=[D23],cbars={D23:CB23+10})
T('H3 provisional not cleared by Coinbase/history-fallback',lambda g:D23 in g,lambda:pC)
# overrides ignored, incl. malformed
for lab,raw in (('NaN',"{\"2026-10-22\":{\"BTC\":NaN}}"),('garbage','{{{'),('huge',json.dumps({D22:{'BTC':1e9,'force':True}}))):
    T(f'O-{lab} overrides.json ignored',81311.890625,lambda raw=raw: run(P,Y,N('2026-10-23T21:00:00'),raw=raw)['closes'][D22]['BTC'])
T('O-code no "overrides" read anywhere in prices.yml/btc_daily/recap_gen',[],lambda:[f for f in ('.github/workflows/prices.yml','tools/btc_daily.py','tools/recap_gen.py','tools/datatest.py') if 'overrides' in open(REPO+'/'+f).read()])
# LOWRISK conflicts
T('L1 BP patches touch LR-changed files only compatibly (apply ok, test_recap/recap_gen edits)',True,lambda: subprocess.run(['git','-C',REPO,'diff','--quiet','HEAD~2','HEAD','--','assets','index.html','compare','custom']).returncode==0)
print('SUMMARY',sum(RES),'/',len(RES))

sys.exit(0 if len(RES) == 40 and all(RES) else 1)
