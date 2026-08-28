"""Distributed Locking and Idempotency Subsystem for GEAP Cloud Run.

Provides stateless event deduplication and distributed locks using Cloud Firestore
with automatic TTL expiration and in-memory mock transport for testing.
"""

import abc
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BaseLockManager(abc.ABC):
    """Abstract base class for distributed lock and idempotency managers."""

    @abc.abstractmethod
    def acquire_lock(
        self,
        lock_key: str,
        ttl_seconds: int = 300,
        owner_id: Optional[str] = None,
    ) -> bool:
        """Attempt to acquire a distributed lock.

        Args:
            lock_key: Unique identifier for the lock.
            ttl_seconds: Time-to-live in seconds before auto-expiration.
            owner_id: Optional identifier of the lock owner/process.

        Returns:
            True if acquired, False if already locked by another active process.
        """
        pass

    @abc.abstractmethod
    def release_lock(self, lock_key: str, owner_id: Optional[str] = None) -> bool:
        """Release a previously acquired lock.

        Args:
            lock_key: Unique identifier for the lock.
            owner_id: Optional identifier of the lock owner.

        Returns:
            True if released, False if not found or owner mismatch.
        """
        pass

    @abc.abstractmethod
    def is_locked(self, lock_key: str) -> bool:
        """Check if a lock is currently active and unexpired."""
        pass

    @abc.abstractmethod
    def mark_event_processed(
        self,
        delivery_id: str,
        event_type: str,
        ttl_seconds: int = 86400,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Record a GitHub webhook delivery ID as processed (idempotency key).

        Args:
            delivery_id: X-GitHub-Delivery UUID header.
            event_type: X-GitHub-Event header.
            ttl_seconds: Retention period in seconds (default 24h).
            metadata: Additional contextual payload metadata.

        Returns:
            True if successfully recorded, False if already exists (duplicate).
        """
        pass

    @abc.abstractmethod
    def is_event_processed(self, delivery_id: str) -> bool:
        """Check if a delivery ID has already been processed."""
        pass

    @abc.abstractmethod
    def get_event_record(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve stored event metadata for a delivery ID."""
        pass

    @abc.abstractmethod
    def clear(self) -> None:
        """Clear all stored locks and events (primarily for test tear-downs)."""
        pass


class InMemoryFirestoreLock(BaseLockManager):
    """Thread-safe in-memory lock and idempotency transport for local testing."""

    def __init__(self) -> None:
        self._locks: Dict[str, Dict[str, Any]] = {}
        self._events: Dict[str, Dict[str, Any]] = {}
        self._mutex = threading.Lock()

    def _now(self) -> float:
        return time.time()

    def acquire_lock(
        self,
        lock_key: str,
        ttl_seconds: int = 300,
        owner_id: Optional[str] = None,
    ) -> bool:
        with self._mutex:
            now = self._now()
            current = self._locks.get(lock_key)
            if current and current.get("expires_at", 0) > now:
                # Lock is active and unexpired
                if owner_id and current.get("owner_id") == owner_id:
                    # Re-entrant by same owner: extend TTL
                    current["expires_at"] = now + ttl_seconds
                    current["updated_at"] = now
                    return True
                return False

            # Lock does not exist or has expired
            self._locks[lock_key] = {
                "lock_key": lock_key,
                "owner_id": owner_id or "default",
                "acquired_at": now,
                "expires_at": now + ttl_seconds,
            }
            return True

    def release_lock(self, lock_key: str, owner_id: Optional[str] = None) -> bool:
        with self._mutex:
            current = self._locks.get(lock_key)
            if not current:
                return False
            if owner_id and current.get("owner_id") != owner_id:
                return False
            del self._locks[lock_key]
            return True

    def is_locked(self, lock_key: str) -> bool:
        with self._mutex:
            now = self._now()
            current = self._locks.get(lock_key)
            if current and current.get("expires_at", 0) > now:
                return True
            if current and current.get("expires_at", 0) <= now:
                del self._locks[lock_key]
            return False

    def mark_event_processed(
        self,
        delivery_id: str,
        event_type: str,
        ttl_seconds: int = 86400,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        with self._mutex:
            now = self._now()
            current = self._events.get(delivery_id)
            if current and current.get("expires_at", 0) > now:
                return False  # Already processed

            self._events[delivery_id] = {
                "delivery_id": delivery_id,
                "event_type": event_type,
                "status": "PROCESSED",
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "created_at_epoch": now,
                "expires_at": now + ttl_seconds,
                "metadata": metadata or {},
            }
            return True

    def is_event_processed(self, delivery_id: str) -> bool:
        with self._mutex:
            now = self._now()
            current = self._events.get(delivery_id)
            if current and current.get("expires_at", 0) > now:
                return True
            if current and current.get("expires_at", 0) <= now:
                del self._events[delivery_id]
            return False

    def get_event_record(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        with self._mutex:
            now = self._now()
            current = self._events.get(delivery_id)
            if current and current.get("expires_at", 0) > now:
                return dict(current)
            return None

    def clear(self) -> None:
        with self._mutex:
            self._locks.clear()
            self._events.clear()


class FirestoreLock(BaseLockManager):
    """Production Cloud Firestore distributed lock and idempotency implementation."""

    def __init__(
        self,
        project_id: str = "odin-500008",
        database: str = "(default)",
        locks_collection: str = "bounty_locks",
        events_collection: str = "bounty_events",
    ) -> None:
        self.project_id = project_id
        self.database = database
        self.locks_collection_name = locks_collection
        self.events_collection_name = events_collection
        self._client: Optional[Any] = None

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                from google.cloud import firestore

                self._client = firestore.Client(
                    project=self.project_id,
                    database=self.database,
                )
                logger.info(
                    "Initialized Firestore client for project %s (db: %s)",
                    self.project_id,
                    self.database,
                )
            except Exception as exc:
                logger.error("Failed to initialize live Firestore client: %s", exc)
                raise
        return self._client

    def acquire_lock(
        self,
        lock_key: str,
        ttl_seconds: int = 300,
        owner_id: Optional[str] = None,
    ) -> bool:
        try:
            doc_ref = self.client.collection(self.locks_collection_name).document(lock_key)
            now_epoch = time.time()
            expires_at = now_epoch + ttl_seconds
            owner = owner_id or "default"

            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict() or {}
                doc_expires = data.get("expires_at", 0)
                if doc_expires > now_epoch:
                    # Active lock exists
                    if data.get("owner_id") == owner:
                        # Extend TTL for owner
                        doc_ref.set(
                            {
                                "lock_key": lock_key,
                                "owner_id": owner,
                                "acquired_at": data.get("acquired_at", now_epoch),
                                "expires_at": expires_at,
                                "updated_at": now_epoch,
                            },
                            merge=True,
                        )
                        return True
                    return False

            # Lock does not exist or is expired; write new lock
            doc_ref.set(
                {
                    "lock_key": lock_key,
                    "owner_id": owner,
                    "acquired_at": now_epoch,
                    "expires_at": expires_at,
                }
            )
            return True
        except Exception as exc:
            logger.error("Firestore error acquiring lock %s: %s", lock_key, exc)
            return False

    def release_lock(self, lock_key: str, owner_id: Optional[str] = None) -> bool:
        try:
            doc_ref = self.client.collection(self.locks_collection_name).document(lock_key)
            doc = doc_ref.get()
            if not doc.exists:
                return False
            data = doc.to_dict() or {}
            if owner_id and data.get("owner_id") != owner_id:
                return False
            doc_ref.delete()
            return True
        except Exception as exc:
            logger.error("Firestore error releasing lock %s: %s", lock_key, exc)
            return False

    def is_locked(self, lock_key: str) -> bool:
        try:
            doc_ref = self.client.collection(self.locks_collection_name).document(lock_key)
            doc = doc_ref.get()
            if not doc.exists:
                return False
            data = doc.to_dict() or {}
            return bool(data.get("expires_at", 0) > time.time())
        except Exception as exc:
            logger.error("Firestore error checking lock %s: %s", lock_key, exc)
            return False

    def mark_event_processed(
        self,
        delivery_id: str,
        event_type: str,
        ttl_seconds: int = 86400,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            doc_ref = self.client.collection(self.events_collection_name).document(delivery_id)
            doc = doc_ref.get()
            now_epoch = time.time()
            if doc.exists:
                data = doc.to_dict() or {}
                if data.get("expires_at", 0) > now_epoch:
                    return False  # Already recorded and active

            doc_ref.set(
                {
                    "delivery_id": delivery_id,
                    "event_type": event_type,
                    "status": "PROCESSED",
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "created_at_epoch": now_epoch,
                    "expires_at": now_epoch + ttl_seconds,
                    "metadata": metadata or {},
                }
            )
            return True
        except Exception as exc:
            logger.error("Firestore error marking event %s: %s", delivery_id, exc)
            return False

    def is_event_processed(self, delivery_id: str) -> bool:
        try:
            doc_ref = self.client.collection(self.events_collection_name).document(delivery_id)
            doc = doc_ref.get()
            if not doc.exists:
                return False
            data = doc.to_dict() or {}
            return bool(data.get("expires_at", 0) > time.time())
        except Exception as exc:
            logger.error("Firestore error checking event %s: %s", delivery_id, exc)
            return False

    def get_event_record(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        try:
            doc_ref = self.client.collection(self.events_collection_name).document(delivery_id)
            doc = doc_ref.get()
            if not doc.exists:
                return None
            data = doc.to_dict() or {}
            if data.get("expires_at", 0) > time.time():
                return data
            return None
        except Exception as exc:
            logger.error("Firestore error fetching event %s: %s", delivery_id, exc)
            return None

    def clear(self) -> None:
        """Clear documents for testing (batch delete)."""
        try:
            for coll_name in [self.locks_collection_name, self.events_collection_name]:
                docs = self.client.collection(coll_name).limit(100).stream()
                for d in docs:
                    d.reference.delete()
        except Exception as exc:
            logger.warning("Error clearing Firestore collections: %s", exc)


# Global singleton instance
_lock_manager_instance: Optional[BaseLockManager] = None


def get_lock_manager(force_in_memory: Optional[bool] = None) -> BaseLockManager:
    """Retrieve or initialize the global lock and idempotency manager."""
    global _lock_manager_instance
    from app.config import get_settings

    settings = get_settings()

    should_use_in_memory = (
        force_in_memory
        if force_in_memory is not None
        else settings.use_in_memory_firestore
    )

    if _lock_manager_instance is not None:
        if should_use_in_memory and not isinstance(_lock_manager_instance, InMemoryFirestoreLock):
            _lock_manager_instance = InMemoryFirestoreLock()
        return _lock_manager_instance

    if should_use_in_memory:
        logger.info("Using InMemoryFirestoreLock transport")
        _lock_manager_instance = InMemoryFirestoreLock()
    else:
        try:
            _lock_manager_instance = FirestoreLock(
                project_id=settings.gcp_project,
                database=settings.firestore_database,
            )
        except Exception as exc:
            logger.warning("Could not initialize FirestoreLock (%s); falling back to InMemory", exc)
            _lock_manager_instance = InMemoryFirestoreLock()

    return _lock_manager_instance
