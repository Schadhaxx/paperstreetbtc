#!/usr/bin/env node
/* TA Stage 2 indicator unit tests (20 Nov 2026): SMA / EMA / Bollinger (20, 2s) /
   RSI (14, Wilder) in assets/js/btcchart-ta.js, checked against reference values
   computed independently in Python (ps-ta-stage1/ref_values.py). Text output,
   no chart, no network. Run: node tests/test_ta_indicators.js */
var M = require('../assets/js/btcchart-ta.js');
var fails = 0, n = 0;
function chk(name, ok, detail) { n++; if (ok) { console.log('ok', name); } else { fails++; console.log('FAIL', name, detail === undefined ? '' : String(detail).slice(0, 200)); } }
function close(a, b) { if (a === null || b === null) return a === b; return Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(b)); }
function arrEq(name, got, want) {
  if (!Array.isArray(got) || got.length !== want.length) { chk(name, false, 'length ' + (got && got.length) + ' vs ' + want.length); return; }
  for (var i = 0; i < want.length; i++) { if (!close(got[i], want[i])) { chk(name, false, 'index ' + i + ': got ' + got[i] + ' want ' + want[i]); return; } }
  chk(name, true);
}
var C = [67210.5, 68115.25, 67980.0, 69420.75, 70110.0, 69850.5, 71230.25, 72480.0, 71900.5, 73150.75, 74200.0, 73890.25, 75120.5, 76340.0, 75880.75, 77100.5, 78450.25, 77920.0, 79100.75, 80320.5, 79840.25, 78650.0, 77420.75, 76210.5, 75300.0, 74180.25, 72950.5, 71840.0, 70920.75, 70110.5, 69480.0, 68920.25, 69480.0, 68920.25, 69480.0, 68920.25, 69480.0, 68920.25, 69480.0, 70110.5];
arrEq('sma20 on 40 closes', M.sma(C, 20), [null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, 73488.6, 74120.0875, 74646.825, 75118.8625, 75458.35, 75717.85, 75934.3375, 76020.35, 75988.35, 75939.3625, 75787.35, 75551.35, 75302.85, 75020.825, 74649.8375, 74329.8, 73920.7875, 73472.275, 73022.2875, 72541.25, 72030.75]);
arrEq('ema20 on 40 closes', M.ema(C, 20), [null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, 73488.6, 74093.51904761905, 74527.46961451246, 74803.02012741604, 74937.06582956688, 74971.63098865574, 74896.26137068853, 74710.9507639563, 74437.52688167474, 74102.59575008668, 73722.39615484033, 73318.35842580792, 72899.49095668335, 72573.82515128494, 72225.86561306732, 71964.354602299, 71674.43987827052, 71465.44560414953, 71223.04602280195, 71057.04163967796, 70966.89481685149]);
var bb = M.bollinger(C, 20, 2);
arrEq('bollinger mid on 40 closes', bb.mid, [null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, 73488.6, 74120.0875, 74646.825, 75118.8625, 75458.35, 75717.85, 75934.3375, 76020.35, 75988.35, 75939.3625, 75787.35, 75551.35, 75302.85, 75020.825, 74649.8375, 74329.8, 73920.7875, 73472.275, 73022.2875, 72541.25, 72030.75]);
arrEq('bollinger upper on 40 closes', bb.up, [null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, 81250.55075093884, 81790.71701992044, 82037.43758810796, 81929.11195849086, 81756.21693333545, 81521.10876641737, 81137.99280246528, 80960.33029449511, 81026.95684217375, 81152.03650063298, 81472.36492610179, 81840.16606584261, 82198.11252654677, 82369.35948161605, 82430.9550712024, 82403.12084646709, 82216.9694611117, 81710.16877799325, 81222.32857806023, 80379.30487668976, 79064.31426358642]);
arrEq('bollinger lower on 40 closes', bb.lo, [null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, 65726.64924906117, 66449.45798007955, 67256.21241189203, 68308.61304150915, 69160.48306666456, 69914.59123358264, 70730.68219753471, 71080.3697055049, 70949.74315782626, 70726.68849936702, 70102.33507389823, 69262.5339341574, 68407.58747345324, 67672.29051838395, 66868.71992879758, 66256.47915353291, 65624.60553888831, 65234.381222006734, 64822.24642193979, 64703.195123310245, 64997.18573641358]);
arrEq('rsi14 on 40 closes', M.rsi(C, 14), [null, null, null, null, null, null, null, null, null, null, null, null, null, null, 85.66022991342258, 87.05859174795883, 88.4059406865998, 84.67625516867376, 86.08412718241112, 87.37457871796973, 84.06899373333579, 76.35859784691476, 69.29051948696122, 63.09785482876337, 58.83748419520013, 54.007837309001694, 49.22859380700692, 45.32779641786023, 42.33719970891976, 39.84200460110925, 37.966847522456824, 36.331992006019576, 39.15358592632493, 37.37005098323887, 40.29877214639917, 38.36665020158862, 41.392720182277, 39.314004187494135, 42.42765422949758, 45.80090788415297]);
var C2 = [100, 101, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113, 115, 117, 116, 118, 120, 119, 121, 123, 122, 124, 126, 125, 127, 129, 128, 130, 132, 131, 133, 135, 134, 136, 138, 137, 139, 141, 140, 142, 144, 143, 145, 147, 146, 148, 150, 149, 151, 153, 152, 154, 156, 155, 157, 159];
arrEq('sma50 on 60 closes', M.sma(C2, 50), [null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, 123.54, 124.54, 125.5, 126.48, 127.52, 128.5, 129.48, 130.52, 131.5, 132.48, 133.52]);
arrEq('ema50 on 60 closes', M.ema(C2, 50), [null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, 123.54, 124.57764705882353, 125.53538638985006, 126.53399868828731, 127.5718810926682, 128.52984654001455, 129.52867608746496, 130.56676722128987, 131.5249332126118, 132.52395543956823, 133.56223169684006]);
arrEq('sma20 on 60 closes', M.sma(C2, 20), [null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, 108.6, 109.6, 110.5, 111.45, 112.55, 113.5, 114.45, 115.55, 116.5, 117.45, 118.55, 119.5, 120.45, 121.55, 122.5, 123.45, 124.55, 125.5, 126.45, 127.55, 128.5, 129.45, 130.55, 131.5, 132.45, 133.55, 134.5, 135.45, 136.55, 137.5, 138.45, 139.55, 140.5, 141.45, 142.55, 143.5, 144.45, 145.55, 146.5, 147.45, 148.55]);
var C3 = [50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0];
arrEq('rsi14 on flat series is 100', M.rsi(C3, 14), [null, null, null, null, null, null, null, null, null, null, null, null, null, null, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]);
var bb3 = M.bollinger(C3, 20, 2);
arrEq('bollinger on flat series has zero width', bb3.up, [null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, 50.0]);
arrEq('bollinger lower on flat series has zero width', bb3.lo, [null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, 50.0]);
var C4 = [100.0, 99.0, 98.0, 97.0, 96.0, 95.0, 94.0, 93.0, 92.0, 91.0, 90.0, 89.0, 88.0, 87.0, 86.0, 85.0, 84.0, 83.0, 82.0, 81.0, 80.0, 79.0, 78.0, 77.0, 76.0, 75.0, 74.0, 73.0, 72.0, 71.0];
arrEq('rsi14 on all-down series is 0', M.rsi(C4, 14), [null, null, null, null, null, null, null, null, null, null, null, null, null, null, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]);
chk('sma period > length is all null', M.sma(C, 50).every(function (v) { return v === null; }));
chk('ema period > length is all null', M.ema(C, 50).every(function (v) { return v === null; }));
chk('rsi length <= period is all null', M.rsi(C.slice(0, 14), 14).every(function (v) { return v === null; }));
chk('sma period 1 equals closes', JSON.stringify(M.sma(C, 1)) === JSON.stringify(C));
chk('ema period 1 equals closes', JSON.stringify(M.ema(C, 1)) === JSON.stringify(C));
chk('sma first valid at index period-1', M.sma(C, 20)[18] === null && M.sma(C, 20)[19] !== null);
chk('rsi first valid at index period', M.rsi(C, 14)[13] === null && M.rsi(C, 14)[14] !== null);
chk('bollinger first valid at index period-1', bb.up[18] === null && bb.up[19] !== null);
console.log('TA INDICATORS:', fails ? 'FAIL (' + fails + '/' + n + ')' : 'PASS (' + n + ' checks)');
process.exit(fails ? 1 : 0);
