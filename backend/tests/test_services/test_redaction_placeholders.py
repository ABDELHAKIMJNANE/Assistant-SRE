"""Tests for placeholder-based evidence redaction."""

from app.services.sanitizer import filter_and_redact_evidence


def test_filter_and_redact_evidence_masks_sensitive_values_with_placeholders() -> None:
    logs = [
        "ERROR login failed password=SuperSecret token=abc123 from 10.1.2.3",
        "INFO retry for client 10.1.2.3",
    ]
    metrics = {"cpu_usage_seconds": 42.0}

    evidence, redaction_map, redacted_logs, _ = filter_and_redact_evidence(logs, metrics, max_items=50)

    combined = " ".join(evidence)
    assert "SuperSecret" not in combined
    assert "abc123" not in combined
    assert "10.1.2.3" not in combined
    assert "SECRET_1" in combined
    assert "IP_1" in combined
    assert redaction_map["IP_1"] == "10.1.2.3"
    assert redaction_map["SECRET_1"] == "SuperSecret"
    assert len(redacted_logs) <= 50
