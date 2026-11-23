import { mountCalendarPreservingScroll } from "../components/calendar-scroll.js";
import { watchRefresh } from "../live-refresh.js";
import { prefetchWeeks } from "../calendar-prefetch.js";
import { startRegistrationAt } from "./prof-slots.js";
import { loadLectures, lectureEditor } from "../components/lecture-editor.js";
import { staffToday } from "../components/staff-today.js";
import { bookingActivity, eventLabels } from "../components/booking-activity.js";
// 교수자·관리자: 예약 현황 · 완료/미참석 · 상담 기록 · 대리 예약 · 일정 조정
import { calendarGet, clearCalendarCache, get, post, put } from "../api.js";
import { addDays, fmtDateTime, fmtDateTimeRange, fmtTime, kstParts, mondayOf, todayKst } from "../time.js";
import { isMobile, onLayoutChange, calendarLegend, renderCalendar, weekNav } from "../components/week-calendar.js";
import {
  STATUS_LABEL, badge, empty, errorToast, field, h, modal, mount, promptText, select, toast,
} from "../ui.js";

let filter = { status: "booked", period: "all" };
let viewMode = "list";
let weekStart = null;
let selectedDay = null;
let mobileView = "week";
let detach = null;
let calendarVersion = 0;
let todayPanel = null;

function viewSwitcher(root) {
  return h("div", { class: "calendar-toggle", "aria-label": "예약 관리 보기 방식" },
    h("a", { class: "btn desktop-timetable-link", href: "#/slots" }, "시간표"),
    ...[["list", "예약 목록"], ["activity", "예약 활동 기록"]].map(([value, label]) =>
      h("button", { class: "btn", "aria-pressed": String(viewMode === value),
        onclick: () => { if (viewMode === value) return; viewMode = value; render(root); } }, label)));
}

export async function showStaffSlot(root, slot, bookings, highlight = false, refresh = () => render(root)) {
  const related = bookings.filter((b) => b.slot.id === slot.id);
  if (!related.length) {
    const r = await modal("빈 상담 시간", h("div", { class: "booking-detail" },
      h("p", {}, fmtDateTime(slot.start_at)),
      h("p", { class: "muted" }, "등록된 상담이지만 학생 예약은 아직 없습니다.")), [
      { label: "닫기", value: null },
      { label: "상담 등록으로 이동", primary: true, value: "book" },
    ]);
    if (r === "book") location.hash = "#/slots/new";
    return;
  }
  const openedPath = location.hash;
  let b = related[0];
  let changed = false;
  while (true) {
    const picker = related.length > 1 ? select(related.map(x => [x.id,
      `${x.applicant_name || x.student_name} · ${STATUS_LABEL[x.status]}`]), String(b.id)) : null;
    const note = h("textarea", { rows: 5, maxlength: 10000 });
    note.value = b.professor_note || "";
    const dirty = () => note.value !== (b.professor_note || "");
    const discard = () => !dirty() || window.confirm("저장하지 않은 상담 기록을 버릴까요? 취소하면 계속 작성할 수 있습니다.");
    const actions = [{ label: "닫기", value: null },
      { label: "기록 저장", primary: true, handler: async () => {
        const savedNote = note.value;
        note.disabled = true;
        if (picker) picker.disabled = true;
        try {
          await put(`/api/bookings/${b.id}/note`, { note: savedNote });
          b.professor_note = savedNote; changed = true;
          toast("상담 기록을 저장했습니다.", "success"); return "saved";
        } finally {
          note.disabled = false;
          if (picker) picker.disabled = false;
        }
      } }];
    const started = new Date(b.slot.start_at) <= new Date();
    if (["booked", "expired", "completed", "no_show"].includes(b.status) && started) {
      for (const [value, label] of [["completed", "상담 완료"], ["no_show", "미참석"]]) {
        if (b.status !== value) actions.push({ label, handler: () => discard() ? value : false });
      }
    }
    if (b.status === "booked") actions.push(
      { label: "일정 조정", handler: () => discard() ? "reschedule" : false },
      { label: "예약 취소", danger: true, handler: () => discard() ? "cancel" : false });
    actions.push({ label: "변경 이력", handler: () => discard() ? "history" : false });
    // Switching students reopens the same editor only after guarding the current draft.
    let nextId = null;
    picker?.addEventListener("change", () => {
      if (!discard()) { picker.value = String(b.id); return; }
      nextId = picker.value;
      note.value = b.professor_note || "";
      document.querySelector("#modal-root .modal-actions button")?.click();
    });
    const result = await modal("예약·상담 상세", h("div", { class: "booking-detail" },
      h("p", {}, fmtDateTimeRange(b.slot.start_at, b.slot.end_at)),
      picker ? field("학생 선택", picker) : null,
      h("p", {}, `${b.applicant_name || b.student_name} · ${STATUS_LABEL[b.status]}`),
      h("p", { class: "muted" }, [b.student_number, b.grade ? `${b.grade}학년` : "", b.student_email].filter(Boolean).join(" · ")),
      h("p", {}, bookingType(b)),
      b.slot.location ? h("p", {}, `장소: ${b.slot.location}`) : null,
      b.slot.note ? h("p", {}, `상담 안내: ${b.slot.note}`) : null,
      h("p", {}, b.topic || "상담 내용 미입력"),
      field("교수자 상담 기록", note),
      h("p", { class: "muted" }, "교수자·관리자만 볼 수 있습니다. 학업·진로·취업 진행사항만 기록하고 건강·심리 상태 등 민감한 개인정보는 입력하지 마세요.")),
      actions, { beforeClose: value => value !== null || discard() });
    if (nextId) { b = related.find(x => String(x.id) === nextId); continue; }
    if (result === null) break;
    try {
      if (result === "completed" || result === "no_show") {
        await post(`/api/bookings/${b.id}/outcome`, { outcome: result });
        b.status = result; changed = true; toast("상담 결과를 저장했습니다.", "success");
      } else if (result === "reschedule") {
        await reschedule(b); changed = true; break;
      } else if (result === "cancel") {
        const reason = await promptText("예약 취소", "취소 사유 (학생에게 표시됨)", { required: true });
        if (reason !== null) {
          await post(`/api/bookings/${b.id}/cancel`, { reason });
          b.status = "cancelled"; changed = true;
        }
      } else if (result === "history") {
        const events = await get(`/api/bookings/${b.id}/history`);
        await modal("변경 이력", h("ul", {}, events.map(e => h("li", {},
          `${fmtDateTime(e.at)} · ${eventLabels[e.action] || e.action} ${e.detail}`))), [{ label: "닫기", value: null }]);
      }
    } catch (e) { errorToast(e); }
  }
  if (changed && root.isConnected && location.hash === openedPath) await refresh();
}

async function renderCalendarView(root) {
  weekStart ||= mondayOf(todayKst());
  selectedDay ||= todayKst();
  detach?.();
  detach = onLayoutChange(() => { if (viewMode === "calendar") renderCalendarView(root); });
  const version = ++calendarVersion, requestedWeek = weekStart;
  const [slots, bookings, lectures] = await Promise.all([
    calendarGet(`/api/slots?start=${requestedWeek}&days=7`),
    calendarGet(`/api/bookings?start=${requestedWeek}&days=7`), loadLectures(requestedWeek),
  ]);
  if (version !== calendarVersion || weekStart !== requestedWeek || viewMode !== "calendar" || !(location.hash === "#/bookings" || /^#\/inbox\/\d+$/.test(location.hash)) || !root.isConnected) return;
  const enhanced = slots.map((slot) => {
    const related = bookings.filter(b => b.slot.id === slot.id && b.status !== "cancelled");
    const names = related.map(b => b.applicant_name || b.student_name || "이름 미입력");
    const count = bookings.filter((b) => b.slot.id === slot.id && b.status === "booked").length;
    return { ...slot, managerState: slot.status === "cancelled" ? null : count ? "reserved" : slot.bookable ? "free" : null,
      bookingCount: count, staffBookingNames: names.join(", ") };
  });
  mountCalendarPreservingScroll(root, () => [
    h("div", { class: "page-head" }, h("h1", {}, "예약 관리")),
    todayPanel ||= staffToday(),
    viewSwitcher(root),
    h("p", { class: "muted" }, "날짜의 숫자는 현재 예약된 학생 수입니다. 시간 칸에서 예약 학생 이름을 확인하고 누르면 상세 기록을 볼 수 있습니다."),
    calendarLegend(),
    h("button", { class: "btn small", onclick: () => { clearCalendarCache(); todayPanel = null; renderCalendarView(root).catch(errorToast); } }, "예약 현황 새로고침"),
    renderCalendar({ navigation: weekNav(weekStart, (w) => { weekStart = w; selectedDay = w; renderCalendarView(root); }), weekStart, selectedDay, slots: [...enhanced, ...lectures].sort((a,b) => a.start_at.localeCompare(b.start_at)), mobileView, dayCountMode: "booked",
      onTimeSelect: startRegistrationAt,
      onWeekChange: (w) => { weekStart = w; selectedDay = w; return renderCalendarView(root); },
      onViewChange: (mode) => { mobileView = mode; renderCalendarView(root); },
      onDay: (day) => { selectedDay = day; renderCalendarView(root); },
      onSlot: (slot) => slot.event_type === "lecture" ? lectureEditor(() => renderCalendarView(root), slot) : showStaffSlot(root, slot, bookings) }),
  ]);
  prefetchWeeks(requestedWeek, ['slots', 'bookings', 'lectures']);
}


export async function render(root) {
  if (location.hash === "#/bookings" && viewMode === "calendar") viewMode = "list";
  calendarVersion++;
  clearCalendarCache();
  todayPanel = null;
  if (viewMode === 'activity') {
    detach?.(); detach = null;
    mount(root, h('div', { class: 'page-head' }, h('h1', {}, '예약 관리')), viewSwitcher(root), bookingActivity());
    return;
  }
  if (viewMode === "calendar") {
    await renderCalendarView(root);
    watchRefresh(root, () => {
      if (viewMode !== "calendar") return;
      todayPanel = null;
      clearCalendarCache();
      return renderCalendarView(root);
    });
    return;
  }
  detach?.();
  detach = null;
  const q = new URLSearchParams();
  if (filter.period === "future") q.set("from_date", todayKst());
  if (filter.period === "recent") { q.set("start", addDays(todayKst(), -90)); q.set("days", "91"); }
  if (filter.status) q.set("status", filter.status);
  const list = await get(`/api/bookings?${q}`);
  const status = select([["", "전체"], ["booked", "예약됨"], ["completed", "완료"], ["no_show", "미참석"],
    ["expired", "기간 종료·결과 미확인"], ["cancelled", "취소됨"]], filter.status);
  status.setAttribute("aria-label", "예약 상태");
  const period = select([["all", "전체 기간"], ["future", "오늘 이후"], ["recent", "최근 90일·오늘"]], filter.period);
  period.setAttribute("aria-label", "기간");
  const apply = () => { filter = { status: status.value, period: period.value }; render(root); };
  period.addEventListener("change", apply);
  status.addEventListener("change", apply);
  const results = h("div", { class: "table-wrap" });
  const showList = () => mount(results, isMobile() ? mobileList(root, list) : table(root, list));
  if (list.length) {
    showList();
    detach = onLayoutChange(showList);
  }
  mount(root,
    h("div", { class: "page-head" }, h("h1", {}, "예약 관리")),
    staffToday(),
    viewSwitcher(root),
    h("div", { class: "filters" }, field("기간", period), field("상태", status)),
    h("p", { class: "muted" }, `${period.selectedOptions[0].textContent} · ${filter.status === "booked" ? "현재 예약 " : ""}${list.length}건 (한국시간)`),
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
      h("span", {}, fmtDateTimeRange(b.slot.start_at, b.slot.end_at), time),
      badge(STATUS_LABEL[b.status], b.status));
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
  return [h("button", { class: "btn small primary", onclick: () =>
    showStaffSlot(root, b.slot, [b]).catch(errorToast) }, "예약·상담 상세")];
}

async function reschedule(b) {
  const day = h("input", { type: "date", value: kstParts(b.slot.start_at).date, min: todayKst() });
  const slotSelect = select([]);
  const reason = h("input", { type: "text", maxlength: 500 });
  let version = 0;
  const load = async () => {
    const current = ++version;
    slotSelect.replaceChildren();
    slotSelect.disabled = true;
    const slots = await get(`/api/slots?start=${day.value}&days=1`);
    if (version !== current) return;
    for (const s of slots.filter((s) => s.id !== b.slot.id && s.status === "open" && s.remaining > 0
      && new Date(s.start_at) > new Date()))
      slotSelect.append(h("option", { value: s.id }, fmtDateTime(s.start_at)));
    slotSelect.disabled = !slotSelect.options.length;
  };
  day.addEventListener("change", () => { if (day.value) load().catch(errorToast); });
  await load();
  const r = await modal("기존 예약 시간 변경", h("div", {},
    h("p", {}, `변경 전: ${fmtDateTime(b.slot.start_at)}`),
    h("p", {}, "예약과 상담 내용은 유지하고 시간만 변경합니다. 원하는 날짜를 선택하세요."),
    field("변경 후 날짜", day), field("변경 후 시간", slotSelect), field("사유 (선택)", reason)), [
    { label: "닫기", value: null },
    { label: "시간 변경", primary: true, handler: () => {
      if (slotSelect.disabled || !slotSelect.value) { toast("변경할 시간을 선택하세요", "error"); return false; }
      return { slot: +slotSelect.value, reason: reason.value };
    } },
  ]);
  if (!r) return;
  await post(`/api/bookings/${b.id}/reschedule`, {
    new_slot_id: r.slot, expected_slot_id: b.slot.id, reason: r.reason,
  });
  toast("기존 예약의 시간을 변경했습니다", "success");
}

// Only called after server-side inbox ownership and booking permission checks.
export async function openNotification(root, booking, notification = {}) {
  const day = kstParts(booking.slot.start_at).date;
  weekStart = mondayOf(day); selectedDay = day; viewMode = "calendar";
  await render(root);
  if (!root.isConnected) return;
  const path = location.hash;
  const card = [...root.querySelectorAll('[data-slot-id]')].find(el => el.dataset.slotId === String(booking.slot.id) && el.dataset.eventType === "consultation");
  card?.classList.add("notification-target");
  card?.scrollIntoView({ block: "nearest", behavior: "instant" });
  const body = h("div", { class: "notification-booking-summary" },
    h("p", { class: "booking-summary-person" }, h("strong", {}, booking.applicant_name || booking.student_name),
      booking.grade ? ` · ${booking.grade}학년` : "", ""),
    h("p", {}, "현재 상태: ", badge(booking.status === "completed" ? "상담 완료" : STATUS_LABEL[booking.status] || "상태 확인 필요", booking.status)),
    h("p", {}, h("strong", {}, fmtDateTimeRange(booking.slot.start_at, booking.slot.end_at))),
    h("p", { class: "hint" }, "현재 예약 정보입니다."),
    booking.topic ? h("p", {}, `상담 주제: ${booking.topic}`) : null,
    notification.arrived_at ? h("small", { class: "muted" }, `알림 시각: ${fmtDateTime(notification.arrived_at)} (한국시간)`) : null);
  void modal(({ "새 상담 예약": "예약 접수 알림", "상담 예약 취소": "예약 취소 알림" })[notification.title] || notification.title || "예약 알림", body, [
    { label: "닫기", value: null },
    { label: "기록·예약 관리", value: "manage", primary: true },
  ]).then(async result => {
  if (!root.isConnected || location.hash !== path) return;
  if (result === "manage") {
    // Preserve the existing editor and every action, but only open it on request.
    // Use this booking alone, including cancelled/shared-slot reservations.
    await showStaffSlot(root, booking.slot, [booking]);
  }
  if (card?.isConnected) {
    card.classList.add("notification-target");
    card.focus({ preventScroll: true });
    setTimeout(() => card.classList.remove("notification-target"), 2800);
  }
  }).catch(errorToast);
  requestAnimationFrame(() => {
    if (root.isConnected && location.hash === path) document.querySelector("#modal-root .modal")?.focus();
  });
}
