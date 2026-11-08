#!/usr/bin/env bash
# All application-generated state stays in this project directory.
[ -n "${BASH_VERSION:-}" ] || { printf "%s\n" "Run this environment script with bash." >&2; return 1; }
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export XDG_CONFIG_HOME="$PROJECT_ROOT/runtime/config"
export XDG_CACHE_HOME="$PROJECT_ROOT/runtime/cache"
export XDG_DATA_HOME="$PROJECT_ROOT/runtime/data"
export XDG_STATE_HOME="$PROJECT_ROOT/runtime/state"
export TMPDIR="$PROJECT_ROOT/runtime/tmp"
export JAVA_HOME="$PROJECT_ROOT/tools/jdk-25.0.5+8"
export PATH="$JAVA_HOME/bin:$PATH"
export _JAVA_OPTIONS="-Duser.home=$PROJECT_ROOT/runtime/home -Djava.io.tmpdir=$PROJECT_ROOT/runtime/tmp -Dapplication.settingsdir=$PROJECT_ROOT/runtime/config -Dapplication.cachedir=$PROJECT_ROOT/runtime/cache"
export GHIDRA_ROOT="$PROJECT_ROOT/tools/ghidra_12.2_PUBLIC"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME" "$XDG_STATE_HOME" "$TMPDIR" "$PROJECT_ROOT/runtime/home"
