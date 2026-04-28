"""Generate narration audio using Google Text-to-Speech."""
from gtts import gTTS

NARRATION = (
    "Introducing eVera. A formal verification framework for critical systems. Feature one: Model checking engine exhaustively verifies system properties. Feature two: Property-based testing generates thousands of edge cases automatically. Feature three: Proof automation eliminates manual verification effort. eVera. Open source and mathematically rigorous. Visit github dot com slash embeddedos-org slash eVera."
)

tts = gTTS(text=NARRATION, lang="en", slow=False)
tts.save("narration.mp3")
print(f"Generated narration.mp3 ({len(NARRATION)} chars)")
