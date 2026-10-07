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

For a future release:

1. Ensure pattern and public-statistics synchronization has completed.
2. Run `make update`, `make test`, and `make check`.
3. Confirm that only intentional release changes remain in the worktree.
4. Update `VERSION`, then run `make version`.
5. Update `CHANGELOG.md` and run `make check` again.
6. Commit the release changes.
7. Tag the commit as `vX.Y.Z`.
8. Create the corresponding GitHub release.
9. Prepare a CTAN submission later when appropriate.

No repository command in this project automatically commits, tags, pushes, or
publishes a release.
