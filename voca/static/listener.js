/* === Voca Listener — Continuous Listening Manager === */

const VocaListener = (function () {
    "use strict";

    // Modes
    const MODE = {
        PUSH: "push",
        WAKE: "wake",
        ALWAYS: "always",
    };

    const WAKE_WORDS = ["hey voca", "voca", "hey buddy"];
    const WAKE_TIMEOUT_MS = 10000;

    let _mode = MODE.PUSH;
    let _recognition = null;
    let _active = false;
    let _wakeDetected = false;
    let _wakeTimer = null;
    let _micStream = null;
    let _supported = false;

    // Callbacks
    let _onTranscript = null; // (text: string) => void
    let _onStateChange = null; // (state: "idle"|"listening"|"wake_listening"|"processing") => void
    let _onWakeWord = null; // () => void
    let _onTranscript = null;
    let _onStateChange = null;
    let _onWakeWord = null;
    let _onMicStream = null;
    let _onInterim = null;
    let _language = "en-US";

    // Supported languages for speech recognition
    const LANGUAGES = {
        "en": "en-US", "es": "es-ES", "fr": "fr-FR", "de": "de-DE",
        "hi": "hi-IN", "te": "te-IN", "ta": "ta-IN", "ja": "ja-JP",
        "ko": "ko-KR", "zh": "zh-CN", "pt": "pt-BR", "ru": "ru-RU",
        "ar": "ar-SA", "it": "it-IT", "nl": "nl-NL", "pl": "pl-PL",
        "tr": "tr-TR", "vi": "vi-VN", "th": "th-TH",
    };

    function init(options) {
        _onTranscript = options.onTranscript || null;
        _onStateChange = options.onStateChange || null;
        _onWakeWord = options.onWakeWord || null;
        _onMicStream = options.onMicStream || null;
        _onInterim = options.onInterim || null;
        _language = options.language || "en-US";

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            _supported = false;
            return false;
        }

        _supported = true;
        _recognition = new SpeechRecognition();
        _recognition.lang = _language;

        _recognition.onresult = _handleResult;
        _recognition.onend = _handleEnd;
        _recognition.onerror = _handleError;

        return true;
    }

    function setLanguage(langCode) {
        _language = LANGUAGES[langCode] || langCode;
        if (_recognition) {
            _recognition.lang = _language;
        }
        // Restart if active
        if (_active) {
            stop();
            start();
        }
    }

    function getLanguage() {
        return _language;
    }

    function setMode(mode) {
        if (!Object.values(MODE).includes(mode)) return;
        const wasActive = _active;
        if (wasActive) stop();

        _mode = mode;
        _wakeDetected = false;

        if (mode === MODE.ALWAYS || mode === MODE.WAKE) {
            start();
        }

        _emitState();
    }

    function getMode() {
        return _mode;
    }

    function isSupported() {
        return _supported;
    }

    function start() {
        if (!_recognition || _active) return;

        _recognition.continuous = (_mode === MODE.ALWAYS || _mode === MODE.WAKE);
        _recognition.interimResults = (_mode === MODE.WAKE || _mode === MODE.ALWAYS);

        _active = true;
        _acquireMic();

        try {
            _recognition.start();
        } catch (e) {
            // Already started
        }

        _emitState();
    }

    function stop() {
        if (!_recognition) return;
        _active = false;
        _wakeDetected = false;

        try {
            _recognition.stop();
        } catch (e) {
            // Already stopped
        }

        if (_wakeTimer) {
            clearTimeout(_wakeTimer);
            _wakeTimer = null;
        }

        _emitState();
    }

    function toggle() {
        if (_mode === MODE.PUSH) {
            if (_active) stop();
            else start();
        }
    }

    function isActive() {
        return _active;
    }

    async function _acquireMic() {
        if (_micStream) return;
        try {
            _micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            if (_onMicStream) _onMicStream(_micStream);
        } catch (e) {
            console.error("Mic access denied:", e);
        }
    }

    function _handleResult(event) {
        const results = event.results;
        const latest = results[results.length - 1];

        if (_mode === MODE.WAKE && !_wakeDetected) {
            // Check interim results for wake word
            for (let i = 0; i < latest.length; i++) {
                const text = latest[i].transcript.toLowerCase().trim();
                for (const ww of WAKE_WORDS) {
                    if (text.includes(ww)) {
                        _wakeDetected = true;
                        if (_onWakeWord) _onWakeWord();
                        _emitState();

                        // Start timeout — go back to idle if no command
                        _wakeTimer = setTimeout(() => {
                            _wakeDetected = false;
                            _emitState();
                        }, WAKE_TIMEOUT_MS);

                        return;
                    }
                }
            }
            // Show interim text for wake mode
            if (!latest.isFinal && _onInterim) {
                _onInterim(latest[0].transcript);
            }
            return;
        }

        if (latest.isFinal) {
            const transcript = latest[0].transcript.trim();
            if (!transcript) return;

            // In wake mode, skip if the transcript is just the wake word
            if (_mode === MODE.WAKE) {
                let isJustWake = false;
                for (const ww of WAKE_WORDS) {
                    if (transcript.toLowerCase() === ww) {
                        isJustWake = true;
                        break;
                    }
                }
                if (isJustWake) return;

                // Reset wake state after capturing command
                _wakeDetected = false;
                if (_wakeTimer) {
                    clearTimeout(_wakeTimer);
                    _wakeTimer = null;
                }
            }

            if (_onTranscript) _onTranscript(transcript);
            _emitState();
        } else if (_onInterim) {
            _onInterim(latest[0].transcript);
        }
    }

    function _handleEnd() {
        if (_mode === MODE.ALWAYS || _mode === MODE.WAKE) {
            // Auto-restart continuous modes
            if (_active) {
                setTimeout(() => {
                    if (_active) {
                        try {
                            _recognition.start();
                        } catch (e) {
                            // ignore
                        }
                    }
                }, 100);
            }
        } else {
            _active = false;
            _emitState();
        }
    }

    function _handleError(event) {
        if (event.error === "no-speech" || event.error === "aborted") {
            // Not a real error in continuous mode
            return;
        }
        console.error("Speech recognition error:", event.error);
        if (_mode === MODE.PUSH) {
            _active = false;
            _emitState();
        }
    }

    function _emitState() {
        if (!_onStateChange) return;
        let s;
        if (!_active) {
            s = "idle";
        } else if (_mode === MODE.WAKE && !_wakeDetected) {
            s = "idle"; // Passively listening for wake word
        } else if (_mode === MODE.WAKE && _wakeDetected) {
            s = "wake_listening";
        } else {
            s = "listening";
        }
        _onStateChange(s);
    }

    function destroy() {
        stop();
        if (_micStream) {
            _micStream.getTracks().forEach(t => t.stop());
            _micStream = null;
        }
    }

    return {
        MODE,
        LANGUAGES,
        init,
        setMode,
        getMode,
        setLanguage,
        getLanguage,
        isSupported,
        start,
        stop,
        toggle,
        isActive,
        destroy,
    };
})();
