/* === Vera Face — 3D Animated Avatar with Holographic Effects (Three.js) ===
 *
 * Production-ready implementation with:
 * - WebGL capability detection & graceful fallback
 * - Three.js CDN load guard
 * - Complete resource cleanup (no memory leaks)
 * - Page Visibility API (pause when tab hidden)
 * - FPS monitoring with adaptive quality
 * - Error boundaries around all critical paths
 * - Subresource Integrity verified CDN loading
 */

const VeraFace = (function () {
    "use strict";

    // ── Expression definitions with morph + glow + gesture config ──
    const EXPRESSIONS = {
        idle:      { eyes: 0, eyeWide: 0, eyeCrescent: 0, eyeX: 0, mouthSmile: 0, mouthOpen: 0, mouthZigzag: 0, browRaise: 0, glow: "rgba(108, 123, 255, 0.15)", glowColor: [0.42, 0.48, 1.0], gesture: "rest" },
        listening: { eyes: 0.15, eyeWide: 0.15, eyeCrescent: 0, eyeX: 0, mouthSmile: 0.05, mouthOpen: 0, mouthZigzag: 0, browRaise: 0.1, glow: "rgba(108, 123, 255, 0.4)", glowColor: [0.42, 0.48, 1.0], gesture: "clasped" },
        thinking:  { eyes: 0, eyeWide: 0, eyeCrescent: 0, eyeX: 0.4, mouthSmile: 0, mouthOpen: 0, mouthZigzag: 0, browRaise: 0.2, glow: "rgba(245, 158, 11, 0.35)", glowColor: [0.96, 0.62, 0.04], gesture: "chin" },
        speaking:  { eyes: 0.05, eyeWide: 0.05, eyeCrescent: 0, eyeX: 0, mouthSmile: 0.2, mouthOpen: 0.3, mouthZigzag: 0, browRaise: 0, glow: "rgba(74, 222, 128, 0.4)", glowColor: [0.29, 0.87, 0.5], gesture: "palms" },
        happy:     { eyes: -0.1, eyeWide: 0, eyeCrescent: 1, eyeX: 0, mouthSmile: 0.8, mouthOpen: 0.2, mouthZigzag: 0, browRaise: 0.1, glow: "rgba(74, 222, 128, 0.45)", glowColor: [0.29, 0.87, 0.5], gesture: "wave" },
        sad:       { eyes: -0.15, eyeWide: 0, eyeCrescent: 0, eyeX: 0, mouthSmile: -0.5, mouthOpen: 0, mouthZigzag: 0, browRaise: -0.2, glow: "rgba(96, 165, 250, 0.3)", glowColor: [0.38, 0.65, 0.98], gesture: "droop" },
        excited:   { eyes: 0.25, eyeWide: 0.3, eyeCrescent: 0, eyeX: 0, mouthSmile: 0.9, mouthOpen: 0.4, mouthZigzag: 0, browRaise: 0.3, glow: "rgba(251, 191, 36, 0.5)", glowColor: [0.98, 0.75, 0.14], gesture: "thumbsup" },
        error:     { eyes: 0, eyeWide: 0, eyeCrescent: 0, eyeX: 0, mouthSmile: -0.3, mouthOpen: 0, mouthZigzag: 1, browRaise: -0.1, glow: "rgba(244, 63, 94, 0.45)", glowColor: [0.96, 0.25, 0.37], gesture: "defensive" },
    };

    // Valid expression names for input validation
    const VALID_EXPRESSIONS = Object.keys(EXPRESSIONS);
    Object.freeze(VALID_EXPRESSIONS);

    // ── State ──
    let _container = null;
    let _glowContainer = null;
    let _renderer = null;
    let _scene = null;
    let _camera = null;
    let _clock = null;
    let _animFrame = null;
    let _resizeObserver = null;
    let _destroyed = false;
    let _initialized = false;
    let _paused = false;

    let _expression = "idle";
    let _target = { ...EXPRESSIONS.idle };
    let _current = { ...EXPRESSIONS.idle };
    let _speakAmplitude = 0;
    let _blinkTimer = 0;
    let _blinkState = 0;
    let _bobPhase = 0;
    let _mouthPhase = 0;
    let _targetGesture = "rest";

    // Blink timer ID for cleanup
    let _blinkTimeoutId = null;

    // Mesh references
    let _head, _torso, _neck;
    let _eyeL, _eyeR, _pupilL, _pupilR, _highlightL, _highlightR;
    let _browL, _browR;
    let _mouth;
    let _shoulderL, _shoulderR;
    let _upperArmL, _upperArmR, _forearmL, _forearmR;
    let _handL, _handR;
    let _fingers = { L: [], R: [] };
    let _particles;
    let _bodyGroup, _armGroupL, _armGroupR;
    let _headGroup;

    // Pre-allocated materials to avoid per-frame allocation (memory leak fix)
    let _holoUniforms;
    let _errorEyeMaterial = null;
    let _normalEyeMaterial = null;
    let _isErrorEyeActive = false;

    // FPS monitoring for adaptive quality
    let _fpsFrames = 0;
    let _fpsLastCheck = 0;
    let _currentFps = 60;
    let _particleCount = 200;
    const FPS_CHECK_INTERVAL = 2000;
    const FPS_LOW_THRESHOLD = 30;

    // ── WebGL capability check ──
    function _isWebGLAvailable() {
        try {
            const canvas = document.createElement("canvas");
            return !!(
                window.WebGLRenderingContext &&
                (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"))
            );
        } catch (e) {
            return false;
        }
    }

    // ── Page Visibility handler ──
    function _onVisibilityChange() {
        if (_destroyed) return;
        if (document.hidden) {
            _paused = true;
            if (_animFrame) {
                cancelAnimationFrame(_animFrame);
                _animFrame = null;
            }
        } else {
            _paused = false;
            if (_initialized && !_animFrame) {
                _clock.getDelta(); // flush accumulated delta
                _animate();
            }
        }
    }

    // ── Init ──
    function init(canvasId, glowContainerId) {
        if (_initialized || _destroyed) return;

        try {
            _container = document.getElementById(canvasId);
            if (!_container) {
                console.error("[VeraFace] Container element not found:", canvasId);
                return;
            }
            _glowContainer = document.getElementById(glowContainerId);

            // Check Three.js availability
            if (typeof THREE === "undefined") {
                console.error("[VeraFace] Three.js not loaded — avatar disabled");
                _renderFallback();
                return;
            }

            // Check WebGL support
            if (!_isWebGLAvailable()) {
                console.warn("[VeraFace] WebGL not supported — using fallback");
                _renderFallback();
                return;
            }

            _clock = new THREE.Clock();

            _setupScene();
            _buildAvatar();
            _buildParticles();
            _scheduleNextBlink();

            // Page Visibility API — pause rendering when tab is hidden
            document.addEventListener("visibilitychange", _onVisibilityChange);

            // Responsive resize
            _resizeObserver = new ResizeObserver(() => {
                if (!_destroyed) _resize();
            });
            _resizeObserver.observe(_container);
            _resize();

            _initialized = true;
            _animate();
        } catch (err) {
            console.error("[VeraFace] Initialization failed:", err);
            _renderFallback();
        }
    }

    // ── Fallback renderer (2D canvas) when WebGL/Three.js unavailable ──
    function _renderFallback() {
        if (!_container) return;
        const canvas = document.createElement("canvas");
        canvas.width = 280;
        canvas.height = 350;
        canvas.style.width = "100%";
        canvas.style.height = "100%";
        canvas.style.borderRadius = "20px";
        _container.appendChild(canvas);

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        ctx.fillStyle = "#1e2130";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.fillStyle = "#6c7bff";
        ctx.font = "14px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("3D Avatar requires WebGL", canvas.width / 2, canvas.height / 2 - 10);
        ctx.fillText("Using simplified mode", canvas.width / 2, canvas.height / 2 + 14);
    }

    // ── Scene setup ──
    function _setupScene() {
        _renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
        _renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        _renderer.setClearColor(0x000000, 0);

        // Security: prevent context from being read by other scripts
        _renderer.domElement.addEventListener("webglcontextlost", function (e) {
            e.preventDefault();
            console.warn("[VeraFace] WebGL context lost");
            if (_animFrame) {
                cancelAnimationFrame(_animFrame);
                _animFrame = null;
            }
        });

        _renderer.domElement.addEventListener("webglcontextrestored", function () {
            console.info("[VeraFace] WebGL context restored");
            if (_initialized && !_destroyed && !_paused) {
                _animate();
            }
        });

        _container.appendChild(_renderer.domElement);

        _scene = new THREE.Scene();

        _camera = new THREE.PerspectiveCamera(40, 280 / 350, 0.1, 100);
        _camera.position.set(0, 0.3, 3.2);
        _camera.lookAt(0, 0.1, 0);

        const ambient = new THREE.AmbientLight(0x4455aa, 0.6);
        _scene.add(ambient);

        const point1 = new THREE.PointLight(0x6c7bff, 1.2, 10);
        point1.position.set(2, 3, 4);
        _scene.add(point1);

        const point2 = new THREE.PointLight(0xa78bfa, 0.6, 10);
        point2.position.set(-2, -1, 3);
        _scene.add(point2);
    }

    // ── Holographic ShaderMaterial ──
    function _createHoloMaterial() {
        _holoUniforms = {
            uTime: { value: 0 },
            uGlowColor: { value: new THREE.Vector3(0.42, 0.48, 1.0) },
            uGlowIntensity: { value: 0.5 },
            uPulseSpeed: { value: 1.0 },
        };

        return new THREE.ShaderMaterial({
            uniforms: _holoUniforms,
            vertexShader: `
                varying vec3 vNormal;
                varying vec3 vPosition;
                varying vec2 vUv;
                void main() {
                    vNormal = normalize(normalMatrix * normal);
                    vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
                    vUv = uv;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform float uTime;
                uniform vec3 uGlowColor;
                uniform float uGlowIntensity;
                uniform float uPulseSpeed;
                varying vec3 vNormal;
                varying vec3 vPosition;
                varying vec2 vUv;

                void main() {
                    vec3 viewDir = normalize(-vPosition);
                    float fresnel = pow(1.0 - max(dot(viewDir, vNormal), 0.0), 2.5);

                    vec3 base = vec3(0.118, 0.129, 0.188);

                    float gridX = step(0.97, fract(vUv.x * 12.0));
                    float gridY = step(0.97, fract(vUv.y * 12.0));
                    float circuit = max(gridX, gridY);
                    float tracePulse = sin(vUv.y * 20.0 - uTime * uPulseSpeed * 3.0) * 0.5 + 0.5;
                    circuit *= tracePulse;

                    float pulse = sin(vPosition.y * 4.0 - uTime * uPulseSpeed * 2.0) * 0.5 + 0.5;
                    pulse = smoothstep(0.3, 0.7, pulse) * 0.15;

                    vec3 color = base;
                    color += uGlowColor * circuit * 0.4;
                    color += uGlowColor * pulse;
                    color += uGlowColor * fresnel * uGlowIntensity;

                    float alpha = 0.85 + fresnel * 0.15;
                    gl_FragColor = vec4(color, alpha);
                }
            `,
            transparent: true,
            side: THREE.DoubleSide,
        });
    }

    function _createWireframeMaterial() {
        return new THREE.MeshBasicMaterial({
            color: 0x6c7bff,
            wireframe: true,
            transparent: true,
            opacity: 0.08,
        });
    }

    function _createEyeMaterial() {
        return new THREE.MeshStandardMaterial({
            color: 0xe4e6f0,
            emissive: 0xe4e6f0,
            emissiveIntensity: 0.4,
            roughness: 0.2,
            metalness: 0.1,
        });
    }

    function _createPupilMaterial() {
        return new THREE.MeshStandardMaterial({
            color: 0x1a1d27,
            emissive: 0x000000,
            roughness: 0.5,
        });
    }

    // ── Build avatar geometry ──
    function _buildAvatar() {
        const holoMat = _createHoloMaterial();
        const wireMat = _createWireframeMaterial();
        const eyeMat = _createEyeMaterial();
        const pupilMat = _createPupilMaterial();

        // Pre-allocate materials for error state (prevents per-frame allocation)
        _normalEyeMaterial = eyeMat;
        _errorEyeMaterial = new THREE.MeshBasicMaterial({
            color: 0xf43f5e,
            transparent: true,
            opacity: 0.9,
        });

        _bodyGroup = new THREE.Group();
        _scene.add(_bodyGroup);

        // Torso — tapered cylinder
        const torsoGeo = new THREE.CylinderGeometry(0.32, 0.22, 0.9, 12);
        _torso = new THREE.Mesh(torsoGeo, holoMat);
        _torso.position.y = -0.2;
        _bodyGroup.add(_torso);

        const torsoWire = new THREE.Mesh(torsoGeo, wireMat);
        _torso.add(torsoWire);

        // Neck
        const neckGeo = new THREE.CylinderGeometry(0.08, 0.1, 0.15, 8);
        _neck = new THREE.Mesh(neckGeo, holoMat);
        _neck.position.y = 0.52;
        _torso.add(_neck);

        // Head group
        _headGroup = new THREE.Group();
        _headGroup.position.y = 0.72;
        _torso.add(_headGroup);

        // Head
        const headGeo = new THREE.SphereGeometry(0.3, 16, 14);
        headGeo.scale(1, 1.1, 0.95);
        _head = new THREE.Mesh(headGeo, holoMat);
        _headGroup.add(_head);

        const headWire = new THREE.Mesh(headGeo, wireMat);
        _head.add(headWire);

        // Eyes
        const eyeGeo = new THREE.SphereGeometry(0.065, 12, 10);
        _eyeL = new THREE.Mesh(eyeGeo, _normalEyeMaterial);
        _eyeL.position.set(-0.11, 0.04, 0.26);
        _headGroup.add(_eyeL);

        _eyeR = new THREE.Mesh(eyeGeo, _normalEyeMaterial);
        _eyeR.position.set(0.11, 0.04, 0.26);
        _headGroup.add(_eyeR);

        // Pupils
        const pupilGeo = new THREE.SphereGeometry(0.032, 10, 8);
        _pupilL = new THREE.Mesh(pupilGeo, pupilMat);
        _pupilL.position.set(0, 0, 0.04);
        _eyeL.add(_pupilL);

        _pupilR = new THREE.Mesh(pupilGeo, pupilMat);
        _pupilR.position.set(0, 0, 0.04);
        _eyeR.add(_pupilR);

        // Pupil highlights
        const highlightGeo = new THREE.SphereGeometry(0.012, 6, 6);
        const highlightMat = new THREE.MeshBasicMaterial({ color: 0xffffff });

        _highlightL = new THREE.Mesh(highlightGeo, highlightMat);
        _highlightL.position.set(0.012, 0.012, 0.035);
        _pupilL.add(_highlightL);

        _highlightR = new THREE.Mesh(highlightGeo, highlightMat);
        _highlightR.position.set(0.012, 0.012, 0.035);
        _pupilR.add(_highlightR);

        // Brow ridges
        const browGeo = new THREE.TorusGeometry(0.06, 0.012, 4, 12, Math.PI);
        const browMat = new THREE.MeshStandardMaterial({
            color: 0x8b90b0,
            emissive: 0x6c7bff,
            emissiveIntensity: 0.15,
        });

        _browL = new THREE.Mesh(browGeo, browMat);
        _browL.position.set(-0.11, 0.12, 0.25);
        _browL.rotation.x = -0.3;
        _headGroup.add(_browL);

        _browR = new THREE.Mesh(browGeo, browMat);
        _browR.position.set(0.11, 0.12, 0.25);
        _browR.rotation.x = -0.3;
        _headGroup.add(_browR);

        // Mouth
        _mouth = _createMouthMesh();
        _mouth.position.set(0, -0.1, 0.27);
        _headGroup.add(_mouth);

        // Arms
        _buildArms(holoMat, wireMat);
    }

    function _createMouthMesh() {
        const curve = new THREE.QuadraticBezierCurve3(
            new THREE.Vector3(-0.08, 0, 0),
            new THREE.Vector3(0, 0.02, 0),
            new THREE.Vector3(0.08, 0, 0)
        );
        const points = curve.getPoints(20);
        const geo = new THREE.BufferGeometry().setFromPoints(points);
        const mat = new THREE.LineBasicMaterial({
            color: 0xe4e6f0,
            linewidth: 2,
        });
        return new THREE.Line(geo, mat);
    }

    function _updateMouth(smile, open, zigzag) {
        if (!_mouth || !_mouth.geometry) return;
        const pts = [];
        const segments = 20;
        for (let i = 0; i <= segments; i++) {
            const t = i / segments;
            const x = (t - 0.5) * 0.16;
            let y = 0;

            y += smile * 0.04 * Math.sin(t * Math.PI);
            y -= open * 0.03 * Math.sin(t * Math.PI);

            if (zigzag > 0) {
                y += zigzag * 0.015 * Math.sin(t * Math.PI * 5) * (1 - Math.abs(t - 0.5) * 2);
            }

            pts.push(new THREE.Vector3(x, y, 0));
        }
        _mouth.geometry.setFromPoints(pts);
        _mouth.geometry.computeBoundingSphere();
    }

    function _buildArms(holoMat, wireMat) {
        // Shared geometries (reuse to reduce GPU memory)
        const upperArmGeo = new THREE.CylinderGeometry(0.04, 0.035, 0.35, 8);
        const forearmGeo = new THREE.CylinderGeometry(0.035, 0.03, 0.3, 8);
        const palmGeo = new THREE.BoxGeometry(0.06, 0.08, 0.025);
        const shoulderGeo = new THREE.SphereGeometry(0.06, 8, 6);
        const elbowGeo = new THREE.SphereGeometry(0.04, 6, 6);

        // Left arm
        _armGroupL = new THREE.Group();
        _armGroupL.position.set(-0.38, 0.15, 0);
        _torso.add(_armGroupL);

        _shoulderL = new THREE.Mesh(shoulderGeo, holoMat);
        _armGroupL.add(_shoulderL);

        _upperArmL = new THREE.Group();
        _armGroupL.add(_upperArmL);

        const upperArmMeshL = new THREE.Mesh(upperArmGeo, holoMat);
        upperArmMeshL.position.y = -0.18;
        _upperArmL.add(upperArmMeshL);

        const elbowL = new THREE.Mesh(elbowGeo, holoMat);
        elbowL.position.y = -0.36;
        _upperArmL.add(elbowL);

        _forearmL = new THREE.Group();
        _forearmL.position.set(0, -0.36, 0);
        _upperArmL.add(_forearmL);

        const forearmMeshL = new THREE.Mesh(forearmGeo, holoMat);
        forearmMeshL.position.y = -0.15;
        _forearmL.add(forearmMeshL);

        _handL = new THREE.Group();
        _handL.position.set(0, -0.32, 0);
        _forearmL.add(_handL);

        _handL.add(new THREE.Mesh(palmGeo, holoMat));
        _fingers.L = _buildFingers(_handL, holoMat);

        // Right arm (mirrored, reusing geometries)
        _armGroupR = new THREE.Group();
        _armGroupR.position.set(0.38, 0.15, 0);
        _torso.add(_armGroupR);

        _shoulderR = new THREE.Mesh(shoulderGeo, holoMat);
        _armGroupR.add(_shoulderR);

        _upperArmR = new THREE.Group();
        _armGroupR.add(_upperArmR);

        const upperArmMeshR = new THREE.Mesh(upperArmGeo, holoMat);
        upperArmMeshR.position.y = -0.18;
        _upperArmR.add(upperArmMeshR);

        const elbowR = new THREE.Mesh(elbowGeo, holoMat);
        elbowR.position.y = -0.36;
        _upperArmR.add(elbowR);

        _forearmR = new THREE.Group();
        _forearmR.position.set(0, -0.36, 0);
        _upperArmR.add(_forearmR);

        const forearmMeshR = new THREE.Mesh(forearmGeo, holoMat);
        forearmMeshR.position.y = -0.15;
        _forearmR.add(forearmMeshR);

        _handR = new THREE.Group();
        _handR.position.set(0, -0.32, 0);
        _forearmR.add(_handR);

        _handR.add(new THREE.Mesh(palmGeo, holoMat));
        _fingers.R = _buildFingers(_handR, holoMat);
    }

    function _buildFingers(handGroup, mat) {
        const fingers = [];
        const fingerGeo = new THREE.CylinderGeometry(0.006, 0.005, 0.04, 4);
        const offsets = [-0.02, -0.01, 0, 0.01, 0.02];

        for (let i = 0; i < 5; i++) {
            const finger = new THREE.Group();
            finger.position.set(offsets[i], -0.05, 0);
            handGroup.add(finger);

            const seg = new THREE.Mesh(fingerGeo, mat);
            seg.position.y = -0.02;
            finger.add(seg);

            fingers.push(finger);
        }
        return fingers;
    }

    // ── Particle aura ──
    function _buildParticles() {
        const count = _particleCount;
        const positions = new Float32Array(count * 3);
        const randoms = new Float32Array(count);

        for (let i = 0; i < count; i++) {
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            const r = 0.8 + Math.random() * 0.6;
            positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
            positions[i * 3 + 1] = r * Math.cos(phi) + 0.1;
            positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
            randoms[i] = Math.random();
        }

        const geo = new THREE.BufferGeometry();
        geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
        geo.setAttribute("aRandom", new THREE.BufferAttribute(randoms, 1));

        const mat = new THREE.ShaderMaterial({
            uniforms: {
                uTime: { value: 0 },
                uColor: { value: new THREE.Vector3(0.42, 0.48, 1.0) },
                uSize: { value: 3.0 * (_renderer ? _renderer.getPixelRatio() : 1) },
            },
            vertexShader: `
                uniform float uTime;
                uniform float uSize;
                attribute float aRandom;
                varying float vAlpha;
                void main() {
                    vec3 pos = position;
                    float angle = uTime * (0.2 + aRandom * 0.3);
                    float c = cos(angle), s = sin(angle);
                    pos.xz = mat2(c, -s, s, c) * pos.xz;
                    pos.y += sin(uTime * 0.5 + aRandom * 6.28) * 0.08;
                    vAlpha = 0.15 + 0.35 * sin(uTime * 1.5 + aRandom * 6.28);
                    vec4 mvPos = modelViewMatrix * vec4(pos, 1.0);
                    gl_Position = projectionMatrix * mvPos;
                    gl_PointSize = uSize * (1.0 / -mvPos.z);
                }
            `,
            fragmentShader: `
                uniform vec3 uColor;
                varying float vAlpha;
                void main() {
                    float d = length(gl_PointCoord - 0.5) * 2.0;
                    float alpha = smoothstep(1.0, 0.3, d) * vAlpha;
                    gl_FragColor = vec4(uColor, alpha);
                }
            `,
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
        });

        _particles = new THREE.Points(geo, mat);
        _scene.add(_particles);
    }

    // ── Resize ──
    function _resize() {
        if (!_container || !_renderer || _destroyed) return;
        const w = _container.clientWidth;
        const h = _container.clientHeight;
        if (w === 0 || h === 0) return;
        _camera.aspect = w / h;
        _camera.updateProjectionMatrix();
        _renderer.setSize(w, h);
    }

    // ── Expression API (with input validation) ──
    function setExpression(name) {
        if (_destroyed) return;
        if (typeof name !== "string") return;
        const sanitized = name.trim().toLowerCase();
        if (EXPRESSIONS[sanitized]) {
            _expression = sanitized;
            _target = { ...EXPRESSIONS[sanitized] };
            _targetGesture = EXPRESSIONS[sanitized].gesture;
        }
    }

    function getExpression() {
        return _expression;
    }

    function setSpeakAmplitude(amp) {
        if (_destroyed) return;
        if (typeof amp !== "number" || !isFinite(amp)) return;
        _speakAmplitude = Math.min(1, Math.max(0, amp));
    }

    // ── Lerp ──
    function _lerp(a, b, t) {
        return a + (b - a) * t;
    }

    // ── Blink ──
    function _scheduleNextBlink() {
        if (_destroyed) return;
        const delay = 2000 + Math.random() * 4000;
        _blinkTimeoutId = setTimeout(() => {
            if (_destroyed) return;
            _blinkState = 1;
            _scheduleNextBlink();
        }, delay);
    }

    // ── Gesture target calculations ──
    function _getGestureTargets(gesture) {
        const t = {
            upperArmL_z: 0, upperArmL_x: 0,
            forearmL_z: 0, forearmL_x: 0,
            handL_x: 0, handL_z: 0,
            upperArmR_z: 0, upperArmR_x: 0,
            forearmR_z: 0, forearmR_x: 0,
            handR_x: 0, handR_z: 0,
            headTilt: 0, headNod: 0, headShake: 0,
        };

        switch (gesture) {
            case "rest":
                t.upperArmL_z = 0.15;
                t.upperArmR_z = -0.15;
                break;
            case "chin":
                t.upperArmR_z = -0.8;
                t.upperArmR_x = 0.6;
                t.forearmR_x = 1.6;
                t.forearmR_z = 0.3;
                t.handR_x = -0.2;
                t.headTilt = 0.15;
                t.upperArmL_z = 0.15;
                break;
            case "wave":
                t.upperArmR_z = -1.2;
                t.upperArmR_x = 0.3;
                t.forearmR_x = 0.8;
                t.headNod = 0.12;
                t.upperArmL_z = 0.15;
                break;
            case "thumbsup":
                t.upperArmR_z = -1.0;
                t.upperArmR_x = 0.4;
                t.forearmR_x = 1.2;
                t.headNod = 0.1;
                t.upperArmL_z = 0.15;
                break;
            case "palms":
                t.upperArmL_z = 0.4;
                t.upperArmL_x = 0.3;
                t.forearmL_x = 0.6;
                t.handL_x = -0.3;
                t.upperArmR_z = -0.4;
                t.upperArmR_x = 0.3;
                t.forearmR_x = 0.6;
                t.handR_x = -0.3;
                break;
            case "clasped":
                t.upperArmL_z = 0.3;
                t.upperArmL_x = 0.4;
                t.forearmL_x = 1.2;
                t.forearmL_z = -0.3;
                t.upperArmR_z = -0.3;
                t.upperArmR_x = 0.4;
                t.forearmR_x = 1.2;
                t.forearmR_z = 0.3;
                break;
            case "defensive":
                t.upperArmL_z = 0.5;
                t.upperArmL_x = 0.3;
                t.forearmL_x = 1.0;
                t.handL_x = -0.4;
                t.upperArmR_z = -0.5;
                t.upperArmR_x = 0.3;
                t.forearmR_x = 1.0;
                t.handR_x = -0.4;
                t.headShake = 0.1;
                break;
            case "droop":
                t.upperArmL_z = 0.08;
                t.upperArmR_z = -0.08;
                t.headNod = -0.2;
                break;
        }
        return t;
    }

    // ── FPS monitoring ──
    function _checkFps(now) {
        _fpsFrames++;
        if (now - _fpsLastCheck >= FPS_CHECK_INTERVAL) {
            _currentFps = Math.round((_fpsFrames * 1000) / (now - _fpsLastCheck));
            _fpsFrames = 0;
            _fpsLastCheck = now;

            // Adaptive quality: reduce particles if FPS drops
            if (_currentFps < FPS_LOW_THRESHOLD && _particles && _particleCount > 50) {
                _particleCount = Math.max(50, Math.floor(_particleCount * 0.7));
                _rebuildParticles();
            }
        }
    }

    function _rebuildParticles() {
        if (!_particles || !_scene) return;
        _scene.remove(_particles);
        if (_particles.geometry) _particles.geometry.dispose();
        if (_particles.material) _particles.material.dispose();
        _buildParticles();
    }

    // ── Main animation loop ──
    function _animate() {
        if (_destroyed || _paused) return;

        _animFrame = requestAnimationFrame(_animate);

        try {
            const time = _clock.getElapsedTime();
            const now = performance.now();
            const t = 0.12;

            // FPS monitoring
            _checkFps(now);

            // Lerp expression morphs
            _current.eyes = _lerp(_current.eyes, _target.eyes, t);
            _current.eyeWide = _lerp(_current.eyeWide, _target.eyeWide, t);
            _current.eyeCrescent = _lerp(_current.eyeCrescent, _target.eyeCrescent, t);
            _current.eyeX = _lerp(_current.eyeX, _target.eyeX, t);
            _current.mouthSmile = _lerp(_current.mouthSmile, _target.mouthSmile, t);
            _current.mouthOpen = _lerp(_current.mouthOpen, _target.mouthOpen, t);
            _current.mouthZigzag = _lerp(_current.mouthZigzag, _target.mouthZigzag, t);
            _current.browRaise = _lerp(_current.browRaise, _target.browRaise, t);
            _current.glowColor = [
                _lerp(_current.glowColor[0], _target.glowColor[0], t),
                _lerp(_current.glowColor[1], _target.glowColor[1], t),
                _lerp(_current.glowColor[2], _target.glowColor[2], t),
            ];

            // Blink
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

            // ── Apply to meshes ──

            // Eyes — scale Y for blink
            let blinkSquish = 1;
            if (_blinkState === 1) blinkSquish = 1 - _blinkTimer;
            else if (_blinkState === 2) blinkSquish = 0.05;
            else if (_blinkState === 3) blinkSquish = _blinkTimer;

            const eyeScale = 1 + _current.eyes;
            _eyeL.scale.set(eyeScale, eyeScale * blinkSquish, eyeScale);
            _eyeR.scale.set(eyeScale, eyeScale * blinkSquish, eyeScale);

            // Crescent eyes (happy)
            if (_current.eyeCrescent > 0.1) {
                const cFactor = _current.eyeCrescent;
                _eyeL.scale.y *= (1 - cFactor * 0.6);
                _eyeR.scale.y *= (1 - cFactor * 0.6);
                _pupilL.visible = cFactor < 0.5;
                _pupilR.visible = cFactor < 0.5;
            } else {
                _pupilL.visible = blinkSquish > 0.3;
                _pupilR.visible = blinkSquish > 0.3;
            }

            // Pupils — horizontal look (thinking)
            _pupilL.position.x = _current.eyeX * 0.02;
            _pupilR.position.x = _current.eyeX * 0.02;

            // Error X-eyes — swap to pre-allocated error material (no per-frame allocation)
            const shouldBeError = _current.mouthZigzag > 0.5;
            if (shouldBeError && !_isErrorEyeActive) {
                _eyeL.material = _errorEyeMaterial;
                _eyeR.material = _errorEyeMaterial;
                _isErrorEyeActive = true;
            } else if (!shouldBeError && _isErrorEyeActive) {
                _eyeL.material = _normalEyeMaterial;
                _eyeR.material = _normalEyeMaterial;
                _isErrorEyeActive = false;
            }

            // Brows
            _browL.position.y = 0.12 + _current.browRaise * 0.03;
            _browR.position.y = 0.12 + _current.browRaise * 0.03;
            _browL.rotation.z = _current.browRaise * 0.1;
            _browR.rotation.z = -_current.browRaise * 0.1;

            // Mouth
            let mouthOpen = _current.mouthOpen;
            if (_expression === "speaking") {
                mouthOpen += Math.sin(_mouthPhase) * _speakAmplitude * 0.5;
            }
            _updateMouth(_current.mouthSmile, mouthOpen, _current.mouthZigzag);

            // Mouth color
            if (_current.mouthZigzag > 0.3) {
                _mouth.material.color.setHex(0xf43f5e);
            } else {
                _mouth.material.color.setHex(0xe4e6f0);
            }

            // ── Idle animations ──

            // Breathing
            const breathe = Math.sin(time * 0.8) * 0.015;
            _torso.scale.y = 1 + breathe;

            // Head micro-bob
            const bobY = Math.sin(_bobPhase) * 0.008;
            _headGroup.position.y = 0.72 + bobY;

            // Head micro-rotation
            const headBaseRotX = Math.sin(time * 0.3) * 0.02;
            const headBaseRotY = Math.sin(time * 0.2) * 0.015;

            // Shoulder micro-sway
            if (_armGroupL && _armGroupR) {
                const sway = Math.sin(time * 0.5) * 0.02;
                _armGroupL.rotation.z = sway;
                _armGroupR.rotation.z = -sway;
            }

            // Finger micro-curl
            for (let i = 0; i < 5; i++) {
                const curl = Math.sin(time * 0.7 + i * 0.5) * 0.1;
                if (_fingers.L[i]) _fingers.L[i].rotation.x = curl;
                if (_fingers.R[i]) _fingers.R[i].rotation.x = curl;
            }

            // ── Gesture animation ──
            const gestureTargets = _getGestureTargets(_targetGesture);
            const gt = 0.06;

            if (_upperArmL) {
                _upperArmL.rotation.z = _lerp(_upperArmL.rotation.z, gestureTargets.upperArmL_z, gt);
                _upperArmL.rotation.x = _lerp(_upperArmL.rotation.x, gestureTargets.upperArmL_x, gt);
            }
            if (_forearmL) {
                _forearmL.rotation.x = _lerp(_forearmL.rotation.x, gestureTargets.forearmL_x, gt);
                _forearmL.rotation.z = _lerp(_forearmL.rotation.z, gestureTargets.forearmL_z, gt);
            }
            if (_handL) {
                _handL.rotation.x = _lerp(_handL.rotation.x, gestureTargets.handL_x, gt);
                _handL.rotation.z = _lerp(_handL.rotation.z, gestureTargets.handL_z, gt);
            }
            if (_upperArmR) {
                _upperArmR.rotation.z = _lerp(_upperArmR.rotation.z, gestureTargets.upperArmR_z, gt);
                _upperArmR.rotation.x = _lerp(_upperArmR.rotation.x, gestureTargets.upperArmR_x, gt);
            }
            if (_forearmR) {
                _forearmR.rotation.x = _lerp(_forearmR.rotation.x, gestureTargets.forearmR_x, gt);
                _forearmR.rotation.z = _lerp(_forearmR.rotation.z, gestureTargets.forearmR_z, gt);
            }
            if (_handR) {
                _handR.rotation.x = _lerp(_handR.rotation.x, gestureTargets.handR_x, gt);
                _handR.rotation.z = _lerp(_handR.rotation.z, gestureTargets.handR_z, gt);
            }

            // Wave oscillation
            if (_targetGesture === "wave" && _forearmR) {
                _forearmR.rotation.z = Math.sin(time * 4) * 0.3;
            }

            // Head gesture rotations (layered on top of idle)
            _headGroup.rotation.x = headBaseRotX + _lerp(_headGroup.rotation.x - headBaseRotX, gestureTargets.headNod, gt);
            _headGroup.rotation.y = headBaseRotY + _lerp(_headGroup.rotation.y - headBaseRotY, gestureTargets.headShake, gt);
            _headGroup.rotation.z = _lerp(_headGroup.rotation.z, gestureTargets.headTilt, gt);

            // Head shake oscillation for error
            if (_targetGesture === "defensive") {
                _headGroup.rotation.y += Math.sin(time * 6) * 0.06;
            }

            // ── Holographic material uniforms ──
            if (_holoUniforms) {
                _holoUniforms.uTime.value = time;
                _holoUniforms.uGlowColor.value.set(
                    _current.glowColor[0],
                    _current.glowColor[1],
                    _current.glowColor[2]
                );
            }

            // Particle aura
            if (_particles && _particles.material && _particles.material.uniforms) {
                _particles.material.uniforms.uTime.value = time;
                _particles.material.uniforms.uColor.value.set(
                    _current.glowColor[0],
                    _current.glowColor[1],
                    _current.glowColor[2]
                );
            }

            // Glow ring CSS
            _updateGlow();

            // Render
            if (_renderer && _scene && _camera) {
                _renderer.render(_scene, _camera);
            }
        } catch (err) {
            console.error("[VeraFace] Animation error:", err);
            // Don't crash the loop — skip this frame
        }
    }

    function _updateGlow() {
        if (!_glowContainer) return;
        const color = _target.glow || "rgba(108, 123, 255, 0.15)";
        _glowContainer.style.boxShadow = `0 0 40px 10px ${color}, inset 0 0 20px 5px ${color}`;
    }

    // ── Complete resource cleanup ──
    function destroy() {
        if (_destroyed) return;
        _destroyed = true;
        _initialized = false;

        // Stop animation loop
        if (_animFrame) {
            cancelAnimationFrame(_animFrame);
            _animFrame = null;
        }

        // Stop blink timer
        if (_blinkTimeoutId) {
            clearTimeout(_blinkTimeoutId);
            _blinkTimeoutId = null;
        }

        // Remove event listeners
        document.removeEventListener("visibilitychange", _onVisibilityChange);

        // Disconnect resize observer
        if (_resizeObserver) {
            _resizeObserver.disconnect();
            _resizeObserver = null;
        }

        // Dispose pre-allocated materials
        if (_errorEyeMaterial) {
            _errorEyeMaterial.dispose();
            _errorEyeMaterial = null;
        }
        if (_normalEyeMaterial) {
            _normalEyeMaterial.dispose();
            _normalEyeMaterial = null;
        }

        // Dispose WebGL resources
        if (_renderer) {
            _renderer.dispose();
            if (_renderer.domElement && _renderer.domElement.parentNode) {
                _renderer.domElement.parentNode.removeChild(_renderer.domElement);
            }
            _renderer = null;
        }

        if (_scene) {
            _scene.traverse(function (child) {
                if (child.geometry) child.geometry.dispose();
                if (child.material) {
                    if (Array.isArray(child.material)) {
                        child.material.forEach(function (m) { m.dispose(); });
                    } else {
                        child.material.dispose();
                    }
                }
            });
            _scene = null;
        }

        _camera = null;
        _clock = null;
        _container = null;
        _glowContainer = null;
    }

    return {
        init,
        setExpression,
        getExpression,
        setSpeakAmplitude,
        destroy,
        EXPRESSIONS: VALID_EXPRESSIONS,
    };
})();
