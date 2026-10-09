# Manuscript content audit — 2026-10-09

Working source: `paper/latex/color-games-revised.tex` and
`paper/latex/revision-appendix.tex`, reviewed from branch head
`63742e1a41499012f1521311a8c1907ad8879f1b` with the corrections below.
This audit supersedes pending-task recommendations in the earlier content
review. It assesses content, not conference acceptance or final page layout.

## Central claim and evidence

The defensible central claim is that receiver-specific calibration of a
three-phrase magnitude policy lowers average displayed target error relative
to the tested fixed quantifier rule in two model families. This is a comparison
of concrete policies under one text prompt and a frozen input distribution.
It does not show that all unfitted rules fail, that every adjustment improves,
or that the policy transfers between models.

| Evidence | Sampling unit and completion | Claim supported |
|---|---|---|
| Fresh grounding | 1,000 descriptions, 250 per regime; 4,000 parsed responses | Qwen mean recorded-target error falls from 42.332 to 22.147 after three oracle revisions. Additional information and adaptation are not separated. |
| Shared-start interfaces | 64 descriptions; 576 parsed revisions | Encoding and axis instructions affect correction when initial displayed states and first feedback match. HEX versus legend LAB equivalence is not established. |
| Qwen magnitude confirmation | 32 calibration colors; 128 held-out colors; 2,108 feasible targets; 2,098 common parsed quartets | Calibrated minus fixed-rule error is −5.497 [−5.786, −5.203]. Available-pair sensitivity agrees. |
| Gemma magnitude replication | Same input plan; independently fitted medians; 128 held-out colors; 2,081 common quartets | Primary effect is −5.161 [−5.484, −4.842]; language-only pairs retain all 2,108 cases and give −5.095 [−5.417, −4.772]. |
| Sequential Qwen pilot | 12 fresh starting colors; 200 targets; 600 completed games | Calibrated versus bare improves endpoint error and reduces evaluation calls. There is no unfitted sequential arm or Gemma sequential replication; calibration cost is additional. |
| Teacher restatement/reception | 60 evaluation descriptions; 480 teacher messages and 600 parsed receiving revisions | Prompting and demonstrations affect preservation; preservation and receiver utility are distinct. This is oracle-assisted restatement, not unaided teacher geometry. |

Targets within a starting color are repeated observations, not independent
colors. The two models use different common parsed cohorts; their means are
not a controlled between-model ranking. Distance and identity partitions are
exploratory diagnostics. In both models, aggregate calibration benefits are
concentrated at 24-unit targets; the median paired improvement is zero and many
policy prompts are identical. Gemma threshold convergence does not increase.

## Reviewer concern audit

| Concern, paraphrased | Completed response | Scientific boundary retained |
|---|---|---|
| HEX generation may confound geometric grounding | Direct-LAB, axis-legend and shared-start controls; numeric execution controls | These expose interface sensitivity, not internal perceptual representations or a full decomposition of name grounding. |
| One assigned color cannot measure semantic ambiguity | Retained and raw-source inventories find no repeated descriptions with alternative targets; validity ratings are distinguished from agreement | Human agreement remains unmeasured. Error is disagreement with the recorded target, not proof that another color is semantically wrong. |
| Zero-shot teacher evidence is insufficient | Matched zero/four-shot natural/restricted study, plus unchanged-message receiver evaluation | Demonstrations establish that supplied-set preservation is possible; no general following-versus-generating capability gap is claimed. |
| Paraphrase prompts and broad vocabulary may distort fidelity scores | Exact-direction restricted prompting and supplementary comparative-scope audit; format certification kept separate | Restriction changes several instructions together. Finite-grammar/assistant review is not independent human semantic annotation. Historical DP=0.11 is not reproduced. |
| Clause limits may force compression | c1/c3 budgets cover the supplied direction count in the new frozen plans | No forced compression in these controls; lost historical run settings cannot be reconstructed. |
| Teacher identity is unclear | Qwen/Qwen3-14B, backend, precision, decoding and 80/64-token teacher/receiver budgets disclosed | Same-family oracle-assisted evidence does not establish cross-family teacher generalization. |

## Corrections made in this pass

- Label the 12-color calibration and 196-target evaluation explicitly as the
  exploratory pilot, and identify sequential transfer as using that pilot's
  frozen policy. They are distinct from each model's 32/128 confirmation.
- Remove stale universal bootstrap-draw claims (historical 1,000/new 2,000).
  Current checked reporting implementations default to 5,000, while production
  summaries supplied here do not establish every invocation's analysis override.
  Retain the supported resampling units and percentile-interval interpretation.
- State the single fixed-rule and single-prompt boundary directly in Limitations.
- Add a permitted break in the full Gemma revision hash for appendix wrapping.
- Update the evidence map and README so completed confirmation, replication,
  source inventories and receiver audits are not presented as pending.

## Remaining work and experiment decision

No additional GPU experiment is necessary to state the scoped central claim
above. Additional experiments become necessary if the manuscript claims
superiority over unfitted policies generally, robustness to prompt wording,
cross-model policy transfer, or replicated sequential cost benefits. Those
claims are currently excluded. Human target agreement requires new judgments
or a dataset with alternative targets; the current exports cannot supply it.

Before submission, preserve/export the machine-side frozen plans, configs,
analysis JSON and checkpoints, verify exact analysis settings, and reconcile
the figure's rounded inputs with those files. The lost historical results
remain excluded. Complete related-work/bibliographic checking and the later
Overleaf publication-font/page-limit review. These are finishing tasks rather
than reasons to relaunch completed controls.

## Verification and provenance

Reported model outcomes come from author-supplied completed production reports
and saved-output inspections, checked against manuscript tables, figure inputs,
and available repository reporting code. Full GPU-machine checkpoint folders
have not been independently loaded in this workspace. This audit does not
claim a fresh raw-output recomputation or add model-performance evidence.
Changes affect prose and documentation only; no prompts, frozen plans,
controller fitting, generation settings or recorded outcomes are modified.
The amended LaTeX compiles to 15 pages with a temporary Courier substitution
for unavailable Inconsolata, with no overfull boxes or unresolved references
or citations in the final log. This checks source integrity; publication-font
layout and page limits remain for the later Overleaf review.
