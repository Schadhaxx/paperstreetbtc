// New-apps frame harness: renders every Pass-1 screen in BOTH themes
// so they can be inspected as images. Mirrors tools/refine-frames.cpp.
// Usage: new-apps-frames [dataDir] [outDir]
// Dumps: dark/light x {1d-line (chip row), 1d-comps, 1y-comps,
// auth-list, auth-hidden, clock-0/1/2, qr-jade, qr-jade-flip,
// qr-ln, qr-ln-flip}
#include <cstdio>
#include <cstdint>
#include <string>
#include "sim.h"
#include "TFT_eSPI.h"

float rangeChange();
void savePrefs();

#include "/home/hatch/workspace/ps-keychain-firmware/paperstreet-keychain.ino"

static std::string g_dir = "new-apps-frames";

static void dump(const char *name) {
  char path[512];
  snprintf(path, sizeof(path), "%s/%s.ppm", g_dir.c_str(), name);
  tft.dumpPPM(path);
  fprintf(stderr, "[frames] %s (theme=%s range=%d type=%d mode=%d focus=%d qr=%d flip=%d cmp=%d%d%d ok=%d%d%d hide=%d)\n",
          name, themeDark ? "dark" : "light", rangeIdx, chartType,
          appMode, clockFocus, qrPage, (int)qrFlipped,
          (int)cmpOn[0], (int)cmpOn[1], (int)cmpOn[2],
          (int)cmpOk[0], (int)cmpOk[1], (int)cmpOk[2],
          (int)authHideCodes);
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

// Tap a button by id (centre of its registered hit rect) — robust
// to chip widths changing with the % text (Pass 3 finding 8).
static void tapBtn(int id) {
  for (int i = 0; i < nBtns; i++) {
    if (btns[i].id == id) {
      tap(btns[i].x + btns[i].w / 2, btns[i].y + btns[i].h / 2);
      return;
    }
  }
  fprintf(stderr, "[frames] ERROR tapBtn: no button id %d (nBtns=%d)\n", id, nBtns);
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
  // 1D: the VS row is hidden (Pass 3 finding 5) — a tap where the
  // SPX chip used to be must be a no-op, and the dump proves the
  // row is gone (no flat lines, no "+0%" chips).
  tap(41, 310); runLoopFor(1000); dump("dark-1d-comps");
  tap(65, 251); runLoopFor(3000);                            // 1Y line
  tapBtn(43); tapBtn(44); tapBtn(45); runLoopFor(3000);     // SPX, GOLD, MSTR
  dump("dark-1y-comps");                                     // 1Y line + comps
  tap(108, 292); runLoopFor(1500); dump("dark-auth-list"); // Auth list
  tap(146, 29); runLoopFor(500); dump("dark-auth-hidden"); // HIDE codes
  tap(146, 29); runLoopFor(500);                           // SHOW again
  tap(92, 238); runLoopFor(2000); dump("dark-clock-0");    // Clock nav -> block focus (Auth nav row y 226, Pass 5 finding 11)
  tap(85, 178); runLoopFor(500); dump("dark-clock-1");     // dot 2: sats
  tap(101, 178); runLoopFor(500); dump("dark-clock-2");    // dot 3: halving
  tap(87, 302); runLoopFor(1000); dump("dark-qr-jade");    // QR nav -> Jade
  tap(85, 136); runLoopFor(500); dump("dark-qr-jade-flip");// tap QR card
  tap(85, 250); runLoopFor(500);                           // tap anywhere: back
  tap(98, 49); runLoopFor(1000); dump("dark-qr-ln");       // Lightning seg
  tap(85, 136); runLoopFor(500); dump("dark-qr-ln-flip");  // tap QR card
  tap(85, 250); runLoopFor(500);                           // back

  // ---- light pass: back to chart, flip theme, walk the same views ----
  tap(53, 302); runLoopFor(1000);                          // Chart nav -> chart (1Y comps)
  tap(48, 292);                                            // Light half of Dark|Light
  fprintf(stderr, "[frames] after Light tap: themeDark=%d\n", (int)themeDark);
  if (themeDark) { themeDark = false; drawAll(); fprintf(stderr, "[frames] WARNING: Light tap missed, forced light\n"); }
  runLoopFor(500);
  dump("light-1y-comps");
  tap(108, 292); runLoopFor(1500); dump("light-auth-list");
  tap(146, 29); runLoopFor(500); dump("light-auth-hidden");
  tap(146, 29); runLoopFor(500);
  tap(92, 238); runLoopFor(2000); dump("light-clock-2x"); // entry keeps focus 2 (Auth nav row y 226)
  tap(69, 178); runLoopFor(500); dump("light-clock-0");    // dot 1: block focus
  tap(85, 178); runLoopFor(500); dump("light-clock-1");
  tap(101, 178); runLoopFor(500); dump("light-clock-2");
  tap(87, 302); runLoopFor(1000); tap(58, 49); runLoopFor(500); dump("light-qr-jade");
  tap(85, 136); runLoopFor(500); dump("light-qr-jade-flip");
  tap(85, 250); runLoopFor(500);
  tap(98, 49); runLoopFor(1000); dump("light-qr-ln");
  tap(85, 136); runLoopFor(500); dump("light-qr-ln-flip");

  fprintf(stderr, "[frames] done\n");
  return 0;
}
