#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
package_dir=$root/tex/latex/azhyphen
test -s "$package_dir/azhyphen.pat.txt" || {
  echo "error: real-pattern tests require an imported azhyphen.pat.txt" >&2
  exit 1
}
test -s "$package_dir/azhyphen-data.json" || {
  echo "error: real-pattern tests require generated metadata" >&2
  exit 1
}

tmp=$(mktemp -d "${TMPDIR:-/tmp}/azhyphen-real-test.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
mkdir -p "$tmp/texmf/tex/latex/azhyphen" "$tmp/cache" "$tmp/out"
cp "$package_dir/azhyphen.sty" "$package_dir/azhyphen.lua" \
   "$package_dir/azhyphen-version.tex" \
   "$package_dir/azhyphen.pat.txt" "$package_dir/azhyphen.hyp.txt" \
   "$tmp/texmf/tex/latex/azhyphen/"

run_lualatex() {
  input=$1
  name=$(basename "$input" .tex)
  if ! env TEXMFCACHE="$tmp/cache" TEXMFVAR="$tmp/cache" \
      TEXINPUTS="$tmp/texmf//:" \
      "${LUALATEX:-lualatex}" -interaction=nonstopmode -halt-on-error \
        -output-directory="$tmp/out" "$input" >"$tmp/out/$name.console" 2>&1; then
    echo "error: real-pattern LuaLaTeX test failed for $input" >&2
    tail -n 80 "$tmp/out/$name.console" >&2
    return 1
  fi
}

run_lualatex "$root/tests/basic.tex"
run_lualatex "$root/tests/real-patterns.tex"
echo "real-pattern tests passed"
