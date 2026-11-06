// Network-only for application pages, authentication, API and exports.
// Cache only the public offline notice: never store student or consultation data.
const CACHE = "classbridge-offline-v1";
const OFFLINE = "/static/offline.html";
self.addEventListener("push", (event) => {
  event.waitUntil((async () => {
    let payload;
    try { payload = event.data.json(); } catch { return; }
    try {
      const response = await fetch("/api/admin/push-config", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok || !(await response.json()).enabled) return;
    } catch { return; }
    // Ignore provider-supplied links; always open the authenticated booking page.
    await self.registration.showNotification("ClassBridge 상담 예약 알림", {
      body: String(payload.body || "상담 예약이 변경되었습니다").slice(0, 120),
      tag: String(payload.tag || "classbridge-booking"),
      data: { url: "/#/bookings" },
    });
  })());
});
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow("/#/bookings"));
});
self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.add(OFFLINE)));
});
self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith("classbridge-offline-") && key !== CACHE) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // Do not replace login callbacks, API/download errors, or non-GET operations with HTML.
  if (event.request.method !== "GET" || event.request.mode !== "navigate"
      || url.origin !== self.location.origin || url.pathname !== "/") return;
  event.respondWith(fetch(event.request).catch(async () => {
    const offline = await caches.match(OFFLINE);
    return offline || new Response("인터넷 연결을 확인한 뒤 다시 열어 주세요.", {
      status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }));
});
