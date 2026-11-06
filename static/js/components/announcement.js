import { get, put } from "../api.js";
import { can } from "../state.js";
import { errorToast, field, h, modal, select, toast } from "../ui.js";

// A notice-loading failure must not prevent booking.
export async function loadAnnouncement() {
  try { return (await get("/api/announcement")).announcement; }
  catch (_) { return undefined; }
}

export function announcementPanel(value, refresh) {
  const manage = can("announcement:manage");
  if (value === undefined) return h("p", { class: "muted" }, "공지를 불러오지 못했습니다. 새로고침해 주세요.");
  if (!manage && !value) return null;
  return h("section", { class: "announcement-panel", "aria-label": "공지사항" },
    h("div", { class: "announcement-head" }, h("strong", {}, "공지사항"),
      manage ? h("span", { class: "muted" }, value.published ? "게시 중" : "학생에게 숨김") : null,
      manage ? h("button", { class: "btn small", onclick: () => edit(value, refresh) },
        value.revision ? "공지 수정" : "공지 작성") : null),
    value.title ? h("h2", {}, value.title) : null,
    value.body ? h("p", { class: "announcement-body" }, value.body)
      : h("p", { class: "muted" }, "학생 예약 화면 위에 표시할 대표 공지를 작성하세요."));
}

async function edit(value, refresh) {
  const title = h("input", { type: "text", maxlength: 100, value: value.title });
  const body = h("textarea", { rows: 6, maxlength: 2000 }, value.body);
  const published = select([["false", "숨김 (초안 저장)"], ["true", "게시 (학생에게 표시)"]], String(value.published));
  const result = await modal("공지사항 편집", h("div", {},
    field("공지 제목", title, "최대 100자"), field("공지 내용", body, "최대 2,000자 · 줄바꿈 가능"),
    field("공개 상태", published),
    h("p", { class: "muted" }, "게시하면 모든 로그인한 학생의 상담 예약 화면에 표시됩니다. 개인별 상담 내용은 쓰지 마세요.")), [
    { label: "닫기", value: false },
    { label: "공지 저장", primary: true, handler: async () => {
      const isPublished = published.value === "true";
      if (isPublished && (!title.value.trim() || !body.value.trim())) {
        toast("게시하려면 제목과 내용을 입력하세요.", "error"); return false;
      }
      try {
        await put("/api/announcement", { title: title.value, body: body.value,
          published: isPublished, revision: value.revision });
        toast(isPublished ? "공지를 게시했습니다." : "공지를 숨김 상태로 저장했습니다.", "success");
        return true;
      } catch (error) { errorToast(error); return false; }
    } },
  ]);
  if (result) await refresh();
}
