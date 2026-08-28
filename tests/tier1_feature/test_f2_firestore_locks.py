"""Tier 1 Feature Tests: Feature 2 - Firestore Distributed Lock & Idempotency."""

import pytest
from app.security.firestore_lock import InMemoryFirestoreLock


class TestFeature2FirestoreLocks:
    """Tier 1: >= 5 direct feature behavior tests for Firestore Locks & Idempotency."""

    def test_f2_t1_01_lock_acquisition_success(self):
        lock_mgr = InMemoryFirestoreLock()
        assert lock_mgr.acquire_lock("resource-lock-01", ttl_seconds=60, owner_id="agent-1") is True
        assert lock_mgr.is_locked("resource-lock-01") is True

    def test_f2_t1_02_lock_release_success(self):
        lock_mgr = InMemoryFirestoreLock()
        lock_mgr.acquire_lock("resource-lock-02", ttl_seconds=60, owner_id="agent-1")
        assert lock_mgr.release_lock("resource-lock-02", owner_id="agent-1") is True
        assert lock_mgr.is_locked("resource-lock-02") is False

    def test_f2_t1_03_lock_mutual_exclusion(self):
        lock_mgr = InMemoryFirestoreLock()
        assert lock_mgr.acquire_lock("bounty-mutex", ttl_seconds=60, owner_id="worker-A") is True
        # Worker B fails
        assert lock_mgr.acquire_lock("bounty-mutex", ttl_seconds=60, owner_id="worker-B") is False

    def test_f2_t1_04_delivery_idempotency_tracking(self):
        lock_mgr = InMemoryFirestoreLock()
        delivery_uuid = "uuid-1234-5678"
        assert lock_mgr.mark_event_processed(delivery_uuid, "issues") is True
        assert lock_mgr.is_event_processed(delivery_uuid) is True
        # Duplicate fails
        assert lock_mgr.mark_event_processed(delivery_uuid, "issues") is False

    def test_f2_t1_05_event_metadata_storage(self):
        lock_mgr = InMemoryFirestoreLock()
        delivery_uuid = "uuid-audit-999"
        lock_mgr.mark_event_processed(
            delivery_uuid,
            "pull_request",
            metadata={"pr_number": 42, "repo": "stellar-org/soroban-contracts"},
        )
        record = lock_mgr.get_event_record(delivery_uuid)
        assert record is not None
        assert record["event_type"] == "pull_request"
        assert record["metadata"]["repo"] == "stellar-org/soroban-contracts"
