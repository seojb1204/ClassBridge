import { get } from '../api.js';
import { can, feature } from '../state.js';
import { todayKst } from '../time.js';
import { h } from '../ui.js';

export function staffToday() {
  const box = h('section', { class: 'panel staff-today', 'aria-label': '오늘 할 일' });
  async function draw() {
    const entries = [
      ['오늘 예약', '#/bookings/today', `/api/bookings?start=${todayKst()}&days=1&status=booked`, rows => rows.length],
    ];
    if (feature('suggestions') && can('suggestion:read'))
      entries.push(['새 건의', '#/suggestions', '/api/suggestions/stats', data => data.by_status.new || 0]);
    if (feature('surveys') && can('survey:manage'))
      entries.push(['진행 중 설문', '#/surveys', '/api/surveys', rows => rows.filter(s => s.status === 'published' &&
        (!s.opens_at || new Date(s.opens_at) <= new Date()) && (!s.closes_at || new Date(s.closes_at) > new Date())).length]);
    entries.push([can('support:manage') ? '미확인 문의' : '내 문의 새 답변',
      can('support:manage') ? '#/help/inbox' : '#/help/mine', '/api/support/counts',
      data => can('support:manage') ? data.inbox : data.mine]);
    const results = await Promise.allSettled(entries.map(async ([label, href, url, count]) =>
      ({ label, href, count: count(await get(url)) })));
    const failed = results.some(r => r.status === 'rejected');
    const active = results.filter(r => r.status === 'fulfilled' && r.value.count > 0).map(r => r.value);
    const links = active.map(({label, href, count}) => h('a', { class: 'btn small', href }, `${label} ${count}건`));
    box.replaceChildren(h('div', { class: 'staff-today-summary' },
      h('span', {}, failed ? '일부 항목 확인 필요' : active.length ? '오늘 할 일' : '오늘 확인할 항목 없음'),
      ...links,
      h('button', { class: 'btn small', onclick: draw, 'aria-label': '오늘 할 일 다시 확인' }, '갱신')));
    if (failed) box.append(h('details', {}, h('summary', {}, '확인하지 못한 항목'),
      ...results.flatMap((result, i) => result.status === 'rejected'
        ? [h('p', {class: 'muted'}, `${entries[i][0]} · 확인 불가`)] : [])));

  }
  box.append(h('p', {}, '오늘 할 일 불러오는 중…'));
  draw();
  return box;
}
