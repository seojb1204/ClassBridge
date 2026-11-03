// 교수자·관리자: 상담 시간 등록·수정·취소, 상담 불가일
import { del, get, patch, post } from "../api.js";
import { onLayoutChange, renderCalendar, weekNav } from "../components/week-calendar.js";
import { addDays, fmtDate, fmtDateTime, mondayOf, todayKst } from "../time.js";
import { busy, confirmAction, errorToast, field, h, modal, mount, promptText, select, toast } from "../ui.js";

let weekStart = null;
let selectedDay = null;
let detach = null;
const WD = ["월", "화", "수", "목", "금", "토", "일"];

export async function render(root) {
  weekStart ||= mondayOf(todayKst());
  selectedDay ||= todayKst();
  detach?.();
  detach = onLayoutChange(() => draw(root));
  await draw(root);
}

async function draw(root) {
  const [slots, blackouts] = await Promise.all([get(`/api/slots?start=${weekStart}&days=7`), get("/api/blackouts")]);
  mount(root,
    h("div", { class: "page-head" }, h("h1", {}, "상담 시간 관리")),
    h("div", { class: "split" },
      h("section", { class: "panel" }, h("h2", {}, "상담 시간 등록"), createForm(root)),
      h("section", { class: "panel" }, h("h2", {}, "상담 불가일"), blackoutPanel(root, blackouts))),
    weekNav(weekStart, (w) => { weekStart = w; selectedDay = w; draw(root); }),
    renderCalendar({ weekStart, slots, selectedDay, onDay: (d) => { selectedDay = d; draw(root); },
      onSlot: (s) => editSlot(root, s),
      extra: (s) => (s.status === "open" ? h("span", { class: "slot-count" }, `${s.capacity - s.remaining}/${s.capacity}명`) : null) }),
  );
}

function createForm(root) {
  const date = h("input", { type: "date", required: true, value: addDays(todayKst(), 1) });
  const start = h("input", { type: "time", required: true, value: "10:00" });
  const end = h("input", { type: "time", required: true, value: "12:00" });
  const dur = h("input", { type: "number", min: 5, max: 240, value: 30 });
  const brk = h("input", { type: "number", min: 0, max: 120, value: 0 });
  const kind = select([["individual", "개인 상담"], ["group", "단체 상담"]], "individual");
  const cap = h("input", { type: "number", min: 1, max: 100, value: 1, disabled: true });
  kind.addEventListener("change", () => {
    cap.disabled = kind.value === "individual";
    cap.value = kind.value === "individual" ? 1 : Math.max(2, +cap.value);
  });
  const weeks = h("input", { type: "number", min: 1, max: 26, value: 1 });
  const wdBoxes = WD.map((w, i) => h("label", { class: "check" }, h("input", { type: "checkbox", value: i }), w));
  const loc = h("input", { type: "text", maxlength: 200, placeholder: "예: 공학관 512호" });
  const btn = h("button", { class: "btn primary", type: "submit" }, "등록");
  const form = h("form", { class: "grid-form" },
    field("날짜(시작일)", date), field("시작", start), field("종료", end),
    field("1회 시간(분)", dur), field("휴식(분)", brk), field("유형", kind), field("정원", cap),
    field("반복(주)", weeks, "1이면 반복 없음"),
    h("div", { class: "field wide" }, h("span", { class: "label" }, "반복 요일 (선택 안 하면 시작일 요일)"),
      h("div", { class: "checks" }, wdBoxes)),
    field("장소", loc), h("div", { class: "field wide" }, btn));
  form.addEventListener("submit", busy(btn, async (e) => {
    e.preventDefault();
    const weekdays = wdBoxes.map((l) => l.firstChild).filter((c) => c.checked).map((c) => +c.value);
    try {
      const r = await post("/api/slots", {
        start_date: date.value, start_time: start.value, end_time: end.value, duration_minutes: +dur.value,
        break_minutes: +brk.value, kind: kind.value, capacity: +cap.value, repeat_weeks: +weeks.value,
        weekdays: weekdays.length ? weekdays : null, location: loc.value,
      });
      toast(`${r.created}개 등록${r.skipped_blackout_days.length ? ` (상담 불가일 ${r.skipped_blackout_days.length}일 제외)` : ""}`, "success");
      weekStart = mondayOf(date.value);
      selectedDay = date.value;
      await draw(root);
    } catch (err) { errorToast(err); }
  }));
  return form;
}

function blackoutPanel(root, list) {
  const day = h("input", { type: "date", required: true });
  const reason = h("input", { type: "text", maxlength: 200, placeholder: "사유 (선택)" });
  const btn = h("button", { class: "btn", type: "submit" }, "추가");
  const form = h("form", { class: "inline-form" }, day, reason, btn);
  form.addEventListener("submit", busy(btn, async (e) => {
    e.preventDefault();
    try { await post("/api/blackouts", { day: day.value, reason: reason.value }); toast("등록했습니다", "success"); await draw(root); }
    catch (err) { errorToast(err); }
  }));
  const upcoming = list.filter((b) => b.day >= todayKst());
  return h("div", {}, form, h("ul", { class: "plain" }, upcoming.map((b) => h("li", {},
    `${fmtDate(b.day)} ${b.reason ? `· ${b.reason}` : ""} `,
    h("button", { class: "link danger", onclick: async () => {
      try { await del(`/api/blackouts/${b.id}`); await draw(root); } catch (err) { errorToast(err); }
    } }, "삭제")))));
}

async function editSlot(root, s) {
  if (s.status === "cancelled") { toast("취소된 상담 시간입니다"); return; }
  const cap = h("input", { type: "number", min: 1, max: 100, value: s.capacity, disabled: s.kind === "individual" });
  const kind = select([["individual", "개인"], ["group", "단체"]], s.kind);
  kind.addEventListener("change", () => {
    cap.disabled = kind.value === "individual";
    cap.value = kind.value === "individual" ? 1 : Math.max(2, +cap.value);
  });
  const loc = h("input", { type: "text", value: s.location, maxlength: 200 });
  const note = h("input", { type: "text", value: s.note, maxlength: 500 });
  const booked = s.capacity - s.remaining;
  const r = await modal("상담 시간 수정", h("div", {},
    h("p", {}, h("strong", {}, fmtDateTime(s.start_at)), ` · 예약 ${booked}명`),
    field("유형", kind), field("정원", cap), field("장소", loc), field("안내", note)), [
    { label: "닫기", value: null },
    { label: "이 시간 취소", danger: true, value: "cancel" },
    { label: "저장", primary: true, handler: async () => {
      try {
        await patch(`/api/slots/${s.id}`, { kind: kind.value, capacity: +cap.value, location: loc.value, note: note.value });
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
  await draw(root);
}
