// 주간 시간표(PC) / 일별 카드 목록(모바일) 공용 컴포넌트.
import { addDays, fmtDate, fmtTime, kstParts } from "../time.js";
import { h } from "../ui.js";

const MOBILE = window.matchMedia("(max-width: 720px)");
const DAYS = ["월", "화", "수", "목", "금", "토", "일"];
const STEP = 15; // 분 단위 행 높이

export function isMobile() { return MOBILE.matches; }

export function onLayoutChange(cb) {
  MOBILE.addEventListener("change", cb);
  return () => MOBILE.removeEventListener("change", cb);
}

function slotClass(s) {
  if (s.managerState === "reserved") return "slot reserved";
  if (s.status === "cancelled") return "slot cancelled";
  if (s.mine) return "slot mine";
  if (s.bookable === false && s.reason) return "slot closed";
  return "slot open";
}

function slotLabel(s) {
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
 */
export function renderCalendar(o) {
  const byDay = {};
  for (const s of o.slots) (byDay[kstParts(s.start_at).date] ||= []).push(s);
  return isMobile() ? renderDaily(o, byDay) : renderWeekly(o, byDay);
}

function renderWeekly(o, byDay) {
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
  const grid = h("div", { class: "week-grid", role: "grid", "aria-label": "주간 상담 시간표" });
  grid.style.gridTemplateRows = `auto repeat(${rows}, 18px)`;
  grid.append(h("div", { class: "corner" }));
  for (let d = 0; d < 7; d++) {
    const day = addDays(o.weekStart, d);
    const head = h("div", { class: "day-head" }, h("strong", {}, DAYS[d]), " ", day.slice(5).replace("-", "/"));
    head.style.gridColumn = String(d + 2);
    grid.append(head);
  }
  for (let hr = minH; hr < maxH; hr++) {
    const label = h("div", { class: "hour" }, `${String(hr).padStart(2, "0")}:00`);
    label.style.gridRow = `${((hr - minH) * 60) / STEP + 2} / span ${60 / STEP}`;
    grid.append(label);
    for (let d = 0; d < 7; d++) {
      const cell = h("div", { class: "cell" });
      cell.style.gridRow = `${((hr - minH) * 60) / STEP + 2} / span ${60 / STEP}`;
      cell.style.gridColumn = String(d + 2);
      grid.append(cell);
    }
  }
  for (let d = 0; d < 7; d++) {
    for (const s of byDay[addDays(o.weekStart, d)] || []) {
      const a = kstParts(s.start_at), b = kstParts(s.end_at);
      const start = (a.hour - minH) * 60 + a.minute;
      const end = (b.hour - minH) * 60 + b.minute;
      const btn = h("button", { class: slotClass(s), onclick: () => o.onSlot(s),
        "aria-label": `${fmtDate(a.date)} ${a.time}-${b.time} ${slotLabel(s)}`, dataset: { slotId: s.id } },
        h("span", { class: "slot-time" }, `${a.time}–${b.time}`),
        h("span", { class: "slot-meta" }, slotLabel(s)),
        o.extra ? o.extra(s) : null);
      btn.style.gridRow = `${start / STEP + 2} / ${Math.max(end / STEP + 2, start / STEP + 3)}`;
      btn.style.gridColumn = String(d + 2);
      grid.append(btn);
    }
  }
  return h("div", { class: "week-wrap" }, grid);
}

function renderDaily(o, byDay) {
  const sel = o.selectedDay && o.selectedDay >= o.weekStart && o.selectedDay <= addDays(o.weekStart, 6)
    ? o.selectedDay : o.weekStart;
  const chips = h("div", { class: "day-chips", role: "tablist" });
  for (let d = 0; d < 7; d++) {
    const day = addDays(o.weekStart, d);
    const n = (byDay[day] || []).filter((s) => o.countMode === "total"
      ? s.status !== "cancelled" : s.bookable || s.mine).length;
    const label = o.countMode === "total" ? "상담" : "선택 가능";
    chips.append(h("button", { class: `chip ${day === sel ? "active" : ""}`, role: "tab",
      "aria-label": `${fmtDate(day)}, ${label} ${n}건`,
      "aria-selected": String(day === sel), onclick: () => o.onDay?.(day) },
    h("span", {}, DAYS[d]), h("strong", {}, day.slice(8)), h("em", {}, String(n))));
  }
  const list = (byDay[sel] || []);
  return h("div", { class: "daily" }, chips,
    h("h3", { class: "daily-title" }, fmtDate(sel)),
    list.length ? h("div", { class: "cards" }, list.map((s) =>
      h("button", { class: `card ${slotClass(s)}`, onclick: () => o.onSlot(s), dataset: { slotId: s.id } },
        h("span", { class: "slot-time" }, `${fmtTime(s.start_at)} – ${fmtTime(s.end_at)}`),
        h("span", { class: "slot-meta" }, slotLabel(s)),
        s.location ? h("span", { class: "slot-loc" }, s.location) : null,
        o.extra ? o.extra(s) : null)))
      : h("p", { class: "empty" }, "이 날은 등록된 상담 시간이 없습니다. 다른 날짜를 선택해 주세요."));
}

export function weekNav(weekStart, onChange) {
  return h("div", { class: "week-nav" },
    h("button", { class: "btn", onclick: () => onChange(addDays(weekStart, -7)), "aria-label": "이전 주" }, "‹ 이전"),
    h("strong", {}, `${fmtDate(weekStart)} – ${fmtDate(addDays(weekStart, 6))}`),
    h("button", { class: "btn", onclick: () => onChange(addDays(weekStart, 7)), "aria-label": "다음 주" }, "다음 ›"));
}
