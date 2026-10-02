# azhyphen

`azhyphen` provides standalone Azerbaijani hyphenation for LuaLaTeX and XeLaTeX.
It does not require Babel or Polyglossia.

```tex
\documentclass{article}
\usepackage{azhyphen}

\begin{document}
Azərbaycan dilində mətn burada yazılır.
\end{document}
```

Loading the package activates Azerbaijani hyphenation globally.

Supported engines:

- LuaLaTeX
- XeLaTeX

pdfLaTeX is not currently supported.

## Status

The runtime, synchronization workflow, installation rules, and integration tests
are implemented. A real production pattern file is intentionally not fabricated
by this repository: synchronize the external PATGEN output before normal use,
installation, or validation with real patterns. The longer-term goal is a CTAN
and TeX Live release after the pattern data and linguistic choices have been
reviewed.

The current left and right hyphenation minima are both **2**. This conservative
default is applied by both engine backends and awaits linguistic review.

## Development and installation

For a local checkout, make the package visible to LuaLaTeX with:

```sh
export TEXINPUTS="$PWD/tex/latex/azhyphen//:"
lualatex document.tex
```

Configure the external PATGEN output in the ignored developer-local `local.mk`:

```make
PATTERNS := ../localization/path/to/generated/patterns.txt
```

Then synchronize the validated runtime snapshot and deterministic metadata:

```sh
make sync
```

An explicit override works without `local.mk`:

```sh
make sync PATTERNS=/path/to/patterns.txt
```

Synchronization validates raw UTF-8 PATGEN input, avoids rewriting unchanged
data, atomically replaces changed data, and deterministically generates
`azhyphen-data.json` plus the mechanically derived `azhyphen-xetex.tex` loader.
The canonical linguistic pattern dataset remains `azhyphen.pat.txt`; the XeTeX
loader is checked against it and is never a second source of truth. No generated
file contains the configured source path. `make import` remains an alias for
`make sync`.

The normal complete developer workflow is:

```sh
make update
```

It synchronizes data, validates metadata and the XeTeX loader, runs LuaLaTeX and
XeLaTeX fixture and real-pattern tests, performs an isolated installation smoke
test, and checks repository consistency. It does not commit, tag, push, change
the package version, or create a release.

Install only the runtime files into the `TEXMFHOME` reported by `kpsewhich`:

```sh
make install
```

For LuaLaTeX, `azhyphen` loads the canonical PATGEN data dynamically through
LuaTeX. For XeLaTeX, this one-time installation step adds the marked `azhyphen`
entry to the user's TeX language configuration, generates a user-level
`language.dat`, and rebuilds only the user `xelatex` format. It never modifies
`TEXMFDIST`, uses `sudo`, or requires root access. Re-running installation is
safe and refreshes the format after pattern updates.

`make uninstall` removes only azhyphen-owned runtime files and registration,
preserves unrelated user language entries, and rebuilds the affected user
format. Repeated uninstallation is safe.

## Testing

```sh
make test
```

`make test` runs both `make test-lua` and `make test-xe`. The fixture/runtime
tests build temporary TEXMF trees and install the deliberately simple
`tests/fixtures/sample-patterns.txt` there as `azhyphen.pat.txt`. They verify
that each engine selects azhyphen's language and inserts an actual discretionary
hyphen from azhyphen-owned data. The fixture is test-only and is never copied
into the source package tree.

`make test-real` separately confirms that the bundled real snapshot is accepted
and used by both engines, including `\showhyphens` over representative
Azerbaijani words. It deliberately does not hardcode linguistic breakpoints,
because those belong to the external pattern project's authoritative evaluation
suite.

`make test-sync` exercises changed, unchanged, empty, invalid, and failure-safe
synchronization behavior without touching production data. `make check` verifies
the imported data and repository consistency.

XeLaTeX format creation necessarily processes every language advertised by the
installed TeX Live database. For isolated CI on a partial TeX Live installation
whose database names unrelated loaders that are not actually installed, the
test harness supplies neutral stubs for those missing unrelated loaders inside
the temporary TEXMF tree only. Production `make install` remains strict and
reports such an inconsistent TeX Live installation instead of dropping or
altering another language.

## Architecture and layout

- `tex/latex/azhyphen/` contains the LaTeX front end, Lua runtime, optional
  exception file, and (after synchronization) generated runtime patterns and
  metadata.
- `scripts/import_patterns.py` is the development-time synchronization bridge;
  `scripts/check_repository.py` validates data and repository consistency.
- `tests/` contains LuaLaTeX integration documents and test-only data.

The Lua backend finds data through kpathsea, creates one cached LuaTeX language
object, loads native patterns and optional exceptions, configures Azerbaijani
hyphenation character mappings, and globally selects the resulting language.
The XeTeX backend selects the named `\l@azhyphen` language embedded in the user
XeLaTeX format from the same synchronized pattern snapshot.
PATGEN source, training corpora, and evaluation data remain maintained outside
this repository. `azhyphen` stores only a validated runtime snapshot and its
reproducible public metadata. Generated pattern and metadata files must never be
edited manually, and updating them does not by itself constitute a package
release.

## License

The maintained package is released under the LaTeX Project Public License 1.3c
or later. See `LICENSE`.
