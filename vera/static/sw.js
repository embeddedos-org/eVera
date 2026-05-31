/**
 * eVera Service Worker — Offline PWA Support
 *
 * Caches static assets for offline use.
 * Network-first strategy for API calls, cache-first for static files.
 * Stale-while-revalidate for i18n strings.
 */

const CACHE_NAME = "evera-v2.1";
const STATIC_ASSETS = [
    "/",
    "/static/style.css",
    "/static/app.js",
    "/static/face.js",
    "/static/waveform.js",
    "/static/listener.js",
    "/static/agents-view.js",
    "/static/pipeline-view.js",
    "/static/diagram-viewer.js",
    "/static/i18n.js",
    "/static/geolocation.js",
    "/static/manifest.json",
    "/static/icon-192.png",
    "/static/icon-512.png",
];

// Install: pre-cache static assets
self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            // addAll fails if any resource fails — use individual adds to be resilient
            return Promise.allSettled(
                STATIC_ASSETS.map((url) =>
                    cache.add(url).catch((e) => {
                        console.warn(`[SW] Failed to cache ${url}:`, e);
                    })
                )
            );
        })
    );
    // Activate immediately without waiting for old SW to be released
    self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys
                    .filter((key) => key !== CACHE_NAME)
                    .map((key) => {
                        console.log(`[SW] Deleting old cache: ${key}`);
                        return caches.delete(key);
                    })
            );
        })
    );
    // Take control of all open clients immediately
    self.clients.claim();
});

// Fetch: routing strategy based on request type
self.addEventListener("fetch", (event) => {
    const url = new URL(event.request.url);

    // Skip: non-GET, WebSocket, SSE, API mutation endpoints
    if (
        event.request.method !== "GET" ||
        url.pathname.startsWith("/ws") ||
        url.pathname.startsWith("/events/") ||
        url.pathname.startsWith("/agents/stream") ||
        url.pathname.startsWith("/chat") ||
        url.pathname.startsWith("/webhook") ||
        url.pathname.startsWith("/location/update")
    ) {
        return;
    }

    // Static assets: stale-while-revalidate (serve cached, update in background)
    if (url.pathname.startsWith("/static") || url.pathname === "/") {
        event.respondWith(
            caches.open(CACHE_NAME).then((cache) => {
                return cache.match(event.request).then((cached) => {
                    const networkFetch = fetch(event.request).then((response) => {
                        if (response.ok) {
                            cache.put(event.request, response.clone());
                        }
                        return response;
                    }).catch(() => cached);

                    // Return cached immediately, update in background
                    return cached || networkFetch;
                });
            })
        );
        return;
    }

    // i18n strings: cache-first with 1-hour TTL
    if (url.pathname.startsWith("/i18n/")) {
        event.respondWith(
            caches.match(event.request).then((cached) => {
                if (cached) {
                    // Revalidate in background
                    fetch(event.request).then((res) => {
                        if (res.ok) {
                            caches.open(CACHE_NAME).then((c) => c.put(event.request, res));
                        }
                    }).catch(() => {});
                    return cached;
                }
                return fetch(event.request).then((res) => {
                    if (res.ok) {
                        caches.open(CACHE_NAME).then((c) => c.put(event.request, res.clone()));
                    }
                    return res;
                });
            })
        );
        return;
    }

    // Health/status endpoints: network-only (always fresh)
    if (url.pathname === "/health" || url.pathname === "/status") {
        return;
    }

    // All other GET requests: network-first with cache fallback
    event.respondWith(
        fetch(event.request)
            .then((response) => {
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, clone);
                    });
                }
                return response;
            })
            .catch(() => {
                return caches.match(event.request).then((cached) => {
                    if (cached) return cached;
                    // Return offline fallback for navigation requests
                    if (event.request.mode === "navigate") {
                        return caches.match("/");
                    }
                    return new Response("Offline", { status: 503 });
                });
            })
    );
});

// Background sync for queued messages (future enhancement)
self.addEventListener("sync", (event) => {
    if (event.tag === "sync-messages") {
        console.log("[SW] Background sync triggered");
    }
});

// Push notifications (future enhancement)
self.addEventListener("push", (event) => {
    if (!event.data) return;
    try {
        const data = event.data.json();
        event.waitUntil(
            self.registration.showNotification(data.title || "eVera", {
                body: data.body || "",
                icon: "/static/icon-192.png",
                badge: "/static/icon-192.png",
                data: data,
            })
        );
    } catch (e) {
        console.warn("[SW] Push notification error:", e);
    }
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    event.waitUntil(
        clients.openWindow("/")
    );
});
