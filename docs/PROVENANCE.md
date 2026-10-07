# Bundled data provenance

The canonical patterns and public statistics originate in Anar Abdullayev's
localization project. On 2026-10-07, the maintainer confirmed ownership of the
pattern-generation/export pipeline and the right to distribute these generated
artifacts under LPPL 1.3c or later. The pattern files were not copied from a
third-party upstream package.

The current source snapshot is localization commit
`edd922da04b7e64a2bb081941cc41420f51a6f07`, containing both:

- `experiments/patterns.pat`, imported byte-for-byte as
  `tex/latex/azhyphen/azhyphen.pat.txt`;
- `experiments/public-stats.json`, exported from the matching experiment results
  and run archive, and synchronized as `docs/model-stats.json`.

The export validator and its tests are included in that source commit. The
upstream `experiments/PROVENANCE.md` records the grant for these two artifacts.
The upstream repository is separate and has no public URL configured at the
time of this audit; this commit identifies provenance, but is not a public
promise that training inputs can be downloaded or redistributed.

`azhyphen-data.json` records the canonical pattern checksum and the checksum of
the mechanically generated `azhyphen-xetex.tex`. Rebuild both using
`scripts/sync_data.py` through `make sync`; the loader is not a second linguistic
source. `azhyphen.hyp.txt` is an intentionally empty exceptions file pending
review. Files in `tests/fixtures/` are synthetic test data, not production data.

The bundled snapshot permits deterministic package builds and tests without
the upstream project. Reproducing PATGEN training or the reported evaluation
requires access to that project's corpus, annotations, and experiment archive.
Its wider application/corpus licensing is separate from the grant for these
exported artifacts.

When importing a new snapshot, verify both source files at the same commit and
update this record. See the repository's `LICENSE` and `LPPL-1.3c.txt` for the
distributed work's terms.
