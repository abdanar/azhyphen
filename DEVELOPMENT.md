# Development

The PATGEN pattern file and public model statistics are maintained outside this
repository and synchronized into `azhyphen` as validated generated artifacts.
To update both together, run:

```sh
make update PATTERNS=/path/to/patterns.pat STATS=/path/to/public-stats.json
```

The update process validates both inputs, verifies that the reported
`pattern_count` matches the imported pattern data, and prepares all generated
outputs before replacing any of them. A failed replacement rolls the complete
generated data set back to its prior contents and permissions when rollback
I/O succeeds. Replacements are atomic per file; this is not a crash-safe or
concurrent-writer transaction. Run one synchronization process at a time.
A successful update then runs the
complete LuaLaTeX and XeLaTeX validation pipeline.

For a synchronized data and README refresh without the full test suite, use:

```sh
make sync PATTERNS=/path/to/patterns.pat STATS=/path/to/public-stats.json
```

Generated pattern data, metadata, XeTeX loader files, and README statistics
should not be edited manually.

Choose patterns and statistics from the same committed localization snapshot.
Matching pattern counts alone does not establish that the statistics describe
the same trained model. Keep `docs/PROVENANCE.md` current when importing a new
snapshot. Public package checks need only the bundled files; training and
evaluation remain in the external project.

`tex/latex/azhyphen/` contains the distributable runtime and generated data;
`scripts/` contains maintenance tools; `tests/` contains isolated integration
tests and synthetic fixtures; `docs/` contains public model metadata.
The low-level importer and statistics renderer remain available for isolated
tests. Use `make sync` for coordinated production updates.

Contributions should include a minimal reproduction and relevant tests. Report
linguistic issues separately from package or installation issues, using the
GitHub issue forms. Never include private documents, logs, or corpus inputs.

Useful development checks are:

```sh
# List the public development targets and configuration overrides.
make help

# Validate synchronized generated state without running engine tests.
make validate-state

# General LuaLaTeX and XeLaTeX package tests.
make test

# Validate the package against the currently bundled real pattern data.
make test-real

# Test pattern/statistics synchronization and generated artifacts.
make test-sync

# Check repository consistency and generated-data integrity.
make check
```

Fixture-based tests use isolated temporary TEXMF trees and do not modify the
user's TeX installation. Real-pattern tests verify that the bundled Azerbaijani
pattern set can be loaded and used correctly by both supported engines.

The LuaLaTeX backend loads `azhyphen.pat.txt` dynamically at runtime. XeLaTeX
uses a deterministically generated loader together with a user-level TeX
language registration created during installation. Both backends use the same
canonical Azerbaijani pattern data and expose the same document interface:

```latex
\usepackage{azhyphen}
```

XeLaTeX format generation depends on the consistency of the local TeX Live
language configuration. The test environment can isolate unrelated missing
loaders, while production installation remains strict and does not modify or
remove unrelated language registrations.

## Development versions and releases

`VERSION` is the only manually maintained software version. Versions in the
`0.x` series are development releases; `1.0.0` will be the first stable
release. Model size and evaluation metrics do not determine the software
version.

After editing `VERSION`, run `make version` to regenerate the shipped LaTeX
metadata, README version badge, and `CITATION.cff`. `make check-version` verifies
that they agree.

For a future software release:

1. Finish changes. Use `make update` only if refreshing linguistic data from
   a matching localization commit; a data refresh does not bump the version.
2. Update `VERSION` and `CHANGELOG.md` for the software release.
3. Run `make version`.
4. Run `make test`, then `make release-check`.
5. Run `make ctan`.
6. Inspect `dist/azhyphen-X.Y.Z.zip`, its printed SHA-256, and the manual PDF.
7. Commit the intentional release changes.
8. Run `git tag -a vX.Y.Z -m "azhyphen vX.Y.Z"`.
9. Run `git push origin main vX.Y.Z`.
10. Confirm GitHub CI, including the release-tag/version check.
11. Create or update the GitHub release as desired.
12. Upload the already-built `dist/azhyphen-X.Y.Z.zip` as the CTAN update.

Submit the complete generated archive again for every CTAN update; do not
assemble an archive or upload individual changed files manually. None of the
build targets contact CTAN or publish a GitHub release.

`make doc` builds `build/doc/azhyphen-doc.pdf`. Documentation uses LuaLaTeX,
`fontspec`, `geometry`, `hyperref`, and the TeX Live `cm-unicode` fonts. The source manual
reads the generated runtime version, and its build-time statistics table is
derived from `docs/model-stats.json`; neither is maintained as a second copy.
The generated PDF need not be committed.

`make ctan` starts clean staging in `build/ctan/azhyphen/`, copies an explicit
allowlist, compiles the manual twice without shell escape, checks source and
archive bytes, and loads the staged runtime in both engines in an isolated
user tree. The archived README is adapted to the archive's manual installation
instructions and flattened provenance path; its generated version/statistics
blocks are preserved. No runtime file needs an independently maintained CTAN
copy. Test-only stubs for missing unrelated language loaders stay outside the
distribution. `make release-check` additionally runs all fixture, real-pattern,
tooling, installation, generated-state, repository, and whitespace checks.
Checks validate the bundled snapshot without requiring the private upstream
project; provenance identifies the matching upstream commit.

Builds use sorted ZIP entries, fixed regular-file permissions, stored (not
compressed) ZIP contents, and UTC timestamps from `SOURCE_DATE_EPOCH`. The
default epoch is 2000-01-01 UTC, independent of commit or checkout time. Set
the same explicit epoch for every reproduction if overriding it. The manual
uses that epoch, suppresses volatile PDF metadata, and uses uncompressed PDF
streams so path/privacy checks can inspect them. Same source, epoch, fonts,
and TeX toolchain should produce identical hashes; different TeX/font versions
can change PDF bytes and are not promised to reproduce an identical archive.
Run one documentation/release build at a time.

To verify reproducibility on your release toolchain:

```sh
make ctan
sha256sum dist/azhyphen-$(cat VERSION).zip
make clean-dist
make ctan
sha256sum dist/azhyphen-$(cat VERSION).zip
```

`make clean` removes documentation/staging and existing test artifacts but
keeps release archives. `make clean-dist` removes `dist/`. Both directories
are ignored; release sources remain tracked. CI runs `make release-check`
on main, pull requests, and `v*` tags, checks the tag against `VERSION`, repeats
the CTAN build to compare hashes, and retains the ZIP as an Actions artifact.

`.gitattributes` enforces LF checkouts, including the canonical patterns and
generated metadata. Automatic CRLF conversion would invalidate the recorded
pattern checksum and generated-file byte comparisons.

No repository command in this project automatically commits, tags, pushes, or
publishes a release.

## Windows development

Use MSYS2's GNU Make and POSIX shell utilities together with native TeX Live
2026 and Python. Keep `make`, `sh`, `python3`, `git`, `lualatex`, `xelatex`,
`kpsewhich`, `tlmgr`, and `fmtutil-user` on the persistent user PATH. A
`python3` alias may point to the existing native Python installation; no
second Python installation is needed. GNU Make can be invoked from an
ordinary PowerShell terminal and uses the MSYS2 shell for existing recipes.
Set the user environment variable `MSYS2_PATH_TYPE=inherit` when using an
MSYS2 login terminal, so it also finds the native Python and TeX tools.
The release packager uses native platform path-list separators.
The shared shell helper converts MSYS temporary paths for native TeX, selects
Windows path-list separators and the `tlmgr.bat` wrapper, and uses the native
Perl-compatible `C` locale. Language-loader probes accept LF and CRLF output.

Open a new terminal after installation or PATH changes. The same targets
apply on Windows and Linux. Native Windows skips only the POSIX `0640`
permission assertion, with an explicit reason; ownership, preservation,
rollback, conflict, and idempotence checks still run. Linux CI retains the
permission assertion. Canonical LF checkouts are required for POSIX scripts
and checksum-bearing generated files.
