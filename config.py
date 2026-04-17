"""Voca configuration — Pydantic Settings loading from .env."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class LLMSettings(BaseSettings):
    ollama_url: str = Field("http://localhost:11434", description="Ollama API URL")
    ollama_model: str = Field("llama3.2", description="Default Ollama model")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    openai_model: str = Field("gpt-4o-mini", description="Default OpenAI model")
    gemini_api_key: Optional[str] = Field(None, description="Google Gemini API key")
    gemini_model: str = Field("gemini/gemini-2.0-flash", description="Default Gemini model")
    fallback_order: list[str] = Field(
        default=["ollama", "openai", "gemini"],
        description="Provider fallback order",
    )

    model_config = {"env_prefix": "VOCA_LLM_"}


class VoiceSettings(BaseSettings):
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
    host: str = Field("127.0.0.1", description="Server bind host (use 127.0.0.1 for local-only, 0.0.0.0 for network)")
    port: int = Field(8000, description="Server bind port")
    cors_origins: list[str] = Field(default=["http://localhost:8000", "http://127.0.0.1:8000"], description="CORS allowed origins")
    api_key: str = Field("", description="API key for authenticating requests (empty = no auth)")
    webhook_secret: str = Field("", description="Shared secret for TradingView webhook verification")

    model_config = {"env_prefix": "VOCA_SERVER_"}


class Settings(BaseSettings):
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
