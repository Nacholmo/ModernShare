#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/environment.sh"
if [[ ! -x "$GHIDRA_ROOT/ghidraRun" ]]; then
  printf '%s\n' 'Local Ghidra is missing. Run python3 scripts/bootstrap.py.' >&2
  exit 1
fi
if [[ ! -f "$PROJECT_ROOT/projects/KodakC713.gpr" ]]; then
  printf '%s\n' 'No saved project. Run bash scripts/analyze.sh first.' >&2
  exit 1
fi
exec "$GHIDRA_ROOT/ghidraRun" "$PROJECT_ROOT/projects/KodakC713.gpr"
