// Deterministic handler replay only; does not emulate browser gesture arbitration.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const path = process.argv[2] || new URL('../static/js/components/week-calendar.js', import.meta.url);
const source = fs.readFileSync(path, 'utf8');
const fn = source.slice(source.indexOf('function enableWeekSwipe('), source.indexOf('\nfunction renderDaily'));
let count = 0;
function run({width, start, points, type='touch', cancel=false, reduced=false, second=false, elapsed=0}) {
  const calls=[], handlers={}, labels={};
  const hint={hidden:true,dataset:{},style:{},classList:{toggle(){}},querySelector(s){return labels[s] ||= {textContent:''}}};
  const wrap={classList:{add(){}},prepend(){},clientWidth:width,scrollTop:0,clientHeight:400,isConnected:true,
    getBoundingClientRect:()=>({left:24,right:24+width}), addEventListener(t,f){handlers[t]=f},setPointerCapture(){}};
  const grid={style:{}};
  let clock=0;
  const context={h:()=>hint,matchMedia:()=>({matches:reduced}),performance:{now:()=>clock},
    setTimeout:f=>f(),addDays:(d,n)=>n,wrap,grid,calls};
  vm.runInNewContext(fn+';enableWeekSwipe(wrap,grid,{weekStart:"2026-11-09",onWeekChange:d=>calls.push(d)})',context);
  const event=(x,y,other={})=>({pointerId:1,pointerType:type,isPrimary:true,clientX:24+start+x,clientY:100+y,...other});
  handlers.pointerdown(event(0,0));
  if (second) handlers.pointerdown(event(0,0,{pointerId:2,isPrimary:false}));
  clock=elapsed;
  for(const p of points) handlers.pointermove(event(...p));
  const ready=hint.dataset.ready, transform=grid.style.transform;
  handlers[cancel?'pointercancel':'pointerup'](event(...points.at(-1)));
  return {calls,ready,transform,hidden:hint.hidden,settled:grid.style.transform};
}
function check(options, expected, ready) {
 const r=run(options); assert.deepEqual(r.calls,expected,JSON.stringify(options));
 if(ready!==undefined)assert.equal(r.ready,ready);
 assert.equal(r.hidden,true); if (!expected.length) assert.ok(!r.settled);count++;
}
for(const width of [312,342]) for(const reduced of [false,true]) for(const sign of [-1,1]) {
 const edge=sign<0 ? width-25 : 25, center=width/2;
 const o={width,reduced,start:edge};
 const outcome=sign<0?7:-7;
 check({...o,points:[[sign*23,0],[sign*230,0]]},[outcome],'true');
 for(const d of [20,35,45]) check({...o,points:[[sign*d,0]]},[],'false');
 check({...o,points:[[sign*12,10],[sign*230,10]]},[outcome],'true');
 check({...o,points:[[sign*10,12],[sign*230,12]]},[outcome],'true');
 check({...o,points:[[sign*2,20],[sign*230,30]]},[]); // clear vertical lock
 check({...o,points:[[sign*230,0]],cancel:true},[],'true');
 check({...o,points:[[sign*230,0],[sign*45,0]]},[],'false');
 check({...o,points:[[sign*230,0]],type:'mouse'},[]);
 check({...o,points:[[sign*230,0]],second:true},[]);
 check({...o,start:center,points:[[sign*23,0],[sign*(center-5),0]]},[outcome],'true');
 check({...o,start:center,points:[[sign*45,0]]},[],'false');
 check({...o,points:[[sign*85,0]]},[outcome],'true');
 const r=run({...o,points:[[sign*150,0]]});
 if(reduced) assert.equal(r.transform,'');
 else assert.ok(r.transform.includes(`${sign*Math.min(150,width*.95)}px`));
 count++;
}
for(const sign of [-1,1]) {
 const o={width:342,start:171};
 check({...o,points:[[sign*25,0]],elapsed:50},[sign<0?7:-7],'true');
 check({...o,points:[[sign*24,0]],elapsed:20},[],'false');
 check({...o,points:[[sign*25,0]],elapsed:100},[],'false');
 check({...o,points:[[sign*50,0]],elapsed:1000},[sign<0?7:-7],'true');
 check({...o,points:[[sign*40,35]],elapsed:30},[]); // diagonal intent undecided
 check({...o,points:[[sign*25,0]],elapsed:50,cancel:true},[],'true');
}
console.log(`${count} handler checks passed (not browser/device validation)`);
