#!/usr/bin/env bash
# Local PR verification: unit tests + Fleet Console production build.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

echo ">>> Branch diff vs master (bounty deliverable):"
git diff --stat master...HEAD

make verify
