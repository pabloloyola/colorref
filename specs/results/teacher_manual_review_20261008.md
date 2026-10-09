# Full-checkpoint confirmation and assistant review of unresolved feedback

Run: `20261007_134620_125917_teacher_fidelity_a100_40gb`.
The author supplied the full-checkpoint supplementary report on 2026-10-08
(Asia/Tokyo). It reports 480 validated raw responses, zero aggregate-only
records, and exactly reproduces the earlier selected-export audit counts.

The following is an **assistant-authored, post-hoc contextual review**, not
an independent human annotation study or a replacement primary metric.
It covers all 22 unresolved natural-zero-shot messages. Required directions,
raw messages and descriptions were checked against the original uploaded
diagnostic JSON; named descriptions can refer to the target rather than
necessarily introducing a new object. Direct suggestions are interpreted
in the task context. Bright/dark, green/red and saturation/muting follow
the task's operational vocabulary; this is not general color semantics.

## Review judgments

All IDs below have condition `natural_0`. Match means preservation of the
supplied direction set under the contextual reading described; mismatch
means a different implied set, not necessarily entirely geometrically wrong
feedback. Broad or missing reference frames remain ambiguous.

| Example / budget | Judgment | Reading and reason |
|---|---|---|
| 254476 / c1 | Match | `lilac rug` is the actual target description. Guess more muted than that target implies more saturated. |
| 239370 / c3 | Mismatch | Too bright/too yellow/not muted enough implies darker, more blue, more muted; the supplied set asks for more red rather than more blue. |
| 468991 / c1 | Mismatch | `the unknown ocean` is the target description. Guess more blue than target implies more yellow under the axis vocabulary; supplied direction is more red. |
| 468991 / c3 | Mismatch | Comparison to the named target implies lighter, more green, more saturated; supplied directions are darker, more red, more muted. |
| 146560 / c3 | Match | Too bright/saturated/yellow implies darker, more muted, more blue. |
| 57135 / c3 | Match | Explicit suggestions `could be more blue and slightly more muted` match both supplied corrections; the opening saturated clause gives no explicit comparison reference. This judgment concerns the explicit actionable suggestions. |
| 115393 / c3 | Mismatch | Explicit guess-versus-target comparison implies more saturated, darker, more red, reversing the supplied muted/lighter/green directions. |
| 334965 / c3 | Ambiguous | Describes the guess as muted/lighter/redder without a target comparison or adjustment command. Cannot safely choose a reference frame from the required answer. |
| 289386 / c3 | Match | Too muted/light/not red enough implies more saturated, darker, more red. |
| 195752 / c3 | Match | Too saturated/green/dark implies more muted, more red, lighter. |
| 343339 / c1 | Match | Bare `More saturated.` is an adjustment in this feedback task. |
| 234668 / c3 | Match | Too light/yellow/saturated implies darker, more blue, more muted. |
| 329040 / c3 | Match | `Make it darker, more saturated, and add more green` preserves all three corrections. |
| 480326 / c3 | Match | Too saturated/dark plus could use more blue implies more muted, lighter, more blue. |
| 346428 / c3 | Mismatch under inclusive reading | Explicit command preserves muted/blue/green, but `too bright` additionally implies darker. If evaluating only the explicit command this would match; retain this scope sensitivity rather than treating it as an unequivocal wrong-direction output. |
| 278520 / c1 | Match | Too dark and needs to be lighter explicitly asks for lighter. |
| 279454 / c1 | Match | Too dark; try making it lighter explicitly asks for lighter. |
| 279454 / c3 | Ambiguous / problematic | Darker implies lighter, but gray and closeness-to-blue are broader relations. A primitive-axis reading of the blue comparison would oppose the supplied more-blue direction, and no red correction is explicit. Do not force arbitrary closeness language into one LAB axis. |
| 340456 / c1 | Ambiguous | `Your guess is more blue.` lacks the target relation or a command. The literal blue word is insufficient to choose adjustment versus state description. |
| 304931 / c3 | Match under task-axis reading | Lighter/saturated/closer to green than target implies darker/muted/red if green proximity is read as the task's red-green direction. This operational reading is broader than the finite grammar; keep that assumption visible. |
| 78640 / c1 | Match | Too light; try making it darker explicitly asks for darker. |
| 408159 / c3 | Match | Too muted/dark/red compared to target implies more saturated, lighter, more green. |

Under these stated contextual readings: 14 matches, five mismatches and three
ambiguous cases. Two judgments have important scope/vocabulary qualifications
(346428 and 304931); 57135 evaluates the explicit suggestions rather than
inventing a reference for the opening clause. These numbers are assistant review
notes, not independently established accuracy estimates. The finite-grammar
report remains 81 matches / 17 mismatches / 22 unresolved for natural zero-shot.
Do not silently merge these review judgments into its primary counts or intervals.

## What the evidence supports

The earlier lexical audit substantially understates faithful comparative
feedback in this matched pilot. All four-shot outputs preserve the supplied
sets under the supplementary grammar when all checkpoints are included.
Neither observation establishes that the original paper's historical teacher
table is entirely an artifact. Exact-set fidelity, geometric validity,
format compliance and receiving-guesser usefulness remain distinct outcomes.

If this review is used in a manuscript, have an independent human review the
labels under explicit guidelines and retain disagreements and scope-sensitive
cases. Identify the assistant's role in preparing the review. No model outputs,
demonstrations, prompts, frozen scores or finite grammar were changed after this
review, and no evaluation response is used to fit a controller.

## Next receiving-guesser control

Use the frozen 60 evaluation examples at c1/c3 from this teacher run. For each
of 120 example/budget cases, provide the same displayed starting HEX state and
description to five receiving conditions: original natural_0, natural_4,
restricted_0, restricted_4 messages, and canonical oracle feedback. This gives
600 fresh-context, single-revision generations with one shared guesser interface,
model, decoding setup and output budget. Pass original messages unchanged;
do not repair comparisons, remove Feedback labels or select cases based on
their audit label. The canonical oracle is the baseline, not a generated teacher.

The guesser must receive only the description, current state and feedback, not
the target HEX, oracle constraint JSON or review annotation. Preserve all
failures and native/displayed results; report target error and gain, constraint
satisfaction, alignment, projection and generation diagnostics. Paired analysis
resamples whole examples within regimes, keeping c1/c3 together; include common
matched cohorts and available-pair sensitivity. Compare natural comparative
feedback with canonical corrections on the same case, not across independently
generated initial guesses. This tests useful feedback in this supplied-start
pilot, not unaided teacher geometry or general interactive performance.
