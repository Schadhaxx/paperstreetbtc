#pragma once
#include <stdint.h>
#include <string>
extern uint64_t simMillis;
extern std::string g_dataDir;
extern bool simFingerDown;
extern int16_t simFingerDX, simFingerDY;
void simSetFinger(bool down, int16_t dx, int16_t dy);
