# First manuscript revision — 2026-10-08 (Asia/Tokyo)

Working entry point: `paper/latex/color-games-revised.tex`.
New appendix sources: `paper/latex/revision-appendix.tex` and
`paper/latex/revision-legacy-results.tex`.
The imported original source, bibliography, ACL style, figures, and compiled
baseline remain unchanged; their checksums are recorded in the import manifest.

## Editorial changes

- Reframe the contribution as prompt-conditioned, graded language control:
  separate initial prediction, output encoding, direction interpretation,
  magnitude, teacher restatement, and feedback reception.
- Preserve the definition of Delta E76, while identifying error as disagreement
  with a recorded target, not uniquely correct meaning or human magnitude.
- Retain the original 12k oracle results and geometry/regime findings. Move
  detailed original diagnostic tables into a separate appendix.
- Add shared-start interface, isolated quantifier, held-out one-step and
  sequential magnitude-control, teacher-fidelity, and receiver evidence.
- Replace the broad following-versus-generating capability claim with the
  narrower conclusions supported by oracle-assisted, matched experiments.
  The historical teacher precision table is not used as revised evidence.
- Distinguish frozen certification from supplementary finite-grammar scope
  resolution and contextual AI review. None supplies independent human labels.
- Explain concentrated restricted-zero-shot gains, budget violations, unchanged
  message reception, and the noncausal saved-message decomposition.
- Document real oracle wording examples from the available implementation;
  these are illustrative code-generated messages, not recovered historical logs.
- Expand the AI assistance disclosure to match coding, experiment-management,
  manuscript-drafting, validity-filtering, and supplementary-review use.

## Evidence provenance

The revision uses author-supplied completed reports and checked repository
implementations, not newly run inference or access to GPU-machine checkpoints.
Full prompts and checkpoints remain on that machine. Evidence notes are in
`specs/results/` and `specs/revision_evidence_map.md`.

| Evidence | Run ID | Revised location |
|---|---|---|
| Isolated quantifier probe | `20261006_130637_580285_quantifier_study_a100_40gb` | Results 5.3; Appendix C.2 |
| Shared-start interfaces | `20261007_043619_593902_shared_start_interface_study_a100_40gb` | Results 5.2; Appendix C.1 |
| Saved-prefix stopping replay | same shared-start run | Discussion; Appendix D.3 |
| One-step magnitude control | `20261007_054337_204395_magnitude_control_a100_40gb_pilot` | Results 5.4; Appendices C.3, D.1 |
| Sequential magnitude transfer | `20261007_072214_768541_magnitude_transfer_a100_40gb` | Results 5.4; Appendix D.2 |
| Oracle-assisted teacher fidelity | `20261007_134620_125917_teacher_fidelity_a100_40gb` | Results 5.5; Appendix E |
| Teacher-feedback receiver/audit | `20261007_152230_242355_teacher_receiver_a100_40gb` | Results 5.5; Appendix E.2 |

The earlier independently predicted-start interface study is supplementary,
not the primary encoding comparison. Primary shared-start inference uses the
first revision; third-revision outcomes have subsequently adaptive feedback.

## Required interpretation boundaries

The numeric arm supplies extra precision and coordinate holds. Calibrated
versus bare feedback supplies different magnitude information; there is no
uncalibrated graded-selection arm isolating the necessity of fitting.
The 34.5% call reduction counts sequential evaluation revisions only, excluding
288 calibration responses and model-loading costs. Threshold stopping is
target-known, not a deployable model-only policy. Native coordinates and
displayed uint8 sRGB projection are kept distinct. Generated outputs are not
projection-filtered, repaired, or selectively replaced. Finite-sample clustered
intervals do not establish broad generalization, generation-randomness
uncertainty, equivalence, or multiplicity-adjusted significance.

## Validation and author checks

The committed main retains `inconsolata`, 11pt ACL review mode, and the imported
style. Exact-font compilation is unavailable in this workspace because that
font package is missing. A scratch-only copy substituting Courier compiles
with BibTeX, has no overfull boxes or undefined references/citations, and was
visually inspected. Its main conclusion ends on page 6; this is not a verified
publication-font page count. The diagnostic PDF is not committed or delivered
as a final paper.

Appendix tables use standard `float` package placement to prevent headings
becoming detached from their tables. The revised bibliography uses scoped
ragged-right wrapping; no font size, margin, or line-spacing reduction is used.

Before submission:

1. Compile the revised main in Overleaf with its actual font package, inspect
   all pages and the full log, and verify the venue's current length rules.
2. Verify original diagnostic subset sizes from recovered runs. The original
   prose/configs disagree about 1k/4k/12k chronology; the retained bandwidth,
   budget, ICL, and model-size appendix tables do not invent denominators.
3. Recover historical teacher-table metadata before any decision to reinstate
   those numerical claims. Omission here does not prove all prior scores were
   artifacts; it avoids using unresolved provenance for a general capability gap.
4. Check all reported figures against archived outputs, author/contribution
   details, data provenance/licensing, and the AI assistance disclosure.
5. Review the actual six same-direction-set changed messages before identifying
   a particular wording mechanism. Current contribution percentages are
   arithmetic descriptions, not causal claims.

No further GPU experiment is requested by this source revision. The draft
remains a first author-review version, not a submission-ready PDF.
