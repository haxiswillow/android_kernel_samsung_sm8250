#!/usr/bin/env bash
# Compatibility entry point; all configuration lives in build.sh.
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/build.sh" "$@"
