#!/bin/zsh
# Finder-compatible launcher: prefer the local venv without shell activation.
grc_project_dir="${0:A:h}"
if [[ -x "$grc_project_dir/.venv/bin/antenna-grc" ]]; then
    exec "$grc_project_dir/.venv/bin/antenna-grc" "$@"
fi
exec /Users/ofi/radioconda/bin/antenna-grc "$@"
