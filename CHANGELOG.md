# Changelog

## [0.2.1] - 2026-10-14

- Polish the user manual's usage, installation, contribution and quality explanations.
- Clarify that reported quality describes the public evaluation set, not an
  unbiased estimate for arbitrary unseen vocabulary.
- No changes to runtime behavior, datasets, hyphenation patterns or quality metrics.

## [0.2.0] - 2026-10-14

- Make azhyphen self-contained with canonical annotated Azerbaijani training
  words and a separate public evaluation set; remove the external localization dependency.
- Regenerate the model deterministically with PATGEN from public words and empty
  patterns, replacing historical seeding; contributors edit `data/hyphenated.txt`.
- Simplify the repository and consolidate maintenance in one portable Python tool.
- Dedicate both datasets under CC0 1.0; retain LPPL 1.3c or later for software,
  runtime, generated patterns and documentation.
- Provide a user manual and reproducible CTAN source archive containing the data
  and generator, with repository tests and CI excluded.

## [0.1.0] - 2026-10-02

- Initial development release of standalone Azerbaijani hyphenation.
- LuaLaTeX and XeLaTeX support through the same public package interface.
- Synchronized PATGEN runtime patterns and public model statistics.
- Fixture, real-pattern, and installation tests for both supported engines.
