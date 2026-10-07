#!/usr/bin/env python3
"""Synchronize azhyphen patterns, statistics, and generated public outputs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any

from import_patterns import (
    DESTINATION,
    METADATA_DESTINATION,
    XETEX_LOADER_DESTINATION,
    PatternData,
    PatternError,
    analyze_pattern_bytes,
    metadata_bytes,
    prepare_temporary,
    print_report,
    read_pattern_file,
    restore_file,
    write_report,
    xetex_loader_bytes,
)
from update_readme_stats import (
    DEFAULT_README,
    DEFAULT_STATS,
    StatsError,
    canonical_stats_bytes,
    load_stats,
    render_readme,
)


class SynchronizationError(RuntimeError):
    """Raised when coordinated output replacement or rollback fails."""


def replace_file(source: Path, destination: Path) -> None:
    """Install one prepared replacement.

    This small boundary makes replacement failures injectable in regression
    tests without changing production behavior.
    """
    os.replace(source, destination)


def _read_output(path: Path) -> tuple[bytes | None, int | None]:
    if not path.exists():
        return None, None
    if not path.is_file():
        raise OSError(f"synchronization destination is not a regular file: {path}")
    return path.read_bytes(), stat.S_IMODE(path.stat().st_mode)


def _old_pattern_count(raw: bytes | None) -> int:
    if raw is None:
        return 0
    try:
        return analyze_pattern_bytes(raw, label="bundled pattern file").pattern_count
    except PatternError:
        return 0


def desired_outputs(
    pattern_source: Path, stats_source: Path
) -> tuple[PatternData, tuple[tuple[Path, bytes], ...]]:
    """Validate both inputs and render every coordinated output in memory."""
    patterns = read_pattern_file(
        pattern_source.expanduser().resolve(), label="configured pattern source"
    )
    stats = load_stats(stats_source.expanduser().resolve())
    if stats["pattern_count"] != patterns.pattern_count:
        raise StatsError(
            "public statistics pattern_count "
            f"({stats['pattern_count']}) does not match pattern data "
            f"({patterns.pattern_count})"
        )
    try:
        readme = DEFAULT_README.read_bytes()
    except OSError as exc:
        raise StatsError(f"cannot read README from {DEFAULT_README}: {exc}") from exc

    outputs = (
        (XETEX_LOADER_DESTINATION, xetex_loader_bytes(patterns)),
        (METADATA_DESTINATION, metadata_bytes(patterns)),
        (DEFAULT_STATS, canonical_stats_bytes(stats)),
        (DEFAULT_README, render_readme(readme, stats)),
        # Keep the canonical source last: derived files never remain paired
        # with a partially installed canonical snapshot after rollback.
        (DESTINATION, patterns.raw),
    )
    return patterns, outputs


def synchronize(pattern_source: Path, stats_source: Path) -> dict[str, Any]:
    """Atomically coordinate the complete generated data state.

    Validation and rendering complete before any destination is touched.
    Changed outputs are prepared first, then installed with atomic per-file
    replacements. If installation fails, every replacement already made is
    restored to its previous contents and permissions.
    """
    patterns, outputs = desired_outputs(pattern_source, stats_source)
    snapshots: dict[Path, tuple[bytes | None, int | None]] = {
        destination: _read_output(destination) for destination, _ in outputs
    }
    changed = {
        destination: snapshots[destination][0] != contents
        for destination, contents in outputs
    }
    old_patterns = _old_pattern_count(snapshots[DESTINATION][0])
    prepared: dict[Path, Path] = {}
    replaced: list[Path] = []

    try:
        for destination, contents in outputs:
            if not changed[destination]:
                continue
            temporary = prepare_temporary(destination, contents)
            prepared[destination] = temporary
            previous_mode = snapshots[destination][1]
            if previous_mode is not None:
                temporary.chmod(previous_mode)

        for destination, _ in outputs:
            if not changed[destination]:
                continue
            temporary = prepared[destination]
            replace_file(temporary, destination)
            prepared.pop(destination)
            replaced.append(destination)
    except BaseException as exc:
        rollback_errors: list[str] = []
        for destination in reversed(replaced):
            previous, mode = snapshots[destination]
            try:
                restore_file(destination, previous, mode)
            except BaseException as rollback_exc:
                rollback_errors.append(f"{destination}: {rollback_exc}")
        if rollback_errors:
            raise SynchronizationError(
                f"synchronization failed ({exc}); rollback also failed: "
                + "; ".join(rollback_errors)
            ) from exc
        raise
    finally:
        for temporary in prepared.values():
            temporary.unlink(missing_ok=True)

    status = lambda path: "updated" if changed[path] else "already up to date"
    return {
        "metadata_status": status(METADATA_DESTINATION),
        "new_patterns": patterns.pattern_count,
        "old_patterns": old_patterns,
        "readme_status": status(DEFAULT_README),
        "result": "success",
        "sha256": patterns.sha256,
        "stats_status": status(DEFAULT_STATS),
        "status": status(DESTINATION),
        "xetex_loader_status": status(XETEX_LOADER_DESTINATION),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patterns", type=Path, help="UTF-8 PATGEN output")
    parser.add_argument("--stats", type=Path, help="public model statistics JSON")
    parser.add_argument("--report", type=Path, help="write a private update report")
    parser.add_argument(
        "--print-report", type=Path, help="print a previously written update report"
    )
    parser.add_argument("--quiet", action="store_true", help="suppress sync summary")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.print_report is not None:
        if args.patterns is not None or args.stats is not None or args.report is not None:
            print(
                "error: --print-report cannot be combined with synchronization",
                file=sys.stderr,
            )
            return 2
        try:
            report = json.loads(args.print_report.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: cannot read update report: {exc}", file=sys.stderr)
            return 1
        print_report(report, update=True)
        return 0
    if args.patterns is None or args.stats is None:
        print("error: --patterns and --stats are required", file=sys.stderr)
        return 2

    try:
        report = synchronize(args.patterns, args.stats)
        if args.report is not None:
            write_report(args.report, report)
    except (OSError, PatternError, StatsError, SynchronizationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not args.quiet:
        print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
