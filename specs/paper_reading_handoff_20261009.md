# Paper reading handoff — 2026-10-09

The content pass is complete for the current scoped argument. Read the revised
manuscript in full before deciding whether to expand the experiment scope.
The current evidence/claim checklist is `manuscript_content_audit_20261009.md`.

## Evidence consolidation

`paper_evidence_inventory.json` lists ten completed production runs and their
sampling units. It distinguishes author-reported outcomes from independently
available raw checkpoints. Historical results lost with the old machine remain
excluded. Stopping replay and saved-output diagnostic reports are collected
with their parent runs; the two source inventories are additional files.

The GPU machine is the remaining source of the complete run folders. After
pulling the current branch, run this once with all run/analysis writers stopped:

```bash
uv run python scripts/export_paper_evidence.py \
  --include-raw \
  --output reports/content_audit/colorref-paper-evidence-20261009.zip
```

This exports saved config, metadata, input snapshots, metric JSON, text reports
and raw JSON/JSONL checkpoints, with per-file SHA256 hashes and missing-file
counts. It excludes weights, dataset parquet files, environment files and
credentials. No generation, controller fitting or report regeneration occurs.
An existing ZIP is never overwritten. Keep this archive outside Git, back it
up separately, and share it for the later raw-evidence reconciliation.
Omit `--include-raw` for a smaller reports/plans/metrics bundle if needed.
The exporter detects availability and preserves bytes; it does not certify
scientific correctness or that every checkpoint is complete. A missing run
does not become a successful experiment through export.

Focused fabricated-fixture checks verify archive hashes, optional raw outputs,
missing-run reporting, refusal to overwrite, input preservation and rejection
of symlinked files. They are software checks, not new performance evidence.

## References and scope

Checked the currently cited color-language, grounding, feedback and model
references against ACL Anthology, publisher/proceedings pages, author copies
or arXiv records. The Bayesian color-semantics entry now uses the verified
DOI and publisher; its existing Brian McMahan author name was correct.
The working draft cites the verified CIE 015:2018 technical report rather
than the malformed inherited 1986 entry, and now cites the Gemma 4 technical
report recommended by the official model card. The original 1986 entry is
retained for the archived source. The Lewis 2008 entry describes a reprint,
so its historical-looking BibTeX key is not evidence of a wrong date.
The NeurIPS Reflexion author list matches its conference version; arXiv has
a different author list and was not substituted for the cited proceedings.

Reference anchors:

- https://aclanthology.org/Q15-1008/
- https://aclanthology.org/Q17-1023/
- https://aclanthology.org/2021.conll-1.9/
- https://aclanthology.org/2023.findings-emnlp.102/
- https://aclanthology.org/P18-2125/
- https://aclanthology.org/2021.naacl-main.320/
- https://aclanthology.org/2025.ranlp-1.53/
- https://aclanthology.org/2020.emnlp-demos.6/
- https://cie.co.at/publications/colorimetry-4th-edition
- https://arxiv.org/abs/2505.09388
- https://arxiv.org/abs/2607.02770
- https://huggingface.co/google/gemma-4-12B-it
- https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html
- https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html
- https://arxiv.org/abs/2203.02155
- https://arxiv.org/abs/2206.05802
- https://arxiv.org/abs/2212.08073
- https://onlinelibrary.wiley.com/doi/book/10.1002/9780470693711
- https://www.nogsky.com/publication/2018a-pnas/2018a-PNAS.pdf
- https://langcog.stanford.edu/publications
- https://cocolab.stanford.edu/publications

Removed the unsupported quantitative-sounding "most evaluations" framing in
the introduction and narrowed its protocol description to the studies actually
reported. No experimental outcome changes. This is a reference integrity and
claim-support check, not an exhaustive literature/novelty search. The exact
1991 Berlin/Kay reprint remains inherited; no accessible publisher page was
retrieved to independently resolve its edition details.

## Reading and submission checks

The fresh PDF includes the main paper, bibliography and appendices. A temporary
Courier substitution permits local compilation; the committed source keeps
the original Inconsolata package. Publication-font layout and the eventual
conference page limit are separate checks for Overleaf after author review.
The reading copy is not a submission-ready declaration.
The temporary-font reading builds are checked for overfull boxes and unresolved
citations/references, and all rendered pages are visually inspected.
All 22 cited keys resolve and the bibliography has no duplicate keys.

Before submission, reconcile the exported production configs and analysis JSON
with the manuscript, including actual resample counts, matched denominators,
model/environment versions and figure inputs. These checks cannot be completed
from pasted summaries alone. For the full read, focus on whether the calibration
contribution is clear, whether the supporting controls earn their space, and
whether the limits match the claims. New experiments remain a subsequent
decision rather than an automatic next step.

## Narrative revision after author feedback

The author found that the calibration-centered revision lost the original
game explanation and introductory motivation. The abstract and introduction
now follow motivation, color as a measurable reference domain, the hidden-target
guesser/teacher game, direction versus magnitude, and receiver calibration.
Supporting controls are connected back to the game without presenting isolated
single-axis studies as full interactive-game evaluations.

A new vector schematic uses constructed colors/messages and explicitly says
it is illustrative. No archived empirical trajectory or lost-run number is
reintroduced. Experimental results, confidence intervals, denominators, and
limits are unchanged. The compiled reading PDF is committed at
`paper/colorref-reading-draft-20261009.pdf` so it can be opened on GitHub.

The narrative-revised temporary-font build has 16 pages; its log has no
overfull boxes or unresolved references/citations, and all pages were rendered
and visually inspected. The introductory schematic appears as Figure 1.
