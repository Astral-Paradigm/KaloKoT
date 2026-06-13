"""ElevenLabs Text-to-Speech for the Digital Lawyer.

Optimised for low latency:
- Uses eleven_turbo_v2 model (fastest ElevenLabs model)
- LRU in-memory cache for repeated phrases
- Connection pooling via requests.Session()
- Pre-warms on module load
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
from collections import OrderedDict
from functools import lru_cache
from io import BytesIO
from typing import Optional

import requests


def clean_for_tts(text: str) -> str:
    """Remove markdown and formatting artifacts before TTS."""
    # Bold/italic (must come first — order matters)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    # Links: [text](url) → text
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    # Code backticks
    text = re.sub(r"`(.*?)`", r"\1", text)
    # Headers
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    # Horizontal rules
    text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)
    # Remaining bare asterisks (bullet points, stray markers)
    text = text.replace("*", "")
    # Excess whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ElevenLabs male voice IDs (natural, authoritative)
MALE_VOICE_ID = "1SM7GgM6IMuvQlz2BwM3"
ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"

# ── LRU Cache ─────────────────────────────────────────────────────────────

MAX_CACHE_ITEMS = 128


class TTSCache:
    """Thread-safe LRU cache for TTS audio responses.

    Key is MD5 of the input text — identical requests return instantly
    without calling ElevenLabs again.
    """

    def __init__(self, maxsize: int = MAX_CACHE_ITEMS):
        self._lock = threading.Lock()
        self._maxsize = maxsize
        self._cache: OrderedDict[str, bytes] = OrderedDict()

    def _key(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[bytes]:
        key = self._key(text)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def put(self, text: str, data: bytes):
        key = self._key(text)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = data
            while len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)


# Shared cache + session (module-level)
_tts_cache = TTSCache()
_session = requests.Session()
# Keep-alive for connection reuse
_session.headers.update({
    "Accept": "audio/mpeg",
    "Content-Type": "application/json",
})


def speak_text(
    text: str,
    api_key: str | None = None,
    voice_id: str = MALE_VOICE_ID,
    stability: float = 0.4,
    similarity_boost: float = 0.75,
) -> Optional[BytesIO]:
    """Convert text to speech using ElevenLabs (turbo model, cached).

    Optimisation layers (in order):
    1. LRU cache hit → return instantly (no network call)
    2. Connection pool → reuse HTTP socket (no TCP handshake)
    3. eleven_turbo_v2 → faster inference on ElevenLabs side
    4. Reduced timeout → fail fast if network is slow

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

    # 1. Check cache
    cached = _tts_cache.get(text)
    if cached is not None:
        buf = BytesIO(cached)
        buf.seek(0)
        return buf

    # 2. Fetch from ElevenLabs (retry once on transient errors)
    import logging, time as _time
    headers = {"xi-api-key": key}
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": 0.25,
            "use_speaker_boost": True,
        },
    }
    for attempt in range(2):
        try:
            resp = _session.post(
                f"{ELEVENLABS_BASE}/text-to-speech/{voice_id}",
                headers=headers,
                json=payload,
                timeout=15,
            )
            if resp.status_code != 200:
                logging.error(f"[TTS] ElevenLabs HTTP {resp.status_code}: {resp.text[:200]}")
                if resp.status_code in (429, 503, 500) and attempt == 0:
                    _time.sleep(1.5)
                    continue
                return None
            resp.raise_for_status()
        except Exception:
            if attempt == 0:
                _time.sleep(1.5)
                continue
            return None

        # Validate response: must be audio/mpeg and at least 1KB
        content_type = resp.headers.get("Content-Type", "")
        if "audio/mpeg" not in content_type:
            return None
        raw = resp.content
        if len(raw) < 1024:
            return None

        # 3. Cache the raw bytes
        _tts_cache.put(text, raw)
        buf = BytesIO(raw)
        buf.seek(0)
        return buf

    return None


# ── Pre-warm ──────────────────────────────────────────────────────────────

_WARMED = False
_warm_lock = threading.Lock()


def warm_tts(api_key: str | None = None):
    """Send a tiny warm-up request so the first real TTS call is faster.

    ElevenLabs' edge infra often has cold-start latency on the first request.
    This primes the connection pool and the model inference pipeline.
    Runs once; idempotent.
    """
    global _WARMED
    if _WARMED:
        return
    with _warm_lock:
        if _WARMED:
            return
        key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            return
        try:
            # Tiny, near-silent phrase that warms the voice model
            speak_text(".", api_key=key)
        except Exception:
            pass  # warm-up is best-effort
        _WARMED = True


# Auto-warm on import (runs in a background thread so it doesn't block startup)
_threading = threading.Thread(target=warm_tts, daemon=True)
_threading.start()
