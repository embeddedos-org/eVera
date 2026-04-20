# ❓ FAQ & Troubleshooting

## General

### Q: What LLM providers does eVoca support?
**A:** Three providers via litellm:
- **Ollama** (local, free) — requires Ollama installed locally
- **OpenAI** (cloud, paid) — GPT-4o, GPT-4o-mini
- **Google Gemini** (cloud, paid) — Gemini 2.0 Flash

You can configure the fallback order in `.env`. If one provider fails, eVoca automatically tries the next.

### Q: Can eVoca work completely offline?
**A:** Yes! With Ollama running locally, eVoca works without internet. Features that require external APIs (web search, stock prices, browser automation) won't work offline, but conversation, system control, and file management all work.

### Q: What languages does the voice input support?
**A:** 19 languages including English, Spanish, French, German, Chinese, Japanese, Korean, Hindi, Arabic, and more. Language is auto-detected from the input script.

---

## Installation

### Q: The desktop app won't start
**A:** Try these steps:
1. Check that no other instance is running (system tray)
2. Delete the app data folder and restart
3. Check Windows Defender / antivirus isn't blocking the app
4. Run from command line to see error messages

### Q: Python backend won't start
**A:** Common issues:
1. **Wrong Python version** — requires 3.11+. Check with `python --version`
2. **Missing dependencies** — run `pip install -r requirements.txt`
3. **Port in use** — change `VOCA_SERVER_PORT` in `.env`
4. **Missing `.env`** — copy `.env.example` to `.env`

### Q: Ollama connection refused
**A:** Ensure Ollama is running:
```bash
ollama serve              # Start Ollama
ollama pull llama3.2      # Download default model
```
Check `VOCA_LLM_OLLAMA_URL` matches your Ollama server address.

---

## Voice

### Q: Voice input isn't working
**A:** Check:
1. Microphone permissions in your OS settings
2. Browser microphone permission (if using web UI)
3. Listen mode is set to "Always On" or "Push-to-Talk"
4. The correct audio device is selected

### Q: Speech recognition is inaccurate
**A:** Try:
1. Use a larger STT model: `VOCA_VOICE_STT_MODEL=medium`
2. Reduce background noise
3. Speak clearly and at a moderate pace
4. The spell correction system fixes 50+ common voice errors

---

## Agents & Tools

### Q: An agent says "I'm in offline mode"
**A:** This means no LLM provider is available. Either:
1. Start Ollama locally
2. Add an OpenAI or Gemini API key to `.env`
3. The agent will use offline responses (template-based, limited)

### Q: Mouse/keyboard automation isn't working
**A:** Requires `pyautogui` installed:
```bash
pip install pyautogui pygetwindow
```
On Linux, also install `xdotool`: `sudo apt install xdotool`

### Q: Browser automation fails
**A:** Install Playwright browsers:
```bash
pip install playwright
playwright install chromium
```

---

## Security

### Q: How do I enable API authentication?
**A:** Set `VOCA_SERVER_API_KEY=your-secret` in `.env`. All requests must include:
```
Authorization: Bearer your-secret
```

### Q: Is my data sent to the cloud?
**A:** Only when using cloud LLM providers (OpenAI/Gemini). The PrivacyGuard automatically:
- Detects PII (emails, phone numbers, SSNs) and anonymizes before sending
- Forces sensitive requests to local processing (Ollama)
- Never sends encrypted vault contents to any provider

### Q: Can eVoca access all my files?
**A:** No. File operations are sandboxed:
- Allowed: home directory, current working directory
- Blocked: `.ssh`, `.env`, `.aws`, `.gnupg`, system directories

---

## Trading

### Q: Is paper trading real money?
**A:** No. Paper trading uses a virtual $100k portfolio stored in `data/`. No real trades are executed unless you configure Alpaca or IBKR broker credentials.

### Q: How do I connect a real broker?
**A:** Add broker credentials to `.env`:
```env
ALPACA_API_KEY=your-key
ALPACA_SECRET_KEY=your-secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Use paper URL for testing
```
All real trades require explicit user confirmation.

---

## Troubleshooting

### Error: "No module named 'voca'"
Run from the project root directory, or add it to PYTHONPATH:
```bash
cd /path/to/eVoca
python main.py --mode server
```

### Error: "Port 8000 already in use"
Change the port: `VOCA_SERVER_PORT=8001` in `.env`

### Error: "FAISS index not found"
First run creates the index automatically. If corrupted, delete `data/faiss_index` and restart.

### Slow responses
1. Use a smaller Ollama model: `VOCA_LLM_OLLAMA_MODEL=llama3.2:1b`
2. Switch to cloud provider for faster inference
3. Check CPU/RAM usage with `system_info` tool
