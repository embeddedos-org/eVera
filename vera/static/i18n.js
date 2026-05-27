/**
 * eVera — Internationalization (i18n) Module
 *
 * Loads UI strings from the server for the current language and applies
 * them to all elements with [data-i18n] and [data-i18n-placeholder] attributes.
 *
 * Supports 19 languages: en, es, fr, de, hi, zh, ar, pt, ja, ko, ru, it,
 *                         te, ta, nl, pl, tr, vi, th
 */

(function () {
    "use strict";

    // Cached strings per language
    const _cache = {};

    /**
     * Load strings for the given language code from the server.
     * Falls back to English if the language is not available.
     */
    async function loadStrings(lang) {
        if (_cache[lang]) return _cache[lang];
        try {
            const res = await fetch(`/i18n/strings/${lang}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            _cache[lang] = data.strings || {};
            return _cache[lang];
        } catch (e) {
            console.warn(`[i18n] Failed to load strings for "${lang}", falling back to "en"`, e);
            if (lang !== "en") return loadStrings("en");
            return {};
        }
    }

    /**
     * Apply loaded strings to the DOM.
     * Elements with [data-i18n="key"] get their textContent replaced.
     * Elements with [data-i18n-placeholder="key"] get their placeholder replaced.
     */
    function applyStrings(strings) {
        document.querySelectorAll("[data-i18n]").forEach(function (el) {
            const key = el.getAttribute("data-i18n");
            if (strings[key] !== undefined) {
                el.textContent = strings[key];
            }
        });
        document.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
            const key = el.getAttribute("data-i18n-placeholder");
            if (strings[key] !== undefined) {
                el.placeholder = strings[key];
            }
        });
        document.querySelectorAll("[data-i18n-title]").forEach(function (el) {
            const key = el.getAttribute("data-i18n-title");
            if (strings[key] !== undefined) {
                el.title = strings[key];
            }
        });
    }

    /**
     * Set the active language, persist to localStorage, update DOM.
     */
    async function setLanguage(lang) {
        localStorage.setItem("vera_lang", lang);
        document.documentElement.lang = lang;
        // RTL for Arabic
        document.documentElement.dir = (lang === "ar") ? "rtl" : "ltr";
        const strings = await loadStrings(lang);
        applyStrings(strings);
        // Sync language selector
        const sel = document.getElementById("langSelector");
        if (sel && sel.value !== lang) sel.value = lang;
        // Expose strings globally for other modules
        window.VERA_STRINGS = strings;
        window.VERA_LANG = lang;
    }

    /**
     * Get a translated string by key, with optional fallback.
     */
    function t(key, fallback) {
        const strings = window.VERA_STRINGS || {};
        return strings[key] !== undefined ? strings[key] : (fallback || key);
    }

    // --- Initialization ---
    async function init() {
        const lang = window.VERA_LANG ||
                     localStorage.getItem("vera_lang") ||
                     (navigator.language || "en").split("-")[0];
        await setLanguage(lang);

        // Wire up the language selector
        const sel = document.getElementById("langSelector");
        if (sel) {
            // Set current value
            if (sel.value !== lang) sel.value = lang;
            sel.addEventListener("change", function () {
                setLanguage(sel.value);
                // Also update speech recognition language
                if (typeof VeraListener !== "undefined") {
                    VeraListener.setLanguage(sel.value);
                }
            });
        }
    }

    // Expose API
    window.VeraI18n = {
        init: init,
        setLanguage: setLanguage,
        t: t,
        loadStrings: loadStrings,
    };

    // Auto-init when DOM is ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
