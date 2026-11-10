import { get, post, put } from "./api.js";
import { professorNotifications } from "./components/professor-notifications.js";
import { can } from "./state.js";
import { busy, errorToast, field, h, mount, toast } from "./ui.js";

function publicKey(value) {
  return Uint8Array.from(atob(value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - value.length % 4) % 4)), c => c.charCodeAt(0));
}

export function pushButton(extraClass = "") {
  return can("booking:manage") ? h("a", { class: "btn small " + extraClass, href: "#/personal" }, "개인 설정") : null;
}

export async function personalAlerts(root) {
  const [prefs, config] = await Promise.all([get("/api/admin/personal-alerts"), get("/api/admin/push-config")]);
  const check = (key, label) => {
    const input = h("input", { type: "checkbox", checked: prefs[key], name: key });
    return h("label", {}, input, " " + label);
  };
  const at = h("input", { type: "time", value: prefs.at, required: true });
  const save = h("button", { class: "btn primary", type: "submit" }, "저장");
  const form = h("form", { class: "panel grid-form" },
    check("daily", "평일 상담 요약 받기"), field("받을 시각 (한국시간)", at),
    check("reminder", "상담 30분 전 알림"), check("instant", "신청·변경·취소 즉시 알림"),
    check("names", "요약·30분 전 알림에 학생 이름 표시"),
    h("p", { class: "hint" }, "남은 상담이 있는 날에만 요약을 보냅니다. 이름을 표시하면 잠금화면에도 보일 수 있습니다."), save);
  form.addEventListener("submit", busy(save, async e => {
    e.preventDefault();
    const body = { at: at.value };
    for (const key of ["daily", "reminder", "instant", "names"]) body[key] = form.elements[key].checked;
    try { await put("/api/admin/personal-alerts", body); toast("내 알림 설정을 저장했습니다", "success"); }
    catch (err) { errorToast(err); }
  }));
  const box = h("section", { class: "panel" });
  mount(root, h("h1", {}, "개인 설정"), h("h2", {}, "내 알림"), form, box, professorNotifications());
  async function device() {
    mount(box, h("h2", {}, "이 기기의 알림"));
    if (!config.enabled || !("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
      box.append(h("p", {}, config.enabled ? "Android Chrome에서 기기를 등록할 수 있습니다." : "서버에서 휴대폰 알림을 켜 주세요.")); return;
    }
    const reg = await navigator.serviceWorker.getRegistration();
    if (!reg?.active) { box.append(h('p', {}, '알림 준비 중입니다. 잠시 후 개인 설정을 다시 열어 주세요.')); return; }
    const sub = await reg.pushManager.getSubscription();
    const status = sub && await post("/api/admin/push-device-state", { endpoint: sub.endpoint });
    const registered = status?.registered && Notification.permission === "granted";
    box.append(h("p", {}, registered ? "이 기기에 등록됨" : "이 기기의 알림 등록이 필요합니다."));
    const action = (label, fn) => {
      const btn = h("button", { class: "btn" }, label);
      btn.addEventListener("click", busy(btn, async () => { try { await fn(); } catch (err) { errorToast(err); } }));
      box.append(btn);
    };
    if (registered) {
      action("테스트 알림 받기", async () => {
        await post("/api/admin/push-test", { endpoint: sub.endpoint });
        toast("테스트 발송을 접수했습니다. 휴대폰 알림을 확인하세요.", "success");
      });
      action("이 기기 알림 끄기", async () => {
        await post("/api/admin/push-device-remove", { endpoint: sub.endpoint }); await sub.unsubscribe(); await device();
      });
    } else action("이 기기에서 알림 받기", async () => {
      if (await Notification.requestPermission() !== "granted") { toast("휴대폰 설정에서 알림을 허용해 주세요."); return; }
      const subscription = sub || await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: publicKey(config.public_key) });
      await post("/api/admin/push-subscription", subscription.toJSON()); await device();
    });
  }
  try { await device(); } catch (err) { errorToast(err); }
}
