#pragma once
#include <Arduino.h>
#include <map>
#include <string>
class Preferences {
  std::map<std::string, std::string> kv_;
public:
  bool begin(const char *name, bool readOnly = false) { (void)name; (void)readOnly; return true; }
  void end() {}
  void putFloat(const char *k, float v);
  void putBool(const char *k, bool v);
  void putInt(const char *k, int v);
  void putString(const char *k, const char *v);
  float getFloat(const char *k, float def);
  bool getBool(const char *k, bool def);
  int getInt(const char *k, int def);
  String getString(const char *k, const char *def);
};
