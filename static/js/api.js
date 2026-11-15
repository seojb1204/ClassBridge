// 서버 API 통신. CSRF 토큰을 모든 변경 요청에 붙인다.
let csrfToken = "";
// Calendar-only, in-memory cache. Never persist student data to browser storage.
const calendarCache = new Map();
let calendarEpoch = 0;
export function clearCalendarCache() { calendarEpoch++; calendarCache.clear(); }
export function calendarGet(path) {
  const hit = calendarCache.get(path);
  if (hit && hit.until > Date.now()) return hit.promise;
  const epoch = calendarEpoch;
  const entry = { until: Date.now() + 15000 };
  entry.promise = get(path).then(value => {
    if (epoch !== calendarEpoch) return get(path); // mutation/auth changed while fetching
    return value;
  }).catch(error => {
    if (calendarCache.get(path) === entry) calendarCache.delete(path);
    throw error;
  });
  calendarCache.set(path, entry);
  // Bound memory even when navigating many weeks.
  if (calendarCache.size > 40) calendarCache.delete(calendarCache.keys().next().value);
  return entry.promise;
}

export function setCsrf(token) { clearCalendarCache(); csrfToken = token || ""; }

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export async function api(path, { method = "GET", body } = {}) {
  if (method !== "GET") clearCalendarCache();
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRF-Token"] = csrfToken;
  let res;
  try {
    res = await fetch(path, { method, headers, credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, "network", "네트워크 오류입니다. 연결을 확인한 뒤 다시 시도하세요.");
  }
  if (method !== "GET") clearCalendarCache();
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch { /* 본문 없음 */ }
  if (!res.ok) {
    throw new ApiError(res.status, data?.error || "error", data?.message || `요청 실패 (${res.status})`);
  }
  return data;
}

export const get = (p) => api(p);
export const post = (p, body = {}) => api(p, { method: "POST", body });
export const put = (p, body = {}) => api(p, { method: "PUT", body });
export const patch = (p, body = {}) => api(p, { method: "PATCH", body });
export const del = (p) => api(p, { method: "DELETE" });
