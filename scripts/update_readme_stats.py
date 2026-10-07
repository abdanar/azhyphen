#!/usr/bin/env python3
"""Validate public model statistics and update README's generated block."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
import tempfile

from import_patterns import PatternError, read_pattern_file


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATS = REPOSITORY_ROOT / "docs" / "model-stats.json"
DEFAULT_PATTERNS = (
    REPOSITORY_ROOT / "tex" / "latex" / "azhyphen" / "azhyphen.pat.txt"
)
DEFAULT_README = REPOSITORY_ROOT / "README.md"
START_MARKER = "<!-- AZHYPHEN-STATS:START -->"
END_MARKER = "<!-- AZHYPHEN-STATS:END -->"

COUNT_FIELDS = (
    "training_count",
    "evaluation_count",
    "pattern_count",
    "correct_breakpoints",
    "wrong_breakpoints",
    "missed_breakpoints",
)
PERCENT_FIELDS = ("exact_accuracy", "precision", "recall", "f1")
FIELD_ORDER = (
    "training_count",
    "evaluation_count",
    "pattern_count",
    "exact_accuracy",
    "precision",
    "recall",
    "f1",
    "correct_breakpoints",
    "wrong_breakpoints",
    "missed_breakpoints",
)


class StatsError(ValueError):
    """Raised when public statistics or README markers are invalid."""


def load_stats(path: Path) -> dict[str, int | float]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StatsError(f"public statistics file does not exist: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StatsError(f"cannot read public statistics from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StatsError("public statistics must be a JSON object")

    required = set(FIELD_ORDER)
    missing = sorted(required - value.keys())
    extra = sorted(value.keys() - required)
    if missing:
        raise StatsError(f"public statistics are missing fields: {', '.join(missing)}")
    if extra:
        raise StatsError(f"public statistics contain unexpected fields: {', '.join(extra)}")

    normalized: dict[str, int | float] = {}
    for field in COUNT_FIELDS:
        field_value = value[field]
        if isinstance(field_value, bool) or not isinstance(field_value, int):
            raise StatsError(f"{field} must be a non-negative integer")
        if field_value < 0:
            raise StatsError(f"{field} must be a non-negative integer")
        normalized[field] = field_value
    for field in PERCENT_FIELDS:
        field_value = value[field]
        if isinstance(field_value, bool) or not isinstance(field_value, (int, float)):
            raise StatsError(f"{field} must be a number from 0 through 100")
        numeric = float(field_value)
        if not math.isfinite(numeric) or not 0 <= numeric <= 100:
            raise StatsError(f"{field} must be a number from 0 through 100")
        normalized[field] = numeric
    return {field: normalized[field] for field in FIELD_ORDER}


def canonical_stats_bytes(stats: dict[str, int | float]) -> bytes:
    return (json.dumps(stats, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def readme_body(stats: dict[str, int | float]) -> str:
    rows = (
        ("Training annotations", f"{stats['training_count']:,}"),
        ("Evaluation annotations", f"{stats['evaluation_count']:,}"),
        ("Patterns", f"{stats['pattern_count']:,}"),
        ("Exact word accuracy", f"{stats['exact_accuracy']:.1f}%"),
        ("Break precision", f"{stats['precision']:.1f}%"),
        ("Break recall", f"{stats['recall']:.1f}%"),
        ("Break F1", f"{stats['f1']:.1f}%"),
        ("Correct breakpoints", f"{stats['correct_breakpoints']:,}"),
        ("Wrong breakpoints", f"{stats['wrong_breakpoints']:,}"),
        ("Missed breakpoints", f"{stats['missed_breakpoints']:,}"),
    )
    lines = [
        "The current pattern set is trained and evaluated on manually annotated",
        "Azerbaijani words. Evaluation uses a held-out set not used for training.",
        "",
        "| Metric | Current |",
        "|---|---:|",
    ]
    lines.extend(f"| {label} | {value} |" for label, value in rows)
    return "\n".join(lines)


def render_readme(original: bytes, stats: dict[str, int | float]) -> bytes:
    try:
        original.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StatsError(f"README is not valid UTF-8: {exc}") from exc
    start = START_MARKER.encode("utf-8")
    end = END_MARKER.encode("utf-8")
    if original.count(start) != 1:
        raise StatsError("README must contain exactly one statistics start marker")
    if original.count(end) != 1:
        raise StatsError("README must contain exactly one statistics end marker")
    start_at = original.index(start)
    end_at = original.index(end)
    if start_at >= end_at:
        raise StatsError("README statistics markers are out of order")
    body = readme_body(stats).encode("utf-8")
    return original[: start_at + len(start)] + b"\n" + body + b"\n" + original[end_at:]


def desired_state(
    stats_path: Path, patterns_path: Path, readme_path: Path
) -> tuple[dict[str, int | float], bytes, bytes]:
    stats = load_stats(stats_path)
    try:
        patterns = read_pattern_file(patterns_path, label="pattern data paired with statistics")
    except PatternError as exc:
        raise StatsError(str(exc)) from exc
    if stats["pattern_count"] != patterns.pattern_count:
        raise StatsError(
            "public statistics pattern_count "
            f"({stats['pattern_count']}) does not match pattern data "
            f"({patterns.pattern_count})"
        )
    try:
        readme = readme_path.read_bytes()
    except OSError as exc:
        raise StatsError(f"cannot read README from {readme_path}: {exc}") from exc
    return stats, canonical_stats_bytes(stats), render_readme(readme, stats)


def atomic_write_if_changed(path: Path, contents: bytes) -> bool:
    if path.is_file() and path.read_bytes() == contents:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o644)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def check_repository_state(
    stats_path: Path = DEFAULT_STATS,
    patterns_path: Path = DEFAULT_PATTERNS,
    readme_path: Path = DEFAULT_README,
) -> list[str]:
    try:
        _, canonical, rendered = desired_state(stats_path, patterns_path, readme_path)
    except StatsError as exc:
        return [str(exc)]
    errors: list[str] = []
    if stats_path.read_bytes() != canonical:
        errors.append("public statistics JSON is not in canonical deterministic format")
    if readme_path.read_bytes() != rendered:
        errors.append("README statistics block does not match public statistics")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS)
    parser.add_argument("--patterns", type=Path, default=DEFAULT_PATTERNS)
    parser.add_argument("--readme", type=Path, default=DEFAULT_README)
    parser.add_argument("--output-stats", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check and args.output_stats is not None:
        print("error: --check cannot be combined with --output-stats", file=sys.stderr)
        return 2
    try:
        stats, canonical, rendered = desired_state(
            args.stats, args.patterns, args.readme
        )
        if args.check:
            errors = check_repository_state(args.stats, args.patterns, args.readme)
            if errors:
                raise StatsError("; ".join(errors))
            if not args.quiet:
                print("public statistics and README block are up to date")
            return 0
        destination = args.output_stats or args.stats
        stats_changed = atomic_write_if_changed(destination, canonical)
        readme_changed = atomic_write_if_changed(args.readme, rendered)
    except (OSError, StatsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(
            "Public statistics: "
            + ("updated" if stats_changed else "already up to date")
        )
        print(
            "README statistics: "
            + ("updated" if readme_changed else "already up to date")
        )
        print(f"Patterns represented: {stats['pattern_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
