// 관리자: 계정·역할, 운영 설정, 감사 기록
import { get, put } from "../api.js";
import { state } from "../state.js";
import { fmtDateTime } from "../time.js";
import { busy, confirmAction, errorToast, field, h, mount, select, toast } from "../ui.js";

const ROLES = [["student", "학생"], ["professor", "교수자"], ["admin", "관리자"]];

export async function renderUsers(root) {
  const users = await get("/api/admin/users");
  mount(root, h("div", { class: "page-head" }, h("h1", {}, "계정·권한 관리")),
    h("p", { class: "muted" }, "역할 변경·비활성화 시 해당 사용자의 기존 로그인 세션은 즉시 무효화됩니다. 마지막 관리자는 강등할 수 없습니다."),
    h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, ["이름", "이메일", "역할", "상태", "최근 로그인"].map((t) => h("th", {}, t)))),
      h("tbody", {}, users.map((u) => row(root, u))))));
}

function row(root, u) {
  const self = u.id === state.me.id;
  const role = select(ROLES, u.role);
  role.disabled = self;
  role.addEventListener("change", async () => {
    const label = ROLES.find((r) => r[0] === role.value)[1];
    if (!(await confirmAction("역할 변경", `${u.email}의 역할을 '${label}'(으)로 변경할까요?`, "변경"))) { role.value = u.role; return; }
    try { await put(`/api/admin/users/${u.id}/role`, { role: role.value }); toast("변경했습니다", "success"); }
    catch (e) { errorToast(e); }
    renderUsers(root);
  });
  const toggle = h("button", { class: u.is_active ? "btn small danger" : "btn small", disabled: self }, u.is_active ? "비활성화" : "활성화");
  toggle.addEventListener("click", busy(toggle, async () => {
    if (!(await confirmAction("계정 상태", `${u.email} 계정을 ${u.is_active ? "비활성화" : "활성화"}할까요?`, "확인", u.is_active))) return;
    try { await put(`/api/admin/users/${u.id}/active`, { is_active: !u.is_active }); } catch (e) { errorToast(e); }
    renderUsers(root);
  }));
  return h("tr", { dataset: { userEmail: u.email } },
    h("td", { "data-label": "이름" }, u.name, self ? " (나)" : ""), h("td", { "data-label": "이메일" }, u.email),
    h("td", { "data-label": "역할" }, role), h("td", { "data-label": "상태" }, toggle),
    h("td", { "data-label": "최근 로그인" }, u.last_login_at ? fmtDateTime(u.last_login_at) : "-"));
}

export async function renderSettings(root) {
  const { values, specs } = await get("/api/admin/settings");
  const inputs = {};
  const btn = h("button", { class: "btn primary", type: "submit" }, "저장");
  const form = h("form", { class: "panel grid-form" },
    specs.map((s) => {
      inputs[s.key] = h("input", { type: "number", min: s.min, max: s.max, value: values[s.key] });
      return field(s.label, inputs[s.key], `기본값 ${s.default} (범위 ${s.min}~${s.max})`);
    }), h("div", { class: "field wide" }, btn));
  form.addEventListener("submit", busy(btn, async (e) => {
    e.preventDefault();
    const changes = {};
    for (const [k, el] of Object.entries(inputs)) if (+el.value !== values[k]) changes[k] = +el.value;
    if (!Object.keys(changes).length) { toast("변경된 값이 없습니다"); return; }
    try { await put("/api/admin/settings", changes); toast("저장했습니다", "success"); renderSettings(root); }
    catch (err) { errorToast(err); }
  }));
  mount(root, h("div", { class: "page-head" }, h("h1", {}, "운영 설정")), form);
}

export async function renderAudit(root) {
  const logs = await get("/api/admin/audit?limit=200");
  mount(root, h("div", { class: "page-head" }, h("h1", {}, "관리 작업 이력")),
    h("p", { class: "muted" }, "익명 설문 응답·건의 제출은 기록되지 않습니다."),
    h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, ["시각", "작업자", "작업", "대상", "내용"].map((t) => h("th", {}, t)))),
      h("tbody", {}, logs.map((l) => h("tr", {},
        h("td", { "data-label": "시각" }, fmtDateTime(l.at)), h("td", { "data-label": "작업자" }, l.actor_id ?? "시스템"),
        h("td", { "data-label": "작업" }, l.action), h("td", { "data-label": "대상" }, `${l.target_type} ${l.target_id}`),
        h("td", { "data-label": "내용" }, h("code", {}, JSON.stringify(l.detail)))))))));
}
