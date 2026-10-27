# azhyphen

Standalone Azerbaijani hyphenation for **LuaLaTeX and XeLaTeX**, using native
engine hyphenation. No Babel or Polyglossia configuration is needed.

```tex
\documentclass{article}
\usepackage{fontspec}
\setmainfont{CMU Serif} % choose an Azerbaijani-capable font
\usepackage{azhyphen}
\begin{document}
Azərbaycan dilində mətn avtomatik olaraq hecalanır.
\end{document}
```

Loading the package activates Azerbaijani globally, including distinct
`i`/`İ` and `ı`/`I` mappings. Compile with LuaLaTeX or XeLaTeX; pdfLaTeX is
unsupported. XeLaTeX requires installation into its user format first.

## Status and quality

<!-- AZHYPHEN-GENERATED:START -->
Azhyphen **0.2.1** is currently a **development release**. Its hyphenation
patterns are generated reproducibly from the public annotated Azerbaijani
dataset included in this repository.

**Dataset** · 3,000 training words · 373 evaluation words · 353 patterns\
**Quality** · 80.43% exact-word accuracy · 97.03% precision · 94.12% recall · **95.55% F1**\
**Breakpoints** · 881 correct · 27 wrong · 55 missed
<!-- AZHYPHEN-GENERATED:END -->

Versions below 1.0.0 are development releases. Linguistic coverage is
experimental. The left/right minima are provisionally **2/2**, pending
Azerbaijani linguistic and typographic review. Metrics compare permitted
breakpoints against full annotations, including edge syllables that minima
suppress; they describe the public evaluation set, not complete language coverage.
It is excluded from PATGEN training. Repeated development against a public
evaluation set does not provide a permanently unbiased estimate on unseen words.

azhyphen remains a standalone GitHub-hosted project under active development.
Future integration with standard TeX hyphenation distributions may be explored
through the [tex-hyphen mailing list](mailto:tex-hyphen@tug.org); no integration
has taken place.

## Install

Use TeX Live with `lualatex`, `xelatex`, `kpsewhich`, `tlmgr`, `fmtutil-user`,
`iftex`, `luaotfload` and `fontspec`, plus Python 3.10 or newer. Install manually
from a GitHub source checkout or extracted GitHub source ZIP:

```sh
python scripts/azhyphen.py install
```

This copies five runtime files to `TEXMFHOME`, adds marked XeLaTeX language
registrations and rebuilds only the user format. Repeat installation after
updating patterns. Unrelated registrations are preserved. Undo with
`python scripts/azhyphen.py uninstall`; modified or unrelated files are kept.
Missing unrelated language loaders require repairing your TeX installation.
See [the manual](doc/azhyphen-doc.tex) for usage and diagnostics.

## Contribute

Install Python 3.10+, GNU Make and TeX Live (including `patgen`). On Windows,
use native Python/TeX Live and GNU Make from MSYS2; put their binaries on
PATH and set `MSYS2_PATH_TYPE=inherit` when using an MSYS2 login shell.
The maintenance tool itself requires no shell or third-party Python modules.

1. Edit [data/hyphenated.txt](data/hyphenated.txt): one NFC Azerbaijani word
   per line, with ASCII `-` marking every reviewed syllable boundary.
   Blank lines, comments, duplicate words and non-Azerbaijani characters are rejected.
2. Run `make update`.
3. Run `make test`.
4. Submit the change, including generated files, with evidence for corrections.

[data/evaluation.txt](data/evaluation.txt) is the public evaluation set,
excluded from PATGEN training and used for quality measurement and regression checks.
Do not move its words into training or tune annotations to predictions.
Corrections to evaluation need independent linguistic evidence. Duplicate
words and overlap between the lists are rejected, including case variants.

## Generation and maintenance

`scripts/azhyphen.py` is the single portable maintenance tool. The Makefile
provides aliases: `make update` is equivalent to
`python scripts/azhyphen.py update`, and the other targets work the same way.

- `make update` validates the word lists, regenerates PATGEN-derived runtime
  files, evaluates quality and updates the README status.
- `make test` runs the repository maintenance tests and LuaLaTeX/XeLaTeX
  runtime checks; the tests are available in the GitHub repository.
- `make check` regenerates in isolation and fails on stale generated files
  or repository consistency errors.
- `make stats` prints the current dataset, model and evaluation statistics
  without writing a results file.
- `make doc` builds and checks the user manual in `build/azhyphen-doc.pdf`.
- `make install` installs into the user's TeX tree and registers Azerbaijani
  in the XeLaTeX user format.
- `make uninstall` removes unmodified package-owned files and marked language
  registrations, preserving modified files and unrelated registrations.
- `make clean` removes `build/`; saved release archives in `dist/` are preserved.

### Pattern generation

Generation validates the two word lists, wraps training words in boundary
dots without changing annotations, creates a UTF-8 Azerbaijani translation
table (including dotted/dotless I), and runs **PATGEN 2.4** from an empty
pattern file: hyphenation level **1**, pattern lengths **2–4**, good/bad
weights **1/3**, threshold **3**, minima **2/2**. The generated canonical
`azhyphen.pat.txt` and derived XeTeX loader are committed for package users.
Temporary dictionaries, patterns and logs are discarded. Document compilation
never runs PATGEN; ordinary users use the pre-generated, validated patterns.
`make check` independently regenerates in isolation and rejects stale output.

Quality is computed against the public evaluation set, excluded from training,
using standard Liang scoring during `make update` and `make stats`.
There is no results JSON or historical experiment archive.

`VERSION` is the sole manually maintained software version; `make update`
generates its runtime representation and README display. Changing the data
never bumps the version.

## License, provenance and reports

Software, generated patterns and package documentation: **LPPL 1.3c or later**.
The two public annotated word lists: **CC0 1.0 Universal**. See
[LICENSE](LICENSE) for the grants and migration provenance, and the complete
[LPPL](LPPL-1.3c.txt) and [CC0](CC0-1.0.txt) texts.

Report bugs and proposed word corrections at
[GitHub Issues](https://github.com/abdanar/azhyphen/issues), with a minimal
example, engine/version and linguistic evidence where relevant. Include no
private documents or credentials.
