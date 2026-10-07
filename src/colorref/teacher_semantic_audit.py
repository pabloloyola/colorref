"""Exploratory finite-grammar audit; never change the frozen lexical scores."""

from __future__ import annotations

import re
from collections import Counter

from colorref.teacher_fidelity import DIRECTIONS, PHRASES

OPPOSITE = {
    direction: next(
        other
        for other, (axis, sign) in DIRECTIONS.items()
        if axis == DIRECTIONS[direction][0] and sign == -DIRECTIONS[direction][1]
    )
    for direction in DIRECTIONS
}
AUDIT_PHRASES = {
    **PHRASES,
    "less red": "more green",
    "less green": "more red",
    "less yellow": "more blue",
    "less blue": "more yellow",
    "less muted": "more saturated",
}


def interpret(text):
    """Resolve only whole direct instructions or explicit guess/target comparisons.

    Unknown/mixed clauses are unresolved, not failures of semantic understanding.
    This grammar is exploratory, developed after inspecting this pilot.
    """
    cleaned = re.sub(r"^\s*feedback\s*:\s*", "", text, count=1, flags=re.I)
    normalized = " ".join(cleaned.lower().strip().split())
    direct = re.fullmatch(r"make it (.+)\.", normalized)
    comparison = re.fullmatch(
        r"your guess is (.+) (?:than|compared to) the target(?: colou?r)?\.",
        normalized,
    )
    if direct:
        form, body = "direct_adjustment", direct[1]
    elif comparison:
        form, body = "guess_target_comparison", comparison[1]
    else:
        return {"resolved": False, "form": "manual_review", "directions": []}
    phrases = re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+", body)
    directions = []
    for phrase in phrases:
        phrase = re.sub(r"^(?:slightly|much)\s+", "", phrase)
        if phrase not in AUDIT_PHRASES:
            return {"resolved": False, "form": "manual_review", "directions": []}
        direction = AUDIT_PHRASES[phrase]
        directions.append(OPPOSITE[direction] if comparison else direction)
    return {
        "resolved": True,
        "form": form,
        "directions": sorted(set(directions)),
        "redundant_mentions": len(directions) - len(set(directions)),
        "label_prefix": cleaned != text,
    }


def audit_row(row):
    interpretation = interpret(row["raw_response"])
    required = {item["direction"] for item in row["required"]}
    actual = set(interpretation["directions"])
    resolved = interpretation["resolved"]
    return {
        "condition_id": row["condition_id"],
        "condition": row["condition"],
        "bandwidth": row["bandwidth"],
        "raw_response": row["raw_response"],
        "required": sorted(required),
        **interpretation,
        "exact_set_match": actual == required if resolved else None,
        "omissions": sorted(required - actual) if resolved else None,
        "additions": sorted(actual - required) if resolved else None,
        "lexical_certified": row["metrics"]["certified_preservation"],
    }


def audit(rows, completion, source_mode):
    """Summarize full checkpoints or the original selected diagnostic export.

    Omitted canonical passes are aggregate-only in export mode. No raw response,
    per-example assignment or paired contrast is manufactured for those passes.
    """
    if source_mode not in {"validated_checkpoints", "diagnostic_export"}:
        raise ValueError("Unknown source mode")
    ids = [r["condition_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate condition IDs")
    scored = [audit_row(row) for row in rows]
    summaries = []
    known_groups = {(c["condition"], c["bandwidth"]) for c in completion}
    if len(known_groups) != len(completion) or any(
        (r["condition"], r["bandwidth"]) not in known_groups for r in rows
    ):
        raise ValueError("Unknown or duplicate completion group")
    for group in completion:
        selected = [
            r
            for r in scored
            if (r["condition"], r["bandwidth"])
            == (group["condition"], group["bandwidth"])
        ]
        originals = [
            r
            for r in rows
            if (r["condition"], r["bandwidth"])
            == (group["condition"], group["bandwidth"])
        ]
        missing = group["completed"] - len(selected)
        canonical_seen = sum(r["metrics"]["canonical_compliant"] for r in originals)
        if missing < 0 or (source_mode == "validated_checkpoints" and missing):
            raise ValueError("Completion counts disagree with responses")
        if source_mode == "diagnostic_export":
            # Original diagnostics omit only certified canonical, non-magnitude rows.
            if group["canonical"] - canonical_seen != missing:
                raise ValueError(
                    "Export does not reconcile with omitted canonical passes"
                )
            if any(
                r["metrics"]["certified_preservation"]
                and r["metrics"]["canonical_compliant"]
                and not r["metrics"]["magnitude_language"]
                for r in originals
            ):
                raise ValueError("Unexpected row in original diagnostic selection")
        matched = sum(r["exact_set_match"] is True for r in selected)
        summaries.append(
            {
                "condition": group["condition"],
                "bandwidth": group["bandwidth"],
                "completed": group["completed"],
                "raw_audited": len(selected),
                "aggregate_only_canonical": missing,
                "resolved_match": matched + missing,
                "resolved_mismatch": sum(
                    r["exact_set_match"] is False for r in selected
                ),
                "manual_review": sum(not r["resolved"] for r in selected),
                "forms_in_audited_raw": dict(Counter(r["form"] for r in selected)),
                "lexical_certified": group["certified"],
            }
        )
    return {
        "source_mode": source_mode,
        "raw_audited": len(rows),
        "summary": summaries,
        "rows": scored,
        "manual_review": [r for r in scored if not r["resolved"]],
        "resolved_mismatches": [r for r in scored if r["exact_set_match"] is False],
    }


def report(result):
    lines = [
        "# Exploratory teacher meaning audit",
        "",
        f"- Source: {result['source_mode']}; raw responses audited: {result['raw_audited']}.",
        "- Whole-sentence comparisons describe the guess; their directions are reversed to obtain the implied adjustment.",
        "- A leading Feedback: label is ignored for meaning, while original format scores remain unchanged.",
        "",
        "| Condition | Budget | Completed | Raw audited | Aggregate-only canonical | Resolved match | Resolved mismatch | Manual review | Original certified |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in result["summary"]:
        lines.append(
            f"| {s['condition']} | {s['bandwidth']} | {s['completed']} | {s['raw_audited']} | {s['aggregate_only_canonical']} | {s['resolved_match']} | {s['resolved_mismatch']} | {s['manual_review']} | {s['lexical_certified']} |"
        )
    for title, key in [
        ("Unresolved wording", "manual_review"),
        ("Resolved set mismatches", "resolved_mismatches"),
    ]:
        lines.extend(["", f"## {title}", ""])
        for row in result[key]:
            lines.extend(
                [
                    f"### {row['condition_id']}",
                    "",
                    f"Required: {row['required']}; implied: {row['directions'] if row['resolved'] else 'unresolved'}.",
                    "",
                    "```text",
                    row["raw_response"],
                    "```",
                    "",
                ]
            )
    lines.extend(
        [
            "## Limits",
            "",
            "This finite grammar was developed after inspecting the pilot and is exploratory. It resolves explicit direct instructions and guess-versus-target comparisons, not arbitrary natural language. Unresolved text needs manual review and is not counted as semantically wrong. Exact-set fidelity differs from geometric validity and from downstream usefulness. Magnitude modifiers are not calibrated here. Raw text, original lexical metrics, prompts, demonstrations and checkpoints are never rewritten. Diagnostic-export mode reconciles omitted canonical passes using aggregate counts only; their raw responses and paired identities are unavailable, so no per-example effects or intervals are inferred. Full-run mode validates frozen inputs and checkpoints. These observations do not reproduce the historical paper table or establish unaided teacher geometry, population generalization or receiving-guesser performance.",
        ]
    )
    return "\n".join(lines) + "\n"
