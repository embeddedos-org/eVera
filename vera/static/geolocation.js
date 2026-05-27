/**
 * eVera — Geolocation Module
 *
 * Requests GPS permission from the browser and sends location updates
 * to the eVera backend so that location-aware agents (weather, travel,
 * nearby search, etc.) can use the user's current position automatically.
 *
 * The user is prompted once; their choice is persisted in localStorage.
 * Location updates are sent every 5 minutes (or on significant movement).
 */

(function () {
    "use strict";

    const STORAGE_KEY = "vera_location_enabled";
    const UPDATE_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes
    const MIN_DISTANCE_M = 500; // only send update if moved > 500 m

    let _watchId = null;
    let _lastLat = null;
    let _lastLon = null;
    let _intervalId = null;

    /**
     * Haversine distance in metres between two lat/lon pairs.
     */
    function _haversine(lat1, lon1, lat2, lon2) {
        const R = 6371000;
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLon / 2) * Math.sin(dLon / 2);
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    /**
     * Send a location update to the eVera backend.
     */
    async function _sendLocation(position) {
        const { latitude, longitude, accuracy, altitude } = position.coords;

        // Skip if not moved enough
        if (_lastLat !== null && _lastLon !== null) {
            const dist = _haversine(_lastLat, _lastLon, latitude, longitude);
            if (dist < MIN_DISTANCE_M) return;
        }

        _lastLat = latitude;
        _lastLon = longitude;

        try {
            await fetch("/location/update", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    latitude: latitude,
                    longitude: longitude,
                    accuracy: accuracy || null,
                    altitude: altitude || null,
                }),
            });
            console.debug("[eVera] Location updated:", latitude.toFixed(4), longitude.toFixed(4));
        } catch (e) {
            console.warn("[eVera] Failed to send location update:", e);
        }
    }

    function _onError(err) {
        console.warn("[eVera] Geolocation error:", err.message);
    }

    /**
     * Start watching GPS position and sending updates to the server.
     */
    function start() {
        if (!navigator.geolocation) {
            console.warn("[eVera] Geolocation not supported by this browser");
            return;
        }
        if (_watchId !== null) return; // already running

        const options = {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 60000,
        };

        // Get initial position immediately
        navigator.geolocation.getCurrentPosition(_sendLocation, _onError, options);

        // Watch for changes
        _watchId = navigator.geolocation.watchPosition(_sendLocation, _onError, options);

        // Also send periodic updates (in case watchPosition doesn't fire)
        _intervalId = setInterval(function () {
            navigator.geolocation.getCurrentPosition(_sendLocation, _onError, options);
        }, UPDATE_INTERVAL_MS);

        localStorage.setItem(STORAGE_KEY, "true");
        console.info("[eVera] Location tracking started");
    }

    /**
     * Stop watching GPS position.
     */
    function stop() {
        if (_watchId !== null) {
            navigator.geolocation.clearWatch(_watchId);
            _watchId = null;
        }
        if (_intervalId !== null) {
            clearInterval(_intervalId);
            _intervalId = null;
        }
        localStorage.setItem(STORAGE_KEY, "false");
        console.info("[eVera] Location tracking stopped");
    }

    /**
     * Ask the user for permission and start tracking if granted.
     * Only asks once (persists decision in localStorage).
     */
    function requestAndStart() {
        if (!navigator.geolocation) return;

        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved === "false") return; // user previously declined

        if (saved === "true") {
            // Previously granted — start silently
            start();
            return;
        }

        // First time — request permission via browser API (no custom dialog needed;
        // the browser will show its own permission prompt when we call getCurrentPosition)
        navigator.geolocation.getCurrentPosition(
            function (pos) {
                // Permission granted
                _sendLocation(pos);
                // Now start continuous tracking
                start();
            },
            function (err) {
                // Permission denied or error — don't ask again
                localStorage.setItem(STORAGE_KEY, "false");
                console.info("[eVera] Location permission denied:", err.message);
            },
            { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
        );
    }

    // Expose API
    window.VeraGeo = {
        start: start,
        stop: stop,
        requestAndStart: requestAndStart,
        isRunning: function () { return _watchId !== null; },
    };

    // Auto-start when DOM is ready (non-blocking)
    function _autoStart() {
        // Small delay to avoid blocking initial page load
        setTimeout(requestAndStart, 2000);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", _autoStart);
    } else {
        _autoStart();
    }
})();
