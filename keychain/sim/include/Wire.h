#pragma once
#include <Arduino.h>
class TwoWire {
  uint8_t buf_[8]{};
  int buflen_ = 0, bufpos_ = 0;
  uint8_t reg_ = 0;
public:
  void begin(int sda, int scl) { (void)sda; (void)scl; }
  void beginTransmission(uint8_t addr) { (void)addr; }
  void write(uint8_t v) { reg_ = v; }
  uint8_t endTransmission() { return endTransmission(true); }
  uint8_t endTransmission(bool stop);
  int requestFrom(uint8_t addr, uint8_t qty);
  int read();
};
extern TwoWire Wire;
