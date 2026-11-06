// Deterministic Korean daytime input; never silently roll a date/year forward.
export function parseDate(value, today) {
  let text = value.trim().replace(/년|월/g, "-").replace(/일/g, "").replace(/[./\s]+/g, "-");
  if (/^\d{8}$/.test(text)) text = `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6)}`;
  if (/^\d{4}$/.test(text)) text = `${text.slice(0, 2)}-${text.slice(2)}`;
  const parts = text.split("-").filter(Boolean);
  if (parts.length === 2) parts.unshift(today.slice(0, 4));
  if (parts.length !== 3 || !parts.every(p => /^\d+$/.test(p)) || parts[0].length !== 4)
    throw new Error("날짜는 11월 20일 또는 2026-11-20처럼 입력해 주세요.");
  const [year, month, day] = parts.map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (year < 2000 || year > 2100 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day)
    throw new Error("실제로 존재하는 날짜를 입력해 주세요.");
  const result = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  if (result < today) throw new Error("이미 지난 날짜입니다. 연도와 날짜를 확인해 주세요.");
  return result;
}

export function parseTime(value) {
  let text = value.trim();
  const period = text.match(/^(오전|오후)/)?.[1];
  text = text.replace(/^(오전|오후)\s*/, "").replace(/시/g, ":").replace(/분/g, "").replace(/\s+/g, ":").replace(/:+/g, ":").replace(/:$/, "");
  if (/^\d{3,4}$/.test(text)) text = `${text.slice(0, -2)}:${text.slice(-2)}`;
  const match = text.match(/^(\d{1,2})(?::(\d{1,2}))?$/);
  if (!match) throw new Error("시간은 10 00, 10시, 오후 3:30처럼 입력해 주세요.");
  let hour = Number(match[1]);
  const minute = Number(match[2] || 0);
  if (period) {
    if (hour < 1 || hour > 12) throw new Error("오전·오후 표기는 1~12시로 입력해 주세요.");
    hour = hour % 12 + (period === "오후" ? 12 : 0);
  } else if (hour >= 1 && hour <= 6) hour += 12;
  if (minute > 59 || hour < 8 || hour > 18 || (hour === 18 && minute !== 0))
    throw new Error("상담 시간은 오전 8시부터 오후 6시까지 입력해 주세요. 7시는 오전·오후를 임의로 정하지 않습니다.");
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

export function parseSchedule(value, today) {
  const match = value.trim().match(/^((?:\d{4}년\s*)?\d{1,2}월\s*\d{1,2}일|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.]\d{1,2})\s+(.+?)(?:~|～|–|부터|-)\s*(.+?)(?:까지)?$/);
  if (!match) throw new Error("예: 11월 20일 3시~6시. 날짜와 시작·종료 시간을 함께 입력해 주세요.");
  const date = parseDate(match[1], today), start = parseTime(match[2]), end = parseTime(match[3]);
  if (end <= start) throw new Error("종료 시간은 시작 시간보다 늦어야 합니다. 다음 날로 자동 변경하지 않습니다.");
  return { date, start, end };
}

export function timeLabel(value) {
  const [hour, minute] = value.split(":").map(Number);
  return `${hour < 12 ? "오전" : "오후"} ${hour % 12 || 12}:${String(minute).padStart(2, "0")}`;
}
