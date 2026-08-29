#!/usr/bin/env bash
# Issue #1 submission verify — delegates to repo root make verify.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

echo ">>> submission verify for universal_bounty_fleet#1"
git diff --stat master...HEAD

make verify
