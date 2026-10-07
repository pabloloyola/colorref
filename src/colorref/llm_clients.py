"""LLM client abstraction for the ColorRef experiment pipeline.

Backends
--------
HFTransformersClient   load a HuggingFace model locally (GPU)
OpenAICompatibleClient call any OpenAI-compatible REST endpoint
MockLLMClient          deterministic stub for unit tests
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response dataclass
# ---------------------------------------------------------------------------

@dataclass
class LLMResponse:
    text: str
    raw: dict | None
    model_name: str
    provider: str
    latency_s: float | None
    error: str | None = None


def _hf_generation_diagnostics(new_ids, eos_token_id, max_tokens):
    """Describe observed tokens without claiming a backend-reported finish reason."""
    count = len(new_ids)
    eos_ids = [] if eos_token_id is None else (
        list(eos_token_id) if isinstance(eos_token_id, (list, tuple)) else [eos_token_id]
    )
    eos_reached = bool(count and int(new_ids[-1]) in eos_ids)
    limit_reached = count >= max_tokens
    return {
        "generated_tokens": count,
        "eos_reached": eos_reached,
        "token_limit_reached": limit_reached,
        "finish_reason": "eos" if eos_reached else "length" if limit_reached else None,
        "finish_reason_source": "observed_output_tokens",
    }


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class LLMClient:
    def generate(self, prompt: str, *, max_tokens: int, temperature: float) -> LLMResponse:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# HuggingFace Transformers backend
# ---------------------------------------------------------------------------

class HFTransformersClient(LLMClient):
    """Run a HuggingFace model locally using the transformers library.

    Suitable for Qwen3 instruct models (and similar chat models).

    Parameters
    ----------
    model_name_or_path:
        HF repo id (e.g. "Qwen/Qwen3-8B") or local path.
    hf_home:
        Override $HF_HOME so the correct cache is used.
    device_map:
        Passed to from_pretrained; "auto" spreads across available GPUs.
    torch_dtype:
        "auto", "bfloat16", "float16", or "float32".
    enable_thinking:
        Qwen3-specific; set False to suppress <think> tokens.
    alias:
        Human-readable name stored in LLMResponse.
    """

    def __init__(
        self,
        model_name_or_path: str,
        *,
        hf_home: str | None = None,
        device_map: str = "auto",
        torch_dtype: str = "bfloat16",
        enable_thinking: bool = False,
        alias: str | None = None,
    ) -> None:
        if hf_home:
            os.environ["HF_HOME"] = hf_home

        self.model_name = model_name_or_path
        self.alias = alias or model_name_or_path
        self.enable_thinking = enable_thinking
        self._model_and_tokenizer = self._load_model(device_map, torch_dtype)

    def _load_model(self, device_map: str, torch_dtype_str: str):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        dtype = dtype_map.get(torch_dtype_str, torch.bfloat16)

        logger.info("Loading model %s (device_map=%s, dtype=%s)…", self.model_name, device_map, torch_dtype_str)
        t0 = time.time()
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            dtype=dtype,
            device_map=device_map,
        )
        logger.info("Model loaded in %.1fs", time.time() - t0)
        return model, tokenizer

    def generate(self, prompt: str, *, max_tokens: int, temperature: float) -> LLMResponse:
        """Generate a response for the given prompt string.

        Uses model + tokenizer directly (not pipeline) so that
        apply_chat_template kwargs (e.g. enable_thinking) work correctly.
        """
        import torch

        model, tokenizer = self._model_and_tokenizer
        messages = [{"role": "user", "content": prompt}]

        # apply_chat_template: Qwen3 respects enable_thinking here
        template_kwargs: dict[str, Any] = {
            "tokenize": False,
            "add_generation_prompt": True,
        }
        try:
            # Qwen3 supports enable_thinking; older models silently ignore it
            text = tokenizer.apply_chat_template(
                messages,
                enable_thinking=self.enable_thinking,
                **template_kwargs,
            )
        except TypeError:
            text = tokenizer.apply_chat_template(messages, **template_kwargs)

        inputs = tokenizer([text], return_tensors="pt").to(model.device)

        gen_kwargs: dict[str, Any] = {"max_new_tokens": max_tokens}
        if temperature > 0.0:
            gen_kwargs["do_sample"] = True
            gen_kwargs["temperature"] = temperature
        else:
            gen_kwargs["do_sample"] = False

        t0 = time.time()
        try:
            with torch.no_grad():
                output_ids = model.generate(**inputs, **gen_kwargs)
            latency = time.time() - t0

            # Strip the input tokens; decode only the new tokens
            new_ids = output_ids[0][inputs.input_ids.shape[1]:]
            response_text = tokenizer.decode(new_ids, skip_special_tokens=True)
            # Includes any generated special/EOS token, unlike decoded text length.
            diagnostics = _hf_generation_diagnostics(
                new_ids, model.generation_config.eos_token_id, max_tokens
            )

            return LLMResponse(
                text=response_text.strip(),
                raw=diagnostics,
                model_name=self.model_name,
                provider="hf_transformers",
                latency_s=latency,
            )
        except Exception as exc:
            latency = time.time() - t0
            logger.warning("HF generate error: %s", exc)
            return LLMResponse(
                text="",
                raw=None,
                model_name=self.model_name,
                provider="hf_transformers",
                latency_s=latency,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# OpenAI-compatible REST backend
# ---------------------------------------------------------------------------

class OpenAICompatibleClient(LLMClient):
    """Call any OpenAI-compatible endpoint (LM Studio, vLLM, OpenAI, etc.)."""

    def __init__(
        self,
        model_name: str,
        base_url: str,
        *,
        api_key_env: str | None = None,
        api_key: str | None = None,
        alias: str | None = None,
        timeout_s: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.alias = alias or model_name
        self.timeout_s = timeout_s
        self.max_retries = max_retries

        if api_key is not None:
            self._api_key = api_key
        elif api_key_env:
            self._api_key = os.environ.get(api_key_env, "dummy-key")
        else:
            self._api_key = "dummy-key"

    def generate(self, prompt: str, *, max_tokens: int, temperature: float) -> LLMResponse:
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai package is required for OpenAICompatibleClient. Run: uv add openai")

        client = OpenAI(api_key=self._api_key, base_url=self.base_url + "/v1")
        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=self.timeout_s,
            )
            latency = time.time() - t0
            text = resp.choices[0].message.content or ""
            return LLMResponse(
                text=text.strip(),
                raw=resp.model_dump(),
                model_name=self.model_name,
                provider="openai_compatible",
                latency_s=latency,
            )
        except Exception as exc:
            latency = time.time() - t0
            logger.warning("OpenAI call error: %s", exc)
            return LLMResponse(
                text="",
                raw=None,
                model_name=self.model_name,
                provider="openai_compatible",
                latency_s=latency,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Mock client (for tests)
# ---------------------------------------------------------------------------

class MockLLMClient(LLMClient):
    """Returns a fixed response string. Useful for unit tests."""

    def __init__(self, fixed_response: str = "#ff0000") -> None:
        self.fixed_response = fixed_response
        self.model_name = "mock"
        self.alias = "mock"

    def generate(self, prompt: str, *, max_tokens: int, temperature: float) -> LLMResponse:
        return LLMResponse(
            text=self.fixed_response,
            raw=None,
            model_name="mock",
            provider="mock",
            latency_s=0.0,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_client(cfg: dict) -> LLMClient:
    """Build the right LLMClient from a model config dict.

    Supported provider values:
        "hf_transformers"    – HFTransformersClient
        "openai_compatible"  – OpenAICompatibleClient
        "mock"               – MockLLMClient
    """
    provider = cfg.get("provider", "hf_transformers")

    if provider == "hf_transformers":
        return HFTransformersClient(
            model_name_or_path=cfg["model_name"],
            hf_home=cfg.get("hf_home"),
            device_map=cfg.get("device_map", "auto"),
            torch_dtype=cfg.get("torch_dtype", "bfloat16"),
            enable_thinking=cfg.get("enable_thinking", False),
            alias=cfg.get("alias"),
        )

    if provider == "openai_compatible":
        return OpenAICompatibleClient(
            model_name=cfg["model_name"],
            base_url=cfg["base_url"],
            api_key_env=cfg.get("api_key_env"),
            alias=cfg.get("alias"),
            timeout_s=cfg.get("timeout_s", 60.0),
            max_retries=cfg.get("max_retries", 2),
        )

    if provider == "mock":
        return MockLLMClient(fixed_response=cfg.get("fixed_response", "#aabbcc"))

    raise ValueError(f"Unknown provider: {provider!r}")
