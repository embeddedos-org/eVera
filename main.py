"""Voca — entry point for CLI voice loop, server, or both."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
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
    from voca.events.bus import EventBus, EventType
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
    import uvicorn

    from voca.app import create_app
    from voca.core import VocaBrain

    brain = VocaBrain()
    app = create_app(brain)

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def run_both(host: str, port: int) -> None:
    """Run both voice loop and server concurrently."""
    await asyncio.gather(
        voice_loop(),
        start_server(host, port),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Voca — Voice-first multi-agent AI assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  text    Text input/output only (no mic/speaker) — great for testing
  cli     Voice mode with mic → VAD → STT → Brain → TTS
  server  FastAPI server with REST + WebSocket
  both    Voice loop + server running concurrently
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["text", "cli", "server", "both"],
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

  Voice-first AI Assistant v0.1.0
    """)

    try:
        if args.mode == "text":
            asyncio.run(text_loop())
        elif args.mode == "cli":
            asyncio.run(voice_loop())
        elif args.mode == "server":
            asyncio.run(start_server(args.host, args.port))
        elif args.mode == "both":
            asyncio.run(run_both(args.host, args.port))
    except KeyboardInterrupt:
        logger.info("Voca shutting down...")
        sys.exit(0)


if __name__ == "__main__":
    main()
