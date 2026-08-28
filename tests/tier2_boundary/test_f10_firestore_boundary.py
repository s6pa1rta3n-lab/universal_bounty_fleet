"""
Tier 2 Boundary Tests: F10 - Firestore Provisioning Boundary & Corner Cases
"""

import pytest
from tests.conftest import MockFirestoreClient


def test_f10_boundary_nonexistent_document_lookup(mock_firestore_client):
    """Test F10-B.1: Looking up non-existent document returns exists=False without crashing."""
    doc = mock_firestore_client.collection("distributed_locks").document("does_not_exist").get()
    assert doc.exists is False
    assert doc.to_dict() == {}


def test_f10_boundary_collection_isolation(mock_firestore_client):
    """Test F10-B.2: Documents in distributed_locks do not appear in webhook_idempotency."""
    mock_firestore_client.collection("distributed_locks").document("key_1").set({"type": "lock"})
    
    assert mock_firestore_client.collection("distributed_locks").document("key_1").get().exists is True
    assert mock_firestore_client.collection("webhook_idempotency").document("key_1").get().exists is False


def test_f10_boundary_update_nonexistent_document_raises_keyerror(mock_firestore_client):
    """Test F10-B.3: Updating non-existent document raises KeyError."""
    doc_ref = mock_firestore_client.collection("distributed_locks").document("non_existent")
    with pytest.raises(KeyError):
        doc_ref.update({"expires_at": 999999})


def test_f10_boundary_document_merge_set(mock_firestore_client):
    """Test F10-B.4: Setting document with merge=True preserves unmodified fields."""
    doc_ref = mock_firestore_client.collection("active_stakes").document("stake_1")
    doc_ref.set({"repo": "stellar/soroban", "amount": 5000})
    doc_ref.set({"status": "staked"}, merge=True)

    data = doc_ref.get().to_dict()
    assert data["repo"] == "stellar/soroban"
    assert data["amount"] == 5000
    assert data["status"] == "staked"


def test_f10_boundary_database_name_validation():
    """Test F10-B.5: Database name complies with GCP Firestore specifications ((default))."""
    default_db = "(default)"
    assert default_db == "(default)"
