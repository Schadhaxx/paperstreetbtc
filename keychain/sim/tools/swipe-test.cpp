// Swipe-navigation test (R4): boots the real sketch, then drives
// finger gestures through the sketch's own touch handling and checks
// the page state + the dots on the framebuffer. Also dumps a
// mid-slide frame (built from the same slideFrame() goToPage uses)
// for visual inspection.
// Usage: swipe-test [dataDir] [outDir]
// Exit 0 = all checks pass.
#include <cstdio>
#include <cstdint>
#include <string>
#include "sim.h"
#include "TFT_eSPI.h"

float rangeChange();
void savePrefs();

#include "../../firmware/paperstreet-keychain.ino"

static std::string g_dir = "swipe-frames";
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

// Finger down at (x0,y0), drag in steps to (x1,y1), lift. Steps are
// 60 ms apart so the sketch's 50 ms touch poll sees the movement.
static void swipe(int16_t x0, int16_t y0, int16_t x1, int16_t y1) {
  simSetFinger(true, x0, y0);
  runLoopFor(100);
  const int steps = 4;
  for (int i = 1; i <= steps; i++) {
    int16_t x = x0 + (x1 - x0) * i / steps;
    int16_t y = y0 + (y1 - y0) * i / steps;
    simSetFinger(true, x, y);
    runLoopFor(60);
  }
  simSetFinger(false, 0, 0);
  runLoopFor(1000);
}

static void dump(const char *name) {
  char path[512];
  snprintf(path, sizeof(path), "%s/%s.ppm", g_dir.c_str(), name);
  tft.dumpPPM(path);
}

static void check(bool ok, const char *what) {
  printf("%s %s (page=%d mode=%d priceOnly=%d landscape=%d themeDark=%d)\n",
         ok ? "PASS" : "FAIL", what, curPage(), appMode, (int)priceOnly,
         (int)landscape, (int)themeDark);
  if (!ok) g_fail++;
}

// The dots: active dot is a cyan 10 px capsule centred on its dot
// position, inactive dots are dim r=2 circles. Read straight off
// the framebuffer the sketch just drew.
static bool dotsOk() {
  int cur = curPage();
  for (int i = 0; i < 6; i++) {
    int16_t cx = 58 + i * 11;
    uint16_t px = tft.readPixel(cx, 317);
    if (i == cur) {
      if (px != C_CYAN) return false;
    } else {
      if (px != C_DIM) return false;
    }
  }
  return true;
}

static void settle() {
  int guard = 0;
  while (!(priceOk && chartRange == 0 && sN >= 2) && guard++ < 200) runLoopFor(100);
}

int main(int argc, char **argv) {
  if (argc > 1) g_dataDir = argv[1];
  if (argc > 2) g_dir = argv[2];
  setup();
  settle();
  printf("settled: page=%d price=$%.0f sN=%d\n", curPage(), priceUSD, sN);
  check(curPage() == 0, "boot is chart page 0");
  check(dotsOk(), "dots on chart page (active 0)");

  // 1. Swipe left: chart -> price-only.
  swipe(85, 25, 35, 25);
  check(curPage() == 1, "swipe left 0 -> 1 price-only");
  check(dotsOk(), "dots follow to page 1");
  dump("swipe-p1-price");

  // 2. Swipe left: price-only -> block clock.
  swipe(85, 25, 35, 25);
  check(curPage() == 2, "swipe left 1 -> 2 clock");
  check(dotsOk(), "dots follow to page 2");
  dump("swipe-p2-clock");

  // 3. Swipe left: clock -> Jade QR.
  swipe(85, 25, 35, 25);
  check(curPage() == 3 && qrPage == 0, "swipe left 2 -> 3 Jade QR");
  check(dotsOk(), "dots follow to page 3");
  dump("swipe-p3-jade");

  // 4. Swipe left: Jade -> Lightning QR.
  swipe(85, 25, 35, 25);
  check(curPage() == 4 && qrPage == 1, "swipe left 3 -> 4 Lightning QR");
  check(dotsOk(), "dots follow to page 4");
  dump("swipe-p4-ln");

  // 5. Swipe left: Lightning -> Auth.
  swipe(85, 25, 35, 25);
  check(curPage() == 5, "swipe left 4 -> 5 Auth");
  check(dotsOk(), "dots follow to page 5");
  dump("swipe-p5-auth");

  // 6. Wrap-around: one more swipe left from Auth returns to chart.
  swipe(85, 25, 35, 25);
  check(curPage() == 0, "swipe left 5 -> 0 wrap to chart");
  check(dotsOk(), "dots follow wrap to page 0");

  // 7. Swipe right from the chart wraps back to Auth.
  swipe(85, 25, 135, 25);
  check(curPage() == 5, "swipe right 0 -> 5 wrap to Auth");
  check(dotsOk(), "dots follow wrap to page 5");

  // 8. Swipe right: Auth -> Lightning.
  swipe(85, 25, 135, 25);
  check(curPage() == 4, "swipe right 5 -> 4 Lightning");
  dump("swipe-p4-ln-back");

  // 9. Short drag (20 px < 34 px threshold) is not a swipe.
  swipe(85, 25, 65, 25);
  check(curPage() == 4, "20px drag does not swipe");

  // 10. Mostly-vertical drag (40 px across, 50 px down) is not a
  // swipe: horizontal is not >= 1.4x vertical (40 < 70).
  swipe(85, 25, 125, 75);
  check(curPage() == 4, "vertical drag does not swipe");

  // 11. Back to the chart via pills (kept as an alternative way to
  // move), then a chart scrub must NOT change page.
  goToPage(PAGE_CHART);  // shortcut pills dropped; swipe / dots remain
  runLoopFor(1000);
  check(curPage() == 0, "return to chart page 0");
  swipe(85, 125, 35, 125);  // drag inside the chart (CH_Y 96, CH_H 58) = scrub
  check(curPage() == 0 && scrubIdx == -1, "chart scrub does not change page");
  check(dotsOk(), "dots intact after scrub");

  // 12. (Pass 5 finding 2) A drag starting on a pill DOES swipe now:
  // down on the 1W range pill, drag left 50 px. The old code fired
  // the pill instead; now the page changes and the range does NOT.
  swipe(54, 213, 4, 213);  // drag from 1W pill
  check(curPage() == 1 && rangeIdx == 0,
        "drag from range pill swipes (page 1, range still 1D)");

  // 12b. Back to the chart, then a near-stationary tap on the same
  // pill still fires it (the <10 px tap gate, finding 2).
  swipe(85, 25, 135, 25);
  check(curPage() == 0, "swipe right back to chart");
  tap(54, 213);  // 1W pill
  runLoopFor(1000);
  check(rangeIdx == 1, "stationary tap on 1W pill still selects 1W");
  tap(23, 213);  // 1D pill, back to 1D for the steps below
  runLoopFor(1000);
  check(rangeIdx == 0, "stationary tap on 1D pill restores 1D");

  // 12c. Chart-page Auth/theme shortcut pills were dropped (Phase 1).
  // A drag starting on the bottom stat tiles still swipes, and does
  // not jump to Auth (there is no Auth shortcut to fire).
  swipe(108, 292, 58, 292);
  check(curPage() == 1, "drag from bottom stat tiles swipes (page 1, not Auth)");

  // 13. Landscape forces the chart page: back to chart, rotate,
  // portrait again — still the chart page, not a restored page.
  // (Auth nav row is at y 226 with 1 account — the centred Auth
  // block, Pass 5 finding 11 — not 258 as in the 4-account layout.)
  swipe(50, 160, 120, 160);  // swipe right back to the chart (tap no longer exits)
  runLoopFor(1000);
  check(curPage() == 0, "swipe right from price-only returns to chart");

  // 13a. (Pass 5 finding 9) Near-miss tap above the 1W pill (visual
  // at R1_Y 207; hit box starts at y 203) still selects 1W; then restore 1D.
  tap(54, 205);
  runLoopFor(1000);
  check(rangeIdx == 1, "near-miss tap above 1W pill selects 1W");
  tap(23, 213);
  runLoopFor(1000);
  check(rangeIdx == 0, "tap on 1D pill restores 1D");
  tap(142, 87);  // Rotate (scrub row at SCRUB_Y 81, right end)
  runLoopFor(500);
  check(landscape && curPage() == 0 && tft.width() == 320,
        "rotate -> landscape chart page");
  tap(285, 158);  // Portrait (landscape controls row)
  runLoopFor(500);
  check(!landscape && curPage() == 0 && tft.width() == 170,
        "portrait returns to chart page");

  // 13b. (Pass 5 finding 4) Clock focus dots: a slow deliberate tap
  // on dot 2 / dot 1 switches focus (the dots were correctly wired
  // all along — verified here rather than "fixed").
  goToPage(2);
  runLoopFor(500);
  check(curPage() == 2, "on clock page for dot test");
  // Capsule dots are left-aligned (prototype); tap by id so the
  // growing active pill does not invalidate hard-coded centres.
  {
    bool hit = false;
    for (int i = 0; i < nBtns; i++) if (btns[i].id == 31) {
      tap(btns[i].x + btns[i].w / 2, btns[i].y + btns[i].h / 2);
      hit = true;
    }
    if (!hit) tap(46, 181);
  }
  runLoopFor(500);
  check(clockFocus == 1, "slow tap on clock dot 2 selects sats focus");
  {
    bool hit = false;
    for (int i = 0; i < nBtns; i++) if (btns[i].id == 30) {
      tap(btns[i].x + btns[i].w / 2, btns[i].y + btns[i].h / 2);
      hit = true;
    }
    if (!hit) tap(16, 181);
  }
  runLoopFor(500);
  check(clockFocus == 0, "slow tap on clock dot 1 selects block focus");

  // 13c. (Pass 5 finding 5) Long-press sleep now fires on lift after
  // a hold: hold 1400 ms on empty background, lift -> asleep; a tap
  // wakes (swallowed, page unchanged).
  simSetFinger(true, 85, 25);
  runLoopFor(1400);
  simSetFinger(false, 0, 0);
  runLoopFor(500);
  check(screenAsleep, "hold 1400ms + lift sleeps the screen");
  tap(85, 160);  // waking touch is swallowed
  runLoopFor(500);
  check(!screenAsleep && curPage() == 2, "wake tap wakes, stays on clock");

  // 13d. (Pass 5 finding 5) A slow swipe is NOT hijacked into sleep:
  // pause 1000 ms, then drag left -> pages to Jade, stays awake.
  simSetFinger(true, 85, 25);
  runLoopFor(1000);
  for (int i = 1; i <= 4; i++) {
    simSetFinger(true, 85 - 50 * i / 4, 25);
    runLoopFor(60);
  }
  simSetFinger(false, 0, 0);
  runLoopFor(1000);
  check(curPage() == 3 && !screenAsleep,
        "pause-then-swipe pages (no sleep hijack)");

  // 14. Mid-slide frame, built from the same functions goToPage
  // uses: capture page 1, draw page 2, push the outgoing strip at
  // dx=85 (halfway). Dumped for visual inspection.
  goToPage(1);
  runLoopFor(500);
  check(curPage() == 1, "back to price-only for mid-slide shot");
  if (slideBufAlloc()) {
    tft.readRect(0, 0, SW, SH, slideBuf);
    setPageState(2);
    drawAll();
    slideFrame(85, 1);
    dump("swipe-mid-p1-p2");
    // Left half must still be the outgoing page (price-only: big
    // price digits near the top centre are bright), right half the
    // incoming clock page (dark surface card). Sample one pixel in
    // each half that differs between the two pages: the price-only
    // big-price row (y 70, x 40) vs the clock focus card (y 100,
    // x 130 is inside the card -> surface colour).
    uint16_t leftPx = tft.readPixel(40, 70);
    uint16_t rightPx = tft.readPixel(130, 100);
    printf("mid-slide samples: left(40,70)=0x%04X right(130,100)=0x%04X\n",
           leftPx, rightPx);
    check(leftPx != rightPx, "mid-slide frame shows two pages at once");
    drawAll();  // land clean on the clock page
    check(curPage() == 2, "landed on clock page after mid-slide");
    dump("swipe-p2-clock-final");
  } else {
    printf("FAIL slide buffer did not allocate\n");
    g_fail++;
  }

  printf(g_fail == 0 ? "SWIPE TEST OK\n" : "SWIPE TEST FAILED (%d)\n", g_fail);
  return g_fail == 0 ? 0 : 1;
}
