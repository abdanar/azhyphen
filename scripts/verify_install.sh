#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/azhyphen-verify-install.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
mkdir -p "$tmp/cache" "$tmp/lua" "$tmp/xe"

run_engine() {
  engine=$1
  output=$2
  texmfvar=$3
  if ! env TEXMFCACHE="$tmp/cache" TEXMFVAR="$texmfvar" \
      "$engine" -interaction=nonstopmode -halt-on-error \
        -output-directory="$output" "$root/tests/basic.tex" \
        >"$output/console.txt" 2>&1; then
    echo "error: installed-package verification failed with $engine" >&2
    tail -n 80 "$output/console.txt" >&2
    return 1
  fi
}

run_engine "${LUALATEX:-lualatex}" "$tmp/lua" "$tmp/cache"
run_engine "${XELATEX:-xelatex}" "$tmp/xe" "${TEXMFVAR:-$tmp/cache}"
echo "installed LuaLaTeX and XeLaTeX package verification passed"
