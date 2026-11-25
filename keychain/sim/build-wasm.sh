#!/bin/bash
# WASM build for the keychain sim (em++, not emcc).
# Run from ~/workspace/ps-keychain-sim. Writes web/keychain.js + .wasm.
set -e
source /home/hatch/emsdk/emsdk_env.sh >/dev/null 2>&1
cd /home/hatch/workspace/ps-keychain-sim
FW=/home/hatch/workspace/ps-keychain-firmware
DEFS="-DUSER_SETUP_LOADED -DST7789_DRIVER -DINIT_SEQUENCE_3 -DCGRAM_OFFSET -DTFT_RGB_ORDER=TFT_RGB -DTFT_INVERSION_ON -DTFT_PARALLEL_8_BIT -DTFT_WIDTH=170 -DTFT_HEIGHT=320 -DTFT_CS=6 -DTFT_DC=7 -DTFT_RST=5 -DTFT_WR=8 -DTFT_RD=9 -DTFT_D0=39 -DTFT_D1=40 -DTFT_D2=41 -DTFT_D3=42 -DTFT_D4=45 -DTFT_D5=46 -DTFT_D6=47 -DTFT_D7=48 -DTFT_BL=38 -DTFT_BACKLIGHT_ON=1 -DLOAD_GLCD -DLOAD_FONT2 -DLOAD_FONT4 -DLOAD_FONT6 -DLOAD_FONT7 -DLOAD_FONT8 -DLOAD_GFXFF -DSMOOTH_FONT"
# shellcheck disable=SC2086
em++ -std=c++17 -O2 -Iinclude -Ithird_party/ArduinoJson/src -I$FW/lib/qrcodegen $DEFS \
  src/stubs.cpp src/tft.cpp src/md.cpp $FW/lib/qrcodegen/qrcodegen.cpp src/wasm.cpp \
  --embed-file data@/data \
  -s "EXPORTED_RUNTIME_METHODS=['HEAPU16','FS']" \
  -o web/keychain.js
ls -la web/keychain.js web/keychain.wasm
