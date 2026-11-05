#!/usr/bin/env python3
"""Layout checks for the floating Light/Dark pill vs the Top button.

Pill mounts only on index (alongside Top). At 320/390/1280: pill visible on
index; after scroll, pill and Top share vertical center, equal height/radius/
font, no overlap, Top to the right of pill. Other pages must NOT show the pill
(they keep footer links; monthly recaps already have Home/All-recaps fabs).

usage: python3 tests/theme_pill_layout.py SITE_DIR
"""
import os, sys, threading, functools, http.server, socketserver
from playwright.sync_api import sync_playwright

PAGES = ['index.html', 'screener.html', 'compare/index.html', 'custom/index.html',
         'recap/index.html', 'recap/2026-10/index.html', 'recap/2026-11/index.html']
WIDTHS = [320, 390, 1280]
exe = next((p for p in ['/usr/bin/google-chrome', '/usr/bin/chromium'] if os.path.exists(p)), None)
site = sys.argv[1]


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=site)); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
U = 'http://127.0.0.1:%d/' % srv.server_address[1]
fails = 0

def check(name, cond, info=''):
    global fails
    fails += not cond
    print(('PASS ' if cond else 'FAIL ') + name + ((' ' + info) if info and not cond else ''), flush=True)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    for w in WIDTHS:
        for pgname in PAGES:
            ctx = b.new_context(viewport={'width': w, 'height': 900}, reduced_motion='reduce')
            ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith(U) else r.abort())
            pg = ctx.new_page()
            pg.clock.set_fixed_time('2026-10-30T20:00:00Z')
            pg.goto(U + pgname, wait_until='networkidle'); pg.wait_for_timeout(400)
            pill = pg.locator('#psThemePill')
            if pgname != 'index.html':
                check('%s@%d no floating pill' % (pgname, w), pill.count() == 0)
                ctx.close(); continue
            check('%s@%d pill visible at top of page' % (pgname, w), pill.is_visible())
            pb = pill.bounding_box()
            fl = pg.locator('.ps-theme-link')
            if fl.count() and fl.is_visible():
                fb = fl.bounding_box()
                if fb and fb['y'] < 900:
                    overlap = not (pb['x'] + pb['width'] <= fb['x'] or fb['x'] + fb['width'] <= pb['x'] or
                                   pb['y'] + pb['height'] <= fb['y'] or fb['y'] + fb['height'] <= pb['y'])
                    check('%s@%d pill does not overlap footer link' % (pgname, w), not overlap)
            pg.evaluate('window.scrollTo(0, 800)'); pg.wait_for_timeout(500)
            top = pg.locator('#backToTop')
            opacity = pg.evaluate('getComputedStyle(document.getElementById("backToTop")).opacity')
            check('%s@%d Top opacity 1 after scroll' % (pgname, w), opacity == '1', opacity)
            tb = top.bounding_box(); pb = pill.bounding_box()
            check('%s@%d equal height' % (pgname, w), abs(pb['height'] - tb['height']) <= 2, 'pill=%s top=%s' % (pb, tb))
            check('%s@%d same vertical center' % (pgname, w), abs((pb['y'] + pb['height']/2) - (tb['y'] + tb['height']/2)) <= 2)
            overlap = not (pb['x'] + pb['width'] <= tb['x'] or tb['x'] + tb['width'] <= pb['x'] or
                           pb['y'] + pb['height'] <= tb['y'] or tb['y'] + tb['height'] <= pb['y'])
            check('%s@%d pill and Top do not overlap' % (pgname, w), not overlap)
            gap = tb['x'] - (pb['x'] + pb['width'])
            check('%s@%d Top sits to the right of pill with gap' % (pgname, w), gap >= 4, 'gap=%s' % gap)
            styles = pg.evaluate('''() => {
              const p = getComputedStyle(document.getElementById('psThemePill'));
              const t = getComputedStyle(document.getElementById('backToTop'));
              return {pfs:p.fontSize, tfs:t.fontSize, pfw:p.fontWeight, tfw:t.fontWeight,
                      pbr:p.borderRadius, tbr:t.borderRadius, pbg:p.backgroundColor, tbg:t.backgroundColor};
            }''')
            check('%s@%d matching font-size' % (pgname, w), styles['pfs'] == styles['tfs'], str(styles))
            check('%s@%d matching font-weight' % (pgname, w), styles['pfw'] == styles['tfw'], str(styles))
            check('%s@%d matching border-radius' % (pgname, w), styles['pbr'] == styles['tbr'], str(styles))
            check('%s@%d matching background' % (pgname, w), styles['pbg'] == styles['tbg'], str(styles))
            # still no overlap with footer after scrolling to bottom
            pg.evaluate('window.scrollTo(0, document.body.scrollHeight)'); pg.wait_for_timeout(300)
            pb = pill.bounding_box(); fb = fl.bounding_box() if fl.count() else None
            if fb:
                overlap = not (pb['x'] + pb['width'] <= fb['x'] or fb['x'] + fb['width'] <= pb['x'] or
                               pb['y'] + pb['height'] <= fb['y'] or fb['y'] + fb['height'] <= pb['y'])
                check('%s@%d pill does not overlap footer at bottom' % (pgname, w), not overlap,
                      'pill=%s footer=%s' % (pb, fb))
            ctx.close()
    b.close()
print('theme pill layout:', 'PASS' if not fails else 'FAIL (%d)' % fails)
sys.exit(1 if fails else 0)
