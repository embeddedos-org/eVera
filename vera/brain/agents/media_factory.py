"""MediaFactory Agent — image generation, video assembly, subtitles, and social media upload.

@file vera/brain/agents/media_factory.py
@brief Agent for autonomous end-to-end content creation: generate images,
       assemble videos with Ken Burns transitions, add subtitles, and upload
       to YouTube/Instagram/TikTok.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "media"


def _ensure_dirs() -> None:
    for sub in ("images", "audio", "videos", "uploads"):
        (DATA_DIR / sub).mkdir(parents=True, exist_ok=True)


def _uploads_log() -> Path:
    _ensure_dirs()
    return DATA_DIR / "uploads.json"


def _log_upload(entry: dict) -> None:
    path = _uploads_log()
    data: list[dict] = []
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = []
    data.append(entry)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Phase 2: Image Generation & Editing Tools (1-4)
# ---------------------------------------------------------------------------


class GenerateImageTool(Tool):
    """Generate an image using Pollinations (free) or DALL-E 3 (premium)."""

    def __init__(self) -> None:
        super().__init__(
            name="generate_image",
            description="Generate an AI image from a text prompt (Pollinations free, DALL-E 3 premium)",
            parameters={
                "prompt": {"type": "str", "description": "Image generation prompt"},
                "width": {"type": "int", "description": "Image width in pixels (default: 1024)"},
                "height": {"type": "int", "description": "Image height in pixels (default: 1024)"},
                "style": {
                    "type": "str",
                    "description": "Image style: realistic, artistic, cartoon (default: realistic)",
                },
                "provider": {"type": "str", "description": "Provider: auto, pollinations, dalle (default: auto)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        import httpx

        prompt = kwargs.get("prompt", "")
        width = int(kwargs.get("width", 1024))
        height = int(kwargs.get("height", 1024))
        style = kwargs.get("style", "realistic")
        provider = kwargs.get("provider", "auto").lower()

        if not prompt:
            return {"status": "error", "message": "No prompt provided"}

        _ensure_dirs()
        from config import settings

        dalle_key = settings.media.dalle_api_key or os.getenv("VERA_MEDIA_DALLE_API_KEY", "")

        if provider == "auto":
            provider = "dalle" if dalle_key else "pollinations"

        styled_prompt = f"{style} style: {prompt}" if style != "realistic" else prompt
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = DATA_DIR / "images" / f"img_{ts}.png"

        if provider == "dalle" and dalle_key:
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/images/generations",
                        headers={"Authorization": f"Bearer {dalle_key}", "Content-Type": "application/json"},
                        json={
                            "model": "dall-e-3",
                            "prompt": styled_prompt,
                            "n": 1,
                            "size": f"{width}x{height}",
                            "response_format": "url",
                        },
                    )
                    resp.raise_for_status()
                    image_url = resp.json()["data"][0]["url"]
                    img_resp = await client.get(image_url)
                    out_path.write_bytes(img_resp.content)
                    return {"status": "success", "path": str(out_path), "provider": "dalle", "prompt": prompt}
            except Exception as e:
                logger.warning("DALL-E failed, falling back to Pollinations: %s", e)
                provider = "pollinations"

        # Pollinations (free, no API key)
        encoded_prompt = urllib.parse.quote(styled_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}"
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                out_path.write_bytes(resp.content)
                return {"status": "success", "path": str(out_path), "provider": "pollinations", "prompt": prompt}
        except Exception as e:
            return {"status": "error", "message": f"Image generation failed: {e}"}


class EditImageTool(Tool):
    """Edit an image: resize, crop, rotate, flip, brightness, contrast, etc."""

    def __init__(self) -> None:
        super().__init__(
            name="edit_image",
            description="Edit an image (resize, crop, rotate, flip, brightness, contrast, blur, sharpen, grayscale, sepia)",
            parameters={
                "path": {"type": "str", "description": "Path to the image file"},
                "action": {
                    "type": "str",
                    "description": "Action: resize, crop, rotate, flip, brightness, contrast, blur, sharpen, grayscale, sepia",
                },
                "value": {
                    "type": "str",
                    "description": "Action value — resize: 'WxH', rotate: degrees, brightness/contrast: 0.5-2.0, flip: horizontal/vertical",
                },
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from PIL import Image, ImageEnhance, ImageFilter

        img_path = kwargs.get("path", "")
        action = kwargs.get("action", "").lower()
        value = kwargs.get("value", "")

        if not img_path or not os.path.exists(img_path):
            return {"status": "error", "message": f"Image not found: {img_path}"}

        img = Image.open(img_path)
        p = Path(img_path)
        out_path = p.parent / f"{p.stem}_edited_{action}{p.suffix}"

        if action == "resize" and "x" in str(value).lower():
            w, h = (int(x) for x in str(value).lower().split("x"))
            img = img.resize((w, h), Image.LANCZOS)
        elif action == "rotate":
            img = img.rotate(float(value), expand=True)
        elif action == "flip":
            if value.lower() == "horizontal":
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            else:
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
        elif action == "brightness":
            img = ImageEnhance.Brightness(img).enhance(float(value))
        elif action == "contrast":
            img = ImageEnhance.Contrast(img).enhance(float(value))
        elif action == "blur":
            radius = float(value) if value else 2.0
            img = img.filter(ImageFilter.GaussianBlur(radius=radius))
        elif action == "sharpen":
            img = img.filter(ImageFilter.SHARPEN)
        elif action == "grayscale":
            img = img.convert("L").convert("RGB")
        elif action == "sepia":
            img = img.convert("RGB")
            pixels = img.load()
            w, h = img.size
            for y in range(h):
                for x in range(w):
                    r, g, b = pixels[x, y]
                    tr = min(255, int(0.393 * r + 0.769 * g + 0.189 * b))
                    tg = min(255, int(0.349 * r + 0.686 * g + 0.168 * b))
                    tb = min(255, int(0.272 * r + 0.534 * g + 0.131 * b))
                    pixels[x, y] = (tr, tg, tb)
        elif action == "crop" and value:
            coords = [int(x.strip()) for x in str(value).split(",")]
            if len(coords) == 4:
                img = img.crop(tuple(coords))
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

        img.save(str(out_path))
        return {"status": "success", "path": str(out_path), "action": action}


class AddTextOverlayTool(Tool):
    """Add text overlay to an image."""

    def __init__(self) -> None:
        super().__init__(
            name="add_text_overlay",
            description="Add text overlay to an image with customizable position, font, and colors",
            parameters={
                "image_path": {"type": "str", "description": "Path to the image file"},
                "text": {"type": "str", "description": "Text to overlay"},
                "position": {"type": "str", "description": "Position: top, center, bottom (default: bottom)"},
                "font_size": {"type": "int", "description": "Font size in pixels (default: 48)"},
                "color": {"type": "str", "description": "Text color (default: white)"},
                "stroke_color": {"type": "str", "description": "Stroke/outline color (default: black)"},
                "stroke_width": {"type": "int", "description": "Stroke width (default: 2)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from PIL import Image, ImageDraw, ImageFont

        image_path = kwargs.get("image_path", "")
        text = kwargs.get("text", "")
        position = kwargs.get("position", "bottom").lower()
        font_size = int(kwargs.get("font_size", 48))
        color = kwargs.get("color", "white")
        stroke_color = kwargs.get("stroke_color", "black")
        stroke_width = int(kwargs.get("stroke_width", 2))

        if not image_path or not os.path.exists(image_path):
            return {"status": "error", "message": f"Image not found: {image_path}"}
        if not text:
            return {"status": "error", "message": "No text provided"}

        img = Image.open(image_path).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        img_w, img_h = img.size

        x = (img_w - text_w) // 2
        if position == "top":
            y = int(img_h * 0.05)
        elif position == "center":
            y = (img_h - text_h) // 2
        else:
            y = int(img_h * 0.85)

        padding = 10
        bg_rect = (x - padding, y - padding, x + text_w + padding, y + text_h + padding)
        draw.rectangle(bg_rect, fill=(0, 0, 0, 128))
        draw.text((x, y), text, font=font, fill=color, stroke_width=stroke_width, stroke_fill=stroke_color)

        result = Image.alpha_composite(img, overlay).convert("RGB")
        p = Path(image_path)
        out_path = p.parent / f"{p.stem}_text{p.suffix}"
        result.save(str(out_path))
        return {"status": "success", "path": str(out_path)}


class RemoveBackgroundTool(Tool):
    """Remove the background from an image using rembg."""

    def __init__(self) -> None:
        super().__init__(
            name="remove_background",
            description="Remove the background from an image (requires rembg)",
            parameters={
                "image_path": {"type": "str", "description": "Path to the image file"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        image_path = kwargs.get("image_path", "")
        if not image_path or not os.path.exists(image_path):
            return {"status": "error", "message": f"Image not found: {image_path}"}

        try:
            from rembg import remove
        except ImportError:
            return {"status": "error", "message": "rembg not installed. Run: pip install rembg"}

        from PIL import Image

        img = Image.open(image_path)
        result = remove(img)

        p = Path(image_path)
        out_path = p.parent / f"{p.stem}_nobg.png"
        result.save(str(out_path))
        return {"status": "success", "path": str(out_path)}


# ---------------------------------------------------------------------------
# Phase 3: Audio & Video Production Tools (5-8)
# ---------------------------------------------------------------------------


class GenerateVoiceoverTool(Tool):
    """Generate a voiceover audio file using edge-tts."""

    def __init__(self) -> None:
        super().__init__(
            name="generate_voiceover",
            description="Generate a text-to-speech voiceover using edge-tts",
            parameters={
                "text": {"type": "str", "description": "Text to convert to speech"},
                "voice": {"type": "str", "description": "edge-tts voice name (default: en-US-AriaNeural)"},
                "output_format": {"type": "str", "description": "Output format: mp3 or wav (default: mp3)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        text = kwargs.get("text", "")
        if not text:
            return {"status": "error", "message": "No text provided"}

        from config import settings

        voice = kwargs.get("voice", "") or settings.media.default_voice
        output_format = kwargs.get("output_format", "mp3").lower()

        _ensure_dirs()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = DATA_DIR / "audio" / f"voiceover_{ts}.{output_format}"

        try:
            import edge_tts

            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(out_path))
            return {"status": "success", "path": str(out_path), "voice": voice}
        except ImportError:
            return {"status": "error", "message": "edge-tts not installed. Run: pip install edge-tts"}
        except Exception as e:
            return {"status": "error", "message": f"Voiceover generation failed: {e}"}


class AssembleVideoTool(Tool):
    """Assemble a video from images + audio with transitions."""

    def __init__(self) -> None:
        super().__init__(
            name="assemble_video",
            description="Create a video from images with transitions, optional audio, and aspect ratio control",
            parameters={
                "images": {"type": "str", "description": "Comma-separated image paths"},
                "audio_path": {"type": "str", "description": "Path to audio file (optional)"},
                "duration_per_image": {"type": "int", "description": "Seconds per image (default: 5)"},
                "transitions": {
                    "type": "str",
                    "description": "Transition type: fade, zoom, ken_burns (default: ken_burns)",
                },
                "aspect_ratio": {"type": "str", "description": "Aspect ratio: 16:9, 9:16, 1:1 (default: 9:16)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        try:
            from moviepy import AudioFileClip, CompositeVideoClip, ImageClip, concatenate_videoclips
        except ImportError:
            return {"status": "error", "message": "moviepy not installed. Run: pip install moviepy"}

        images_str = kwargs.get("images", "")
        audio_path = kwargs.get("audio_path", "")
        duration_per_image = int(kwargs.get("duration_per_image", 5))
        transition = kwargs.get("transitions", "ken_burns").lower()
        aspect_ratio = kwargs.get("aspect_ratio", "9:16")

        image_paths = [p.strip() for p in images_str.split(",") if p.strip()]
        if not image_paths:
            return {"status": "error", "message": "No image paths provided"}

        for ip in image_paths:
            if not os.path.exists(ip):
                return {"status": "error", "message": f"Image not found: {ip}"}

        aspect_map = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}
        target_w, target_h = aspect_map.get(aspect_ratio, (1080, 1920))

        audio_clip = None
        if audio_path and os.path.exists(audio_path):
            audio_clip = AudioFileClip(audio_path)
            total_duration = audio_clip.duration
            duration_per_image = total_duration / len(image_paths)
        else:
            total_duration = duration_per_image * len(image_paths)

        clips = []
        for i, ip in enumerate(image_paths):
            clip = ImageClip(ip).with_duration(duration_per_image)
            clip = clip.resized((target_w, target_h))

            if transition == "ken_burns":
                start_scale = 1.0
                end_scale = 1.15
                clip = clip.resized(
                    lambda t, dur=duration_per_image: start_scale + (end_scale - start_scale) * (t / dur)
                )
            elif transition == "zoom":
                clip = clip.resized(lambda t, dur=duration_per_image: 1.0 + 0.3 * (t / dur))

            if transition == "fade" and i > 0:
                clip = clip.with_effects([]) if not hasattr(clip, "crossfadein") else clip

            clips.append(clip)

        if not clips:
            return {"status": "error", "message": "No clips created"}

        video = concatenate_videoclips(clips, method="compose")

        if audio_clip:
            video = video.with_audio(audio_clip)

        _ensure_dirs()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = str(DATA_DIR / "videos" / f"video_{ts}.mp4")
        video.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac", logger=None)

        video.close()
        if audio_clip:
            audio_clip.close()

        return {"status": "success", "path": out_path, "duration": total_duration, "aspect_ratio": aspect_ratio}


class AddSubtitlesTool(Tool):
    """Add subtitles to a video using whisper transcription."""

    def __init__(self) -> None:
        super().__init__(
            name="add_subtitles",
            description="Transcribe and burn subtitles into a video (uses faster-whisper)",
            parameters={
                "video_path": {"type": "str", "description": "Path to the video file"},
                "style": {
                    "type": "str",
                    "description": "Subtitle style: bottom-center or word-by-word (default: bottom-center)",
                },
                "font_size": {"type": "int", "description": "Subtitle font size (default: 36)"},
                "color": {"type": "str", "description": "Subtitle text color (default: white)"},
                "bg_color": {"type": "str", "description": "Subtitle background color (default: black)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        video_path = kwargs.get("video_path", "")
        if not video_path or not os.path.exists(video_path):
            return {"status": "error", "message": f"Video not found: {video_path}"}

        try:
            from moviepy import CompositeVideoClip, TextClip, VideoFileClip
        except ImportError:
            return {"status": "error", "message": "moviepy not installed. Run: pip install moviepy"}

        font_size = int(kwargs.get("font_size", 36))
        color = kwargs.get("color", "white")

        video = VideoFileClip(video_path)
        segments: list[dict] = []

        # Try transcription with faster-whisper
        try:
            from faster_whisper import WhisperModel

            model = WhisperModel("base", device="cpu", compute_type="int8")
            audio_path = video_path.replace(".mp4", "_temp_audio.wav")
            video.audio.write_audiofile(audio_path, logger=None)
            segs, _ = model.transcribe(audio_path)
            for seg in segs:
                segments.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
            try:
                os.remove(audio_path)
            except OSError:
                pass
        except ImportError:
            video.close()
            return {"status": "error", "message": "faster-whisper not installed. Run: pip install faster-whisper"}
        except Exception as e:
            video.close()
            return {"status": "error", "message": f"Transcription failed: {e}"}

        if not segments:
            video.close()
            return {"status": "error", "message": "No speech detected in video"}

        # Save SRT file
        p = Path(video_path)
        srt_path = p.parent / f"{p.stem}.srt"
        srt_lines = []
        for i, seg in enumerate(segments, 1):
            start_ts = _format_srt_time(seg["start"])
            end_ts = _format_srt_time(seg["end"])
            srt_lines.append(f"{i}\n{start_ts} --> {end_ts}\n{seg['text']}\n")
        srt_path.write_text("\n".join(srt_lines), encoding="utf-8")

        # Burn subtitles
        subtitle_clips = []
        for seg in segments:
            try:
                txt_clip = (
                    TextClip(
                        text=seg["text"],
                        font_size=font_size,
                        color=color,
                        bg_color="rgba(0,0,0,128)",
                        method="caption",
                        size=(video.w * 0.9, None),
                    )
                    .with_start(seg["start"])
                    .with_duration(seg["end"] - seg["start"])
                    .with_position(("center", 0.85), relative=True)
                )
                subtitle_clips.append(txt_clip)
            except Exception:
                continue

        if subtitle_clips:
            final = CompositeVideoClip([video, *subtitle_clips])
        else:
            final = video

        out_path = str(p.parent / f"{p.stem}_subtitled{p.suffix}")
        final.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
        final.close()
        video.close()

        return {"status": "success", "path": out_path, "srt_path": str(srt_path), "segments": len(segments)}


def _format_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class AddBackgroundMusicTool(Tool):
    """Add background music to a video."""

    def __init__(self) -> None:
        super().__init__(
            name="add_background_music",
            description="Mix background music into a video at adjustable volume",
            parameters={
                "video_path": {"type": "str", "description": "Path to the video file"},
                "music_path": {"type": "str", "description": "Path to the music file"},
                "volume": {"type": "float", "description": "Music volume 0.0-1.0 (default: 0.15)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        video_path = kwargs.get("video_path", "")
        music_path = kwargs.get("music_path", "")
        volume = float(kwargs.get("volume", 0.15))

        if not video_path or not os.path.exists(video_path):
            return {"status": "error", "message": f"Video not found: {video_path}"}
        if not music_path or not os.path.exists(music_path):
            return {"status": "error", "message": f"Music file not found: {music_path}"}

        try:
            from moviepy import AudioFileClip, CompositeAudioClip, VideoFileClip, afx
        except ImportError:
            return {"status": "error", "message": "moviepy not installed. Run: pip install moviepy"}

        video = VideoFileClip(video_path)
        music = AudioFileClip(music_path)

        if music.duration < video.duration:
            loops_needed = int(video.duration / music.duration) + 1
            from moviepy import concatenate_audioclips

            music = concatenate_audioclips([music] * loops_needed)
        music = music.subclipped(0, video.duration)
        music = music.with_volume_scaled(volume)

        if video.audio:
            final_audio = CompositeAudioClip([video.audio, music])
        else:
            final_audio = music

        final = video.with_audio(final_audio)
        p = Path(video_path)
        out_path = str(p.parent / f"{p.stem}_music{p.suffix}")
        final.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac", logger=None)

        final.close()
        video.close()
        music.close()

        return {"status": "success", "path": out_path, "volume": volume}


# ---------------------------------------------------------------------------
# Phase 4: Upload / Publishing Tools (9-11)
# ---------------------------------------------------------------------------


class UploadYouTubeTool(Tool):
    """Upload a video to YouTube via the Data API v3."""

    def __init__(self) -> None:
        super().__init__(
            name="upload_youtube",
            description="Upload a video to YouTube (requires OAuth credentials)",
            parameters={
                "video_path": {"type": "str", "description": "Path to the video file"},
                "title": {"type": "str", "description": "Video title"},
                "description": {"type": "str", "description": "Video description"},
                "tags": {"type": "str", "description": "Comma-separated tags"},
                "category": {"type": "str", "description": "YouTube category ID (default: 22 = People & Blogs)"},
                "privacy": {"type": "str", "description": "Privacy: public, unlisted, private (default: private)"},
                "thumbnail_path": {"type": "str", "description": "Path to custom thumbnail image (optional)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        video_path = kwargs.get("video_path", "")
        title = kwargs.get("title", "Untitled")
        description = kwargs.get("description", "")
        tags = kwargs.get("tags", "")
        category = kwargs.get("category", "22")
        privacy = kwargs.get("privacy", "private").lower()

        if not video_path or not os.path.exists(video_path):
            return {"status": "error", "message": f"Video not found: {video_path}"}

        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError:
            entry = {
                "platform": "youtube",
                "video_path": video_path,
                "title": title,
                "status": "pending_deps",
                "created": datetime.now().isoformat(),
            }
            _log_upload(entry)
            return {
                "status": "error",
                "message": "google-api-python-client not installed. Run: pip install google-api-python-client google-auth-oauthlib",
                "saved": True,
            }

        from config import settings

        creds_path = settings.media.youtube_credentials_path
        secrets_path = settings.media.youtube_client_secrets_path

        if not secrets_path or not os.path.exists(secrets_path):
            return {
                "status": "error",
                "message": "YouTube client_secret.json not configured. Set VERA_MEDIA_YOUTUBE_CLIENT_SECRETS_PATH",
            }

        creds = None
        if os.path.exists(creds_path):
            creds = Credentials.from_authorized_user_file(creds_path)

        if not creds or not creds.valid:
            scopes = ["https://www.googleapis.com/auth/youtube.upload"]
            flow = InstalledAppFlow.from_client_secrets_file(secrets_path, scopes)
            creds = flow.run_local_server(port=0)
            Path(creds_path).parent.mkdir(parents=True, exist_ok=True)
            Path(creds_path).write_text(creds.to_json(), encoding="utf-8")

        youtube = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tag_list,
                "categoryId": category,
            },
            "status": {"privacyStatus": privacy},
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = request.execute()

        video_id = response.get("id", "")
        entry = {
            "platform": "youtube",
            "video_id": video_id,
            "title": title,
            "url": f"https://youtube.com/watch?v={video_id}",
            "privacy": privacy,
            "created": datetime.now().isoformat(),
        }
        _log_upload(entry)

        return {"status": "success", "video_id": video_id, "url": entry["url"], "privacy": privacy}


class UploadInstagramTool(Tool):
    """Upload media to Instagram via the Graph API."""

    def __init__(self) -> None:
        super().__init__(
            name="upload_instagram",
            description="Upload a reel, post, or story to Instagram (requires Graph API token or browser automation)",
            parameters={
                "media_path": {"type": "str", "description": "Path to the image or video file"},
                "caption": {"type": "str", "description": "Post caption"},
                "hashtags": {"type": "str", "description": "Comma-separated hashtags"},
                "media_type": {"type": "str", "description": "Media type: reel, post, story (default: reel)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        media_path = kwargs.get("media_path", "")
        caption = kwargs.get("caption", "")
        hashtags = kwargs.get("hashtags", "")
        media_type = kwargs.get("media_type", "reel").lower()

        if not media_path or not os.path.exists(media_path):
            return {"status": "error", "message": f"Media not found: {media_path}"}

        tag_list = [t.strip().lstrip("#") for t in hashtags.split(",") if t.strip()] if hashtags else []
        full_caption = caption
        if tag_list:
            full_caption += "\n\n" + " ".join(f"#{t}" for t in tag_list)

        from config import settings

        access_token = settings.media.instagram_access_token or os.getenv("VERA_MEDIA_INSTAGRAM_ACCESS_TOKEN", "")

        if not access_token:
            entry = {
                "platform": "instagram",
                "media_path": media_path,
                "caption": full_caption[:200],
                "media_type": media_type,
                "status": "pending_token",
                "message": "Set VERA_MEDIA_INSTAGRAM_ACCESS_TOKEN for Graph API upload, or use browser agent as fallback.",
                "created": datetime.now().isoformat(),
            }
            _log_upload(entry)
            return {"status": "saved", "message": entry["message"], "entry": entry}

        import httpx

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                # Step 1: Create media container
                container_resp = await client.post(
                    "https://graph.facebook.com/v18.0/me/media",
                    data={
                        "caption": full_caption,
                        "media_type": "REELS" if media_type == "reel" else "IMAGE",
                        "access_token": access_token,
                    },
                )
                container_resp.raise_for_status()
                container_id = container_resp.json().get("id")

                # Step 2: Publish
                publish_resp = await client.post(
                    "https://graph.facebook.com/v18.0/me/media_publish",
                    data={"creation_id": container_id, "access_token": access_token},
                )
                publish_resp.raise_for_status()
                media_id = publish_resp.json().get("id", "")

                entry = {
                    "platform": "instagram",
                    "media_id": media_id,
                    "media_type": media_type,
                    "caption": full_caption[:200],
                    "status": "published",
                    "created": datetime.now().isoformat(),
                }
                _log_upload(entry)
                return {"status": "success", "media_id": media_id, "media_type": media_type}
        except Exception as e:
            return {"status": "error", "message": f"Instagram upload failed: {e}"}


class UploadTikTokTool(Tool):
    """Upload a video to TikTok via browser automation."""

    def __init__(self) -> None:
        super().__init__(
            name="upload_tiktok",
            description="Upload a video to TikTok (browser automation — TikTok API is restrictive)",
            parameters={
                "video_path": {"type": "str", "description": "Path to the video file"},
                "caption": {"type": "str", "description": "Video caption"},
                "hashtags": {"type": "str", "description": "Comma-separated hashtags"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        video_path = kwargs.get("video_path", "")
        caption = kwargs.get("caption", "")
        hashtags = kwargs.get("hashtags", "")

        if not video_path or not os.path.exists(video_path):
            return {"status": "error", "message": f"Video not found: {video_path}"}

        tag_list = [t.strip().lstrip("#") for t in hashtags.split(",") if t.strip()] if hashtags else []
        full_caption = caption
        if tag_list:
            full_caption += " " + " ".join(f"#{t}" for t in tag_list)

        entry = {
            "platform": "tiktok",
            "video_path": video_path,
            "caption": full_caption[:200],
            "status": "pending_browser",
            "message": "TikTok upload requires browser automation. Use BrowserAgent to navigate to tiktok.com/upload and complete the upload.",
            "created": datetime.now().isoformat(),
        }
        _log_upload(entry)

        return {
            "status": "saved",
            "message": entry["message"],
            "next_step": "Use the browser agent to automate TikTok upload at https://www.tiktok.com/upload",
            "entry": entry,
        }


# ---------------------------------------------------------------------------
# Phase 5: Pipeline Orchestrator (tool 12)
# ---------------------------------------------------------------------------


class CreateReelTool(Tool):
    """End-to-end reel/video creation pipeline."""

    def __init__(self) -> None:
        super().__init__(
            name="create_reel",
            description="Create a complete reel/short video end-to-end: research topic → generate images → voiceover → assemble video → subtitles → optional upload",
            parameters={
                "topic": {"type": "str", "description": "Topic for the reel"},
                "platform": {
                    "type": "str",
                    "description": "Target platform: youtube, instagram, tiktok, all (default: youtube)",
                },
                "style": {"type": "str", "description": "Content style: news, tutorial, motivational (default: news)"},
                "voice": {"type": "str", "description": "edge-tts voice (default: from config)"},
                "auto_upload": {"type": "bool", "description": "Auto-upload after creation (default: false)"},
                "num_scenes": {"type": "int", "description": "Number of image scenes to generate (default: 4)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        topic = kwargs.get("topic", "")
        if not topic:
            return {"status": "error", "message": "No topic provided"}

        platform = kwargs.get("platform", "youtube").lower()
        style = kwargs.get("style", "news").lower()
        auto_upload = kwargs.get("auto_upload", False)
        num_scenes = int(kwargs.get("num_scenes", 4))

        results: dict[str, Any] = {"topic": topic, "steps": []}

        # Step 1: Generate scene prompts based on topic
        style_prompts = {
            "news": [
                f"Breaking news headline about {topic}, dramatic cinematic lighting",
                f"Journalist reporting on {topic}, modern newsroom background",
                f"Data visualization infographic about {topic}, clean modern design",
                f"World map highlighting regions affected by {topic}, dramatic colors",
                f"People discussing {topic} in a conference, professional setting",
                f"Summary slide about {topic} with key takeaways, clean design",
            ],
            "tutorial": [
                f"Step 1 tutorial illustration for {topic}, clean flat design",
                f"Hands-on demonstration of {topic}, close-up detailed view",
                f"Diagram explaining {topic} concepts, educational style",
                f"Before and after comparison for {topic}, split screen",
                f"Tips and tricks for {topic}, colorful icons and text",
                f"Final result showcase of {topic}, professional finish",
            ],
            "motivational": [
                f"Inspiring sunrise landscape representing {topic}, golden hour",
                f"Person overcoming challenges related to {topic}, dramatic lighting",
                f"Motivational quote about {topic}, elegant typography",
                f"Success celebration related to {topic}, confetti and lights",
                f"Path forward representing {topic}, leading to bright future",
                f"Community coming together for {topic}, warm colors",
            ],
        }
        prompts = (style_prompts.get(style, style_prompts["news"]))[:num_scenes]

        # Step 2: Generate images
        gen_tool = GenerateImageTool()
        image_paths = []
        for i, prompt in enumerate(prompts):
            result = await gen_tool.execute(prompt=prompt, width=1080, height=1920, style="realistic")
            if result.get("status") == "success":
                image_paths.append(result["path"])
                results["steps"].append({"step": f"image_{i + 1}", "status": "success", "path": result["path"]})
            else:
                results["steps"].append({"step": f"image_{i + 1}", "status": "failed", "error": result.get("message")})

        if not image_paths:
            return {"status": "error", "message": "Failed to generate any images", "details": results}

        # Step 3: Generate script text for voiceover
        script_texts = {
            "news": f"Breaking news update on {topic}. Here's everything you need to know. Let's dive into the key points and what this means for you.",
            "tutorial": f"Welcome to this quick tutorial on {topic}. Follow along as I walk you through the essential steps. Let's get started!",
            "motivational": f"Today we're talking about {topic}. Remember, every great journey starts with a single step. You've got this!",
        }
        script = script_texts.get(style, script_texts["news"])

        # Step 4: Generate voiceover
        vo_tool = GenerateVoiceoverTool()
        voice = kwargs.get("voice", "")
        vo_result = await vo_tool.execute(text=script, voice=voice)
        audio_path = ""
        if vo_result.get("status") == "success":
            audio_path = vo_result["path"]
            results["steps"].append({"step": "voiceover", "status": "success", "path": audio_path})
        else:
            results["steps"].append({"step": "voiceover", "status": "failed", "error": vo_result.get("message")})

        # Step 5: Assemble video
        asm_tool = AssembleVideoTool()
        aspect = "9:16" if platform in ("instagram", "tiktok") else "16:9"
        asm_result = await asm_tool.execute(
            images=",".join(image_paths),
            audio_path=audio_path,
            transitions="ken_burns",
            aspect_ratio=aspect,
        )
        video_path = ""
        if asm_result.get("status") == "success":
            video_path = asm_result["path"]
            results["steps"].append({"step": "assemble_video", "status": "success", "path": video_path})
        else:
            results["steps"].append({"step": "assemble_video", "status": "failed", "error": asm_result.get("message")})
            return {"status": "partial", "message": "Video assembly failed", "details": results}

        # Step 6: Add subtitles
        sub_tool = AddSubtitlesTool()
        sub_result = await sub_tool.execute(video_path=video_path)
        if sub_result.get("status") == "success":
            video_path = sub_result["path"]
            results["steps"].append({"step": "subtitles", "status": "success", "path": video_path})
        else:
            results["steps"].append({"step": "subtitles", "status": "skipped", "reason": sub_result.get("message")})

        results["final_video"] = video_path

        # Step 7: Optional upload
        if auto_upload and video_path:
            platforms_to_upload = [platform] if platform != "all" else ["youtube", "instagram", "tiktok"]
            upload_tools = {
                "youtube": UploadYouTubeTool(),
                "instagram": UploadInstagramTool(),
                "tiktok": UploadTikTokTool(),
            }
            for plat in platforms_to_upload:
                tool = upload_tools.get(plat)
                if tool:
                    upload_kwargs: dict[str, Any] = {"video_path": video_path}
                    if plat == "youtube":
                        upload_kwargs.update(
                            {"title": f"{topic} | {style.title()}", "description": script, "privacy": "private"}
                        )
                    elif plat == "instagram":
                        upload_kwargs.update({"media_path": video_path, "caption": script[:200], "media_type": "reel"})
                    elif plat == "tiktok":
                        upload_kwargs.update({"caption": script[:150]})
                    up_result = await tool.execute(**upload_kwargs)
                    results["steps"].append(
                        {"step": f"upload_{plat}", "status": up_result.get("status"), "details": up_result}
                    )

        return {"status": "success", "details": results}


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class MediaFactoryAgent(BaseAgent):
    """Generates images, assembles videos, adds subtitles, and uploads to social platforms.

    The MediaFactory agent enables fully autonomous content creation:
    image generation → video assembly → subtitles → upload.
    """

    name = "media_factory"
    description = "Generates images, edits photos, assembles videos with transitions, adds subtitles, and uploads to YouTube/Instagram/TikTok"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a media production specialist. You help users create visual content end-to-end: "
        "generate images (Pollinations free / DALL-E premium), edit photos, assemble videos with "
        "Ken Burns transitions, add voiceovers and subtitles, and upload to YouTube, Instagram, and TikTok. "
        "For quick one-shot content, use create_reel to run the entire pipeline. "
        "For fine control, use individual tools step by step. "
        "Always confirm before uploading to social platforms."
    )

    offline_responses = {
        "image": "🖼️ I'll generate that image for you!",
        "video": "🎬 Let me assemble that video!",
        "reel": "📱 I'll create a reel for you!",
        "upload": "📤 I'll prepare the upload!",
        "subtitle": "💬 I'll add subtitles to your video!",
        "background": "✂️ I'll remove the background!",
        "voiceover": "🎙️ I'll generate a voiceover!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            GenerateImageTool(),
            EditImageTool(),
            AddTextOverlayTool(),
            RemoveBackgroundTool(),
            GenerateVoiceoverTool(),
            AssembleVideoTool(),
            AddSubtitlesTool(),
            AddBackgroundMusicTool(),
            UploadYouTubeTool(),
            UploadInstagramTool(),
            UploadTikTokTool(),
            CreateReelTool(),
        ]
