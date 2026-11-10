import { professorNotifications } from "../components/professor-notifications.js";
import { staffToday } from "../components/staff-today.js";
import { bookingActivity, eventLabels } from "../components/booking-activity.js";
// 교수자·관리자: 예약 현황 · 완료/미참석 · 상담 기록 · 대리 예약 · 일정 조정
import { get, post, put } from "../api.js";
import { addDays, fmtDateTime, kstParts, mondayOf, todayKst } from "../time.js";
import { isMobile, onLayoutChange, renderCalendar, weekNav } from "../components/week-calendar.js";
import {
  STATUS_LABEL, badge, busy, empty, errorToast, field, h, modal, mount, promptText, select, toast,
} from "../ui.js";

let filter = { status: "booked" };
let viewMode = "list";
let weekStart = null;
let selectedDay = null;
let mobileView = "list";
let detach = null;

function viewSwitcher(root) {
  return h("div", { class: "calendar-toggle", "aria-label": "예약 관리 보기 방식" },
    ...[["calendar", "주간 예약 시간표"], ["list", "예약 목록"], ["activity", "예약 활동 기록"]].map(([value, label]) =>
      h("button", { class: "btn", "aria-pressed": String(viewMode === value),
        onclick: () => { viewMode = value; render(root); } }, label)));
}

async function showStaffSlot(root, slot, bookings) {
  const related = bookings.filter((b) => b.slot.id === slot.id);
  if (!related.length) {
    const r = await modal("빈 상담 시간", h("div", { class: "booking-detail" },
      h("p", {}, fmtDateTime(slot.start_at)),
      h("p", { class: "muted" }, "등록된 상담이지만 학생 예약은 아직 없습니다.")), [
      { label: "닫기", value: null },
      { label: "학생 대신 예약", primary: true, value: "book" },
    ]);
    if (r === "book") await bookForStudent(root);
    return;
  }
  let b = related[0];
  const picker = related.length > 1 ? select(related.map((x) => [
    x.id, `${x.applicant_name || x.student_name} · ${x.student_number || x.student_email}`,
  ])) : null;
  const info = h("p", { class: "muted" }, "");
  const note = h("textarea", { rows: 5, maxlength: 10000 });
  const reason = h("input", { type: "text", maxlength: 500, placeholder: "취소 시 학생에게 보여줄 사유" });
  const update = () => {
    b = related.find((x) => String(x.id) === String(picker?.value)) || related[0];
    info.textContent = `${b.applicant_name || b.student_name} · ${b.grade ? b.grade + "학년" : "학년 미입력"} · ${b.status} · ${b.topic || "상담 주제 미입력"}`;
    note.value = b.professor_note || "";
  };
  picker?.addEventListener("change", update);
  update();
  const actions = [
    { label: "닫기", value: null },
    { label: "기록 저장", primary: true, handler: async () => {
      try { await put(`/api/bookings/${b.id}/note`, { note: note.value }); toast("상담 기록을 저장했습니다.", "success"); return true; }
      catch (e) { errorToast(e); return false; }
    } },
  ];
  if (related.some((x) => x.status === "booked")) {
    actions.push({ label: "예약 취소", danger: true, handler: async () => {
      if (b.status !== "booked") { toast("진행 중인 예약을 선택해 주세요.", "error"); return false; }
      if (!reason.value.trim()) { toast("취소 사유를 입력해 주세요.", "error"); reason.focus(); return false; }
      try { await post(`/api/bookings/${b.id}/cancel`, { reason: reason.value }); toast("예약을 취소했습니다.", "success"); return true; }
      catch (e) { errorToast(e); return false; }
    } });
    if (new Date(slot.start_at) <= new Date()) actions.push({
      label: "상담 완료", handler: async () => {
        if (b.status !== "booked") { toast("진행 중인 예약을 선택해 주세요.", "error"); return false; }
        try { await post(`/api/bookings/${b.id}/outcome`, { outcome: "completed" }); toast("완료 처리했습니다.", "success"); return true; }
        catch (e) { errorToast(e); return false; }
      },
    });
  }
  const result = await modal("예약·상담 상세", h("div", { class: "booking-detail" },
    h("p", {}, h("strong", {}, fmtDateTime(slot.start_at)), ` · 예약 ${related.length}/${slot.capacity}명`),
    picker ? field("학생 선택", picker) : null, info,
    field("교수자 상담 기록", note),
    h("p", { class: "muted" }, "학업·진로·취업 진행사항만 기록해 주세요. 건강·심리 상태 등 민감한 개인정보는 입력하지 마세요."),
    reason && related.some((x) => x.status === "booked") ? field("예약 취소 사유", reason) : null,
  ), actions);
  if (result !== null) await render(root);
}

async function renderCalendarView(root) {
  weekStart ||= mondayOf(todayKst());
  selectedDay ||= todayKst();
  detach?.();
  detach = onLayoutChange(() => { if (viewMode === "calendar") renderCalendarView(root); });
  const [slots, bookings] = await Promise.all([
    get(`/api/slots?start=${weekStart}&days=7`),
    get(`/api/bookings?start=${weekStart}&days=7`),
  ]);
  const enhanced = slots.map((slot) => {
    const count = bookings.filter((b) => b.slot.id === slot.id && b.status === "booked").length;
    return { ...slot, managerState: slot.status === "cancelled" ? null : count ? "reserved" : "free",
      bookingCount: count };
  });
  mount(root,
    h("div", { class: "page-head" }, h("h1", {}, "예약 관리"),
      h("button", { class: "btn primary", onclick: () => bookForStudent(root) }, "학생 대신 예약")),
    professorNotifications(),
    staffToday(),
    viewSwitcher(root),
    h("p", { class: "muted" }, "날짜의 숫자는 현재 예약된 학생 수입니다. 상담 시간을 누르면 학생과 기록을 확인할 수 있습니다."),
    weekNav(weekStart, (w) => { weekStart = w; selectedDay = w; renderCalendarView(root); }),
    renderCalendar({ weekStart, selectedDay, slots: enhanced, mobileView, dayCountMode: "booked",
      onViewChange: (mode) => { mobileView = mode; renderCalendarView(root); },
      onDay: (day) => { selectedDay = day; renderCalendarView(root); },
      onSlot: (slot) => showStaffSlot(root, slot, bookings) }),
  );
}


export async function render(root) {
  if (viewMode === 'activity') {
    detach?.(); detach = null;
    mount(root, h('div', { class: 'page-head' }, h('h1', {}, '예약 관리')), viewSwitcher(root), bookingActivity());
    return;
  }
  if (viewMode === "calendar") return renderCalendarView(root);
  detach?.();
  detach = null;
  const q = new URLSearchParams();
  if (filter.status) q.set("status", filter.status);
  const list = await get(`/api/bookings?${q}`);
  const status = select([["", "전체"], ["booked", "예약됨"], ["completed", "완료"], ["no_show", "미참석"],
    ["cancelled", "취소됨"]], filter.status);
  const apply = () => { filter = { status: status.value }; render(root); };
  status.addEventListener("change", apply);
  const newBtn = h("button", { class: "btn primary", onclick: () => bookForStudent(root) }, "학생 대신 예약");
  const results = h("div", { class: "table-wrap" });
  const showList = () => mount(results, isMobile() ? mobileList(root, list) : table(root, list));
  if (list.length) {
    showList();
    detach = onLayoutChange(showList);
  }
  mount(root,
    h("div", { class: "page-head" }, h("h1", {}, "예약 관리"), newBtn),
    professorNotifications(),
    staffToday(),
    viewSwitcher(root),
    h("div", { class: "filters" }, field("상태", status)),
    h("p", { class: "muted" }, `전체 기간 · ${filter.status === "booked" ? "현재 예약 " : ""}${list.length}건 (한국시간)`),
    list.length ? results : empty("해당 조건의 예약이 없습니다."));
}

export async function todayBookings(root) {
  const list = await get(`/api/bookings?start=${todayKst()}&days=1&status=booked`);
  mount(root, h("h1", {}, "오늘 상담 일정"), h("a", {class: "btn", href: "#/bookings"}, "전체 예약 관리"),
    list.length ? mobileList(root, list) : empty("오늘 예약이 없습니다."));
}

function mobileList(root, list) {
  const cards = h("div", { class: "cards mobile-bookings" });
  const clocks = [];
  for (const b of list) {
    const time = h("small", { class: "muted" });
    if (b.status === "booked") clocks.push({ start: b.slot.start_at, time });
    const summary = h("summary", {},
      h("strong", {}, b.applicant_name || b.student_name, " · ", b.student_number || "학번 미입력"),
      h("span", {}, fmtDateTime(b.slot.start_at), time));
    cards.append(h("details", { class: "card", dataset: { bookingId: b.id } }, summary,
      h("p", {}, badge(STATUS_LABEL[b.status], b.status), " ", bookingType(b)),
      h("p", { class: "muted" }, [b.grade && b.grade + "학년", b.student_email].filter(Boolean).join(" · ")),
      h("p", {}, b.topic || "상담 내용 미입력"),
      h("div", { class: "actions" }, actions(root, b))));
  }
  const update = () => {
    const today = todayKst();
    for (const { start, time } of clocks) {
      const minutes = Math.ceil((Date.parse(start) - Date.now()) / 60000);
      const hours = Math.floor(minutes / 60);
      let label = "";
      if (minutes > 0 && kstParts(start).date === today) {
        const parts = [hours && hours + "시간", minutes % 60 && minutes % 60 + "분"];
        label = " · " + parts.filter(Boolean).join(" ") + " 후";
      }
      time.textContent = label;
    }
  };
  update();
  if (clocks.length) {
    const timer = setInterval(() => {
      if (cards.isConnected) update();
      else clearInterval(timer);
    }, 30000);
  }
  return cards;
}

function bookingType(b) {
  const topic = { career: "진로", employment: "취업", academics: "학업", campus: "학교생활", other: "기타" };
  return [b.slot.kind === "group" ? "단체" : "개인", topic[b.consultation_type] || "기타",
    b.consultation_mode === "online" ? "온라인" : "대면"].join(" · ");
}

function table(root, list) {
  return h("table", { class: "table" },
    h("thead", {}, h("tr", {}, ["일시", "학생", "유형", "상담 내용", "상태", "작업"].map((t) => h("th", {}, t)))),
    h("tbody", {}, list.map((b) => h("tr", { dataset: { bookingId: b.id } },
      h("td", { "data-label": "일시" }, fmtDateTime(b.slot.start_at)),
      h("td", { "data-label": "학생" }, `${b.applicant_name || b.student_name} `,
        h("small", { class: "muted" }, [b.student_number, b.grade ? `${b.grade}학년` : "", b.student_email]
          .filter(Boolean).join(" · "))),
      h("td", { "data-label": "유형" }, bookingType(b)),
      h("td", { "data-label": "상담 내용" }, b.topic || "-"),
      h("td", { "data-label": "상태" }, badge(STATUS_LABEL[b.status], b.status)),
      h("td", { "data-label": "작업", class: "actions" }, actions(root, b))))));
}

function actions(root, b) {
  const started = new Date(b.slot.start_at) <= new Date();
  const out = [];
  const act = (label, fn, cls = "btn small") => {
    const btn = h("button", { class: cls }, label);
    btn.addEventListener("click", busy(btn, async () => {
      try { await fn(); await render(root); } catch (e) { errorToast(e); }
    }));
    out.push(btn);
  };
  if (["booked", "completed", "no_show"].includes(b.status) && started) {
    if (b.status !== "completed") act("완료", async () => { await post(`/api/bookings/${b.id}/outcome`, { outcome: "completed" }); toast("완료 처리", "success"); });
    if (b.status !== "no_show") act("미참석", async () => { await post(`/api/bookings/${b.id}/outcome`, { outcome: "no_show" }); toast("미참석 처리", "success"); });
  }
  if (b.status === "booked") {
    act("일정 조정", () => reschedule(b));
    act("취소", async () => {
      const reason = await promptText("예약 취소", "취소 사유 (학생에게 표시됨)", { required: true });
      if (reason === null) return;
      await post(`/api/bookings/${b.id}/cancel`, { reason });
      toast("취소했습니다", "success");
    }, "btn small danger");
  }
  act("상담 기록", async () => {
    const note = await promptText("상담 기록", "교수자·관리자만 볼 수 있습니다. 학업·진로·취업 진행사항만 기록하고 건강·심리 상태 등 민감한 개인정보는 입력하지 마세요. 외부 AI로 전송되지 않습니다.",
      { multiline: true, value: b.professor_note });
    if (note === null) return;
    await put(`/api/bookings/${b.id}/note`, { note });
    toast("저장했습니다", "success");
  });
  act("이력", async () => {
    const ev = await get(`/api/bookings/${b.id}/history`);
    await modal("변경 이력", h("ul", { class: "plain" }, ev.map((e) => h("li", {}, `${fmtDateTime(e.at)} · ${eventLabels[e.action] || e.action} ${e.detail}`))),
      [{ label: "닫기", value: null }]);
  });
  if (out.length <= 2) return out;
  const main = out.find((btn) => btn.textContent === "일정 조정") || out[0];
  const more = h("details", { class: "action-more" },
    h("summary", { class: "btn small", "aria-label": "추가 예약 관리 작업" }, "⋯ 더보기"),
    h("div", { class: "action-more-panel" }, ...out.filter((btn) => btn !== main)));
  return [main, more];
}

async function pickSlot(title, noteLabel = "사유 (선택)") {
  const from = todayKst();
  const slots = (await get(`/api/slots?start=${from}&days=31`)).filter((s) => s.status === "open" && s.remaining > 0
    && new Date(s.start_at) > new Date());
  if (!slots.length) { toast("남은 자리가 있는 상담 시간이 없습니다", "error"); return null; }
  const sel = select(slots.map((s) => [s.id, `${kstParts(s.start_at).date} ${kstParts(s.start_at).time} (${s.kind === "group" ? `단체 ${s.remaining}석` : "개인"})`]));
  const reason = h("input", { type: "text", maxlength: 500 });
  const r = await modal(title, h("div", {}, field("상담 시간", sel), field(noteLabel, reason)), [
    { label: "취소", value: null }, { label: "확인", primary: true, handler: () => ({ slot: +sel.value, reason: reason.value }) },
  ]);
  return r;
}

async function reschedule(b) {
  const r = await pickSlot("일정 조정");
  if (!r) return;
  await post(`/api/bookings/${b.id}/reschedule`, { new_slot_id: r.slot, reason: r.reason });
  toast("일정을 조정했습니다", "success");
}

async function bookForStudent(root) {
  try {
    const students = await get("/api/students");
    if (!students.length) { toast("등록된 학생이 없습니다", "error"); return; }
    const who = select(students.map((s) => [s.id, `${s.name} (${s.email})`]));
    const r1 = await modal("학생 선택", field("학생", who), [{ label: "취소", value: null }, { label: "다음", primary: true, handler: () => +who.value }]);
    if (!r1) return;
    const r2 = await pickSlot("상담 시간 선택", "상담 주제 (선택)");
    if (!r2) return;
    await post("/api/bookings", { slot_id: r2.slot, student_id: r1, topic: r2.reason });
    toast("예약했습니다", "success");
    await render(root);
  } catch (e) { errorToast(e); }
}
