#pragma once
// Light-sleep in the sim just advances the virtual clock so loop()
// does not spin. Matches the firmware's 50 ms timer wakeup slices.
inline void esp_sleep_enable_timer_wakeup(uint64_t us) { (void)us; }
inline void esp_light_sleep_start() { extern uint64_t simMillis; simMillis += 50; }
