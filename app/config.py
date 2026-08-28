"""Configuration settings for The Universal Bounty Fleet."""

import os
from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Cloud Platform Settings
    gcp_project: str = Field(
        default="odin-500008",
        validation_alias="GCP_PROJECT",
        description="Target GCP Project ID",
    )
    gcp_region: str = Field(
        default="us-central1",
        validation_alias="GCP_REGION",
        description="Target GCP Region",
    )
    vertex_ai_location: str = Field(
        default="us-central1",
        validation_alias="VERTEX_AI_LOCATION",
        description="Vertex AI regional endpoint",
    )
    quota_project_id: str = Field(
        default="odin-500008",
        validation_alias="QUOTA_PROJECT_ID",
        description="Quota Project ID for ADC Vertex AI operations",
    )

    # GitHub Settings
    github_token: Optional[str] = Field(
        default=None,
        validation_alias="GITHUB_TOKEN",
        description="GitHub Personal Access Token or App Token",
    )
    github_webhook_secret: Optional[str] = Field(
        default="ubf-dev-secret-2026",
        validation_alias="GITHUB_WEBHOOK_SECRET",
        description="HMAC secret key for GitHub webhook validation",
    )

    # Server Settings
    port: int = Field(
        default=8080,
        validation_alias="PORT",
        description="HTTP Server Port",
    )
    host: str = Field(
        default="0.0.0.0",
        validation_alias="HOST",
        description="HTTP Server Host",
    )
    app_env: str = Field(
        default="development",
        validation_alias="APP_ENV",
        description="Environment name (development, staging, production)",
    )

    # Firestore Settings
    firestore_database: str = Field(
        default="(default)",
        validation_alias="FIRESTORE_DATABASE",
        description="Firestore database name",
    )
    firestore_emulator_host: Optional[str] = Field(
        default=None,
        validation_alias="FIRESTORE_EMULATOR_HOST",
        description="Firestore emulator host for local testing",
    )
    use_in_memory_firestore: bool = Field(
        default=False,
        validation_alias="USE_IN_MEMORY_FIRESTORE",
        description="Force use of in-memory lock transport for testing",
    )

    # Payout Routing Invariant Addresses
    evm_payout_address: str = Field(
        default="0xF7b492cCBA473254E392Df444ce2dF4BE0AA29F4",
        validation_alias="EVM_PAYOUT_ADDRESS",
        description="Standard EVM payout wallet address",
    )
    stellar_payout_address: str = Field(
        default="GCL6OXAMLD75BMTINA6EMRUDWK5THQUSHMYNLSNBCJAPZJHNYJTUNIBC",
        validation_alias="STELLAR_PAYOUT_ADDRESS",
        description="Standard Stellar/Soroban payout address",
    )


@lru_cache()
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()
