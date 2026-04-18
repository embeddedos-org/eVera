/**
 * Voca Service Worker — Offline PWA Support
 *
 * Caches static assets for offline use.
 * Network-first strategy for API calls, cache-first for static files.
 */

const CACHE_NAME = "voca-v1";
const STATIC_ASSETS = [
    "/",
    "/static/index.html",
    "/static/style.css",
    "/static/app.js",
    "/static/face.js",
    "/static/waveform.js",
    "/static/listener.js",
    "/static/agents-view.js",
    "/static/manifest.json",
];

// Install: pre-cache static assets
self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys
                    .filter((key) => key !== CACHE_NAME)
                    .map((key) => caches.delete(key))
            );
        })
    );
    self.clients.claim();
});

// Fetch: network-first for API, cache-first for static
self.addEventListener("fetch", (event) => {
    const url = new URL(event.request.url);

    // Skip WebSocket, SSE, and API requests
    if (
        event.request.method !== "GET" ||
        url.pathname.startsWith("/ws") ||
        url.pathname.startsWith("/events/") ||
        url.pathname.startsWith("/agents/stream") ||
        url.pathname.startsWith("/chat") ||
        url.pathname.startsWith("/webhook")
    ) {
        return;
    }

    // Static assets: cache-first
    if (url.pathname.startsWith("/static") || url.pathname === "/") {
        event.respondWith(
            caches.match(event.request).then((cached) => {
                if (cached) {
                    // Update cache in background
                    fetch(event.request)
                        .then((response) => {
                            if (response.ok) {
                                caches.open(CACHE_NAME).then((cache) => {
                                    cache.put(event.request, response);
                                });
                            }
                        })
                        .catch(() => {});
                    return cached;
                }
                return fetch(event.request).then((response) => {
                    if (response.ok) {
                        const clone = response.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, clone);
                        });
                    }
                    return response;
                });
            })
        );
        return;
    }

    // Other GET requests: network-first with cache fallback
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
                return caches.match(event.request);
            })
    );
});
