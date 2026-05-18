/**
 * Forensa Console — service worker (US-F31, RT-F20).
 *
 * Strategy
 * --------
 *   - Precache the read-only app shell (HTML routes + static
 *     assets) on install so it's available offline (AC-2, AC-4).
 *   - Stale-while-revalidate for `/v1/receipts` and
 *     `/v1/evidence-packs` (read-only API surface): return cached
 *     payload immediately if present, refresh in background.
 *   - Network-only with no fallback for POST/PUT/PATCH/DELETE so
 *     write actions cannot be silently swallowed offline (AC-5).
 *     The OfflineBanner is the explicit UX signal for the user.
 *
 * No third-party deps. Vanilla SW + Cache API only — keeps the
 * bundle small enough to ship in CP9.52 without a Vite plugin.
 *
 * Versioning
 * ----------
 *   Bump CACHE_VERSION whenever the precache list changes so the
 *   activate handler can sweep old caches. We also call
 *   self.skipWaiting + clients.claim so the new SW takes effect on
 *   the next navigation rather than after a full quit.
 */

const CACHE_VERSION = "forensa-v1";
const APP_SHELL = [
  "/",
  "/receipts",
  "/evidence",
  "/manifest.webmanifest",
  "/icon-192.svg",
  "/icon-512.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_VERSION)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((k) => k !== CACHE_VERSION)
          .map((k) => caches.delete(k)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;

  // Never cache writes. If we're offline, the network attempt
  // fails and the caller surfaces the OfflineBanner / error path.
  if (req.method !== "GET") {
    return; // default browser behaviour
  }

  const url = new URL(req.url);

  // Read-only API: stale-while-revalidate.
  const isReadOnlyApi =
    url.pathname.startsWith("/v1/receipts") ||
    url.pathname.startsWith("/v1/evidence-packs") ||
    url.pathname.startsWith("/v1/anchors");

  if (isReadOnlyApi) {
    event.respondWith(staleWhileRevalidate(req));
    return;
  }

  // Same-origin navigations / static: cache-first with network fallback.
  if (url.origin === self.location.origin) {
    event.respondWith(cacheFirst(req));
  }
});

async function cacheFirst(req) {
  const cache = await caches.open(CACHE_VERSION);
  const cached = await cache.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(req, res.clone());
    return res;
  } catch (err) {
    // Last resort: try the app-shell root so the UI can render
    // the OfflineBanner instead of a blank "no internet" page.
    const shell = await cache.match("/");
    if (shell) return shell;
    throw err;
  }
}

async function staleWhileRevalidate(req) {
  const cache = await caches.open(CACHE_VERSION);
  const cached = await cache.match(req);
  const fetchPromise = fetch(req)
    .then((res) => {
      if (res.ok) cache.put(req, res.clone());
      return res;
    })
    .catch(() => cached);
  return cached || fetchPromise;
}
