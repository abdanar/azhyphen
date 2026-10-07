#!/bin/sh
set -eu

mode=${1:-fixture}
case $mode in
  fixture|real) ;;
  *) echo "error: expected fixture or real mode" >&2; exit 2 ;;
esac

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/azhyphen-xetex-test.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
mkdir -p "$tmp/home/tex/generic/config" "$tmp/var" "$tmp/config" "$tmp/cache"
mkdir -p "$tmp/out" "$tmp/repository"
sh "$root/tests/prepare-isolated-xetex.sh" "$tmp/home"

if test "$mode" = fixture; then
  # Copy only inputs needed by installation and fixture validation.
  cp -R "$root/scripts" "$root/tests" "$root/tex" "$root/docs" "$tmp/repository/"
  cp "$root/Makefile" "$root/README.md" "$root/VERSION" "$root/CITATION.cff" "$tmp/repository/"
  python3 "$tmp/repository/scripts/import_patterns.py" \
    "$tmp/repository/tests/fixtures/sample-patterns.txt" --quiet
  python3 "$tmp/repository/scripts/update_readme_stats.py" \
    --stats "$tmp/repository/tests/fixtures/sample-stats.json" \
    --patterns "$tmp/repository/tex/latex/azhyphen/azhyphen.pat.txt" \
    --output-stats "$tmp/repository/docs/model-stats.json" --quiet
  repository=$tmp/repository
else
  test -s "$root/tex/latex/azhyphen/azhyphen.pat.txt" || {
    echo "error: real XeLaTeX tests require imported patterns" >&2
    exit 1
  }
  repository=$root
fi

local_config=$tmp/home/tex/generic/config/language-local.dat
printf '%% unrelated test registration\nazhyphen-unrelated zerohyph.tex\n' \
  >"$local_config"

run_make() {
  env TEXMFHOME="$tmp/home" TEXMFVAR="$tmp/var" \
    TEXMFCONFIG="$tmp/config" TEXMFCACHE="$tmp/cache" \
    LUALATEX="${LUALATEX:-lualatex}" XELATEX="${XELATEX:-xelatex}" \
    make --no-print-directory -C "$repository" "$@"
}

run_make install >/dev/null
run_make install >/dev/null
test "$(grep -c '^azhyphen azhyphen-xetex\.tex$' "$local_config")" -eq 1
grep -q '^azhyphen-unrelated zerohyph\.tex$' "$local_config"

if ! env TEXMFHOME="$tmp/home" TEXMFVAR="$tmp/var" \
    TEXMFCONFIG="$tmp/config" TEXMFCACHE="$tmp/cache" \
    "${XELATEX:-xelatex}" -interaction=nonstopmode -halt-on-error \
      -output-directory="$tmp/out" "$repository/tests/xetex-runtime.tex" \
      >"$tmp/out/console.txt" 2>&1; then
  echo "error: XeLaTeX azhyphen integration test failed" >&2
  tail -n 100 "$tmp/out/console.txt" >&2
  exit 1
fi
grep -q 'AZHYPHEN-XETEX-LANGUAGE-SELECTED' "$tmp/out/console.txt"
if test "$mode" = fixture; then
  grep -q 'fo-toelektrik' "$tmp/out/xetex-runtime.log" || {
    echo "error: XeLaTeX did not use the azhyphen fixture patterns" >&2
    exit 1
  }
fi

run_make uninstall >/dev/null
grep -q '^azhyphen-unrelated zerohyph\.tex$' "$local_config"
if grep -q '^azhyphen azhyphen-xetex\.tex$' "$local_config"; then
  echo "error: XeLaTeX registration survived uninstall" >&2
  exit 1
fi
mkdir -p "$tmp/out-uninstalled"
if ! env TEXMFHOME="$tmp/home" TEXMFVAR="$tmp/var" \
    TEXMFCONFIG="$tmp/config" TEXMFCACHE="$tmp/cache" \
    "${XELATEX:-xelatex}" -interaction=nonstopmode -halt-on-error \
      -output-directory="$tmp/out-uninstalled" \
      "$repository/tests/xetex-unrelated.tex" \
      >"$tmp/out-uninstalled/console.txt" 2>&1; then
  echo "error: unrelated XeTeX registration did not survive uninstall" >&2
  tail -n 80 "$tmp/out-uninstalled/console.txt" >&2
  exit 1
fi
grep -q 'AZHYPHEN-UNRELATED-LANGUAGE-PRESERVED' \
  "$tmp/out-uninstalled/console.txt"
run_make uninstall >/dev/null

echo "XeLaTeX $mode tests passed"
