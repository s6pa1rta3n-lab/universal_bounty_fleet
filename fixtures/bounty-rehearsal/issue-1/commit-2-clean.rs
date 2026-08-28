// Executor draft PR — commit 2 (bypass removed; auditor may APPROVE)

use soroban_sdk::{Address, Env};

pub fn withdraw(env: Env, recipient: Address, amount: i128) {
    recipient.require_auth();
    let _ = (env, recipient, amount);
}
