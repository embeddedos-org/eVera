"""Voca configuration — Pydantic Settings loading from .env.

@file config.py
@brief Central configuration module using Pydantic BaseSettings.

All settings are loaded from environment variables and/or a `.env` file.
Each settings group (LLM, Voice, Memory, Safety, Server) uses a prefix
(e.g., VOCA_LLM_, VOCA_VOICE_) to namespace env vars.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class LLMSettings(BaseSettings):
    """LLM provider configuration.

    Controls which language model providers are available and their
    connection parameters. Supports Ollama (local), OpenAI, and
    Google Gemini with configurable fallback order.

    @param ollama_url: Base URL for local Ollama API server.
    @param ollama_model: Default model name for Ollama inference.
    @param openai_api_key: API key for OpenAI (optional).
    @param openai_model: Default OpenAI model identifier.
    @param gemini_api_key: API key for Google Gemini (optional).
    @param gemini_model: Default Gemini model identifier.
    @param fallback_order: Provider priority list for automatic fallback.
    """
    ollama_url: str = Field("http://localhost:11434", description="Ollama API URL")
    ollama_model: str = Field("llama3.2", description="Default Ollama model")
    openai_api_key: str | None = Field(None, description="OpenAI API key")
    openai_model: str = Field("gpt-4o-mini", description="Default OpenAI model")
    gemini_api_key: str | None = Field(None, description="Google Gemini API key")
    gemini_model: str = Field("gemini/gemini-2.0-flash", description="Default Gemini model")
    fallback_order: list[str] = Field(
        default=["ollama", "openai", "gemini"],
        description="Provider fallback order",
    )

    model_config = {"env_prefix": "VOCA_LLM_"}


class VoiceSettings(BaseSettings):
    """Voice input/output configuration.

    Controls speech-to-text (faster-whisper), text-to-speech (pyttsx3),
    and voice activity detection parameters.

    @param stt_model: Whisper model size (tiny/base/small/medium/large).
    @param stt_device: Compute device for STT inference (cpu/cuda).
    @param stt_compute_type: Quantization level for STT model.
    @param tts_rate: Speaking rate in words per minute.
    @param vad_aggressiveness: VAD sensitivity level 0-3 (higher = more aggressive).
    @param vad_trailing_silence_ms: Silence duration before speech endpoint.
    @param sample_rate: Audio sample rate in Hz.
    @param chunk_duration_ms: Audio chunk size for VAD processing.
    """
    stt_model: str = Field("small", description="faster-whisper model size")
    stt_device: str = Field("cpu", description="STT compute device")
    stt_compute_type: str = Field("int8", description="STT quantization")
    tts_rate: int = Field(175, description="TTS words per minute")
    vad_aggressiveness: int = Field(2, description="VAD aggressiveness (0-3)")
    vad_trailing_silence_ms: int = Field(500, description="Trailing silence before speech end")
    sample_rate: int = Field(16000, description="Audio sample rate in Hz")
    chunk_duration_ms: int = Field(30, description="Audio chunk duration in ms")

    model_config = {"env_prefix": "VOCA_VOICE_"}


class MemorySettings(BaseSettings):
    """Memory subsystem configuration.

    Configures paths and parameters for the 4-layer memory system:
    Working (conversation buffer), Episodic (FAISS vectors),
    Semantic (key-value facts), and Secure (Fernet-encrypted vault).

    @param faiss_index_path: File path for the FAISS vector index.
    @param embedding_model: sentence-transformers model name for embeddings.
    @param semantic_store_path: JSON file path for semantic memory.
    @param secure_vault_path: Encrypted vault file path.
    @param working_memory_max_turns: Max conversation turns to retain.
    """
    faiss_index_path: Path = Field(
        Path("data/faiss_index"), description="FAISS index storage path"
    )
    embedding_model: str = Field(
        "all-MiniLM-L6-v2", description="Sentence-transformers model"
    )
    semantic_store_path: Path = Field(
        Path("data/semantic.json"), description="Semantic memory JSON path"
    )
    secure_vault_path: Path = Field(
        Path("data/vault.enc"), description="Encrypted vault file path"
    )
    working_memory_max_turns: int = Field(
        20, description="Max conversation turns in working memory"
    )

    model_config = {"env_prefix": "VOCA_MEMORY_"}


class SafetySettings(BaseSettings):
    """Safety policy configuration.

    Defines lists of actions categorized by risk level:
    allowed (no confirmation), confirm (user approval needed),
    and denied (always blocked).

    @param allowed_actions: Actions that execute without confirmation.
    @param confirm_actions: Actions requiring explicit user approval.
    @param denied_actions: Actions that are always blocked.
    """
    allowed_actions: list[str] = Field(
        default=["chat", "check_mood", "suggest_activity", "tell_joke", "get_time"],
        description="Actions that need no confirmation",
    )
    confirm_actions: list[str] = Field(
        default=["execute_script", "send_email", "manage_files"],
        description="Actions requiring user confirmation",
    )
    denied_actions: list[str] = Field(
        default=["transfer_money", "delete_all"],
        description="Actions that are always blocked",
    )

    model_config = {"env_prefix": "VOCA_SAFETY_"}


class ServerSettings(BaseSettings):
    """FastAPI server configuration.

    Controls the HTTP server binding, CORS policy, and authentication.

    @param host: IP address to bind (127.0.0.1 for local-only, 0.0.0.0 for network).
    @param port: TCP port for the FastAPI server.
    @param cors_origins: List of allowed CORS origins.
    @param api_key: Bearer token for API authentication (empty = disabled).
    @param webhook_secret: Shared secret for TradingView webhook verification.
    """
    host: str = Field(
        "127.0.0.1",
        description="Server bind host (127.0.0.1 for local, 0.0.0.0 for network)",
    )
    port: int = Field(8000, description="Server bind port")
    cors_origins: list[str] = Field(
        default=["http://localhost:8000", "http://127.0.0.1:8000"],
        description="CORS allowed origins",
    )
    api_key: str = Field(
        "", description="API key for authenticating requests (empty = no auth)",
    )
    webhook_secret: str = Field(
        "", description="Shared secret for TradingView webhook verification",
    )

    model_config = {"env_prefix": "VOCA_SERVER_"}


class Settings(BaseSettings):
    """Root settings — aggregates all configuration groups.

    Loads configuration from environment variables with the VOCA_ prefix
    and from a `.env` file. Supports nested delimiter `__` for sub-settings.

    @param llm: LLM provider settings.
    @param voice: Voice I/O settings.
    @param memory: Memory subsystem settings.
    @param safety: Safety policy settings.
    @param server: FastAPI server settings.
    @param debug: Enable verbose debug logging.
    @param data_dir: Root directory for persistent data storage.
    """
    llm: LLMSettings = Field(default_factory=LLMSettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    safety: SafetySettings = Field(default_factory=SafetySettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    debug: bool = Field(False, description="Enable debug logging")
    data_dir: Path = Field(Path("data"), description="Data storage directory")

    model_config = {"env_prefix": "VOCA_", "env_file": ".env", "env_nested_delimiter": "__"}

    def ensure_data_dirs(self) -> None:
        """Create data directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.memory.faiss_index_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
