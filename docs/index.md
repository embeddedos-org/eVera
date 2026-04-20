# 📚 eVoca Documentation

Welcome to the eVoca documentation. eVoca is a voice-first multi-agent AI assistant that controls your entire digital life.

---

## Quick Links

| Document | Description |
|----------|-------------|
| [Getting Started](getting_started.md) | Installation, first run, and basic configuration |
| [Architecture](architecture.md) | System architecture, component overview, data flow |
| [Agents](agents.md) | All 10 agents with tools, descriptions, and examples |
| [API Reference](api_reference.md) | REST, WebSocket, and SSE endpoint documentation |
| [Security](security.md) | Safety policies, PII detection, sandboxing |
| [Configuration](configuration.md) | All environment variables with defaults |
| [Development](development.md) | Building from source, testing, contributing |
| [FAQ](faq.md) | Common questions and troubleshooting |
| [Diagrams](diagrams.md) | 7 Mermaid architecture diagrams |
| [Release Notes v0.5.0](release_notes_v0.5.0.md) | What's new in the latest release |

---

## Generated Documentation

### HTML (Doxygen)

```bash
cd docs && doxygen Doxyfile
# Open docs/html/index.html in your browser
```

### PDF (Doxygen + LaTeX)

```bash
cd docs && doxygen Doxyfile
cd latex && make
# Output: docs/latex/refman.pdf
```

### Diagram Images

```bash
npm install -g @mermaid-js/mermaid-cli
python docs/generate_diagrams.py
# Output: docs/images/*.png
```

---

## Project Stats

| Metric | Value |
|--------|-------|
| Agents | 10+ (extensible via plugins) |
| Tools | 90+ |
| API Endpoints | 20+ |
| Test Cases | 200+ |
| Supported Languages | 19 |
| Crew Strategies | 4 (sequential, parallel, hierarchical, debate) |
| Memory Layers | 4 (working, episodic, semantic, secure) |
| LLM Tiers | 4 (regex, local, cloud specialist, cloud strategist) |
| Platforms | Windows, macOS, Linux |

---

*Built with ❤️ by Srikanth Patchava*
