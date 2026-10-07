# Revision evidence map

Based on the attached expert review, the submitted PDF, repository source audited at commit `51d1ec7`, and user-provided production summaries. This document distinguishes observed results, source-code checks, proposed wording, and experiments still to run. It is a revision draft, not a new manuscript submission or a claim that all review concerns are resolved.

## Evidence and action matrix

| Concern | What we can establish now | Remaining action | Paper change |
|---|---|---|---|
| Output encoding versus color grounding | In the matched 64-example diagnostic, HEX has lower final error than plain LAB; an axis legend substantially improves LAB. Exact coordinate controls in the separate quantifier study are almost always executed correctly. | The shared-start control is completed; inspect remaining trajectory/magnitude failure cases and retain uncertainty at the primary first-revision endpoint. | State output representation and axis instructions explicitly. Treat the interface results as diagnostic protocol comparisons. |
| Ambiguous crowdsourced targets | Current error is distance to one recorded target, not a measure of whether every alternative color is linguistically implausible. Strong recovery from feedback shows localization of that assigned target. | Audit raw data for repeated descriptions, alternative targets, or per-color votes; distinguish description-validity scores from agreement about a target. If these data are absent, collect human alternative-color judgments for a modest stratified sample. | Replace broad statements that abstract descriptions are intrinsically wrong/noisy with disagreement from the recorded target. Bring this qualification into dataset/metrics/results prose. |
| Following versus generating is only tested zero-shot | Existing teacher conditions are zero-shot; guesser ICL is not evidence about teacher few-shot performance. | Run few-shot teachers, starting with oracle-assisted feedback; compare demonstrations at fixed feedback constraints and output budgets. | Narrow the teacher claim to the evaluated zero-shot configurations until these controls exist. |
| Oracle-assisted paraphrases may change meaning | The current prompt explicitly asks for a natural paraphrase and permits warmer/cooler and gray/less-gray phrases outside the oracle's primitive directions. | Compare unrestricted and exact-direction wording, each zero-shot and few-shot, using matched target/guess states and the same oracle directions. Audit additions, omissions, substitutions, and reversals separately. | Present the old result as a prompt-conditioned failure rather than a demonstrated inability to restate correct feedback. |
| The matched-vocabulary ceiling might not match teacher language | In current `TemplateOracleLLMVocab`, candidate directions are still the eight primitive L/a/b/saturation directions. Added dictionary entries for warmer/cooler/gray/less-gray are not selected. For turns with selected constraints, the emitted text therefore matches `TemplateOracle` at the same settings; their no-candidate fallback messages differ. | Recover actual ceiling messages and bandwidth from the paper's runs; compare controls that match the emitted direction count and evaluated phrase family. | Treat the available implementation as a valid primitive-direction oracle control, not evidence that broad-vocabulary teacher feedback would succeed if geometrically correct. |
| Clauses might force lossy compression | In the available implementation, `_oracle_constraints()` and `max_clauses` both use `self.max_n`. The current archived oracle-assisted debug config sets it to one. | Inspect the actual rendered prompts/configuration of the paper's `debug_4000` run when available. | The available source does not demonstrate a constraint-count/clause-budget mismatch; do not assert that it caused DP=0.11. |
| Teacher model identity is missing | The current archived debug configs explicitly specify Qwen/Qwen3-14B for both roles, with separate aliases; guesser budget 64 tokens and teacher budget 80. These configs point to `debug_400`, whereas the PDF's teacher table says `debug_4000`. | Recover metadata for the exact table-producing runs before attaching that identity to the published numbers. | Report teacher and guesser model, backend, thinking mode, token budgets, and prompt condition alongside the teacher results. |

## A concrete appendix correction

Appendix A.5 currently gives template examples containing “a little” and “a bit.” Those examples were drafted earlier in the conversation but are absent from the current `TemplateOracle` phrase bank. This matters because the new quantifier study shows that magnitude modifiers can change the size of an update. They should not be used as examples of an experiment that varied canonical direction wording without those modifiers.

The following outputs were generated directly by the current oracle code for a reproducible illustrative state: target `#a0b0c0`, guess `#805000`, `example_id=0`, `seed=13`, feedback turn 0. The selected direction ordering is muted → lighter → blue. These are code-generated illustrations, not recovered historical experiment outputs.

| Condition | Exact feedback |
|---|---|
| minimal c1 | Make it more muted. |
| axis c1 | Make it more muted. |
| axis c2 | Make it more muted and lighter. |
| axis c3 | Make it more muted, lighter, and more blue. |
| template c1 | Make it less saturated. |
| template c2 | Make it less saturated. Move toward a brighter shade. |
| template c3 | Make it less saturated. Move toward a brighter shade. Move it toward blue. |

Copy-ready LaTeX for the appendix example block:

```latex
For a target color \texttt{\#A0B0C0} and current guess
\texttt{\#805000}, the oracle selects the directions
\emph{more muted}, \emph{lighter}, and \emph{more blue}, in that order.
The following examples are generated by the implementation with
example ID $0$, seed $13$, and feedback turn $0$.

\begin{center}
\small
\begin{tabular}{@{}lp{0.64\columnwidth}@{}}
\toprule
Condition & Example feedback \\
\midrule
minimal$_{c1}$ & Make it more muted. \\
axis$_{c1}$ & Make it more muted. \\
axis$_{c2}$ & Make it more muted and lighter. \\
axis$_{c3}$ & Make it more muted, lighter, and more blue. \\
template$_{c1}$ & Make it less saturated. \\
template$_{c2}$ & Make it less saturated. Move toward a brighter shade. \\
template$_{c3}$ & Make it less saturated. Move toward a brighter shade.
Move it toward blue. \\
\bottomrule
\end{tabular}
\end{center}

The template conditions express the same selected constraints using
deterministic alternative phrases; they do not introduce graded modifiers
such as \emph{a little} or \emph{much}. We study those modifiers separately
in the quantifier experiments.
```

The paragraph column allows feedback text to wrap rather than creating a long unbreakable condition list. Rendering must be checked in the actual paper source; the current workspace has the submitted PDF, not its LaTeX project.

## Results that can already enter the revision

### Output-interface diagnostic

Draft paragraph:

> A matched diagnostic on 64 examples tests sensitivity to output representation and explicit coordinate instructions. Among the 61 examples with complete parsed trajectories in every condition, final displayed-color error is 22.94 ΔE76 for HEX, 46.72 for plain LAB, and 29.39 for LAB with an axis legend. The legend improves LAB directional alignment from 0.353 to 0.782. These results show that representation and instruction choices materially affect measured performance. Because the conditions produce different initial guesses, their improvement magnitudes do not isolate feedback following alone. The comparison uses three fixed rounds and displayed-state feedback, and therefore differs from the main experiment's early-stopping protocol.

Report the full denominator next to this paragraph: 192 completed games, three legend-condition parse failures, 61/64 common fully parsed triplets. Do not combine this diagnostic's means with the original 12,000-example results or interpret its small regime groups as a replication of all earlier regime findings.

### Shared-start feedback-following control

The user completed the 64-example control with identical displayed starts and first corrections, 576/576 parsed revisions, and no missing matched cases. Detailed results are in `specs/results/shared_start_20261007.md`.

Draft paragraph:

> To separate initial prediction from subsequent correction, we supply the same HEX-derived displayed starting state to each interface. Across 64 matched examples, first-revision error is 32.10 ΔE76 for HEX, 38.29 for plain LAB, and 32.58 for LAB with the axis legend. Plain LAB exceeds HEX by 6.19 [0.85, 11.89] ΔE76, while the legend's first-revision improvement over plain LAB is uncertain (-5.71 [-11.44, 1.41]). After three fixed revisions, final errors are 22.78, 35.28, and 23.16, respectively; legend minus plain LAB is -12.11 [-18.04, -5.49]. Thus, output/prompt choices affect correction even when starts are held fixed. The similar HEX and legend mean endpoints do not establish equivalence, and later feedback is adaptive rather than identical.

Intervals are paired regime-stratified percentile 95% intervals over the fixed cohort. Qualify findings as conditional on this HEX-derived start policy, single model, and prompting intervention. All outputs parsed, so this run has no parse-based cohort exclusion. Its forced rounds differ from the main paper's early stopping. Best-so-far error uses knowledge of the target and is not an automatically available editing policy.

### Operational interpretation of quantifiers

Draft paragraph:

> Isolated adjustment probes separate verbal direction and magnitude instructions from color-name prediction. Across 12 fixed starting colors, explicit LAB axis instructions increase correct-direction qualitative updates from 228/288 to 288/288, while exact 5- and 10-unit controls and no-change controls are nearly always executed correctly. The exception is one legend-condition 10-unit update that instead changes the requested coordinate by 20. Quantifier ordering improves with the axis legend, but large updates often have substantial sRGB projection error. Consequently, reliable direction and ordinal magnitude interpretation do not by themselves guarantee usable displayed-color corrections.

Keep the distinct units clear: qualitative direction uses 288 individual responses per prompt; strict ordinal ordering uses 216 within-start/direction pairs per prompt. These are overlapping comparisons over 12 fixed anchors, not 216 independent colors. There is no hidden intended target for qualitative quantifier probes, so their numerical headroom fraction does not measure a fraction of remaining target distance.

### Teacher result, pending the required controls

Replace the subsection heading “Following feedback is easier than generating feedback” with:

> Zero-shot teacher feedback under the tested prompts

Proposed replacement for the strongest conclusion in that subsection:

> Under the evaluated zero-shot teacher prompts, generated corrections are less reliable than deterministic oracle feedback. This comparison identifies a failure of the tested feedback-generation pipeline; it does not establish a general capability gap between receiving and producing corrections. The oracle-assisted condition supplies valid directions but asks the model to paraphrase them using a broader vocabulary, so its failures may reflect the wording instructions. Few-shot teacher prompting and direction-preserving output restrictions are needed to distinguish these explanations.

Apply the same narrowing to the abstract's final sentence, the introduction's teacher preview, the discussion paragraph, the conclusion, and Figure 1/Table 7 captions. A single anecdotal paired trajectory illustrates a prompt-conditioned failure, not a universal asymmetry.

### Target interpretation

Suggested metric clarification:

> We interpret ΔE76 as disagreement from the dataset's recorded color target. It measures accuracy in locating that assigned target, rather than ruling out other colors that a speaker might reasonably associate with the description. This distinction is especially relevant for abstract and idiosyncratic names; interactive recovery demonstrates localization from feedback without establishing that the original prediction was semantically implausible.

## Evidence still needed before stronger conclusions

1. Inspect saved trajectory diagnostics, including the shared-start initially converged case. Run the existing CPU trajectory analysis. It produces paired intervals, fixed-cohort turn curves, available-pair sensitivity to failed third interfaces, and checks for initially correct guesses drifting away under forced rounds.
2. The shared-start comparison is completed with all 64 matched examples and no parse failures. See `specs/results/shared_start_20261007.md`. Interpret its first-revision and final endpoints separately; near-equal HEX/legend means do not establish equivalence. Additional starting-state/model replications would extend the current conditional result.
3. Run the restricted/unrestricted × zero-/few-shot oracle-assisted teacher comparison on held-out matched states. Set the clause budget at least as large as the supplied direction count and log both values. Canonical directions must be preserved exactly in the restricted condition; magnitude language is excluded so the audit does not mix direction fidelity with step-size effects. Demonstration examples must be separate from evaluated examples/descriptions. Reuse one model instance for same-model teacher/guesser calls on the A100, or audit teacher outputs offline on frozen states; do not require two independent 14B model loads.
4. Audit the source data's target ambiguity. Description validity and target agreement are separate measurements; do not assume that a high validity score is low target ambiguity.
5. Evaluate a magnitude-calibrated oracle on held-out examples after directions and output compliance are controlled. Fit language-to-step behavior on a calibration split and compare target-distance error, overshooting, off-axis movement, and projection cost on a separate evaluation split at matched feedback budgets. Creative editing remains a motivation until this downstream benefit is demonstrated.

## Central framing for the revision

ColorRef measures natural-language control of color predictions. Its decomposition should distinguish initial target prediction, output representation, direction following, magnitude interpretation, and feedback generation. Current evidence supports substantial protocol sensitivity and benefits from valid feedback; teacher-side generalizations need additional controls, and creative-application claims need held-out target-localization evidence.
