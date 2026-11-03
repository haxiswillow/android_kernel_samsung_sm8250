#!/usr/bin/env sh
# SPDX-License-Identifier: GPL-2.0-only
# Optional diagnostic tag only. No source code depends on Git history.
set -eu
case "${1:-}" in
ids)
    dir=${2:-.}
    git -C "$dir" rev-parse --verify HEAD >/dev/null 2>&1 || exit 0
    checkout=$(git -C "$dir" reflog --format='%H %gs' 2>/dev/null |
        sed '/^[^ ]* cherry-pick:/d' | sed -n '1s/ .*//p')
    range=HEAD
    if [ -n "$checkout" ] && git -C "$dir" rev-parse --verify "${checkout}^" >/dev/null 2>&1; then
        range="${checkout}^..HEAD"
    fi
    git -C "$dir" log -50 "$range" 2>/dev/null |
        sed -nE 's/^[[:space:]]*Change-Id: (I[0-9a-f]{10})[0-9a-f]{30}[[:space:]]*$/\1/p' |
        paste -sd ',' -
    ;;
timestamp)
    if [ -n "${SOURCE_DATE_EPOCH:-}" ]; then
        case "$SOURCE_DATE_EPOCH" in *[!0-9]*|'') exit 1 ;; esac
        date -u -d "@$SOURCE_DATE_EPOCH" +'%Y-%m-%dT%H:%M:%SZ'
    else
        date -u +'%Y-%m-%dT%H:%M:%SZ'
    fi
    ;;
*) exit 2 ;;
esac
