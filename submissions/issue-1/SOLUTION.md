# Solution — issue #1 (`auth_bypass`)

**Repo:** `s6pa1rta3n-lab/universal_bounty_fleet`  
**Issue:** https://github.com/s6pa1rta3n-lab/universal_bounty_fleet/issues/1  
**Reward:** $1,200 USDC (GrantFox escrow)

## What this branch delivers (PR-honest)

| Acceptance step | Automation on branch |
|-----------------|----------------------|
| Intake `/try` + escrow | Webhook intake + claim staker + Memory Bank |
| Draft PR commit 1 cheat | `contracts/rehearsal-vault/src/lib.rs` |
| Auditor `REQUEST_CHANGES` | Murder Board Pillar 2 + native GitHub review POST |
| `audit_status=FAIL`, merge blocked | Memory Bank + `merge_allowed` gate |
| Console BLOCKED banner | `BLOCKED — MERGE DENIED / auth_bypass` fixture + UI bundle |
| Fix → `APPROVE` / `PASS` | Webhook re-audit on `synchronize` + dry-run script |
| Verify entrypoint | `make test` / `make verify` |

## What still requires live ops (cannot fake in PR)

- Push branch + open draft PR on GitHub
- Real `@universal_auditor` review on the planted bypass
- Second commit on GitHub + Cloud Run redeploy
- Human merge click

See `REHEARSAL_OPERATOR.md` and `PR_BODY.md`.
