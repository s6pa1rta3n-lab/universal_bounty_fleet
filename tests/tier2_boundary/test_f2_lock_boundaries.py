"""Tier 2 Boundary Tests: Feature 2 - Firestore Lock Boundary & Edge Cases."""

import time
import pytest
from app.security.firestore_lock import InMemoryFirestoreLock


class TestFeature2LockBoundaries:
    """Tier 2: >= 5 boundary and corner-case tests for Firestore Locks."""

    def test_f2_t2_01_zero_ttl_lock_expires_immediately(self):
        lock_mgr = InMemoryFirestoreLock()
        assert lock_mgr.acquire_lock("zero-ttl", ttl_seconds=0) is True
        time.sleep(0.005)
        assert lock_mgr.is_locked("zero-ttl") is False

    def test_f2_t2_02_negative_ttl_handled_as_expired(self):
        lock_mgr = InMemoryFirestoreLock()
        lock_mgr.acquire_lock("neg-ttl", ttl_seconds=-10)
        assert lock_mgr.is_locked("neg-ttl") is False

    def test_f2_t2_03_empty_lock_key_handling(self):
        lock_mgr = InMemoryFirestoreLock()
        assert lock_mgr.acquire_lock("", ttl_seconds=30, owner_id="empty-key-owner") is True
        assert lock_mgr.is_locked("") is True
        assert lock_mgr.release_lock("", owner_id="empty-key-owner") is True

    def test_f2_t2_04_release_non_existent_lock(self):
        lock_mgr = InMemoryFirestoreLock()
        assert lock_mgr.release_lock("ghost-lock") is False

    def test_f2_t2_05_event_record_not_found(self):
        lock_mgr = InMemoryFirestoreLock()
        assert lock_mgr.get_event_record("non-existent-uuid") is None
        assert lock_mgr.is_event_processed("non-existent-uuid") is False
