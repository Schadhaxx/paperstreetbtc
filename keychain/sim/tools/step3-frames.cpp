// Step-3 frame harness (R6/R7/R8/R9/R10/R11): renders every changed
// screen in BOTH themes so they can be inspected as images, and checks
// the new behaviours (sleep/wake, brightness, landscape theme, manual
// refresh, disabled pills, sanity gate, scrub % reference) by printing
// PASS/FAIL lines. Mirrors tools/refine-frames.cpp.
// Usage: step3-frames [dataDir] [outDir]
// Exit 0 = all checks pass.
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>
#include "sim.h"
#include "TFT_eSPI.h"

float rangeChange();
void savePrefs();

#include "../../firmware/paperstreet-keychain.ino"

static std::string g_dir = "step3-frames";
static int g_fail = 0;

static void runLoopFor(unsigned long ms) {
  unsigned long start = (unsigned long)simMillis;
  unsigned long target = start + ms;
  int guard = 0;
  while (simMillis < target && guard++ < 100000) loop();
}

static void tap(int16_t dx, int16_t dy) {
  simSetFinger(true, dx, dy);
  runLoopFor(100);
  runLoopFor(100);
  simSetFinger(false, 0, 0);
  runLoopFor(100);
  runLoopFor(100);
  runLoopFor(100);
}

// Tap the centre of the button with the given id (from the last draw).
static bool tapBtn(int id) {
  for (int i = 0; i < nBtns; i++) {
    if (btns[i].id == id) {
      tap(btns[i].x + btns[i].w / 2, btns[i].y + btns[i].h / 2);
      return true;
    }
  }
  printf("FAIL tapBtn: no button id %d (nBtns=%d)\n", id, nBtns);
  g_fail++;
  return false;
}

static void dump(const char *name) {
  char path[512];
  snprintf(path, sizeof(path), "%s/%s.ppm", g_dir.c_str(), name);
  tft.dumpPPM(path);
  fprintf(stderr, "[step3] %s (theme=%s range=%d type=%d land=%d priceOnly=%d mode=%d asleep=%d bright=%d%%)\\n",
          name, themeDark ? "dark" : "light", rangeIdx, chartType,
          (int)landscape, (int)priceOnly, (int)appMode, (int)screenAsleep,
          brightnessPct);
}

static void check(bool ok, const char *what) {
  printf("%s %s (page=%d range=%d type=%d land=%d asleep=%d bright=%d%% price=$%.0f)\\n",
         ok ? "PASS" : "FAIL", what, curPage(), rangeIdx, chartType,
         (int)landscape, (int)screenAsleep, brightnessPct, priceUSD);
  if (!ok) g_fail++;
}

static void settle() {
  int guard = 0;
  while (!(priceOk && chartRange == 0 && sN >= 2) && guard++ < 200) runLoopFor(100);
}

// Finger down and HELD (no lift) for ms — for the sleep long-press.
static void holdFinger(int16_t dx, int16_t dy, unsigned long ms) {
  simSetFinger(true, dx, dy);
  runLoopFor(ms);
}

int main(int argc, char **argv) {
  if (argc > 1) g_dataDir = argv[1];
  if (argc > 2) g_dir = argv[2];
  setup();
  settle();
  printf("settled: price=$%.0f range=%d sN=%d\\n", priceUSD, rangeIdx, sN);

  // ---- R7 sanity gate (unit-level, via the real function) ----
  check(priceSane(priceUSD * 1.05f), "R7 gate: +5% tick is sane");
  check(!priceSane(priceUSD * 1.20f), "R7 gate: +20% tick is rejected");
  check(!priceSane(priceUSD * 0.80f), "R7 gate: -20% tick is rejected");
  check(priceSane(0) == false, "R7 gate: zero price is rejected");

  // ---- R7 manual refresh: tap the LIVE indicator. The poll runs on
  // the next loop pass and clears manualRefresh, so the check is that
  // a fresh poll actually happened (lastPriceOkMs advances) — the
  // regular 60 s poll cannot fire inside this 2 s window.
  unsigned long okBefore = lastPriceOkMs;
  tap(liveHitX + liveHitW / 2, 7);  // LIVE, right of status bar
  runLoopFor(2000);
  check(lastPriceOkMs != okBefore && priceOk && priceUSD > 50000,
        "R7: LIVE tap runs a fresh price poll at once");

  // ---- R11 disabled pill: candle mode, tap 5Y (must be a no-op) ----
  tap(79, 175); runLoopFor(1500);  // Cndl (TYPE_Y 168)
  check(chartType == 1, "R11 setup: candle mode on");
  printf("R11: candle label 1D = \"%s\"\\n", CANDLE_LABEL[0]);
  check(strcmp(CANDLE_LABEL[0], "24 x 15m") == 0, "R11: 1D candle label is 24 x 15m");
  tap(104, 237); runLoopFor(500);  // 5Y (R2_Y 227), disabled in candle mode
  check(rangeIdx == 0 && chartType == 1,
        "R11: disabled 5Y tap changes nothing (range still 1D, still candles)");
  dump("dark-1d-candles-disabled5y");
  tap(47, 175); runLoopFor(1000);  // back to Line

  // ---- R9 fetching note, forced (sim fetches return instantly, so the
  // live note cannot be caught mid-fetch — this paints the same code
  // path directly and dumps it) ----
  fetching = true; drawScrubRow(); dump("dark-fetching");
  fetching = false; drawAll();

  // ---- R11 scrub % vs range start: hold a scrub mid-chart and dump ----
  simSetFinger(true, 60, 125);
  runLoopFor(100);
  simSetFinger(true, 100, 125);
  runLoopFor(200);
  dump("dark-scrub-mid");
  {
    // The scrubbed point's % vs the range start, as the readout shows.
    int idx = (int)((long)(100 - gCH_X) * (sN - 1) / (gCH_W - 1));
    float pcStart = (sClose[idx] / sClose[0] - 1.0f) * 100.0f;
    float pcLast = (sClose[idx] / sClose[sN - 1] - 1.0f) * 100.0f;
    printf("R11 scrub: idx=%d price=%.0f vs-start=%+.2f%% vs-last=%+.2f%% (readout must match vs-start)\\n",
           idx, sClose[idx], pcStart, pcLast);
  }
  simSetFinger(false, 0, 0);
  runLoopFor(500);

  // ---- R8 landscape theme pill ----
  tap(142, 87); runLoopFor(1500);  // Rotate (SCRUB_Y 81)
  check(landscape, "R8 setup: landscape on");
  dump("dark-landscape-theme");
  check(tapBtn(24), "R8: landscape Light pill exists and taps");
  runLoopFor(500);
  check(!themeDark, "R8: landscape theme pill switches to light");
  dump("light-landscape-theme");
  check(tapBtn(23), "R8: landscape Dark pill exists and taps");
  runLoopFor(500);
  check(themeDark, "R8: landscape theme pill switches back to dark");
  tap(285, 158); runLoopFor(500);  // Portrait

  // ---- Price-only (Phase 2): prototype layout, no brightness stepper ----
  goToPage(PAGE_PRICE); runLoopFor(1500);
  check(priceOnly, "price-only page");
  dump("dark-price-only");
  {
    bool hasDim = false, hasBright = false;
    for (int i = 0; i < nBtns; i++) {
      if (btns[i].id == 25) hasDim = true;
      if (btns[i].id == 26) hasBright = true;
    }
    check(!hasDim && !hasBright, "price-only: brightness stepper is not on this screen");
  }
  int cad0 = curCAD;
  check(tapBtn(27), "price-only: big-price tap is registered");
  runLoopFor(200);
  check(curCAD != cad0, "price-only: big-price tap toggles USD/CAD");
  tapBtn(27); runLoopFor(200);  // restore
  // A stationary tap on empty space does not leave the page (swipe does).
  tap(85, 180);
  runLoopFor(300);
  check(curPage() == 1 && priceOnly, "price-only: tap on empty space stays on the page");

  // ---- R6 sleep/wake, dark ----
  // Long-press on empty background (header strip, y 25: not a pill,
  // not chart — the old y 220 hold point is inside the expanded
  // range-pill hit box since Pass 5 finding 9). Sleep fires on the
  // LIFT after a 1200 ms hold (Pass 5 finding 5), not while held.
  holdFinger(85, 25, 1400);
  check(!screenAsleep, "R6: still awake while holding (sleep fires on lift)");
  simSetFinger(false, 0, 0);
  runLoopFor(500);
  check(screenAsleep, "R6: 1200ms hold + lift puts the screen to sleep");
  check(screenAsleep, "R6: still asleep after the sleeping finger lifts");
  dump("dark-sleep-veil");
  // A short hold must NOT sleep: lift before 1200 ms.
  tap(85, 160);  // wake (swallowed tap)
  runLoopFor(500);
  check(!screenAsleep, "R6: tap wakes the screen");
  // Sleep started on price-only, so wake returns to price-only.
  check(curPage() == 1 && priceOnly, "R6: wake returns to the page it slept from (price-only)");
  goToPage(PAGE_CHART); runLoopFor(500);  // swipe is the way back; tests jump
  check(curPage() == 0 && !priceOnly, "R6 setup: back on the chart page");
  holdFinger(85, 25, 400);
  simSetFinger(false, 0, 0);
  runLoopFor(500);
  check(!screenAsleep, "R6: 400ms hold does NOT sleep");

  // ---- Light theme: price-only + veil ----
  themeDark = false; drawAll();  // Light (portrait theme pill dropped)
  runLoopFor(500);
  check(!themeDark, "light setup: theme is light");
  goToPage(PAGE_PRICE); runLoopFor(1500);  // price-only
  dump("light-price-only");
  holdFinger(85, 25, 1400);
  simSetFinger(false, 0, 0);
  runLoopFor(500);
  check(screenAsleep, "R6 light: long-press sleeps");
  dump("light-sleep-veil");
  tap(85, 160);
  runLoopFor(500);
  check(!screenAsleep, "R6 light: tap wakes");

  printf(g_fail == 0 ? "STEP3 TEST OK\\n" : "STEP3 TEST: %d FAILURES\\n", g_fail);
  return g_fail == 0 ? 0 : 1;
}
