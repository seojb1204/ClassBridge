import { calendarGet } from "./api.js";
import { addDays } from "./time.js";

// Only two adjacent weeks, session-memory only; failures remain retryable on navigation.
export function prefetchWeeks(week, resources) {
  for (const offset of [-7, 7]) {
    const start = addDays(week, offset);
    for (const resource of resources)
      calendarGet(`/api/${resource}?start=${start}&days=7`).catch(() => {});
  }
}
