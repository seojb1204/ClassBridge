import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source = fs.readFileSync(new URL('../static/js/components/calendar-scroll.js', import.meta.url), 'utf8')
  .replace(/import[^\n]+\n/, '').replace('export function', 'function');
let cases = 0;
function scenario({ existing = true, fail = false } = {}) {
  const oldInner = { scrollTop: 125 }, newInner = { scrollTop: 0 };
  let mounted = false;
  const root = { style: { minHeight: '3px' }, getBoundingClientRect: () => ({ height: 1100 }),
    querySelector: sel => sel === '.week-nav' ? existing : mounted ? newInner : oldInner };
  const calls = [];
  const window = { scrollX: 0, scrollY: 240, scrollTo: p => calls.push(p) };
  const context = { window, mount: () => { mounted = true; } };
  vm.createContext(context); vm.runInContext(source, context);
  const build = () => {
    if (existing) assert.equal(root.style.minHeight, '1100px');
    if (fail) throw new Error('build failed');
    return [];
  };
  if (fail) assert.throws(() => context.mountCalendarPreservingScroll(root, build));
  else context.mountCalendarPreservingScroll(root, build);
  assert.equal(root.style.minHeight, '3px');
  if (existing && !fail) { assert.equal(newInner.scrollTop, 125); assert.equal(calls.at(-1).top, 240); }
  if (!existing || fail) assert.equal(calls.length, 0);
  cases++;
}
scenario(); scenario({ existing: false }); scenario({ fail: true });
console.log(`${cases} calendar scroll unit scenarios passed (not browser validation)`);
