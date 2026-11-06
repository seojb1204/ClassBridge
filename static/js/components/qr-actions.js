import { h, toast } from "../ui.js";

export function qrActions(url, filename) {
  const actions = h("div", { class: "actions" },
    h("a", { class: "btn primary", href: url, download: filename }, "QR 이미지 저장(PNG)"),
    h("a", { class: "btn", href: url, target: "_blank", rel: "noopener" }, "이미지 크게 보기"));
  let supported = false;
  try {
    supported = typeof navigator.canShare === "function" && typeof navigator.share === "function"
      && navigator.canShare({ files: [new File([""], filename, { type: "image/png" })] });
  } catch { /* PNG download remains available when native sharing is restricted. */ }
  if (supported) actions.append(h("button", { class: "btn", type: "button", onclick: async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const response = await fetch(url, { credentials: "same-origin" });
      if (!response.ok || !response.headers.get("Content-Type")?.startsWith("image/png")) throw new Error();
      const file = new File([await response.blob()], filename, { type: "image/png" });
      await navigator.share({ files: [file], title: "ClassBridge QR" });
    } catch (error) {
      if (error.name !== "AbortError") toast("공유할 수 없습니다. ‘QR 이미지 저장(PNG)’ 또는 ‘이미지 크게 보기’를 이용해 주세요.", "error");
    } finally { button.disabled = false; }
  } }, "공유하기"));
  return h("div", {}, actions,
    h("p", { class: "hint" }, "저장한 PNG는 사진 앱이나 다운로드 폴더에서 열 수 있습니다. 이미지 크게 보기에서 길게 눌러 저장할 수도 있습니다."));
}
