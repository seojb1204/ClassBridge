import { h, modal, toast } from "../ui.js";
import { qrActions } from "./qr-actions.js";

export function surveyUrl(s) {
  return `${location.origin}/#/surveys/${s.access_mode === "anonymous" ? `public/${s.public_token}` : `take/${s.id}`}`;
}

export async function showSurveyQr(s) {
  const url = surveyUrl(s);
  const warning = h("p", { class: "error-box", hidden: true }, "QR을 불러오지 못했습니다. 창을 닫고 다시 열어 주세요.");
  await modal("설문 QR 공유", h("div", { class: "survey-qr" },
    h("h3", {}, s.title),
    h("img", { src: `/api/surveys/${s.id}/qr.png`, alt: "학생 참여용 설문 QR 코드", width: 280, height: 280,
      onerror: () => { warning.hidden = false; } }), warning,
    h("p", {}, s.access_mode === "anonymous" ? "로그인 없이 바로 응답합니다. 링크를 가진 누구나 참여할 수 있습니다."
      : "Google 로그인 후 해당 설문으로 바로 이동합니다. 이미 로그인했다면 바로 응답합니다."),
    h("p", { class: "muted" }, "카메라로 QR을 찍고 표시된 링크를 여세요."),
    h("div", { class: "actions" },
      qrActions(`/api/surveys/${s.id}/qr.png`, `survey-${s.id}-qr.png`),
      h("button", { class: "btn", onclick: async () => {
        try { await navigator.clipboard.writeText(url); toast("설문 링크를 복사했습니다", "success"); }
        catch { toast("아래 링크를 길게 눌러 복사해 주세요."); }
      } }, "링크 복사")),
    h("a", { class: "survey-share-url", href: url, target: "_blank", rel: "noopener" }, url)),
  [{ label: "닫기", value: true }]);
}
