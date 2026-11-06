import { h, modal } from "../ui.js";
import { qrActions } from "./qr-actions.js";

export function siteQrButton(className = "btn") {
  return h("button", { type: "button", class: className, onclick: showSiteQr }, "사이트 접속 QR");
}

async function showSiteQr() {
  const warning = h("p", { class: "error-box", hidden: true }, "QR을 불러오지 못했습니다. 다시 열어 주세요.");
  await modal("ClassBridge 사이트 접속 QR", h("div", { class: "survey-qr" },
    h("img", { src: "/api/site/qr.png", alt: "ClassBridge 사이트 접속 QR 코드", width: 280, height: 280,
      onerror: () => { warning.hidden = false; } }), warning,
    h("p", {}, "카메라로 QR을 찍으면 ClassBridge 첫 화면으로 이동합니다."),
    h("p", { class: "muted" }, "개인 계정이나 예약 정보는 포함하지 않습니다."),
    qrActions("/api/site/qr.png", "classbridge-site-qr.png")),
  [{ label: "닫기", value: true }]);
}
