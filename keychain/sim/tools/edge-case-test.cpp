// Edge-case test for the triple-attention hardening (Layer 2).
// Exercises the failure paths the native harness can drive:
//   fail     — boot with NO fetch data and NO fonts: every fetch
//              fails, every .vlw load fails. The sketch must stay
//              honest (stale, not crashed), fall back to built-in
//              fonts (and cache the failed loads), then RECOVER
//              when the data dir is pointed back at good data.
//   poison   — candles-3600.json with malformed rows (a zero-close
//              row, a short row, a zero-time row): the 1W tiles must
//              be identical to the clean-data tiles — the bad rows
//              are skipped, not collapsed into the chart. The
//              expected tiles are DERIVED from the data file at run
//              time (see expected1W): the 1W tiles are the min/max
//              CLOSE of the thinned series, not the raw file's
//              min-low/max-high, and the 7-day window rolls with the
//              file — hardcoding $55,705/$65,476 broke the moment it
//              did (the thinned-close low moved to $56,220.85).
//              Run against data-poison/ (a copy of data/ with the
//              three malformed rows injected into candles-3600.json).
//   fail needs an EMPTY dir (no .json, no .vlw) as dataDir and
//   goodDataDir as the recovery target; the mode now refuses to
//   run if the fail dir contains any fetch data or fonts, because
//   a run pointed at the good data dir fails exactly the first
//   five checks and looks like five firmware bugs (that is how
//   the earlier "5 fail-mode failures" were produced: a setup
//   error, not a firmware bug — the empty-dir run passes 9/9 on
//   both the current firmware and the Step-1 build).
//   interact — rapid range taps; landscape touch-remap round-trip;
//              candle-mode scrub snap + drag-from-pill must not
//              scrub; DEL with a non-numeric index must not delete
//              account 0.
// Usage: edge-case-test <dataDir> <mode> [goodDataDir]
//   fail needs goodDataDir (recovery target); poison/interact use
//   the same dir for everything.
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <cctype>
#include <string>
#include <vector>
#include "sim.h"
#include "TFT_eSPI.h"

float rangeChange();
void savePrefs();
void serialCommand(char *line);

#include "/home/hatch/workspace/ps-keychain-firmware/paperstreet-keychain.ino"

static int nPass = 0, nFail = 0;
static void check(const char *name, bool ok) {
  printf("  [%s] %s\n", ok ? "PASS" : "FAIL", name);
  if (ok) nPass++; else nFail++;
}

static void runLoopFor(unsigned long ms) {
  unsigned long start = (unsigned long)simMillis;
  unsigned long target = start + ms;
  int guard = 0;
  while (simMillis < target && guard++ < 100000) loop();
}

// Same finger pattern as the video tour's tap(): down across two loop
// polls, then lift. Coords are DRAWING coords.
static void tap(int16_t dx, int16_t dy) {
  simSetFinger(true, dx, dy);
  runLoopFor(100);
  runLoopFor(100);
  simSetFinger(false, 0, 0);
  runLoopFor(100);
  runLoopFor(100);
  runLoopFor(100);
}

// Tap a registered button by id (scans btns[], so it follows the
// layout instead of hardcoding coords). Returns false if no such
// button is on screen.
static bool tapBtn(int id) {
  for (int i = 0; i < nBtns; i++) {
    if (btns[i].id == id) {
      tap(btns[i].x + btns[i].w / 2, btns[i].y + btns[i].h / 2);
      return true;
    }
  }
  printf("  [tapBtn] no button id %d on screen (nBtns=%d)\n", id, nBtns);
  return false;
}

// A drag: finger down at (x0,y0), move to (x1,y1), lift. The
// caller asserts state between move and lift via the `afterMove`
// callback (nullptr = no assertion).
static void drag(int16_t x0, int16_t y0, int16_t x1, int16_t y1,
                 void (*afterMove)()) {
  simSetFinger(true, x0, y0);
  runLoopFor(100);
  simSetFinger(true, x1, y1);
  runLoopFor(100);
  if (afterMove) afterMove();
  simSetFinger(false, 0, 0);
  runLoopFor(300);
}

static void settleChart(int wantRange) {
  int guard = 0;
  while (chartRange != wantRange && guard++ < 100) runLoopFor(100);
  runLoopFor(500);
}

static bool g_scrubSnapOk = false;
static void assertScrubSnap() {
  // After a drag in candle mode: scrubbing, a candle is selected,
  // and the series index is that candle's close.
  g_scrubSnapOk = scrubbing && scrubCand >= 0 && scrubCand < dispCandN &&
                  scrubIdx == dispCand[scrubCand].si;
  printf("  scrub state: scrubbing=%d scrubCand=%d dispCandN=%d scrubIdx=%d si=%d\n",
         (int)scrubbing, scrubCand, dispCandN, scrubIdx,
         scrubCand >= 0 && scrubCand < dispCandN ? dispCand[scrubCand].si : -1);
}

static bool g_noScrubOk = false;
static void assertNoScrub() {
  g_noScrubOk = !scrubbing && scrubIdx == -1;
  printf("  drag-from-pill state: scrubbing=%d scrubIdx=%d\n",
         (int)scrubbing, scrubIdx);
}

// ---- Data-independent 1W expectations (poison mode) ----
// Replicates the firmware's 1W pipeline so the test never hardcodes
// a price:
//   fetchCoinbaseCandles(3600, 604800): newest want = 604800/3600+1
//   = 169 rows, malformed rows skipped (size < 6, t <= 0, or any of
//   low/high/open/close <= 0), stored oldest-first;
//   thinInto: stride ceil(n/100), plus the newest point;
//   fetchChart: last close := live spot price (priceUSD), last
//   point's low/high clamped to it.
// In line mode chartMin/Max are the min/max CLOSE of that thinned
// series; in candle mode they are the min LOW / max HIGH of the
// thinned rows (buildCandles buckets sLow/sHigh, which preserves
// the global extremes). A bad row that is NOT skipped still fails
// these checks: a zero close would drag the line low to 0, a
// zero-time row with close 1 would drag it to 1.
struct CandleRow {
  double t = 0, lo = 0, hi = 0, op = 0, cl = 0;
  int n = 0;  // fields present in the row
};

// Bracket-aware scan of candles-3600.json: rows are JSON arrays
// [t, low, high, open, close, vol]; a short row stays a short row
// instead of shifting the flat number stream.
static bool parseCandleFile(const char *path, std::vector<CandleRow> &rows) {
  FILE *f = fopen(path, "r");
  if (!f) return false;
  std::string txt;
  char b[8192];
  size_t n;
  while ((n = fread(b, 1, sizeof(b), f)) > 0) txt.append(b, n);
  fclose(f);
  int depth = 0;
  std::vector<double> cur;
  std::string num;
  auto flushNum = [&]() {
    if (!num.empty()) {
      cur.push_back(strtod(num.c_str(), nullptr));
      num.clear();
    }
  };
  for (size_t i = 0; i < txt.size(); i++) {
    char c = txt[i];
    if (c == '[') {
      depth++;
      if (depth == 2) cur.clear();
    } else if (c == ']') {
      flushNum();
      if (depth == 2) {
        CandleRow r;
        r.n = (int)cur.size();
        r.t = cur.size() > 0 ? cur[0] : 0;
        r.lo = cur.size() > 1 ? cur[1] : 0;
        r.hi = cur.size() > 2 ? cur[2] : 0;
        r.op = cur.size() > 3 ? cur[3] : 0;
        r.cl = cur.size() > 4 ? cur[4] : 0;
        rows.push_back(r);
      }
      depth--;
    } else if (depth == 2 &&
               (isdigit((unsigned char)c) || c == '-' || c == '+' ||
                c == '.' || c == 'e' || c == 'E')) {
      num += c;
    } else if (depth == 2 && c == ',') {
      flushNum();
    }
  }
  return !rows.empty();
}

static bool expected1W(float &expLo, float &expHi,
                       float &expCLo, float &expCHi) {
  std::string path = g_dataDir + "/candles-3600.json";
  std::vector<CandleRow> rows;
  if (!parseCandleFile(path.c_str(), rows)) return false;
  const int want = 604800 / 3600 + 1;  // 169, RANGES[1] spanSec/gran + 1
  int total = (int)rows.size();
  int take = total < want ? total : want;  // newest `take` rows
  std::vector<CandleRow> good;
  for (int i = take - 1; i >= 0; i--) {  // oldest-first, as stored
    const CandleRow &r = rows[i];
    if (r.n < 6) continue;
    if (r.t <= 0 || r.lo <= 0 || r.hi <= 0 || r.op <= 0 || r.cl <= 0)
      continue;
    good.push_back(r);
  }
  if (good.size() < 2) return false;
  int n = (int)good.size();
  std::vector<CandleRow> thin;
  if (n <= 100) {
    thin = good;
  } else {
    int stride = (n + 100 - 1) / 100;
    for (int i = 0; i < n - 1; i += stride) thin.push_back(good[i]);
    thin.push_back(good[n - 1]);  // last slot is always the newest
  }
  thin.back().cl = priceUSD;  // live spot overwrites the last close
  if (thin.back().lo > priceUSD) thin.back().lo = priceUSD;
  if (thin.back().hi < priceUSD) thin.back().hi = priceUSD;
  expLo = expHi = (float)thin[0].cl;
  expCLo = expCHi = 0;
  expCLo = (float)thin[0].lo;
  expCHi = (float)thin[0].hi;
  for (size_t i = 0; i < thin.size(); i++) {
    if (thin[i].cl < expLo) expLo = (float)thin[i].cl;
    if (thin[i].cl > expHi) expHi = (float)thin[i].cl;
    if (thin[i].lo < expCLo) expCLo = (float)thin[i].lo;
    if (thin[i].hi > expCHi) expCHi = (float)thin[i].hi;
  }
  return true;
}

int main(int argc, char **argv) {
  if (argc < 3) {
    fprintf(stderr, "usage: edge-case-test <dataDir> <fail|poison|interact> [goodDataDir]\n");
    return 2;
  }
  g_dataDir = argv[1];
  const char *mode = argv[2];
  const char *goodDir = argc > 3 ? argv[3] : argv[1];

  setup();

  if (strcmp(mode, "fail") == 0) {
    // Pre-flight: the fail dir must actually contain NO fetch data
    // and NO fonts, or the "fetch failure" assertions below test a
    // setup that never fails. Refuse loudly instead of reporting
    // misleading firmware FAILs.
    const char *mustBeAbsent[] = {"coingecko.json", "coinbase-spot.json",
      "candles-900.json", "candles-3600.json", "candles-21600.json",
      "candles-86400.json", "btc-daily.json", "block-height.txt",
      "InterB6.vlw", "OutfitXB30.vlw"};
    for (size_t i = 0; i < sizeof(mustBeAbsent) / sizeof(*mustBeAbsent); i++) {
      FILE *f = fopen((g_dataDir + "/" + mustBeAbsent[i]).c_str(), "r");
      if (f) {
        fclose(f);
        fprintf(stderr,
          "SETUP ERROR: fail dir '%s' contains %s — it must be empty\n"
          "  (no .json/.txt fetch data, no .vlw fonts), or the fetch-\n"
          "  failure checks below cannot fail. Use an empty dir.\n",
          g_dataDir.c_str(), mustBeAbsent[i]);
        return 2;
      }
    }
    // --- All fetches fail, all fonts missing ---
    runLoopFor(5000);
    drawAll();  // must not crash with sN==0 / price 0
    check("fetch failure: price not ok (honest, not stale-as-live)", !priceOk);
    check("fetch failure: no chart loaded", sN == 0 && chartRange == -1);
    check("fetch failure: chart reads stale", chartStale());
    check("fetch failure: chartMin/Max safe on empty series",
          chartMin() == 0.0f && chartMax() == 0.0f);
    check("missing fonts: failed load cached (no re-open per draw)",
          failedFontName != nullptr);
    // The framebuffer still has content (built-in fonts rendered).
    const uint16_t *fb = tft.framebuffer();
    int nonzero = 0;
    for (int i = 0; i < 170 * 320; i++) if (fb[i]) nonzero++;
    check("missing fonts: screen still renders with built-ins", nonzero > 1000);

    // --- Recovery: point at good data, the next poll must land ---
    g_dataDir = goodDir;
    int guard = 0;
    while (!(priceOk && chartRange == 0 && sN >= 2) && guard++ < 900)
      runLoopFor(100);
    check("recovery: price lands after data returns", priceOk && priceUSD > 1000);
    check("recovery: 1D chart lands after data returns",
          chartRange == 0 && sN >= 2);
    check("recovery: tiles sane", chartMin() > 50000 && chartMax() > 60000);
  } else if (strcmp(mode, "poison") == 0) {
    // --- Malformed candle rows must be skipped, not collapse the chart ---
    int guard = 0;
    while (!(priceOk && chartRange == 0 && sN >= 2) && guard++ < 200)
      runLoopFor(100);
    check("poison: 1D settles", priceOk && chartRange == 0 && sN >= 2);
    float expLo = 0, expHi = 0, expCLo = 0, expCHi = 0;
    bool haveExp = expected1W(expLo, expHi, expCLo, expCHi);
    printf("  1W expected from file: line low=%.2f high=%.2f "
           "candle low=%.2f high=%.2f (spot $%.0f)\n",
           expLo, expHi, expCLo, expCHi, priceUSD);
    check("poison: expected 1W tiles derived from the data file", haveExp);
    tapBtn(1);  // 1W
    settleChart(1);
    printf("  1W tiles with poisoned rows: low=%.2f high=%.2f\n",
           chartMin(), chartMax());
    check("poison: 1W low is the file's thinned min close (bad rows skipped)",
          haveExp && fabsf(chartMin() - expLo) < 1.0f);
    check("poison: 1W high is the file's thinned max close (bad rows skipped)",
          haveExp && fabsf(chartMax() - expHi) < 1.0f);
    check("poison: chart did not collapse to 0", chartMin() > 1000);
    tapBtn(19);  // Candles
    runLoopFor(1000);
    printf("  1W candle tiles: low=%.2f high=%.2f (dispCandN=%d)\n",
           chartMin(), chartMax(), dispCandN);
    check("poison: candle mode builds on poisoned data",
          chartType == 1 && dispCandN > 0 && chartMin() > 50000);
    check("poison: candle low is the file's thinned min low (bad rows skipped)",
          haveExp && fabsf(chartMin() - expCLo) < 1.0f);
    check("poison: candle high is the file's thinned max high (bad rows skipped)",
          haveExp && fabsf(chartMax() - expCHi) < 1.0f);
  } else if (strcmp(mode, "interact") == 0) {
    int guard = 0;
    while (!(priceOk && chartRange == 0 && sN >= 2) && guard++ < 200)
      runLoopFor(100);
    check("interact: 1D settles", priceOk && chartRange == 0 && sN >= 2);

    // --- Rapid range taps: 1W -> 1M -> 3M -> 1Y, no settling between ---
    tapBtn(1); tapBtn(2); tapBtn(3); tapBtn(6);
    settleChart(6);
    printf("  after rapid taps: rangeIdx=%d chartRange=%d low=%.2f high=%.2f\n",
           rangeIdx, chartRange, chartMin(), chartMax());
    check("rapid taps: final range is 1Y, data matches",
          rangeIdx == 6 && chartRange == 6);
    check("rapid taps: 1Y tiles sane (no stale-range tiles)",
          chartMin() > 50000 && chartMin() < 65000 &&
          chartMax() > 90000 && chartMax() < 100000);

    // --- Landscape touch-remap round-trip ---
    check("landscape: Rotate pill present", tapBtn(15));
    runLoopFor(500);
    check("landscape: rotated", landscape == true);
    check("landscape: Portrait pill present", tapBtn(15));
    runLoopFor(500);
    check("landscape: back to portrait", landscape == false);
    check("landscape: portrait buttons hit-testable after round-trip",
          tapBtn(0) && rangeIdx == 0);

    // --- Candle-mode scrub snap ---
    tapBtn(1);  // 1W
    settleChart(1);
    check("scrub: Candles pill present", tapBtn(19));
    runLoopFor(1000);
    check("scrub: candle mode with buckets", chartType == 1 && dispCandN > 0);
    drag(100, 180, 120, 180, assertScrubSnap);
    check("scrub: drag snaps to a candle centre (dot on candle, readout its close)",
          g_scrubSnapOk);
    check("scrub: lift clears the scrub", scrubIdx == -1 && scrubCand == -1);

    // --- Drag starting on a pill must NOT scrub (Pass 5 finding 2:
    // a long drag from a pill is a swipe now, not a tap) ---
    drag(23, 231, 100, 180, assertNoScrub);
    check("scrub: drag from a pill does not scrub", g_noScrubOk);
    check("drag-from-pill: long drag swipes instead of firing the pill",
          curPage() == 5 && rangeIdx == 1);  // 1W stays: the 1D pill never fired

    // --- DEL validation (serial) ---
    int before = nAuth;
    char buf[96];
    strcpy(buf, "DEL abc"); serialCommand(buf);
    check("DEL abc: non-numeric index deletes nothing", nAuth == before);
    strcpy(buf, "DEL 99"); serialCommand(buf);
    check("DEL 99: out-of-range index deletes nothing", nAuth == before);
    strcpy(buf, "DEL 0"); serialCommand(buf);
    check("DEL 0: valid index deletes account 0", nAuth == before - 1);
    strcpy(buf, "ADD Bad !!!"); serialCommand(buf);
    check("ADD Bad secret: invalid base32 rejected", nAuth == before - 1);
    strcpy(buf, "ADD Demo GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ");
    serialCommand(buf);
    check("ADD Demo: valid account added back", nAuth == before);
  } else {
    fprintf(stderr, "unknown mode %s\n", mode);
    return 2;
  }

  printf("EDGE-CASE TEST %s (%d pass, %d fail)\n",
         nFail == 0 ? "PASS" : "FAIL", nPass, nFail);
  return nFail == 0 ? 0 : 1;
}
