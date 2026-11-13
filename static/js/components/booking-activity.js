import { get } from '../api.js';
import { fmtDateTime } from '../time.js';
import { field, h, select } from '../ui.js';

export const eventLabels = {
  book: '학생 예약 신청', book_by_staff: '대리 예약', cancel: '학생 예약 취소',
  cancel_by_staff: '교수자·관리자 예약 취소', cancel_by_slot: '상담 시간 취소로 예약 취소',
  rescheduled_from: '일정 변경 · 이전 예약', rescheduled_to: '일정 변경 · 새 예약',
  slot_changed: '상담 시간 정보 수정', completed: '상담 완료 처리', no_show: '미참석 처리',
  note_update: '상담 기록 수정',
};

export function bookingActivity() {
  const box = h('section', { class: 'panel booking-activity', 'aria-label': '예약 활동 기록' });
  const filter = select([['all', '전체 활동'], ['cancel', '예약 취소'], ['change', '일정 변경']], 'all');
  const list = h('div', { class: 'cards' });
  const status = h('p', { class: 'muted', role: 'status' });
  let cursor = null, generation = 0, loading = false;
  const more = h('button', { class: 'btn', hidden: true, onclick: () => load(false) }, '이전 기록 더 보기');
  const refresh = h('button', { class: 'btn small', onclick: () => load(true) }, '기록 새로고침');
  async function load(reset) {
    if (!reset && loading) return;
    const version = ++generation;
    loading = true;
    more.disabled = true;
    status.textContent = '기록을 불러오는 중…';
    if (reset) { cursor = null; list.replaceChildren(); more.hidden = true; }
    try {
      const params = new URLSearchParams({ kind: filter.value, limit: '30' });
      if (cursor) params.set('before_id', cursor);
      const data = await get(`/api/staff/booking-events?${params}`);
      if (version !== generation) return;
      list.append(...data.items.map(item => h('article', { class: 'card', dataset: { eventId: item.id } },
        h('strong', {}, eventLabels[item.action] || item.action),
        h('p', {}, `학생: ${item.student_name} · 예약 #${item.booking_id}`),
        h('p', {}, `처리자: ${item.actor_name} (${item.actor_is_student ? '예약 학생 본인' : '교수자·관리자'})`),
        h('p', {}, '처리 시각: ' + new Date(item.at).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', hour12: false })),
        h('p', {}, `상담 일시: ${fmtDateTime(item.start_at)} · 현재 상태: ${{expired: "기간 종료·결과 미확인", booked:'예약됨',cancelled:'취소됨',completed:'완료',no_show:'미참석'}[item.status] || item.status}`),
        item.detail ? h('p', {}, `기록 내용: ${item.detail}`) : null)));
      cursor = data.next_before_id;
      more.hidden = !cursor;
      status.textContent = list.children.length ? `${list.children.length}건 표시 · 최신 기록부터` : '해당 예약 활동 기록이 없습니다.';
    } catch {
      if (version === generation) status.textContent = '기록을 불러오지 못했습니다. 새로고침하거나 이전 기록 조회를 다시 시도하세요.';
    } finally {
      if (version === generation) { loading = false; more.disabled = false; }
    }
  }
  filter.addEventListener('change', () => load(true));
  box.append(h('h2', {}, '예약 활동 기록'),
    h('p', { class: 'hint' }, '학생의 취소도 보존됩니다. 일정 변경은 단순 취소와 구분됩니다. 처리 시각은 한국시간이며, 이름·상담 일시는 현재 저장된 정보입니다.'),
    h('div', { class: 'filters' }, field('활동 종류', filter), refresh), status, list, more);
  load(true);
  return box;
}
