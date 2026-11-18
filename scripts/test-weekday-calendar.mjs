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

vm.runInNewContext('this.prioritize=consultationFirstEvents',c);
const lecture={id:10,event_type:'lecture',start_at:'2026-11-16T11:00:00+09:00',end_at:'2026-11-16T15:00:00+09:00'};
const consult=(start,end,status='open')=>({id:20,start_at:`2026-11-16T${start}:00+09:00`,end_at:`2026-11-16T${end}:00+09:00`,status});
for(const [cuts,expected] of [
  [[],[['11:00','15:00']]],
  [[consult('12:00','13:00')],[['11:00','12:00'],['13:00','15:00']]],
  [[consult('10:00','16:00')],[]],
  [[consult('10:00','11:00'),consult('15:00','16:00')],[['11:00','15:00']]],
  [[consult('12:00','14:00'),consult('13:00','14:30')],[['11:00','12:00'],['14:30','15:00']]],
  [[consult('12:00','13:00','cancelled')],[['11:00','15:00']]],
  [[consult('10:00','12:00')],[['12:00','15:00']]],
  [[consult('14:00','16:00')],[['11:00','14:00']]],
]) {
  const input=[lecture,...cuts],before=JSON.stringify(input);
  const output=c.prioritize(input).filter(s=>s.event_type==='lecture');
  const times=output.map(s=>[new Date(Date.parse(s.start_at)+9*3600000).toISOString().slice(11,16),new Date(Date.parse(s.end_at)+9*3600000).toISOString().slice(11,16)]);
  assert.equal(JSON.stringify(times),JSON.stringify(expected));
  assert.equal(JSON.stringify(input),before);
  for(const part of output)assert.equal(part.originalSlot||part,lecture);
}
console.log('8 consultation priority, boundary, cancellation and immutable-source cases passed');
