"""Normalized identities and interface metadata for experiment artifacts."""

from __future__ import annotations

from typing import Any

from colorref.games import SUPPORTED_OUTPUT_SPACES


def output_space_from_config(cfg: dict[str, Any]) -> str:
    """Return and validate the configured guesser output space.

    Configurations predating the direct-LAB control default to ``hex`` so the
    archived experiments remain reproducible.
    """
    output_space = str(cfg.get("interface", {}).get("output_space", "hex")).lower()
    if output_space not in SUPPORTED_OUTPUT_SPACES:
        raise ValueError(
            f"Unsupported interface.output_space={output_space!r}; "
            f"expected one of {sorted(SUPPORTED_OUTPUT_SPACES)}"
        )
    return output_space


def model_identity(model_cfg: dict[str, Any]) -> dict[str, Any]:
    """Extract the stable model fields that should accompany every run."""
    return {
        "alias": model_cfg.get("alias"),
        "model_name": model_cfg.get("model_name"),
        "provider": model_cfg.get("provider"),
    }


def teacher_identity(
    teacher_cfg: dict[str, Any],
    guesser_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Describe both deterministic and model-backed teachers explicitly."""
    teacher_type = str(teacher_cfg.get("type", "minimal_oracle"))
    is_llm = teacher_type.startswith("llm_teacher")
    teacher_model_cfg = teacher_cfg.get("model", {}) if is_llm else {}
    teacher_model = model_identity(teacher_model_cfg)
    guesser_model = model_identity(guesser_cfg)
    shares_guesser = bool(
        is_llm
        and teacher_model["model_name"]
        and teacher_model["model_name"] == guesser_model["model_name"]
        and teacher_model["provider"] == guesser_model["provider"]
    )
    return {
        "type": teacher_type,
        "kind": "llm" if is_llm else "deterministic",
        **teacher_model,
        "shares_guesser_model": shares_guesser,
    }


def interface_identity(cfg: dict[str, Any]) -> dict[str, Any]:
    """Describe how native predictions are parsed, scored, and projected."""
    output_space = output_space_from_config(cfg)
    if output_space == "lab":
        return {
            "output_space": "lab",
            "output_format": "LAB(L, a, b)",
            "parser": "extract_lab",
            "evaluation_space": "lab",
            "evaluation_uses_native_output": True,
            "display_projection": "clipped_srgb_from_lab",
            "lab_bounds": {
                "l": [0.0, 100.0],
                "a": [-128.0, 127.0],
                "b": [-128.0, 127.0],
            },
        }
    return {
        "output_space": "hex",
        "output_format": "#RRGGBB",
        "parser": "extract_hex",
        "evaluation_space": "lab",
        "evaluation_uses_native_output": False,
        "display_projection": None,
    }
