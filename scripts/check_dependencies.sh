#!/bin/sh
set -eu

# The repository currently has no package lockfiles. Scan any that are added,
# including ignored paths in the supplied snapshot, without advisory ignores.
exec osv-scanner scan source \
    --recursive \
    --no-ignore \
    --all-vulns \
    --allow-no-lockfiles \
    --config=/dev/null \
    "$1"
