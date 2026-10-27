import pytest
from pydantic import ValidationError

from app.config import Settings, settings


@pytest.mark.parametrize(
    "change",
    [
        {"demo_daily_budget_usd": 0},
        {"demo_daily_budget_usd": "1.01"},
        {"demo_attempts_per_visitor": 4},
        {"demo_daily_admissions": 101},
        {"openai_chat_model": "unreviewed-model"},
        {"openai_title_model": "unreviewed-model"},
        {"assistant_output_tokens": 20000},
        {"openai_embedding_dimensions": 1024},
        {"assistant_deadline_seconds": 240},
    ],
)
def test_demo_fails_closed_for_unsupported_configuration(change):
    values = {
        **settings.model_dump(),
        "demo_enabled": True,
        "assistant_reasoning_effort": "none",
        **change,
    }
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_demo_off_preserves_regular_model_selection():
    values = {
        **settings.model_dump(),
        "demo_enabled": False,
        "openai_chat_model": "gpt-4.1-mini",
        "assistant_reasoning_effort": "none",
    }
    assert Settings(_env_file=None, **values).demo_enabled is False
