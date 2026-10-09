# Minimal manuscript and Overleaf import — 2026-10-09

Pre-cleanup branch head: `0ec264f7703267fea6f06a63f18f607c791225db`.
The user requested removal of unused paper files and an easy Overleaf import.
This is a file-layout change, not a manuscript rewrite or new experiment.

## Active project

`paper/overleaf/` contains eight compile dependencies, with project-local paths:

| Previous path under paper/latex/ | Current path under paper/overleaf/ |
|---|---|
| color-games-revised.tex | main.tex |
| revision-appendix.tex | appendix.tex |
| custom.bib | references.bib |
| acl.sty | acl.sty |
| acl_natbib.bst | acl_natbib.bst |
| figures/reference_game.pdf | figures/reference_game.pdf |
| figures/southern_lime_green.pdf | figures/southern_lime_green.pdf |
| figures/calibration_effects.pdf | figures/calibration_effects.pdf |

Only figure/include/bibliography paths in the main source change. Reversing
those substitutions reproduces the previous source exactly. Appendix, bibliography,
style files and all three figure PDFs are byte-identical. The existing compiled
reading PDF is retained unchanged outside the import project.

`paper/colorref-overleaf.zip` contains the eight files directly at archive root,
with no enclosing folder, compiled main PDF, bibliography outputs, data or
previews. `scripts/package_overleaf.py` rebuilds and validates it deterministically.
The one active TeX project is the editable source; the ZIP is its import snapshot.
No content sections were split or rewritten as part of the cleanup.

## Supporting artifacts and removals

The compact trajectory export/manifest move unchanged from `paper/evidence/`
to `artifacts/paper/evidence/`. Selected trajectory and calibration estimate
JSON files move from the old figure folder to `artifacts/paper/figure-data/`.
The gallery PDF and ZIP move to `artifacts/paper/galleries/`.
Their original blob content is preserved; these artifacts are not needed to
compile the manuscript. Reproduction scripts use the new paths and put PNG
previews under generated `reports/`, rather than in the active paper folder.

Unused original/legacy TeX sources, the swatch-table include, LuaLaTeX example,
historical unreferenced figures, duplicate previews and the imported baseline
are removed from the active tree. They remain retrievable in the complete
pre-cleanup Git commit above. A local backup was kept while performing the
restructure. The loose locally generated gallery was not tracked; the preserved
ZIP retains its individual assets without duplicating them in the source tree.

The paper README is replaced with concise editing, compilation and Overleaf
instructions. Root README and current evidence-map paths are updated. Earlier
chronological notes intentionally retain the paths used at the time; use the
mapping above when following old notes.

## Validation

- Verify exact manuscript equivalence after reversing only path substitutions.
- Verify unchanged supporting source/figure/PDF bytes and moved artifact hashes.
- Validate all eight ZIP members, CRCs, relative paths and source identity.
- Compile the extracted ZIP in an isolated directory without repository TeX
  search paths. Only the extracted diagnostic copy substitutes Courier because
  local Inconsolata is absent; the archive retains the publication font package.
- The build has no overfull boxes or unresolved reference/citation warnings.
  All 20 extracted-page texts and rendered PNGs are identical to the previously
  inspected complete reading draft. A rendered page was also visually checked.
- Run both figure scripts and the 16-case gallery rebuild in an isolated fixture;
  verify their new output/evidence paths and the complete gallery archive.

The import bundle is structurally complete and locally compile-checked. It has
not been uploaded into the author's Overleaf account or compiled there. Final
font/page-limit review and full raw-checkpoint reconciliation remain separate.
