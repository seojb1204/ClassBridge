import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync('static/js/components/week-calendar.js','utf8').replace(/^import .*;\n/gm,'').replace(/export /g,'');
const time=fs.readFileSync('static/js/time.js','utf8').replace(/export /g,'');
const nodes=[];
function h(tag,attrs={},...children){const n={tag,attrs,children:children.flat(),style:{},dataset:{},append(...x){this.children.push(...x)}};nodes.push(n);return n;}
const c={window:{matchMedia:()=>({matches:false})},h};
vm.runInNewContext(time+'\n'+source+'\nthis.render=renderCalendar',c);
const calls=[];
c.render({weekStart:'2026-11-16',slots:[],onTimeSelect:x=>calls.push(x)});
assert.equal(nodes.filter(n=>n.attrs.class?.startsWith('day-head')).length,5);
for(const n of nodes.filter(n=>n.attrs.class==='cell calendar-time-cell'))n.attrs.onclick({detail:0,currentTarget:{getBoundingClientRect:()=>({})}});
assert.equal(calls.length,25);
assert.ok(calls.every(x=>!['2026-11-21','2026-11-22'].includes(x.date)));
assert.equal(nodes.filter(n=>n.attrs.class==='legacy-weekend-events').length,0);
nodes.length=0;
const clicked=[];
const s={id:99,event_type:'lecture',title:'주말 강의',start_at:'2026-11-21T10:00:00+09:00',end_at:'2026-11-21T11:00:00+09:00'};
c.render({weekStart:'2026-11-16',slots:[s],onSlot:x=>clicked.push(x)});
const button=nodes.find(n=>n.attrs.dataset?.slotId===99);
assert.ok(button);assert.equal(button.attrs.class,'btn legacy-weekend-event');button.attrs.onclick();assert.equal(clicked[0],s);
console.log('7 weekday rendering, selection and legacy-access assertions passed');

// Minimum visible interval and expansion must not depend on booking count.
for (const [start,end,first,last] of [
  [null,null,'11:00','15:00'],
  ['13:00','13:30','11:00','15:00'],
  ['09:00','09:30','08:00','15:00'],
  ['16:00','17:30','11:00','18:00'],
]) {
  nodes.length=0;
  const slots=start ? [{id:1,start_at:`2026-11-16T${start}:00+09:00`,end_at:`2026-11-16T${end}:00+09:00`}] : [];
  c.render({weekStart:'2026-11-16',slots});
  const hours=nodes.filter(n=>n.attrs.class==='hour').map(n=>n.children[0]);
  assert.equal(hours[0],first);assert.equal(hours.at(-1),last);
  assert.ok(hours.includes('11:00') && hours.includes('15:00'));
}
console.log('4 minimum-hours and out-of-range schedule cases passed');
