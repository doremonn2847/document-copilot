import importlib

import pytest
from pydantic import ValidationError


@pytest.fixture
def settings_class(monkeypatch):
    values = {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "test-anon",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-secret",
        "DATABASE_URL": "postgresql://postgres:test-password@localhost:5432/postgres",
        "OPENAI_API_KEY": "test-openai-secret",
        "ALLOWED_ORIGINS": "http://localhost:5173, http://localhost:4173/",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return importlib.import_module("app.config").Settings


def test_origins_and_secret_representation(settings_class):
    settings = settings_class(_env_file=None)
    assert settings.cors_origins == ["http://localhost:5173", "http://localhost:4173"]
    assert settings.openai_api_key.get_secret_value() == "test-openai-secret"
    assert "test-openai-secret" not in repr(settings)
    assert "test-password" not in repr(settings)


def test_missing_required_setting(settings_class, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL")
    with pytest.raises(ValidationError) as error:
        settings_class(_env_file=None)
    assert any(item["loc"] == ("supabase_url",) for item in error.value.errors())


def test_errors_hide_input(settings_class, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "invalid-test-secret")
    with pytest.raises(ValidationError) as error:
        settings_class(_env_file=None)
    assert "invalid-test-secret" not in str(error.value)


@pytest.mark.parametrize("origin", ["*", "http://localhost:5173/path", ""])
def test_invalid_origins(settings_class, monkeypatch, origin):
    monkeypatch.setenv("ALLOWED_ORIGINS", origin)
    with pytest.raises(ValidationError):
        settings_class(_env_file=None)


def test_empty_credential(settings_class, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", " ")
    with pytest.raises(ValidationError):
        settings_class(_env_file=None)


def test_app_health_cors_and_structured_logs(settings_class, capsys):
    import json

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        for origin, expected_status in [
            ("http://localhost:5173", 200),
            ("https://unapproved.example", 400),
        ]:
            response = client.options(
                "/health",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "authorization",
                },
            )
            assert response.status_code == expected_status
            if expected_status == 200:
                assert response.headers["access-control-allow-origin"] == origin
                assert response.headers["access-control-allow-credentials"] == "true"
            else:
                assert "access-control-allow-origin" not in response.headers

    output = capsys.readouterr().out
    events = [json.loads(line)["event"] for line in output.splitlines()]
    assert events == ["application_started", "application_stopped"]
    assert "test-service-secret" not in output
    assert "test-openai-secret" not in output
