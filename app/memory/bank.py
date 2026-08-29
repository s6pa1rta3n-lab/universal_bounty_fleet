"""Firestore-backed Memory Bank with an in-memory fallback for tests."""

from __future__ import annotations

import logging
import re
import threading
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

_ISSUE_LINK_RE = re.compile(
    r"(?i)(?:fix(?:e)?s|close[sd]?|resolve[sd]?)\s+#(\d+)",
)
_BARE_ISSUE_RE = re.compile(r"#(\d+)\b")


def sanitize_repo_slug(repo: str) -> str:
    """Firestore-safe repo slug (slashes would break document paths)."""
    return repo.replace("/", "-")


def bounty_id_for_issue(repo: str, issue_number: int) -> str:
    """Canonical Memory Bank key for a funded GitHub issue."""
    return f"{sanitize_repo_slug(repo)}#{issue_number}"


def linked_issue_from_pr(pr: Dict[str, Any]) -> Optional[int]:
    """Resolve the parent bounty issue from PR title/body (e.g. Fixes #1)."""
    text = " ".join(filter(None, [pr.get("title"), pr.get("body")]))
    if not text.strip():
        return None
    match = _ISSUE_LINK_RE.search(text)
    if match:
        return int(match.group(1))
    bare = _BARE_ISSUE_RE.search(text)
    if bare and any(token in text.lower() for token in ("bounty", "issue", "fixes", "closes")):
        return int(bare.group(1))
    return None


def bounty_id_for_pr(repo: str, pr: Dict[str, Any]) -> str:
    """Memory Bank key for a PR; links to the parent issue when present."""
    issue_number = linked_issue_from_pr(pr)
    if issue_number is not None:
        return bounty_id_for_issue(repo, issue_number)
    pr_number = pr.get("number") or 0
    return f"{sanitize_repo_slug(repo)}#pr-{pr_number}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_bounty(bounty_id: str) -> Dict[str, Any]:
    return {
        "bounty_id": bounty_id,
        "issue_url": None,
        "pr_url": None,
        "repo": None,
        "issue_number": None,
        "pr_number": None,
        "title": None,
        "escrow": {"verified": False, "amount_usd": 0.0, "source": None},
        "audit_status": "PENDING",
        "merge_allowed": False,
        "cheat_detected": None,
        "compute_budget": {"used_seconds": 0, "limit_seconds": 900, "killed": False},
        "agents": {
            "intake": "idle",
            "executor": "idle",
            "auditor": "idle",
        },
        "events": [],
        "gcp": {
            "project": get_settings().gcp_project,
            "region": get_settings().gcp_region,
            "firestore_doc": f"bounty_memory/{bounty_id}",
            "trace_id": None,
        },
        "source": "live",
        "updated_at": _now(),
        "created_at": _now(),
    }


def classify_cheat(findings: Optional[Dict[str, Any]]) -> Optional[str]:
    """Map 3-pillar audit failures to a single cheat label for the console."""
    if not findings:
        return None
    if findings.get("pillar1_crypto") is False:
        return "mock_cipher"
    if findings.get("pillar2_auth") is False:
        return "auth_bypass"
    if findings.get("pillar3_assertions") is False:
        return "skipped_assertion"
    return None


RECORDING_CUE_BANNER = "BLOCKED — MERGE DENIED / auth_bypass"


def console_banner_copy(bounty: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Mirror console-ui/src/render.ts bannerCopy for API→console parity."""
    if not bounty:
        return {"title": "PENDING", "cls": "PENDING", "sub": "Waiting for fleet state."}
    status = bounty.get("audit_status") or "PENDING"
    if status == "FAIL":
        cheat = bounty.get("cheat_detected")
        cheat_suffix = f" / {cheat}" if cheat else ""
        return {
            "title": f"BLOCKED — MERGE DENIED{cheat_suffix}",
            "cls": "BLOCKED",
            "sub": "Auditor holds the gate until the cheat is gone.",
        }
    if status == "PASS" and bounty.get("merge_allowed"):
        return {
            "title": "CLEARED",
            "cls": "CLEARED",
            "sub": "Auditor approved. Merge is allowed.",
        }
    return {
        "title": "PENDING",
        "cls": "PENDING",
        "sub": "Fleet in flight. Waiting for the next GitHub state change.",
    }


class InMemoryBank:
    """Thread-safe local Memory Bank used in tests and offline demos."""

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._mutex = threading.Lock()

    def upsert(self, bounty_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        with self._mutex:
            current = self._store.get(bounty_id) or _empty_bounty(bounty_id)
            current = deepcopy(current)
            for key, value in patch.items():
                if key == "escrow" and isinstance(value, dict):
                    current["escrow"] = {**current.get("escrow", {}), **value}
                elif key == "agents" and isinstance(value, dict):
                    current["agents"] = {**current.get("agents", {}), **value}
                elif key == "gcp" and isinstance(value, dict):
                    current["gcp"] = {**current.get("gcp", {}), **value}
                elif key == "compute_budget" and isinstance(value, dict):
                    current["compute_budget"] = {**current.get("compute_budget", {}), **value}
                elif key != "events":
                    current[key] = value
            current["bounty_id"] = bounty_id
            current["updated_at"] = _now()
            current["merge_allowed"] = current.get("audit_status") == "PASS"
            self._store[bounty_id] = current
            return deepcopy(current)

    def append_event(self, bounty_id: str, event_type: str, detail: str) -> Dict[str, Any]:
        with self._mutex:
            current = self._store.get(bounty_id) or _empty_bounty(bounty_id)
            current = deepcopy(current)
            current.setdefault("events", []).append(
                {"t": _now(), "type": event_type, "detail": detail}
            )
            current["updated_at"] = _now()
            self._store[bounty_id] = current
            return deepcopy(current)

    def get(self, bounty_id: str) -> Optional[Dict[str, Any]]:
        with self._mutex:
            item = self._store.get(bounty_id)
            return deepcopy(item) if item else None

    def latest(self) -> Optional[Dict[str, Any]]:
        with self._mutex:
            if not self._store:
                return None
            newest = max(self._store.values(), key=lambda item: item.get("updated_at", ""))
            return deepcopy(newest)

    def list_all(self) -> List[Dict[str, Any]]:
        with self._mutex:
            items = sorted(
                self._store.values(),
                key=lambda item: item.get("updated_at", ""),
                reverse=True,
            )
            return [deepcopy(item) for item in items]

    def clear(self) -> None:
        with self._mutex:
            self._store.clear()


class FirestoreBank:
    """Production Memory Bank persisted in Cloud Firestore."""

    collection_name = "bounty_memory"

    def __init__(self, project_id: str, database: str = "(default)") -> None:
        from google.cloud import firestore

        self._client = firestore.Client(project=project_id, database=database)

    def _col(self):
        return self._client.collection(self.collection_name)

    def upsert(self, bounty_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        doc_ref = self._col().document(bounty_id)
        snap = doc_ref.get()
        current = snap.to_dict() if snap.exists else _empty_bounty(bounty_id)
        for key, value in patch.items():
            if key in {"escrow", "agents", "gcp", "compute_budget"} and isinstance(value, dict):
                current[key] = {**(current.get(key) or {}), **value}
            elif key != "events":
                current[key] = value
        current["bounty_id"] = bounty_id
        current["updated_at"] = _now()
        current["merge_allowed"] = current.get("audit_status") == "PASS"
        doc_ref.set(current)
        return current

    def append_event(self, bounty_id: str, event_type: str, detail: str) -> Dict[str, Any]:
        current = self.get(bounty_id) or _empty_bounty(bounty_id)
        events = list(current.get("events") or [])
        events.append({"t": _now(), "type": event_type, "detail": detail})
        current["events"] = events
        current["updated_at"] = _now()
        self._col().document(bounty_id).set(current)
        return current

    def get(self, bounty_id: str) -> Optional[Dict[str, Any]]:
        snap = self._col().document(bounty_id).get()
        return snap.to_dict() if snap.exists else None

    def latest(self) -> Optional[Dict[str, Any]]:
        items = self.list_all()
        return items[0] if items else None

    def list_all(self) -> List[Dict[str, Any]]:
        docs = self._col().limit(50).stream()
        items = [doc.to_dict() or {} for doc in docs]
        return sorted(items, key=lambda item: item.get("updated_at", ""), reverse=True)

    def clear(self) -> None:
        for doc in self._col().limit(100).stream():
            doc.reference.delete()


_bank: Optional[Any] = None


def get_memory_bank(force_in_memory: Optional[bool] = None) -> Any:
    """Return the process-wide Memory Bank (Firestore or in-memory)."""
    global _bank
    settings = get_settings()
    use_memory = (
        force_in_memory
        if force_in_memory is not None
        else (settings.use_in_memory_firestore or settings.app_env == "test")
    )
    if _bank is not None:
        if use_memory and not isinstance(_bank, InMemoryBank):
            _bank = InMemoryBank()
        return _bank
    if use_memory:
        _bank = InMemoryBank()
        return _bank
    try:
        _bank = FirestoreBank(settings.gcp_project, settings.firestore_database)
    except Exception as exc:
        logger.warning("Memory Bank falling back to in-memory: %s", exc)
        _bank = InMemoryBank()
    return _bank


def seed_demo_bounty(bank: Optional[Any] = None) -> Dict[str, Any]:
    """Planted-cheat fixture so the console is filmable before the next live webhook."""
    target = bank or get_memory_bank()
    repo = "s6pa1rta3n-lab/universal_bounty_fleet"
    bounty_id = bounty_id_for_issue(repo, 1)
    existing = target.get(bounty_id)
    if existing:
        return existing
    target.upsert(
        bounty_id,
        {
            "title": "[Bounty] Fail-closed Victory Audit on planted auth_bypass",
            "repo": repo,
            "issue_number": 1,
            "pr_number": 1,
            "issue_url": f"https://github.com/{repo}/issues/1",
            "pr_url": f"https://github.com/{repo}/pull/1",
            "escrow": {"verified": True, "amount_usd": 1200.0, "source": "fixture"},
            "audit_status": "FAIL",
            "cheat_detected": "auth_bypass",
            "agents": {"intake": "idle", "executor": "waiting", "auditor": "reviewing"},
            "gcp": {"trace_id": "demo-otel-issue-1"},
            "source": "fixture",
        },
    )
    target.append_event(bounty_id, "claimed", "/try on #1 — GrantFox escrow verified")
    target.append_event(bounty_id, "draft_pr", "Draft PR #1 opened as native save-state")
    target.append_event(
        bounty_id,
        "audit_fail",
        "Pillar 2: commented-out require_auth() in vault withdraw",
    )
    return target.get(bounty_id) or {}
