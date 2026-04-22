/* === Vera Waveform — Audio Visualizer using Web Audio API === */

const VeraWaveform = (function () {
    "use strict";

    let _canvas = null;
    let _ctx = null;
    let _audioCtx = null;
    let _analyser = null;
    let _source = null;
    let _dataArray = null;
    let _animFrame = null;
    let _active = false;
    let _stream = null;

    const COLORS = {
        idle: { r: 108, g: 123, b: 255 },
        listening: { r: 108, g: 123, b: 255 },
        thinking: { r: 245, g: 158, b: 11 },
        speaking: { r: 74, g: 222, b: 128 },
        happy: { r: 74, g: 222, b: 128 },
        sad: { r: 96, g: 165, b: 250 },
        excited: { r: 251, g: 191, b: 36 },
        error: { r: 244, g: 63, b: 94 },
    };

    let _color = COLORS.idle;

    function init(canvasId) {
        _canvas = document.getElementById(canvasId);
        if (!_canvas) return;
        _ctx = _canvas.getContext("2d");
        _resize();
        window.addEventListener("resize", _resize);
        _drawIdle();
    }

    function _resize() {
        if (!_canvas) return;
        const container = _canvas.parentElement;
        _canvas.width = container.clientWidth;
        _canvas.height = 48;
    }

    function connectMic(stream) {
        _stream = stream;
        if (!_audioCtx) {
            _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (_audioCtx.state === "suspended") {
            _audioCtx.resume();
        }

        _analyser = _audioCtx.createAnalyser();
        _analyser.fftSize = 128;
        _analyser.smoothingTimeConstant = 0.8;

        _source = _audioCtx.createMediaStreamSource(stream);
        _source.connect(_analyser);

        _dataArray = new Uint8Array(_analyser.frequencyBinCount);
        _active = true;
        _animate();
    }

    function disconnect() {
        _active = false;
        if (_source) {
            _source.disconnect();
            _source = null;
        }
        if (_animFrame) {
            cancelAnimationFrame(_animFrame);
            _animFrame = null;
        }
        _drawIdle();
    }

    function setColor(expression) {
        _color = COLORS[expression] || COLORS.idle;
    }

    function getAmplitude() {
        if (!_analyser || !_dataArray) return 0;
        _analyser.getByteFrequencyData(_dataArray);
        let sum = 0;
        for (let i = 0; i < _dataArray.length; i++) {
            sum += _dataArray[i];
        }
        return sum / (_dataArray.length * 255);
    }

    function _animate() {
        if (!_active) return;

        _analyser.getByteFrequencyData(_dataArray);
        _draw();
        _animFrame = requestAnimationFrame(_animate);
    }

    function _draw() {
        if (!_ctx) return;
        const w = _canvas.width;
        const h = _canvas.height;

        _ctx.clearRect(0, 0, w, h);

        const barCount = _dataArray.length;
        const barWidth = Math.max(2, (w / barCount) - 1);
        const gap = 1;

        for (let i = 0; i < barCount; i++) {
            const val = _dataArray[i] / 255;
            const barHeight = Math.max(2, val * h * 0.9);
            const x = i * (barWidth + gap);
            const y = (h - barHeight) / 2;

            const alpha = 0.4 + val * 0.6;
            _ctx.fillStyle = `rgba(${_color.r}, ${_color.g}, ${_color.b}, ${alpha})`;
            _ctx.beginPath();
            _ctx.roundRect(x, y, barWidth, barHeight, 1);
            _ctx.fill();
        }
    }

    function _drawIdle() {
        if (!_ctx) return;
        const w = _canvas.width;
        const h = _canvas.height;

        _ctx.clearRect(0, 0, w, h);

        const barCount = 64;
        const barWidth = Math.max(2, (w / barCount) - 1);
        const gap = 1;
        const time = Date.now() / 1000;

        for (let i = 0; i < barCount; i++) {
            const wave = Math.sin(time * 1.5 + i * 0.3) * 0.15 + 0.15;
            const barHeight = Math.max(2, wave * h);
            const x = i * (barWidth + gap);
            const y = (h - barHeight) / 2;

            _ctx.fillStyle = `rgba(${_color.r}, ${_color.g}, ${_color.b}, 0.25)`;
            _ctx.beginPath();
            _ctx.roundRect(x, y, barWidth, barHeight, 1);
            _ctx.fill();
        }

        if (!_active) {
            requestAnimationFrame(_drawIdle);
        }
    }

    function getStream() {
        return _stream;
    }

    function destroy() {
        disconnect();
        if (_audioCtx) {
            _audioCtx.close();
            _audioCtx = null;
        }
        window.removeEventListener("resize", _resize);
    }

    return {
        init,
        connectMic,
        disconnect,
        setColor,
        getAmplitude,
        getStream,
        destroy,
    };
})();
