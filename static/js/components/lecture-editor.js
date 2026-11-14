import { get, post, patch } from '../api.js';
import { h, field, modal, errorToast, select, busy, toast } from '../ui.js';
import { kstParts, todayKst } from '../time.js';

export function loadLectures(start) { return get(`/api/lectures?start=${start}&days=7`); }
function editorFields(refresh, row = null, seed = null) {
  const a = row ? kstParts(row.start_at) : null, b = row ? kstParts(row.end_at) : null;
  const title = h('input', { value: row?.title || '', maxlength: 120, required: true });
  const location = h('input', { value: row?.location || '', maxlength: 200 });
  const date = h('input', { type: 'date', value: a?.date || seed?.date || todayKst(), required: true });
  const start = h('input', { type: 'time', value: a?.time || seed?.start || '09:00', required: true });
  const end = h('input', { type: 'time', value: b?.time || seed?.end || '10:00', required: true });
  const weeks = h('input', { type: 'number', min: 1, max: 26, value: 1 });
  const cancelScope = select([['once', '이번 강의만'], ['series', '반복 강의 전체']]);
  const body = h('div', {}, field('강의명', title), field('날짜', date),
    field('시작 (한국 시간)', start), field('종료 (한국 시간)', end), field('강의실 (선택)', location),
    row ? h('p', { class: 'muted' }, '수정은 이번 강의에만 적용됩니다.') : field('같은 요일로 총 몇 주', weeks, '이번 주 포함 · 1~26주'),
    h('p', { class: 'notice' }, '강의는 상담과 같은 시간표에 표시됩니다. 강의 시간에는 새 상담 예약이 차단됩니다. 기존 예약과 겹치는 강의는 저장되지 않습니다.'),
    row ? field('삭제 범위', cancelScope) : null);
  const save = async () => {
    try {
      if (!title.reportValidity() || !date.reportValidity() || !start.reportValidity() || !end.reportValidity() || !weeks.reportValidity()) return false;
      const value = { title: title.value, location: location.value, date: date.value, start_time: start.value, end_time: end.value, weeks: row ? 1 : Number(weeks.value) };
      await (row ? patch(`/api/lectures/${row.id}`, value) : post('/api/lectures', value));
      await refresh(value); return true;
    } catch (e) { errorToast(e); return false; }
  };
  return { body, save, cancelScope };
}

export function lectureCreateForm(refresh, seed = null) {
  const { body, save } = editorFields(refresh, null, seed);
  const button = h('button', { class: 'btn primary', type: 'submit' }, '강의 저장');
  const form = h('form', { class: 'lecture-create-form' }, body, button);
  form.addEventListener('submit', busy(button, async (event) => {
    event.preventDefault();
    if (await save()) toast('강의를 시간표에 등록했습니다.', 'success');
  }));
  return form;
}

export async function lectureEditor(refresh, row = null) {
  const { body, save, cancelScope } = editorFields(refresh, row);
  const actions = [{ label: '닫기', value: null }, { label: '강의 저장', primary: true, handler: save }];
  // Close the editor before opening confirmation: the shared modal has one root.
  if (row) actions.push({ label: '강의 삭제', danger: true, value: 'delete' });
  const result = await modal(row ? '강의 수정' : '강의 추가', body, actions);
  if (result !== 'delete') return result;
  return modal('강의 삭제', h('p', {}, cancelScope.value === 'series'
    ? '이 반복 강의 전체를 시간표에서 지울까요? 상담 예약은 유지됩니다.' : '이번 강의를 시간표에서 지울까요?'), [
    { label: '아니오', value: false },
    { label: '예, 삭제', danger: true, handler: async () => {
      try {
        await post(`/api/lectures/${row.id}/cancel?series=${cancelScope.value === 'series'}`, {});
        await refresh(); return true;
      } catch (e) { errorToast(e); return false; }
    } },
  ]);
}
