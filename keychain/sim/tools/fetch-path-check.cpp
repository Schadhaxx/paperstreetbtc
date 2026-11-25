// Pass 5 findings 3 + 6 verification.
//  F3: entering the clock page must NOT fetch synchronously — after
//      goToPage(PAGE_CLOCK) with lastClockFetchMs == 0, the page is
//      drawn and lastClockFetchMs is still 0; the loop's 5-min slot
//      does the fetch on the next pass.
//  F6: after failed fetches the `fetching` flag must be clear (the
//      guard cleared) so a redrawn scrub row cannot keep saying
//      "Fetching...". Run against data-empty/ for the failure half.
// Usage: fetch-path-check [dataDir]
// Exit 0 = all checks pass.
#include <cstdio>
#include <cstdint>
#include <string>
#include "sim.h"
#include "TFT_eSPI.h"

float rangeChange();
void savePrefs();

#include "/home/hatch/workspace/ps-keychain-firmware/paperstreet-keychain.ino"

static int g_fail = 0;
static void check(bool ok, const char *what) {
  printf("%s %s\n", ok ? "PASS" : "FAIL", what);
  if (!ok) g_fail++;
}

static void runLoopFor(unsigned long ms) {
  unsigned long start = (unsigned long)simMillis;
  unsigned long target = start + ms;
  int guard = 0;
  while (simMillis < target && guard++ < 100000) loop();
}

int main(int argc, char **argv) {
  if (argc > 1) g_dataDir = argv[1];
  setup();
  int guard = 0;
  while (!(priceOk && chartRange == 0 && sN >= 2) && guard++ < 200)
    runLoopFor(100);
  // F3: fresh clock entry performs no fetch synchronously.
  lastClockFetchMs = 0;
  goToPage(PAGE_CLOCK);
  check(curPage() == 2, "F3: clock page entered");
  check(lastClockFetchMs == 0,
        "F3: no synchronous fetch on clock entry (lastClockFetchMs still 0)");
  runLoopFor(2000);
  check(lastClockFetchMs > 0,
        "F3: loop clock slot fetched after entry");
  check(blockHeight > 0 || g_dataDir == "data-empty",
        "F3: clock data landed (or empty-data dir, as expected)");
  // F6: after loop passes with (possibly failing) fetches, the flag
  // is clear — a redrawn scrub row shows the hint, not "Fetching...".
  runLoopFor(65000);
  check(!fetching, "F6: fetching flag clear after loop passes");
  printf(g_fail == 0 ? "FETCH-PATH CHECK OK\n" : "FETCH-PATH CHECK FAILED (%d)\n",
         g_fail);
  return g_fail == 0 ? 0 : 1;
}
