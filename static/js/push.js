import { del, get, post } from "./api.js";
import { can } from "./state.js";
import { errorToast, h, modal, toast } from "./ui.js";

function publicKey(value) {
  return Uint8Array.from(atob(value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - value.length % 4) % 4)), (c) => c.charCodeAt(0));
}

export function pushButton() {
  if (!can("booking:manage")) return null;
  return h("button", { class: "btn small", onclick: async () => {
    try {
      if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
        toast("Android Chrome에서 열어 주세요. 이 브라우저는 휴대폰 알림을 지원하지 않습니다."); return;
      }
      const config = await get("/api/admin/push-config");
      if (!config.enabled) { toast("휴대폰 알림이 아직 설정되지 않았거나 지정된 교수자 계정이 아닙니다."); return; }
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      const action = await modal("휴대폰 알림", h("div", {},
        h("p", {}, "예약 신청·변경·취소 알림과 상담 시각을 이 기기에서 받습니다. 학생 이름과 상담 내용은 표시하지 않습니다."),
        h("p", {}, "로그아웃·로그인 만료 후에는 다시 알림을 켜 주세요. 통신·절전 설정에 따라 지연될 수 있습니다.")),
      [{ label: "닫기", value: null }, ...(subscription ? [{ label: "알림 끄기", value: "off" }] : []),
        { label: "이 기기에서 알림 받기", value: "on", primary: true }]);
      if (action === "off") {
        await del("/api/admin/push-subscription");
        await subscription.unsubscribe();
        toast("이 로그인 세션의 알림을 껐습니다");
      } else if (action === "on") {
        if (await Notification.requestPermission() !== "granted") { toast("Chrome 또는 휴대폰 설정에서 알림을 허용해 주세요."); return; }
        const sub = subscription || await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: publicKey(config.public_key) });
        await post("/api/admin/push-subscription", sub.toJSON());
        toast("이 기기의 알림 수신을 등록했습니다", "success");
      }
    } catch (e) { errorToast(e); }
  } }, "휴대폰 알림");
}
