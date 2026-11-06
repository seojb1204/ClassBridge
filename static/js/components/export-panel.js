import { get } from "../api.js";
import { can } from "../state.js";
import { h, field, select, errorToast } from "../ui.js";
import { addDays, todayKst } from "../time.js";

export function exportPanel(staff = false) {
  if (!can("data:export") || !can("booking:manage")) return null;
  const start = h("input", { type: "date", value: addDays(todayKst(), -90), required: true });
  const end = h("input", { type: "date", value: todayKst(), required: true });
  const student = select([["", "전체 학생"]], "");
  const numbers = h("input", { type: "checkbox" });
  const contacts = h("input", { type: "checkbox" });
  const notes = h("input", { type: "checkbox" });
  const links = [
    ["xlsx", "Excel 다운로드"], ["csv", "CSV 다운로드"], ["print", "PDF 저장 / 인쇄"],
  ].map(([format, title]) => h("a", { class: "btn", target: format === "print" ? "_blank" : "_self", rel: "noopener", href: "#",
    onclick: (event) => {
      if (!start.value || !end.value || start.value > end.value) {
        event.preventDefault(); errorToast(new Error("시작일과 종료일을 확인해 주세요")); return;
      }
      const params = new URLSearchParams({ start: start.value, end: end.value, format,
        include_numbers: numbers.checked, include_contacts: contacts.checked, include_notes: staff && notes.checked });
      if (staff && student.value) params.set("student_id", student.value);
      event.currentTarget.href = `/api/exports/consultations?${params}`;
    } }, title));
  if (staff) get("/api/students").then((items) => items.forEach((s) =>
    student.append(h("option", { value: s.id }, `${s.name} (${s.email})`)))).catch(errorToast);
  return h("details", { class: "panel export-panel" }, h("summary", {}, "상담 자료 다운로드"),
    h("p", { class: "muted" }, "상담 시작일 기준 · 최대 366일/2,000건. 파일은 이 기기에 저장되며 외부 서비스에 자동 전송되지 않습니다."),
    h("div", { class: "grid-form" }, field("시작일", start), field("종료일", end), staff ? field("학생", student) : null),
    h("div", { class: "checks" }, h("label", { class: "check" }, numbers, "학번·학년 포함"),
      h("label", { class: "check" }, contacts, "이메일 포함"),
      staff ? h("label", { class: "check" }, notes, "교수자 전용 상담 기록 포함") : null),
    h("p", { class: "hint" }, "필요한 항목만 선택하세요. 내려받은 파일의 보관·공유는 직접 관리해야 합니다."),
    h("div", { class: "toolbar" }, links));
}
