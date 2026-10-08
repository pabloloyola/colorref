# Content review and argument decisions — 2026-10-08

Scope: expert feedback, completed evidence, and the first revised manuscript.
Formatting is deliberately deferred. No new inference or fitting is performed.
The current concern checklist is `specs/revision_evidence_map.md`.
The subsequent source audit is `specs/results/content_source_audit_20261008.md`:
archival discrepancies and data-preservation behavior are checked; production
multiplicity counts and the six raw receiver pairs still require the supplied
CPU-only commands on the machine containing those files.

## Recommended central argument

ColorRef measures whether natural-language corrections produce useful color
updates. A correction needs an interpretable direction and a suitable step
size relative to the current state. Output encoding affects execution; display
projection and continued correction can undo otherwise valid movement. Teacher
messages must be evaluated both for what they preserve and what a receiver does
with them. These behaviors can be separated in a controlled color task.

The strongest new contribution is the progression from direction following to
graded magnitude control, with a frozen policy transferring to unseen starts.
The interface and teacher studies are important controls around that argument,
not unrelated additional benchmark axes. The original 12k evaluation supplies
large-scale evidence that interaction localizes recorded targets.

This framing retains grounded language as the motivation, while avoiding a
claim of direct access to internal understanding or uniquely correct color
semantics. Practical creative interfaces motivate the study; image-editing or
human-interface benefits are not demonstrated here.

## Claim hierarchy for the next prose pass

| Role | Content | Evidence and necessary limit |
|---|---|---|
| Foundation | Interactive feedback improves localization of recorded targets. | Original 12k error 40.58→22.32; keep disagreement-from-target interpretation. |
| Main new finding | Correct direction and ordinal wording alone do not ensure a useful step. | Controlled quantifiers, harmful direction-compliant one-step updates, and close-start drift. Native step choices and projection differ; no single causal mechanism is identified. |
| Main constructive finding | A frozen direction-specific wording policy improves held-out control over bare corrections. | One-step and fresh-start sequential studies; sequential error 6.461→2.979 and calls 516→338. Twelve starts are the clusters; call savings exclude calibration. |
| Supporting control | Output encoding and axis instructions influence correction from the same state. | Shared starts/first messages on 64 descriptions; primary first-revision and later adaptive endpoints remain distinct. LAB with a legend is not unaided perceptual grounding. |
| Supporting language finding | Faithful supplied-direction restatement and useful feedback are different outcomes. | Four-shot fidelity and unchanged-message receiver comparisons. Restricted zero-shot extras and concentrated gains prevent an information-matched superiority claim. |
| Secondary result | Feedback changes global behavioral geometry and target-known stopping retains reached success. | Original geometry results and saved-prefix replay; neither proves internal representation changes or deployable autonomous stopping. |

The title currently emphasizes behavioral geometry more than the expanded
argument. Revisit it after the content hierarchy is accepted; a candidate is
“ColorRef: Evaluating Direction and Magnitude in Natural-Language Color
Correction.” No title change is applied in this review.

## Expert checklist outcome

Direct-LAB and teacher few-shot/restricted-wording controls have been completed.
New teacher identity/settings and clause-budget coverage are explicit. These
address the missing experimental comparisons and disclosure concerns, without
settling unaided teacher geometry or the source of every historical error.

The single-target concern is addressed in interpretation, not empirically
resolved. Description validity cannot stand in for agreement with a target.
Repeated feedback can successfully localize an assigned target even when the
initial guess was linguistically reasonable. Abstract-regime improvements must
be described in this conditional sense throughout the paper.

The historical DP=0.11 claim remains unverified. The new pilot demonstrates
that word-level scoring can misread a correct comparative statement and that
few-shot answers can preserve supplied directions. It does not establish that
the historical numerical result was entirely a scorer or prompt artifact.
The revised manuscript appropriately retires the general capability-gap claim.

## Quantifier interpretation to preserve

There are three separate observations:

1. **Ordinal behavior:** a little, somewhat, and much usually produce ordered
   steps under the tested prompts. Nondecreasing scores include ties and do
   not imply correct-direction movement.
2. **Operational scale:** the emitted native and displayed step sizes vary with
   direction and starting state. The calibrated medians are descriptions of
   this model/prompt/sample, not universal or human-calibrated units.
3. **Execution/display consequences:** large proposals may overshoot or project
   into changes on unrequested coordinates, limiting target localization even
   when the requested direction is followed.

CIELAB is only approximately perceptually uniform, but equal coordinate step
magnitudes have equal Euclidean Delta E76 by definition. Consequently, an
observed directional difference in generated step sizes is not explained by
human perceptual nonuniformity alone. The restricted sRGB gamut and projection
are separate geometric constraints; a gamut boundary is not a prompt's numeric
coordinate bound or an empirically measured human magnitude scale.

The mathematical improvement condition, for a nonzero update u and target
residual v, is ||u|| < 2 ||v|| cos(theta). It explains why a positive directional
update can increase Euclidean error, without diagnosing the model's internal
reasoning. Direction compliance, ordering, target error, and stopping should
remain separate measurements.

## Claims to avoid or qualify

| Too strong | Supported replacement |
|---|---|
| “LLMs can follow corrections but cannot generate them.” | Tested teacher prompts differ in restatement and downstream utility; four-shot supplied-set preservation can be faithful. |
| “LAB eliminates grounding/output confounds.” | Shared-state interface controls expose sensitivity while retaining an instructed numeric interface. |
| “The model understands a little as a fixed perceptual distance.” | Under the tested prompt, a little produces a measured direction/state-dependent step distribution. |
| “Calibration is necessary.” | The frozen calibrated policy improves over bare direction; necessity relative to an uncalibrated graded controller is untested. |
| “Calibration saves 34.5% total compute.” | Sequential evaluation requires 34.5% fewer generations after a separate 288-response calibration; token and setup costs differ. |
| “Few-shot teachers are better.” | Few-shot supplied-set fidelity improves, but receiver accuracy does not uniformly improve. |
| “Restricted zero-shot wins because it adds information.” | Changed-message groups contribute to the observed mean arithmetically; additions and surface changes were not randomized. |
| “Abstract colors are predicted incorrectly.” | Abstract names have greater disagreement with their recorded targets in the original cohort. |
| “Stopping/self-correction is solved.” | Target-known stopping retains qualifying prefixes; subsequent oracle corrections can recover execution errors. |
| “This improves creative image editing.” | It motivates measurable direction/magnitude control for creative interfaces; downstream editing remains untested. |

## Remaining content tasks, in order

### 1. Historical evidence consistency — superseded by fresh replication

Update: the author confirmed that the original machine was wiped and historical
outputs cannot be recovered. Do not request them again. The completed fresh
1,000-description replication replaces historical grounding values in the
working main text. Unresolved historical tables remain archived and excluded
from its compilation. The recovery guidance below is historical, not a pending
task. See `specs/results/grounding_replication_20261008.md`.

Recover original run metadata for bandwidth, budget, ICL, model-size, and
historical teacher evaluations. Confirm subset sizes, selected IDs, model
revision/backend/settings, stopping rules, prompt templates and result-file
identity. Original prose/configs disagree about 1k/4k/12k chronology and
debug_400/debug_4000. Do not infer a denominator from a filename alone.

Decision rule: retain a numerical claim as fully specified evidence only when
its corresponding metadata can be established. If original diagnostic metadata
cannot be recovered, omit or explicitly quarantine that unresolved table in the
author draft; do not submit a table with an invented sample size. New matched
studies have frozen provenance and do not depend on reinstating old teacher DP.

### 2. Target-ambiguity data availability — next empirical-content audit

Audit the available source data before proposing human collection:

- Are repeated normalized descriptions paired with different HEX targets?
- Are there per-description alternative targets or agreement judgments, or are
  evaluation scores only ratings of whether a string is a valid description?
- Can repeated entries be distinguished from duplicate records, spelling
  variants and parser-normalization collisions?
- Does any usable agreement evidence overlap the actual evaluation examples?

If repeated-name evidence exists, summarize recorded target dispersion by
regime with occurrence counts and preprocessing sensitivity. That describes
dataset multiplicity; it is not independent human semantic ground truth.
If it does not exist, keep the single-target limitation explicit. Independent
alternative-color judgments are needed only to claim that a prediction is
semantically inappropriate, rather than far from the assigned target.
This audit has not been run in this workspace: the HF data repository is private
and the production/source data are not present locally.

### 3. Trace review for concrete examples — existing outputs, no new model calls

Inspect the six restricted-zero-shot messages that changed text while
preserving the lexical direction set before attributing their contribution to
word order or another surface mechanism. The supplied aggregate audit identifies
their count/contribution, not the six raw pairs. Select one faithful-but-unhelpful
receiver example and one direction-correct harmful magnitude example for an
explanation tied to actual traces, with all selected examples labeled illustrative.
Avoid choosing examples as independent estimates of failure prevalence.

### 4. Second content pass — after the consistency decisions

Rewrite the abstract and introduction around the main direction/magnitude
question. Keep the large-scale oracle result as foundation and the held-out
policy result as the constructive contribution. Summarize the interface and
teacher controls succinctly, then explain their implications in Discussion.
Retain exact protocol differences and unresolved issues in the relevant methods
and limitations, without repeating every diagnostic caveat in every paragraph.

The current first rewrite is usable for this pass; it contains the required
evidence and safeguards but gives several diagnostic results similar narrative
weight. This review records the hierarchy without yet changing the title or
applying another full prose rewrite.

## Additional experiments: scope-dependent, not the next default action

- An uncalibrated graded-selection comparator would be required for a strong
  claim that fitting itself is necessary. Current wording does not claim that.
- Additional models/starting-color samples would be required for broad transfer
  claims. Current conclusions are conditional on one model/prompt family.
- Unaided teacher geometry would be required for a general producing-versus-
  receiving capability comparison. The revised paper claims oracle-assisted
  restatement and receiving behavior instead.
- Human judgments or an editing interface would support semantic/perceptual
  and downstream creative claims. They are extensions, not completed evidence.

Proceed with the archival/data-availability checks and content hierarchy first.
No GPU experiment is requested by this content review. Formatting remains
deferred as requested by the author.
