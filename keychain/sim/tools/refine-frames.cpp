// Refinement frame harness: renders every view in BOTH themes so the
// critical pass can inspect them as images. Not part of the video tour.
// Usage: refine-frames [dataDir] [outDir]
// Dumps: dark/light x {1d-line, 1d-candles, 1w-candles, 1m-candles,
// 1y-line, landscape, price-only, auth} plus stale-1w captures
// (the draw right after a range tap, before the fetch lands).
#include <cstdio>
#include <cstdint>
#include <string>
#include "sim.h"
#include "TFT_eSPI.h"

float rangeChange();
void savePrefs();

#include "../../firmware/paperstreet-keychain.ino"

static std::string g_dir = "refine-frames";

static void dump(const char *name) {
  char path[512];
  snprintf(path, sizeof(path), "%s/%s.ppm", g_dir.c_str(), name);
  tft.dumpPPM(path);
  fprintf(stderr, "[frames] %s (theme=%s range=%d type=%d land=%d priceOnly=%d mode=%d)\n",
          name, themeDark ? "dark" : "light", rangeIdx, chartType,
          (int)landscape, (int)priceOnly, (int)appMode);
}

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

static void settle() {
  int guard = 0;
  while (!(priceOk && chartRange == 0 && sN >= 2) && guard++ < 200) runLoopFor(100);
}

int main(int argc, char **argv) {
  if (argc > 1) g_dataDir = argv[1];
  if (argc > 2) g_dir = argv[2];
  setup();
  settle();
  fprintf(stderr, "[frames] settled dark 1D line\n");

  // ---- dark pass ----
  dump("dark-1d-line");
  tap(79, 175); runLoopFor(1500); dump("dark-1d-candles");   // Cndl
  tap(54, 213); runLoopFor(2000); dump("dark-1w-candles");   // 1W
  tap(85, 213); runLoopFor(2000); dump("dark-1m-candles");   // 1M
  tap(47, 175); tap(65, 237); runLoopFor(2000); dump("dark-1y-line");  // Line, 1Y
  tap(142, 87); runLoopFor(1500); dump("dark-landscape");   // Rotate (SCRUB_Y 81)
  tap(285, 158); runLoopFor(500);                            // Portrait
  goToPage(PAGE_PRICE); runLoopFor(1500); dump("dark-price-only");    // price-only
  tap(85, 150); runLoopFor(500);                             // tap chart -> back
  goToPage(PAGE_AUTH); runLoopFor(1500); dump("dark-auth");         // Auth
  tap(51, 238); runLoopFor(500);                             // Price pill (Auth nav row y 226, Pass 5 finding 11) -> back to chart (1Y line)

  // ---- stale-state capture (dark): 1D line, then change range with
  // no loop() in between — exactly what onTap's drawAll paints
  // before the fetch lands. ----
  tap(23, 213); runLoopFor(2000);                            // 1D line
  rangeIdx = 1; drawAll(); dump("dark-stale-1w");
  runLoopFor(2000); dump("dark-fresh-1w");

  // ---- light pass: switch theme via the real Light pill, then walk
  // the same views. Current state: 1W line. ----
  themeDark = false; drawAll();  // Light (chart theme pill dropped)
  fprintf(stderr, "[frames] after Light tap: themeDark=%d\n", (int)themeDark);
  if (themeDark) { themeDark = false; drawAll(); fprintf(stderr, "[frames] WARNING: Light tap missed, forced light\n"); }
  runLoopFor(500);
  dump("light-1w-line");
  tap(23, 213); runLoopFor(2000); dump("light-1d-line");
  tap(79, 175); runLoopFor(1500); dump("light-1d-candles");
  tap(54, 213); runLoopFor(2000); dump("light-1w-candles");
  tap(85, 213); runLoopFor(2000); dump("light-1m-candles");
  tap(47, 175); tap(65, 237); runLoopFor(2000); dump("light-1y-line");
  tap(142, 87); runLoopFor(1500); dump("light-landscape");
  tap(285, 158); runLoopFor(500);
  goToPage(PAGE_PRICE); runLoopFor(1500); dump("light-price-only");
  tap(85, 150); runLoopFor(500);
  goToPage(PAGE_AUTH); runLoopFor(1500); dump("light-auth");
  tap(51, 238); runLoopFor(500);                             // Price pill (Auth nav row y 226) -> back to chart
  tap(23, 213); runLoopFor(2000);                            // 1D line
  rangeIdx = 1; drawAll(); dump("light-stale-1w");
  runLoopFor(2000); dump("light-fresh-1w");

  fprintf(stderr, "[frames] done\n");
  return 0;
}
