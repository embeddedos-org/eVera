"""Vera — entry point for CLI voice loop, server, or both."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(name)-25s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("vera")


def _is_electron() -> bool:
    """Detect if running inside Electron wrapper."""
    return os.environ.get("VERA_ELECTRON") == "1" or getattr(sys, "frozen", False)


async def voice_loop() -> None:
    """CLI voice loop: Mic → VAD → STT → Brain → TTS.

    When wake_word_enabled=True, operates in Siri/Alexa style:
      LISTENING → (wake word) → chime + greeting → ACTIVE → (timeout/goodbye) → LISTENING

    When wake_word_enabled=False, behaves as before (always active).
    """
    from config import settings as _settings
    from vera.action.chime import play_activation_chime
    from vera.action.tts import TextToSpeech
    from vera.core import VeraBrain
    from vera.events.bus import EventType
    from vera.perception.audio_stream import AudioStream
    from vera.perception.session import VoiceSession
    from vera.perception.stt import SpeechToText
    from vera.perception.vad import VoiceActivityDetector
    from vera.perception.wake_word import WakeWordDetector

    brain = VeraBrain()
    await brain.start()

    stt = SpeechToText()
    vad = VoiceActivityDetector()
    tts = TextToSpeech(event_bus=brain.event_bus)
    audio = AudioStream()
    session = VoiceSession(event_bus=brain.event_bus)
    wake_detector = WakeWordDetector(stt=stt)

    wake_enabled = _settings.voice.wake_word_enabled
    proactive_tts = _settings.voice.proactive_tts_enabled

    # Proactive TTS bridge — speak scheduler notifications aloud
    if proactive_tts:

        async def _on_proactive_notification(notification: dict) -> None:
            if session.is_active:
                return  # don't interrupt active conversation
            message = notification.get("message", "")
            if message:
                await brain.event_bus.publish(
                    EventType.PROACTIVE_NOTIFICATION,
                    {"message": message},
                )
                print(f"📢 {message}")
                await tts.speak(message)

        brain.scheduler.add_notification_handler(_on_proactive_notification)

    if wake_enabled:
        print("🎙️  Vera listening for wake word... (say 'Hey Vera')")
    else:
        print("🎙️  Vera listening... (Ctrl+C to stop)")

    try:
        await audio.start()
        async for chunk in audio.get_chunks():
            # --- Barge-in: interrupt TTS if user speaks ---
            if tts.is_speaking:
                result = vad.process_chunk(chunk)
                if result.is_speech_end:
                    tts.interrupt()
                continue

            # --- Check session timeout ---
            if session.is_active and session.is_timed_out():
                print("💤 Session timed out — going back to sleep")
                await tts.speak("Going to sleep. Say Hey Vera when you need me!")
                await session.deactivate()
                continue

            result = vad.process_chunk(chunk)
            if not result.is_speech_end:
                continue

            # --- LISTENING state: check for wake word ---
            if not session.is_active:
                if wake_detector.check(result.audio_buffer):
                    await brain.event_bus.publish(EventType.WAKE_WORD_DETECTED)
                    await session.activate()
                    await play_activation_chime()
                    greeting = "Hey! What can I do for you?"
                    print(f"🤖 Vera: {greeting}")
                    await tts.speak(greeting)
                continue

            # --- ACTIVE state: full STT → Brain → TTS pipeline ---
            transcript = stt.transcribe(result.audio_buffer)
            if not transcript.strip():
                continue

            session.touch()
            print(f"\n👤 You: {transcript}")

            # Goodbye detection
            if session.is_goodbye(transcript):
                farewell = "Goodbye! Just say Hey Vera whenever you need me."
                print(f"🤖 Vera: {farewell}")
                await tts.speak(farewell)
                await session.deactivate()
                continue

            response = await brain.process(transcript, voice_mode=True)
            print(f"🤖 Vera [{response.agent}]: {response.response}")
            await tts.speak(response.response)
    except KeyboardInterrupt:
        pass
    finally:
        if proactive_tts:
            brain.scheduler.remove_notification_handler(_on_proactive_notification)
        await audio.stop()
        await brain.stop()


async def text_loop() -> None:
    """Text-only mode: stdin → Brain → stdout (no mic/speaker needed)."""
    from vera.core import VeraBrain

    brain = VeraBrain()
    await brain.start()

    print("⌨️  Vera text mode — type your message (Ctrl+C to quit)")
    print("─" * 50)

    try:
        while True:
            try:
                transcript = input("\n👤 You: ").strip()
            except EOFError:
                break
            if not transcript:
                continue
            if transcript.lower() in ("quit", "exit", "bye"):
                print("👋 Goodbye!")
                break

            response = await brain.process(transcript)
            tier_label = f"T{response.tier}"
            print(f"🤖 Vera [{response.agent}|{tier_label}]: {response.response}")
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    finally:
        await brain.stop()


async def start_server(host: str, port: int) -> None:
    """Start the FastAPI server."""
    import uvicorn

    from vera.app import create_app
    from vera.core import VeraBrain

    brain = VeraBrain()
    app = create_app(brain)

    # Auto-open browser only when NOT running inside Electron or frozen exe
    if not _is_electron():
        import threading
        import webbrowser

        def open_browser():
            import time

            time.sleep(2)
            url = f"http://{'localhost' if host in ('0.0.0.0', '127.0.0.1') else host}:{port}"
            print(f"🌐 Opening {url} in browser...")
            webbrowser.open(url)

        threading.Thread(target=open_browser, daemon=True).start()

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def run_both(host: str, port: int) -> None:
    """Run both voice loop and server concurrently."""
    await asyncio.gather(
        voice_loop(),
        start_server(host, port),
    )


async def run_all(host: str, port: int) -> None:
    """Run ALL input modes: voice + server + text CLI simultaneously."""
    from vera.core import VeraBrain

    brain = VeraBrain()
    await brain.start()

    async def cli_input():
        """Background CLI input loop."""
        print("⌨️  CLI input active — type messages here too")
        loop = asyncio.get_event_loop()
        while True:
            try:
                transcript = await loop.run_in_executor(None, input, "\n👤 CLI: ")
                transcript = transcript.strip()
                if not transcript:
                    continue
                if transcript.lower() in ("quit", "exit"):
                    break
                response = await brain.process(transcript)
                print(f"🤖 Vera [{response.agent}|T{response.tier}]: {response.response}")
            except (EOFError, KeyboardInterrupt):
                break

    await asyncio.gather(
        voice_loop(),
        start_server(host, port),
        cli_input(),
    )


def main() -> None:
    # Ensure data directories exist on startup
    settings.ensure_data_dirs()

    parser = argparse.ArgumentParser(
        description="Vera — Voice-first multi-agent AI assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  text    Text input/output only (no mic/speaker) — great for testing
  cli     Voice mode with mic → VAD → STT → Brain → TTS
  server  FastAPI server with REST + WebSocket + Web UI
  both    Voice loop + server running concurrently
  all     ALL inputs: voice + server + CLI text simultaneously
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["text", "cli", "server", "both", "all"],
        default="text",
        help="Run mode (default: text)",
    )
    parser.add_argument("--host", default=settings.server.host, help="Server host")
    parser.add_argument("--port", type=int, default=settings.server.port, help="Server port")
    parser.add_argument(
        "--unsafe-paths",
        action="store_true",
        help="Allow Coder agent to access blocked paths (dangerous!)",
    )

    args = parser.parse_args()

    # Apply CLI overrides to settings
    if args.unsafe_paths:
        settings.safety.coder_unsafe_paths = True
        logger.warning("⚠️  UNSAFE-PATHS enabled — Coder agent can access blocked paths")

    print(r"""
 __     __
 \ \   / /___   ___  __ _
  \ \ / / _ \ / __|/ _` |
   \ V / (_) | (__| (_| |
    \_/ \___/ \___|\__,_|

  Voice-first AI Assistant v0.6.0
    """)

    max_retries = 10
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            if args.mode == "text":
                asyncio.run(text_loop())
                break
            elif args.mode == "cli":
                asyncio.run(voice_loop())
                break
            elif args.mode == "server":
                asyncio.run(start_server(args.host, args.port))
                break
            elif args.mode == "both":
                asyncio.run(run_both(args.host, args.port))
                break
            elif args.mode == "all":
                asyncio.run(run_all(args.host, args.port))
                break
        except KeyboardInterrupt:
            logger.info("Vera shutting down...")
            sys.exit(0)
        except Exception as e:
            logger.error("Vera crashed (attempt %d/%d): %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                logger.info("Self-recovery: restarting in %d seconds...", retry_delay)
                import time

                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
            else:
                logger.critical("Max retries reached. Vera shutting down.")
                sys.exit(1)


if __name__ == "__main__":
    main()
