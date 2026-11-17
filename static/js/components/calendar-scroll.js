import { mount } from "../ui.js";

// Reserve the old height before constructing nodes: reused children (today's
// summary) are detached during construction and can otherwise clamp scrollY.
export function mountCalendarPreservingScroll(root, build) {
  const existing = root.querySelector('.week-nav');
  if (!existing) { mount(root, ...build()); return; }
  const x = window.scrollX, y = window.scrollY;
  const inner = root.querySelector('.week-wrap');
  const innerTop = inner?.scrollTop || 0;
  const minHeight = root.style.minHeight;
  root.style.minHeight = `${root.getBoundingClientRect().height}px`;
  try {
    mount(root, ...build());
    const next = root.querySelector('.week-wrap');
    if (next) next.scrollTop = innerTop;
    window.scrollTo({ left: x, top: y, behavior: 'instant' });
  } finally {
    root.style.minHeight = minHeight;
  }
  // The destination may genuinely be shorter. Let the browser clamp to its
  // bottom, but do not focus/scroll to the top or restore stale async positions.
  window.scrollTo({ left: x, top: y, behavior: 'instant' });
}
