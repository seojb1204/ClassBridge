// Run: node scripts/test-calendar-cache.mjs
import assert from 'node:assert/strict';
import { calendarGet, clearCalendarCache, setCsrf, post } from '../static/js/api.js';
let calls = 0, fail = false;
globalThis.fetch = async () => {
  calls++;
  if (fail) throw new Error('offline');
  return { ok: true, status: 200, json: async () => ({ call: calls }) };
};
const path = '/api/bookings?start=2026-11-16&days=7';
const [a, b] = await Promise.all([calendarGet(path), calendarGet(path)]);
assert.equal(calls, 1); assert.deepEqual(a, b);
await calendarGet(path); assert.equal(calls, 1);
await post('/api/bookings/1/cancel');
await calendarGet(path); assert.equal(calls, 3);
setCsrf('new-session'); await calendarGet(path); assert.equal(calls, 4);
clearCalendarCache(); fail = true;
await assert.rejects(calendarGet(path));
fail = false; await calendarGet(path); assert.equal(calls, 6);
const before = calls; const realNow = Date.now;
Date.now = () => realNow() + 16000;
await calendarGet(path); assert.equal(calls, before + 1); Date.now = realNow;
// In-flight response from before invalidation must not re-populate the cache.
clearCalendarCache(); let release;
globalThis.fetch = () => new Promise(resolve => { release = () => resolve({ ok: true, status: 200, json: async () => ['old'] }); });
const pending = calendarGet(path);
clearCalendarCache();
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ['new'] });
release(); assert.deepEqual(await pending, ['new']);
assert.deepEqual(await calendarGet(path), ['new']);
console.log('calendar cache: dedupe, reuse, writes, auth, error, expiry and in-flight invalidation passed');
