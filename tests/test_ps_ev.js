// Tests for Stage 3 light event analytics (assets/js/ps-ev.js).
// Run: node tests/test_ps_ev.js   (node:test, no dependencies, no network)
//
// Loads ps-ev.js in a vm sandbox with a fake DOM and asserts the seven
// events fire from the right hooks, the ?src= tag rides along, the /me/
// opt-out flag and automated browsers suppress sends, and a failed send
// never throws. The real Worker endpoint is never called: sendBeacon and
// fetch are stubs that record their calls.

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const PS_EV = fs.readFileSync(
  path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'assets', 'js', 'ps-ev.js'),
  'utf8',
);
const EV_URL = 'https://paperstreet-quotes.schadha08.workers.dev/ev';

// --- Fake DOM ---------------------------------------------------------------

function matches(el, sel) {
  sel = sel.trim();
  // a[href^="..."]
  const attrPrefix = sel.match(/^([a-z]+)\[href\^="([^"]+)"\]$/i);
  if (attrPrefix) {
    return el.tagName === attrPrefix[1].toUpperCase() &&
      typeof el.getAttribute('href') === 'string' &&
      el.getAttribute('href').startsWith(attrPrefix[2]);
  }
  if (sel.startsWith('#')) return el.id === sel.slice(1);
  if (sel.startsWith('[') && sel.endsWith(']')) {
    return el.getAttribute(sel.slice(1, -1)) !== null;
  }
  return el.tagName === sel.toUpperCase();
}

class FakeEl {
  constructor({ tag = 'button', id = '', attrs = {}, parent = null } = {}) {
    this.tagName = tag.toUpperCase();
    this.id = id;
    this._attrs = { ...attrs };
    this.parent = parent;
  }
  getAttribute(name) {
    return Object.prototype.hasOwnProperty.call(this._attrs, name) ? this._attrs[name] : null;
  }
  closest(selector) {
    const parts = selector.split(',').map((s) => s.trim());
    let el = this;
    while (el) {
      for (const part of parts) if (matches(el, part)) return el;
      el = el.parent;
    }
    return null;
  }
}

function makeStore(initial = {}) {
  const m = new Map(Object.entries(initial));
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => { m.set(k, String(v)); },
    _map: m,
  };
}

// Load ps-ev.js in a fresh sandbox. Returns the sandbox + captured calls.
// opts: pathname, search, readyState, optOut ('1' to set the flag),
// webdriver (true to fake an automated browser), sendBeacon (false to
// omit it, 'fail' to make it return false), fetchCalls (array to record
// fetch calls into).
function loadEv(opts = {}) {
  const beaconCalls = [];
  const fetchCalls = opts.fetchCalls || [];
  const listeners = {};
  const sandbox = {
    console,
    URLSearchParams,
    Blob,
    Date,
    JSON,
    Math,
    RegExp,
    navigator: {
      userAgent: opts.userAgent || 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15',
      webdriver: opts.webdriver || false,
      sendBeacon: opts.sendBeacon === false
        ? undefined
        : (url, blob) => {
            beaconCalls.push({ url, blob });
            return opts.sendBeacon !== 'fail';
          },
    },
    location: { pathname: opts.pathname || '/', search: opts.search || '' },
    localStorage: makeStore(opts.optOut ? { 'ps-no-count': '1' } : {}),
    sessionStorage: makeStore(opts.session || {}),
    document: {
      readyState: opts.readyState || 'complete',
      addEventListener: (type, fn) => {
        (listeners[type] = listeners[type] || []).push(fn);
      },
    },
    fetch: (url, init) => {
      fetchCalls.push({ url, init });
      return Promise.resolve({ ok: true });
    },
    window: {},
  };
  sandbox.window.localStorage = sandbox.localStorage;
  sandbox.window.URLSearchParams = URLSearchParams;
  vm.createContext(sandbox);
  vm.runInContext(PS_EV, sandbox, { filename: 'ps-ev.js' });
  return {
    sandbox,
    beaconCalls,
    fetchCalls,
    listeners,
    fire: (type, event) => { (listeners[type] || []).forEach((fn) => fn(event)); },
  };
}

async function payloads(calls) {
  const out = [];
  for (const c of calls) out.push(JSON.parse(await c.blob.text()));
  return out;
}

// --- Page-open events -------------------------------------------------------

test('desk_open fires on /screener.html load, btc_chart_open on /clock/ load', async () => {
  const desk = loadEv({ pathname: '/screener.html' });
  assert.equal(desk.beaconCalls.length, 1);
  assert.deepEqual(await payloads(desk.beaconCalls), [{ event: 'desk_open', page: '/screener.html', src: '' }]);

  const clock = loadEv({ pathname: '/clock/' });
  assert.equal(clock.beaconCalls.length, 1);
  assert.deepEqual(await payloads(clock.beaconCalls), [{ event: 'btc_chart_open', page: '/clock/', src: '' }]);

  const home = loadEv({ pathname: '/' });
  assert.equal(home.beaconCalls.length, 0);
});

test('page-open events fire on DOMContentLoaded when the script loads early', async () => {
  const ctx = loadEv({ pathname: '/screener.html', readyState: 'loading' });
  assert.equal(ctx.beaconCalls.length, 0);
  ctx.fire('DOMContentLoaded', {});
  assert.equal(ctx.beaconCalls.length, 1);
  assert.deepEqual(await payloads(ctx.beaconCalls), [{ event: 'desk_open', page: '/screener.html', src: '' }]);
});

// --- Delegated clicks ---------------------------------------------------------

test('xfollow fires on the X profile link, btc_chart_open on the header pill', async () => {
  const ctx = loadEv({ pathname: '/' });
  const xlink = new FakeEl({ tag: 'a', attrs: { href: 'https://x.com/PaperstreetBTC' } });
  ctx.fire('click', { target: new FakeEl({ tag: 'span', parent: xlink }) });
  const pill = new FakeEl({ tag: 'button', id: 'hdrTick' });
  ctx.fire('click', { target: pill });
  assert.deepEqual(await payloads(ctx.beaconCalls), [
    { event: 'xfollow', page: '/', src: '' },
    { event: 'btc_chart_open', page: '/', src: '' },
  ]);
});

test('range_switch fires on a BTC chart range pill, compare_use on Compare controls', async () => {
  const ctx = loadEv({ pathname: '/clock/' });
  // The /clock/ load already fired btc_chart_open; clear it.
  ctx.beaconCalls.length = 0;
  const rg = new FakeEl({ tag: 'div', id: 'bcRgs' });
  const pill = new FakeEl({ tag: 'button', attrs: { 'data-r': '1W' }, parent: rg });
  ctx.fire('click', { target: pill });
  assert.deepEqual(await payloads(ctx.beaconCalls), [{ event: 'range_switch', page: '/clock/', src: '' }]);

  const cmp = loadEv({ pathname: '/compare/' });
  const series = new FakeEl({ tag: 'div', id: 'pvSeries' });
  const sBtn = new FakeEl({ tag: 'button', attrs: { 'data-k': 'MSTR' }, parent: series });
  cmp.fire('click', { target: sBtn });
  const range = new FakeEl({ tag: 'div', id: 'pvRange' });
  const rBtn = new FakeEl({ tag: 'button', attrs: { 'data-r': '6M' }, parent: range });
  cmp.fire('click', { target: rBtn });
  assert.deepEqual(await payloads(cmp.beaconCalls), [
    { event: 'compare_use', page: '/compare/', src: '' },
    { event: 'compare_use', page: '/compare/', src: '' },
  ]);
});

test('lab_model fires on the Portfolio Lab sleeve select change', async () => {
  const ctx = loadEv({ pathname: '/compare/' });
  ctx.fire('change', { target: new FakeEl({ tag: 'select', id: 'pvS' }) });
  assert.deepEqual(await payloads(ctx.beaconCalls), [{ event: 'lab_model', page: '/compare/', src: '' }]);
});

test('screener_use fires on search typing, filter and sort clicks', async () => {
  const ctx = loadEv({ pathname: '/screener.html' });
  ctx.beaconCalls.length = 0; // clear the desk_open from load
  ctx.fire('input', { target: new FakeEl({ tag: 'input', id: 'screener-search' }) });
  const filter = new FakeEl({ tag: 'button', attrs: { 'data-filter': 'gainers' } });
  ctx.fire('click', { target: filter });
  const sort = new FakeEl({ tag: 'button', attrs: { 'data-sort': 'ytdPct' } });
  ctx.fire('click', { target: sort });
  const got = await payloads(ctx.beaconCalls);
  assert.equal(got.length, 3);
  assert.ok(got.every((p) => p.event === 'screener_use' && p.page === '/screener.html'));
});

// --- ?src= tag, opt-out, automation ------------------------------------------

test('?src= is captured on arrival, kept for the tab, and sent with events', async () => {
  const ctx = loadEv({ pathname: '/screener.html', search: '?src=x' });
  assert.equal(ctx.sandbox.sessionStorage.getItem('ps-src'), 'x');
  assert.deepEqual(await payloads(ctx.beaconCalls), [{ event: 'desk_open', page: '/screener.html', src: 'x' }]);
  // A later page in the same tab (no tag in the URL) still carries it.
  const later = loadEv({ pathname: '/clock/', session: { 'ps-src': 'x' } });
  assert.deepEqual(await payloads(later.beaconCalls), [{ event: 'btc_chart_open', page: '/clock/', src: 'x' }]);
});

test('an invalid ?src= is dropped, not sent', async () => {
  const ctx = loadEv({ pathname: '/screener.html', search: '?src=bad%20src!' });
  assert.equal(ctx.sandbox.sessionStorage.getItem('ps-src'), null);
  assert.deepEqual(await payloads(ctx.beaconCalls), [{ event: 'desk_open', page: '/screener.html', src: '' }]);
});

test('the /me/ opt-out flag suppresses every send', async () => {
  const ctx = loadEv({ pathname: '/screener.html', optOut: true });
  ctx.fire('click', { target: new FakeEl({ tag: 'button', id: 'hdrTick' }) });
  ctx.fire('input', { target: new FakeEl({ tag: 'input', id: 'screener-search' }) });
  assert.equal(ctx.beaconCalls.length, 0);
  assert.equal(ctx.fetchCalls.length, 0);
  assert.equal(typeof ctx.sandbox.window.__psEv, 'undefined');
});

test('automated browsers (webdriver / headless UA) send nothing', async () => {
  const a = loadEv({ pathname: '/screener.html', webdriver: true });
  assert.equal(a.beaconCalls.length, 0);
  const b = loadEv({ pathname: '/screener.html', userAgent: 'Mozilla/5.0 HeadlessChrome/120.0' });
  assert.equal(b.beaconCalls.length, 0);
});

// --- Fire-and-forget behaviour ------------------------------------------------

test('rapid repeats of one event are deduped', async () => {
  const ctx = loadEv({ pathname: '/' });
  const pill = new FakeEl({ tag: 'button', id: 'hdrTick' });
  ctx.fire('click', { target: pill });
  ctx.fire('click', { target: pill });
  ctx.fire('click', { target: pill });
  assert.equal(ctx.beaconCalls.length, 1);
});

test('a failed sendBeacon falls back to fetch and never throws', async () => {
  const fetchCalls = [];
  const ctx = loadEv({ pathname: '/screener.html', sendBeacon: 'fail', fetchCalls });
  assert.equal(ctx.beaconCalls.length, 1); // sendBeacon was attempted
  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0].url, EV_URL);
  assert.equal(fetchCalls[0].init.method, 'POST');
  assert.equal(fetchCalls[0].init.headers['Content-Type'], 'text/plain');
  assert.equal(JSON.parse(fetchCalls[0].init.body).event, 'desk_open');
});

test('no sendBeacon at all still sends via fetch', async () => {
  const fetchCalls = [];
  const ctx = loadEv({ pathname: '/screener.html', sendBeacon: false, fetchCalls });
  assert.equal(ctx.beaconCalls.length, 0);
  assert.equal(fetchCalls.length, 1);
  assert.equal(JSON.parse(fetchCalls[0].init.body).event, 'desk_open');
});

test('window.__psEv is exposed and ignores unknown event names', async () => {
  const ctx = loadEv({ pathname: '/' });
  const send = ctx.sandbox.window.__psEv;
  assert.equal(typeof send, 'function');
  send('nope');
  assert.equal(ctx.beaconCalls.length, 0);
  send('xfollow');
  assert.equal(ctx.beaconCalls.length, 1);
});
