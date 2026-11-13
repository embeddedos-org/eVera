# Hub voice-split scoping (H6)

Status: scoping only, 2026-11-13. Docs, no code change. Home repo: eVera,
as owner of the voice surface. Companion: eNet `docs/ehub-pro-spec.md`
§9, which records the same split from the hub side. Refs H6 / eNet #10
(SH3, merged 2026-11-12). Pipeline position: smart-home-iot is
specified, 0/5 components; this slice scopes the voice split, it does
not build any voice path.

## 1. Where the voice surface lives (read from master, 2026-11-13)

Every path below was read from eVera `master` before writing this doc.
The voice service source EXISTS — the earlier "unverified" note is
closed by this slice.

Server / CLI pipeline — `Mic → VAD → (wake word) → STT → Brain → TTS`
(`main.py`, CLI voice loop):

| File | What it does today |
|---|---|
| `vera/perception/vad.py` | Voice activity detection with `webrtcvad`; ring buffer keeps pre-speech audio, trailing-silence timer ends the segment. Falls back to treating all audio as speech if `webrtcvad` is missing. |
| `vera/perception/stt.py` | Local speech-to-text with `faster-whisper` (CTranslate2). Model, device and compute type come from config (defaults: model `small`, device `cpu`, compute `int8`); English only, `beam_size=5`, `vad_filter=True`. |
| `vera/perception/wake_word.py` | Wake-word detection for the phrase `hey vera`: transcribes short VAD segments (0.3–3.0 s) with the same local STT and fuzzy-matches the transcript (covers common Whisper misreadings such as "hey siri"). There is NO dedicated wake-word model — detection is full transcription plus string matching. |
| `vera/perception/session.py` | Session state machine: LISTENING ↔ ACTIVE ↔ PROCESSING. Wake word (when enabled) moves LISTENING → ACTIVE with a chime; 10 s of silence or a goodbye phrase (`goodbye`, `thanks vera`, `that's all`, `never mind`, `stop listening`, `go to sleep`) deactivates. When wake-word mode is off, the session stays permanently ACTIVE (always-on). |
| `vera/action/tts.py` | Text-to-speech, two engines behind a `TTSEngine` protocol: local `pyttsx3` (default, plays on local speakers, no streaming) and `edge-tts` (Microsoft Edge TTS, streaming over WebSocket; a cloud call when selected). |
| `config.py` (`VoiceSettings`, `VERA_VOICE_*`) | Defaults: `wake_word_enabled=False`, `wake_word_phrase="hey vera"`, `wake_word_timeout_s=10`, `stt_model="small"` / `stt_device="cpu"` / `stt_compute_type="int8"`, `tts_engine="pyttsx3"`, `server_enabled=False`, `proactive_tts_enabled=False`. |

Mobile app — push-to-talk, no wake word:

| File | What it does today |
|---|---|
| `mobile/src/services/voice.ts` | Speech-to-text via `@react-native-voice/voice` and text-to-speech via `react-native-tts` (en-US, rate 0.5). Explicit `startListening()` / `stopListening()` / `cancelListening()` after a microphone-permission check; `speak()` strips emoji before TTS. No wake-word path, no always-listening mode. STT/TTS are the phone OS speech services — their cloud behaviour is the OS vendor's, not eVera's. |

What the voice surface does today, in one line: it lets a person talk
to eVera's brain/agents on the machine (or phone) running eVera. Voice
input becomes a transcript for the agent loop; voice output is spoken
agent text. Nothing in the surface addresses a device, a room, or a
Matter cluster.

## 2. What is NOT there

- No Matter, Thread, Zigbee, or Z-Wave code in the voice path. No
  voice-command → device-command mapping of any kind.
- No Alexa endpoint. The only "Alexa" mentions in the repo are
  comparisons, not integrations: `main.py` describes the CLI loop as
  operating "in Siri/Alexa style" when wake-word mode is on, and
  `vera/brain/agents/music_agent.py` claims to "beat Alexa/Siri/Google"
  at music. No Alexa Smart Home Skill, no account linking, no skill
  manifest, no Alexa API call.
- No "Matter" integration either: the four Matter hits in the repo are
  passing mentions in `main.py`, `vera/brain/agents/wellness.py`,
  `docs/doxygen_main_page.md`, and `docs/manifest.json` — not a stack.
- No far-field / multi-microphone handling: single-mic 16 kHz PCM
  throughout (`sample_rate=16000`, 30 ms chunks). The eSpeaker-AI
  datasheet role ("voice front end", eNet spec §1) is not wired to any
  eVera code in this slice.
- Wake-word mode is OFF by default. The out-of-the-box behaviour is
  always-on ACTIVE, not wake-word-gated.

## 3. The split decision (H6 outcome)

Two paths, decided separately. This slice scopes both and builds
neither.

### Path A — Matter-local voice command path (the proposed direction)

Voice commands stay inside the home: wake word → local STT → eVera
brain → a capability-scoped action on a Matter device, with no cloud
endpoint in the path. eVera's local pipeline (VAD → wake word →
faster-whisper STT → session → local pyttsx3 TTS) is the candidate
starting point, because it already runs without a cloud call — but it
is a candidate only:

- The missing piece is the intent → Matter cluster mapping (which
  spoken command drives which cluster command on which device, and
  who owns that mapping — eVera's brain or an eNet hub service).
  That mapping does not exist anywhere in the org today.
- Any command the voice path issues must be capability-scoped per
  eSec Controls 7–9 (voice is an untrusted input channel: a spoken
  command must not carry more authority than the speaker's
  capability). No capability design is attempted in this slice; the
  control reference is recorded so the later design cannot skip it.
- `edge-tts` must be excluded from Path A (it is a Microsoft cloud
  call) unless a later decision explicitly allows it; the local
  default (`pyttsx3`) is the Path A TTS.
- Mobile push-to-talk is a Path A input only if its OS speech
  services can be kept local; that is unverified (see §4).

### Path B — Alexa Smart Home Skill cloud endpoint (NOT proposed here)

An Alexa Skill is a separate, authenticated cloud endpoint that
Amazon operates against: account linking, a skill manifest, an
endpoint the org must host and operate, and a vendor dependency for
every voice command. That is a product and operations commitment,
not a protocol task. **No Alexa endpoint is designed in this slice,
and none is proposed.** If the org ever wants it, it needs its own
proposal, its own owner, and Aswin's call — it does not follow from
Path A.

### The Home Assistant 2026.11 reference (corrected)

Home Assistant 2026.11 shipped 2026-11-04 (first-party release
notes, `home-assistant.io/blog/2026/11/04/release-202611/`), and its
two-way audio shipped IN that release as a **Labs preview** — enable
in Settings > System > Labs. The eNet spec §9 "(Labs)" label is
corrected by the eNet side of this slice to "shipped in 2026.11 as a
Labs preview". Two scope limits, both from the same release notes:

- It is camera/doorbell talk-back (a talk button on a live stream),
  NOT a voice-command path: it lets a person speak to whoever is
  near a camera, it does not turn "turn on the lights" into a Matter
  command.
- It is narrow: Matter cameras and Reolink cameras over RTSP only,
  and it works only over HTTPS (browser microphone access requires a
  secure connection).

So the HA path is evidence that a hub-local voice path can exist
without a cloud endpoint — but it is not, by itself, the Matter-local
voice *command* path. Path A still needs its intent → cluster mapping.

## 4. Still unknown after reading the source

1. Performance on hub-class hardware: `faster-whisper small` on CPU
   with `int8` has no measured latency or accuracy on an
   eHub-Pro-class machine (quad Cortex-A53, 2 GB RAM). Real-time
   wake-word-by-transcription may or may not keep up; no measurement
   exists.
2. Wake-word reliability in a real home: transcribing every short
   segment and fuzzy-matching is cheap but fragile (background TV,
   overlapping speech, accents). No false-accept / false-reject data
   exists, and no comparison with a dedicated wake-word engine
   (e.g. openWakeWord) has been done.
3. Intent → Matter cluster mapping: who owns it, what its shape is,
   and which clusters v1 covers. Undecided, and the largest open
   design question for Path A.
4. `edge-tts` in Path A: excluded by default in this scoping (see
   §3), but no decision record exists; a later slice must confirm
   the exclusion or explicitly allow it.
5. Mobile OS speech cloud behaviour: whether `react-native-voice`
   STT on iOS/Android stays on-device or sends audio to the vendor
   cloud is unverified per platform. Path A cannot claim the mobile
   path is local until that is checked.
6. eSpeaker-AI front end: mic array, far-field behaviour, and how
   its audio reaches eVera are not specified in any source read for
   this slice (datasheet role only, via the eNet spec).
7. Server-mode voice (`server_enabled`, WebSocket audio in/out):
   the setting exists in config but this slice did not trace the
   server voice path; its trust boundary (who may open a voice
   WebSocket) is unexamined.

## 5. What this slice does NOT claim

No voice command path exists; no Matter stack exists; no Alexa
endpoint exists or is proposed; no certification is claimed; no
performance or reliability claim is made for wake-word detection or
STT on hub hardware. The smart-home-iot bundle stays specified,
0/5 components.
