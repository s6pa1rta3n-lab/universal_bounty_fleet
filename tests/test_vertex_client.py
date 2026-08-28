"""Unit tests for Vertex AI Client Factory & Wrapper."""

from typing import Optional
from unittest.mock import MagicMock, patch
import pytest
from pydantic import BaseModel, Field
from app.utils.vertex_client import VertexClientFactory, get_vertex_client


class SampleAuditSchema(BaseModel):
    passed: bool = Field(description="Audit pass status")
    score: int = Field(description="Security score")
    summary: str = Field(description="Audit summary")


class TestVertexClientFactory:
    """Test suite for VertexClientFactory."""

    def test_factory_initialization_defaults(self):
        factory = VertexClientFactory()
        assert factory.project_id == "odin-500008"
        assert factory.location == "us-central1"
        assert factory.quota_project_id == "odin-500008"

    def test_factory_custom_params(self):
        factory = VertexClientFactory(
            project_id="custom-project",
            location="europe-west1",
            quota_project_id="quota-project",
        )
        assert factory.project_id == "custom-project"
        assert factory.location == "europe-west1"
        assert factory.quota_project_id == "quota-project"

    def test_get_vertex_client_singleton(self):
        v1 = get_vertex_client()
        v2 = get_vertex_client()
        assert v1 is v2

    def test_generate_structured_parsing(self):
        factory = VertexClientFactory()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"passed": true, "score": 95, "summary": "Clean code verified"}'
        mock_client.models.generate_content.return_value = mock_response

        with patch.object(factory, "get_client", return_value=mock_client):
            result = factory.generate_structured(
                prompt="Audit this contract diff",
                response_schema=SampleAuditSchema,
            )

            assert isinstance(result, SampleAuditSchema)
            assert result.passed is True
            assert result.score == 95
            assert result.summary == "Clean code verified"
            mock_client.models.generate_content.assert_called_once()
