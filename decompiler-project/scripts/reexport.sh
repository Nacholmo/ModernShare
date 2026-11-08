#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/environment.sh"
exec python3 "$PROJECT_ROOT/scripts/pipeline.py" export
