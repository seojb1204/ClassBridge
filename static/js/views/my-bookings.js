// 학생: 내 예약 목록 · 취소
import { watchRefresh } from "../live-refresh.js";
import { get, post } from "../api.js";
import { downloadConsultationIcs } from "../calendar-ics.js";
import { fmtDateTime, fmtDateTimeRange } from "../time.js";
import { STATUS_LABEL, badge, busy, confirmAction, empty, errorToast, h, modal, mount, toast } from "../ui.js";

export async function render(root) {
  await draw(root);
  watchRefresh(root, () => draw(root));
}

async function draw(root) {
  const [list, counts] = await Promise.all([get("/api/bookings/mine"), get("/api/support/counts").catch(() => ({mine: 0}))]);
  mount(root, h("div", { class: "page-head" }, h("h1", {}, "내 예약")),
    counts.mine ? h("a", { class: "notice", href: "#/help/mine" }, `문의 답변·상태 변경 ${counts.mine}건 확인하기`) : null,
    list.length ? h("div", { class: "cards" }, list.map((b) => item(root, b))) : h("div", {}, empty("예약 내역이 없습니다."), h("a", { class: "btn primary", href: "#/booking" }, "상담 예약하기")));
}

function item(root, b) {
  const cancelBtn = h("button", { class: "btn danger" }, "예약 취소");
  cancelBtn.addEventListener("click", busy(cancelBtn, async () => {
    if (!(await confirmAction("예약 취소", `${fmtDateTime(b.slot.start_at)} 상담을 취소할까요?`, "취소하기", true))) return;
    try {
      await post(`/api/bookings/${b.id}/cancel`, {});
      toast("예약을 취소했습니다.", "success");
    } catch (e) { errorToast(e); }
    await render(root);
  }));
  return h("div", { class: `card booking ${b.status}`, dataset: { bookingId: b.id } },
    h("div", { class: "row" }, h("strong", {}, fmtDateTimeRange(b.slot.start_at, b.slot.end_at)), badge(b.status === "cancelled" && b.cancel_reason === "예약 변경" ? "변경 전 기록" : STATUS_LABEL[b.status], b.status)),
    h("span", { class: "muted" }, b.slot.kind === "group" ? "단체 상담" : "개인 상담",
      b.slot.location ? ` · ${b.slot.location}` : ""),
    h("p", { class: "muted" },
      `${({career: "진로", employment: "취업", academics: "학업", campus: "학교생활", other: "기타"})[b.consultation_type] || "기타"}` +
      ` · ${b.consultation_mode === "online" ? "온라인" : "대면"}`),
    b.unread_update ? badge(b.status === "cancelled" ? "취소됨 · 미확인" : "변경됨 · 미확인", "new") : null,
    b.latest_update_id ? h("button", { class: "btn", onclick: () => showUpdates(root, b).catch(errorToast) }, "변경 내용 확인") : null,
    b.slot.note ? h("p", { class: "muted" }, `상담 안내: ${b.slot.note}`) : null,
    b.topic ? h("p", {}, b.topic) : null,
    b.cancel_reason ? h("p", { class: "muted" }, b.cancel_reason === "예약 변경"
      ? "이전 방식으로 변경된 예약의 과거 기록입니다." : `취소 사유: ${b.cancel_reason}`) : null,
    b.status === "booked" ? h("div", { class: "actions" },
      h("a", { class: "btn primary", href: "#/booking" }, "취소 없이 시간 변경"),
      h("button", { class: "btn", onclick: () => downloadConsultationIcs(b) }, "내 달력에 추가"), cancelBtn) : null);
}


const updateLabels = { book_by_staff: "교수자가 새 예약을 등록했습니다", cancel_by_staff: "교수자가 예약을 취소했습니다",
  cancel_by_slot: "상담 일정이 취소되었습니다", rescheduled: "예약 시간이 변경되었습니다", slot_changed: "상담 장소·안내가 변경되었습니다" };
function describeUpdate(event) {
  if (event.action !== "rescheduled") return event.detail;
  const times = [...event.detail.matchAll(/\[([^~]+)~([^\]]+)\]/g)];
  if (times.length !== 2) return event.detail;
  const reason = event.detail.includes("; ") ? event.detail.split("; ").slice(1).join("; ") : "";
  return `변경 전: ${fmtDateTime(times[0][1])} → 변경 후: ${fmtDateTime(times[1][1])}${reason ? ` · 사유: ${reason}` : ""}`;
}
async function showUpdates(root, booking) {
  const events = await get(`/api/bookings/${booking.id}/updates`);
  const seen = events.at(-1)?.id;
  await modal("예약 변경 내용", h("div", {},
    h("p", {}, `현재 일정: ${fmtDateTime(booking.slot.start_at)} · ${booking.slot.location || "장소 미정"}`),
    ...events.map(e => h("section", { class: "panel" }, h("strong", {}, updateLabels[e.action]),
      h("p", { class: "muted" }, fmtDateTime(e.at)), h("p", {}, describeUpdate(e))))),
    [{ label: "확인했어요", primary: true, handler: async () => {
      if (seen) await post(`/api/bookings/${booking.id}/updates/${seen}/read`);
      return true;
    } }, { label: "나중에 확인", value: null }]);
  if (root.isConnected) await draw(root);
}
