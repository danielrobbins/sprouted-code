#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -ne 1 ] || [ ! -d "$1" ]; then
  echo "Usage: $0 PATH-TO-EXTRACTED-SPROUTED-CODE" >&2
  exit 2
fi

root="$(cd "$1" && pwd)"

mapfile -t elf_paths < <(
  find "$root" -type f -exec file -N -F $'\t' -- {} + \
    | awk -F '\t' '$2 ~ /ELF/ { print $1 }'
)

elf_files() {
  printf '%s\0' "${elf_paths[@]}"
}

max_symbol_version() {
  local pattern="$1"
  elf_files \
    | xargs -0 -r readelf --version-info 2>/dev/null \
    | grep -oE "$pattern" \
    | sort -Vu \
    | tail -1
}

echo "Build root: $root"
printf 'ELF files: %s\n' "${#elf_paths[@]}"

echo
echo "Unresolved shared libraries:"
missing=0
while IFS= read -r -d '' candidate; do
  unresolved="$(ldd "$candidate" 2>/dev/null | grep 'not found' || true)"
  if [ -n "$unresolved" ]; then
    missing=1
    printf '%s\n%s\n' "$candidate" "$unresolved"
  fi
done < <(elf_files)
if [ "$missing" -eq 0 ]; then
  echo "None"
fi

echo
echo "Maximum imported symbol versions:"
printf '  GLIBC:   %s\n' "$(max_symbol_version 'GLIBC_[0-9.]+')"
printf '  GLIBCXX: %s\n' "$(max_symbol_version 'GLIBCXX_[0-9.]+')"
printf '  CXXABI:  %s\n' "$(max_symbol_version 'CXXABI_[0-9.]+')"

echo
echo "Directly required shared libraries:"
elf_files | while IFS= read -r -d '' candidate; do
  readelf -d "$candidate" 2>/dev/null \
    | sed -n 's/.*Shared library: \[\(.*\)\]/\1/p'
done | sort -u
