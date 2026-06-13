"""LLM client wrapper for OpenTender + Counsel.

Supports multiple providers with a unified interface.
"""

from __future__ import annotations

import json
import os
import re
import time
from functools import wraps
from typing import Optional, Any

try:
    from google import genai
    from google.genai import types as genai_types
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


_DEFAULT_PHI_MODEL = "microsoft/Phi-3-mini-4k-instruct"


def retry_on_error(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for exponential backoff retry on LLM calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(delay * (backoff ** attempt))
        return wrapper
    return decorator


class LLMClient:
    """Unified LLM client that can switch between providers."""

    def __init__(self, provider: str = "gemini", model: Optional[str] = None,
                 quantize: Optional[str] = None, api_key: Optional[str] = None):
        # Try loading .env from project root
        try:
            from dotenv import load_dotenv
            import sys
            for p in (os.getcwd(), os.path.dirname(os.path.abspath(__file__)),
                      os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")):
                dotenv_path = os.path.join(p, ".env")
                if os.path.isfile(dotenv_path):
                    load_dotenv(dotenv_path)
                    break
        except ImportError:
            pass
        self.provider = provider
        self.model = model
        self.quantize = quantize

        if provider == "gemini":
            key = api_key or os.environ.get("GEMINI_API_KEY")
            if not key:
                raise ValueError(
                    "GEMINI_API_KEY not set. Set it in .env or pass via env var."
                )
            if not HAS_GEMINI:
                raise ImportError("google-genai not installed. Run: pip install google-genai")
            self._gemini_client = genai.Client(
                api_key=key,
                http_options={"timeout": 120_000},  # 120s — generous for multi-page analysis
            )
            self.model_name = model or "gemini-2.5-flash"

        elif provider == "anthropic":
            key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise ValueError("ANTHROPIC_API_KEY not set.")
            try:
                import anthropic
            except ImportError:
                raise ImportError("anthropic not installed. Run: pip install anthropic")
            self.model_name = model or "claude-sonnet-4-20250514"
            self.client = anthropic.Anthropic(api_key=key)

        elif provider == "openrouter":
            self._setup_openrouter(model, api_key=api_key)
        elif provider == "openai":
            self._setup_openai(model, api_key=api_key)
        elif provider == "phi":
            self._setup_phi(model)
        else:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Use gemini, anthropic, openrouter, openai, or phi."
            )

    def _setup_openrouter(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model_name = model or "anthropic/claude-sonnet-4"
        key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise ValueError("OPENROUTER_API_KEY not set.")
        try:
            import requests
        except ImportError:
            raise ImportError("requests not installed.")
        self._api_key = key
        self._http_session = requests.Session()
        self.provider = "openrouter"

    # ------------------------------------------------------------------
    # OpenAI-compatible API (OpenAI, any OpenAI-compatible proxy)
    # ------------------------------------------------------------------

    def _setup_openai(self, model: Optional[str] = None, api_key: Optional[str] = None):
        """Configure the OpenAI client (works with any OpenAI-compatible endpoint)."""
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY not set. Set it in .env or pass via env var.")
        self.model_name = model or os.environ.get("LLM_DEFAULT_MODEL", "gpt-4o-mini")
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai not installed. Run: pip install openai")
        self._openai_client = OpenAI(api_key=key)
        self.provider = "openai"

    # ------------------------------------------------------------------
    # Microsoft Phi (local, transformers)
    # ------------------------------------------------------------------

    def _setup_phi(self, model: Optional[str] = None):
        """Load a Microsoft Phi model via ``transformers`` with optional quantization."""
        self.model_name = model or _DEFAULT_PHI_MODEL
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError:
            raise ImportError(
                "transformers / torch not installed. Run: pip install transformers torch"
            )

        tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, trust_remote_code=True,
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        load_kwargs = {
            "trust_remote_code": True,
            "device_map": "auto",
            "low_cpu_mem_usage": True,
        }

        quant = self.quantize or os.environ.get("PHI_QUANTIZE", "")
        if quant == "4bit":
            try:
                from transformers import BitsAndBytesConfig
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
            except ImportError:
                load_kwargs["torch_dtype"] = torch.float16
        elif quant == "8bit":
            try:
                from transformers import BitsAndBytesConfig
                load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
            except ImportError:
                load_kwargs["torch_dtype"] = torch.float16
        else:
            load_kwargs["torch_dtype"] = torch.float32

        self._tokenizer = tokenizer
        self._phi_model = AutoModelForCausalLM.from_pretrained(
            self.model_name, **load_kwargs,
        )
        self._phi_device = next(self._phi_model.parameters()).device
        print(f"  [phi] Loaded {self.model_name} on {self._phi_device}")

    def _phi_generate(self, prompt: str, temperature: float = 0.3,
                      max_tokens: int = 2048) -> str:
        """Run local inference through the Phi model."""
        import torch

        messages = [{"role": "user", "content": prompt}]
        if hasattr(self._tokenizer, "apply_chat_template"):
            input_text = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )
        else:
            input_text = prompt

        inputs = self._tokenizer(input_text, return_tensors="pt",
                                 truncation=True, max_length=4096)
        inputs = {k: v.to(self._phi_device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._phi_model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
                pad_token_id=self._tokenizer.pad_token_id,
                eos_token_id=self._tokenizer.eos_token_id,
            )

        full = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Strip input from output
        if hasattr(self._tokenizer, "apply_chat_template"):
            prompt_len = len(self._tokenizer.decode(inputs["input_ids"][0],
                                                     skip_special_tokens=True))
            answer = full[prompt_len:].strip()
        else:
            answer = full[len(input_text):].strip()
        return answer

    @staticmethod
    def _extract_json(text: str) -> str:
        """Strip markdown fences and leading/trailing noise to extract pure JSON."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]
        if text.startswith("```json"):
            text = text[7:]
            text = text.rsplit("```", 1)[0]
        return text.strip()

    def generate(self, system_prompt: str, user_prompt: str,
                 temperature: float = 0.3, max_tokens: int = 4096) -> str:
        """Send a prompt and get a text response."""
        @retry_on_error(max_retries=3, delay=1.0, backoff=2.0)
        def _call() -> str:
            if self.provider == "gemini":
                combined = f"{system_prompt}\n\n{user_prompt}"
                response = self._gemini_client.models.generate_content(
                    model=self.model_name,
                    contents=combined,
                    config=genai_types.GenerateContentConfig(
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

            elif self.provider == "openai":
                resp = self._openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content

            elif self.provider == "phi":
                combined = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
                return self._phi_generate(combined, temperature, max_tokens)

            raise ValueError(f"Unhandled provider: {self.provider}")

        return _call()

    def generate_structured(self, system_prompt: str, user_prompt: str,
                            output_schema: dict, temperature: float = 0.1) -> dict:
        """Send a prompt and get a structured JSON response according to schema."""
        @retry_on_error(max_retries=3, delay=1.0, backoff=2.0)
        def _call() -> dict:
            if self.provider == "gemini":
                combined = f"{system_prompt}\n\n{user_prompt}"
                response = self._gemini_client.models.generate_content(
                    model=self.model_name,
                    contents=combined,
                    config=genai_types.GenerateContentConfig(
                        temperature=temperature,
                        response_mime_type="application/json",
                        response_schema=output_schema,
                    ),
                )
                if hasattr(response, "text") and response.text:
                    return json.loads(response.text)
                return json.loads(str(response))

            elif self.provider == "phi":
                schema_instruction = (
                    f"{system_prompt}\n\n"
                    f"CRITICAL: You MUST respond with valid JSON matching this schema:\n"
                    f"{json.dumps(output_schema, indent=2)}\n\n"
                    f"Respond with ONLY the JSON object. No markdown, no explanation."
                )
                combined = f"{schema_instruction}\n\n{user_prompt}"
                result = self._phi_generate(combined, temperature, max_tokens=2048)
                result = self._extract_json(result)
                return json.loads(result)

            else:
                # Non-Gemini providers: ask for JSON in system prompt
                enhanced_prompt = f"{system_prompt}\n\nCRITICAL: You MUST respond with valid JSON matching this schema:\n{json.dumps(output_schema, indent=2)}"
                result = self.generate(enhanced_prompt, user_prompt, temperature=temperature)
                result = self._extract_json(result)
                return json.loads(result.strip())

        return _call()

    # ── Vision / OCR ─────────────────────────────────────────────────────────────

    def extract_text_from_image(self, image_data: bytes, mime_type: str = "image/png") -> str:
        """Extract text from an image using Gemini vision (OCR).

        Only works with the 'gemini' provider.
        """
        if self.provider != "gemini":
            raise ValueError("Image OCR is only available with the 'gemini' provider")

        import base64

        img_part = genai_types.Part.from_bytes(
            data=image_data,
            mime_type=mime_type,
        )

        response = self._gemini_client.models.generate_content(
            model=self.model_name,
            contents=[
                "Extract all text from this tender document image. "
                "Return ONLY the extracted text as plain text — no commentary, "
                "no markdown, no formatting. Preserve the original language and "
                "as much layout information (paragraphs, sections, numbers) as possible.",
                img_part,
            ],
            config=genai_types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8192,
            ),
        )

        return response.text if hasattr(response, "text") else str(response)

    # ── Vision / OCR ─────────────────────────────────────────────────────────────


# ── Fallback LLM Client ─────────────────────────────────────────────────────────


class FallbackLLMClient:
    """LLM client that automatically falls back to alternative providers on rate limits."""

    def __init__(
        self,
        primary: str,
        fallbacks: list[str],
        model: Optional[str] = None,
        phi_model: Optional[str] = None,
    ):
        self.primary = primary
        self.fallbacks = fallbacks
        self.model = model
        self.phi_model = phi_model
        self._clients: dict[str, LLMClient] = {}
        self._init_clients()

    def _init_clients(self):
        """Initialize all available clients."""
        all_providers = [self.primary] + self.fallbacks
        for p in all_providers:
            try:
                if p == "gemini" and os.environ.get("GEMINI_API_KEY"):
                    self._clients[p] = LLMClient(provider="gemini", model=self.model or "gemini-2.5-flash")
                elif p == "openrouter" and os.environ.get("OPENROUTER_API_KEY"):
                    self._clients[p] = LLMClient(provider="openrouter", model=self.model or "anthropic/claude-sonnet-4")
                elif p == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
                    self._clients[p] = LLMClient(provider="anthropic", model=self.model or "claude-sonnet-4-20250514")
                elif p == "openai" and os.environ.get("OPENAI_API_KEY"):
                    self._clients[p] = LLMClient(provider="openai", model=self.model or "gpt-4o-mini")
                elif p == "phi":
                    self._clients[p] = LLMClient(provider="phi", model=self.phi_model or _DEFAULT_PHI_MODEL)
            except Exception as e:
                print(f"[FallbackLLM] Failed to initialize {p}: {e}")

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if error is a rate limit / quota exhausted error."""
        error_str = str(error).lower()
        return any(
            keyword in error_str
            for keyword in [
                "429",
                "rate limit",
                "quota exhausted",
                "resource exhausted",
                "too many requests",
                "rate_limit",
            ]
        )

    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.3, max_tokens: int = 4096) -> str:
        """Try primary provider, fall back on rate limit errors."""
        providers = [self.primary] + self.fallbacks
        last_error = None

        for p in providers:
            client = self._clients.get(p)
            if not client:
                continue
            try:
                return client.generate(system_prompt, user_prompt, temperature, max_tokens)
            except Exception as e:
                last_error = e
                if self._is_rate_limit_error(e):
                    print(f"[FallbackLLM] {p} rate limited, trying next provider...")
                    continue
                # Non-rate-limit error - re-raise
                raise

        # All providers failed
        raise last_error or RuntimeError("No LLM providers available")

    def generate_structured(self, system_prompt: str, user_prompt: str, output_schema: dict, temperature: float = 0.1) -> dict:
        """Try primary provider, fall back on rate limit errors."""
        providers = [self.primary] + self.fallbacks
        last_error = None

        for p in providers:
            client = self._clients.get(p)
            if not client:
                continue
            try:
                return client.generate_structured(system_prompt, user_prompt, output_schema, temperature)
            except Exception as e:
                last_error = e
                if self._is_rate_limit_error(e):
                    print(f"[FallbackLLM] {p} rate limited (structured), trying next provider...")
                    continue
                raise

        raise last_error or RuntimeError("No LLM providers available")

    def extract_text_from_image(self, image_data: bytes, mime_type: str = "image/png") -> str:
        """Extract text from an image using the primary provider's vision capabilities."""
        # Only Gemini supports vision/OCR currently
        for p in [self.primary] + self.fallbacks:
            client = self._clients.get(p)
            if not client:
                print(f"[FallbackLLM] No client for provider: {p}")
                continue
            if client.provider == "gemini":
                try:
                    return client.extract_text_from_image(image_data, mime_type)
                except Exception as e:
                    print(f"[FallbackLLM] Gemini vision failed: {e}")
                    continue
            else:
                print(f"[FallbackLLM] Provider {p} ({client.provider}) doesn't support vision")
        available = [p for p, c in self._clients.items() if c.provider == "gemini"]
        raise RuntimeError(
            f"No Gemini provider available for image OCR. "
            f"Available Gemini clients: {available}. "
            f"Set GEMINI_API_KEY and ensure google-genai is installed."
        )


def create_fallback_llm(
    primary: str,
    fallbacks: list[str],
    model: Optional[str] = None,
    phi_model: Optional[str] = None,
) -> Any:
    """Create a FallbackLLMClient with primary and fallback providers."""
    client = FallbackLLMClient(primary=primary, fallbacks=fallbacks, model=model, phi_model=phi_model)
    return client if client._clients else None


def create_llm_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    phi_model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Optional[LLMClient]:
    """Create an LLMClient by trying providers in a consistent priority order.

    This replaces the separate `get_llm` in main.py and `_get_llm` in api.py
    to ensure consistent behavior across CLI, Gradio UI, and FastAPI server.

    Priority order:
      1. Explicit `provider` argument (e.g., "phi", "openai", "gemini", etc.)
      2. LLM_DEFAULT_PROVIDER env var + corresponding API key
      3. GEMINI_API_KEY
      4. OPENROUTER_API_KEY
      5. ANTHROPIC_API_KEY
      6. OPENAI_API_KEY (if LLM_DEFAULT_PROVIDER=openai)
      7. None

    Args:
        provider: Explicit provider name to use (overrides env var).
        model: Model name for non-Phi providers.
        phi_model: Model name for Phi provider.
        api_key: Optional API key. Passed directly to LLMClient instead of env var.

    Returns:
        LLMClient instance or None if no provider can be initialized.
    """
    # 1. Explicit provider argument
    if provider:
        if provider == "phi":
            return LLMClient(provider="phi", model=phi_model)
        if provider == "openai":
            if api_key or os.environ.get("OPENAI_API_KEY"):
                return LLMClient(provider="openai", model=model or "gpt-4o-mini", api_key=api_key)
            return None
        if provider == "gemini":
            if api_key or os.environ.get("GEMINI_API_KEY"):
                return LLMClient(provider="gemini", model=model or "gemini-2.5-flash", api_key=api_key)
            return None
        if provider == "openrouter":
            if api_key or os.environ.get("OPENROUTER_API_KEY"):
                return LLMClient(provider="openrouter", model=model or "anthropic/claude-sonnet-4", api_key=api_key)
            return None
        if provider == "anthropic":
            if api_key or os.environ.get("ANTHROPIC_API_KEY"):
                return LLMClient(provider="anthropic", model=model or "claude-sonnet-4-20250514", api_key=api_key)
            return None
        # Explicit provider requested but key missing
        return None

    # 2. LLM_DEFAULT_PROVIDER env var
    default_provider = os.environ.get("LLM_DEFAULT_PROVIDER", "").lower()
    if default_provider == "openai" and os.environ.get("OPENAI_API_KEY"):
        return create_fallback_llm(
            primary="openai",
            fallbacks=["anthropic", "gemini", "openrouter"],
            model=model or "gpt-4o-mini",
        )
    if default_provider == "gemini" and os.environ.get("GEMINI_API_KEY"):
        return create_fallback_llm(
            primary="gemini",
            fallbacks=["openrouter", "anthropic", "openai"],
            model=model or "gemini-2.5-flash",
        )
    if default_provider == "openrouter" and os.environ.get("OPENROUTER_API_KEY"):
        return create_fallback_llm(
            primary="openrouter",
            fallbacks=["anthropic", "gemini", "openai"],
            model=model or "anthropic/claude-sonnet-4",
        )
    if default_provider == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        return create_fallback_llm(
            primary="anthropic",
            fallbacks=["gemini", "openrouter", "openai"],
            model=model or "claude-sonnet-4-20250514",
        )
    if default_provider == "phi":
        return LLMClient(provider="phi", model=phi_model)

    # 3. Auto-detect from available API keys (priority order)
    if os.environ.get("GEMINI_API_KEY"):
        return create_fallback_llm(
            primary="gemini",
            fallbacks=["openrouter", "anthropic", "openai"],
            model=model or "gemini-2.5-flash",
        )
    if os.environ.get("OPENROUTER_API_KEY"):
        return create_fallback_llm(
            primary="openrouter",
            fallbacks=["anthropic", "gemini", "openai"],
            model=model or "anthropic/claude-sonnet-4",
        )
    if os.environ.get("ANTHROPIC_API_KEY"):
        return create_fallback_llm(
            primary="anthropic",
            fallbacks=["gemini", "openrouter", "openai"],
            model=model or "claude-sonnet-4-20250514",
        )
    if os.environ.get("OPENAI_API_KEY"):
        return LLMClient(provider="openai", model=model or "gpt-4o-mini")

    return None
