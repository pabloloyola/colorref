"""Matched oracle-assisted teacher prompts; no inference or controller fitting."""

from __future__ import annotations

import copy
import json
import random
import re
from collections import Counter
from statistics import mean

import numpy as np

from colorref.interface_study import REGIMES, color_from_hex
from colorref.quantifier_study import plan_digest
from colorref.shared_start_study import validate_plan as validate_parent
from colorref.teachers import _compute_candidate_deltas, detect_constraints

CONDITIONS = ("natural_0", "natural_4", "restricted_0", "restricted_4")
DIRECTIONS = {
    "lighter": ("lab_l", 1),
    "darker": ("lab_l", -1),
    "more red": ("lab_a", 1),
    "more green": ("lab_a", -1),
    "more yellow": ("lab_b", 1),
    "more blue": ("lab_b", -1),
    "more saturated": ("hsv_s", 1),
    "more muted": ("hsv_s", -1),
}
PHRASES = {
    "lighter": "lighter",
    "brighter": "lighter",
    "more lightness": "lighter",
    "darker": "darker",
    "deeper": "darker",
    "less bright": "darker",
    "more red": "more red",
    "redder": "more red",
    "more green": "more green",
    "greener": "more green",
    "more yellow": "more yellow",
    "yellower": "more yellow",
    "more blue": "more blue",
    "bluer": "more blue",
    "more saturated": "more saturated",
    "more vivid": "more saturated",
    "vivid": "more saturated",
    "more muted": "more muted",
    "less saturated": "more muted",
    "duller": "more muted",
}
LEXICAL = re.compile(
    r"\b(?:"
    + "|".join(re.escape(p) for p in sorted(PHRASES, key=len, reverse=True))
    + r")\b"
)
CONNECTORS = set(
    "make it the color colour should be look feel please try making move shift toward towards to and also a shade tone more less little bit slightly somewhat much very considerably significantly substantially change adjust lighter".split()
)


def study_config(snapshot, name, output_root=None):
    parent = snapshot["config"]
    model = {**copy.deepcopy(parent["model"]), "max_tokens": 80}
    model["alias"] = parent["model"].get("alias", "teacher") + "_teacher_fidelity"
    return {
        "experiment_name": name,
        "seed": 59,
        "model": model,
        "output": {"run_root": str(output_root or parent["output"]["run_root"])},
        "study": {
            "bandwidths": [1, 3],
            "demonstrations_per_regime": 1,
            "min_delta": copy.deepcopy(parent["teacher"]["min_delta"]),
        },
        "analysis": {"resamples": 2000, "seed": 13},
    }


def canonical(directions):
    if not directions:
        raise ValueError("Teacher fidelity requires a nonempty direction set")
    return (
        "Make it "
        + (
            directions[0]
            if len(directions) == 1
            else " and ".join(directions)
            if len(directions) == 2
            else ", ".join(directions[:-1]) + ", and " + directions[-1]
        )
        + "."
    )


def state_key(example):
    return (example["hex"], example["shared_start_hex"])


def name_key(example):
    return " ".join(example["raw_name"].casefold().split())


def candidates(example, cfg):
    return _compute_candidate_deltas(
        color_from_hex(example["hex"]),
        color_from_hex(example["shared_start_hex"]),
        cfg["study"]["min_delta"],
    )


def render_case(template, example, required, bandwidth):
    return template.format(
        raw_name=example["raw_name"],
        target_hex=example["hex"],
        guess_hex=example["shared_start_hex"],
        max_clauses=bandwidth,
        oracle_constraints_json=json.dumps(
            [{"direction": c["direction"], "axis": c["axis"]} for c in required],
            indent=2,
        ),
    )


def build_plan(cfg, snapshot, templates):
    parent_cfg, parent_plan, metadata = (
        snapshot["config"],
        snapshot["plan"],
        snapshot["metadata"],
    )
    validate_parent(parent_cfg, parent_plan)
    if (
        metadata["study_kind"] != "shared_start_interface"
        or metadata["config_sha256"] != plan_digest([parent_cfg])
        or metadata["plan_sha256"] != plan_digest([parent_plan])
    ):
        raise ValueError("Parent input digests do not match the shared-start study")
    expected = study_config(snapshot, cfg["experiment_name"], cfg["output"]["run_root"])
    if cfg != expected:
        raise ValueError("Teacher configuration differs from the declared protocol")
    if set(templates) != {"natural", "restricted"} or not all(templates.values()):
        raise ValueError("Require both frozen teacher templates")
    examples = sorted(parent_plan["examples"], key=lambda e: e["example_id"])
    rng = random.Random(cfg["seed"])
    ordered = examples.copy()
    rng.shuffle(ordered)
    demonstrations = []
    for regime in REGIMES:
        eligible = [
            e
            for e in ordered
            if e["regime_label"] == regime
            and candidates(e, cfg)
            and all(
                name_key(e) != name_key(d) and state_key(e) != state_key(d)
                for d in demonstrations
            )
        ]
        if not eligible:
            raise ValueError(f"No distinct nonempty demonstration for {regime}")
        demonstrations.append(eligible[0])
    demo_ids = {e["example_id"] for e in demonstrations}
    demo_names = {name_key(e) for e in demonstrations}
    demo_states = {state_key(e) for e in demonstrations}
    evaluation, exclusions = [], []
    for example in examples:
        if example["example_id"] in demo_ids:
            continue
        reason = (
            "demonstration_description_or_state_overlap"
            if name_key(example) in demo_names or state_key(example) in demo_states
            else "no_oracle_constraint"
            if not candidates(example, cfg)
            else None
        )
        if reason:
            exclusions.append({"example_id": example["example_id"], "reason": reason})
        else:
            evaluation.append(example)
    if any(not any(e["regime_label"] == r for e in evaluation) for r in REGIMES):
        raise ValueError("Need held-out evaluation examples in every regime")
    coverage = {}
    for bandwidth in cfg["study"]["bandwidths"]:
        coverage[str(bandwidth)] = dict(
            Counter(
                c["direction"]
                for d in demonstrations
                for c in candidates(d, cfg)[:bandwidth]
            )
        )
    tasks = []
    rng.shuffle(evaluation)
    for example in evaluation:
        all_candidates = candidates(example, cfg)
        for bandwidth in cfg["study"]["bandwidths"]:
            required = all_candidates[:bandwidth]
            conditions = list(CONDITIONS)
            rng.shuffle(conditions)
            for condition in conditions:
                form, shots = condition.split("_")
                prompt = render_case(templates[form], example, required, bandwidth)
                demo_blocks = []
                if shots == "4":
                    for n, d in enumerate(demonstrations, 1):
                        dc = candidates(d, cfg)[:bandwidth]
                        demo_blocks.append(
                            f"Example {n}:\n"
                            + render_case(templates[form], d, dc, bandwidth)
                            + "\nFeedback: "
                            + canonical([c["direction"] for c in dc])
                        )
                    prompt = (
                        "Worked examples:\n\n"
                        + "\n\n".join(demo_blocks)
                        + "\n\nNew case:\n"
                        + prompt
                    )
                tasks.append(
                    {
                        "slot": len(tasks),
                        "condition_id": f"{example['example_id']}:c{bandwidth}:{condition}",
                        "case_id": f"{example['example_id']}:c{bandwidth}",
                        "example_id": example["example_id"],
                        "regime": example["regime_label"],
                        "condition": condition,
                        "bandwidth": bandwidth,
                        "clause_budget": bandwidth,
                        "constraint_count": len(required),
                        "example": example,
                        "required": required,
                        "all_candidates": all_candidates,
                        "demonstration_ids": [d["example_id"] for d in demonstrations]
                        if shots == "4"
                        else [],
                        "prompt": prompt,
                        "oracle_feedback": canonical(
                            [c["direction"] for c in required]
                        ),
                    }
                )
    return {
        "templates": templates,
        "demonstrations": demonstrations,
        "evaluation": evaluation,
        "exclusions": exclusions,
        "demo_direction_coverage": coverage,
        "tasks": tasks,
        "parent_run_id": metadata["run_id"],
    }


def score(task, text):
    required = {c["direction"] for c in task["required"]}
    valid = {c["direction"] for c in task["all_candidates"]}
    matches = list(LEXICAL.finditer(text.lower()))
    mentions = [PHRASES[m.group()] for m in matches]
    detected = set(mentions)
    remainder = LEXICAL.sub(" ", text.lower())
    unknown = sorted(set(re.findall(r"[a-z]+", remainder)) - CONNECTORS)
    flags = []
    if re.search(r"\b(?:not|never|without|avoid|neither|no)\b|n['’]t\b", text.lower()):
        flags.append("negation_or_scope")
    if re.search(
        r"\b(?:warm(?:er)?|cool(?:er)?|gr[ae]y|neutral|chroma)\b", text.lower()
    ):
        flags.append("broad_vocabulary")
    if unknown:
        flags.append("unrecognized_words")
    if re.search(r"\b(?:more|less)\b", remainder):
        flags.append("unresolved_comparative_scope")
    if re.search(r"\d", text):
        flags.append("numeric_content")
    if re.search(r"#?[0-9a-fA-F]{6}\b", text):
        flags.append("hex_like_content")
    nonempty = bool(text.strip())
    canonical_parts = re.split(
        r"\s*,\s*(?:and\s+)?|\s+and\s+", text.strip().lower()[8:-1]
    )
    grammar = (
        text.strip().lower().startswith("make it ")
        and text.strip().endswith(".")
        and all(p in DIRECTIONS for p in canonical_parts)
        and len(canonical_parts) == len(set(canonical_parts))
        and set(canonical_parts) == required
    )
    reverse = sorted(
        d
        for d in detected
        if any(
            DIRECTIONS[d][0] == DIRECTIONS[r][0]
            and DIRECTIONS[d][1] != DIRECTIONS[r][1]
            for r in required
        )
    )
    contradictions = sorted(
        axis
        for axis in {DIRECTIONS[d][0] for d in detected}
        if {DIRECTIONS[d][1] for d in detected if DIRECTIONS[d][0] == axis} == {-1, 1}
    )
    legacy = {c["direction"] for c in detect_constraints(text)}
    return {
        **task,
        "raw_response": text,
        "metrics": {
            "nonempty": nonempty,
            "detected_directions": sorted(detected),
            "keyword_set_equal": detected == required,
            "certified_preservation": nonempty
            and detected == required
            and not flags
            and len(mentions) == len(detected),
            "canonical_compliant": grammar,
            "omissions": sorted(required - detected),
            "additions": sorted(detected - required),
            "reversals": reverse,
            "contradictory_axes": contradictions,
            "duplicate_mentions": len(mentions) - len(detected),
            "audit_flags": flags,
            "unrecognized_words": unknown,
            "recognized_geometric_precision": len(detected & valid) / len(detected)
            if detected
            else None,
            "legacy_keyword_geometric_precision": len(legacy & valid) / len(legacy)
            if legacy
            else None,
            "magnitude_language": bool(
                re.search(
                    r"\b(?:little|slightly|somewhat|much|very|considerably|significantly|substantially)\b",
                    text.lower(),
                )
            ),
            "direction_mentions": len(mentions),
            "direction_count_above_budget": len(mentions) > task["clause_budget"],
            "punctuated_segments": sum(
                bool(p.strip()) for p in re.split(r"[.!?]+", text)
            ),
        },
    }


def paired_interval(tasks, rows, left, right, cfg):
    grouped = {}
    for t in tasks:
        grouped.setdefault(t["case_id"], {})[t["condition"]] = t
    cases = [
        v
        for v in grouped.values()
        if left in v
        and right in v
        and v[left]["condition_id"] in rows
        and v[right]["condition_id"] in rows
    ]
    values = {}
    for case in cases:
        t = case[left]
        delta = int(
            rows[case[right]["condition_id"]]["metrics"]["certified_preservation"]
        ) - int(rows[t["condition_id"]]["metrics"]["certified_preservation"])
        values.setdefault(t["regime"], {}).setdefault(t["example_id"], []).append(delta)
    count = sum(len(v) for group in values.values() for v in group.values())
    estimate = (
        sum(sum(v) for group in values.values() for v in group.values()) / count
        if count
        else None
    )
    clusters = sum(len(g) for g in values.values())
    interval = None
    if clusters >= 2:
        rng = np.random.default_rng(cfg["analysis"]["seed"])
        sums = np.zeros(cfg["analysis"]["resamples"])
        sizes = np.zeros_like(sums)
        for group in values.values():
            entries = list(group.values())
            draw = rng.integers(len(entries), size=(len(sums), len(entries)))
            sums += np.array([sum(v) for v in entries])[draw].sum(axis=1)
            sizes += np.array([len(v) for v in entries])[draw].sum(axis=1)
        interval = np.quantile(sums / sizes, [0.025, 0.975]).tolist()
    return {
        "left": left,
        "right": right,
        "cases": count,
        "examples": clusters,
        "difference": estimate,
        "interval": interval,
    }


def analyze(cfg, plan, rows):
    completion = []
    common = {}
    for t in plan["tasks"]:
        common.setdefault(t["case_id"], []).append(t)
    common_tasks = [
        t
        for group in common.values()
        if all(t["condition_id"] in rows for t in group)
        for t in group
    ]
    for bandwidth in cfg["study"]["bandwidths"]:
        for condition in CONDITIONS:
            tasks = [
                t
                for t in plan["tasks"]
                if t["bandwidth"] == bandwidth and t["condition"] == condition
            ]
            saved = [
                rows[t["condition_id"]] for t in tasks if t["condition_id"] in rows
            ]
            metrics = [r["metrics"] for r in saved]
            precisions = [
                m["recognized_geometric_precision"]
                for m in metrics
                if m["recognized_geometric_precision"] is not None
            ]
            completion.append(
                {
                    "condition": condition,
                    "bandwidth": bandwidth,
                    "planned": len(tasks),
                    "completed": len(saved),
                    "pending": len(tasks) - len(saved),
                    "nonempty": sum(m["nonempty"] for m in metrics),
                    "certified": sum(m["certified_preservation"] for m in metrics),
                    "keyword_equal": sum(m["keyword_set_equal"] for m in metrics),
                    "canonical": sum(m["canonical_compliant"] for m in metrics),
                    "audit_flagged": sum(bool(m["audit_flags"]) for m in metrics),
                    "omission_outputs": sum(bool(m["omissions"]) for m in metrics),
                    "addition_outputs": sum(bool(m["additions"]) for m in metrics),
                    "reversal_outputs": sum(bool(m["reversals"]) for m in metrics),
                    "duplicate_outputs": sum(
                        bool(m["duplicate_mentions"]) for m in metrics
                    ),
                    "magnitude_outputs": sum(m["magnitude_language"] for m in metrics),
                    "above_budget_outputs": sum(
                        m["direction_count_above_budget"] for m in metrics
                    ),
                    "geometric_precision": mean(precisions) if precisions else None,
                    "precision_outputs": len(precisions),
                    "mean_prompt_tokens": mean(
                        [
                            r["prompt_tokens"]
                            for r in saved
                            if r.get("prompt_tokens") is not None
                        ]
                    )
                    if any(r.get("prompt_tokens") is not None for r in saved)
                    else None,
                    "mean_output_tokens": mean(
                        [
                            r["generation"]["generated_tokens"]
                            for r in saved
                            if r.get("generation", {}).get("generated_tokens")
                            is not None
                        ]
                    )
                    if any(
                        r.get("generation", {}).get("generated_tokens") is not None
                        for r in saved
                    )
                    else None,
                }
            )
    comparisons = [
        ("natural_0", "natural_4"),
        ("restricted_0", "restricted_4"),
        ("natural_0", "restricted_0"),
        ("natural_4", "restricted_4"),
    ]
    effects = [
        {"cohort": cohort, **paired_interval(tasks, rows, left, right, cfg)}
        for cohort, tasks in (
            ("common_quartets", common_tasks),
            ("available_pairs", plan["tasks"]),
        )
        for left, right in comparisons
    ]
    diagnostics = [
        r
        for r in rows.values()
        if not r["metrics"]["certified_preservation"]
        or not r["metrics"]["canonical_compliant"]
        or r["metrics"]["magnitude_language"]
    ]
    return {
        "planned": len(plan["tasks"]),
        "completed": len(rows),
        "common_quartets": len(common_tasks) // 4,
        "completion": completion,
        "effects": effects,
        "diagnostics": diagnostics,
        "demo_direction_coverage": plan["demo_direction_coverage"],
        "exclusions": plan["exclusions"],
        "oracle_canonical_certified": sum(
            score(t, t["oracle_feedback"])["metrics"]["certified_preservation"]
            for t in plan["tasks"]
        )
        == len(plan["tasks"]),
    }


def fmt(v):
    return "n/a" if v is None else f"{v:.3f}"


def report(result, cfg, plan, run_id):
    lines = [
        f"# Matched oracle-assisted teacher fidelity: {run_id}",
        "",
        f"- Teacher: {cfg['model']['model_name']} via {cfg['model']['provider']}; temperature 0, thinking disabled, 80 output tokens.",
        f"- Completed: {result['completed']} / {result['planned']}; common matched quartets: {result['common_quartets']}.",
        f"- Demonstrations: {len(plan['demonstrations'])}; evaluation examples: {len(plan['evaluation'])}; exclusions: {len(plan['exclusions'])}.",
        "- Each generation has a fresh context; no guesser revisions are generated.",
        "- c1/c3 indicate maximum supplied directions; clause budget equals that maximum.",
        "- Exact-direction canonical oracle baseline passes the audit: "
        + str(result["oracle_canonical_certified"]),
        "",
        "## Completion and conservative preservation",
        "",
        "Certified means the detected direction set matches, without ambiguous/unknown wording or duplicate mentions. Uncertified is not automatically semantically wrong.",
        "",
        "| Condition | Budget | Completed / planned | Certified N | Keyword-equal N | Canonical N | Flagged N | Recognized geometric precision (N) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in result["completion"]:
        lines.append(
            f"| {r['condition']} | {r['bandwidth']} | {r['completed']} / {r['planned']} | {r['certified']} | {r['keyword_equal']} | {r['canonical']} | {r['audit_flagged']} | {fmt(r['geometric_precision'])} ({r['precision_outputs']}) |"
        )
    lines += [
        "",
        "## Output diagnostics",
        "",
        "Counts overlap. Additions may be geometrically valid but are absent from the supplied set; reversals concern supplied axes. Keyword-only precision is not a semantic judgment.",
        "",
        "| Condition | Budget | Omits | Adds | Reverses | Duplicates | Magnitude | Above direction budget | Mean prompt / output tokens |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in result["completion"]:
        lines.append(
            f"| {r['condition']} | {r['bandwidth']} | {r['omission_outputs']} | {r['addition_outputs']} | {r['reversal_outputs']} | {r['duplicate_outputs']} | {r['magnitude_outputs']} | {r['above_budget_outputs']} | {fmt(r['mean_prompt_tokens'])} / {fmt(r['mean_output_tokens'])} |"
        )
    lines += [
        "",
        "## Paired certified-preservation differences",
        "",
        "Right minus left, with regime-stratified whole-example percentile 95% intervals. Both bandwidths stay together in each sampled example. Differences are proportions.",
        "",
        "| Cohort | Left → right | Cases | Examples | Difference [95% interval] |",
        "|---|---|---:|---:|---|",
    ]
    for e in result["effects"]:
        interval = (
            ""
            if e["interval"] is None
            else " [" + ", ".join(map(fmt, e["interval"])) + "]"
        )
        lines.append(
            f"| {e['cohort']} | {e['left']} → {e['right']} | {e['cases']} | {e['examples']} | {fmt(e['difference'])}{interval} |"
        )
    lines += ["", "## Diagnostic outputs (first twelve)", ""]
    for row in result["diagnostics"][:12]:
        m = row["metrics"]
        lines += [
            f"### {row['condition_id']}",
            "",
            f"Required: {[c['direction'] for c in row['required']]}; "
            f"detected: {m['detected_directions']}; flags: {m['audit_flags']}; "
            f"certified: {m['certified_preservation']}; canonical: {m['canonical_compliant']}.",
            "",
            "```text",
            row["raw_response"],
            "```",
            "",
        ]
    if not result["diagnostics"]:
        lines.append(
            "None among saved outputs. Check pending counts before interpretation."
        )
    lines += [
        "",
        "## Demonstration direction coverage",
        "",
        str(result["demo_direction_coverage"]),
        "",
        "## Interpretation limits",
        "",
        "This audits restatement of supplied oracle directions, not unaided teacher geometry, downstream guesser performance or the original paper's teacher-table replication. Natural_0 uses the archived paraphrase prompt; restricted prompting is a multi-instruction intervention. Few-shot answers are canonical oracle sentences, not learned teacher outputs, and do not guarantee coverage of every direction. The same demonstration IDs/order are used across forms; c1/c3 demonstrate their respective selected directions. Few-shot prompts have more input tokens but share the same output budget. Empty outputs count as completed failures. Backend errors stay pending, never receive fallback feedback. Frozen exclusions depend only on input overlap/empty oracle sets, not model outcomes. Broad vocabulary, negation and unknown wording require manual review; conservative certification cannot establish that uncertified natural language is wrong. Canonical-format compliance is a restricted-output diagnostic, not a fair standalone ranking of natural wording. Intervals condition on matched observed cases, do not quantify generation randomness, establish population generalization or adjust for multiple comparisons; singleton strata have no resampling variation. Full prompts/responses, metrics, legacy detector scores and manual-review candidates remain in metrics/teacher_analysis.json and checkpoints. No outputs are repaired or used to select demonstrations.",
        "",
    ]
    return "\n".join(lines)
