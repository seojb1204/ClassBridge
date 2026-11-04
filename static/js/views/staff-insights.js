// 교수자·관리자 전용: 상담 현황 통계와 기존 상담 기록을 한곳에서 열람·수정.
import { get, put } from "../api.js";
import { fmtDateTime } from "../time.js";
import { errorToast, h, mount, promptText, select, toast } from "../ui.js";

const LABELS = {
  booked: "예약 중", completed: "상담 완료", no_show: "미참석", cancelled: "취소",
  career: "진로", employment: "취업", academics: "학업", campus: "학교생활", other: "기타",
  in_person: "대면", online: "온라인",
};
let period = 90;
let query = "";
let offset = 0;
const LIMIT = 20;

function metric(title, value, caption = "") {
  return h("div", { class: "insight-metric" },
    h("span", { class: "muted" }, title),
    h("strong", { class: "insight-number" }, String(value)),
    caption ? h("small", { class: "muted" }, caption) : null);
}

function breakdown(title, counts) {
  const entries = Object.entries(counts || {}).filter(([, count]) => count > 0);
  return h("section", { class: "panel insight-breakdown" },
    h("h3", {}, title),
    entries.length ? h("ul", { class: "plain" },
      entries.map(([key, value]) => h("li", { class: "insight-breakdown-item" },
        h("span", {}, LABELS[key] || key),
        h("strong", {}, `${value}건`))))
      : h("p", { class: "muted" }, "집계된 예약이 없습니다."));
}

function overviewView(data) {
  const counts = data.status_counts;
  const percent = data.completion_rate === null ? "—" : `${data.completion_rate}%`;
  return h("div", { class: "insight-overview" },
    h("p", { class: "muted" },
      `${data.period_start} ~ ${data.period_end}에 상담이 시작하는 예약 기준 · 상태별 건수`),
    h("div", { class: "insight-metrics" },
      metric("기간 내 전체 예약", data.total_bookings),
      metric("예약 중", counts.booked),
      metric("상담 완료", counts.completed),
      metric("미참석", counts.no_show),
      metric("취소", counts.cancelled),
      metric("작성된 상담 기록", data.recorded_notes),
      metric("열린 상담 시간", data.open_slots),
      metric("향후 14일 예약", data.upcoming_14_days),
      metric("종결 건 중 상담 완료율", percent, "완료 ÷ (완료 + 미참석)")),
    h("div", { class: "insight-breakdowns" },
      breakdown("상담 주제별 예약", data.type_counts),
      breakdown("상담 방식별 예약", data.mode_counts)));
}

async function editNote(item, refresh) {
  const next = await promptText("상담 기록 수정", "학업·진로·취업 진행사항만 기록해 주세요. 건강·심리 상태 등 민감한 개인정보는 입력하지 마세요. 교수자·관리자만 볼 수 있습니다.",
    { multiline: true, value: item.note });
  if (next === null || next === item.note) return;
  try {
    await put(`/api/bookings/${item.booking_id}/note`, { note: next });
    toast("상담 기록을 저장했습니다.", "success");
    await refresh();
  } catch (error) { errorToast(error); }
}

function notesView(data, refresh, goToOffset) {
  const start = data.total ? offset + 1 : 0;
  const last = Math.min(offset + LIMIT, data.total);
  return h("div", { class: "insight-notes" },
    h("p", { class: "muted" },
      `작성된 상담 기록 ${data.total}건 · ${start}~${last}건 표시 · 기록은 상담 예약 데이터에 보존됩니다.`),
    data.items.length ? h("div", { class: "consult-note-list" },
      data.items.map((item) => h("article", { class: "panel consult-note-card",
        dataset: { bookingId: item.booking_id } },
        h("div", { class: "row consult-note-head" },
          h("strong", {}, item.student_name || "이름 미입력"),
          h("span", { class: "badge" }, LABELS[item.status] || item.status)),
        h("p", { class: "muted" },
          `${fmtDateTime(item.start_at)} · ${LABELS[item.consultation_type] || "기타"} · ${LABELS[item.consultation_mode] || "대면"}`),
        item.student_number ? h("p", { class: "muted" }, `학번: ${item.student_number} (학생 입력값)`) : null,
        h("p", { class: "consult-note-text pre" }, item.note),
        h("button", { class: "btn small", type: "button",
          onclick: () => editNote(item, refresh) }, "상담 기록 수정"))))
      : h("p", { class: "empty" }, "검색 조건에 맞는 작성된 상담 기록이 없습니다."),
    h("div", { class: "insight-pagination" },
      h("button", { class: "btn", type: "button", disabled: offset === 0,
        onclick: () => goToOffset(Math.max(0, offset - LIMIT)) }, "이전"),
      h("span", { class: "muted" }, `${data.total ? Math.floor(offset / LIMIT) + 1 : 0} 페이지`),
      h("button", { class: "btn", type: "button", disabled: offset + LIMIT >= data.total,
        onclick: () => goToOffset(offset + LIMIT) }, "다음")));
}

export async function render(root) {
  const periodPicker = select([[7, "최근 7일"], [30, "최근 30일"],
    [90, "최근 90일"], [365, "최근 1년"]], String(period));
  const search = h("input", { type: "search", value: query, maxlength: 80,
    placeholder: "학생 이름·학번·상담 기록 검색", "aria-label": "상담 기록 검색" });
  const statsRoot = h("div", { id: "staff-overview" },
    h("p", { class: "loading" }, "상담 통계를 불러오는 중…"));
  const notesRoot = h("div", { id: "staff-notes" },
    h("p", { class: "loading" }, "상담 기록을 불러오는 중…"));

  async function loadOverview() {
    try {
      const data = await get(`/api/staff/overview?days=${period}`);
      mount(statsRoot, overviewView(data));
    } catch (error) { mount(statsRoot, h("p", { class: "error-box" }, error.message)); }
  }

  async function loadNotes() {
    try {
      const data = await get(`/api/staff/notes?limit=${LIMIT}&offset=${offset}&q=${encodeURIComponent(query)}`);
      mount(notesRoot, notesView(data, () => Promise.all([loadNotes(), loadOverview()]), (next) => {
        offset = next;
        loadNotes();
      }));
    } catch (error) { mount(notesRoot, h("p", { class: "error-box" }, error.message)); }
  }

  const submitSearch = (event) => {
    event.preventDefault();
    query = search.value.trim();
    offset = 0;
    loadNotes();
  };
  periodPicker.addEventListener("change", () => {
    period = Number(periodPicker.value);
    loadOverview();
  });
  mount(root,
    h("div", { class: "page-head" }, h("h1", {}, "상담 정보"),
      h("p", { class: "muted" }, "교수자·관리자만 볼 수 있는 상담 통계와 비공개 상담 기록입니다.")),
    h("section", { class: "insight-section" },
      h("div", { class: "insight-section-head" }, h("h2", {}, "상담 현황"),
        h("label", { class: "insight-period" }, "집계 기간 ", periodPicker)),
      statsRoot),
    h("section", { class: "insight-section" },
      h("div", { class: "insight-section-head" }, h("h2", {}, "전체 상담 기록")),
      h("p", { class: "muted" }, "작성된 상담 기록만 표시합니다. 학번은 사용자가 입력한 정보이며 학교에서 검증되지 않았습니다."),
      h("form", { class: "insight-search", onsubmit: submitSearch }, search,
        h("button", { class: "btn", type: "submit" }, "검색"),
        h("button", { class: "btn", type: "button", onclick: () => {
          search.value = "";
          query = "";
          offset = 0;
          loadNotes();
        } }, "초기화")),
      notesRoot));
  await Promise.all([loadOverview(), loadNotes()]);
}
