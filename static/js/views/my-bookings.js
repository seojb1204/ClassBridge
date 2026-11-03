// 학생: 내 예약 목록 · 취소
import { get, post } from "../api.js";
import { fmtDateTime } from "../time.js";
import { STATUS_LABEL, badge, busy, confirmAction, empty, errorToast, h, mount, toast } from "../ui.js";

export async function render(root) {
  const list = await get("/api/bookings/mine");
  mount(root, h("div", { class: "page-head" }, h("h1", {}, "내 예약")),
    list.length ? h("div", { class: "cards" }, list.map((b) => item(root, b))) : empty("예약 내역이 없습니다."));
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
    h("div", { class: "row" }, h("strong", {}, fmtDateTime(b.slot.start_at)), badge(STATUS_LABEL[b.status], b.status)),
    h("span", { class: "muted" }, b.slot.kind === "group" ? "단체 상담" : "개인 상담",
      b.slot.location ? ` · ${b.slot.location}` : ""),
    h("p", { class: "muted" },
      `${({career: "진로", employment: "취업", academics: "학업", campus: "학교생활", other: "기타"})[b.consultation_type] || "기타"}` +
      ` · ${b.consultation_mode === "online" ? "온라인" : "대면"}`),
    b.topic ? h("p", {}, b.topic) : null,
    b.cancel_reason ? h("p", { class: "muted" }, `취소 사유: ${b.cancel_reason}`) : null,
    b.status === "booked" ? h("div", { class: "actions" }, cancelBtn,
      h("a", { class: "btn", href: "#/booking" }, "시간 변경")) : null);
}
