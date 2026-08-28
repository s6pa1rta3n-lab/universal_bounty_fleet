"""Memory Bank bounty key helpers — issue/PR correlation for the live loop."""

from app.memory.bank import (
    bounty_id_for_issue,
    bounty_id_for_pr,
    linked_issue_from_pr,
    sanitize_repo_slug,
)


def test_sanitize_repo_slug():
    assert sanitize_repo_slug("s6pa1rta3n-lab/universal_bounty_fleet") == (
        "s6pa1rta3n-lab-universal_bounty_fleet"
    )


def test_bounty_id_for_issue():
    assert bounty_id_for_issue("org/repo", 1) == "org-repo#1"


def test_linked_issue_from_pr_prefers_fixes_keyword():
    pr = {"title": "Vault patch", "body": "Fixes #1 for the bounty rehearsal."}
    assert linked_issue_from_pr(pr) == 1


def test_bounty_id_for_pr_links_to_parent_issue():
    pr = {"number": 9, "title": "Fixes #1", "body": ""}
    assert bounty_id_for_pr("s6pa1rta3n-lab/universal_bounty_fleet", pr) == (
        "s6pa1rta3n-lab-universal_bounty_fleet#1"
    )


def test_bounty_id_for_pr_without_issue_link():
    pr = {"number": 9, "title": "Unrelated change", "body": ""}
    assert bounty_id_for_pr("org/repo", pr) == "org-repo#pr-9"
