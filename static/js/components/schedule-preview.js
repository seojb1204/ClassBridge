import { addDays, kstParts } from "../time.js";
import { h } from "../ui.js";

export function schedulePreview(slots) {
  const groups = {};
  for (const slot of slots) (groups[kstParts(slot.start_at).date] ||= []).push(slot);
  const dates = Object.keys(groups).sort();
  if (!dates.length) return h("p", {}, "등록할 상담 시간이 없습니다.");
  let selected = dates[0], month = selected.slice(0, 7);
  const months = [...new Set(dates.map(d => d.slice(0, 7)))];
  const root = h("section", { class: "schedule-preview", "aria-label": "등록 예정 달력" });
  function draw() {
    const first = month + "-01", offset = (new Date(first + "T12:00:00+09:00").getUTCDay() + 6) % 7;
    const grid = h("div", { class: "preview-month" });
    for (const day of ["월", "화", "수", "목", "금", "토", "일"]) grid.append(h("span", { class: "muted" }, day));
    for (let i = 0; i < offset; i++) grid.append(h("span", {}));
    for (let day = first; day.slice(0, 7) === month; day = addDays(day, 1)) {
      const date = day, count = groups[date]?.length || 0;
      grid.append(h("button", { type: "button", disabled: !count, "aria-pressed": String(selected === date),
        "aria-label": `${date} · ${count}개 예정`, onclick: () => { selected = date; draw(); } },
        h("strong", {}, String(+date.slice(-2))), count ? h("small", {}, `${count}개`) : null));
    }
    const index = months.indexOf(month);
    root.replaceChildren(h("p", {}, `총 ${dates.length}일 · 상담 ${slots.length}개 등록 예정`),
      h("div", { class: "row" },
        h("button", { type: "button", class: "btn small", disabled: index === 0, onclick: () => { month = months[index - 1]; selected = dates.find(d => d.startsWith(month)); draw(); } }, "이전 달"),
        h("strong", {}, month.replace("-", "년 ") + "월"),
        h("button", { type: "button", class: "btn small", disabled: index === months.length - 1, onclick: () => { month = months[index + 1]; selected = dates.find(d => d.startsWith(month)); draw(); } }, "다음 달")), grid,
      h("div", { class: "preview-times", "aria-live": "polite" }, h("h3", {}, `${selected} · ${groups[selected].length}개 예정`),
        h("ul", { class: "plain" }, ...groups[selected].map(s => h("li", {}, `${kstParts(s.start_at).time} ~ ${kstParts(s.end_at).time}`)))));
  }
  draw();
  return root;
}
