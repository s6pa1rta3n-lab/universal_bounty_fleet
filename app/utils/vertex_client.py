"""Vertex AI Client Factory & Wrapper for Gemini Enterprise Reasoning.

Handles Google Application Default Credentials (ADC), quota project binding
(quota_project_id="odin-500008"), and structured generation via the google-genai SDK.
"""

import json
import logging
import os
import subprocess
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel
from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class VertexClientFactory:
    """Factory for initializing configured Google GenAI Vertex AI clients."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        quota_project_id: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.project_id = project_id or settings.gcp_project
        self.location = location or settings.vertex_ai_location
        self.quota_project_id = quota_project_id or settings.quota_project_id
        self._client: Optional[Any] = None
        self._credentials: Optional[Any] = None

    def get_credentials(self) -> Any:
        """Obtain Google OAuth2 credentials with explicit quota_project_id."""
        if self._credentials is not None:
            return self._credentials
        try:
            import google.auth
            from google.oauth2.credentials import Credentials

            # First attempt standard google.auth default with quota_project_id
            try:
                credentials, detected_project = google.auth.default(
                    quota_project_id=self.quota_project_id
                )
                if credentials:
                    self._credentials = credentials
                    return self._credentials
            except Exception as auth_err:
                logger.debug("google.auth.default with quota_project_id failed: %s", auth_err)

            # Secondary mechanism: obtain access token via gcloud CLI if running locally
            try:
                token_out = (
                    subprocess.check_output(["gcloud", "auth", "print-access-token"], timeout=5)
                    .decode("utf-8")
                    .strip()
                )
                if token_out:
                    self._credentials = Credentials(token=token_out, quota_project_id=self.quota_project_id)
                    return self._credentials
            except Exception as cli_err:
                logger.debug("gcloud auth print-access-token fallback failed: %s", cli_err)

            # Fallback to base credentials without explicit quota project
            credentials, _ = google.auth.default()
            self._credentials = credentials
            return self._credentials
        except Exception as exc:
            logger.warning("Could not initialize Google Credentials: %s", exc)
            return None

    def get_client(self) -> Any:
        """Initialize or retrieve the cached genai.Client in Vertex AI mode."""
        if self._client is not None:
            return self._client

        try:
            from google import genai

            credentials = self.get_credentials()
            kwargs: Dict[str, Any] = {
                "vertexai": True,
                "project": self.project_id,
                "location": self.location,
            }
            if credentials is not None:
                kwargs["credentials"] = credentials

            self._client = genai.Client(**kwargs)
            logger.info(
                "Initialized Vertex AI Client (project=%s, location=%s, quota_project=%s)",
                self.project_id,
                self.location,
                self.quota_project_id,
            )
            return self._client
        except Exception as exc:
            logger.error("Failed to construct Vertex AI genai.Client: %s", exc)
            raise

    def generate_text(
        self,
        prompt: str,
        model: str = "gemini-2.5-flash",
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        """Generate textual response using Vertex AI Gemini model."""
        client = self.get_client()
        config: Dict[str, Any] = {"temperature": temperature}
        if system_instruction:
            config["system_instruction"] = system_instruction

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        return getattr(response, "text", str(response))

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        model: str = "gemini-2.5-flash",
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> T:
        """Generate Pydantic structured output using Vertex AI Gemini model."""
        client = self.get_client()
        config: Dict[str, Any] = {
            "temperature": temperature,
            "response_mime_type": "application/json",
            "response_schema": response_schema,
        }
        if system_instruction:
            config["system_instruction"] = system_instruction

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )

        text = getattr(response, "text", "")
        if not text:
            # Fallback if raw parsed object is returned
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, response_schema):
                return parsed
            raise ValueError("Vertex AI response contained empty text")

        return response_schema.model_validate_json(text)


# Global singleton instance
_vertex_factory_instance: Optional[VertexClientFactory] = None


def get_vertex_client(
    project_id: Optional[str] = None,
    location: Optional[str] = None,
) -> VertexClientFactory:
    """Retrieve global VertexClientFactory instance."""
    global _vertex_factory_instance
    if _vertex_factory_instance is None or project_id or location:
        _vertex_factory_instance = VertexClientFactory(
            project_id=project_id,
            location=location,
        )
    return _vertex_factory_instance
