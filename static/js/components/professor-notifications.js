import { get } from "../api.js";
import { fmtDateTime } from "../time.js";
import { h } from "../ui.js";

export function professorNotifications() {
  const box = h("section", { class: "panel notification-summary", "aria-label": "내 예약 알림 상태" });
  async function draw() {
    const refresh = h("button", { type: "button", class: "btn small", onclick: draw }, "상태 새로고침");
    try {
      const data = await get("/api/admin/notification-summary");
      const rows = Object.entries(data).map(([channel, status]) => {
        let label = status.paused ? "일시 중지" : !status.enabled ? "미설정 · 관리자 설정 필요" : !status.recipient ? "이 계정은 알림 수신 대상으로 지정되지 않았습니다" : "발송 사용 중";
        if (status.enabled && status.recipient && channel === "push") {
          label = !status.session_registered ? "이 로그인에서 알림 등록 필요" : "이 로그인에서 수신 등록됨";
          if (!("Notification" in window)) label = "이 브라우저는 휴대폰 알림을 지원하지 않습니다";
          else if (Notification.permission !== "granted") label = "이 브라우저의 알림 허용 필요";
        }
        return h("div", {}, h("strong", {}, channel === "gmail" ? "이메일" : "휴대폰"), h("span", {}, ` · ${label}`),
          status.attention ? h("p", { class: "warn" }, `확인 필요 ${status.attention}건 · 관리자에게 발송 상태 확인을 요청하세요.`) : null,
          status.pending ? h("p", {}, `발송 대기 ${status.pending}건`) : null,
          h("small", { class: "muted" }, status.last_success ? `최근 발송 처리 ${fmtDateTime(status.last_success)}` : "발송 성공 기록 없음"));
      });
      box.replaceChildren(h("h2", {}, "내 예약 알림 상태"), ...rows,
        h("p", { class: "hint" }, "발송 처리는 실제 수신·읽음 확인과 다릅니다. 로그인 만료 후에는 휴대폰 알림을 다시 등록해 주세요."), refresh);
    } catch {
      box.replaceChildren(h("h2", {}, "내 예약 알림 상태"), h("p", {}, "상태를 불러오지 못했습니다. 예약 기능은 계속 사용할 수 있습니다."), refresh);
    }
  }
  draw();
  return box;
}
