#!/usr/bin/env node
/* Reference functions for the BTC trend-support (floor) overlay redo.
   Pure helpers, no I/O. Pepper should expose the same names on P._floor:
     at, broken, isWeekComplete, weekMonday, evaluateBreak, display
*/
'use strict';

const LABEL = 'Trend support (weekly closes)';
const BREAK_RULE = 'Completed weekly close (Monday-Sunday UTC) 2% or more below the floor. An in-progress week does not count.';
const BROKEN_NOTE = 'Broken: a completed weekly close finished 2% or more below this line.';
const BREAK_TOL = 0.98;

function pad(n) { return n < 10 ? '0' + n : String(n); }
function isoDate(d) {
  return d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate());
}

/* Returns {kind: 'date'|'datetime', date: Date at UTC midnight, instant?: Date}. */
function parseAsOf(value) {
  if (value instanceof Date) {
    if (isNaN(value.getTime())) throw new TypeError('bad as_of date');
    return { kind: 'datetime', date: utcMidnight(value), instant: value };
  }
  if (typeof value !== 'string') throw new TypeError('as_of must be an ISO string or Date');
  const s = value.trim();
  if (s.indexOf('T') !== -1) {
    const inst = new Date(s.endsWith('Z') || /[+-]\d\d:?\d\d$/.test(s) ? s : s + 'Z');
    if (isNaN(inst.getTime())) throw new TypeError('bad as_of datetime');
    return { kind: 'datetime', date: utcMidnight(inst), instant: inst };
  }
  const d = new Date(s.slice(0, 10) + 'T00:00:00Z');
  if (isNaN(d.getTime())) throw new TypeError('bad as_of date');
  return { kind: 'date', date: d };
}

function utcMidnight(d) {
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
}

function weekMonday(ts) {
  const p = parseAsOf(ts);
  const d = p.kind === 'datetime' ? p.instant : p.date;
  const mon = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() - ((d.getUTCDay() + 6) % 7)));
  return mon; // Date at Monday 00:00 UTC
}

function weekSunday(weekStart) {
  const mon = weekMonday(weekStart);
  return new Date(Date.UTC(mon.getUTCFullYear(), mon.getUTCMonth(), mon.getUTCDate() + 6));
}

function isWeekComplete(weekStart, asOf) {
  const mon = weekMonday(weekStart);
  const sunday = new Date(Date.UTC(mon.getUTCFullYear(), mon.getUTCMonth(), mon.getUTCDate() + 6));
  const nextMon = new Date(Date.UTC(mon.getUTCFullYear(), mon.getUTCMonth(), mon.getUTCDate() + 7));
  const p = parseAsOf(asOf);
  if (p.kind === 'date') return p.date.getTime() >= sunday.getTime();
  return p.instant.getTime() >= nextMon.getTime();
}

function floorAt(anchorDate, anchorLow, slopePerWeek, ds) {
  if (anchorDate == null || anchorLow == null || typeof slopePerWeek !== 'number' || ds == null) return null;
  const a = weekMonday(anchorDate);
  const d = weekMonday(ds);
  const w = Math.round((d - a) / (7 * 864e5));
  if (w < 0) return null;
  return anchorLow + slopePerWeek * w;
}

function floorAtPayload(j, ds) {
  if (!j || !j.anchor || typeof j.slopePerWeek !== 'number') return null;
  try {
    return floorAt(j.anchor.date, j.anchor.low, j.slopePerWeek, ds);
  } catch (e) {
    return null;
  }
}

/* Panel-compatible: floorAt(j, ds) */
function at(j, ds) { return floorAtPayload(j, ds); }

function weekBreaks(close, floor) {
  if (close == null || floor == null || floor === 0) return false;
  return close <= floor * BREAK_TOL;
}

function evaluateBreak(j, asOf) {
  const empty = {
    broken: false, lastCompletedWeek: null, lastCompletedSunday: null,
    lastCompletedClose: null, floorAtLastCompleted: null, pctAtLastCompleted: null,
    inProgressWeek: null, inProgressClose: null, inProgressPct: null,
    inProgressTriggersBreak: false, maxUnderPct: 0.0, floorNow: null,
    breakTrigger: null, asOfInput: null, dashInProgress: false, lineIsRed: false,
    inProgressWouldBreakIfCompleted: false
  };
  if (!j) return empty;
  const as_of = asOf != null ? asOf : j.asOf;
  if (as_of == null) throw new Error('as_of or j.asOf is required');
  const weeks = j.weeks || [];
  const completed = [];
  let inProg = null;
  let floorNow = null;
  for (let i = 0; i < weeks.length; i++) {
    const monS = weeks[i][0], close = Number(weeks[i][1]);
    const mon = weekMonday(monS);
    const fl = floorAtPayload(j, mon);
    if (fl != null) floorNow = fl;
    const pct = fl ? (close / fl - 1) * 100 : null;
    const rec = {
      monday: isoDate(mon),
      sunday: isoDate(new Date(Date.UTC(mon.getUTCFullYear(), mon.getUTCMonth(), mon.getUTCDate() + 6))),
      close: close,
      floor: fl,
      pct: pct,
      complete: isWeekComplete(mon, as_of)
    };
    rec.weekBreaks = !!(rec.complete && weekBreaks(close, fl));
    if (rec.complete) completed.push(rec);
    else inProg = rec;
  }
  const last = completed.length ? completed[completed.length - 1] : null;
  const unders = completed.filter(function (r) { return r.pct != null && r.pct < 0; }).map(function (r) { return r.pct; });
  const inWould = !!(inProg && weekBreaks(inProg.close, inProg.floor));
  const broken = completed.some(function (r) { return r.weekBreaks; });
  return {
    broken: broken,
    lastCompletedWeek: last ? last.monday : null,
    lastCompletedSunday: last ? last.sunday : null,
    lastCompletedClose: last ? last.close : null,
    floorAtLastCompleted: last && last.floor != null ? round2(last.floor) : null,
    pctAtLastCompleted: last && last.pct != null ? round1(last.pct) : null,
    inProgressWeek: inProg ? inProg.monday : null,
    inProgressClose: inProg ? inProg.close : null,
    inProgressPct: inProg && inProg.pct != null ? round1(inProg.pct) : null,
    inProgressTriggersBreak: false,
    inProgressWouldBreakIfCompleted: inWould,
    maxUnderPct: unders.length ? round2(Math.min.apply(null, unders)) : 0.0,
    floorNow: floorNow == null ? null : round2(floorNow),
    breakTrigger: last && last.floor != null ? round2(last.floor * BREAK_TOL) : null,
    asOfInput: typeof as_of === 'string' ? as_of : (as_of instanceof Date ? as_of.toISOString() : String(as_of)),
    dashInProgress: !!inProg,
    lineIsRed: broken
  };
}

function round2(x) { return Math.round(x * 100) / 100; }
function round1(x) { return Math.round(x * 10) / 10; }

function broken(j, asOf) {
  if (!j || !j.weeks || !j.anchor) return false;
  try { return evaluateBreak(j, asOf).broken; }
  catch (e) { return false; }
}

function display(j, asOf) {
  const ev = (j && j.weeks) ? evaluateBreak(j, asOf) : { broken: false, lastCompletedSunday: null };
  return {
    label: LABEL,
    asOf: ev.lastCompletedSunday || null,
    source: (j && j.source) != null ? j.source : null,
    breakRule: BREAK_RULE,
    brokenNote: ev.broken ? BROKEN_NOTE : null
  };
}

const api = {
  LABEL, BREAK_RULE, BROKEN_NOTE, BREAK_TOL,
  parseAsOf, weekMonday, weekSunday, isWeekComplete,
  floorAt, floorAtPayload, at, evaluateBreak, broken, display, isoDate
};

if (typeof module !== 'undefined' && module.exports) module.exports = api;
