# Development rules

- Keep `azhyphen` standalone: do not add Babel or Polyglossia dependencies.
- Support both LuaLaTeX and XeLaTeX. Preserve the zero-configuration document
  interface `\usepackage{azhyphen}` and global activation on package load.
- Treat `tex/latex/azhyphen/azhyphen.pat.txt` and `azhyphen-data.json` as
  generated synchronization outputs. Never edit them by hand or substitute
  fixture data for production patterns.
- Treat the localization repository as the sole source of public model
  statistics. Keep `docs/model-stats.json` synchronized with the canonical
  patterns from the same localization commit.
- Never edit the README statistics block by hand. It is delimited by
  `AZHYPHEN-STATS` markers and generated from `docs/model-stats.json`.
- Treat `VERSION` as the only manually maintained package version. Run
  `make version` after changing it; do not hand-edit the generated TeX version
  file, README badge block, or `CITATION.cff`.
- Keep software versions independent of annotation counts, pattern counts, and
  evaluation metrics. Versions below 1.0.0 are development releases.
- Require public `pattern_count` to match the canonical runtime pattern count;
  stale or mismatched statistics must fail synchronization and consistency
  checks.
- The linguistic source of truth, including PATGEN training and evaluation
  material, lives outside this repository. Runtime code must never depend on
  paths or files in that external project.
- Keep the runtime small and use LuaTeX's native language and hyphenation
  facilities for LuaLaTeX and TeX Live's named, format-time language
  registration for XeLaTeX. Do not add a custom hyphenation algorithm.
- Maintain exactly one canonical pattern dataset, `azhyphen.pat.txt`. Any XeTeX
  loader must be mechanically derived and verified, never edited as a second
  linguistic source.
- Keep the Azerbaijani case and hyphenation-character mappings covered by
  integration tests, especially `i`/`İ` and `ı`/`I`.
- Use ignored `local.mk` or an explicit `PATTERNS=...` override for local source
  configuration. Never place external paths in public generated files.
- Preserve the distinction between fixture/runtime tests and real-pattern
  tests across both engines. Fixture data must never contaminate the bundled
  runtime snapshot.
- XeTeX installation must remain user-level, reversible, idempotent, confined
  to `TEXMFHOME`/user format storage, and preserve unrelated registrations.
- Do not add pdfLaTeX, Babel, or Polyglossia as supported runtime backends.
- Run `make update` for a complete pattern/statistics refresh and `make test`
  for runtime changes. Data updates do not automatically change versions,
  create releases, commit, tag, or push.
- The documented 2/2 hyphenation minima are provisional pending Azerbaijani
  linguistic and typographic review; do not change them without authoritative
  evidence.
