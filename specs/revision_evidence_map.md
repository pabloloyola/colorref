# Revision evidence map — current as of 2026-10-08

This is the current status of the expert concerns after the completed experiments
and first manuscript rewrite. Earlier pending-work guidance is superseded here;
the Git history and individual result notes preserve the chronological record.
The original review is paraphrased, not reproduced publicly.

Working manuscript: `paper/latex/color-games-revised.tex`.
Completed source/availability audit and machine-side commands:
`specs/results/content_source_audit_20261008.md`.
Content decisions and remaining tasks: `specs/manuscript_content_review_20261008.md`.
Import/rewrite provenance: `specs/manuscript_baseline_20261008.md` and
`specs/manuscript_revision_20261008.md`.

## Concern-to-evidence checklist

| Concern | Current evidence | Status and remaining boundary | Revised manuscript location |
|---|---|---|---|
| No direct LAB comparison; output encoding may confound grounding | The 64-example shared-start study holds displayed starts and first oracle feedback fixed across HEX, plain LAB, and legend LAB. All 576 revisions parse. Numeric controls separately test coordinate execution. | Experimental control completed. It establishes interface/prompt sensitivity, not a full causal decomposition of name grounding or internal perceptual understanding. Later feedback is adaptive; primary first-revision comparisons remain distinct. | Framework 3.2–3.3; Setup 4.2; Results 5.2; Appendix C.1 |
| One crowd-sourced target can conflate ambiguity with model error | The manuscript defines error as disagreement with the recorded target. Production inventories find unique descriptions in all 705,869 raw English entries and 518,830 retained rows, with no repeated targets; evaluation fields have no explicit votes or alternative colors. | Source availability audited; addressed by reframing. Human target agreement remains unmeasured. Feedback localizes an assigned target, without proving another prediction semantically implausible. | Introduction; Dataset 3.1; Results 5.1; Limitations; Appendix A |
| Teacher capability conclusion was based only on zero-shot prompting | The matched teacher study crosses natural/restricted wording with zero/four-shot conditions: 480 messages, four input-selected demonstrations excluded from 60 evaluation examples. The receiver study passes all messages unchanged in 600 revisions. | Required few-shot control completed. Both four-shot conditions preserve all 120 supplied sets under the supplementary finite grammar; this does not imply optimal receiving performance or unaided teacher geometry. | Setup 4.4; Results 5.5; Appendix E |
| Natural paraphrasing and broader vocabulary may distort supplied directions | The archived natural prompt is retained and compared with an exact-direction restricted prompt. Lexical certification, scope-aware matching, and downstream receiving error are reported separately. | Alternative prompting tested. Restricted wording changes several instructions at once, so it does not isolate a single causal wording mechanism. The available template-vocab oracle selects primitive directions and is not a broad-vocabulary ceiling. | Setup 4.1, 4.4; Results 5.5; Appendices B, E |
| The clause limit might force compression below the supplied direction count | New plans log c1/c3 and set the clause budget to the maximum supplied count; the dry-run confirms coverage. Available archived implementation also uses the same maximum for selection and clauses. | Ruled out as a forced constraint in the new comparison. Exact historical table-producing configuration remains unverified; do not attribute DP=0.11 to clause compression. | Setup 4.4; Appendix E |
| Teacher model identity was not disclosed | New teacher and receiver experiments explicitly use Qwen/Qwen3-14B via HF Transformers on an A100 40 GB, bfloat16, thinking disabled, temperature zero; teacher/receiver output budgets are 80/64. | Disclosure fixed for new evidence. Archived debug configs do not establish the exact identity/settings of the historical table-producing run. | Setup 4.5; Appendix E |
| Extremely low oracle-assisted precision may be a prompt/scoring artifact | Supplementary auditing resolves comparisons such as “your guess is darker than the target” as lighter corrections; harmless Feedback labels explain many failures of strict certification. Natural zero-shot has 81 resolved matches, 17 mismatches and 22 unresolved cases. | Scoring vulnerability demonstrated in the new pilot. Historical scores are neither reproduced nor wholly invalidated. Their raw-output/provenance audit remains open; the old general capability claim is removed. | Results 5.5; Discussion; Appendix E.1 |

## Completed evidence anchors

| Study | Independent units and completion | Main observation | Result note |
|---|---|---|---|
| Shared-start interfaces | 64 descriptions; 192 games; 576 parsed revisions | First-revision plain LAB minus HEX: +6.187 [0.845, 11.889]. Final legend minus plain LAB: −12.114 [−18.035, −5.489]. Close HEX/legend means do not establish equivalence. | `specs/results/shared_start_20261007.md` |
| Isolated quantifiers | 12 fixed anchors; 888 parsed responses | Positive qualitative updates: 228/288 plain, 288/288 legend. Strict ordinal pairs: 172/216 plain, 210/216 legend. Pairs overlap within anchors. | `specs/quantifier_calibration.md`; Appendix C.2 |
| One-step magnitude policy | 12 calibration colors, 288 calls/287 parsed; 12 held-out starts, 196 targets/588 parsed responses | Bare/calibrated/numeric target errors: 11.770/6.362/0.533. Calibrated minus bare: −5.408 [−10.220, −2.173]; median paired difference zero. | `specs/results/magnitude_control_20261007.md` |
| Sequential transfer | 12 further starts; 200 targets; 600 games; 1,059 parsed revisions | Bare/calibrated/numeric errors: 6.461/2.979/0.095; calls: 516/338/205. Calibrated evaluation-call savings exclude 288 calibration responses. | `specs/results/magnitude_transfer_20261007.md` |
| Teacher restatement | 60 evaluation examples, four conditions, two budgets; 480 completed messages | Four-shot supplied-set fidelity is possible in this task. Frozen certification and supplementary scope-aware scores measure different things. | `specs/results/teacher_fidelity_20261007.md`; `specs/results/teacher_manual_review_20261008.md` |
| Teacher feedback reception | 60 examples with c1/c3; 120 cases, five arms; 600 parsed revisions | Restricted zero-shot improves mean error over natural zero-shot, but adds directions in sixteen cases. Its advantage over oracle is concentrated in changed messages, not uniform or information-matched. | `specs/results/teacher_receiver_20261008.md` |
| Target-known stopping replay | Saved 64-example shared-start trajectories; zero new generation | Nine otherwise lost convergence outcomes retained and 23/576 calls saved. This is not model-only stopping. | `specs/results/stopping_replay_20261007.md` |

These figures come from author-supplied completed production summaries and
checked repository implementations. This workspace has not independently loaded
the GPU-machine checkpoint folders. Software tests with simulated responses are
not additional model-performance evidence.

## Closed experimental requests and open scientific scope

Do not relaunch the already completed teacher few-shot/restricted controls,
shared-start study, magnitude transfer, or saved-output CPU audits because an
older chronological note says they are pending. The planned package is complete.

The remaining central content work is a raw-data availability audit for target
ambiguity, recovery of original diagnostic denominators/teacher provenance,
and author review of the revised claim hierarchy. These are primarily archival
and interpretation tasks. Human target judgments, unaided teacher geometry,
cross-model transfer, and downstream creative editing remain extensions unless
the paper is broadened to claim them.

## Decisions retained for the manuscript

1. Treat language as a graded control interface over recorded color states.
   Direction, magnitude, display projection, and stopping are distinct.
2. Keep original large-scale oracle gains as motivation and baseline evidence;
   do not describe them as proof that ambiguous names have a unique true color.
3. Present the new magnitude policy as a held-out policy comparison. Its benefit
   does not isolate the necessity of empirical calibration from the addition of
   magnitude information; numeric controls additionally supply precision/holds.
4. Replace the universal following-versus-generating claim with demonstrated
   distinctions among supplied-set fidelity, output-format compliance, and
   usefulness to the receiving guesser.
5. Use actual primitive-direction oracle examples, without inventing magnitude
   modifiers absent from the tested template bank. Appendix B labels these as
   implementation-generated illustrations, not historical recovered utterances.
6. Leave format, font, and page-layout work to the later Overleaf review. The
   current content checklist does not declare a submission-ready manuscript.
