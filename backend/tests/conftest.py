import pytest


@pytest.fixture(autouse=True)
def no_live_titles(request, monkeypatch):
    """Offline tests never call the title model; title tests opt in."""
    if "live_titles" in request.keywords:
        return

    async def no_title(_question):
        return None

    from app.chat import streaming

    monkeypatch.setattr(streaming, "summarize_title", no_title)
