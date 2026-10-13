# azhyphen

<!-- AZHYPHEN-BADGES:START -->
![Version](https://img.shields.io/badge/version-0.1.0--development-blue)
![License](https://img.shields.io/badge/license-LPPL%201.3c%2B-blue)
![LuaLaTeX](https://img.shields.io/badge/LuaLaTeX-supported-2ea44f)
![XeLaTeX](https://img.shields.io/badge/XeLaTeX-supported-2ea44f)
![Status](https://img.shields.io/badge/status-active%20development-orange)
<!-- AZHYPHEN-BADGES:END -->

Standalone Azerbaijani hyphenation for LuaLaTeX and XeLaTeX. It does not
require Babel, Polyglossia, or document-level language configuration.

## Usage

```tex
\documentclass{article}
\usepackage{azhyphen}

\begin{document}
Azərbaycan dilində mətn avtomatik olaraq hecalanır.
\end{document}
```

Compile with LuaLaTeX or XeLaTeX. pdfLaTeX is not currently supported.
Loading the package activates Azerbaijani hyphenation globally. XeLaTeX also
sets Azerbaijani case mappings, including the distinct `i`/`İ` and `ı`/`I`
pairs. Automatic switching between languages is outside this package's scope.

## Current status

<!-- AZHYPHEN-STATS:START -->
The current pattern set is trained and evaluated on manually annotated
Azerbaijani words. Evaluation uses a held-out set not used for training.

| Metric | Current |
|---|---:|
| Training annotations | 2,007 |
| Evaluation annotations | 263 |
| Patterns | 291 |
| Exact word accuracy | 65.0% |
| Break precision | 89.0% |
| Break recall | 92.7% |
| Break F1 | 90.8% |
| Correct breakpoints | 599 |
| Wrong breakpoints | 74 |
| Missed breakpoints | 47 |
<!-- AZHYPHEN-STATS:END -->

These figures describe the synchronized experimental model, not complete
linguistic coverage. The current left and right hyphenation minima are both 2
and remain subject to linguistic and typographic review.

## Project status

azhyphen is under active development and is already usable with LuaLaTeX and
XeLaTeX. The Azerbaijani pattern set continues to grow and be evaluated.
Releases in the `0.x` series are development releases, so model statistics and
linguistic behavior may change between them. Version `1.0.0` will mark the
first stable release after the pattern set, package behavior, and regression
coverage are sufficiently mature. Current linguistic quality is reported
separately above.

## Installation

From the repository checkout, run:

```sh
make install
```

Installation requires a POSIX shell, GNU Make, Python 3.10 or newer, and a
working TeX Live installation with `lualatex`, `xelatex`, `kpsewhich`, `tlmgr`,
`fmtutil-user`, `iftex`, and `luaotfload`. Both engines must be available for
the installation verification. Installation is tested with TeX Live 2026
on Ubuntu and native Windows with MSYS2. See
[Windows development](DEVELOPMENT.md#windows-development) for toolchain
configuration. Other TeX distributions have not been verified.

This installs azhyphen in your user `TEXMFHOME` and requires no root access.
The same step performs XeLaTeX's one-time user-level language registration.
Re-running installation is safe. Run `make uninstall` to remove only
azhyphen-owned files and registration.
XeLaTeX registration rebuilds your user format. If TeX Live reports an unrelated
missing language loader, repair that TeX installation and retry; production
installation does not replace missing loaders with test stubs.

## Development

The linguistic data, PATGEN experiments, and authoritative model statistics
are maintained separately. This repository contains their validated runtime
snapshot and selected public statistics. See [DEVELOPMENT.md](DEVELOPMENT.md)
for synchronization, testing, versioning, and release details.
The origin and licensing of the bundled data are documented in
[docs/PROVENANCE.md](docs/PROVENANCE.md).

## License

azhyphen is released under the LaTeX Project Public License 1.3c or later. See
[LICENSE](LICENSE).
