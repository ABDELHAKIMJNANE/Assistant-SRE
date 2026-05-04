"""Tests des validators et modèles Pydantic."""
import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.webhook import AlertPayload
from app.models.incident import IncidentCreate, ValidateRequest, Diagnostic
from app.models.chat import ChatRequest, ChatResponse
from app.utils.validators import validate_object_id, validate_non_empty_string, validate_alert_name


class TestAlertPayload:
    def test_valid_payload(self):
        payload = AlertPayload(alert_name="OOMKilled")
        assert payload.alert_name == "OOMKilled"
        assert payload.state == "alerting"
        assert payload.labels == {}
        assert payload.message == ""

    def test_payload_with_all_fields(self):
        payload = AlertPayload(
            alert_name="OOMKilled",
            state="firing",
            labels={"pod": "test-pod"},
            message="Container killed",
            dashboard_url="https://grafana.example.com",
        )
        assert payload.dashboard_url == "https://grafana.example.com"

    def test_alert_name_required(self):
        with pytest.raises(ValidationError):
            AlertPayload()


class TestIncidentCreate:
    def test_valid_incident(self):
        incident = IncidentCreate(alert_name="OOMKilled", state="alerting")
        assert incident.status == "ouvert"
        assert incident.validated_solution is None
        assert isinstance(incident.created_at, datetime)

    def test_diagnostic_embedded(self):
        incident = IncidentCreate(
            alert_name="OOMKilled",
            state="alerting",
            diagnostic=Diagnostic(
                cause_racine="Memory leak",
                solution="kubectl fix",
                severite="haute",
                categorie="resource_exhaustion",
            )
        )
        assert incident.diagnostic.cause_racine == "Memory leak"


class TestValidateRequest:
    def test_valid_solution(self):
        req = ValidateRequest(validated_solution="kubectl fix resources")
        assert req.validated_solution == "kubectl fix resources"

    def test_empty_solution_fails(self):
        with pytest.raises(ValidationError):
            ValidateRequest()


class TestChatModels:
    def test_chat_request(self):
        req = ChatRequest(incident_id="abc123", question="Comment résoudre ?")
        assert req.incident_id == "abc123"

    def test_chat_response(self):
        resp = ChatResponse(answer="Voici la solution.", incident_id="abc123")
        assert resp.answer == "Voici la solution."


class TestCustomValidators:
    def test_valid_object_id(self):
        oid = "507f1f77bcf86cd799439011"
        result = validate_object_id(oid)
        assert result == oid

    def test_invalid_object_id(self):
        with pytest.raises(ValueError):
            validate_object_id("not-an-id")

    def test_non_empty_string(self):
        result = validate_non_empty_string("  hello  ")
        assert result == "hello"

    def test_empty_string_fails(self):
        with pytest.raises(ValueError):
            validate_non_empty_string("   ")

    def test_validate_alert_name(self):
        result = validate_alert_name("OOMKilled")
        assert result == "OOMKilled"

    def test_alert_name_too_long(self):
        with pytest.raises(ValueError):
            validate_alert_name("x" * 256)
