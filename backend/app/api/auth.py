from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import (
    AuthIdentity,
    CurrentUser,
    get_auth_identity,
    get_current_user,
)
from app.demo.errors import DemoUnavailable
from app.demo.store import DemoStatus, DemoStore

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def current_user(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    return user


@router.post("/demo")
async def admit_demo(
    identity: Annotated[AuthIdentity, Depends(get_auth_identity)],
) -> DemoStatus:
    if not identity.is_anonymous:
        raise HTTPException(403, "Only anonymous identities may enter the demo")
    try:
        return await DemoStore().admit(identity.id)
    except DemoUnavailable as error:
        raise demo_http_error(error) from None


@router.get("/demo")
async def demo_status(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DemoStatus:
    if not user.is_demo:
        raise HTTPException(403, "This account is not a demo visitor")
    try:
        return await DemoStore().status(user.id)
    except DemoUnavailable as error:
        raise demo_http_error(error) from None


def demo_http_error(error: DemoUnavailable) -> HTTPException:
    return HTTPException(
        503 if error.reason == "unavailable" else 429,
        detail={"code": "demo_limit", "reason": error.reason},
    )
