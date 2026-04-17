/* === Voca Face — Animated SVG Face with Expressions === */

const VocaFace = (function () {
    "use strict";

    const EXPRESSIONS = {
        idle: { eyeScale: 1, eyeCurve: false, mouthWidth: 20, mouthCurve: 5, pupilX: 0, pupilY: 0, glow: "rgba(108, 123, 255, 0.15)" },
        listening: { eyeScale: 1.15, eyeCurve: false, mouthWidth: 16, mouthCurve: 2, pupilX: 0, pupilY: 0, glow: "rgba(108, 123, 255, 0.4)" },
        thinking: { eyeScale: 1, eyeCurve: false, mouthWidth: 12, mouthCurve: 0, pupilX: 4, pupilY: -3, glow: "rgba(245, 158, 11, 0.35)" },
        speaking: { eyeScale: 1.05, eyeCurve: false, mouthWidth: 22, mouthCurve: 8, pupilX: 0, pupilY: 0, glow: "rgba(74, 222, 128, 0.4)" },
        happy: { eyeScale: 0.9, eyeCurve: true, mouthWidth: 26, mouthCurve: 12, pupilX: 0, pupilY: 0, glow: "rgba(74, 222, 128, 0.45)" },
        sad: { eyeScale: 0.85, eyeCurve: false, mouthWidth: 18, mouthCurve: -6, pupilX: 0, pupilY: 3, glow: "rgba(96, 165, 250, 0.3)" },
        excited: { eyeScale: 1.25, eyeCurve: false, mouthWidth: 28, mouthCurve: 14, pupilX: 0, pupilY: 0, glow: "rgba(251, 191, 36, 0.5)" },
        error: { eyeScale: 1, eyeCurve: false, mouthWidth: 20, mouthCurve: -4, pupilX: 0, pupilY: 0, glow: "rgba(244, 63, 94, 0.45)" },
    };

    let _canvas = null;
    let _ctx = null;
    let _expression = "idle";
    let _target = EXPRESSIONS.idle;
    let _current = { ...EXPRESSIONS.idle };
    let _blinkTimer = 0;
    let _blinkState = 0; // 0 = open, 1 = closing, 2 = closed, 3 = opening
    let _bobPhase = 0;
    let _mouthPhase = 0;
    let _speakAmplitude = 0;
    let _animFrame = null;
    let _glowContainer = null;

    function init(canvasId, glowContainerId) {
        _canvas = document.getElementById(canvasId);
        if (!_canvas) return;
        _ctx = _canvas.getContext("2d");
        _glowContainer = document.getElementById(glowContainerId);

        _resize();
        window.addEventListener("resize", _resize);
        _scheduleNextBlink();
        _animate();
    }

    function _resize() {
        const container = _canvas.parentElement;
        const size = Math.min(container.clientWidth, 200);
        _canvas.width = size;
        _canvas.height = size;
    }

    function setExpression(name) {
        if (EXPRESSIONS[name]) {
            _expression = name;
            _target = EXPRESSIONS[name];
        }
    }

    function getExpression() {
        return _expression;
    }

    function setSpeakAmplitude(amp) {
        _speakAmplitude = Math.min(1, Math.max(0, amp));
    }

    function _lerp(a, b, t) {
        return a + (b - a) * t;
    }

    function _scheduleNextBlink() {
        const delay = 2000 + Math.random() * 4000;
        setTimeout(() => {
            _blinkState = 1;
            _scheduleNextBlink();
        }, delay);
    }

    function _animate() {
        const t = 0.12;
        _current.eyeScale = _lerp(_current.eyeScale, _target.eyeScale, t);
        _current.mouthWidth = _lerp(_current.mouthWidth, _target.mouthWidth, t);
        _current.mouthCurve = _lerp(_current.mouthCurve, _target.mouthCurve, t);
        _current.pupilX = _lerp(_current.pupilX, _target.pupilX, t);
        _current.pupilY = _lerp(_current.pupilY, _target.pupilY, t);

        // Blink animation
        if (_blinkState === 1) {
            _blinkTimer += 0.25;
            if (_blinkTimer >= 1) { _blinkState = 2; _blinkTimer = 0; }
        } else if (_blinkState === 2) {
            _blinkTimer += 0.3;
            if (_blinkTimer >= 1) { _blinkState = 3; _blinkTimer = 0; }
        } else if (_blinkState === 3) {
            _blinkTimer += 0.25;
            if (_blinkTimer >= 1) { _blinkState = 0; _blinkTimer = 0; }
        }

        _bobPhase += 0.02;
        _mouthPhase += 0.15;

        _draw();
        _updateGlow();
        _animFrame = requestAnimationFrame(_animate);
    }

    function _draw() {
        if (!_ctx) return;
        const w = _canvas.width;
        const h = _canvas.height;
        const cx = w / 2;
        const cy = h / 2;
        const scale = w / 200;

        _ctx.clearRect(0, 0, w, h);

        // Bob offset
        const bobY = Math.sin(_bobPhase) * 2 * scale;

        // Face circle
        _ctx.beginPath();
        _ctx.arc(cx, cy + bobY, 70 * scale, 0, Math.PI * 2);
        _ctx.fillStyle = "#1e2130";
        _ctx.fill();
        _ctx.strokeStyle = "#3b4cca";
        _ctx.lineWidth = 2.5 * scale;
        _ctx.stroke();

        // Eye positions
        const eyeSpacing = 22 * scale;
        const eyeY = cy - 12 * scale + bobY;
        const eyeRadius = 8 * _current.eyeScale * scale;
        const pupilRadius = 4 * _current.eyeScale * scale;

        // Blink squish factor
        let blinkSquish = 1;
        if (_blinkState === 1) blinkSquish = 1 - _blinkTimer;
        else if (_blinkState === 2) blinkSquish = 0.05;
        else if (_blinkState === 3) blinkSquish = _blinkTimer;

        if (_expression === "error") {
            _drawX(cx - eyeSpacing, eyeY, eyeRadius, scale);
            _drawX(cx + eyeSpacing, eyeY, eyeRadius, scale);
        } else if (_target.eyeCurve) {
            // Happy crescents ^‿^
            _drawCrescentEye(cx - eyeSpacing, eyeY, eyeRadius, scale);
            _drawCrescentEye(cx + eyeSpacing, eyeY, eyeRadius, scale);
        } else {
            _drawEye(cx - eyeSpacing, eyeY, eyeRadius, pupilRadius, blinkSquish, scale);
            _drawEye(cx + eyeSpacing, eyeY, eyeRadius, pupilRadius, blinkSquish, scale);
        }

        // Mouth
        const mouthY = cy + 18 * scale + bobY;
        const mw = _current.mouthWidth * scale;
        let mc = _current.mouthCurve * scale;

        // Speaking mouth animation
        if (_expression === "speaking") {
            mc += Math.sin(_mouthPhase) * _speakAmplitude * 8 * scale;
        }

        if (_expression === "error") {
            _drawZigzagMouth(cx, mouthY, mw, scale);
        } else {
            _drawMouth(cx, mouthY, mw, mc, scale);
        }

        // Thinking dots
        if (_expression === "thinking") {
            _drawThinkingDots(cx + 35 * scale, cy - 25 * scale + bobY, scale);
        }
    }

    function _drawEye(x, y, radius, pupilRadius, blinkSquish, scale) {
        // White
        _ctx.save();
        _ctx.translate(x, y);
        _ctx.scale(1, blinkSquish);

        _ctx.beginPath();
        _ctx.arc(0, 0, radius, 0, Math.PI * 2);
        _ctx.fillStyle = "#e4e6f0";
        _ctx.fill();

        // Pupil
        if (blinkSquish > 0.3) {
            _ctx.beginPath();
            _ctx.arc(_current.pupilX * scale * 0.5, _current.pupilY * scale * 0.5, pupilRadius, 0, Math.PI * 2);
            _ctx.fillStyle = "#1a1d27";
            _ctx.fill();

            // Pupil highlight
            _ctx.beginPath();
            _ctx.arc(
                _current.pupilX * scale * 0.5 + pupilRadius * 0.35,
                _current.pupilY * scale * 0.5 - pupilRadius * 0.35,
                pupilRadius * 0.3, 0, Math.PI * 2
            );
            _ctx.fillStyle = "#fff";
            _ctx.fill();
        }

        _ctx.restore();
    }

    function _drawCrescentEye(x, y, radius, scale) {
        _ctx.beginPath();
        _ctx.arc(x, y + radius * 0.3, radius, Math.PI, 0, false);
        _ctx.strokeStyle = "#e4e6f0";
        _ctx.lineWidth = 2.5 * scale;
        _ctx.lineCap = "round";
        _ctx.stroke();
    }

    function _drawX(x, y, radius, scale) {
        _ctx.strokeStyle = "#f43f5e";
        _ctx.lineWidth = 2.5 * scale;
        _ctx.lineCap = "round";
        const r = radius * 0.7;

        _ctx.beginPath();
        _ctx.moveTo(x - r, y - r);
        _ctx.lineTo(x + r, y + r);
        _ctx.stroke();

        _ctx.beginPath();
        _ctx.moveTo(x + r, y - r);
        _ctx.lineTo(x - r, y + r);
        _ctx.stroke();
    }

    function _drawMouth(x, y, width, curve, scale) {
        _ctx.beginPath();
        _ctx.moveTo(x - width / 2, y);
        _ctx.quadraticCurveTo(x, y + curve, x + width / 2, y);
        _ctx.strokeStyle = "#e4e6f0";
        _ctx.lineWidth = 2.5 * scale;
        _ctx.lineCap = "round";
        _ctx.stroke();

        // Fill mouth area when wide open (speaking / happy / excited)
        if (curve > 6 * scale) {
            _ctx.beginPath();
            _ctx.moveTo(x - width / 2, y);
            _ctx.quadraticCurveTo(x, y + curve, x + width / 2, y);
            _ctx.fillStyle = "rgba(30, 33, 48, 0.8)";
            _ctx.fill();
        }
    }

    function _drawZigzagMouth(x, y, width, scale) {
        const segments = 5;
        const segW = width / segments;
        const amp = 3 * scale;

        _ctx.beginPath();
        _ctx.moveTo(x - width / 2, y);
        for (let i = 1; i <= segments; i++) {
            const sx = x - width / 2 + i * segW;
            const sy = y + (i % 2 === 0 ? -amp : amp);
            _ctx.lineTo(sx, sy);
        }
        _ctx.strokeStyle = "#f43f5e";
        _ctx.lineWidth = 2 * scale;
        _ctx.lineCap = "round";
        _ctx.lineJoin = "round";
        _ctx.stroke();
    }

    function _drawThinkingDots(x, y, scale) {
        const phase = Date.now() / 400;
        for (let i = 0; i < 3; i++) {
            const alpha = 0.3 + 0.7 * Math.abs(Math.sin(phase + i * 0.8));
            _ctx.beginPath();
            _ctx.arc(x + i * 7 * scale, y - i * 4 * scale, 2.5 * scale, 0, Math.PI * 2);
            _ctx.fillStyle = `rgba(245, 158, 11, ${alpha})`;
            _ctx.fill();
        }
    }

    function _updateGlow() {
        if (!_glowContainer) return;
        const color = _target.glow || "rgba(108, 123, 255, 0.15)";
        _glowContainer.style.boxShadow = `0 0 40px 10px ${color}, inset 0 0 20px 5px ${color}`;
    }

    function destroy() {
        if (_animFrame) cancelAnimationFrame(_animFrame);
        window.removeEventListener("resize", _resize);
    }

    return {
        init,
        setExpression,
        getExpression,
        setSpeakAmplitude,
        destroy,
        EXPRESSIONS: Object.keys(EXPRESSIONS),
    };
})();
