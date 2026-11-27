// 4-account Auth list check: seeds 3 extra accounts after setup
// (the sim only ships the 1 Demo account) and dumps the list with
// 4 rows, hidden codes, and a row-3 selection, in both themes.
// Usage: auth-list-4up [dataDir] [outDir]
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>
#include "sim.h"
#include "TFT_eSPI.h"

float rangeChange();
void savePrefs();

#include "../../firmware/paperstreet-keychain.ino"

static std::string g_dir = "auth-list-4up";

static void dump(const char *name) {
  char path[512];
  snprintf(path, sizeof(path), "%s/%s.ppm", g_dir.c_str(), name);
  tft.dumpPPM(path);
  fprintf(stderr, "[frames] %s (theme=%s nAuth=%d authIdx=%d hide=%d)\n",
          name, themeDark ? "dark" : "light", nAuth, authIdx,
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

static void settle() {
  int guard = 0;
  while (!(priceOk && chartRange == 0 && sN >= 2) && guard++ < 200) runLoopFor(100);
}

int main(int argc, char **argv) {
  if (argc > 1) g_dataDir = argv[1];
  if (argc > 2) g_dir = argv[2];
  setup();
  settle();

  // Seed 3 more accounts (same test secret — layout is what's under
  // test; the long label checks row truncation).
  const char *labels[3] = {"GitHub", "Email", "PaperStreet-Backup-2"};
  for (int i = 0; i < 3; i++) {
    strncpy(authAccts[1 + i].label, labels[i], AUTH_LABEL_LEN - 1);
    authAccts[1 + i].label[AUTH_LABEL_LEN - 1] = 0;
    strncpy(authAccts[1 + i].secret, AUTH_DEMO_SECRET, AUTH_SEC_LEN - 1);
    authAccts[1 + i].secret[AUTH_SEC_LEN - 1] = 0;
  }
  nAuth = 4; authIdx = 0;
  authRefresh();

  appMode = MODE_AUTH;
  drawAll();
  dump("dark-auth-4up");
  // HIDE / SHOW by id 53; row 3 by id 63; nav pills were dropped.
  {
    for (int i = 0; i < nBtns; i++) if (btns[i].id == 53)
      tap(btns[i].x + btns[i].w / 2, btns[i].y + btns[i].h / 2);
  }
  runLoopFor(500); dump("dark-auth-4up-hidden");
  {
    for (int i = 0; i < nBtns; i++) if (btns[i].id == 53)
      tap(btns[i].x + btns[i].w / 2, btns[i].y + btns[i].h / 2);
  }
  runLoopFor(500);
  {
    for (int i = 0; i < nBtns; i++) if (btns[i].id == 63)
      tap(btns[i].x + btns[i].w / 2, btns[i].y + btns[i].h / 2);
  }
  runLoopFor(500); dump("dark-auth-4up-sel3");
  goToPage(PAGE_CHART); runLoopFor(500);
  themeDark = false; drawAll();                                 // Light (chart theme pill dropped)
  goToPage(PAGE_AUTH); runLoopFor(1000); dump("light-auth-4up");
  fprintf(stderr, "[frames] done\n");
  return 0;
}
