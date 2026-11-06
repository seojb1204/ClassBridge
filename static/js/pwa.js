import { can } from "./state.js";
import { h, modal } from "./ui.js";

let promptEvent = null;
let installedThisVisit = false;
export const isStandalone = () => window.matchMedia("(display-mode: standalone)").matches;

function updateButtons() {
  document.querySelectorAll(".pwa-install").forEach((button) => {
    button.hidden = isStandalone() || installedThisVisit || !can("booking:manage");
    button.textContent = promptEvent ? "앱 설치" : "앱 설치 안내";
  });
}

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  promptEvent = event;
  updateButtons();
});
window.addEventListener("appinstalled", () => {
  promptEvent = null;
  installedThisVisit = true;
  updateButtons();
});
window.matchMedia("(display-mode: standalone)").addEventListener("change", updateButtons);

export function initializePwa() {
  if ("serviceWorker" in navigator && window.isSecureContext) {
    navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).catch(() => {
      // Installation must never prevent normal online booking or login.
    });
  }
}

export function installButton(className = "") {
  if (!can("booking:manage") || isStandalone()) return null;
  const button = h("button", { type: "button", class: `pwa-install ${className}`,
    hidden: installedThisVisit,
    onclick: async () => {
      if (promptEvent) {
        const pending = promptEvent;
        promptEvent = null;
        button.disabled = true;
        try { await pending.prompt(); await pending.userChoice; }
        catch (_) { await showInstructions(); }
        finally { button.disabled = false; updateButtons(); }
      } else await showInstructions();
    } }, promptEvent ? "앱 설치" : "앱 설치 안내");
  return button;
}

async function showInstructions() {
  await modal("안드로이드 앱 설치", h("div", {},
    h("p", {}, "Chrome에서 이 사이트를 열고 오른쪽 위 ⋮ 메뉴의 ‘홈 화면에 추가’ 또는 ‘앱 설치’를 선택해 주세요."),
    h("p", {}, "카카오톡 등의 내부 브라우저에서는 ‘다른 브라우저로 열기’로 Chrome에 접속해 주세요. 이미 설치했다면 홈 화면의 ClassBridge 아이콘을 실행하세요."),
    h("p", {}, "교수자 계정으로 로그인하면 현재 예약된 전체 목록부터 확인합니다. 인터넷 연결이 필요합니다. 운영자가 알림을 설정한 뒤 ‘휴대폰 알림’에서 이 기기의 수신을 켤 수 있습니다.")),
    [{ label: "확인", value: true, primary: true }]);
}
