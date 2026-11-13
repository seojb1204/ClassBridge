import { get, post, put } from "../api.js";
import { notificationHelp } from './notification-help.js';
import { confirmAction, errorToast, h, mount, toast } from "../ui.js";

const labels = { pending: "발송 대기", sending: "발송 중", sent: "서비스 접수 완료", uncertain: "발송 여부 확인 필요", reauth: "인증·키 확인 필요", failed: "발송 실패", skipped: "발송 제외" };
export async function notificationStatus() {
  const box = h("section", { class: "panel" });
  async function draw() {
    try {
      const status = await get("/api/admin/notifications");
      mount(box, h("h2", {}, "예약 알림 상태"),
        h("p", {}, `이메일 ${status.email_paused ? "일시 중지" : status.enabled ? "사용" : "미설정"} · 휴대폰 ${status.push_enabled ? "사용" : "미설정"} · 수신 가능한 기기 ${status.push_devices}개`),
        h("p", { class: "hint" }, "접수 완료는 메일함·휴대폰의 실제 수신을 보장하지 않습니다. 인증 오류는 서버 설정을 고친 뒤 재시도하세요. 발송 여부가 불명확하면 발신함·수신 기기를 먼저 확인하세요."),
        status.enabled ? h("button", { class: "btn", onclick: async () => {
          const pause = !status.email_paused;
          if (!await confirmAction("예약 이메일", pause ? "교수자 휴대폰에서 실제 수신을 확인했나요? 예약 이메일을 일시 중지합니다." : "예약 이메일을 다시 보낼까요?", pause ? "일시 중지" : "재개")) return;
          try { await put("/api/admin/email-delivery", { paused: pause }); await draw(); } catch (err) { errorToast(err); }
        } }, status.email_paused ? "예약 이메일 재개" : "예약 이메일 일시 중지") : null,
        h("button", { class: "btn", onclick: draw }, "상태 새로고침"),
        ...status.items.map((item) => h("div", { class: "card" },
          h("strong", {}, `${item.channel === "push" ? "휴대폰" : "이메일"} · ${item.booking_id ? `예약 #${item.booking_id}` : '예약 일정 알림'} · ${labels[item.status] || item.status}`),
          h("span", { class: "muted" }, `${item.attempts}회 시도 · ${item.error_code || "대기 중"}`),
          h("p", { class: "notification-help" }, notificationHelp(item)),
          ["uncertain", "reauth", "failed"].includes(item.status) ? h("div", { class: "actions" },
            ...[["retry", "재시도"], ["confirmed_sent", "수신 확인됨"], ["skip", "발송 제외"]].map(([action, label]) => h("button", { class: "btn small", onclick: async () => {
              if (!await confirmAction("알림 처리", `${label} 처리할까요? 발신함·기기를 먼저 확인하세요. 재시도하면 이미 전달된 알림이 중복으로 전달될 수 있습니다.`, "확인")) return;
              try { await post(`/api/admin/notifications/${item.id}/resolve`, { action, acknowledge: true }); await draw(); toast("처리했습니다", "success"); }
              catch (e) { errorToast(e); }
            } }, label))) : null)));
    } catch (e) { mount(box, h("p", {}, "알림 상태를 불러오지 못했습니다.")); errorToast(e); }
  }
  await draw();
  return box;
}
