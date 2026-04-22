/* === Vera Code Viewer — File Browser + Syntax + AI Analysis === */

var VeraCodeViewer = (function () {
    "use strict";

    var fileTree = [];
    var flatFiles = [];
    var currentIndex = -1;
    var currentFile = null;
    var activityLog = [];

    // Syntax rules per language
    var SYNTAX = {
        python: {
            keywords: /\b(def|class|async|await|import|from|return|if|elif|else|for|while|try|except|finally|raise|with|as|pass|break|continue|yield|lambda|and|or|not|in|is|True|False|None|self)\b/g,
            strings: /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g,
            comments: /(#.*$)/gm,
            numbers: /\b(\d+\.?\d*)\b/g,
            decorators: /(@\w+)/g,
            functions: /\b(\w+)\s*(?=\()/g,
        },
        javascript: {
            keywords: /\b(function|const|let|var|class|return|if|else|for|while|do|switch|case|break|continue|try|catch|finally|throw|new|this|typeof|instanceof|import|export|from|default|async|await|yield|null|undefined|true|false|of|in)\b/g,
            strings: /(`[\s\S]*?`|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g,
            comments: /(\/\/.*$|\/\*[\s\S]*?\*\/)/gm,
            numbers: /\b(\d+\.?\d*)\b/g,
            functions: /\b(\w+)\s*(?=\()/g,
        },
        typescript: null, // will alias to javascript
        java: {
            keywords: /\b(public|private|protected|static|final|class|interface|extends|implements|return|if|else|for|while|do|switch|case|break|continue|try|catch|finally|throw|new|this|import|package|void|int|long|float|double|boolean|String|null|true|false)\b/g,
            strings: /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g,
            comments: /(\/\/.*$|\/\*[\s\S]*?\*\/)/gm,
            numbers: /\b(\d+\.?\d*[fFdDlL]?)\b/g,
            functions: /\b(\w+)\s*(?=\()/g,
        },
        go: {
            keywords: /\b(package|import|func|return|if|else|for|range|switch|case|default|break|continue|go|defer|select|chan|type|struct|interface|map|var|const|nil|true|false)\b/g,
            strings: /(`[\s\S]*?`|"(?:[^"\\]|\\.)*")/g,
            comments: /(\/\/.*$|\/\*[\s\S]*?\*\/)/gm,
            numbers: /\b(\d+\.?\d*)\b/g,
            functions: /\b(\w+)\s*(?=\()/g,
        },
    };
    SYNTAX.typescript = SYNTAX.javascript;
    SYNTAX.jsx = SYNTAX.javascript;
    SYNTAX.tsx = SYNTAX.javascript;

    function init() {
        loadFileTree(".");
        bindEvents();
    }

    function bindEvents() {
        document.getElementById("btnPrev").addEventListener("click", function () {
            navigateFile(-1);
        });
        document.getElementById("btnNext").addEventListener("click", function () {
            navigateFile(1);
        });
        document.getElementById("aiPanelClose").addEventListener("click", closeAiPanel);
        document.getElementById("activityToggle").addEventListener("click", toggleActivity);

        document.addEventListener("keydown", function (e) {
            if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
            if (document.getElementById("graphModal").classList.contains("open")) return;

            switch (e.key) {
                case "ArrowLeft":
                    e.preventDefault();
                    navigateFile(-1);
                    break;
                case "ArrowRight":
                    e.preventDefault();
                    navigateFile(1);
                    break;
                case "s":
                case "S":
                    if (!e.ctrlKey && !e.metaKey) triggerAnalysis("summarize");
                    break;
                case "e":
                case "E":
                    if (!e.ctrlKey && !e.metaKey) triggerAnalysis("explain");
                    break;
                case "f":
                case "F":
                    if (!e.ctrlKey && !e.metaKey) triggerAnalysis("find_issues");
                    break;
            }
        });
    }

    function loadFileTree(path) {
        fetch("/api/code/files?path=" + encodeURIComponent(path))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                fileTree = data.tree;
                flatFiles = [];
                flattenTree(data.tree, data.root);
                renderTree(data.tree, document.getElementById("fileTree"), 0, data.root);
            })
            .catch(function (err) {
                console.error("Failed to load file tree:", err);
            });
    }

    function flattenTree(node, basePath) {
        if (node.type === "file") {
            flatFiles.push(basePath + "/" + node.name);
        } else if (node.children) {
            for (var i = 0; i < node.children.length; i++) {
                var child = node.children[i];
                var childPath = basePath + "/" + child.name;
                if (child.type === "file") {
                    flatFiles.push(childPath);
                } else {
                    flattenTree(child, childPath);
                }
            }
        }
    }

    function renderTree(node, container, depth, basePath) {
        container.innerHTML = "";
        if (!node.children) return;

        for (var i = 0; i < node.children.length; i++) {
            var child = node.children[i];
            var childPath = basePath + "/" + child.name;
            var el = document.createElement("div");
            el.className = "tree-item" + (child.type === "directory" ? " dir" : "");
            el.style.paddingLeft = (12 + depth * 16) + "px";

            var icon = document.createElement("span");
            icon.className = "tree-icon";
            icon.textContent = child.type === "directory" ? "📁" : getFileIcon(child.name);

            var name = document.createElement("span");
            name.textContent = child.name;

            el.appendChild(icon);
            el.appendChild(name);

            if (child.type === "file") {
                (function (p) {
                    el.addEventListener("click", function () {
                        openFile(p);
                    });
                })(childPath);
            }

            container.appendChild(el);

            if (child.type === "directory" && child.children) {
                var subContainer = document.createElement("div");
                renderTree(child, subContainer, depth + 1, childPath);
                container.appendChild(subContainer);
            }
        }
    }

    function getFileIcon(name) {
        var ext = name.split(".").pop().toLowerCase();
        var icons = {
            py: "🐍", js: "🟨", ts: "🔷", jsx: "⚛️", tsx: "⚛️",
            html: "🌐", css: "🎨", json: "📋", md: "📝", yaml: "⚙️",
            yml: "⚙️", toml: "⚙️", sh: "🖥️", go: "🔵", rs: "🦀",
            java: "☕", rb: "💎", c: "🔧", cpp: "🔧", h: "🔧",
        };
        return icons[ext] || "📄";
    }

    function openFile(path) {
        fetch("/api/code/file?path=" + encodeURIComponent(path))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                currentFile = data;
                currentIndex = flatFiles.indexOf(path);
                if (currentIndex < 0) {
                    for (var i = 0; i < flatFiles.length; i++) {
                        if (flatFiles[i].endsWith(data.name)) {
                            currentIndex = i;
                            break;
                        }
                    }
                }

                document.getElementById("currentFile").textContent = data.name;

                var badge = document.getElementById("complexityBadge");
                badge.style.display = "inline";
                badge.textContent = data.complexity;
                badge.className = "complexity-badge complexity-" + data.complexity;

                renderCode(data);

                // Highlight active sidebar item
                var items = document.querySelectorAll(".tree-item");
                for (var j = 0; j < items.length; j++) {
                    items[j].classList.remove("active");
                }
                // Find and activate the matching item
                items.forEach(function (item) {
                    if (item.textContent.trim() === data.name) {
                        item.classList.add("active");
                    }
                });
            })
            .catch(function (err) {
                console.error("Failed to open file:", err);
            });
    }

    function navigateFile(direction) {
        if (flatFiles.length === 0) return;
        var next = currentIndex + direction;
        if (next < 0) next = flatFiles.length - 1;
        if (next >= flatFiles.length) next = 0;
        openFile(flatFiles[next]);
        addActivity(direction > 0 ? "swipe_right" : "swipe_left", flatFiles[next]);
    }

    function renderCode(fileData) {
        var container = document.getElementById("codeContainer");
        var lines = fileData.content.split("\n");
        var lang = fileData.language;
        var html = "";

        for (var i = 0; i < lines.length; i++) {
            var lineNum = i + 1;
            var highlighted = highlightLine(lines[i], lang);
            html += '<div class="code-line" data-line="' + lineNum + '">' +
                '<span class="line-number">' + lineNum + '</span>' +
                '<span class="line-content">' + highlighted + '</span>' +
                '</div>';
        }

        container.innerHTML = html;
    }

    function highlightLine(text, lang) {
        var escaped = escapeHtml(text);
        var rules = SYNTAX[lang];
        if (!rules) return escaped;

        // Extract strings and comments first, replace with placeholders
        var tokens = [];
        var idx = 0;

        function placeholder(cls, match) {
            var id = "§" + idx + "§";
            tokens.push({ id: id, html: '<span class="' + cls + '">' + escapeHtml(match) + '</span>' });
            idx++;
            return id;
        }

        // Comments
        if (rules.comments) {
            escaped = escaped.replace(rules.comments, function (m) {
                return placeholder("tok-comment", m);
            });
        }

        // Strings
        if (rules.strings) {
            escaped = escaped.replace(rules.strings, function (m) {
                return placeholder("tok-string", m);
            });
        }

        // Decorators
        if (rules.decorators) {
            escaped = escaped.replace(rules.decorators, function (m) {
                return placeholder("tok-decorator", m);
            });
        }

        // Keywords
        if (rules.keywords) {
            escaped = escaped.replace(rules.keywords, function (m) {
                return '<span class="tok-keyword">' + m + '</span>';
            });
        }

        // Numbers
        if (rules.numbers) {
            escaped = escaped.replace(rules.numbers, function (m) {
                if (m.match(/^§\d+§$/)) return m;
                return '<span class="tok-number">' + m + '</span>';
            });
        }

        // Restore placeholders
        for (var i = 0; i < tokens.length; i++) {
            escaped = escaped.replace(tokens[i].id, tokens[i].html);
        }

        return escaped;
    }

    function triggerAnalysis(action) {
        if (!currentFile) return;

        var panel = document.getElementById("aiPanel");
        var body = document.getElementById("aiPanelBody");
        var title = document.getElementById("aiPanelTitle");

        var titles = {
            summarize: "🤏 AI Summary",
            explain: "✋ AI Explanation",
            find_issues: "☝️ Issue Analysis",
        };
        title.textContent = titles[action] || "AI Analysis";

        panel.classList.add("open", "loading");
        body.innerHTML = '<div class="ai-loading"><div class="spinner"></div> Analyzing...</div>';

        addActivity(
            action === "summarize" ? "pinch" : action === "explain" ? "open_palm" : "point",
            currentFile.name
        );

        fetch("/api/code/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                path: currentFile.path,
                content: currentFile.content,
                action: action,
            }),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                panel.classList.remove("loading");
                showAnalysisResult(action, data);
            })
            .catch(function (err) {
                panel.classList.remove("loading");
                body.innerHTML = '<div style="color:var(--error);">Analysis failed: ' + escapeHtml(err.message || String(err)) + '</div>';
            });
    }

    function showAnalysisResult(action, data) {
        var body = document.getElementById("aiPanelBody");
        var html = "";

        if (action === "summarize") {
            html += '<div>' + escapeHtml(data.summary || "") + '</div>';
            if (data.key_concepts && data.key_concepts.length) {
                html += '<div class="concept-tags">';
                for (var i = 0; i < data.key_concepts.length; i++) {
                    html += '<span class="concept-tag">' + escapeHtml(data.key_concepts[i]) + '</span>';
                }
                html += '</div>';
            }
        } else if (action === "explain") {
            if (data.steps) {
                for (var j = 0; j < data.steps.length; j++) {
                    html += '<div class="step-card">' +
                        '<span class="step-number">' + (j + 1) + '.</span>' +
                        escapeHtml(data.steps[j]) +
                        '</div>';
                }
            }
            if (data.key_line && data.key_line.number) {
                highlightCodeLine(data.key_line.number);
                html += '<div style="margin-top:10px;color:var(--accent);font-size:12px;">' +
                    '↑ Key line ' + data.key_line.number + ': ' + escapeHtml(data.key_line.explanation || "") +
                    '</div>';
            }
        } else if (action === "find_issues") {
            if (!data.issues || data.issues.length === 0) {
                html += '<div style="color:var(--success);">✅ No issues found!</div>';
            } else {
                for (var k = 0; k < data.issues.length; k++) {
                    var issue = data.issues[k];
                    html += '<div class="issue-card">' +
                        '<div class="issue-header">' +
                        '<span class="severity-badge severity-' + (issue.severity || "medium") + '">' +
                        escapeHtml(issue.severity || "medium") + '</span>' +
                        '<span class="issue-line-ref">Line ' + (issue.line || "?") + '</span>' +
                        '</div>' +
                        '<div>' + escapeHtml(issue.description || "") + '</div>';
                    if (issue.suggestion) {
                        html += '<div class="issue-suggestion">💡 ' + escapeHtml(issue.suggestion) + '</div>';
                    }
                    html += '</div>';

                    if (issue.line) highlightCodeLine(issue.line);
                }
            }
        }

        // Typewriter reveal
        body.innerHTML = "";
        var wrapper = document.createElement("div");
        wrapper.innerHTML = html;
        body.appendChild(wrapper);
        wrapper.style.opacity = "0";
        wrapper.style.transform = "translateY(8px)";
        wrapper.style.transition = "all 0.3s ease";
        setTimeout(function () {
            wrapper.style.opacity = "1";
            wrapper.style.transform = "translateY(0)";
        }, 50);
    }

    function highlightCodeLine(lineNum) {
        var line = document.querySelector('.code-line[data-line="' + lineNum + '"]');
        if (line) {
            line.classList.add("highlighted");
            line.scrollIntoView({ behavior: "smooth", block: "center" });
            setTimeout(function () { line.classList.remove("highlighted"); }, 5000);
        }
    }

    function closeAiPanel() {
        var panel = document.getElementById("aiPanel");
        panel.classList.remove("open", "loading");
    }

    function addActivity(gesture, file) {
        var icons = {
            swipe_left: "👆",
            swipe_right: "👆",
            pinch: "🤏",
            open_palm: "✋",
            point: "☝️",
        };
        var names = {
            swipe_left: "Swipe Left",
            swipe_right: "Swipe Right",
            pinch: "Summarize",
            open_palm: "Explain",
            point: "Find Issues",
        };

        var entry = {
            icon: icons[gesture] || "❓",
            name: names[gesture] || gesture,
            file: typeof file === "string" ? file.split("/").pop() : "",
            time: new Date().toLocaleTimeString(),
        };

        activityLog.unshift(entry);
        if (activityLog.length > 50) activityLog.pop();

        renderActivity();
    }

    function renderActivity() {
        var list = document.getElementById("activityList");
        var count = document.getElementById("activityCount");
        count.textContent = activityLog.length;

        var html = "";
        var max = Math.min(activityLog.length, 20);
        for (var i = 0; i < max; i++) {
            var entry = activityLog[i];
            html += '<div class="activity-item">' +
                '<span class="activity-icon">' + entry.icon + '</span>' +
                '<span class="activity-name">' + escapeHtml(entry.name) + '</span>' +
                '<span class="activity-file">' + escapeHtml(entry.file) + '</span>' +
                '<span class="activity-time">' + escapeHtml(entry.time) + '</span>' +
                '</div>';
        }
        list.innerHTML = html;
    }

    function toggleActivity() {
        document.getElementById("activityList").classList.toggle("open");
    }

    function escapeHtml(str) {
        var div = document.createElement("div");
        div.textContent = str || "";
        return div.innerHTML;
    }

    return {
        init: init,
        openFile: openFile,
        navigateFile: navigateFile,
        triggerAnalysis: triggerAnalysis,
    };
})();
