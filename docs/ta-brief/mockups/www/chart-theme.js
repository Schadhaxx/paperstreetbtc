/* Chart chrome follows data-theme. Dark mode keeps the original color strings. */
(function () {
  window.psC = window.psC || function (dark, light) {
    return document.documentElement.getAttribute("data-theme") === "light" ? light : dark;
  };

  var INK = {
    "#9aa6bc": "#475569",
    "#94a3b8": "#475569",
    "#64748b": "#475569",
    "#cbd5e1": "#334155",
    "#e2e8f0": "#334155",
    "#eef2fb": "#0f172a",
    "#e8eef7": "#0f172a",
    "#e5e7eb": "#0f172a",
  };
  var GRID = {
    "#1e293b": "#e2e8f0",
    "rgba(255,255,255,.05)": "rgba(15,23,42,.08)",
    "rgba(255,255,255,.08)": "rgba(15,23,42,.10)",
    "rgba(255,255,255,0.05)": "rgba(15,23,42,.08)",
    "rgba(255,255,255,0.08)": "rgba(15,23,42,.10)",
  };
  /* Near-white series only. Cyan stays #22d3ee. */
  var SERIES = {
    "#cbd5e1": "#64748b",
    "#e2e8f0": "#64748b",
    "#f1f5f9": "#64748b",
  };

  function map(table, c) {
    return typeof c === "string" && table[c] ? table[c] : c;
  }

  function themeConfig(cfg) {
    if (!cfg || document.documentElement.getAttribute("data-theme") !== "light") return cfg;
    var o = cfg.options || (cfg.options = {});
    o.plugins = o.plugins || {};
    var tip = o.plugins.tooltip || (o.plugins.tooltip = {});
    if (tip.enabled !== false) {
      tip.backgroundColor = "#ffffff";
      tip.titleColor = "#0f172a";
      tip.bodyColor = "#334155";
      tip.borderColor = "#e2e8f0";
      tip.borderWidth = 1;
    }
    var leg = o.plugins.legend;
    if (leg && leg.labels && typeof leg.labels.color === "string") {
      leg.labels.color = map(INK, leg.labels.color);
    }
    if (o.scales) {
      Object.keys(o.scales).forEach(function (k) {
        var s = o.scales[k];
        if (!s) return;
        if (s.grid && typeof s.grid.color === "string") s.grid.color = map(GRID, s.grid.color);
        if (s.ticks && typeof s.ticks.color === "string") s.ticks.color = map(INK, s.ticks.color);
      });
    }
    var sets = cfg.data && cfg.data.datasets;
    if (sets) {
      sets.forEach(function (ds) {
        if (!ds) return;
        if (typeof ds.borderColor === "string") ds.borderColor = map(SERIES, ds.borderColor);
        if (typeof ds.pointBackgroundColor === "string") ds.pointBackgroundColor = map(SERIES, ds.pointBackgroundColor);
        if (typeof ds.backgroundColor === "string") ds.backgroundColor = map(SERIES, ds.backgroundColor);
      });
    }
    return cfg;
  }

  function install(C) {
    if (!C || C.__psWrapped) return C;
    function Wrapped(item, config) {
      return new C(item, themeConfig(config));
    }
    Wrapped.prototype = C.prototype;
    /* Inherit static members (Chart.register, Chart.defaults, getChart...),
       which are non-enumerable on the Chart.js class. */
    try { Object.setPrototypeOf(Wrapped, C); } catch (e) {}
    Object.keys(C).forEach(function (k) {
      try { Wrapped[k] = C[k]; } catch (e) {}
    });
    Wrapped.__psWrapped = true;
    return Wrapped;
  }

  /* Dark (default): do nothing at all. window.Chart is left untouched. */
  if (document.documentElement.getAttribute("data-theme") !== "light") return;

  var current = window.Chart;
  try {
    Object.defineProperty(window, "Chart", {
      configurable: true,
      enumerable: true,
      get: function () { return current; },
      set: function (v) { current = install(v); },
    });
  } catch (e) {
    if (current) window.Chart = install(current);
  }
  if (current) current = install(current);
})();
