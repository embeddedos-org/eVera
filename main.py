"""Voca — entry point for CLI voice loop, server, or both."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(name)-25s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("voca")


async def voice_loop() -> None:
    """CLI voice loop: Mic → VAD → STT → Brain → TTS."""
    from voca.action.tts import TextToSpeech
    from voca.core import VocaBrain
    from voca.perception.audio_stream import AudioStream
    from voca.perception.stt import SpeechToText
    from voca.perception.vad import VoiceActivityDetector

    brain = VocaBrain()
    await brain.start()

    stt = SpeechToText()
    vad = VoiceActivityDetector()
    tts = TextToSpeech(event_bus=brain.event_bus)
    audio = AudioStream()

    print("🎙️  Voca listening... (Ctrl+C to stop)")

    try:
        await audio.start()
        async for chunk in audio.get_chunks():
            result = vad.process_chunk(chunk)
            if result.is_speech_end:
                transcript = stt.transcribe(result.audio_buffer)
                if transcript.strip():
                    print(f"\n👤 You: {transcript}")
                    response = await brain.process(transcript)
                    print(f"🤖 Voca [{response.agent}]: {response.response}")
                    await tts.speak(response.response)
    except KeyboardInterrupt:
        pass
    finally:
        await audio.stop()
        await brain.stop()


async def text_loop() -> None:
    """Text-only mode: stdin → Brain → stdout (no mic/speaker needed)."""
    from voca.core import VocaBrain

    brain = VocaBrain()
    await brain.start()

    print("⌨️  Voca text mode — type your message (Ctrl+C to quit)")
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
            print(f"🤖 Voca [{response.agent}|{tier_label}]: {response.response}")
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    finally:
        await brain.stop()


async def start_server(host: str, port: int) -> None:
    """Start the FastAPI server."""
    import threading
    import webbrowser

    import uvicorn

    from voca.app import create_app
    from voca.core import VocaBrain

    brain = VocaBrain()
    app = create_app(brain)

    # Auto-open browser after server starts
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
    from voca.core import VocaBrain

    brain = VocaBrain()
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
                print(f"🤖 Voca [{response.agent}|T{response.tier}]: {response.response}")
            except (EOFError, KeyboardInterrupt):
                break

    await asyncio.gather(
        voice_loop(),
        start_server(host, port),
        cli_input(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Voca — Voice-first multi-agent AI assistant",
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

    args = parser.parse_args()

    print(r"""
 __     __
 \ \   / /___   ___  __ _
  \ \ / / _ \ / __|/ _` |
   \ V / (_) | (__| (_| |
    \_/ \___/ \___|\__,_|

  Voice-first AI Assistant v0.5.0
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
            logger.info("Voca shutting down...")
            sys.exit(0)
        except Exception as e:
            logger.error("Voca crashed (attempt %d/%d): %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                logger.info("Self-recovery: restarting in %d seconds...", retry_delay)
                import time
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
            else:
                logger.critical("Max retries reached. Voca shutting down.")
                sys.exit(1)


if __name__ == "__main__":
    main()
