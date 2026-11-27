#pragma once
#include <Arduino.h>
class WiFiClientSecure {
public:
  void setCACert(const char *cert) { (void)cert; }  // no-op in the sim
  void setTimeout(int ms) { (void)ms; }
};
