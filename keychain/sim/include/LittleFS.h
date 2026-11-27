#pragma once
#include "FS.h"
class LittleFSClass : public fs::FS {
public:
  bool begin(bool formatOnFail = false) { (void)formatOnFail; return true; }
};
extern LittleFSClass LittleFS;
