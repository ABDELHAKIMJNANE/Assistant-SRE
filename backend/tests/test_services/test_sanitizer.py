"""Tests unitaires du Sanitizer (service layer)."""
from app.services.sanitizer import sanitize_text, sanitize_logs


class TestSanitizeText:
    def test_password_masking(self):
        raw = "Connection: password=MySecret123 established"
        cleaned = sanitize_text(raw)
        assert "MySecret123" not in cleaned
        assert "password=***" in cleaned

    def test_token_masking(self):
        raw = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature"
        cleaned = sanitize_text(raw)
        assert "eyJ" not in cleaned
        assert "Bearer ***" in cleaned

    def test_ip_masking(self):
        raw = "Client IP: 192.168.1.100 connected to server 10.0.1.50"
        cleaned = sanitize_text(raw)
        assert "192.168.1.100" not in cleaned
        assert "X.X.X.X" in cleaned

    def test_connection_string_masking(self):
        raw = "mongodb://admin:SuperSecret@host.cosmos.azure.com:10255"
        cleaned = sanitize_text(raw)
        assert "SuperSecret" not in cleaned
        assert "***" in cleaned

    def test_normal_text_unchanged(self):
        raw = "INFO: Request completed in 150ms - status 200"
        cleaned = sanitize_text(raw)
        assert "Request completed" in cleaned


class TestSanitizeLogs:
    def test_truncation(self):
        logs = [f"Log line {i}" for i in range(100)]
        result = sanitize_logs(logs, max_lines=50)
        assert len(result) == 50

    def test_empty_logs(self):
        result = sanitize_logs([], max_lines=50)
        assert result == []

    def test_sanitization_applied(self):
        logs = ["password=secret123", "Normal log line"]
        result = sanitize_logs(logs, max_lines=50)
        assert "secret123" not in result[0]
