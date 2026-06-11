"""LLM client wrapper for OpenTender + Counsel.

Supports multiple providers with a unified interface.
"""

from __future__ import annotations

import os
import json
from typing import Optional

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


class LLMClient:
    """Unified LLM client that can switch between providers."""

    def __init__(self, provider: str = "gemini", model: Optional[str] = None):
        self.provider = provider
        self.model = model

        if provider == "gemini":
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError(
                    "GEMINI_API_KEY not set. Set it in .env or pass via env var."
                )
            if not HAS_GEMINI:
                raise ImportError("google-generativeai not installed. Run: pip install google-generativeai")
            genai.configure(api_key=api_key)
            self.model_name = model or "gemini-2.5-flash"
            self.client = genai.GenerativeModel(self.model_name)

        elif provider == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set.")
            try:
                import anthropic
            except ImportError:
                raise ImportError("anthropic not installed. Run: pip install anthropic")
            self.model_name = model or "claude-sonnet-4-20250514"
            self.client = anthropic.Anthropic(api_key=api_key)

        elif provider == "openrouter":
            self._setup_openrouter(model)
        else:
            raise ValueError(f"Unknown provider: {provider}. Use gemini, anthropic, or openrouter.")

    def _setup_openrouter(self, model: Optional[str] = None):
        self.model_name = model or "anthropic/claude-sonnet-4"
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not set.")
        try:
            import requests
        except ImportError:
            raise ImportError("requests not installed.")
        self._api_key = api_key
        self._http_session = requests.Session()
        self.provider = "openrouter"

    def generate(self, system_prompt: str, user_prompt: str,
                 temperature: float = 0.3, max_tokens: int = 4096) -> str:
        """Send a prompt and get a text response."""
        if self.provider == "gemini":
            response = self.client.generate_content(
                f"{system_prompt}\n\n{user_prompt}",
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            return response.text if hasattr(response, "text") else str(response)

        elif self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text

        elif self.provider == "openrouter":
            import requests
            resp = self._http_session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

        raise ValueError(f"Unhandled provider: {self.provider}")

    def generate_structured(self, system_prompt: str, user_prompt: str,
                            output_schema: dict, temperature: float = 0.1) -> dict:
        """Send a prompt and get a structured JSON response according to schema."""
        if self.provider == "gemini":
            model = genai.GenerativeModel(
                self.model_name,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=output_schema,
                ),
            )
            response = model.generate_content(
                f"{system_prompt}\n\n{user_prompt}"
            )
            if hasattr(response, "text"):
                return json.loads(response.text)
            return json.loads(str(response))

        else:
            # Non-Gemini providers: ask for JSON in system prompt
            enhanced_prompt = f"{system_prompt}\n\nCRITICAL: You MUST respond with valid JSON matching this schema:\n{json.dumps(output_schema, indent=2)}"
            result = self.generate(enhanced_prompt, user_prompt, temperature=temperature)
            # Extract JSON from response
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1]
                result = result.rsplit("\n", 1)[0]
            if result.startswith("```json"):
                result = result[7:]
                result = result.rsplit("```", 1)[0]
            return json.loads(result.strip())
