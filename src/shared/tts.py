"""ElevenLabs Text-to-Speech for the Digital Lawyer.

Uses a deep male voice model suitable for a legal counsel persona.
"""

from __future__ import annotations

import os
import requests
from io import BytesIO
from typing import Optional

# ElevenLabs male voice IDs (deep, authoritative)
# "Adam" — deep, authoritative male voice
MALE_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # Adam (deep, authoritative)

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"


def speak_text(
    text: str,
    api_key: str | None = None,
    voice_id: str = MALE_VOICE_ID,
    stability: float = 0.4,
    similarity_boost: float = 0.75,
) -> Optional[BytesIO]:
    """Convert text to speech using ElevenLabs.

    Args:
        text: Text to speak.
        api_key: ElevenLabs API key. Falls back to ELEVENLABS_API_KEY env var.
        voice_id: ElevenLabs voice ID. Defaults to "Adam" (male).
        stability: Voice stability 0.0–1.0.
        similarity_boost: Voice similarity 0.0–1.0.

    Returns:
        BytesIO with MP3 audio data, or None on failure.
    """
    key = api_key or os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        return None

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": key,
    }

    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": 0.25,
            "use_speaker_boost": True,
        },
    }

    try:
        resp = requests.post(
            f"{ELEVENLABS_BASE}/text-to-speech/{voice_id}",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        buf = BytesIO(resp.content)
        buf.seek(0)
        return buf
    except Exception:
        return None
