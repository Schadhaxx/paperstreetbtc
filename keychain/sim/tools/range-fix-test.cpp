// Verification for the range-change fetch-throttle fix:
// boot -> settle on 1D -> tap 1W within seconds of boot -> confirm the
// 1W chart (not the stale 1D chart) is in place WITHOUT waiting 30 s.
// Expected (from data/candles-3600.json, newest 168 x 1h, bucketed to
// 28 x 6h for display — bucketing preserves the global extremes).
// Snapshot 24 Nov 2026 (refreshed for Pass 3; BTC ~$59.6k, down from
// ~$62.6k, so the 1W high is lower than in the old snapshot):
//   1D tiles: low ~$59,542 / high ~$62,823
//   1W tiles: low ~$56,221 / high ~$64,723
// The 1W low (~$56.2k) vs the stale 1D low (~$59.5k) is the discriminator.
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

int main(int argc, char **argv) {
  if (argc > 1) g_dataDir = argv[1];
  setup();

  int guard = 0;
  while (!(priceOk && chartRange == 0 && sN >= 2) && guard++ < 200) runLoopFor(100);
  unsigned long bootMs = (unsigned long)simMillis;
  printf("settled: t=%lums price=$%.0f rangeIdx=%d chartRange=%d sN=%d\n",
         bootMs, priceUSD, rangeIdx, chartRange, sN);
  printf("1D tiles: low=%.2f high=%.2f\n", chartMin(), chartMax());

  // Tap 1W (range row 1, coords from the video tour) seconds after boot.
  tap(54, 213);  // 1W (R1_Y 207)
  runLoopFor(2000);
  unsigned long tapMs = (unsigned long)simMillis;
  printf("after 1W tap +2s: t=%lums rangeIdx=%d chartRange=%d sN=%d\n",
         tapMs, rangeIdx, chartRange, sN);
  printf("1W tiles: low=%.2f high=%.2f\n", chartMin(), chartMax());

  bool fetched = (chartRange == 1);
  // The 1W high must clear $64k: the stale 1D high is ~$62.8k, the
  // fresh 1W high ~$64.7k. (Was $65k against the old snapshot, whose
  // 1W high was ~$65.5k; BTC has fallen since, so the threshold
  // moved with the data — the firmware is unchanged here.)
  bool trueData = (chartMin() < 58000.0f) && (chartMax() > 64000.0f);
  bool fast = (tapMs < 30000);
  printf("checks: fetched-1W=%d true-1W-data=%d under-30s=%d (t=%lums)\n",
         (int)fetched, (int)trueData, (int)fast, tapMs);

  // Phase 2 — same 1W data in candle mode: the tiles then come from the
  // bucketed 28 x 6h candle lows/highs, so the low should be the true
  // 7d wick low (~$55,106 in this snapshot).
  tap(79, 175);  // Cndl (TYPE_Y 168)
  runLoopFor(1000);
  printf("1W candles: type=%d dispCandN=%d low=%.2f high=%.2f\n",
         chartType, dispCandN, chartMin(), chartMax());
  bool candleData = (chartType == 1) && (chartMin() < 57000.0f) && (chartMax() > 64000.0f);
  printf("checks: candle-1W-data=%d\n", (int)candleData);

  // Phase 3 — first-draw tiles: the fetch's own drawAll must already
  // paint the true 1W tiles. Back to 1D candles, then tap 1W again;
  // checksum the HIGH/LOW tile row right after the fetch lands, then
  // checksum again after an explicit extra drawAll(). If the fetch's
  // draw lagged one draw behind, the two checksums differ (stale 1D
  // tiles $62,943/$59,300 vs fresh 1W tiles $64,933/$55,106); if it
  // painted fresh tiles, they match. No extra draw in between.
  auto tileHash = []() {
    const uint16_t *fb = tft.framebuffer();
    uint64_t h = 1469598103934665603ULL;
    for (int y = 277; y < 302; y++)  // 24H HIGH/LOW tiles (TILE_Y2)
      for (int x = 0; x < 170; x++) {
        h ^= (uint64_t)fb[y * 320 + x];
        h *= 1099511628211ULL;
      }
    return h;
  };
  tap(23, 213);  // 1D (R1_Y 207)
  guard = 0;
  while (chartRange != 0 && guard++ < 50) runLoopFor(100);
  runLoopFor(1000);
  printf("back on 1D candles: rangeIdx=%d chartRange=%d type=%d low=%.2f high=%.2f\n",
         rangeIdx, chartRange, chartType, chartMin(), chartMax());
  tap(54, 213);  // 1W (R1_Y 207)  // 1W again
  guard = 0;
  while (chartRange != 1 && guard++ < 50) runLoopFor(100);
  uint64_t hash1 = tileHash();
  printf("1W first-draw tiles: rangeIdx=%d chartRange=%d low=%.2f high=%.2f hash=%llx\n",
         rangeIdx, chartRange, chartMin(), chartMax(), (unsigned long long)hash1);
  drawAll();
  uint64_t hash2 = tileHash();
  printf("1W after extra drawAll: low=%.2f high=%.2f hash=%llx\n",
         chartMin(), chartMax(), (unsigned long long)hash2);
  bool firstDrawFresh = (hash1 == hash2) && (chartMin() < 57000.0f) && (chartMax() > 64000.0f);
  printf("checks: first-draw-tiles-fresh=%d\n", (int)firstDrawFresh);

  bool ok = fetched && trueData && fast && candleData && firstDrawFresh;
  printf("RANGE-FIX TEST %s\n", ok ? "PASS" : "FAIL");
  return ok ? 0 : 1;
}
