/* === Vera Gesture Engine — Dual-Input (MediaPipe Hands + Keyboard) === */

var VeraGestureEngine = (function () {
    "use strict";

    var videoEl = null;
    var canvasEl = null;
    var canvasCtx = null;
    var hands = null;
    var camera = null;
    var tracking = false;
    var callbacks = [];
    var activityLog = [];

    var DEBOUNCE_MS = 500;
    var lastGestureTime = 0;
    var lastGestureType = "";

    // Swipe tracking
    var swipeHistory = [];
    var SWIPE_THRESHOLD = 0.15;
    var SWIPE_WINDOW_MS = 300;

    // Gesture ripple colors
    var RIPPLE_COLORS = {
        pinch: "rgba(108, 123, 255, 0.5)",
        open_palm: "rgba(74, 222, 128, 0.5)",
        point: "rgba(251, 191, 36, 0.5)",
        swipe_left: "rgba(167, 139, 250, 0.4)",
        swipe_right: "rgba(167, 139, 250, 0.4)",
    };

    function init(video, canvas) {
        videoEl = video;
        canvasEl = canvas;
        if (canvasEl) {
            canvasCtx = canvasEl.getContext("2d");
        }
    }

    function onGesture(callback) {
        callbacks.push(callback);
    }

    function emit(type, detail) {
        var now = Date.now();
        if (now - lastGestureTime < DEBOUNCE_MS && type === lastGestureType) return;

        lastGestureTime = now;
        lastGestureType = type;

        var event = {
            type: type,
            timestamp: now,
            detail: detail || {},
        };

        // Log activity
        activityLog.unshift(event);
        if (activityLog.length > 50) activityLog.pop();

        // Fire callbacks
        for (var i = 0; i < callbacks.length; i++) {
            try { callbacks[i](event); } catch (e) { console.error("Gesture callback error:", e); }
        }

        // Visual ripple
        if (detail && detail.x !== undefined && detail.y !== undefined) {
            showRipple(detail.x, detail.y, RIPPLE_COLORS[type] || "rgba(108, 123, 255, 0.4)");
        }
    }

    function showRipple(x, y, color) {
        var ripple = document.createElement("div");
        ripple.className = "gesture-ripple";
        ripple.style.left = (x - 30) + "px";
        ripple.style.top = (y - 30) + "px";
        ripple.style.background = color;
        document.body.appendChild(ripple);
        setTimeout(function () {
            if (ripple.parentNode) ripple.parentNode.removeChild(ripple);
        }, 600);
    }

    // --- MediaPipe Hands ---

    function startCamera() {
        if (tracking || !videoEl) return;

        try {
            if (typeof Hands === "undefined") {
                console.warn("MediaPipe Hands not loaded — gesture detection unavailable");
                tracking = false;
                return;
            }

            hands = new Hands({
                locateFile: function (file) {
                    return "https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/" + file;
                },
            });

            hands.setOptions({
                maxNumHands: 1,
                modelComplexity: 0,
                minDetectionConfidence: 0.6,
                minTrackingConfidence: 0.5,
            });

            hands.onResults(onHandResults);

            camera = new Camera(videoEl, {
                onFrame: async function () {
                    if (hands) await hands.send({ image: videoEl });
                },
                width: 320,
                height: 240,
            });

            camera.start();
            tracking = true;
        } catch (e) {
            console.error("Failed to start gesture camera:", e);
            tracking = false;
        }
    }

    function stopCamera() {
        if (camera) {
            camera.stop();
            camera = null;
        }
        if (hands) {
            hands.close();
            hands = null;
        }
        tracking = false;

        if (canvasCtx && canvasEl) {
            canvasCtx.clearRect(0, 0, canvasEl.width, canvasEl.height);
        }
    }

    function toggleCamera() {
        if (tracking) {
            stopCamera();
        } else {
            startCamera();
        }
    }

    function onHandResults(results) {
        if (!canvasEl || !canvasCtx) return;

        // Set canvas dimensions
        canvasEl.width = canvasEl.clientWidth;
        canvasEl.height = canvasEl.clientHeight;
        canvasCtx.clearRect(0, 0, canvasEl.width, canvasEl.height);

        if (!results.multiHandLandmarks || results.multiHandLandmarks.length === 0) {
            swipeHistory = [];
            return;
        }

        var landmarks = results.multiHandLandmarks[0];

        // Draw hand
        drawHand(landmarks);

        // Classify gesture
        classifyGesture(landmarks);
    }

    function drawHand(landmarks) {
        if (typeof drawConnectors !== "undefined" && typeof drawLandmarks !== "undefined") {
            drawConnectors(canvasCtx, landmarks, Hands.HAND_CONNECTIONS, {
                color: "rgba(108, 123, 255, 0.4)",
                lineWidth: 2,
            });
            drawLandmarks(canvasCtx, landmarks, {
                color: "rgba(108, 123, 255, 0.8)",
                lineWidth: 1,
                radius: 3,
            });
        } else {
            // Fallback: draw circles
            for (var i = 0; i < landmarks.length; i++) {
                var lm = landmarks[i];
                canvasCtx.beginPath();
                canvasCtx.arc(
                    lm.x * canvasEl.width,
                    lm.y * canvasEl.height,
                    3, 0, Math.PI * 2
                );
                canvasCtx.fillStyle = "rgba(108, 123, 255, 0.8)";
                canvasCtx.fill();
            }
        }
    }

    function classifyGesture(landmarks) {
        // Landmark indices:
        // 0=wrist, 4=thumb_tip, 5=index_mcp, 8=index_tip, 9=middle_mcp
        // 12=middle_tip, 13=ring_mcp, 16=ring_tip, 17=pinky_mcp, 20=pinky_tip

        var thumbTip = landmarks[4];
        var indexTip = landmarks[8];
        var indexMcp = landmarks[5];
        var middleTip = landmarks[12];
        var middleMcp = landmarks[9];
        var ringTip = landmarks[16];
        var ringMcp = landmarks[13];
        var pinkyTip = landmarks[20];
        var pinkyMcp = landmarks[17];
        var wrist = landmarks[0];

        // Calculate screen coords for ripple
        var handCenterX = wrist.x * window.innerWidth;
        var handCenterY = wrist.y * window.innerHeight;

        // --- Pinch detection ---
        var thumbIndexDist = dist2D(thumbTip, indexTip);
        if (thumbIndexDist < 0.05) {
            emit("pinch", { x: handCenterX, y: handCenterY });
            return;
        }

        // --- Open Palm detection ---
        var indexExtended = indexTip.y < indexMcp.y;
        var middleExtended = middleTip.y < middleMcp.y;
        var ringExtended = ringTip.y < ringMcp.y;
        var pinkyExtended = pinkyTip.y < pinkyMcp.y;
        var thumbExtended = thumbTip.x < landmarks[3].x; // thumb extended outward

        if (indexExtended && middleExtended && ringExtended && pinkyExtended) {
            // Check spread — distance between index and pinky tips
            var spread = dist2D(indexTip, pinkyTip);
            if (spread > 0.12) {
                emit("open_palm", { x: handCenterX, y: handCenterY });
                return;
            }
        }

        // --- Point detection ---
        var middleCurled = middleTip.y > middleMcp.y;
        var ringCurled = ringTip.y > ringMcp.y;
        var pinkyCurled = pinkyTip.y > pinkyMcp.y;

        if (indexExtended && middleCurled && ringCurled && pinkyCurled) {
            emit("point", { x: handCenterX, y: handCenterY });
            return;
        }

        // --- Swipe detection ---
        var now = Date.now();
        swipeHistory.push({ x: wrist.x, t: now });

        // Clean old entries
        swipeHistory = swipeHistory.filter(function (e) {
            return now - e.t < SWIPE_WINDOW_MS;
        });

        if (swipeHistory.length > 3) {
            var oldest = swipeHistory[0];
            var newest = swipeHistory[swipeHistory.length - 1];
            var deltaX = newest.x - oldest.x;

            if (Math.abs(deltaX) > SWIPE_THRESHOLD) {
                if (deltaX > 0) {
                    emit("swipe_right", { x: handCenterX, y: handCenterY });
                } else {
                    emit("swipe_left", { x: handCenterX, y: handCenterY });
                }
                swipeHistory = [];
            }
        }
    }

    function dist2D(a, b) {
        var dx = a.x - b.x;
        var dy = a.y - b.y;
        return Math.sqrt(dx * dx + dy * dy);
    }

    function getActivityLog() {
        return activityLog.slice();
    }

    function isTracking() {
        return tracking;
    }

    return {
        init: init,
        startCamera: startCamera,
        stopCamera: stopCamera,
        toggleCamera: toggleCamera,
        onGesture: onGesture,
        getActivityLog: getActivityLog,
        isTracking: isTracking,
    };
})();
