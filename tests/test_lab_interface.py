"""Tests for the direct CIELAB guesser interface."""

import pytest

from colorref.games import _parse_and_convert, run_game_for_example
from colorref.llm_clients import MockLLMClient
from colorref.run_metadata import (
    interface_identity,
    output_space_from_config,
    teacher_identity,
)
from colorref.teachers import AxisOracle


def _example() -> dict:
    return {
        "example_id": 1,
        "raw_name": "dusty sunset",
        "hex": "#c08060",
        "rgb_r": 192,
        "rgb_g": 128,
        "rgb_b": 96,
        "lab_l": 60.0,
        "lab_a": 40.0,
        "lab_b": 20.0,
        "hsv_h": 20.0,
        "hsv_s": 0.5,
        "hsv_v": 0.75,
        "regime_label": "compound_associative",
    }


def test_direct_lab_parser_preserves_native_coordinates() -> None:
    guess = _parse_and_convert("LAB(50, 10, -20)", output_space="lab")
    assert guess["parse_ok"] is True
    assert guess["lab"] == (50.0, 10.0, -20.0)
    assert guess["hex"].startswith("#")
    assert guess["lab_projection_delta_e"] >= 0.0


def test_direct_lab_parser_records_out_of_gamut_projection_error() -> None:
    guess = _parse_and_convert("LAB(50, 127, 127)", output_space="lab")
    assert guess["parse_ok"] is True
    assert guess["lab"] == (50.0, 127.0, 127.0)
    assert guess["lab_projection_delta_e"] > 1.0


def test_unknown_output_space_fails_early() -> None:
    with pytest.raises(ValueError, match="Unsupported output space"):
        _parse_and_convert("#ff0000", output_space="rgb")


def test_lab_game_uses_native_revision_prompt_and_records_identity() -> None:
    game = run_game_for_example(
        example=_example(),
        run_id="test-lab",
        initial_template="Color: {raw_name}. Return LAB(L, a, b).",
        revision_template=(
            "Color: {raw_name}. Previous: {previous_guess_lab}. "
            "Feedback: {feedback}. Return LAB(L, a, b)."
        ),
        guesser=MockLLMClient("LAB(50, 10, -20)"),
        teacher=AxisOracle(max_feedback_constraints=3),
        model_alias="mock",
        teacher_type="axis_oracle",
        prompt_version="lab-test",
        max_turns=1,
        output_space="lab",
        guesser_model_name="mock/model",
        guesser_provider="mock",
    )

    assert len(game.turn_records) == 2
    revision = game.turn_records[1]
    assert "Previous: LAB(50.00, 10.00, -20.00)" in revision["prompt"]
    assert revision["output_space"] == "lab"
    assert revision["evaluation_space"] == "lab"
    assert revision["guesser_model_name"] == "mock/model"
    assert revision["guess_lab_l"] == 50.0
    assert game.summary["output_space"] == "lab"


def test_legacy_config_defaults_to_hex() -> None:
    cfg = {"model": {"alias": "m", "model_name": "org/m", "provider": "hf"}}
    assert output_space_from_config(cfg) == "hex"
    assert interface_identity(cfg)["parser"] == "extract_hex"


def test_teacher_identity_distinguishes_oracle_and_shared_llm() -> None:
    guesser = {"alias": "qwen", "model_name": "Qwen/Qwen3-14B", "provider": "hf"}
    oracle = teacher_identity({"type": "axis_oracle"}, guesser)
    assert oracle["kind"] == "deterministic"
    assert oracle["model_name"] is None

    llm = teacher_identity(
        {"type": "llm_teacher", "model": guesser.copy()},
        guesser,
    )
    assert llm["kind"] == "llm"
    assert llm["model_name"] == "Qwen/Qwen3-14B"
    assert llm["shares_guesser_model"] is True
