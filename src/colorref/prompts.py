"""Prompt rendering for the ColorRef experiment pipeline.

Templates use Python str.format() placeholders: {raw_name}, {feedback}, etc.
"""

from __future__ import annotations

from pathlib import Path


def load_template(path: str | Path) -> str:
    """Load a prompt template file and return its contents."""
    return Path(path).read_text(encoding="utf-8")


def render(template: str, **kwargs: object) -> str:
    """Render a prompt template with the given keyword arguments.

    Uses Python str.format() so placeholders must be {key} style.
    Raises KeyError if a placeholder is missing from kwargs.
    """
    return template.format(**kwargs)


def render_oneshot(template: str, raw_name: str) -> str:
    return render(template, raw_name=raw_name)


def render_revision(
    template: str,
    raw_name: str,
    previous_guess_hex: str,
    feedback: str,
) -> str:
    return render(
        template,
        raw_name=raw_name,
        previous_guess_hex=previous_guess_hex,
        feedback=feedback,
    )


def render_revision_lab(
    template: str,
    raw_name: str,
    previous_guess_lab: str,
    feedback: str,
) -> str:
    """Render a revision prompt for the direct CIELAB output interface."""
    return render(
        template,
        raw_name=raw_name,
        previous_guess_lab=previous_guess_lab,
        feedback=feedback,
    )


def render_quantifier_calibration(
    template: str,
    base_lab: str,
    instruction: str,
) -> str:
    """Render an isolated LAB adjustment prompt."""
    return render(
        template,
        base_lab=base_lab,
        instruction=instruction,
    )


def render_llm_teacher(
    template: str,
    raw_name: str,
    target_hex: str,
    guess_hex: str,
    **extra: object,
) -> str:
    return render(
        template,
        raw_name=raw_name,
        target_hex=target_hex,
        guess_hex=guess_hex,
        **extra,
    )
