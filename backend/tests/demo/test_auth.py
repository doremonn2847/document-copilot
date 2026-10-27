from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import dependencies
from app.auth.dependencies import get_current_user


@pytest.mark.anyio
@pytest.mark.parametrize(
    "anonymous,profile,expected",
    [
        (True, True, 200),
        (True, False, 403),
        (False, True, 403),
        (False, False, 200),
        (False, None, 403),
    ],
)
async def test_verified_identity_must_match_server_profile(
    monkeypatch, anonymous, profile, expected
):
    user_id = str(uuid4())

    def handler(req):
        if req.url.path == "/auth/v1/user":
            return httpx.Response(
                200,
                json={
                    "id": user_id,
                    "email": None if anonymous else "normal@example.test",
                    "is_anonymous": anonymous,
                    "user_metadata": {"is_demo": True},
                },
            )
        assert req.url.params["select"] == "id,is_demo"
        return httpx.Response(
            200, json=[] if profile is None else [{"id": user_id, "is_demo": profile}]
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        dependencies.httpx,
        "AsyncClient",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    token = HTTPAuthorizationCredentials(scheme="Bearer", credentials="unit-test")
    if expected == 200:
        user = await get_current_user(token)
        assert user.is_demo == anonymous
        assert user.email == (None if anonymous else "normal@example.test")
    else:
        with pytest.raises(HTTPException) as error:
            await get_current_user(token)
        assert error.value.status_code == expected


@pytest.mark.anyio
async def test_demo_admission_rejects_normal_unapproved_user(monkeypatch):
    from app.api.auth import admit_demo
    from app.auth.dependencies import AuthIdentity

    with pytest.raises(HTTPException) as error:
        await admit_demo(
            AuthIdentity(id=uuid4(), email="normal@example.test", is_anonymous=False)
        )
    assert error.value.status_code == 403
