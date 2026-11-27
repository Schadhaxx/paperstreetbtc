// Native harness: compiles the REAL keychain sketch on Linux and runs a
// scripted click-through tour, dumping the framebuffer as PPM frames.
// The sketch is included read-only; nothing in it is modified.
#include <cstdio>
#include <cstdint>
#include <string>
#include <vector>
#include "sim.h"
#include "TFT_eSPI.h"

// Forward declarations the Arduino IDE normally auto-generates for .ino
// files (the sketch calls these before their definitions).
float rangeChange();
void savePrefs();

#include "../firmware/paperstreet-keychain.ino"

// ---- video timeline (1s sim time == 1s video) ----
static std::string g_outDir = "frames";
static double g_videoTime = 0.0;
static std::string g_caption = "";
static int g_frameNo = 0;

struct FrameRec { std::string file; double t; std::string caption; };
struct TapRec { double t; int cx, cy; };
struct SwipeRec { double t; int x0, y0, x1, y1; };
static std::vector<FrameRec> g_frames;
static std::vector<TapRec> g_taps;
static std::vector<SwipeRec> g_swipes;

static void captureFrame() {
  char path[512];
  snprintf(path, sizeof(path), "%s/frame_%04d.ppm", g_outDir.c_str(), g_frameNo);
  tft.dumpPPM(path);
  char file[64];
  snprintf(file, sizeof(file), "frame_%04d.ppm", g_frameNo);
  g_frames.push_back({file, g_videoTime, g_caption});
  g_frameNo++;
}

static void runLoopFor(unsigned long ms) {
  unsigned long start = (unsigned long)simMillis;
  unsigned long target = start + ms;
  int guard = 0;
  while (simMillis < target && guard++ < 100000) loop();
  g_videoTime += (simMillis - start) / 1000.0;
}

static void hold(double seconds) {
  int steps = (int)(seconds * 10 + 0.5);
  for (int i = 0; i < steps; i++) { runLoopFor(100); captureFrame(); }
}

static void setCaption(const char *c) { g_caption = c; }

// Tap at DRAWING coords (what the user sees). Records a tap event in
// canvas coords for the compositor's tap indicator, then drives the
// finger down/up so the sketch's own touchRead/hitTest/onTap handle it.
static void tap(int16_t dx, int16_t dy, const char *captionAfter) {
  int w = tft.width();
  int cx = (w == 170) ? 225 + dx * 3 : dx * 3;
  int cy = (w == 170) ? dy * 3 : 225 + dy * 3;
  g_taps.push_back({g_videoTime, cx, cy});
  simSetFinger(true, dx, dy);
  runLoopFor(100); captureFrame();   // finger down, old state
  runLoopFor(100); captureFrame();   // still down
  simSetFinger(false, 0, 0);
  g_caption = captionAfter;          // state changes on lift; caption tracks it
  runLoopFor(100); captureFrame();   // lifted, new state, indicator fading
  runLoopFor(100); captureFrame();
  runLoopFor(100); captureFrame();
}

// Two taps ~120 ms apart (lift to lift): with the 30 ms debounce
// (Pass 5 finding 4) both must land. Records a tap indicator for
// each tap, like tap() does.
static void fastTapPair(int16_t x1, int16_t y1, int16_t x2, int16_t y2,
                        const char *captionAfter) {
  int w = tft.width();
  auto toCanvas = [w](int16_t dx, int16_t dy, int &cx, int &cy) {
    cx = (w == 170) ? 225 + dx * 3 : dx * 3;
    cy = (w == 170) ? dy * 3 : 225 + dy * 3;
  };
  int cx, cy;
  toCanvas(x1, y1, cx, cy);
  g_taps.push_back({g_videoTime, cx, cy});
  simSetFinger(true, x1, y1);
  runLoopFor(60); captureFrame();
  simSetFinger(false, 0, 0);
  runLoopFor(60); captureFrame();
  fprintf(stderr, "[tour] fastTapPair tap1 -> range=%d\\n", rangeIdx);
  toCanvas(x2, y2, cx, cy);
  g_taps.push_back({g_videoTime, cx, cy});
  simSetFinger(true, x2, y2);
  runLoopFor(60); captureFrame();
  simSetFinger(false, 0, 0);
  g_caption = captionAfter;
  runLoopFor(100); captureFrame();
  runLoopFor(100); captureFrame();
  runLoopFor(100); captureFrame();
  fprintf(stderr, "[tour] fastTapPair -> page=%d range=%d\\n",
          curPage(), rangeIdx);
}

// Tap a registered button by id (scans btns[], so it follows the
// layout instead of hardcoding coords). Logs the resulting state so
// a missed tap is visible in stderr instead of silently touring the
// wrong screen.
static void tapBtn(int id, const char *captionAfter) {
  for (int i = 0; i < nBtns; i++) {
    if (btns[i].id == id) {
      tap(btns[i].x + btns[i].w / 2, btns[i].y + btns[i].h / 2, captionAfter);
      fprintf(stderr, "[tour] tapBtn %d -> page=%d range=%d type=%d cmp=%d%d%d hide=%d asleep=%d\n",
              id, curPage(), rangeIdx, chartType,
              (int)cmpOn[0], (int)cmpOn[1], (int)cmpOn[2],
              (int)authHideCodes, (int)screenAsleep);
      return;
    }
  }
  fprintf(stderr, "[tour] ERROR tapBtn: no button id %d on screen (nBtns=%d)\n", id, nBtns);
}

// Swipe left/right in the proven y=25 lane (header strip: empty
// background on every page — not chart, not a pill). Steps are
// 60 ms apart so the sketch's 50 ms touch poll sees the movement.
// The slide itself runs synchronously inside goToPage (delay() only
// advances sim time), so the video shows the gesture + the landed
// page; a mid-slide frame is dumped by tools/swipe-test.cpp instead.
static void swipe(int16_t x0, int16_t y0, int16_t x1, int16_t y1,
                  const char *captionAfter) {
  int w = tft.width();
  int cx0 = (w == 170) ? 225 + x0 * 3 : x0 * 3;
  int cy0 = (w == 170) ? y0 * 3 : 225 + y0 * 3;
  int cx1 = (w == 170) ? 225 + x1 * 3 : x1 * 3;
  int cy1 = (w == 170) ? y1 * 3 : 225 + y1 * 3;
  g_swipes.push_back({g_videoTime, cx0, cy0, cx1, cy1});
  simSetFinger(true, x0, y0);
  runLoopFor(100); captureFrame();
  const int steps = 4;
  for (int i = 1; i <= steps; i++) {
    int16_t x = x0 + (x1 - x0) * i / steps;
    int16_t y = y0 + (y1 - y0) * i / steps;
    simSetFinger(true, x, y);
    runLoopFor(60); captureFrame();
  }
  simSetFinger(false, 0, 0);
  g_caption = captionAfter;
  runLoopFor(100); captureFrame();
  runLoopFor(100); captureFrame();
  runLoopFor(100); captureFrame();
  fprintf(stderr, "[tour] swipe %d,%d -> %d,%d -> page=%d focus=%d qr=%d flip=%d\n",
          x0, y0, x1, y1, curPage(), clockFocus, qrPage, (int)qrFlipped);
}

// Finger down and HELD (no lift) for ms — for the sleep long-press.
// Captures a frame every 100 ms so the veil appearing is on video.
static void holdFinger(int16_t dx, int16_t dy, unsigned long ms) {
  simSetFinger(true, dx, dy);
  unsigned long start = (unsigned long)simMillis;
  while ((unsigned long)simMillis - start < ms) {
    runLoopFor(100); captureFrame();
  }
  fprintf(stderr, "[tour] holdFinger %d,%d %lums -> asleep=%d\n",
          dx, dy, ms, (int)screenAsleep);
}

int main(int argc, char **argv) {
  if (argc > 1) g_dataDir = argv[1];
  if (argc > 2) g_outDir = argv[2];
  fprintf(stderr, "[sim] data dir: %s\n[sim] frames dir: %s\n",
          g_dataDir.c_str(), g_outDir.c_str());

  setup();

  // Boot beat: the price-0 / OFFLINE / "fetching chart..." state.
  setCaption("Booting…");
  captureFrame();
  runLoopFor(100); captureFrame();
  runLoopFor(100); captureFrame();

  // Settle: run until we have a live price and the 1D chart.
  int guard = 0;
  while (!(priceOk && chartRange == 0 && sN >= 2) && guard++ < 200) {
    runLoopFor(100); captureFrame();
  }
  fprintf(stderr, "[sim] settled: price $%.0f (chg %.2f%%), range %d, sN=%d, chartRange=%d\n",
          priceUSD, chg24h, rangeIdx, sN, chartRange);

  // ---- tour: the original 11 taps, then the Pass-1 screens ----
  setCaption("1D · Line — live price");
  hold(4.0);
  tap(66, 272, "1D · Candles");            // Cndl (type pill)
  hold(4.0);
  tap(54, 231, "1W · Candles");            // 1W (range row 1)
  hold(4.0);
  tap(85, 231, "1M · Candles");            // 1M (range row 1)
  hold(3.0);
  tap(142, 142, "Landscape · 1M Candles"); // Rotate (scrub row, right)
  hold(5.0);
  tap(285, 158, "1M · Candles");           // Portrait (landscape row)
  hold(1.0);
  tap(45, 272, "1M · Line");               // Line (type pill)
  tap(65, 251, "1Y · Line");               // 1Y (range row 2)
  hold(3.0);

  // ---- Pass 5 finding 4: two fast taps ~120 ms apart (lift to
  // lift) — both must land with the 30 ms debounce ----
  fastTapPair(54, 231, 85, 231, "Fast taps — 1W then 1M, both land");
  hold(2.0);
  tap(65, 251, "1Y · Line");               // back to 1Y for comparisons
  hold(1.0);

  // ---- R3 comparisons: SPX, then GOLD, then MSTR, lines accumulate ----
  tapBtn(43, "1Y · Line + S&P 500");
  hold(2.5);
  tapBtn(44, "Comparisons: S&P + Gold");
  hold(1.5);
  tapBtn(45, "Comparisons: S&P + Gold + MSTR");
  hold(1.5);

  // ---- R8/R10 price-only: stepper demo, then back to the chart ----
  tap(75, 292, "Price only");              // Price (control row)
  hold(2.0);
  tapBtn(25, "Price only — dimmed to 95%");  // DIM stepper
  hold(1.0);
  tapBtn(26, "Price only — back to 100%");   // BRIGHT stepper
  hold(1.0);
  tap(85, 150, "1Y · Line + comparisons");   // tap chart -> back to chart
  hold(1.0);

  // ---- R4 swipe tour: chart -> price-only -> clock -> Jade -> LN -> Auth -> wrap ----
  // Pass 5 finding 2: the Jade -> Lightning swipe starts ON the QR
  // card (85,136) — the old header-lane swipe hid that pill-start
  // swipes used to be suppressed there.
  swipe(85, 25, 35, 25, "Swipe → Price only");
  hold(1.5);
  swipe(85, 25, 35, 25, "Block clock — block height");
  hold(2.5);
  tapBtn(31, "Block clock — sats per dollar");  // focus dot 2
  hold(2.0);
  tapBtn(32, "Block clock — halving countdown");  // focus dot 3
  hold(2.0);
  swipe(85, 25, 35, 25, "Receive — Jade QR");
  hold(2.5);
  tap(85, 136, "Jade — full address");     // tap QR card to flip
  hold(2.5);
  tap(85, 250, "Receive — Jade QR");        // tap below the card: back
  hold(0.5);
  swipe(85, 136, 35, 136, "Swipe from the QR card → Lightning");
  hold(2.5);
  tap(85, 136, "Lightning — full address");  // tap QR card to flip
  hold(2.0);
  tap(85, 250, "Receive — Lightning QR");    // tap below the card: back
  hold(0.5);
  swipe(85, 25, 35, 25, "Authenticator — all codes");
  hold(2.5);
  fprintf(stderr, "[sim] auth code showing: %s (window %lu)\n", authCode, (unsigned long)authWindow);
  tapBtn(53, "Authenticator — codes hidden");  // HIDE
  hold(2.0);
  tapBtn(53, "Authenticator — codes shown");   // SHOW
  hold(1.0);
  swipe(85, 25, 35, 25, "Swipe wraps around → Chart");
  hold(1.5);
  // Pass 5 finding 2: a swipe starting ON a range pill still pages
  // (it used to fire the pill) — then swipe back from the header.
  swipe(54, 231, 4, 231, "Swipe from a pill still pages");
  hold(1.5);
  swipe(85, 25, 135, 25, "Swipe back → Chart");
  hold(1.0);

  // ---- R6 sleep/wake: long-press on empty background, then wake tap ----
  // Pass 5 finding 5: sleep fires on lift after a 1200 ms hold, so
  // the hold must be >1200 ms (1000 ms no longer sleeps). Hold point
  // is the header strip (85,25): the old (85,220) is inside the
  // expanded range-pill hit box since finding 9, so a hold there
  // never arms sleep.
  holdFinger(85, 25, 1400);               // 1200 ms hold + lift -> sleep
  simSetFinger(false, 0, 0);
  runLoopFor(100); captureFrame();
  fprintf(stderr, "[tour] after sleep lift -> asleep=%d\\n", (int)screenAsleep);
  setCaption("Screen asleep — tap to wake");
  hold(1.5);
  tap(85, 160, "Awake — back on the chart");  // waking touch is swallowed
  hold(1.5);
  fprintf(stderr, "[tour] end: page=%d range=%d type=%d cmp=%d%d%d asleep=%d bright=%d%%\n",
          curPage(), rangeIdx, chartType,
          (int)cmpOn[0], (int)cmpOn[1], (int)cmpOn[2],
          (int)screenAsleep, brightnessPct);

  // ---- manifest ----
  std::string mp = g_outDir + "/manifest.json";
  FILE *mf = fopen(mp.c_str(), "w");
  fprintf(mf, "{\n  \"fps\": 10,\n  \"duration\": %.2f,\n  \"frames\": [\n", g_videoTime);
  for (size_t i = 0; i < g_frames.size(); i++) {
    fprintf(mf, "    {\"file\": \"%s\", \"t\": %.2f, \"caption\": \"%s\"}%s\n",
            g_frames[i].file.c_str(), g_frames[i].t, g_frames[i].caption.c_str(),
            i + 1 < g_frames.size() ? "," : "");
  }
  fprintf(mf, "  ],\n  \"taps\": [\n");
  for (size_t i = 0; i < g_taps.size(); i++) {
    fprintf(mf, "    {\"t\": %.2f, \"x\": %d, \"y\": %d}%s\n",
            g_taps[i].t, g_taps[i].cx, g_taps[i].cy,
            i + 1 < g_taps.size() ? "," : "");
  }
  fprintf(mf, "  ],\n  \"swipes\": [\n");
  for (size_t i = 0; i < g_swipes.size(); i++) {
    fprintf(mf, "    {\"t\": %.2f, \"x0\": %d, \"y0\": %d, \"x1\": %d, \"y1\": %d}%s\n",
            g_swipes[i].t, g_swipes[i].x0, g_swipes[i].y0,
            g_swipes[i].x1, g_swipes[i].y1,
            i + 1 < g_swipes.size() ? "," : "");
  }
  fprintf(mf, "  ]\n}\n");
  fclose(mf);
  fprintf(stderr, "[sim] done: %d frames, %.1fs video, %zu taps\n",
          g_frameNo, g_videoTime, g_taps.size());
  return 0;
}
