import { get } from '../api.js';
import { can, feature } from '../state.js';
import { todayKst } from '../time.js';
import { h } from '../ui.js';

export function staffToday() {
  const box = h('section', { class: 'panel staff-today', 'aria-label': '오늘 할 일' });
  async function draw() {
    const entries = [
      ['오늘 예약', '#/bookings', `/api/bookings?start=${todayKst()}&days=1&status=booked`, rows => rows.length],
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
      h('a', { class: 'btn', href }, `${label} ${count(await get(url))}건`)));
    box.replaceChildren(h('div', { class: 'page-head' }, h('h2', {}, '오늘 할 일'),
      h('button', { class: 'btn small', onclick: draw }, '요약 새로고침')),
      h('p', { class: 'hint' }, `${todayKst()} · 한국시간 · 오늘 예약을 누르면 전체 예약 관리로 이동합니다.`),
      h('div', { class: 'actions' }, ...results.map((r, i) => r.status === 'fulfilled' ? r.value :
        h('span', { class: 'muted' }, `${entries[i][0]} · 확인 불가`))));
  }
  box.append(h('p', {}, '오늘 할 일 불러오는 중…'));
  draw();
  return box;
}
