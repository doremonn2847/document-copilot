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


def test_retrieval_settings_limits(settings_class):
    settings = settings_class(_env_file=None)
    assert settings.retrieval_candidate_k == 50
    assert settings.retrieval_fts_keyword_model == "gpt-4o-mini"
    for overrides in (
        {"retrieval_top_k": 51},
        {"retrieval_rrf_k": 0},
        {"retrieval_fts_config": "simple"},
        {"retrieval_fts_keyword_min": 5, "retrieval_fts_keyword_max": 3},
        {"retrieval_fts_keyword_min": 1, "retrieval_fts_keyword_max": 2},
    ):
        with pytest.raises(ValidationError):
            settings_class(_env_file=None, **overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"openai_grounding_model": " "},
        {"openai_chat_model": " "},
        {"assistant_search_calls": 13},
        {"assistant_tool_calls": 0},
        {"assistant_tool_chars": 50000},
        {"assistant_grounding_repairs": 2},
        {"assistant_claim_refs": 9},
        {"assistant_deadline_seconds": 0},
        {"assistant_reasoning_effort": "invalid"},
    ],
)
def test_grounded_answer_settings_limits(settings_class, overrides):
    with pytest.raises(ValidationError):
        settings_class(_env_file=None, **overrides)


@pytest.mark.parametrize("field", ["openai_chat_model", "openai_grounding_model"])
@pytest.mark.parametrize("model", ["gpt-5.4-mini", "gpt-5.4-mini-2026-03-17"])
def test_gpt54_mini_requires_a_supported_reasoning_effort(settings_class, field, model):
    for effort in ("minimal", "low"):
        with pytest.raises(ValidationError):
            settings_class(
                _env_file=None, **{field: model}, assistant_reasoning_effort=effort
            )
    configured = settings_class(
        _env_file=None,
        **{field: model},
        assistant_reasoning_effort="none",
        assistant_output_tokens=4000,
    )
    assert configured.assistant_output_tokens == 4000


def test_nano_cannot_use_disabled_reasoning(settings_class):
    with pytest.raises(ValidationError):
        settings_class(
            _env_file=None,
            openai_chat_model="gpt-5-nano",
            assistant_reasoning_effort="none",
        )


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


@pytest.mark.parametrize(
    "token,auth_status,approved,expected",
    [
        (None, 200, True, 401),
        ("invalid", 401, True, 401),
        ("expired-test-token", 403, True, 401),
        ("unapproved", 200, False, 403),
        ("approved", 200, True, 200),
        ("upstream-error", 500, True, 502),
    ],
)
def test_auth_boundary(
    settings_class, monkeypatch, token, auth_status, approved, expected
):
    import httpx
    from fastapi.testclient import TestClient

    from app.auth import dependencies
    from app.main import app

    user_id = "00000000-0000-0000-0000-000000000001"
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["authorization"] == f"Bearer {token}"
        if request.url.path == "/auth/v1/user":
            return httpx.Response(
                auth_status, json={"id": user_id, "email": "analyst@example.test"}
            )
        assert request.url.path == "/rest/v1/users"
        assert request.url.params["id"] == f"eq.{user_id}"
        return httpx.Response(200, json=[{"id": user_id}] if approved else [])

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        dependencies.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(
            **kwargs,
            transport=httpx.MockTransport(handler),
        ),
    )
    response = TestClient(app).get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"} if token else {},
    )
    assert response.status_code == expected
    if token is None:
        assert requests == []
    if expected == 200:
        assert response.json() == {"id": user_id, "email": "analyst@example.test"}
    else:
        assert token is None or token not in response.text
