# Framework content revision — 2026-10-09

This is a content pass following the approved introduction and paired game figures.
The requested priority is explanatory coherence; page-limit trimming is deferred.

## What changed

- Define description, assigned recorded target, semantic regime and guess distinctly.
  Assigned-target disagreement is not unique semantic correctness.
- Explain turn 0, feedback reception, fresh-context prompting and supplied starts.
  One-shot refers to prediction without revision, independently of demonstration count.
- Separate three fixed revisions in the current grounding/interface studies from
  target-known stopping at Delta E76 <= 5 in the sequential pilot (cap five).
  Remove the historical early-stop protocol from the definition of current games.
- Define native LAB and displayed-state conversion before interpreting trajectories.
- Add a receiver-calibrated wording subsection with the fitted displayed-step median
  and nearest-positive-median selection rule. Parsed zero/wrong-sign steps remain;
  bare wording is unranked; tie rules and unavailable mappings are explicit.
- Explain the study progression and the question answered by each control: reference
  games, shared starts, isolated adjustments, calibration confirmation and teacher
  production/reception. Full-game calibration transfer is not claimed.
- Disclose the axis-oracle minimum discrepancies and fixed normalization ranges,
  checked against `src/colorref/teachers.py` and the grounding configuration.

## Implementation reconciliation

`magnitude_control.fit_mapping` pools parsed displayed requested-axis steps by
receiving model, direction and wording, then takes their median. It keeps zero
and negative parsed steps. A graded phrase is usable only with a positive fitted
median; the bare baseline is excluded from selection. `choose_phrase` minimizes
absolute distance from the requested-axis residual, breaking ties by smaller
median and then phrase order. An absent candidate is recorded as unavailable.
The held-out plan retains distinct arms and explicit numeric coordinate holds;
no evaluation responses refit either model's controller.

The oracle includes absolute discrepancies at least [2, 3, 3, 0.05] on [L, a, b,
HSV saturation], ranks using ranges [100, 200, 220, 1], and emits at most the
configured count. Ranking scales are policy choices, not perceptual step units.
No code or prompt is changed by this manuscript edit.

## Preserved evidence and validation

The introductory text and everything from Results onward are unchanged byte for
byte. Original figure assets, datasets, model outputs, numerical result tables,
plans and prompts are preserved. This pass introduces no new performance evidence.

The reading copy is compiled with a temporary Courier substitution for the absent
Inconsolata package. Committed sources keep Inconsolata and the original ACL style.
The final 18-page build has no overfull boxes or unresolved references/citations.
All rendered pages and high-resolution views of the edited methods were inspected. The output is a content-reading draft, not final
submission-font/page-limit approval. The next editorial task is the Results
narrative and then Discussion/claim alignment, followed by the author's full read.
