#!/usr/bin/env python3
"""Headless matrix (P1-P4): 4 time zones x 390/1280 px x faked clocks + recap ticker states + ET on every page + reduced motion.
usage: python3 tests/headless_matrix.py BASE_URL [OUTDIR]     exit 1 on any problem."""
import json, os, re, sys
from datetime import datetime
from playwright.sync_api import sync_playwright
B = sys.argv[1].rstrip('/'); OUT = sys.argv[2] if len(sys.argv) > 2 else '/tmp/headless_matrix'; os.makedirs(OUT, exist_ok=True)
exe = next((p for p in ['/usr/bin/google-chrome', '/usr/bin/chromium'] if os.path.exists(p)), None)
TZ = ['America/New_York', 'Asia/Tokyo', 'America/Los_Angeles', 'Europe/London']
# (name, utc instant, market state the labels must show)
CL = [('sat', '2026-10-24T19:00:00+00:00', 'closed'), ('thanksgiving', '2026-11-26T17:00:00+00:00', 'closed'),
      ('fri-open', '2026-10-23T15:00:00+00:00', 'open'), ('early-close-after', '2026-11-27T22:30:00+00:00', 'closed'),
      ('nov2-afterhours', '2026-11-02T23:30:00+00:00', 'any')]
P = []; n = 0
def bad(*a): P.append(a); print('PROBLEM', *a, flush=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    for name, iso, state in CL:
        for w in (390, 1280):
            for tz in TZ:
                n += 1; c = b.new_context(viewport={'width': w, 'height': 900}, timezone_id=tz); pg = c.new_page()
                pg.clock.install(time=datetime.fromisoformat(iso)); pg.goto(B + '/'); pg.wait_for_timeout(6500); t = pg.inner_text('body')
                bt = pg.inner_text('#btcTime'); yl = pg.inner_text('#ytdLbl').upper(); chips = ' '.join(pg.eval_on_selector_all('.pulse-chg', 'e=>e.map(x=>x.innerText)'))
                over = pg.evaluate("[...document.querySelectorAll('.pulse-card,.pf-card')].filter(e=>e.scrollWidth>e.clientWidth+1).length")
                nz = [x for x in re.findall(r'\b\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AP]M)?(?:\s?ET)?', t) if not x.endswith('ET')]
                print(name, w, tz, '|', bt, '|', yl, '|', chips[:40], flush=True)
                if not bt.endswith(' ET') or nz: bad(name, w, tz, 'time without ET', bt, nz)
                if over: bad(name, w, tz, 'overflow', over)
                if state == 'closed' and ('today' in chips or yl == 'YTD (LIVE)' or 'Live market value' in t): bad(name, w, tz, 'live/today on a closed day', yl, chips[:60])
                if state == 'open' and 'today' not in chips: bad(name, w, tz, 'open session should say today', chips[:60])
                if w == 390 and tz in ('America/New_York', 'Asia/Tokyo'): pg.screenshot(path=f'{OUT}/home-{name}-{w}-{tz.split("/")[1]}.png')
                c.close()
    vals = {}; import urllib.request, time as _t
    SNAP = {k: urllib.request.urlopen(f'https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/{k}?t={int(_t.time())}', timeout=30).read() for k in ('prices.json', 'history.json')}
    def frozen(route):   # identical data for every zone: the 5-min prices.json refresh must not make zones differ
        u = route.request.url
        for k, body in SNAP.items():
            if k in u: return route.fulfill(status=200, body=body, headers={'content-type': 'application/json', 'access-control-allow-origin': '*'})
        return route.abort()
    for tz in TZ:
        c = b.new_context(timezone_id=tz); pg = c.new_page(); pg.clock.install(time=datetime.fromisoformat('2026-10-24T19:00:00+00:00'))
        pg.route(re.compile(r'.*(coinbase|coingecko|prices\.json|history\.json).*'), frozen); pg.goto(B + '/'); pg.wait_for_timeout(6000)
        vals[tz] = pg.eval_on_selector_all('.pf-card .pf-val, .pulse-val', 'e=>e.map(x=>x.innerText)'); c.close()
    n += 1
    if len({json.dumps(v) for v in vals.values()}) != 1: bad('values differ by zone', vals)
    # SL cycle-1 #6: a stale prices.json (10 days old) must never be labelled live, in or out of market hours
    ST = json.loads(SNAP['prices.json']); ST['updated'] = '2026-10-23T20:50:00Z'; STB = json.dumps(ST).encode()
    def stale(route):
        u = route.request.url
        if 'prices.json' in u: return route.fulfill(status=200, body=STB, headers={'content-type': 'application/json', 'access-control-allow-origin': '*'})
        if 'history.json' in u: return route.fulfill(status=200, body=SNAP['history.json'], headers={'content-type': 'application/json', 'access-control-allow-origin': '*'})
        return route.abort()
    for lab, iso in (('Nov 2 7:30 PM EST', '2026-11-03T00:30:00+00:00'), ('Nov 2 11:00 AM EST (market open)', '2026-11-02T16:00:00+00:00')):
        for tz in ('America/New_York', 'Asia/Tokyo'):
            n += 1; c = b.new_context(viewport={'width': 390, 'height': 900}, timezone_id=tz); pg = c.new_page(); pg.clock.install(time=datetime.fromisoformat(iso))
            pg.route(re.compile(r'.*(coinbase|coingecko|kraken|prices\.json|history\.json).*'), stale); pg.goto(B + '/'); pg.wait_for_timeout(6500)
            t = pg.inner_text('body'); yl = pg.inner_text('#ytdLbl').upper()
            print('stale', lab, tz, '|', yl, flush=True)
            if 'YTD (LIVE)' == yl or 'Live market value' in t: bad('stale prices.json labelled live', lab, tz, yl)
            pg.screenshot(path=f'{OUT}/home-stale-{"open" if "AM" in lab else "evening"}-{tz.split("/")[1]}.png'); c.close()
    for w in (360, 1280):
        for mode in ('blocked', 'normal', 'missing-symbol'):
            n += 1; c = b.new_context(viewport={'width': w, 'height': 800}); pg = c.new_page()
            if mode != 'normal': pg.route(re.compile(r'.*prices\.json.*'), lambda r: r.abort())
            pg.goto(B + '/recap/2026-06/'); pg.wait_for_timeout(3500)
            if mode == 'missing-symbol': pg.evaluate("delete PX.stocks.STRC; rT(null)")
            rows = [l for l in pg.inner_text('#ticker').split('\n') if l.strip()]; print('recap', w, mode, rows, flush=True)
            hdr = pg.inner_text('table.btcm tr')
            if 'Low close (in June)' not in hdr or 'High close (in June)' not in hdr: bad('recap headers', hdr)
            if mode == 'blocked' and (len(rows) < 4 or any('%' in r for r in rows[1:3]) or not all('offline' in r for r in rows[1:3])): bad('recap fallback', rows)
            if mode == 'missing-symbol' and not any(r.startswith('STRC') and 'no data' in r for r in rows): bad('missing symbol placeholder', rows)
            if any(re.search(r'\d{4}-\d\d-\d\d', r) for r in rows): bad('raw ISO date in ticker', rows)
            pg.screenshot(path=f'{OUT}/recap-jun-{mode}-{w}.png'); c.close()
    c = b.new_context(); pg = c.new_page(); miss = []
    for path in ['/', '/compare/', '/custom/', '/recap/'] + [f'/recap/2026-{m:02d}/' for m in range(1, 11)]:
        n += 1; pg.goto(B + path); pg.wait_for_timeout(400)
        if pg.evaluate('typeof ET') != 'object': miss.append(path)
    if miss: bad('ET missing', miss)
    c.close()
    for w in (390, 1280):
        n += 1; c = b.new_context(reduced_motion='reduce', viewport={'width': w, 'height': 900}); pg = c.new_page(); pg.goto(B + '/'); pg.wait_for_timeout(6000)
        r = pg.evaluate("""(async()=>{const c=document.querySelector('.pf-card');c.click();await new Promise(r=>setTimeout(r,300));
          window.dispatchEvent(new CustomEvent('btcprice',{detail:{usd:12345,chg:0,src:'t',time:'x'}}));await new Promise(r=>setTimeout(r,400));
          const n=document.querySelector('.pf-card[data-i="'+c.dataset.i+'"]');return {same:n===c,open:c.classList.contains('open')}})()""")
        if not (r['same'] and r['open']): bad('card node lost', w, r)
        c.close()
    b.close()
print('HEADLESS RUNS', n, 'PROBLEMS', len(P)); sys.exit(1 if P else 0)
