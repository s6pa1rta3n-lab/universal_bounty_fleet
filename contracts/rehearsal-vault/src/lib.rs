// Executor draft PR — commit 1 (planted cheat for issue #1 rehearsal)
// Victory Audit must fail Pillar 2 until this bypass is removed.
// Fix commit: replace this file with fixtures/bounty-rehearsal/issue-1/commit-2-clean.rs

use soroban_sdk::{Address, Env};

pub fn withdraw_bypass(env: Env, recipient: Address, amount: i128) {
    // recipient.require_auth(); // Auth check bypassed — planted for fail-closed demo
    let _ = (env, recipient, amount);
}
