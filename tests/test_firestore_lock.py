"""Unit tests for Firestore Distributed Lock & Idempotency Manager."""

import time
import pytest
from app.security.firestore_lock import (
    BaseLockManager,
    FirestoreLock,
    InMemoryFirestoreLock,
    get_lock_manager,
)


class TestInMemoryFirestoreLock:
    """Test suite for InMemoryFirestoreLock transport."""

    def test_acquire_and_release_lock(self):
        lock_mgr = InMemoryFirestoreLock()
        assert lock_mgr.acquire_lock("resource-1", ttl_seconds=10, owner_id="worker-1") is True
        assert lock_mgr.is_locked("resource-1") is True

        assert lock_mgr.release_lock("resource-1", owner_id="worker-1") is True
        assert lock_mgr.is_locked("resource-1") is False

    def test_concurrent_lock_conflict(self):
        lock_mgr = InMemoryFirestoreLock()
        assert lock_mgr.acquire_lock("issue-42", ttl_seconds=10, owner_id="worker-1") is True

        # Second worker cannot acquire
        assert lock_mgr.acquire_lock("issue-42", ttl_seconds=10, owner_id="worker-2") is False

    def test_lock_release_owner_mismatch_fails(self):
        lock_mgr = InMemoryFirestoreLock()
        assert lock_mgr.acquire_lock("pr-101", ttl_seconds=10, owner_id="worker-1") is True

        # Worker 2 cannot release worker 1's lock
        assert lock_mgr.release_lock("pr-101", owner_id="worker-2") is False
        assert lock_mgr.is_locked("pr-101") is True

    def test_reentrant_lock_extends_ttl(self):
        lock_mgr = InMemoryFirestoreLock()
        assert lock_mgr.acquire_lock("task-99", ttl_seconds=5, owner_id="worker-1") is True
        # Same owner re-acquires
        assert lock_mgr.acquire_lock("task-99", ttl_seconds=20, owner_id="worker-1") is True
        assert lock_mgr.is_locked("task-99") is True

    def test_expired_lock_can_be_reacquired(self):
        lock_mgr = InMemoryFirestoreLock()
        # Acquire with 0 second TTL (instant expiration)
        assert lock_mgr.acquire_lock("quick-lock", ttl_seconds=0, owner_id="worker-1") is True
        time.sleep(0.01)

        # Should be expired
        assert lock_mgr.is_locked("quick-lock") is False
        # Worker 2 can now acquire
        assert lock_mgr.acquire_lock("quick-lock", ttl_seconds=10, owner_id="worker-2") is True

    def test_mark_event_processed_idempotency(self):
        lock_mgr = InMemoryFirestoreLock()
        delivery_id = "delivery-uuid-001"

        # First delivery: should succeed
        assert lock_mgr.mark_event_processed(delivery_id, "issues", ttl_seconds=60) is True
        assert lock_mgr.is_event_processed(delivery_id) is True

        # Second delivery (duplicate): should fail (return False)
        assert lock_mgr.mark_event_processed(delivery_id, "issues", ttl_seconds=60) is False

    def test_get_event_record(self):
        lock_mgr = InMemoryFirestoreLock()
        delivery_id = "delivery-uuid-002"

        lock_mgr.mark_event_processed(
            delivery_id,
            "pull_request",
            metadata={"action": "opened", "pr_number": 5},
        )

        record = lock_mgr.get_event_record(delivery_id)
        assert record is not None
        assert record["delivery_id"] == delivery_id
        assert record["event_type"] == "pull_request"
        assert record["status"] == "PROCESSED"
        assert record["metadata"]["pr_number"] == 5

    def test_clear_resets_all_state(self):
        lock_mgr = InMemoryFirestoreLock()
        lock_mgr.acquire_lock("lock-a")
        lock_mgr.mark_event_processed("del-a", "issues")

        lock_mgr.clear()
        assert lock_mgr.is_locked("lock-a") is False
        assert lock_mgr.is_event_processed("del-a") is False


class TestGetLockManagerFactory:
    """Test suite for get_lock_manager factory."""

    def test_force_in_memory_returns_in_memory_instance(self):
        mgr = get_lock_manager(force_in_memory=True)
        assert isinstance(mgr, InMemoryFirestoreLock)

    def test_singleton_consistency(self):
        mgr1 = get_lock_manager(force_in_memory=True)
        mgr2 = get_lock_manager(force_in_memory=True)
        assert mgr1 is mgr2
