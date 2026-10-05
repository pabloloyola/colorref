"""Budget-aware teacher wrapper for the information-budget ablation (spec §5).

Wraps any base Teacher to enforce a total constraint budget across all turns.
When the budget is exhausted, returns a stop sentinel and the game should end.
"""

from __future__ import annotations

import logging
from typing import Any

from colorref.teachers import Feedback, Teacher

logger = logging.getLogger(__name__)

_STOP_TEXT = "[BUDGET_EXHAUSTED]"


class BudgetedTeacher(Teacher):
    """Enforce a total_constraint_budget across all feedback rounds.

    If the budget is exhausted, `give_feedback` returns a Feedback with
    `metadata["budget_exhausted"] = True`.  The caller should check this
    and stop the game rather than asking for another revision.

    Parameters
    ----------
    base_teacher:
        Any Teacher instance (typically AxisOracle).
    total_constraint_budget:
        Maximum total constraints to issue across all turns.
        Set to None (or 0) to use unlimited budget (passthrough mode).
    max_constraints_per_turn:
        Override the base teacher's per-turn limit if set.
    """

    def __init__(
        self,
        base_teacher: Teacher,
        total_constraint_budget: int | None,
        max_constraints_per_turn: int | None = None,
    ) -> None:
        self.base_teacher = base_teacher
        self.total_budget = total_constraint_budget
        self._max_per_turn = max_constraints_per_turn
        self._used: dict[int, int] = {}   # example_id → constraints used so far

    # ------------------------------------------------------------------
    # Internal accounting
    # ------------------------------------------------------------------

    def _constraints_used(self, example_id: int) -> int:
        return self._used.get(example_id, 0)

    def _record_usage(self, example_id: int, count: int) -> None:
        self._used[example_id] = self._used.get(example_id, 0) + count

    def reset(self, example_id: int) -> None:
        """Reset accounting for a new example."""
        self._used.pop(example_id, None)

    # ------------------------------------------------------------------
    # Teacher protocol
    # ------------------------------------------------------------------

    def give_feedback(
        self,
        target: dict,
        guess: dict,
        example: dict,
        turn: int,
    ) -> Feedback:
        example_id = int(example.get("example_id", 0))

        # Unlimited mode
        if not self.total_budget:
            return self.base_teacher.give_feedback(target, guess, example, turn)

        used = self._constraints_used(example_id)
        remaining = self.total_budget - used

        if remaining <= 0:
            return Feedback(
                text=_STOP_TEXT,
                teacher_type=getattr(self.base_teacher, "teacher_type", "budgeted"),
                constraint_axis=None,
                constraint_direction=None,
                constraint_sign=None,
                target_value=None,
                guess_value=None,
                delta=None,
                metadata={
                    "budget_exhausted": True,
                    "total_budget": self.total_budget,
                    "used": used,
                    "remaining": 0,
                },
            )

        # Temporarily limit the base teacher's per-turn constraint count
        original_max_n = getattr(self.base_teacher, "max_n", None)
        effective_limit = min(
            remaining,
            self._max_per_turn or (original_max_n or remaining),
        )
        if original_max_n is not None:
            self.base_teacher.max_n = effective_limit  # type: ignore[attr-defined]

        fb = self.base_teacher.give_feedback(target, guess, example, turn)

        # Restore original limit
        if original_max_n is not None:
            self.base_teacher.max_n = original_max_n  # type: ignore[attr-defined]

        # Count how many constraints were actually issued
        issued = _count_issued_constraints(fb)
        self._record_usage(example_id, issued)

        # Annotate feedback with budget metadata
        fb.metadata["budget_exhausted"] = False
        fb.metadata["budget_used"] = self._constraints_used(example_id)
        fb.metadata["budget_remaining"] = max(0, self.total_budget - self._constraints_used(example_id))
        fb.metadata["constraints_this_turn"] = issued
        fb.metadata["total_budget"] = self.total_budget

        return fb


def _count_issued_constraints(fb: Feedback) -> int:
    """Count actionable constraints in a Feedback object."""
    if fb.constraint_axis is None:
        return 0
    all_constraints = fb.metadata.get("all_constraints", [])
    if isinstance(all_constraints, list) and all_constraints:
        return len(all_constraints)
    # Single constraint
    return 1 if fb.constraint_axis else 0


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

# Budget condition definitions (spec Table §5.3)
BUDGET_CONDITIONS: dict[str, dict[str, int]] = {
    "one_shot":     {"rounds": 0, "max_c_per_turn": 0, "total_budget": 0},
    "one_turn_c1":  {"rounds": 1, "max_c_per_turn": 1, "total_budget": 1},
    "one_turn_c2":  {"rounds": 1, "max_c_per_turn": 2, "total_budget": 2},
    "one_turn_c3":  {"rounds": 1, "max_c_per_turn": 3, "total_budget": 3},
    "two_turn_c1":  {"rounds": 2, "max_c_per_turn": 1, "total_budget": 2},
    "two_turn_c2":  {"rounds": 2, "max_c_per_turn": 2, "total_budget": 4},
    "three_turn_c1":{"rounds": 3, "max_c_per_turn": 1, "total_budget": 3},
    "three_turn_c2":{"rounds": 3, "max_c_per_turn": 2, "total_budget": 6},
    "three_turn_c3":{"rounds": 3, "max_c_per_turn": 3, "total_budget": 9},
    "four_turn_c1": {"rounds": 4, "max_c_per_turn": 1, "total_budget": 4},
}


def build_budgeted_teacher(
    condition_name: str,
    base_teacher_cfg: dict[str, Any],
) -> tuple[Teacher, dict[str, Any]]:
    """Build a BudgetedTeacher for a named budget condition.

    Returns (teacher, condition_info_dict).
    """
    from colorref.teachers import build_teacher

    cond = BUDGET_CONDITIONS.get(condition_name)
    if cond is None:
        raise ValueError(f"Unknown budget condition: {condition_name!r}. "
                         f"Known: {list(BUDGET_CONDITIONS)}")

    rounds = cond["rounds"]
    max_c = cond["max_c_per_turn"]
    total = cond["total_budget"]

    if rounds == 0:
        # No feedback — return a teacher but the caller should skip feedback rounds
        from colorref.teachers import MinimalOracle
        teacher = MinimalOracle()
        return BudgetedTeacher(teacher, total_constraint_budget=0), cond

    # Build base teacher with per-turn constraint limit
    cfg = dict(base_teacher_cfg)
    cfg["max_feedback_constraints"] = max_c
    base = build_teacher(cfg)

    budgeted = BudgetedTeacher(
        base_teacher=base,
        total_constraint_budget=total,
        max_constraints_per_turn=max_c,
    )
    return budgeted, cond
