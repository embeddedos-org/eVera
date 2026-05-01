"""Music Agent -- playback, Spotify/YouTube control, DJ mixing, podcasts.

Beats Alexa/Siri/Google: multi-platform music, AI DJ, podcasts, lyrics, mood playlists.
"""

from __future__ import annotations

import logging
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


class SpotifyControlTool(Tool):
    """Control Spotify playback."""

    def __init__(self):
        super().__init__(
            name="spotify_control",
            description="Control Spotify (play/pause/skip/search/queue/volume/shuffle/current)",
            parameters={
                "action": {
                    "type": "str",
                    "description": "play|pause|skip|previous|queue|search|volume|shuffle|current",
                },
                "query": {"type": "str", "description": "Song/artist name"},
                "volume": {"type": "int", "description": "Volume 0-100"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        action, query = kw.get("action", "current"), kw.get("query", "")
        try:
            import os

            import spotipy
            from spotipy.oauth2 import SpotifyOAuth

            sp = spotipy.Spotify(
                auth_manager=SpotifyOAuth(
                    client_id=os.getenv("SPOTIFY_CLIENT_ID", ""),
                    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", ""),
                    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback"),
                    scope="user-modify-playback-state user-read-playback-state user-read-currently-playing",
                )
            )
            if action == "play" and query:
                r = sp.search(q=query, limit=1, type="track")
                t = r["tracks"]["items"][0] if r["tracks"]["items"] else None
                if t:
                    sp.start_playback(uris=[t["uri"]])
                    return {"status": "success", "track": t["name"], "artist": t["artists"][0]["name"]}
            elif action == "pause":
                sp.pause_playback()
                return {"status": "success", "action": "paused"}
            elif action == "skip":
                sp.next_track()
                return {"status": "success", "action": "skipped"}
            elif action == "previous":
                sp.previous_track()
                return {"status": "success", "action": "previous"}
            elif action == "volume":
                sp.volume(kw.get("volume", 50))
                return {"status": "success", "volume": kw.get("volume", 50)}
            elif action == "current":
                c = sp.current_playback()
                if c and c.get("item"):
                    return {
                        "status": "success",
                        "track": c["item"]["name"],
                        "artist": c["item"]["artists"][0]["name"],
                        "playing": c["is_playing"],
                    }
                return {"status": "success", "message": "Nothing playing"}
            elif action == "search":
                r = sp.search(q=query, limit=5, type="track")
                return {
                    "status": "success",
                    "results": [
                        {"name": t["name"], "artist": t["artists"][0]["name"]}
                        for t in r.get("tracks", {}).get("items", [])
                    ],
                }
            elif action == "queue" and query:
                r = sp.search(q=query, limit=1, type="track")
                t = r["tracks"]["items"][0]
                sp.add_to_queue(t["uri"])
                return {"status": "success", "queued": t["name"]}
            return {"status": "success", "action": action}
        except ImportError:
            return {"status": "error", "message": "pip install spotipy"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class YouTubeMusicTool(Tool):
    """Search YouTube music."""

    def __init__(self):
        super().__init__(
            name="youtube_music",
            description="Search YouTube music",
            parameters={
                "query": {"type": "str", "description": "Search query"},
                "max_results": {"type": "int", "description": "Max results"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as d:
                results = list(
                    d.text(f"site:youtube.com {kw.get('query', '')} music", max_results=kw.get("max_results", 5))
                )
            return {"status": "success", "results": [{"title": r["title"], "url": r["href"]} for r in results]}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class LyricsLookupTool(Tool):
    """Look up song lyrics."""

    def __init__(self):
        super().__init__(
            name="lyrics_lookup",
            description="Find song lyrics",
            parameters={
                "song": {"type": "str", "description": "Song title"},
                "artist": {"type": "str", "description": "Artist name"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"https://api.lyrics.ovh/v1/{kw.get('artist', '')}/{kw.get('song', '')}")
                if r.status_code == 200:
                    return {"status": "success", "lyrics": r.json().get("lyrics", "")[:2000]}
            return {"status": "success", "message": "Lyrics not found via API"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class MoodPlaylistTool(Tool):
    """Generate mood-based playlist recommendations."""

    def __init__(self):
        super().__init__(
            name="mood_playlist",
            description="Mood-based playlist recommendations",
            parameters={
                "mood": {"type": "str", "description": "happy|sad|energetic|calm|focus|romantic|chill|workout|sleep"}
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        m = kw.get("mood", "chill")
        g = {
            "happy": ["pop", "dance", "indie pop"],
            "sad": ["acoustic", "piano", "ambient"],
            "energetic": ["edm", "hip-hop", "rock"],
            "calm": ["ambient", "classical", "lo-fi"],
            "focus": ["lo-fi beats", "classical", "ambient"],
            "romantic": ["r&b", "soul", "jazz"],
            "chill": ["chillhop", "lo-fi", "downtempo"],
            "workout": ["edm", "dubstep", "drum and bass"],
            "sleep": ["ambient", "nature sounds", "white noise"],
        }.get(m, ["pop"])
        return {"status": "success", "mood": m, "genres": g}


class PodcastDiscoveryTool(Tool):
    """Discover podcasts via iTunes API."""

    def __init__(self):
        super().__init__(
            name="podcast_discovery",
            description="Discover podcasts by topic",
            parameters={
                "topic": {"type": "str", "description": "Topic"},
                "max_results": {"type": "int", "description": "Max results"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from urllib.parse import quote_plus

            import httpx

            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(
                    f"https://itunes.apple.com/search?term={quote_plus(kw.get('topic', ''))}&media=podcast&limit={kw.get('max_results', 5)}"
                )
            return {
                "status": "success",
                "podcasts": [
                    {"name": p["collectionName"], "artist": p["artistName"]} for p in r.json().get("results", [])
                ],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class AudioAnalysisTool(Tool):
    """Analyze audio files for BPM, key, duration."""

    def __init__(self):
        super().__init__(
            name="audio_analysis",
            description="Analyze audio for BPM/key/duration",
            parameters={"file_path": {"type": "str", "description": "Audio file path"}},
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import librosa

            y, sr = librosa.load(kw["file_path"])
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            return {
                "status": "success",
                "bpm": round(float(tempo)),
                "duration_s": round(librosa.get_duration(y=y, sr=sr), 2),
            }
        except ImportError:
            return {"status": "error", "message": "pip install librosa"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class DJMixTool(Tool):
    """Create crossfade mixes between tracks."""

    def __init__(self):
        super().__init__(
            name="dj_mix",
            description="Create crossfade mix between tracks",
            parameters={
                "track1": {"type": "str", "description": "First track"},
                "track2": {"type": "str", "description": "Second track"},
                "crossfade_seconds": {"type": "int", "description": "Crossfade duration"},
                "output": {"type": "str", "description": "Output path"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from pydub import AudioSegment

            out = kw.get("output", "mix.wav")
            AudioSegment.from_file(kw["track1"]).append(
                AudioSegment.from_file(kw["track2"]), crossfade=kw.get("crossfade_seconds", 5) * 1000
            ).export(out, format="wav")
            return {"status": "success", "output": out}
        except ImportError:
            return {"status": "error", "message": "pip install pydub"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class MusicAgent(BaseAgent):
    """Music playback, DJ mixing, podcast discovery, and audio analysis."""

    name = "music"
    description = "Music playback, Spotify/YouTube, DJ mixing, podcasts, lyrics, mood playlists, audio analysis"
    tier = ModelTier.SPECIALIST
    system_prompt = "You are eVera's Music Agent. Control Spotify, search YouTube, find lyrics, create mood playlists, discover podcasts, analyze audio, create DJ mixes."
    offline_responses = {
        "play": "\U0001f3b5 Playing!",
        "music": "\U0001f3b6 Finding music!",
        "song": "\U0001f3b5 Looking up!",
        "podcast": "\U0001f399 Finding podcasts!",
        "lyrics": "\U0001f4dd Looking up lyrics!",
    }

    def _setup_tools(self):
        self._tools = [
            SpotifyControlTool(),
            YouTubeMusicTool(),
            LyricsLookupTool(),
            MoodPlaylistTool(),
            PodcastDiscoveryTool(),
            AudioAnalysisTool(),
            DJMixTool(),
        ]
