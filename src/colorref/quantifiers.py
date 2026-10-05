"""Controlled quantifier and direction specifications for calibration experiments."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class DirectionSpec:
    name: str
    axis: str
    index: int
    sign: int
    phrase: str


DIRECTION_SPECS: dict[str, DirectionSpec] = {
    "lighter": DirectionSpec("lighter", "lab_l", 0, 1, "lighter"),
    "darker": DirectionSpec("darker", "lab_l", 0, -1, "darker"),
    "more_red": DirectionSpec("more_red", "lab_a", 1, 1, "more red"),
    "more_green": DirectionSpec("more_green", "lab_a", 1, -1, "more green"),
    "more_yellow": DirectionSpec("more_yellow", "lab_b", 2, 1, "more yellow"),
    "more_blue": DirectionSpec("more_blue", "lab_b", 2, -1, "more blue"),
}


@dataclass(frozen=True)
class QuantifierSpec:
    name: str
    modifier: str
    rank: int | None


QUANTIFIER_SPECS: dict[str, QuantifierSpec] = {
    "baseline": QuantifierSpec("baseline", "", None),
    "a_little": QuantifierSpec("a_little", "a little", 1),
    "somewhat": QuantifierSpec("somewhat", "somewhat", 2),
    "much": QuantifierSpec("much", "much", 3),
}


def get_direction(name: str) -> DirectionSpec:
    try:
        return DIRECTION_SPECS[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown calibration direction {name!r}; "
            f"expected one of {sorted(DIRECTION_SPECS)}"
        ) from exc


def get_quantifier(name: str) -> QuantifierSpec:
    try:
        return QUANTIFIER_SPECS[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown quantifier {name!r}; "
            f"expected one of {sorted(QUANTIFIER_SPECS)}"
        ) from exc


def make_instruction(quantifier: str, direction: str) -> str:
    """Render a controlled adjustment sentence."""
    q = get_quantifier(quantifier)
    d = get_direction(direction)
    prefix = f"{q.modifier} " if q.modifier else ""
    return f"Make it {prefix}{d.phrase}."


def measure_update(
    base_lab: tuple[float, float, float],
    predicted_lab: tuple[float, float, float],
    direction: str,
) -> dict[str, float]:
    """Measure signed requested movement and orthogonal drift in LAB."""
    d = get_direction(direction)
    update = tuple(predicted - base for predicted, base in zip(predicted_lab, base_lab))
    signed_step = d.sign * update[d.index]
    off_axis_sq = sum(update[i] ** 2 for i in range(3) if i != d.index)
    return {
        "update_l": update[0],
        "update_a": update[1],
        "update_b": update[2],
        "requested_signed_step": signed_step,
        "requested_abs_step": abs(update[d.index]),
        "off_axis_drift": math.sqrt(off_axis_sq),
        "movement_norm": math.sqrt(sum(value ** 2 for value in update)),
        "direction_followed": float(signed_step > 0.0),
    }


def pairwise_monotonicity(rows: list[dict]) -> dict[str, float | int]:
    """Compare a_little < somewhat < much within each base/direction.

    The unmodified baseline has no magnitude rank. Resolve ranks by name so
    archived trials with baseline rank 0 are also scored correctly. Equality
    counts as nondecreasing, but is reported separately from strict increases.
    """
    grouped: dict[tuple[str, str], dict[int, float]] = {}
    for row in rows:
        if not row.get("parse_ok"):
            continue
        rank = get_quantifier(row["quantifier"]).rank
        if rank is None:
            continue
        key = (str(row["base_id"]), str(row["direction"]))
        values = grouped.setdefault(key, {})
        if rank in values:
            raise ValueError(f"Duplicate quantifier rank {rank} for {key}")
        values[rank] = float(row["requested_signed_step"])

    comparisons = ordered = strict = ties = 0
    for values in grouped.values():
        ranks = sorted(values)
        for lower_i, lower_rank in enumerate(ranks):
            for higher_rank in ranks[lower_i + 1:]:
                comparisons += 1
                lower, higher = values[lower_rank], values[higher_rank]
                ordered += int(higher >= lower)
                strict += int(higher > lower)
                ties += int(higher == lower)
    return {
        "monotonicity_comparisons": comparisons,
        "monotonicity_ordered_pairs": ordered,
        "monotonicity_strict_pairs": strict,
        "monotonicity_tied_pairs": ties,
        "monotonicity_rate": ordered / comparisons if comparisons else float("nan"),
        "strict_monotonicity_rate": strict / comparisons if comparisons else float("nan"),
    }
