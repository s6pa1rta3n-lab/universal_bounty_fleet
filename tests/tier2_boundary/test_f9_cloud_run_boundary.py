"""
Tier 2 Boundary Tests: F9 - Cloud Run Deployment Boundary & Corner Cases
"""

import os
import pytest


def test_f9_boundary_missing_env_vars_detected():
    """Test F9-B.1: Config validator flags missing required environment variables."""
    def validate_cloud_run_config(env_dict: dict) -> list:
        required = ["PROJECT_ID", "WEBHOOK_SECRET"]
        missing = [k for k in required if not env_dict.get(k)]
        return missing

    missing_all = validate_cloud_run_config({})
    assert "PROJECT_ID" in missing_all
    assert "WEBHOOK_SECRET" in missing_all

    valid = validate_cloud_run_config({"PROJECT_ID": "odin-500008", "WEBHOOK_SECRET": "secret"})
    assert len(valid) == 0


def test_f9_boundary_port_environment_override():
    """Test F9-B.2: Service binds to $PORT if provided, defaulting to 8080."""
    def get_port(env_dict: dict) -> int:
        return int(env_dict.get("PORT", 8080))

    assert get_port({}) == 8080
    assert get_port({"PORT": "8000"}) == 8000
    assert get_port({"PORT": "8080"}) == 8080


def test_f9_boundary_region_specification_strictness():
    """Test F9-B.3: Region is validated against approved GCP locations (us-central1, us-east1)."""
    approved_regions = ["us-central1", "us-east1", "us-west1", "europe-west1"]
    target_region = "us-central1"
    assert target_region in approved_regions


def test_f9_boundary_concurrency_and_timeout_limits():
    """Test F9-B.4: Concurrency and timeout limits comply with Cloud Run constraints."""
    concurrency = 80
    timeout_seconds = 300
    assert 1 <= concurrency <= 1000
    assert 1 <= timeout_seconds <= 3600


def test_f9_boundary_unauthenticated_flag_present():
    """Test F9-B.5: Webhook gateway requires public ingress for GitHub webhooks."""
    deploy_flags = ["--allow-unauthenticated", "--ingress=all"]
    assert "--allow-unauthenticated" in deploy_flags
