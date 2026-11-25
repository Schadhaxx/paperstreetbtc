// Node smoke test for the WASM build: boots the real sketch, steps it,
// taps buttons, and checks the price + framebuffer are real.
// Run: cd web && node ../tools/wasm-smoke-test.js
// (In Node, the glue exports Module via module.exports; the onRuntimeInitialized
// callback is set synchronously right after require, before the async
// wasm instantiation completes.)
const Module = require('/home/hatch/workspace/ps-keychain-sim/web/keychain.js');

Module.onRuntimeInitialized = () => {
  try {
    Module._sim_init();
    // Step ~2s of sim time so the sketch settles (price + 1D chart).
    for (let i = 0; i < 20; i++) Module._sim_step(100);
    const price = Module._sim_price_cents() / 100;
    const w = Module._sim_fb_width(), h = Module._sim_fb_height();
    const ptr = Module._sim_fb_ptr();
    const stride = Module._sim_fb_stride();
    const fb = Module.HEAPU16;
    const base = ptr >> 1;
    let nonzero = 0;
    for (let y = 0; y < h; y++)
      for (let x = 0; x < w; x++)
        if (fb[base + y * stride + x] !== 0) nonzero++;
    console.log(`price_ok=${Module._sim_price_ok()} price=$${price} fb=${w}x${h} nonzero_px=${nonzero}`);
    if (!Module._sim_price_ok() || price < 1000 || nonzero < 1000) {
      throw new Error('sketch did not settle with a real price/chart');
    }
    const tap = (dx, dy, steps = 3) => {
      Module._sim_touch_down(dx, dy);
      for (let i = 0; i < steps; i++) Module._sim_step(100);
      Module._sim_touch_up();
      for (let i = 0; i < 5; i++) Module._sim_step(100);
    };
    tap(66, 272); // Cndl (type pill, portrait)
    tap(45, 272); // back to Line
    tap(65, 251); // 1Y (range row 2)
    console.log(`after 1Y tap: fb=${Module._sim_fb_width()}x${Module._sim_fb_height()} price=$${Module._sim_price_cents() / 100}`);
    tap(142, 142); // Rotate -> landscape (scrub row, right end)
    const lw = Module._sim_fb_width(), lh = Module._sim_fb_height();
    console.log(`after rotate: fb=${lw}x${lh} landscape=${Module._sim_landscape()}`);
    if (lw !== 320 || lh !== 170 || !Module._sim_landscape()) {
      throw new Error('rotate did not switch to landscape');
    }
    tap(285, 158); // Portrait (landscape controls row)
    if (Module._sim_fb_width() !== 170 || Module._sim_fb_height() !== 320) {
      throw new Error('portrait did not switch back');
    }
    tap(108, 292); // Auth (control row)
    console.log(`after auth tap: fb=${Module._sim_fb_width()}x${Module._sim_fb_height()}`);
    console.log('WASM SMOKE TEST OK');
    process.exit(0);
  } catch (e) {
    console.error('WASM SMOKE TEST FAILED:', e);
    process.exit(1);
  }
};
setTimeout(() => { console.error('WASM SMOKE TEST TIMEOUT'); process.exit(1); }, 30000);
