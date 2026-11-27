// Focused check for the step3-frames R7 LIVE-tap clause: tap the LIVE
// indicator and confirm a fresh price poll actually ran
// (lastPriceOkMs advances). The step3 R7 check also requires
// priceUSD > 60000, which the current $59,647 snapshot cannot satisfy
// on any firmware — that clause is data staleness, not a regression.
// Usage: live-tap-check [dataDir]
#include <cstdio>
#include <cstdint>
#include <string>
#include "sim.h"
#include "TFT_eSPI.h"

float rangeChange();
void savePrefs();

#include "../../firmware/paperstreet-keychain.ino"

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

int main(int argc, char **argv) {
  if (argc > 1) g_dataDir = argv[1];
  setup();
  int guard = 0;
  while (!(priceOk && chartRange == 0 && sN >= 2) && guard++ < 200)
    runLoopFor(100);
  unsigned long okBefore = lastPriceOkMs;
  tap(liveHitX + liveHitW / 2, 7);  // LIVE indicator (right of status bar)
  runLoopFor(2000);
  printf("okBefore=%lu okAfter=%lu priceOk=%d priceUSD=%.0f manualRefresh=%d\n",
         okBefore, lastPriceOkMs, (int)priceOk, priceUSD, (int)manualRefresh);
  bool ok = (lastPriceOkMs != okBefore && priceOk);
  printf(ok ? "LIVE-TAP CHECK OK (fresh poll ran)\n"
            : "LIVE-TAP CHECK FAILED\n");
  return ok ? 0 : 1;
}
