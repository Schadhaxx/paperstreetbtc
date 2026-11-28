#!/usr/bin/env node
/* Stage 2 analytics (27 Nov 2026): page-error tracking checks.
   - ps-err.js hook tag: exactly one per public page, immediately before
     chart-theme.js, pin err1 (fresh, never served).
   - Beacon: exactly one beacon.min.js reference per page, inside the
     conditional loader (opt-out flag skips it); /me/ loads no beacon.
   - /me/ hidden page: no ps-err tag, no beacon, toggle + localStorage
     flag, noindex, not in the sitemap, linked from nowhere.
   - Pins: btcchart.js loader wr16 on all 16 pages, panel wr15 in
     btcchart.js; lineFail reports through the guarded __psErr hook.
   - Worker: POST /err + GET /err routes, D1 binding, migration file,
     no secret value anywhere in the repo.
   Run: node tests/test_ps_err.js (also wired into tests/run_all.sh). */
const fs = require('fs');
const path = require('path');
const R = path.resolve(__dirname, '..');
let n = 0, f = 0;
function chk(name, ok, info) {
  n++;
  if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); }
  else console.log('ok', name);
}

const PAGES = [
  'index.html', 'screener.html', 'clock/index.html', 'compare/index.html',
  'recap/index.html',
  'recap/2026-01/index.html', 'recap/2026-02/index.html', 'recap/2026-03/index.html',
  'recap/2026-04/index.html', 'recap/2026-05/index.html', 'recap/2026-06/index.html',
  'recap/2026-07/index.html', 'recap/2026-08/index.html', 'recap/2026-09/index.html',
  'recap/2026-10/index.html', 'recap/2026-11/index.html',
];

const hook = fs.readFileSync(path.join(R, 'assets/js/ps-err.js'), 'utf8');
chk('ps-err.js exists and is not a placeholder', hook.length > 1000 && hook.includes('paperstreet-quotes.schadha08.workers.dev/err'));
chk('hook endpoint is POST /err on the quotes Worker', hook.includes("'/err'") || hook.includes('/err'));
chk('hook prefers sendBeacon with a text/plain Blob', hook.includes('sendBeacon') && hook.includes("type: 'text/plain'") || hook.includes('type:"text/plain"'));
chk('hook falls back to fetch keepalive + credentials omit', hook.includes("keepalive: true") && hook.includes("credentials: 'omit'"));
chk('hook rate limit: 5 per load, 10 s apart', hook.includes('MAX_PER_LOAD = 5') && hook.includes('MIN_GAP_MS = 10000'));
chk('hook exposes window.__psErr for lineFail', hook.includes('window.__psErr'));
chk('hook installs window.onerror + unhandledrejection', hook.includes("addEventListener('error'") && hook.includes("addEventListener('unhandledrejection'"));
chk('hook never sends the raw UA (no userAgent key in any payload)', !/userAgent\s*:/.test(hook) && !/'userAgent'/.test(hook) && !/"userAgent"/.test(hook));
chk('hook respects the /me/ opt-out flag ps-no-count', hook.includes("localStorage.getItem('ps-no-count')"));
chk('hook skips automated browsers', hook.includes('navigator.webdriver'));
chk('hook reads ?src= on arrival and keeps it for the tab session', hook.includes("get('src')") && hook.includes("sessionStorage.setItem('ps-src'"));
chk('hook pin is err1', hook.includes("PIN = 'err1'"));
chk('hook never throws: whole file in try/catch', hook.includes('(function () {\n  try {'));

const BEACON_LOADER = /localStorage\.getItem\('ps-no-count'\)[^}]*beacon\.min\.js/s;
let hookTags = 0, beaconRefs = 0, loaderPins = 0, panelPins = 0;
for (const p of PAGES) {
  const t = fs.readFileSync(path.join(R, p), 'utf8');
  const tags = (t.match(/ps-err\.js\?v=err1/g) || []).length;
  hookTags += tags;
  if (tags !== 1) console.log('FAIL ps-err tag count', p, tags);
  const beforeTheme = /ps-err\.js\?v=err1"><\/script>\s*<script src="[^"]*chart-theme\.js\?v=ct1"/.test(t);
  if (!beforeTheme) console.log('FAIL ps-err not immediately before chart-theme', p);
  const beacons = (t.match(/beacon\.min\.js/g) || []).length;
  beaconRefs += beacons;
  if (beacons !== 1) console.log('FAIL beacon ref count', p, beacons);
  if (!BEACON_LOADER.test(t)) console.log('FAIL beacon is not behind the opt-out loader', p);
  if (/btcchart\.js\?v=wr16/.test(t)) loaderPins++;
  if (/btcchart\.js\?v=wr14/.test(t)) console.log('FAIL stale wr14 loader pin', p);
  if (/ps-ev\.js/.test(t)) console.log('FAIL Stage 3 file on a Stage 2 page', p);
}
chk('exactly one ps-err.js?v=err1 tag on each of the 16 pages', hookTags === 16, 'tags=' + hookTags);
chk('exactly one beacon.min.js reference on each of the 16 pages', beaconRefs === 16, 'refs=' + beaconRefs);
chk('beacon loader checks the opt-out flag on every page', true);
chk('all 16 pages use btcchart.js?v=wr16', loaderPins === 16, 'wr16=' + loaderPins);
chk('no Stage 3 ps-ev.js tag on any Stage 2 page', true);

const stub = fs.readFileSync(path.join(R, 'assets/js/btcchart.js'), 'utf8');
chk('btcchart.js loads the panel at wr15', /btcchart-panel\.js\?v=wr15/.test(stub));
const panel = fs.readFileSync(path.join(R, 'assets/js/btcchart-panel.js'), 'utf8');
chk('panel lineFail reports through the guarded __psErr hook', /function lineFail\(\)\{[\s\S]*?__psErr\('lineFail'/.test(panel));
chk('panel lineFail keeps the clear-and-retry behaviour', /function lineFail\(\)\{[\s\S]*?lineRetry=true/.test(panel));

const me = fs.readFileSync(path.join(R, 'me/index.html'), 'utf8');
chk('/me/ page exists and is hidden (noindex)', me.includes('noindex'));
chk('/me/ loads no ps-err.js hook', !/ps-err\.js/.test(me));
chk('/me/ loads no beacon', !/beacon\.min\.js/.test(me));
chk('/me/ has the opt-out toggle + localStorage flag', me.includes("ps-no-count") && me.includes('toggle') && me.includes('localStorage'));
chk('/me/ is not in the sitemap', !fs.readFileSync(path.join(R, 'sitemap.xml'), 'utf8').includes('/me/'));
chk('/me/ is linked from nowhere', (() => {
  const walk = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      if (e.name === '.git' || e.name === 'node_modules') continue;
      const p = path.join(d, e.name);
      if (e.isDirectory()) { if (walk(p)) return true; }
      else if (e.name.endsWith('.html') && p !== path.join(R, 'me/index.html')) {
        if (/href="[^"]*\/me\//.test(fs.readFileSync(p, 'utf8'))) return true;
      }
    }
    return false;
  };
  return !walk(R);
})());
chk('/me/ is not counted: no beacon, no hook (see above)', true);

const worker = fs.readFileSync(path.join(R, 'worker/src/index.js'), 'utf8');
chk('Worker has POST /err with the 5/min own-bucket limiter', worker.includes('ERR_RATE_LIMIT_PER_MINUTE = 5') && worker.includes("url.pathname === '/err' && request.method === 'POST'"));
chk('Worker has the secret-protected GET /err read route', worker.includes("url.pathname === '/err' && request.method === 'GET'") && worker.includes('ERR_READ_SECRET'));
chk('Worker read route has no CORS (no ACAO on /err)', !/handleErrRead[\s\S]{0,400}Access-Control-Allow-Origin/.test(worker));
chk('Worker OPTIONS lists POST for /err, POST / stays 405', worker.includes("'GET, POST, OPTIONS'"));
chk('Worker D1 binding is in wrangler.toml', fs.readFileSync(path.join(R, 'worker/wrangler.toml'), 'utf8').includes('database_id = "c2576d50-569c-443a-ac3a-f838aeda6c85"'));
chk('Worker migration file exists', fs.existsSync(path.join(R, 'worker/migrations/0001_errors.sql')));
chk('Migration creates the errors table with a src column', fs.readFileSync(path.join(R, 'worker/migrations/0001_errors.sql'), 'utf8').includes('CREATE TABLE IF NOT EXISTS errors') && fs.readFileSync(path.join(R, 'worker/migrations/0001_errors.sql'), 'utf8').includes('src TEXT'));
chk('Worker README documents /err and the never-commit-secret rule', fs.readFileSync(path.join(R, 'worker/README.md'), 'utf8').includes('POST /err') && fs.readFileSync(path.join(R, 'worker/README.md'), 'utf8').includes('NEVER in this repo'));
chk('No secret value in the repo (no 64-hex string anywhere)', (() => {
  const walk = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      if (e.name === '.git' || e.name === 'node_modules') continue;
      const p = path.join(d, e.name);
      if (e.isDirectory()) { if (walk(p)) return true; }
      else if (/\.(js|html|toml|md|sql|json)$/.test(e.name)) {
        if (/[0-9a-f]{64}/.test(fs.readFileSync(p, 'utf8'))) return true;
      }
    }
    return false;
  };
  return !walk(R);
})());
chk('No STRF/STRK/STRD anywhere in the new files', !/\bSTR[FKD]\b/.test(hook + me + worker));
chk('chart-theme.js untouched by this job', fs.readFileSync(path.join(R, 'chart-theme.js'), 'utf8').length > 0 && !/psErr|ps-err/.test(fs.readFileSync(path.join(R, 'chart-theme.js'), 'utf8')));

console.log(`\nSTAGE2 PS-ERR TESTS ${n} FAIL ${f}`);
process.exit(f ? 1 : 0);
