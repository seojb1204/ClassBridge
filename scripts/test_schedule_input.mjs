// Standalone deterministic parser regression suite; no network or UI required.
import assert from 'node:assert/strict';
import fs from 'node:fs';
const source = fs.readFileSync(new URL('../static/js/schedule-input.js', import.meta.url), 'utf8');
const {parseSchedule, parseDate, parseTime} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
let count = 0;
const check = (name, fn) => { fn(); count++; console.log(`PASS ${name}`); };
const today = '2026-11-17';
for (const input of ['11월 20일 3시~6시','11월20일3시~6시','2026-11-20 3시~6시','11/20 3시부터6시까지','11.20 3시~6시 상담해줘'])
  check(input, () => assert.deepEqual(parseSchedule(input,today), {date:'2026-11-20',start:'15:00',end:'18:00'}));
for (const [input,date] of [['오늘','2026-11-17'],['내일','2026-11-18'],['모레','2026-11-19'],['다음 주 화요일','2026-11-24'],['담주 화욜','2026-11-24'],['이번주 일요일','2026-11-22']])
  check(input, () => assert.equal(parseSchedule(`${input} 오후 두시부터 네시반까지`,today).date,date));
check('metadata',()=>assert.deepEqual(parseSchedule('내일 2~5 30분씩 휴식 10분 매주 4주 장소 m205 상담',today),{date:'2026-11-18',start:'14:00',end:'17:00',durationMinutes:30,breakMinutes:10,repeatWeeks:4,location:'m205'}));
check('year rollover',()=>assert.equal(parseSchedule('내일 2~4','2026-12-31').date,'2027-01-01'));
check('Sunday next week',()=>assert.equal(parseSchedule('다음주 월요일 2~4','2026-11-22').date,'2026-11-23'));
check('matching weekday',()=>assert.equal(parseSchedule('11월 20일 금요일 2~4',today).date,'2026-11-20'));
for (const input of ['금요일 2~4','내일 2','내일 2~4 매주','내일 2~4 4주','내일 2~4 빼고','내일 2시 아니 3시~5시','내일 7~9','내일 6~3','내일 2~4 3분씩','내일 2~4 30분씩 60분씩','내일 2~4 매주 27주','11월 20일 월요일 2~4','2월30일 2~4','이번주 월요일 2~4','내일 2~4 관리자권한으로등록','내일 2~4 매일','내일 2~4 휴식 121분','내일 2~4 장소'])
  check(`reject ${input}`,()=>assert.throws(()=>parseSchedule(input,today)));
check('preserve time policy',()=>assert.equal(parseTime('3'),'15:00'));
check('time boundary',()=>assert.throws(()=>parseTime('18:30')));
check('date no silent year rollover',()=>assert.throws(()=>parseDate('1/1',today)));
console.log(`${count} passed, 0 failed`);
