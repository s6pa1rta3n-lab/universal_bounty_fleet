## Summary

Fail-closed Victory Audit rehearsal for GrantFox bounty **issue #1** (`auth_bypass`).

- Plants commented-out `require_auth()` in `contracts/rehearsal-vault/src/lib.rs` (commit 1 / draft PR save-state)
- Victory Auditor must `REQUEST_CHANGES` with `audit_status=FAIL` and `merge_allowed=false`
- Fix commit replaces the vault with `fixtures/bounty-rehearsal/issue-1/commit-2-clean.rs` → `APPROVE` / `PASS`
- Fleet Console shows **`BLOCKED — MERGE DENIED / auth_bypass`** until the cheat is removed

Fixes #1

## Executor commits (recording order)

| Step | File | Expected auditor outcome |
|------|------|--------------------------|
| Draft PR opened | `contracts/rehearsal-vault/src/lib.rs` | `REQUEST_CHANGES`, `audit_status=FAIL` |
| Fix pushed | copy `commit-2-clean.rs` → `lib.rs` | `APPROVE`, `audit_status=PASS` |

Export unified diffs: `bash scripts/export_rehearsal_diffs.sh`

## Verify locally

```bash
make verify
bash submissions/issue-1/verify.sh
```

`make test` completes in ~25s (294 tests). Prior harness `Terminated` at ~97% was caused by
`GeminiCodeAuditor()` without a mock hitting live Vertex ADC (~40s); fixed in commit `9b63ac4`.

Dry-run prints the recording sequence without GitHub or Cloud Run:

```bash
PYTHONPATH=. python scripts/dry_run_issue_1.py
```

## Live loop (operator — out of PR)

See `REHEARSAL_OPERATOR.md` for `/try`, draft PR, `@universal_auditor` review, Cloud Run redeploy, and human merge gate.

**Do not mark ready-for-review until the auditor has failed closed once on the planted bypass.**
