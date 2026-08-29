# Bounty rehearsal — issue #1 (`auth_bypass`)

Executor save-state for the GrantFox judging loop on
`s6pa1rta3n-lab/universal_bounty_fleet#1`.

| Step | Artifact | Expected auditor outcome |
|------|----------|--------------------------|
| Draft PR opened (commit 1) | `contracts/rehearsal-vault/src/lib.rs` | `REQUEST_CHANGES`, `audit_status=FAIL` |
| Fix pushed (commit 2) | `fixtures/.../commit-2-clean.rs` replaces `lib.rs` | `APPROVE`, `audit_status=PASS` |

Open as a **draft PR** linking `Fixes #1`. Do not mark ready-for-review until
the auditor has failed closed once on the planted bypass.

Export unified diffs: `bash scripts/export_rehearsal_diffs.sh`

Live recording checklist: `REHEARSAL_OPERATOR.md`  
PR description template: `PR_BODY.md`  
Submission metadata: `submissions/issue-1/submission.json`
