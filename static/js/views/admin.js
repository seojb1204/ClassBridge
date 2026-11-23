// 관리자: 계정·역할, 운영 설정, 감사 기록
import { del, get, put } from "../api.js";
import { state } from "../state.js";
import { notificationStatus } from "../components/notification-status.js";
import { fmtDateTime } from "../time.js";
import { busy, confirmAction, errorToast, field, h, mount, select, toast } from "../ui.js";

const ROLES = [["student", "학생"], ["professor", "교수자"], ["admin", "관리자"]];

let userQuery = "";
let roleFilter = "";

export async function renderUsers(root) {
  const users = await get("/api/admin/users");
  const tbody = h("tbody", {}, users.map((u) => row(root, u)));
  const count = h("small", { class: "muted", role: "status" });
  const search = h("input", { type: "search", value: userQuery, maxlength: 80, "aria-label": "이름·이메일 검색",
    placeholder: "이름·이메일 검색" });
  const role = select([["", "전체 역할"], ...ROLES], roleFilter);
  role.setAttribute("aria-label", "역할 필터");
  const apply = () => {
    userQuery = search.value.trim().toLowerCase();
    roleFilter = role.value;
    let shown = 0;
    tbody.querySelectorAll("tr").forEach((tr, i) => {
      const u = users[i];
      const match = (!userQuery || `${u.name} ${u.email}`.toLowerCase().includes(userQuery)) && (!roleFilter || u.role === roleFilter);
      tr.hidden = !match;
      if (match) shown++;
    });
    count.textContent = `${shown}명 표시 · 전체 ${users.length}명`;
  };
  search.addEventListener("input", apply);
  role.addEventListener("change", apply);
  mount(root, h("div", { class: "page-head" }, h("h1", {}, "계정·권한 관리")),
    h("p", { class: "muted" }, "역할 변경·비활성화 시 해당 사용자의 기존 로그인 세션은 즉시 무효화됩니다. 마지막 관리자는 강등할 수 없습니다. 역할 변경·계정 삭제는 확인 후 적용됩니다."),
    h("div", { class: "filters user-filters" }, search, role, count),
    h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, ["이름", "이메일", "역할", "상태", "최근 로그인"].map((t) => h("th", {}, t)))),
      tbody)));
  apply();
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
    h("td", { "data-label": "역할" }, role), h("td", { "data-label": "상태" }, toggle,
      !self && u.role === "student" ? h("button", { class: "btn small danger", onclick: async () => {
        try {
          const preview = await get(`/api/admin/users/${u.id}/deletion-preview`);
          if (!preview.can_delete) {
            await confirmAction("삭제할 수 없는 계정", Object.entries(preview.records).map(([k, v]) => `${k} ${v}건`).join(" · ") + "이 연결되어 있습니다. 기록과 계정은 보존합니다.", "확인");
            return;
          }
          if (!await confirmAction("학생 계정 삭제", `${preview.name} (${preview.email}) 계정을 삭제합니다. 연결된 활동 기록은 없으며 로그인은 해제됩니다. 계정 삭제는 복원할 수 없지만, 다시 Google 로그인하면 새로 가입할 수 있습니다.`, "삭제", true)) return;
          await del(`/api/admin/users/${u.id}`);
          await renderUsers(root);
          toast("학생 계정을 삭제했습니다", "success");
        } catch (e) { errorToast(e); }
      } }, "계정 삭제") : null),
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
  mount(root, h("div", { class: "page-head" }, h("h1", {}, "운영 설정")), form, await notificationStatus());
}

const ACTIONS = {
  "announcement.update": "공지 수정", "booking.auto_completed": "상담 자동 완료 처리", "booking.cancel_by_staff": "교수자 예약 취소",
  "booking.create_for_student": "학생 대신 예약", "booking.expired": "결과 미확인으로 종료", "booking.reschedule_by_staff": "교수자 예약 변경",
  "email.pause": "예약 이메일 중지", "email.resume": "예약 이메일 재개", "lecture.cancel": "강의 취소", "lecture.create": "강의 등록",
  "lecture.update": "강의 수정", "settings.update": "운영 설정 변경", "slot.booking_moved": "예약 시간 이동", "slot.cancel": "상담 시간 취소",
  "slot.create": "상담 시간 등록", "slot.delete_empty_cancelled": "빈 상담 시간 삭제", "slot.replace_unbooked": "미예약 상담 시간 교체",
  "slot.update": "상담 시간 수정", "staff_reminder.cancelled": "교수자 알림 취소", "staff_reminder.created": "교수자 알림 예약",
  "suggestion.reply": "건의 답변", "suggestion.trash": "건의 휴지통 이동", "suggestion.restore": "건의 복원",
  "suggestion.delete_selected": "건의 영구 삭제", "suggestion.empty_trash": "건의 휴지통 비우기", "support.reply": "개발자 문의 답변",
  "support.status": "개발자 문의 상태 변경", "survey.close": "설문 마감", "survey.create": "설문 생성", "survey.delete": "설문 삭제",
  "survey.duplicate": "설문 복제", "survey.publish": "설문 게시", "survey.update": "설문 수정", "user.activate": "계정 활성화",
  "user.bootstrap_role": "초기 역할 부여", "user.deactivate": "계정 비활성화", "user.delete_empty_student": "학생 계정 삭제",
  "user.role_change": "역할 변경", "user.staging_identity_rebind": "테스트 계정 재연결",
};
const TARGETS = { announcement: "공지", booking: "예약", lecture: "강의", lecture_series: "반복 강의", settings: "운영 설정",
  slot: "상담 시간", slot_series: "반복 상담 묶음", staff_reminder: "교수자 알림", suggestion: "건의", survey: "설문",
  user: "계정", support_ticket: "개발자 문의" };
const DETAIL_KEYS = { count: "건수", kind: "유형", capacity: "정원", reason: "사유", role: "역할", from: "이전", to: "이후",
  cancelled_bookings: "취소된 예약", changes: "변경 항목" };

function detailText(detail) {
  const entries = Object.entries(detail || {});
  if (!entries.length) return "—";
  return entries.map(([k, v]) => `${DETAIL_KEYS[k] || k}: ${typeof v === "object" ? JSON.stringify(v) : v === "" ? "없음" : v}`).join(" · ");
}

export async function renderAudit(root) {
  const [logs, users] = await Promise.all([get("/api/admin/audit?limit=200"),
    get("/api/admin/users").catch(() => [])]);
  const names = new Map(users.map((u) => [u.id, u.name || u.email]));
  const shortId = (id) => (String(id).length > 12 ? `${String(id).slice(0, 8)}…` : String(id));
  mount(root, h("div", { class: "page-head" }, h("h1", {}, "관리 작업 이력")),
    h("p", { class: "muted" }, "익명 설문 응답·건의 제출은 기록되지 않습니다. 작업 코드는 오류 문의 시 확인용으로 함께 표시합니다."),
    h("div", { class: "table-wrap" }, h("table", { class: "table audit-table" },
      h("thead", {}, h("tr", {}, ["시각", "작업자", "작업", "대상", "내용"].map((t) => h("th", {}, t)))),
      h("tbody", {}, logs.map((l) => h("tr", {},
        h("td", { "data-label": "시각" }, fmtDateTime(l.at)),
        h("td", { "data-label": "작업자", class: "audit-actor" }, l.actor_id == null ? "시스템 자동" : names.get(l.actor_id) || `계정 #${l.actor_id}`),
        h("td", { "data-label": "작업" }, ACTIONS[l.action] || l.action, h("small", { class: "muted audit-code" }, l.action)),
        h("td", { "data-label": "대상" }, l.target_type ? `${TARGETS[l.target_type] || l.target_type}${l.target_id ? ` #${shortId(l.target_id)}` : ""}` : "—"),
        h("td", { "data-label": "내용" }, detailText(l.detail))))))));
}
