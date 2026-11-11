import { copySiteLink, siteQrButton } from "../components/site-share.js";
import { get, post, put } from "../api.js";
import { can } from "../state.js";
import { go } from "../router.js";
import { fmtDateTime } from "../time.js";
import { badge, busy, empty, errorToast, field, h, mount, select, toast } from "../ui.js";

const categories = [["bug", "오류 신고"], ["feature", "기능 제안"], ["help", "사용 방법"]];
const labels = Object.fromEntries(categories);
const statuses = [["received", "접수"], ["reviewing", "검토 중"], ["completed", "완료"]];
const statusLabels = Object.fromEntries(statuses);
let sourcePath = "/";

export function rememberSource() {
  const path = location.hash.replace(/^#/, "") || "/";
  if (!path.startsWith("/help") && /^\/[A-Za-z0-9_/-]*$/.test(path)) sourcePath = path.slice(0, 200);
}

export async function refreshCounts() {
  try {
    const counts = await get("/api/support/counts");
    document.querySelectorAll(".support-count").forEach((el) => {
      const n = counts.mine + counts.inbox;
      el.textContent = n ? ` ${n}` : "";
      el.hidden = !n;
      el.setAttribute("aria-label", `미확인 문의 및 답변 ${n}건`);
    });
    document.querySelectorAll(".support-inbox-count").forEach((el) => { el.textContent = `미확인 ${counts.inbox}건`; });
  } catch { /* Help stays available if only the counter request fails. */ }
}

export function helpLink(className = "") {
  return h("a", { class: className, href: "#/help" }, "도움말 · 문의",
    h("span", { class: "badge support-count", hidden: true }));
}

export async function renderHome(root) {
  mount(root, h("div", { class: "page-head" }, h("h1", {}, "도움말 · 문의")),
    h("p", { class: "muted" }, "ClassBridge 사용 중 불편한 점이나 개선 아이디어를 개발자에게 알려 주세요."),
    h("div", { class: "cards" },
      h("section", { class: "card" }, h("h2", {}, "사이트 공유"),
        h("p", {}, "ClassBridge 접속 QR을 다시 보거나 내려받아 공유하세요."), h("div", { class: "actions" }, siteQrButton(), copySiteLink())),
      h("section", { class: "card" }, h("h2", {}, "개발자에게 문의"),
        h("p", {}, "오류 신고 · 기능 제안 · 사용 방법. 작성자와 개발자(관리자)만 확인하는 비공개 문의입니다."),
        h("a", { class: "btn primary", href: "#/help/new" }, "문의 작성"),
        h("a", { class: "btn", href: "#/help/mine" }, "내 문의")),
      can("support:manage") ? h("section", { class: "card" }, h("h2", {}, "개발자 관리"),
        h("p", {}, "문의 내용을 확인하고 답변과 처리 상태를 관리합니다."),
        h("span", { class: "badge support-inbox-count" }),
        h("a", { class: "btn", href: "#/help/inbox" }, "개발자 문의함")) : null),
    h("section", { class: "panel support-guide" }, h("h2", {}, "문의 전에 확인해 주세요"),
      h("p", {}, "수업·상담 운영에 관한 의견은 기존 건의함을 이용해 주세요. 개발자 문의는 익명이 아니며, 개발자가 계정 이름·이메일과 문의 내용을 확인합니다."),
      h("p", {}, "비밀번호, 인증번호, 다른 사람의 개인정보나 상담 기록은 보내지 마세요. 답변과 처리 상태는 ‘내 문의’에서 확인할 수 있습니다."),
      h("a", { href: "/privacy", target: "_blank", rel: "noopener" }, "개인정보처리방침")));
  await refreshCounts();
}

export function renderNew(root) {
  const category = select(categories, "bug");
  category.setAttribute("aria-label", "문의 종류");
  const title = h("input", { required: true, maxlength: 120 });
  const content = h("textarea", { required: true, maxlength: 4000, rows: 7,
    placeholder: "어떤 화면에서 무엇을 하다가 문제가 생겼는지 알려 주세요." });
  const submit = h("button", { class: "btn primary", type: "submit" }, "문의 보내기");
  const pagePath = sourcePath;
  const form = h("form", { class: "panel" },
    h("p", { class: "notice" }, "익명 문의가 아닙니다. 개발자(관리자)가 계정 이름·이메일과 문의 내용을 확인합니다. 다른 이용자나 교수자에게는 공개되지 않습니다."),
    field("문의 종류", category), field("제목", title), field("내용", content),
    h("p", { class: "hint" }, "비밀번호·인증번호·개인 상담 기록은 입력하지 마세요. 내용은 최대 4,000자입니다."),
    h("p", { class: "muted" }, "첨부할 화면: ", h("code", {}, `#${pagePath}`), " (서비스 내부 경로만 첨부)"),
    h("div", { class: "toolbar" }, submit, h("a", { class: "btn", href: "#/help" }, "취소")));
  form.addEventListener("submit", busy(submit, async (e) => {
    e.preventDefault();
    try {
      const item = await post("/api/support/tickets", { category: category.value, title: title.value,
        content: content.value, page_path: pagePath });
      toast("문의가 접수되었습니다. 내 문의에서 답변을 확인하세요.", "success");
      go(`/help/tickets/${item.id}`);
    } catch (err) { errorToast(err); }
  }));
  mount(root, h("div", { class: "page-head" }, h("h1", {}, "개발자에게 문의")), form);
}

export async function renderList(root, inbox = false, offset = 0) {
  const items = await get(`/api/support/tickets?inbox=${inbox}&offset=${offset}`);
  const base = inbox ? "/help/inbox" : "/help/tickets";
  mount(root, h("div", { class: "page-head" }, h("h1", {}, inbox ? "개발자 문의함" : "내 문의"),
    h("a", { class: "btn", href: "#/help" }, "도움말 · 문의")),
    inbox ? h("p", { class: "muted" }, "미확인 수는 관리자가 아직 확인하지 않은 문의 수입니다. 처리 상태와는 별개입니다.") :
      h("a", { class: "btn primary", href: "#/help/new" }, "문의 작성"),
    items.length ? h("div", { class: "cards support-list" }, items.map((item) => h("article", { class: "card" },
      h("div", { class: "row" }, badge(labels[item.category]), badge(statusLabels[item.status], item.status)),
      h("a", { href: `#${base}/${item.id}`, class: "support-title" }, item.title),
      item.unread ? h("span", { class: "badge booked" }, inbox ? "미확인" : "새 답변·변경") : null,
      h("small", { class: "muted" }, fmtDateTime(item.updated_at))))) : empty("문의가 없습니다."),
    h("div", { class: "toolbar" },
      h("button", { class: "btn", disabled: offset === 0, onclick: () => renderList(root, inbox, offset - 50).catch(errorToast) }, "이전"),
      h("span", {}, `${Math.floor(offset / 50) + 1} 페이지`),
      h("button", { class: "btn", disabled: items.length < 50, onclick: () => renderList(root, inbox, offset + 50).catch(errorToast) }, "다음")));
  await refreshCounts();
}

export async function renderDetail(root, { id }, inbox = false) {
  const path = `/api/support/tickets/${id}`;
  const query = `?inbox=${inbox}`;
  const item = await get(path + query);
  const content = h("textarea", { required: true, rows: 5, maxlength: 4000 });
  const send = h("button", { class: "btn primary", type: "submit" }, inbox ? "답변 보내기" : "추가 내용 보내기");
  const form = h("form", { class: "panel" }, field(inbox ? "개발자 답변" : "추가 내용", content),
    h("p", { class: "hint" }, "최대 4,000자. 비밀번호·인증번호·개인 상담 기록은 보내지 마세요."),
    !inbox && item.status === "completed" ? h("p", { class: "hint" }, "추가 내용을 보내면 다시 접수됩니다.") : null, send);
  form.addEventListener("submit", busy(send, async (event) => {
    event.preventDefault();
    try { await post(path + "/messages" + query, { content: content.value }); await renderDetail(root, { id }, inbox); }
    catch (err) { errorToast(err); }
  }));
  const statusSelect = select(statuses, item.status);
  statusSelect.setAttribute("aria-label", "처리 상태");
  const saveStatus = h("button", { class: "btn" }, "상태 저장");
  saveStatus.addEventListener("click", busy(saveStatus, async () => {
    try { await put(path + "/status", { status: statusSelect.value }); await renderDetail(root, { id }, inbox); }
    catch (err) { errorToast(err); }
  }));
  mount(root, h("div", { class: "page-head" }, h("h1", { class: "support-title" }, item.title),
    h("a", { class: "btn", href: inbox ? "#/help/inbox" : "#/help/mine" }, "목록으로")),
    h("div", { class: "panel" }, badge(labels[item.category]), " ", badge(statusLabels[item.status], item.status),
      h("p", { class: "muted" }, `접수 ${fmtDateTime(item.created_at)} · 첨부 화면 #${item.page_path || "/"}`),
      inbox ? h("p", {}, `작성자: ${item.owner.name} (${item.owner.email})`) : null,
      inbox ? h("div", { class: "toolbar" }, field("처리 상태", statusSelect), saveStatus) : null),
    h("div", { class: "support-thread" }, item.messages.map((message) => h("section", { class: "panel" },
      h("strong", {}, message.is_developer ? "개발자 답변" : "문의 작성자"),
      h("small", { class: "muted" }, ` · ${fmtDateTime(message.created_at)}`),
      h("p", { class: "pre" }, message.content)))), form);
  await post(path + "/read" + query, { updated_at: item.updated_at });
  await refreshCounts();
}
