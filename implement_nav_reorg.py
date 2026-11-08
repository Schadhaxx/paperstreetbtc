#!/usr/bin/env python3
"""Menu reorg v3 — implement the approved nav on all 14 nav pages.

Replaces the 8-link desktop <nav> and the 8-link .mnav-menu with the
5-tab structure (Sleeves click-to-open dropdown + Portfolio Lab +
Live BTC Chart + The Desk + Articles). Per-page href prefixes:
  root (index.html):        ""
  depth 1 (compare/, recap/): "../"
  depth 2 (recap/2026-XX/):   "../../"
"""
import re, pathlib

ROOT = pathlib.Path('/home/hatch/workspace/ps-nav-reorg')

PAGES = [
    ('index.html', ''),
    ('compare/index.html', '../'),
    ('recap/index.html', '../'),
] + [(f'recap/2026-{m:02d}/index.html', '../../') for m in range(1, 12)]

def nav_html(p):
    # p = prefix for homepage anchors, e.g. '' or '../index.html' or '../../index.html'
    return f'''    <nav>
      <div class="desk-drop">
        <button type="button" class="desk-tab" aria-expanded="false" aria-haspopup="true">Sleeves <span class="desk-chev">\u25be</span></button>
        <div class="desk-panel">
          <a href="{p}#principles">Principles</a>
          <a href="{p}#sleeves">Sleeves</a>
          <a href="{p}#tracker">Sleeve tracker</a>
          <a href="{p}#rules">Rules</a>
          <a href="{p[:-len('index.html')] if p.endswith('index.html') else p}recap/index.html">Monthly Recap</a>
        </div>
      </div>
      <a href="{p[:-len('index.html')] if p.endswith('index.html') else p}compare/index.html">Portfolio Lab</a>
      <a href="{p[:-len('index.html')] if p.endswith('index.html') else p}clock/index.html">Live BTC Chart</a>
      <a href="{p[:-len('index.html')] if p.endswith('index.html') else p}screener.html">The Desk</a>
      <a href="{p}#articles">Articles</a>
    </nav>'''

def mnav_html(p):
    d = p[:-len('index.html')] if p.endswith('index.html') else p
    return f'''  <div class="mnav-menu" id="mnavMenu" hidden>
    <div class="mnav-drop">
      <button type="button" class="mnav-tab" aria-expanded="false">Sleeves <span class="nav-chev">\u25be</span></button>
      <div class="mnav-sub">
        <a href="{p}#principles">Principles</a>
        <a href="{p}#sleeves">Sleeves</a>
        <a href="{p}#tracker">Sleeve tracker</a>
        <a href="{p}#rules">Rules</a>
        <a href="{d}recap/index.html">Monthly Recap</a>
      </div>
    </div>
    <a href="{d}compare/index.html">Portfolio Lab</a>
    <a href="{d}clock/index.html">Live BTC Chart</a>
    <a href="{d}screener.html">The Desk</a>
    <a href="{p}#articles">Articles</a>
  </div>'''

NAV_RE = re.compile(r'<nav>.*?</nav>', re.DOTALL)
MNAV_RE = re.compile(r'<div class="mnav-menu" id="mnavMenu" hidden>.*?</div>', re.DOTALL)

changed = []
for rel, prefix in PAGES:
    path = ROOT / rel
    text = path.read_text()
    # homepage-anchor prefix: '' on root, else the index.html path
    hp = '' if prefix == '' else prefix + 'index.html'
    nav = nav_html(hp)
    mnav = mnav_html(hp)
    n1, n2 = len(NAV_RE.findall(text)), len(MNAV_RE.findall(text))
    assert n1 == 1, f'{rel}: found {n1} <nav> blocks'
    assert n2 == 1, f'{rel}: found {n2} mnav-menu blocks'
    text2 = NAV_RE.sub(lambda _: nav, text, count=1)
    text2 = MNAV_RE.sub(lambda _: mnav, text2, count=1)
    assert 'Compare' not in NAV_RE.search(text2).group(0), f'{rel}: nav still has Compare'
    assert '>Tools<' not in text2.split('mnavMenu')[0][:0]  # no-op guard
    path.write_text(text2)
    changed.append(rel)
    print(f'{rel}: nav + mnav replaced')

print(f'\n{len(changed)} pages updated')

# --- nav.css: append the v3 dropdown styles ---
css = (ROOT / 'assets/css/nav.css').read_text()
assert 'desk-drop' not in css
css += '''
/* Menu reorg (8 Nov 2026, v3, Sunil-approved): five main tabs; Sleeves is a
   click-to-open dropdown on desktop (>=1000px) and a tap-to-expand item in
   the hamburger menu below 1000px. Clicking Sleeves only opens/closes its
   menu; it never navigates. The "Sleeves" link inside each menu goes to
   #sleeves. Breakpoint stays at 1000px as the live site does today (so
   iPad portrait 768px keeps the hamburger). */
/* Desktop Sleeves dropdown */
.desk-drop{position:relative;display:flex;align-items:center}
.desk-tab{background:none;border:0;padding:0;margin:0;color:var(--muted,#94a3b8);font:500 .95rem Outfit,Inter,sans-serif;cursor:pointer;display:inline-flex;align-items:center;gap:5px;white-space:nowrap}
.desk-tab:hover{color:var(--text,#e8eef7)}
.desk-tab:focus-visible{outline:2px solid #22d3ee;outline-offset:2px}
.desk-chev{font-size:.65rem;color:#94a3b8;transition:transform .2s}
.desk-drop.open .desk-chev{transform:rotate(180deg)}
.desk-panel{display:none;position:absolute;top:calc(100% + 10px);left:0;width:232px;background:rgba(15,23,42,.98);border:1px solid var(--border,#1e293b);border-radius:12px;box-shadow:0 12px 30px rgba(0,0,0,.45);padding:6px;z-index:30}
.desk-drop.open .desk-panel{display:block}
.desk-panel a{display:flex;align-items:center;min-height:44px;padding:0 12px;color:var(--muted,#94a3b8);font:500 .95rem Outfit,Inter,sans-serif;text-decoration:none;border-left:2px solid rgba(34,211,238,.35);margin:2px 6px;border-radius:6px}
.desk-panel a:hover{color:#22d3ee}
@media (max-width:1180px){.header nav .desk-tab{font-size:.82rem}.desk-panel a{font-size:.82rem}}
@media (prefers-reduced-motion:reduce){.desk-chev{transition:none}}
/* Mobile Sleeves dropdown inside the hamburger menu */
.mnav-drop{border-bottom:1px solid var(--border,#1e293b)}
.mnav-tab{display:flex;align-items:center;justify-content:space-between;width:100%;min-height:48px;padding:0 8px;background:none;border:0;color:var(--muted,#94a3b8);font:500 1rem Outfit,Inter,sans-serif;cursor:pointer;text-align:left}
.mnav-tab:hover{color:#22d3ee}
.nav-chev{font-size:.65rem;color:#94a3b8;transition:transform .2s}
.mnav-sub{display:none;padding:2px 0 8px}
.mnav-drop.open .mnav-sub{display:block}
.mnav-drop.open .nav-chev{transform:rotate(180deg)}
.mnav-sub a{display:flex;align-items:center;min-height:44px;padding:0 8px 0 24px;color:var(--muted,#94a3b8);font:500 .95rem Outfit,Inter,sans-serif;text-decoration:none;border-left:2px solid rgba(34,211,238,.35);margin-left:8px}
.mnav-sub a:hover{color:#22d3ee}
'''
(ROOT / 'assets/css/nav.css').write_text(css)
print('nav.css: v3 styles appended')

# --- s7.js: append the dropdown toggle behaviour (s7.js is unpinned) ---
js = (ROOT / 'assets/js/s7.js').read_text()
assert 'desk-tab' not in js
js += '''
/* Menu reorg (8 Nov 2026, v3): Sleeves dropdowns — desktop click-to-open
   (.desk-drop) and hamburger tap-to-expand (.mnav-drop). Sleeves only
   opens/closes its menu; it never navigates. */
(function(){
function closeDesk(){document.querySelectorAll('.desk-drop.open').forEach(function(x){x.classList.remove('open');});document.querySelectorAll('.desk-tab').forEach(function(x){x.setAttribute('aria-expanded','false');});}
document.querySelectorAll('.desk-tab').forEach(function(b){
  b.addEventListener('click',function(e){
    e.stopPropagation();
    var d=b.closest('.desk-drop');if(!d)return;
    var wasOpen=d.classList.contains('open');
    closeDesk();
    if(!wasOpen){d.classList.add('open');b.setAttribute('aria-expanded','true');}
  });
});
document.querySelectorAll('.desk-panel a').forEach(function(a){a.addEventListener('click',closeDesk);});
document.addEventListener('click',function(e){if(!e.target.closest('.desk-drop'))closeDesk();});
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeDesk();});
document.querySelectorAll('.mnav-tab').forEach(function(b){
  b.addEventListener('click',function(){
    var d=b.closest('.mnav-drop');if(!d)return;
    var wasOpen=d.classList.contains('open');
    document.querySelectorAll('.mnav-drop.open').forEach(function(x){x.classList.remove('open');});
    document.querySelectorAll('.mnav-tab').forEach(function(x){x.setAttribute('aria-expanded','false');});
    if(!wasOpen){d.classList.add('open');b.setAttribute('aria-expanded','true');}
  });
});
})();
'''
(ROOT / 'assets/js/s7.js').write_text(js)
print('s7.js: toggle behaviour appended')

# --- nav.css pin bump cr022 -> cr023 on the 4 pinned callers ---
for rel in ['index.html', 'compare/index.html', 'recap/index.html', 'screener.html']:
    p = ROOT / rel
    t = p.read_text()
    assert 'nav.css?v=cr022' in t, rel
    p.write_text(t.replace('nav.css?v=cr022', 'nav.css?v=cr023'))
    print(f'{rel}: nav.css pin cr022 -> cr023')
print('\nDONE')
