const paths = {
  "/slots": "M4 5h16v16H4z M4 10h16 M8 3v4 M16 3v4",
  "/slots/new": "M4 5h16v16H4z M4 10h16 M8 3v4 M16 3v4 M12 12v6 M9 15h6",
  "/booking": "M4 5h16v16H4z M4 10h16 M8 3v4 M16 3v4",
  "/bookings": "M5 3h14v18H5z M8 12l3 3 5-6",
  "/my-bookings": "M5 3h14v18H5z M8 12l3 3 5-6",
  "/staff/insights": "M4 3h16v18H4z M8 7h8 M8 11h8 M8 15h5",
  "/surveys": "M4 3h16v18H4z M7 7h1 M11 7h6 M7 12h1 M11 12h6 M7 17h1 M11 17h6",
  "/suggestions": "M3 4h18v13H9l-6 4z M7 9h10 M7 13h6",
  "/admin/users": "M8 8a4 4 0 1 0 8 0a4 4 0 1 0-8 0 M4 21v-2a8 8 0 0 1 16 0v2",
  "/admin/settings": "M4 6h16 M4 12h16 M4 18h16 M8 3v6 M16 9v6 M10 15v6",
  "/admin/audit": "M4 12a8 8 0 1 0 2-6 M3 3v5h5 M12 7v5l3 2",
};
export function navIcon(route) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  for (const [key, value] of Object.entries({viewBox: "0 0 24 24", width: "19", height: "19", fill: "none",
    stroke: "currentColor", "stroke-width": "1.7", "stroke-linecap": "round", "stroke-linejoin": "round",
    "aria-hidden": "true", class: "nav-icon"})) svg.setAttribute(key, value);
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", paths[route] || "M4 4h16v16H4z"); svg.append(path); return svg;
}
