// Replicates the video tour's exact tap sequence (Cndl, then 1W) and
// samples the chart state after the 1W tap, to see when the 1W fetch
// lands in the tour order (vs the range-fix test's line-mode tap).
#include <cstdio>
#include <cstdint>
#include <string>
#include "sim.h"
#include "TFT_eSPI.h"

float rangeChange();
void savePrefs();

#include "/home/hatch/workspace/ps-keychain-firmware/paperstreet-keychain.ino"

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

static void sample(const char *tag) {
  printf("%s t=%lums rangeIdx=%d chartRange=%d type=%d sN=%d dispN=%d low=%.2f high=%.2f appMode=%d priceOnly=%d\n",
         tag, (unsigned long)simMillis, rangeIdx, chartRange, chartType,
         sN, dispCandN, chartMin(), chartMax(), appMode, (int)priceOnly);
}

int main(int argc, char **argv) {
  if (argc > 1) g_dataDir = argv[1];
  setup();
  int guard = 0;
  while (!(priceOk && chartRange == 0 && sN >= 2) && guard++ < 200) runLoopFor(100);
  sample("settled-1D-line");
  for (int i = 0; i < 40; i++) runLoopFor(100);  // hold 4s
  tap(66, 272);  // Cndl
  sample("after-Cndl-tap");
  for (int i = 0; i < 40; i++) runLoopFor(100);  // hold 4s
  sample("before-1W-tap");
  tap(54, 231);  // 1W
  sample("1W-tap+0.5s");
  tft.dumpPPM("/tmp/before-explicit-draw.ppm");
  drawAll();
  tft.dumpPPM("/tmp/after-explicit-draw.ppm");
  sample("after-explicit-drawAll");
  for (int i = 0; i < 5; i++) { runLoopFor(100); sample("1W-sample"); }
  for (int i = 0; i < 35; i++) runLoopFor(100);  // rest of the 4s hold
  sample("1W-tap+4s");
  return 0;
}
