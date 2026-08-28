pub fn execute_payout() {
    require_auth();
    distribute_tokens();
}
