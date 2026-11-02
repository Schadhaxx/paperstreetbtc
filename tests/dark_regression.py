#!/usr/bin/env python3
"""Dark-regression check for the opt-in light mode.

Screenshots every shipped page with NO query and EMPTY localStorage on two
static servers (BASE = main checkout, HEAD = this branch) under the same fixed
clock, same local data, external network blocked and animations disabled, at
390px and 1280px, and requires pixel-identical results.

Two comparisons per page:
  strict : raw screenshots.
  masked : HEAD with the new footer theme link (.ps-theme-link) hidden.
The footer pages (index, monthly recaps) gain one visible "Light version"
line by design, so only "masked" must be identical there; every other page
must be identical in "strict".

usage: python3 tests/dark_regression.py BASE_DIR HEAD_DIR OUT_DIR
"""
import os, sys, json, threading, functools, http.server, socketserver
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

PAGES = ['index.html', 'screener.html', 'compare/index.html', 'custom/index.html', 'recap/index.html'] + \
        ['recap/2026-%02d/index.html' % m for m in range(1, 11)]
FOOTER = {'index.html'} | {'recap/2026-%02d/index.html' % m for m in range(1, 11)}
WIDTHS = [390, 1280]
CLOCK = '2026-10-30T20:00:00Z'
exe = next((p for p in ['/usr/bin/google-chrome', '/usr/bin/chromium'] if os.path.exists(p)), None)


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


def serve(d):
    h = functools.partial(Q, directory=d)
    s = socketserver.ThreadingTCPServer(('127.0.0.1', 0), h); s.daemon_threads = True
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, 'http://127.0.0.1:%d/' % s.server_address[1]


def shoot(b, url, w, path, hide_link=False, storage=None):
    ctx = b.new_context(viewport={'width': w, 'height': 900}, device_scale_factor=1, reduced_motion='reduce')
    ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith('http://127.0.0.1') else r.abort())
    if storage is not None:
        ctx.add_init_script('try{localStorage.setItem("ps-theme",%s)}catch(e){}' % json.dumps(storage))
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'net::ERR_FAILED' not in m.text and 'Failed to load resource' not in m.text else None)
    pg.clock.set_fixed_time(CLOCK)
    pg.goto(url, wait_until='networkidle')
    pg.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}' +
                     ('.ps-theme-link{display:none!important}' if hide_link else ''))
    pg.evaluate('document.fonts.ready.then(function(){return 1})')
    pg.wait_for_timeout(800)
    pg.screenshot(path=path, full_page=True, animations='disabled')
    theme = pg.evaluate('document.documentElement.getAttribute("data-theme")')
    ctx.close()
    return errs, theme


def diff(a, b):
    A, B = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
    if A.size != B.size: return 'size %s vs %s' % (A.size, B.size)
    bb = ImageChops.difference(A, B).getbbox()
    return None if bb is None else 'bbox %s' % (bb,)


def main():
    base, head, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    (s1, u1), (s2, u2) = serve(base), serve(head)
    rows, fail = [], 0
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        # warm-up (first cold load in a fresh browser can paint before web fonts settle)
        for w in WIDTHS:
            shoot(b, u1 + PAGES[0], w, out + '/_warmup.png'); shoot(b, u2 + PAGES[0], w, out + '/_warmup.png')
        for pg in PAGES:
            for w in WIDTHS:
                n = pg.replace('/', '_').replace('.html', '') + '_%d' % w
                fa, fa2, fb, fm = ['%s/%s_%s.png' % (out, n, k) for k in ('base', 'base2', 'head', 'headmasked')]
                e1, _ = shoot(b, u1 + pg, w, fa)
                shoot(b, u1 + pg, w, fa2)
                e2, th = shoot(b, u2 + pg, w, fb)
                shoot(b, u2 + pg, w, fm, hide_link=True)
                # garbage storage value must also render dark, identically
                fg = '%s/%s_headgarbage.png' % (out, n)
                e3, thg = shoot(b, u2 + pg, w, fg, hide_link=True, storage='banana')
                noise = diff(fa, fa2)
                strict, masked, garb = diff(fa, fb), diff(fa, fm), diff(fa, fg)
                ok = noise is None and masked is None and garb is None and th is None and thg is None and \
                     (strict is None or pg in FOOTER) and not (set(e2) - set(e1))
                fail += not ok
                rows.append(dict(page=pg, width=w, base_stable=noise is None, strict=strict or 'identical',
                                 masked=masked or 'identical', garbage=garb or 'identical', theme_attr=th,
                                 new_console_errors=sorted(set(e2) - set(e1)), ok=ok))
                print(('PASS' if ok else 'FAIL'), pg, w, 'strict=' + (strict or 'identical'), 'masked=' + (masked or 'identical'),
                      'garbage=' + (garb or 'identical'), '' if noise is None else 'BASE-UNSTABLE ' + noise, flush=True)
        b.close()
    json.dump(rows, open(out + '/dark_regression.json', 'w'), indent=1)
    print('dark regression:', 'PASS' if not fail else 'FAIL (%d)' % fail)
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()
