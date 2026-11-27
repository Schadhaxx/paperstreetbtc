# Keychain rebuild artifacts (27 Nov 2026)

Saved so any bot or machine can pick up the work from GitHub.

- `web-build/` - the browser simulator build (C++ firmware compiled to WebAssembly with emsdk 7.0.1) from branch keychain-rebuild at 27879e8. Upload this folder as-is to Netlify (manual deploy) to publish the sim.
- `fonts/` - the .vlw fonts used by the sim and firmware (copy into keychain/sim/data and keychain/firmware/data; normally gitignored).
- `PLAN.md`, `HANDOFF.md` - the rebuild plan and the handoff notes for all three phases.
- `shots/` - side-by-side screenshots, prototype vs rebuilt firmware, per phase.

Not included: ArduinoJson v7 (download it into keychain/sim/third_party/ArduinoJson).
