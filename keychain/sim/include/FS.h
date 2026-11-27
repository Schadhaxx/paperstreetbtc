#pragma once
#include <Arduino.h>
#include <stdio.h>
#include <string>
#include "sim.h"

namespace fs {

class File {
  FILE *f_ = nullptr;
public:
  File() {}
  explicit File(FILE *f) : f_(f) {}
  operator bool() const { return f_ != nullptr; }
  size_t read(uint8_t *buf, size_t n) {
    if (!f_) return 0;
    return fread(buf, 1, n, f_);
  }
  void close() { if (f_) { fclose(f_); f_ = nullptr; } }
};

class FS {
public:
  File open(const char *path, const char *mode = "r") {
    if (!path) return File();
    std::string p = path;
    // Bare font names (e.g. OutfitXB29.vlw) live in the sim data dir.
    auto tryOpen = [](const std::string &cand) -> FILE * {
      return fopen(cand.c_str(), "rb");
    };
    FILE *f = tryOpen(p);
    if (!f && p.find('/') == std::string::npos) {
      if (!g_dataDir.empty()) f = tryOpen(g_dataDir + "/" + p);
    }
    return File(f);
  }
};

}  // namespace fs
