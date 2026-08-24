/* BatchProjects service worker — installability + safe offline shell.

SECURITY RULES (non-negotiable):
  - NEVER cache authenticated responses: /api/*, /workspace HTML (it embeds
    csrf_token + session user), or any response carrying Set-Cookie.
  - Only cache public, content-hashed static assets under
    /assets/batch_projects/ (entry JS/CSS, fonts, images, manifest).
  - Navigation requests are network-first; offline falls back to a tiny
    static offline page (no session data).
  - Everything else passes through untouched.
*/
const CACHE_NAME = "bp-pwa-v1";
const STATIC_PREFIX = "/assets/batch_projects/";
const OFFLINE_URL = "/assets/batch_projects/offline.html";

self.addEventListener("install", (event) => {
  // Pre-cache the static offline page so the offline fallback actually works.
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.add(OFFLINE_URL))
  );
  // Activate immediately so the new SW takes control without waiting for
  // all tabs to close.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      );
      await self.clients.claim();
    })()
  );
});

function isStaticAsset(url) {
  const u = new URL(url);
  return (
    u.origin === self.location.origin &&
    u.pathname.startsWith(STATIC_PREFIX) &&
    u.pathname !== OFFLINE_URL
  );
}

function isNavigation(request) {
  return request.mode === "navigate";
}

self.addEventListener("fetch", (event) => {
  const request = event.request;

  // Only GET, same-origin requests are candidates for caching.
  if (request.method !== "GET") return;

  // Never touch API/auth endpoints — pass through to the network untouched.
  const url = new URL(request.url);
  if (url.pathname.startsWith("/api/")) return;

  // Navigation: network-first, fall back to the static offline page.
  if (isNavigation(request)) {
    event.respondWith(
      (async () => {
        try {
          const fresh = await fetch(request);
          return fresh;
        } catch (err) {
          const cached = await caches.match(OFFLINE_URL);
          if (cached) return cached;
          // No cached offline page — return a minimal inline fallback.
          return new Response(
            "<!doctype html><html><body style='font-family:sans-serif;text-align:center;padding-top:20vh'><h1>You're offline</h1><p>BatchProjects needs a connection to load.</p></body></html>",
            { headers: { "Content-Type": "text/html; charset=utf-8" } }
          );
        }
      })()
    );
    return;
  }

  // Static assets: cache-first (they are content-hashed, so a stale cache
  // entry is impossible for a given URL), with network fallback + populate.
  if (isStaticAsset(request.url)) {
    event.respondWith(
      (async () => {
        const cached = await caches.match(request);
        if (cached) return cached;
        try {
          const fresh = await fetch(request);
          if (fresh.ok) {
            const clone = fresh.clone();
            const cache = await caches.open(CACHE_NAME);
            await cache.put(request, clone);
          }
          return fresh;
        } catch (err) {
          return new Response("", { status: 504, statusText: "Offline" });
        }
      })()
    );
    return;
  }

  // Everything else (non-asset same-origin GETs): network only, no caching.
  return;
});