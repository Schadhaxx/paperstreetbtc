#!/usr/bin/env python3
"""Layout checks for the floating Light/Dark pill vs the Top button.

Pill mounts only on index (alongside Top). At 320/390/1280: pill visible on
index; after scroll, pill and Top must match computed height, font-family,
font-size, font-weight, line-height, border-radius, padding, and the same
top/bottom edges (within 0.5px), in dark AND light. Other pages must NOT
show the pill.

usage: python3 tests/theme_pill_layout.py SITE_DIR
"""
import os, sys, threading, functools, http.server, socketserver
from playwright.sync_api import sync_playwright

PAGES = ['index.html', 'screener.html', 'compare/index.html', 'custom/index.html',
         'recap/index.html', 'recap/2026-10/index.html', 'recap/2026-11/index.html']
WIDTHS = [320, 390, 1280]
exe = next((p for p in ['/usr/bin/google-chrome', '/usr/bin/chromium'] if os.path.exists(p)), None)
site = sys.argv[1]

MEASURE = '''() => {
  const pEl = document.getElementById('psThemePill');
  const tEl = document.getElementById('backToTop');
  const p = getComputedStyle(pEl), t = getComputedStyle(tEl);
  const pr = pEl.getBoundingClientRect(), tr = tEl.getBoundingClientRect();
  return {
    pfs:p.fontSize, tfs:t.fontSize, pfw:p.fontWeight, tfw:t.fontWeight,
    pff:p.fontFamily, tff:t.fontFamily, plh:p.lineHeight, tlh:t.lineHeight,
    pbr:p.borderRadius, tbr:t.borderRadius, pbg:p.backgroundColor, tbg:t.backgroundColor,
    ppad:p.padding, tpad:t.padding,
    ph:pr.height, th:tr.height, ptop:pr.top, ttop:tr.top, pbot:pr.bottom, tbot:tr.bottom
  };
}'''


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=site)); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
U = 'http://127.0.0.1:%d/' % srv.server_address[1]
fails = 0
COMPUTED = []

def check(name, cond, info=''):
    global fails
    fails += not cond
    print(('PASS ' if cond else 'FAIL ') + name + ((' ' + info) if info and not cond else ''), flush=True)

def assert_match(pgname, w, mode, styles):
    check('%s@%d %s matching font-size' % (pgname, w, mode), styles['pfs'] == styles['tfs'], str(styles))
    check('%s@%d %s matching font-weight' % (pgname, w, mode), styles['pfw'] == styles['tfw'], str(styles))
    check('%s@%d %s matching font-family' % (pgname, w, mode), styles['pff'] == styles['tff'], str(styles))
    check('%s@%d %s matching line-height' % (pgname, w, mode), styles['plh'] == styles['tlh'], str(styles))
    check('%s@%d %s matching border-radius' % (pgname, w, mode), styles['pbr'] == styles['tbr'], str(styles))
    check('%s@%d %s matching padding' % (pgname, w, mode), styles['ppad'] == styles['tpad'], str(styles))
    check('%s@%d %s matching background' % (pgname, w, mode), styles['pbg'] == styles['tbg'], str(styles))
    check('%s@%d %s identical height (<=0.5px)' % (pgname, w, mode), abs(styles['ph'] - styles['th']) <= 0.5,
          'ph=%.3f th=%.3f' % (styles['ph'], styles['th']))
    check('%s@%d %s same top edge (<=0.5px)' % (pgname, w, mode), abs(styles['ptop'] - styles['ttop']) <= 0.5,
          'ptop=%.3f ttop=%.3f' % (styles['ptop'], styles['ttop']))
    check('%s@%d %s same bottom edge (<=0.5px)' % (pgname, w, mode), abs(styles['pbot'] - styles['tbot']) <= 0.5,
          'pbot=%.3f tbot=%.3f' % (styles['pbot'], styles['tbot']))
    line = 'COMPUTED@%d %s: pill h=%.3f ff=%r lh=%s top=%.3f | top-btn h=%.3f ff=%r lh=%s top=%.3f' % (
        w, mode, styles['ph'], styles['pff'], styles['plh'], styles['ptop'],
        styles['th'], styles['tff'], styles['tlh'], styles['ttop'])
    print('  ' + line, flush=True)
    COMPUTED.append(line)

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
            opacity = pg.evaluate('getComputedStyle(document.getElementById("backToTop")).opacity')
            check('%s@%d Top opacity 1 after scroll' % (pgname, w), opacity == '1', opacity)
            tb = pg.locator('#backToTop').bounding_box(); pb = pill.bounding_box()
            overlap = not (pb['x'] + pb['width'] <= tb['x'] or tb['x'] + tb['width'] <= pb['x'] or
                           pb['y'] + pb['height'] <= tb['y'] or tb['y'] + tb['height'] <= pb['y'])
            check('%s@%d pill and Top do not overlap' % (pgname, w), not overlap)
            gap = tb['x'] - (pb['x'] + pb['width'])
            check('%s@%d Top sits to the right of pill with gap' % (pgname, w), gap >= 4, 'gap=%s' % gap)
            assert_match(pgname, w, 'dark', pg.evaluate(MEASURE))
            # light mode
            pg.goto(U + pgname + '?theme=light', wait_until='networkidle'); pg.wait_for_timeout(400)
            pg.evaluate('window.scrollTo(0, 800)'); pg.wait_for_timeout(500)
            assert_match(pgname, w, 'light', pg.evaluate(MEASURE))
            ctx.close()
    b.close()
print('theme pill layout:', 'PASS' if not fails else 'FAIL (%d)' % fails)
sys.exit(1 if fails else 0)
