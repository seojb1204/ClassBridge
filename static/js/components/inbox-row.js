import { h } from "../ui.js";
import { kstParts, todayKst } from "../time.js";

// A single presentation for both the header preview and the full inbox.
export function inboxRow(item) {
  const label = item.booking_summary?.student_name;
  const link = h("a", { class: `inbox-row-link ${item.read ? "is-read" : "is-unread"}`, href: item.url });
  const raw = item.arrived_at;
  let short = item.arrived_on || item.created_on || "";
  let full = short;
  if (raw && !Number.isNaN(Date.parse(raw))) {
    const p = kstParts(raw);
    short = p.date === todayKst() ? p.time : `${p.date.slice(5).replace('-', '/')} ${p.time}`;
    full = `${p.date} ${p.time} (한국시간)`;
  }
  link.append(
    h("div", { class: "inbox-item-heading" },
      h("h3", {}, item.read ? null : h("span", { class: "inbox-unread-dot", "aria-hidden": "true" }),
        item.title, label ? ` · ${label}` : null),
      h("time", { class: "inbox-arrival", dateTime: raw || "", title: `알림 시각 ${full}`,
        "aria-label": `알림 시각 ${full}` }, short)),
    h("p", { class: "inbox-summary" }, item.body),
    h("span", { class: "sr-only" }, `${item.read ? "읽음" : "읽지 않음"}. 관련 내용 열기`));
  return link;
}
