// PC·모바일 주간 시간표 / 모바일 일별 목록 공용 컴포넌트.
import { addDays, fmtDate, fmtTime, kstParts, todayKst } from "../time.js";
import { h } from "../ui.js";

const MOBILE = window.matchMedia("(max-width: 720px)");
const DAYS = ["월", "화", "수", "목", "금", "토", "일"];
const STEP = 15; // 분 단위 행 높이

export function isMobile() { return MOBILE.matches; }

export function revealSelectedDay(root) {
  if (!isMobile()) return;
  const title = root.querySelector(".daily-title"), path = location.hash;
  if (!title) return;
  requestAnimationFrame(() => {
    if (!title.isConnected || location.hash !== path) return;
    const headerHeight = document.querySelector(".topbar")?.getBoundingClientRect().height || 0;
    title.focus({ preventScroll: true });
    window.scrollTo({ top: Math.max(0, window.scrollY + title.getBoundingClientRect().top - headerHeight - 12),
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  });
}

function dayCount(o, slots) {
  return o.dayCountMode === "booked"
    ? slots.filter(s => s.event_type !== "lecture" && s.status !== "cancelled").reduce((sum, s) => sum + (s.bookingCount || 0), 0)
    : slots.filter(s => s.bookable === true).length;
}

export function onLayoutChange(cb) {
  const route = location.hash;
  const update = () => { if (location.hash === route) cb(); };
  const detach = () => {
    MOBILE.removeEventListener("change", update);
    window.removeEventListener("hashchange", detach);
  };
  MOBILE.addEventListener("change", update);
  window.addEventListener("hashchange", detach, { once: true });
  return detach;
}

// Consultation slots and lectures can intentionally coexist on the same time axis.
function sharingLane(slot, events) {
  return events.some(other => other !== slot && (other.event_type === "lecture") !== (slot.event_type === "lecture")
    && new Date(other.start_at) < new Date(slot.end_at) && new Date(other.end_at) > new Date(slot.start_at));
}

function slotClass(s) {
  if (s.event_type === "lecture") return "slot lecture";
  if (s.managerState === "reserved") return "slot reserved";
  if (s.status === "cancelled") return "slot cancelled";
  if (s.mine) return "slot mine";
  if (s.bookable === false && s.reason) return "slot closed";
  return "slot open";
}

function slotLabel(s) {
  if (s.event_type === "lecture") return `강의 · ${s.title}`;
  if (s.managerState === "reserved") return `예약 ${s.bookingCount}/${s.capacity}명`;
  if (s.managerState === "free") return "빈 상담";
  const kind = s.kind === "group" ? `단체 · 남은 ${s.remaining}/${s.capacity}` : "개인";
  if (s.status === "cancelled") return "취소됨";
  if (s.mine) return `내 예약 · ${kind}`;
  if (s.reason) return `${s.reason} · ${kind}`;
  return `예약 가능 · ${kind}`;
}

/**
 * @param {object} o
 * @param {string} o.weekStart 월요일 (YYYY-MM-DD, KST)
 * @param {Array} o.slots 서버 SlotOut 배열
 * @param {(slot)=>void} o.onSlot 클릭 핸들러
 * @param {string} [o.selectedDay] 모바일에서 선택한 날짜
 * @param {(day)=>void} [o.onDay]
 * @param {(slot)=>Node|null} [o.extra] 슬롯 카드에 추가로 붙일 노드
 * @param {boolean} [o.mobileListOnly] 모바일에서 목록만 표시
 * @param {"week"|"list"|"timeline"} [o.mobileView] 모바일 보기
 * @param {(week:string)=>Promise<void>|void} [o.onWeekChange] 주 이동
 * @param {(mode:string)=>void} [o.onViewChange] 모바일 보기 전환
 */
export function renderCalendar(o) {
  const byDay = {};
  for (const s of o.slots) (byDay[kstParts(s.start_at).date] ||= []).push(s);
  return isMobile() ? renderMobile(o, byDay) : renderWeekly(o, byDay);
}

// Keep the same event data and detail handlers in every view. Mobile defaults
// to a whole-week overview; list mode provides readable event details.
function renderMobile(o, byDay) {
  const mode = ["week", "list", "timeline"].includes(o.mobileView) ? o.mobileView : "week";
  const toggle = h("div", { class: "mobile-view-toggle calendar-view-switch", role: "group", "aria-label": "일정 보기 방식" },
    ...[["week", "주간"], ["list", "목록"]].map(([value, label]) =>
      h("button", { type: "button", class: mode === value ? "btn primary" : "btn",
        "aria-pressed": String(mode === value), onclick: () => o.onViewChange?.(value) }, label)));
  if (mode === "list" || mode === "timeline") {
    return h("div", { class: "mobile-calendar" }, toggle,
      renderDaily({ ...o, mobileListOnly: mode === "list", hideViewToggle: true }, byDay));
  }
  const days = Array.from({ length: 7 }, (_, i) => addDays(o.weekStart, i));
  return h("div", { class: "mobile-calendar calendar-week" }, toggle,
    h("h3", { class: "daily-title calendar-grid-title", tabindex: "-1" }, `${fmtDate(o.weekStart)} – ${fmtDate(days[6])}`),
    h("p", { class: "hint calendar-help" }, "좌우로 충분히 밀면 이전·다음 주로 이동합니다. 작은 일정은 목록에서 자세히 볼 수 있어요."),
    renderWeekly({ ...o, gridDays: days, compactGrid: true }, byDay));
}

function renderWeekly(o, byDay) {
  const days = o.gridDays || Array.from({ length: 7 }, (_, d) => addDays(o.weekStart, d));
  const rowPx = o.compactGrid ? 24 : 18;
  // The pixel size of a 15-minute interval must NOT change with the
  // consultation duration or the number of slots in the displayed week.
  let minH = 9, maxH = 12;
  if (o.slots.length) {
    const starts = o.slots.map((s) => kstParts(s.start_at).hour);
    const ends = o.slots.map((s) => {
      const p = kstParts(s.end_at);
      return p.hour + (p.minute ? 1 : 0);
    });
    minH = Math.max(0, Math.min(...starts) - 1);
    maxH = Math.min(24, Math.max(...ends) + 1);
  }
  const rows = ((maxH - minH) * 60) / STEP;
  const grid = h("div", { class: "week-grid", role: "grid", "aria-label": "주간 시간표" });
  grid.style.gridTemplateRows = `auto repeat(${rows}, ${rowPx}px)`;
  if (o.compactGrid) grid.style.gridTemplateColumns = `36px repeat(${days.length}, minmax(0, 1fr))`;
  grid.append(h("div", { class: "corner" }));
  for (let d = 0; d < days.length; d++) {
    const day = days[d];
    const weekday = kstParts(`${day}T12:00:00+09:00`).weekday;
    const head = h("div", { class: `day-head${day === todayKst() ? " is-today" : ""}` }, h("strong", {}, weekday), " ", day.slice(5).replace("-", "/"));
    if (o.dayCountMode === "booked") head.append(h("small", { class: "reserved-day-count" }, `예약 ${dayCount(o, byDay[day] || [])}명`));
    head.style.gridColumn = String(d + 2);
    grid.append(head);
  }
  for (let hr = minH; hr < maxH; hr++) {
    const label = h("div", { class: "hour" }, `${String(hr).padStart(2, "0")}:00`);
    label.style.gridRow = `${((hr - minH) * 60) / STEP + 2} / span ${60 / STEP}`;
    grid.append(label);
    for (let d = 0; d < days.length; d++) {
      const selectTime = (event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        // Keyboard activation selects the labelled hour; touch picks a quarter.
        const minute = event.detail && rect.height
          ? Math.max(0, Math.min(3, Math.floor((event.clientY - rect.top) / rect.height * 4))) * 15 : 0;
        const start = hr * 60 + minute, end = Math.min(23 * 60 + 59, start + 30);
        const clock = n => `${String(Math.floor(n / 60)).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}`;
        o.onTimeSelect?.({ date: days[d], start: clock(start), end: clock(end), duration: end - start });
      };
      const cell = h(o.onTimeSelect ? "button" : "div", { class: "cell calendar-time-cell",
        ...(o.onTimeSelect ? { type: "button", onclick: selectTime,
          "aria-label": `${fmtDate(days[d])} ${String(hr).padStart(2, "0")}:00 시간 선택` } : {}) });
      cell.style.gridRow = `${((hr - minH) * 60) / STEP + 2} / span ${60 / STEP}`;
      cell.style.gridColumn = String(d + 2);
      grid.append(cell);
    }
  }
  for (let d = 0; d < days.length; d++) {
    for (const s of byDay[days[d]] || []) {
      const a = kstParts(s.start_at), b = kstParts(s.end_at);
      const start = (a.hour - minH) * 60 + a.minute;
      const end = (b.hour - minH) * 60 + b.minute;
      const btn = h("button", { class: slotClass(s), onclick: () => o.onSlot(s),
        "aria-label": `${fmtDate(a.date)} ${a.time}-${b.time} ${slotLabel(s)}`, dataset: { slotId: s.id } },
        h("span", { class: "slot-time" }, `${a.time}–${b.time}`),
        h("span", { class: "slot-meta" }, o.compactGrid
          ? (s.event_type === "lecture" ? `강의 · ${s.title}` : s.status === "cancelled" ? "취소"
            : s.mine ? "내 예약" : s.reason || (s.managerState === "reserved" ? `예약 ${s.bookingCount}명` : "상담"))
          : slotLabel(s)),
        o.extra && !o.compactGrid ? o.extra(s) : null);
      // CSS grid line numbers must be integers (e.g. a 09:05 lecture).
      btn.style.gridRow = `${Math.floor(start / STEP) + 2} / ${Math.ceil(end / STEP) + 2}`;
      btn.style.marginTop = `${1 + (start % STEP) * rowPx / STEP}px`;
      btn.style.marginBottom = `${1 + ((STEP - end % STEP) % STEP) * rowPx / STEP}px`;
      btn.style.gridColumn = String(d + 2);
      if (sharingLane(s, o.slots)) {
        btn.style.width = "calc(50% - 4px)";
        btn.style.justifySelf = s.event_type === "lecture" ? "end" : "start";
      }
      grid.append(btn);
    }
  }
  const wrap = h("div", { class: `week-wrap${o.compactGrid ? " mobile-grid-wrap" : ""}`,
    ...(o.compactGrid ? { tabindex: "0", role: "region", "aria-label": "시간표 스크롤 영역" } : {}) }, grid);
  if (o.compactGrid && o.onWeekChange) enableWeekSwipe(wrap, grid, o);
  return wrap;
}

// Own only clearly horizontal touch/pen gestures. The browser retains vertical
// scrolling (including chaining), pinch zoom, and ordinary event-card taps.
function enableWeekSwipe(wrap, grid, o) {
  wrap.classList.add("week-swipe");
  let gesture = null, busy = false, suppressUntil = 0;
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const settle = () => {
    grid.style.transition = reduced() ? "none" : "transform 220ms cubic-bezier(.2,.8,.2,1)";
    grid.style.transform = "";
  };
  wrap.addEventListener("pointerdown", e => {
    if (e.pointerType === "mouse" || busy) return;
    if (!e.isPrimary || gesture) { gesture = null; settle(); return; }
    gesture = { id: e.pointerId, x: e.clientX, y: e.clientY, dx: 0, axis: null };
  });
  wrap.addEventListener("pointermove", e => {
    const g = gesture;
    if (!g || e.pointerId !== g.id) return;
    const dx = e.clientX - g.x, dy = e.clientY - g.y;
    if (!g.axis && Math.max(Math.abs(dx), Math.abs(dy)) >= 12) {
      g.axis = Math.abs(dx) > Math.abs(dy) * 1.3 ? "x" : "y";
      if (g.axis === "x") wrap.setPointerCapture(e.pointerId);
    }
    if (g.axis !== "x") return;
    g.dx = dx;
    suppressUntil = performance.now() + 600;
    // Increasing resistance, capped displacement: never throw the week offscreen.
    const offset = Math.sign(dx) * 72 * (1 - Math.exp(-Math.abs(dx) / 130));
    grid.style.transition = "none";
    grid.style.transform = reduced() ? "" : `translateX(${offset}px)`;
  });
  wrap.addEventListener("click", e => {
    if (performance.now() < suppressUntil) { e.preventDefault(); e.stopImmediatePropagation(); }
  }, true);
  const finish = (e, cancelled = false) => {
    const g = gesture;
    if (!g || e.pointerId !== g.id) return;
    gesture = null;
    if (g.axis !== "x" || cancelled) { settle(); return; }
    suppressUntil = performance.now() + 600;
    const threshold = Math.min(110, Math.max(80, wrap.clientWidth * .28));
    settle();
    if (Math.abs(g.dx) < threshold) return;
    busy = true;
    setTimeout(async () => {
      if (!wrap.isConnected) return;
      try { await o.onWeekChange(addDays(o.weekStart, g.dx < 0 ? 7 : -7)); }
      finally { busy = false; }
    }, reduced() ? 0 : 160);
  };
  wrap.addEventListener("pointerup", e => finish(e));
  wrap.addEventListener("pointercancel", e => finish(e, true));
  // Ignore bubbled loss of a card's implicit capture when taking over its drag.
  wrap.addEventListener("lostpointercapture", e => { if (e.target === wrap) finish(e, true); });
}

function renderDaily(o, byDay) {
  const sel = o.selectedDay && o.selectedDay >= o.weekStart && o.selectedDay <= addDays(o.weekStart, 6)
    ? o.selectedDay : o.weekStart;
  const chips = h("div", { class: "day-chips", role: "tablist" });
  for (let d = 0; d < 7; d++) {
    const day = addDays(o.weekStart, d);
    const n = dayCount(o, byDay[day] || []);
    const reserved = o.dayCountMode === "booked";
    const label = reserved ? "예약" : "예약 가능", unit = reserved ? "명" : "건";
    chips.append(h("button", { class: `chip ${day === sel ? "active" : ""}`, role: "tab",
      "aria-label": `${fmtDate(day)}, ${label} ${n}${unit}`,
      "aria-selected": String(day === sel), onclick: () => o.onDay?.(day) },
    h("span", {}, DAYS[d]), h("strong", {}, day.slice(8)), h("em", {}, reserved ? `${n}명` : String(n))));
  }
  const list = (byDay[sel] || []);
  const mode = !o.mobileListOnly && o.mobileView === "timeline" ? "timeline" : "list";
  const changeView = (value) => o.onViewChange?.(value);
  const toggle = h("div", { class: "mobile-view-toggle", role: "group", "aria-label": "일정 보기 방식" },
    h("button", { type: "button", class: mode === "list" ? "btn primary" : "btn",
      "aria-pressed": String(mode === "list"), onclick: () => changeView("list") }, "목록 보기"),
    h("button", { type: "button", class: mode === "timeline" ? "btn primary" : "btn",
      "aria-pressed": String(mode === "timeline"), onclick: () => changeView("timeline") }, "일간 시간표 보기"));
  const cards = h("div", { class: "cards" }, list.map((s) =>
    h("button", { class: `card ${slotClass(s)}`, onclick: () => o.onSlot(s), dataset: { slotId: s.id } },
      h("span", { class: "slot-time" }, `${fmtTime(s.start_at)} – ${fmtTime(s.end_at)}`),
      h("span", { class: "slot-meta" }, slotLabel(s)),
      s.location ? h("span", { class: "slot-loc" }, s.location) : null,
      o.extra ? o.extra(s) : null)));
  return h("div", { class: "daily" }, chips,
    h("h3", { class: "daily-title", tabindex: "-1" }, `${fmtDate(sel)} · 일정`),
    o.mobileListOnly || o.hideViewToggle ? null : toggle,
    list.length ? (mode === "timeline" ? renderDailyTimeline(o, list, sel) : cards)
      : h("p", { class: "empty" }, "이 날은 등록된 일정이 없습니다. 다른 날짜를 선택해 주세요."));
}

// On narrow screens display one day on a true time axis instead of squeezing
// the seven-column desktop calendar into a phone-width viewport.
function renderDailyTimeline(o, slots, day) {
  const starts = slots.map((s) => kstParts(s.start_at));
  const ends = slots.map((s) => kstParts(s.end_at));
  const minH = Math.max(0, Math.min(...starts.map((v) => v.hour)) - 1);
  const maxH = Math.min(24, Math.max(...ends.map((v) => v.hour + (v.minute ? 1 : 0))) + 1);
  const pxPerMinute = 1.6; // 30 min = 48 px; 60 min = 96 px
  const height = (maxH - minH) * 60 * pxPerMinute;
  const axis = h("div", { class: "day-timeline", role: "group",
    "aria-label": `${fmtDate(day)} 일간 시간표` });
  axis.style.height = `${height}px`;
  for (let hour = minH; hour <= maxH; hour++) {
    const line = h("div", { class: "day-timeline-hour" },
      h("span", {}, `${String(hour).padStart(2, "0")}:00`));
    line.style.top = `${(hour - minH) * 60 * pxPerMinute}px`;
    axis.append(line);
  }
  for (const s of slots) {
    const start = kstParts(s.start_at), end = kstParts(s.end_at);
    const from = (start.hour - minH) * 60 + start.minute;
    const to = (end.hour - minH) * 60 + end.minute;
    const button = h("button", { type: "button",
      class: `day-timeline-slot ${slotClass(s)}`,
      onclick: () => o.onSlot(s), dataset: { slotId: s.id },
      "aria-label": `${fmtDate(day)} ${start.time}부터 ${end.time}까지 ${slotLabel(s)}` },
    h("span", { class: "slot-time" }, `${start.time}–${end.time}`),
    h("span", { class: "slot-meta" }, slotLabel(s)));
    button.style.top = `${from * pxPerMinute}px`;
    button.style.height = `${Math.max(44, (to - from) * pxPerMinute - 2)}px`;
    if (sharingLane(s, slots)) {
      button.style.width = "calc((100% - 64px) / 2 - 4px)";
      if (s.event_type === "lecture") button.style.left = "calc(64px + (100% - 64px) / 2)";
    }
    axis.append(button);
  }
  return axis;
}

export function weekNav(weekStart, onChange) {
  return h("div", { class: "week-nav" },
    h("button", { class: "btn", onclick: () => onChange(addDays(weekStart, -7)), "aria-label": "이전 주" }, "‹ 이전"),
    h("strong", {}, `${fmtDate(weekStart)} – ${fmtDate(addDays(weekStart, 6))}`),
    h("button", { class: "btn", onclick: () => onChange(addDays(weekStart, 7)), "aria-label": "다음 주" }, "다음 ›"));
}
