# Issue #1 — live recording checklist

Controlled judging rehearsal for `s6pa1rta3n-lab/universal_bounty_fleet#1`.
Capture **in order**; do not batch steps.

## Pre-flight (repo)

1. Merge `fleet-console` → `master` on upstream (if not already).
2. Redeploy Cloud Run so `/console` serves the latest bundle.
3. Local verify: `make verify` (287+ pytest, console build, dry-run).

## Recording sequence

| # | Action | Expected visible state |
|---|--------|------------------------|
| 1 | `/try` comment on issue #1 | Intake staked; `audit_status=PENDING` |
| 2 | Open **draft PR** (`Fixes #1`) with commit 1 cheat | `contracts/rehearsal-vault/src/lib.rs` planted bypass |
| 3 | `@universal_auditor` reviews planted bypass | `REQUEST_CHANGES`; console **`BLOCKED — MERGE DENIED / auth_bypass`** |
| 4 | Push fix commit (commit 2 clean vault) | `APPROVE`; `audit_status=PASS`; `merge_allowed=true` |
| 5 | Film `/console` + Cloud Run / Vertex / Firestore (~5s) | CLEARED banner |
| 6 | Human clicks merge | Demo gate — not the bot |

## Commit 2 content

Replace `contracts/rehearsal-vault/src/lib.rs` with:

`fixtures/bounty-rehearsal/issue-1/commit-2-clean.rs`

## Out of scope

- Do not hunt extra OSS PRs or submit `bounty_operations`.
- Do not use a god-token.
- Do not mark ready-for-review before the auditor fails closed once.
