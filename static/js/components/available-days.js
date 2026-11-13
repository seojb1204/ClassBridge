import { get } from "../api.js";
import { fmtDate } from "../time.js";
import { h } from "../ui.js";

export async function loadAvailableDays() {
  try {
    const days = await get("/api/slots/available-days");
    return days.map(({ date, count }) => [date, count]);
  } catch { return null; }
}

export function availableDaysPanel(days, selectDay) {
  const panel = h("section", { class: "available-days", "aria-label": "예약 가능한 상담 일정" },
    h("h2", {}, "예약 가능한 상담 일정"));
  if (days === null) { panel.append(h("p", {}, "일정을 불러오지 못했습니다. 새로고침해 주세요.")); return panel; }
  if (!days.length) { panel.append(h("p", {}, "현재 예약 가능한 상담 시간이 없습니다.")); return panel; }
  const buttons = h("div", { class: "available-day-buttons" });
  const draw = (all = false) => buttons.replaceChildren(...(all ? days : days.slice(0, 3)).map(([day, count]) =>
    h("button", { type: "button", class: "btn", onclick: () => selectDay(day) }, `${fmtDate(day)} · ${count}개 시간`)));
  draw();
  panel.append(buttons);
  if (days.length > 3) panel.append(h("button", { type: "button", class: "btn small", onclick: (e) => {
    const all = e.currentTarget.getAttribute("aria-expanded") !== "true";
    draw(all); e.currentTarget.setAttribute("aria-expanded", String(all));
    e.currentTarget.textContent = all ? "가까운 일정만 보기" : "전체 일정 보기";
  }, "aria-expanded": "false" }, "전체 일정 보기"));
  return panel;
}
