# Development rules

- Keep `azhyphen` standalone: do not add Babel or Polyglossia dependencies.
- Support both LuaLaTeX and XeLaTeX. Preserve the zero-configuration document
  interface `\usepackage{azhyphen}` and global activation on package load.
- Treat `tex/latex/azhyphen/azhyphen.pat.txt` and `azhyphen-data.json` as
  generated synchronization outputs. Never edit them by hand or substitute
  fixture data for production patterns.
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
- Run `make update` for a complete pattern refresh and `make test` for runtime
  changes. Pattern updates do not automatically change versions, create
  releases, commit, tag, or push.
- The documented 2/2 hyphenation minima are provisional pending Azerbaijani
  linguistic and typographic review; do not change them without authoritative
  evidence.
