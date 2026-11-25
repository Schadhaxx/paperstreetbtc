// Pass 5 finding 1 verification: the block-clock ring gauge must have
// 0 holes. Boots the real sketch, lands on the clock page (focus 0),
// and samples every pixel whose centre lies in the annulus
// 16.5 <= r < 22.5 around the ring centre (38,128): each must be the
// arc colour (C_CYAN) or the track colour (C_BARBG) — anything else
// (e.g. the card surface) is a hole. Checks both themes.
// Usage: ring-check [dataDir]
// Exit 0 = 0 holes in both themes.
#include <cstdio>
#include <cstdint>
#include <cmath>
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

static int sampleRing(const char *theme) {
  int holes = 0, filled = 0, fg = 0, track = 0;
  for (int y = 128 - 23; y <= 128 + 23; y++) {
    for (int x = 38 - 23; x <= 38 + 23; x++) {
      double dx = x - 38, dy = y - 128;
      double r = sqrt(dx * dx + dy * dy);
      if (r < 16.5 || r >= 22.5) continue;
      uint16_t px = tft.readPixel(x, y);
      if (px == C_CYAN) { fg++; filled++; }
      else if (px == C_BARBG) { track++; filled++; }
      else {
        holes++;
        if (holes <= 5)
          printf("  hole %s at (%d,%d) r=%.2f px=0x%04X\n", theme, x, y, r, px);
      }
    }
  }
  printf("ring %s: annulus px=%d fg=%d track=%d holes=%d\n",
         theme, filled + holes, fg, track, holes);
  return holes;
}

int main(int argc, char **argv) {
  if (argc > 1) g_dataDir = argv[1];
  setup();
  int guard = 0;
  while (!(priceOk && chartRange == 0 && sN >= 2) && guard++ < 200)
    runLoopFor(100);
  goToPage(PAGE_CLOCK);
  runLoopFor(500);
  clockFocus = 0;
  drawAll();
  printf("clock page: focus=%d lastBlockTs=%ld\n", clockFocus, lastBlockTs);
  int holes = 0;
  holes += sampleRing("dark");
  themeDark = false;
  drawAll();
  holes += sampleRing("light");
  printf(holes == 0 ? "RING CHECK OK (0 holes, both themes)\n"
                    : "RING CHECK FAILED (%d holes)\n", holes);
  return holes == 0 ? 0 : 1;
}
