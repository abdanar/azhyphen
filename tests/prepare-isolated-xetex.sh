#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$root/scripts/tex_environment.sh"
test_home=$(tex_native_path "$1")
probe=$(tex_native_path "$(mktemp -d "${TMPDIR:-/tmp}/azhyphen-language-probe.XXXXXX")")
trap 'rm -rf "$probe"' EXIT HUP INT TERM
: >"$probe/language-local.dat"
tex_tlmgr generate language.dat --localcfg "$probe/language-local.dat" \
  --dest "$probe/language.dat" >/dev/null
language_dat=$probe/language.dat
missing=0
carriage_return=$(printf '\r')

while IFS= read -r line; do
  # Native TeX Live may generate CRLF language.dat; filenames exclude the CR.
  line=${line%"$carriage_return"}
  set -- $line
  test "$#" -ge 2 || continue
  language=$1
  loader=$2
  case $language in
    \%*|=*) continue ;;
  esac
  case $loader in
    \%*) continue ;;
  esac
  if ! kpsewhich "$loader" >/dev/null 2>&1; then
    stub=$test_home/tex/generic/azhyphen-test-stubs/$loader
    mkdir -p "$(dirname "$stub")"
    printf '%% Test-only stub for a missing unrelated TeX Live loader.\n' >"$stub"
    missing=$((missing + 1))
  fi
done <"$language_dat"

if test "$missing" -gt 0; then
  echo "isolated XeTeX test: stubbed $missing missing unrelated TeX Live loaders" >&2
fi
