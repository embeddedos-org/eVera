"""Vera configuration — Pydantic Settings loading from .env.

@file config.py
@brief Central configuration module using Pydantic BaseSettings.

All settings are loaded from environment variables and/or a `.env` file.
Each settings group (LLM, Voice, Memory, Safety, Server) uses a prefix
(e.g., VERA_LLM_, VERA_VOICE_) to namespace env vars.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


def _resolve_env_file() -> str:
    """Resolve the .env file path, handling PyInstaller frozen exes."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle — check _MEIPASS first, then exe dir
        meipass = Path(getattr(sys, "_MEIPASS", "."))
        exe_dir = Path(sys.executable).parent
        # Prefer user's .env next to the exe (editable), fall back to bundled
        for candidate in [exe_dir / ".env", meipass / ".env", meipass / ".env.example"]:
            if candidate.is_file():
                return str(candidate)
        return str(exe_dir / ".env")
    return ".env"


def _resolve_data_dir() -> Path:
    """Resolve the data directory, using %APPDATA%/eVera in production."""
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", "")
            if appdata:
                return Path(appdata) / "eVera" / "data"
        return Path(sys.executable).parent / "data"
    return Path("data")


class LLMSettings(BaseSettings):
    """LLM provider configuration.

    Controls which language model providers are available and their
    connection parameters. Supports Ollama (local), OpenAI, and
    Google Gemini with configurable fallback order.
    """

    ollama_url: str = Field("http://localhost:11434", description="Ollama API URL")
    ollama_model: str = Field("llama3.2", description="Default Ollama model")
    openai_api_key: str | None = Field(None, description="OpenAI API key")
    openai_model: str = Field("gpt-4o-mini", description="Default OpenAI model")
    gemini_api_key: str | None = Field(None, description="Google Gemini API key")
    gemini_model: str = Field("gemini/gemini-2.0-flash", description="Default Gemini model")
    # Phase 1: Additional providers
    anthropic_api_key: str | None = Field(None, description="Anthropic API key")
    anthropic_model: str = Field("claude-sonnet-4-20250514", description="Default Anthropic model")
    mistral_api_key: str | None = Field(None, description="Mistral API key")
    deepseek_api_key: str | None = Field(None, description="DeepSeek API key")
    groq_api_key: str | None = Field(None, description="Groq API key")
    together_api_key: str | None = Field(None, description="Together AI API key")
    perplexity_api_key: str | None = Field(None, description="Perplexity API key")
    fallback_order: list[str] = Field(
        default=["ollama", "openai", "gemini"],
        description="Provider fallback order",
    )

    model_config = {"env_prefix": "VERA_LLM_"}


class VoiceSettings(BaseSettings):
    """Voice input/output configuration."""

    stt_model: str = Field("small", description="faster-whisper model size")
    stt_device: str = Field("cpu", description="STT compute device")
    stt_compute_type: str = Field("int8", description="STT quantization")
    tts_rate: int = Field(175, description="TTS words per minute")
    vad_aggressiveness: int = Field(2, description="VAD aggressiveness (0-3)")
    vad_trailing_silence_ms: int = Field(500, description="Trailing silence before speech end")
    sample_rate: int = Field(16000, description="Audio sample rate in Hz")
    chunk_duration_ms: int = Field(30, description="Audio chunk duration in ms")
    server_enabled: bool = Field(False, description="Enable voice input/output in server mode via WebSocket")
    tts_engine: str = Field("pyttsx3", description="TTS engine: pyttsx3 (local) or edge-tts (streaming)")
    wake_word_enabled: bool = Field(False, description="Enable wake word activation mode")
    wake_word_phrase: str = Field("hey vera", description="Trigger phrase (case-insensitive)")
    wake_word_timeout_s: int = Field(10, description="Seconds of silence before auto-deactivation")
    wake_word_chime: bool = Field(True, description="Play activation chime on wake word")
    proactive_tts_enabled: bool = Field(False, description="Speak proactive notifications aloud")

    model_config = {"env_prefix": "VERA_VOICE_"}


class VisionSettings(BaseSettings):
    """Real-time screen vision monitoring configuration."""

    monitor_enabled: bool = Field(False, description="Enable periodic screen monitoring")
    monitor_interval_s: int = Field(10, description="Seconds between screen captures")
    monitor_model: str = Field("gpt-4o", description="Vision LLM model to use")
    monitor_prompt: str = Field(
        "Briefly describe what is on screen. Focus on active application, visible text, and user activity.",
        description="System prompt for screen analysis",
    )

    model_config = {"env_prefix": "VERA_VISION_"}


class MobileSettings(BaseSettings):
    """Mobile device control configuration."""

    control_enabled: bool = Field(False, description="Enable mobile device control via WebSocket")
    control_commands: list[str] = Field(
        default=["notification", "clipboard", "open_app", "set_alarm", "toggle_setting", "device_info"],
        description="Allowed mobile command types",
    )
    command_timeout_s: int = Field(10, description="Timeout for mobile commands in seconds")

    model_config = {"env_prefix": "VERA_MOBILE_"}


class JobHunterSettings(BaseSettings):
    """Autonomous job searching and application configuration."""

    enabled: bool = Field(False, description="Master toggle for job hunter agent")
    auto_apply: bool = Field(True, description="Fully automatic mode (vs. review-first)")
    scan_interval_minutes: int = Field(120, description="Minutes between automatic job scans")
    max_daily_applications: int = Field(25, description="Daily application cap to avoid spam/bans")
    resume_path: str = Field("data/job_profile/resume.pdf", description="Path to user resume file")
    target_titles: list[str] = Field(default=[], description="Desired job titles (e.g. Software Engineer)")
    target_locations: list[str] = Field(default=[], description="Preferred locations (e.g. Remote)")
    min_salary: int = Field(0, description="Minimum salary filter")
    excluded_companies: list[str] = Field(default=[], description="Companies to skip")
    cover_letter_enabled: bool = Field(True, description="Generate tailored cover letters via LLM")
    fit_threshold: float = Field(0.5, description="Minimum job fit score (0-1) to auto-apply")

    model_config = {"env_prefix": "VERA_JOB_"}


class MemorySettings(BaseSettings):
    """Memory subsystem configuration."""

    faiss_index_path: Path = Field(Path("data/faiss_index"), description="FAISS index storage path")
    embedding_model: str = Field("all-MiniLM-L6-v2", description="Sentence-transformers model")
    semantic_store_path: Path = Field(Path("data/semantic.json"), description="Semantic memory JSON path")
    secure_vault_path: Path = Field(Path("data/vault.enc"), description="Encrypted vault file path")
    working_memory_max_turns: int = Field(20, description="Max conversation turns in working memory")
    fact_extraction_enabled: bool = Field(True, description="Enable LLM-powered fact extraction from conversations")
    fact_extraction_tier: str = Field("EXECUTOR", description="ModelTier for fact extraction LLM calls")
    fact_extraction_min_words: int = Field(5, description="Minimum transcript word count to trigger fact extraction")

    model_config = {"env_prefix": "VERA_MEMORY_"}


class SafetySettings(BaseSettings):
    """Safety policy configuration."""

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
    coder_unsafe_paths: bool = Field(
        False,
        description="Skip BLOCKED_PATHS check in Coder agent (still logs warnings)",
    )
    coder_allowed_extra_paths: list[str] = Field(
        default=[],
        description="Additional root paths the Coder agent may access",
    )
    admin_enabled: bool = Field(
        False,
        description="Enable elevated/admin command execution",
    )
    admin_allowed_commands: list[str] = Field(
        default=[],
        description="fnmatch patterns for allowed admin commands",
    )
    admin_audit_log: str = Field(
        "data/admin_audit.log",
        description="Path for admin command audit log",
    )

    model_config = {"env_prefix": "VERA_SAFETY_"}


class ServerSettings(BaseSettings):
    """FastAPI server configuration."""

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
        "",
        description="API key for authenticating requests (empty = no auth)",
    )
    webhook_secret: str = Field(
        "",
        description="Shared secret for TradingView webhook verification",
    )

    model_config = {"env_prefix": "VERA_SERVER_"}


class PlannerSettings(BaseSettings):
    """Planner agent configuration — daily/weekly/monthly planning cycles."""

    enabled: bool = Field(True, description="Enable planner agent")
    morning_plan_time: str = Field("08:00", description="Time to generate morning plan (HH:MM)")
    daily_review_time: str = Field("18:00", description="Time to prompt daily review (HH:MM)")
    weekly_review_day: str = Field("sunday", description="Day of week for weekly review")
    monthly_review_day: int = Field(1, description="Day of month for monthly review")

    model_config = {"env_prefix": "VERA_PLANNER_"}


class WellnessSettings(BaseSettings):
    """Wellness agent configuration — focus sessions, breaks, burnout prevention."""

    enabled: bool = Field(True, description="Enable wellness agent")
    focus_duration_min: int = Field(25, description="Default pomodoro/focus duration in minutes")
    break_duration_min: int = Field(5, description="Default break duration in minutes")
    break_reminder_interval_min: int = Field(90, description="Remind to break every N minutes of continuous work")
    max_work_hours: int = Field(8, description="Maximum recommended work hours per day")
    burnout_threshold: int = Field(3, description="Consecutive low energy ratings that trigger burnout warning")

    model_config = {"env_prefix": "VERA_WELLNESS_"}


class EmotionalSettings(BaseSettings):
    """Emotional intelligence configuration — sentiment analysis and mood tracking."""

    enabled: bool = Field(True, description="Master toggle for emotional intelligence")
    sentiment_method: str = Field("hybrid", description="Sentiment method: keyword, llm, or hybrid")
    sentiment_tier: str = Field("EXECUTOR", description="ModelTier for LLM sentiment calls")
    mood_check_interval_min: int = Field(30, description="Minutes between proactive mood checks")
    negative_mood_threshold: int = Field(3, description="Consecutive negative moods before outreach")
    pattern_lookback_days: int = Field(14, description="Days of history for pattern analysis")
    proactive_empathy_enabled: bool = Field(True, description="Enable proactive mood-based notifications")

    model_config = {"env_prefix": "VERA_EMOTIONAL_"}


class DigestSettings(BaseSettings):
    """Digest agent configuration — RSS feeds, news digests, information filtering."""

    enabled: bool = Field(True, description="Enable digest agent")
    digest_time: str = Field("07:30", description="Time to generate daily digest (HH:MM)")
    max_items_per_source: int = Field(5, description="Maximum items to fetch per source")
    auto_digest: bool = Field(True, description="Generate digest automatically vs on-demand only")

    model_config = {"env_prefix": "VERA_DIGEST_"}


class JiraSettings(BaseSettings):
    """Jira/ticket system integration configuration."""

    enabled: bool = Field(False, description="Enable Jira integration")
    base_url: str = Field("", description="Jira Cloud base URL (e.g. https://myorg.atlassian.net)")
    api_token: str = Field("", description="Jira API token")
    username: str = Field("", description="Jira username/email for Basic auth")
    project_key: str = Field("", description="Default Jira project key (e.g. PROJ)")
    board_id: str = Field("", description="Agile board ID for sprint queries")
    provider: str = Field("jira", description="Ticket provider: jira, github, linear, azure_devops")
    scan_interval_minutes: int = Field(15, description="Minutes between automatic ticket scans")

    model_config = {"env_prefix": "VERA_JIRA_"}


class ChannelMonitorSettings(BaseSettings):
    """Slack/Teams channel monitoring configuration."""

    enabled: bool = Field(False, description="Enable channel monitoring")
    channels: list[str] = Field(default=[], description="Channel IDs to monitor")
    poll_interval_min: int = Field(5, description="Minutes between channel polls")
    summarize: bool = Field(True, description="LLM-summarize channel activity")
    mention_alert: bool = Field(True, description="Alert on @mentions")

    model_config = {"env_prefix": "VERA_CHANNEL_"}


class CodebaseIndexerSettings(BaseSettings):
    """Codebase indexing and analysis configuration."""

    enabled: bool = Field(True, description="Enable codebase indexer agent")
    default_project_path: str = Field(".", description="Default project path to index")
    max_files: int = Field(500, description="Maximum files to index per project")
    index_extensions: list[str] = Field(
        default=[".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".h"],
        description="File extensions to index",
    )

    model_config = {"env_prefix": "VERA_CODEBASE_"}


class MeetingSettings(BaseSettings):
    """Meeting notes processing configuration."""

    enabled: bool = Field(True, description="Enable meeting agent")
    auto_create_tickets: bool = Field(False, description="Auto-create Jira tickets from action items")
    auto_create_todos: bool = Field(True, description="Auto-create todos from action items")

    model_config = {"env_prefix": "VERA_MEETING_"}


class MediaSettings(BaseSettings):
    """Media factory agent configuration — image gen, video assembly, social upload."""

    enabled: bool = Field(True, description="Enable media factory agent")
    dalle_api_key: str = Field("", description="OpenAI DALL-E API key for premium image generation")
    youtube_client_secrets_path: str = Field("", description="Path to YouTube OAuth client_secret.json")
    youtube_credentials_path: str = Field(
        "data/media/youtube_creds.json", description="Path to cached YouTube OAuth credentials"
    )
    instagram_access_token: str = Field("", description="Instagram Graph API access token")
    tiktok_session_cookie: str = Field("", description="TikTok session cookie for browser automation")
    default_voice: str = Field("en-US-AriaNeural", description="Default edge-tts voice for voiceovers")
    default_aspect_ratio: str = Field("9:16", description="Default video aspect ratio (Reels format)")
    max_video_duration_sec: int = Field(120, description="Maximum video duration in seconds")
    default_image_provider: str = Field("pollinations", description="Default image provider: pollinations or dalle")

    model_config = {"env_prefix": "VERA_MEDIA_"}


class BrokerSettings(BaseSettings):
    """Trading broker configuration."""

    alpaca_api_key: str = Field("", description="Alpaca API key")
    alpaca_secret_key: str = Field("", description="Alpaca secret key")
    alpaca_paper: bool = Field(True, description="Use Alpaca paper trading")
    ibkr_host: str = Field("127.0.0.1", description="IBKR Gateway host")
    ibkr_port: int = Field(7497, description="IBKR Gateway port (7497=paper, 7496=live)")
    ibkr_client_id: int = Field(1, description="IBKR client ID")
    auto_trade_limit: float = Field(500.0, description="Auto-trade threshold in dollars")

    model_config = {"env_prefix": "VERA_"}


class Settings(BaseSettings):
    """Root settings — aggregates all configuration groups."""

    llm: LLMSettings = Field(default_factory=LLMSettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    vision: VisionSettings = Field(default_factory=VisionSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    safety: SafetySettings = Field(default_factory=SafetySettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    mobile: MobileSettings = Field(default_factory=MobileSettings)
    job_hunter: JobHunterSettings = Field(default_factory=JobHunterSettings)
    planner: PlannerSettings = Field(default_factory=PlannerSettings)
    wellness: WellnessSettings = Field(default_factory=WellnessSettings)
    digest: DigestSettings = Field(default_factory=DigestSettings)
    emotional: EmotionalSettings = Field(default_factory=EmotionalSettings)
    jira: JiraSettings = Field(default_factory=JiraSettings)
    channel_monitor: ChannelMonitorSettings = Field(default_factory=ChannelMonitorSettings)
    codebase_indexer: CodebaseIndexerSettings = Field(default_factory=CodebaseIndexerSettings)
    meeting: MeetingSettings = Field(default_factory=MeetingSettings)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    media: MediaSettings = Field(default_factory=MediaSettings)
    debug: bool = Field(False, description="Enable debug logging")
    data_dir: Path = Field(default_factory=_resolve_data_dir, description="Data storage directory")

    model_config = {
        "env_prefix": "VERA_",
        "env_file": _resolve_env_file(),
        "env_nested_delimiter": "__",
        "extra": "ignore",
    }

    def ensure_data_dirs(self) -> None:
        """Create data directories if they don't exist."""
        dirs = [
            self.data_dir,
            self.data_dir / "faiss_index",
            self.data_dir / "media",
            self.data_dir / "diagrams",
            self.data_dir / "knowledge",
            self.data_dir / "job_profile",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        self.memory.faiss_index_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
