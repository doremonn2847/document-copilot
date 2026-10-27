import importlib.util
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def module():
    path = Path(__file__).resolve().parents[2] / "deploy" / "push_railway_env.py"
    spec = importlib.util.spec_from_file_location("deploy_env", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_windows_cli_is_resolved_and_secret_stays_on_stdin(module, monkeypatch, capsys):
    resolved = "C:/tools/railway.cmd"
    monkeypatch.setattr(shutil, "which", lambda name: resolved)
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(module.subprocess, "run", run)
    secret = "offline-sentinel-never-print"
    module.push("backend", {"OPENAI_API_KEY": secret})
    args, kwargs = calls[0]
    assert args[0] == resolved
    assert kwargs["input"] == secret
    assert secret not in str(args)
    assert secret not in capsys.readouterr().out
    assert kwargs["check"] is False


def test_missing_cli_does_not_attempt_upload(module, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(SystemExit, match="not found on PATH"):
        module.push("backend", {"OPENAI_API_KEY": "offline-sentinel"})


def test_failed_upload_never_repeats_service_error_or_secret(
    module, monkeypatch, capsys
):
    monkeypatch.setattr(shutil, "which", lambda name: "railway")
    secret = "offline-sentinel-never-print"
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr=secret),
    )
    with pytest.raises(SystemExit) as failure:
        module.push("backend", {"OPENAI_API_KEY": secret})
    assert secret not in str(failure.value)
    assert secret not in capsys.readouterr().out


def test_publish_uses_pooler_and_public_frontend_without_admin_secrets(
    module, monkeypatch
):
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "push_railway_env.py",
            "--backend-url",
            "https://api.example.com",
            "--frontend-url",
            "https://app.example.com",
        ],
    )

    def read(path):
        if path.parent.name == "backend":
            return {
                "DATABASE_URL": "postgresql://offline:sentinel@aws.pooler.supabase.com:5432/postgres",
                "DATABASE_PASSWORD": "standalone-admin-secret",
                "SUPABASE_SERVICE_ROLE_KEY": "admin-secret",
                "ALLOWED_ORIGINS": "http://localhost:5173",
            }
        return {
            "VITE_SUPABASE_URL": "https://example.supabase.co",
            "VITE_SUPABASE_ANON_KEY": "public-key",
        }

    monkeypatch.setattr(module, "read_env", read)
    uploads = {}
    monkeypatch.setattr(
        module, "push", lambda service, values: uploads.update({service: values})
    )
    module.main()
    assert "DATABASE_PASSWORD" not in uploads["backend"]
    assert "SUPABASE_SERVICE_ROLE_KEY" not in uploads["backend"]
    assert ":6543/" in uploads["backend"]["DATABASE_URL"]
    assert uploads["backend"]["ALLOWED_ORIGINS"] == "https://app.example.com"
    assert set(uploads["frontend"]) == {
        "VITE_SUPABASE_URL",
        "VITE_SUPABASE_ANON_KEY",
        "VITE_API_BASE_URL",
    }
