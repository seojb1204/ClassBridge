import { loadLectures, lectureEditor } from "../components/lecture-editor.js";
import { schedulePreview } from "../components/schedule-preview.js";
import { availableDaysPanel, loadAvailableDays } from "../components/available-days.js";
import { parseDate, parseSchedule, parseTime, timeLabel } from "../schedule-input.js";
// 교수자·관리자: 등록된 상담 시간으로 예약 가능 여부 관리
import { del, get, patch, post } from "../api.js";
import { announcementPanel, loadAnnouncement } from "../components/announcement.js";
import { isMobile, onLayoutChange, renderCalendar, revealSelectedDay, weekNav } from "../components/week-calendar.js";
import { addDays, fmtDateTime, isoToKstInput, kstInputToIso, kstParts, mondayOf, todayKst } from "../time.js";
import { busy, confirmAction, errorToast, field, h, modal, mount, promptText, select, toast } from "../ui.js";

let weekStart = null;
let selectedDay = null;
let detach = null;
let drawVersion = 0;
let showForm = null;
let showCancelled = false;

let revealCreated = false;

export function renderRegistration(root) {
  mount(root, h("h1", {}, "상담 시간 등록"), h("section", { class: "panel", id: "slot-create-panel" }, createForm(root)));
}

export async function render(root) {
  weekStart ||= mondayOf(todayKst());
  selectedDay ||= todayKst();
  if (showForm === null) {
    showForm = !isMobile();
    if (isMobile()) {
      const upcoming = await get(`/api/slots?start=${todayKst()}&days=30`);
      const first = upcoming.find((slot) => slot.status === "open");
      if (first) {
        selectedDay = kstParts(first.start_at).date;
        weekStart = mondayOf(selectedDay);
      }
    }
  }
  detach?.();
  detach = onLayoutChange(() => draw(root));
  const reveal = revealCreated;
  revealCreated = false;
  await draw(root, reveal);
}

async function draw(root, revealDay = false) {
  if (location.hash !== "#/slots") return;
  const version = ++drawVersion, path = location.hash;
  const [slots, announcement, availableDays, lectures] = await Promise.all([
    get(`/api/slots?start=${weekStart}&days=7`), loadAnnouncement(), loadAvailableDays(), loadLectures(weekStart),
  ]);
  if (version !== drawVersion || location.hash !== path) return;
  mount(root,
    h("div", { class: "page-head" }, h("h1", {}, "상담 시간 관리"),
      isMobile() ? null : h("button", { class: "btn primary", onclick: () => { showForm = !showForm; draw(root); },
        "aria-expanded": String(showForm), "aria-controls": "slot-create-panel" },
        showForm ? "등록 양식 접기" : "+ 상담 시간 등록")),
    h("p", { class: "muted" }, "등록된 상담 시간만 예약할 수 있습니다. 시간을 누르면 수정하거나 취소할 수 있습니다."),
    announcementPanel(announcement, () => draw(root)),
    availableDaysPanel(availableDays, (day) => { weekStart = mondayOf(day); selectedDay = day; draw(root, true); }),
    h("button", { class: "btn", onclick: () => lectureEditor(() => draw(root)) }, "+ 강의 추가"),
    weekNav(weekStart, (w) => { weekStart = w; selectedDay = w; draw(root); }),
    h("label", { class: "check" }, h("input", { type: "checkbox", checked: showCancelled,
      onchange: (e) => { showCancelled = e.target.checked; draw(root); } }), "취소된 상담 시간 보기"),
    renderCalendar({ weekStart, slots: [...(showCancelled ? slots : slots.filter(s => s.status !== "cancelled")), ...lectures].sort((a,b) => a.start_at.localeCompare(b.start_at)), selectedDay, mobileListOnly: true,
      onDay: (d) => { selectedDay = d; draw(root, true); },
      onSlot: (s) => s.event_type === "lecture" ? lectureEditor(() => draw(root), s) : editSlot(root, s),
      extra: (s) => s.event_type === "lecture" ? null : (s.status === "open" ? h("span", { class: "slot-count" }, `${s.capacity - s.remaining}/${s.capacity}명`)
        : s.can_delete ? h("span", { class: "slot-count" }, "눌러서 빈 시간 삭제") : null) }),
    showForm && !isMobile() ? h("section", { class: "panel", id: "slot-create-panel" },
      h("h2", {}, "상담 시간 등록"), createForm(root)) : null,
  );
  if (revealDay) revealSelectedDay(root);
}

function createForm(root) {
  const date = h("input", { type: "text", placeholder: "예: 11월 20일", required: true, value: addDays(todayKst(), 1) });
  const start = h("input", { type: "text", placeholder: "예: 10 00", required: true, value: "10:00" });
  const end = h("input", { type: "text", placeholder: "예: 3시", required: true, value: "12:00" });
  const dur = h("input", { type: "number", min: 5, max: 240, value: 30 });
  const brk = h("input", { type: "number", min: 0, max: 120, value: 0 });
  const kind = select([["individual", "개인 상담"], ["group", "단체 상담"]], "individual");
  kind.setAttribute("aria-label", "유형");
  const cap = h("input", { type: "number", min: 1, max: 100, value: 1, disabled: true });
  kind.addEventListener("change", () => {
    cap.disabled = kind.value === "individual";
    cap.value = kind.value === "individual" ? 1 : Math.max(2, +cap.value);
  });
  const weeks = h("input", { type: "number", min: 1, max: 26, value: 1 });
  const repeat = select([["once", "이번 날짜만"], ["weekly", "같은 일정으로 매주 등록"]], "once");
  repeat.setAttribute("aria-label", "반복 방식");
  weeks.setAttribute("aria-label", "총 몇 주");
  const repeatWeeks = field("총 몇 주", weeks, "이번 날짜 포함 · 같은 요일과 시간 · 최대 26주");
  repeatWeeks.hidden = true;
  repeat.addEventListener("change", () => { repeatWeeks.hidden = repeat.value !== "weekly"; });
  const sentence = h("input", { type: "text", placeholder: "예: 11월 20일 3시~6시", maxlength: 100 });
  const interpreted = h("p", { class: "notice", role: "status" }, "8~11시는 오전, 12시는 낮, 1~6시는 오후로 해석합니다.");
  const readInputs = () => {
    const parsed = { date: parseDate(date.value, todayKst()), start: parseTime(start.value), end: parseTime(end.value) };
    if (parsed.end <= parsed.start) throw new Error("종료 시간은 시작 시간보다 늦어야 합니다.");
    return parsed;
  };
  const describe = (v) => `${v.date} · ${timeLabel(v.start)}~${timeLabel(v.end)}`;
  for (const input of [date, start, end]) input.addEventListener("blur", () => {
    try { interpreted.textContent = describe(readInputs()); }
    catch (error) { interpreted.textContent = error.message; }
  });
  const applySentence = h("button", { class: "btn", type: "button", onclick: () => {
    try {
      const parsed = parseSchedule(sentence.value, todayKst());
      date.value = parsed.date; start.value = parsed.start; end.value = parsed.end;
      interpreted.textContent = `${describe(parsed)} · 아래 설정을 확인하고 미리보기를 눌러 주세요.`;
    } catch (error) { interpreted.textContent = error.message; errorToast(error); }
  } }, "입력 내용 적용");
  const loc = h("input", { type: "text", maxlength: 200, value: "m205", placeholder: "예: m205" });
  const btn = h("button", { class: "btn primary", type: "submit" }, "등록 미리보기");
  const form = h("form", { class: "grid-form" },
    h("div", { class: "field wide" }, field("한 문장으로 입력", sentence), applySentence, interpreted),
    field("날짜(시작일)", date), field("시작", start), field("종료", end),
    field("1회 시간(분)", dur), field("휴식(분)", brk), field("유형", kind), field("정원", cap),
    field("반복 방식", repeat), repeatWeeks,
    field("장소", loc), h("div", { class: "field wide" }, btn));
  form.addEventListener("submit", busy(btn, async (e) => {
    e.preventDefault();
    try {
      const parsed = readInputs();
      interpreted.textContent = describe(parsed);
      const spec = {
        start_date: parsed.date, start_time: parsed.start, end_time: parsed.end, duration_minutes: +dur.value,
        break_minutes: +brk.value, kind: kind.value, capacity: +cap.value, repeat_weeks: repeat.value === "weekly" ? +weeks.value : 1,
        weekdays: null, location: loc.value,
      };
      const preview = await post("/api/slots/preview", spec);
      const warning = preview.protected_ids.length;
      const confirmed = await modal("상담 시간 등록 미리보기", h("div", { class: "schedule-preview-body" },
        h("p", {}, describe(parsed)),
        h("p", {}, `${dur.value}분씩 · 휴식 ${brk.value}분 · 장소 ${loc.value || "미지정"}`),
        h("p", {}, `생성할 새 상담 ${preview.created}건`),
        h("p", {}, `겹치는 기존 상담 ${preview.replaced}건`),
        schedulePreview(preview.planned_slots),
        warning ? h("p", { class: "warn" }, `예약된 상담 ${warning}건이 있어 자동 교체할 수 없습니다.`) : null,
        preview.replaced && !warning
          ? h("p", {}, "기존 미예약 상담을 취소 상태로 보존한 뒤 새 상담으로 교체합니다.") : null), [
        { label: "돌아가기", value: false },
        ...(warning ? [] : [{ label: preview.replaced ? "미예약 상담 교체·등록" : "등록 확정",
          primary: true, value: true }]),
      ]);
      if (!confirmed) return;
      const r = preview.replaced
        ? await post("/api/slots/replace", { ...spec, expected_overlap_ids: preview.overlap_ids })
        : await post("/api/slots", spec);
      toast(`${r.created}개 등록${r.replaced ? ` · 기존 미예약 상담 ${r.replaced}개 교체` : ""}`, "success");
      weekStart = mondayOf(parsed.date);
      selectedDay = parsed.date;
      showForm = false;
      if (location.hash === "#/slots/new") {
        revealCreated = true;
        location.hash = "#/slots";
        return;
      }
      await draw(root, true);
      if (!isMobile()) {
        const calendar = root.querySelector(".week-grid");
        if (calendar) {
          calendar.tabIndex = -1;
          calendar.focus({ preventScroll: true });
          calendar.scrollIntoView({ block: "start", behavior: "instant" });
        }
      }
    } catch (err) { errorToast(err); }
  }));
  return form;
}

async function editSlot(root, s) {
  if (s.status === "cancelled") {
    if (!s.can_delete) { toast("예약 이력이 있거나 다른 교수자가 등록한 시간입니다. 삭제하지 않고 보관합니다."); return; }
    if (!(await confirmAction("빈 상담 시간 삭제", `${fmtDateTime(s.start_at)}의 취소된 빈 시간을 영구 삭제할까요? 예약 이력은 없으며 삭제 후 복원할 수 없습니다.`, "삭제", true))) return;
    try { await del(`/api/slots/${s.id}`); await draw(root); toast("빈 상담 시간을 삭제했습니다", "success"); }
    catch (error) { errorToast(error); }
    return;
  }
  const cap = h("input", { type: "number", min: 1, max: 100, value: s.capacity, disabled: s.kind === "individual" });
  const kind = select([["individual", "개인"], ["group", "단체"]], s.kind);
  kind.addEventListener("change", () => {
    cap.disabled = kind.value === "individual";
    cap.value = kind.value === "individual" ? 1 : Math.max(2, +cap.value);
  });
  const loc = h("input", { type: "text", value: s.location, maxlength: 200 });
  const note = h("input", { type: "text", value: s.note, maxlength: 500 });
  const booked = s.capacity - s.remaining;
  const startAt = h("input", { type: "datetime-local", value: isoToKstInput(s.start_at), disabled: booked > 0 });
  const endAt = h("input", { type: "datetime-local", value: isoToKstInput(s.end_at), disabled: booked > 0 });
  const r = await modal("상담 시간 수정", h("div", {},
    h("p", {}, h("strong", {}, fmtDateTime(s.start_at)), ` · 예약 ${booked}명`),
    booked ? h("p", { class: "warn" }, "예약자가 있는 상담은 시작·종료 시각을 변경할 수 없습니다.") : null,
    field("시작 시각 (한국시간)", startAt), field("종료 시각 (한국시간)", endAt),
    field("유형", kind), field("정원", cap), field("장소", loc), field("안내", note)), [
    { label: "닫기", value: null },
    { label: "이 시간 취소", danger: true, value: "cancel" },
    { label: "저장", primary: true, handler: async () => {
      try {
        await patch(`/api/slots/${s.id}`, { kind: kind.value, capacity: +cap.value,
          location: loc.value, note: note.value,
          ...(booked ? {} : { start_at: kstInputToIso(startAt.value), end_at: kstInputToIso(endAt.value) }) });
        toast("저장했습니다", "success");
        return true;
      } catch (e) { errorToast(e); return false; }
    } },
  ]);
  if (r === "cancel") {
    let reason = "";
    if (booked > 0) {
      reason = await promptText("상담 시간 취소", `예약된 학생 ${booked}명의 예약도 함께 취소됩니다. 사유를 입력하세요.`, { required: true });
      if (reason === null) return;
    } else if (!(await confirmAction("상담 시간 취소", "이 상담 시간을 취소할까요?", "취소하기", true))) return;
    try {
      const res = await post(`/api/slots/${s.id}/cancel`, { force: booked > 0, reason });
      toast(`취소했습니다${res.cancelled_bookings ? ` (예약 ${res.cancelled_bookings}건 취소)` : ""}`, "success");
    } catch (e) { errorToast(e); }
  }
  const reveal = revealCreated;
  revealCreated = false;
  await draw(root, reveal);
}
