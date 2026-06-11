"""LLM client wrapper for OpenTender + Counsel.

Supports multiple providers with a unified interface.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


_DEFAULT_PHI_MODEL = "microsoft/Phi-3-mini-4k-instruct"


class LLMClient:
    """Unified LLM client that can switch between providers."""

    def __init__(self, provider: str = "gemini", model: Optional[str] = None,
                 quantize: Optional[str] = None):
        self.provider = provider
        self.model = model
        self.quantize = quantize

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
        elif provider == "phi":
            self._setup_phi(model)
        else:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Use gemini, anthropic, openrouter, or phi."
            )

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

        quant = self.quantize or os.environ.get("PHI_QUANTIZE", "4bit")
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
                print("  [phi] bitsandbytes not available — falling back to 8-bit via PyTorch")
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

        elif self.provider == "phi":
            combined = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
            return self._phi_generate(combined, temperature, max_tokens)

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
