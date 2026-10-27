from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings

bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: UUID
    email: str | None
    is_demo: bool = False


class AuthIdentity(BaseModel):
    id: UUID
    email: str | None = None
    is_anonymous: bool = False


def auth_headers(credentials: HTTPAuthorizationCredentials) -> dict[str, str]:
    return {
        "apikey": settings.supabase_anon_key.get_secret_value(),
        "Authorization": f"Bearer {credentials.credentials}",
    }


async def get_auth_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthIdentity:
    if credentials is None:
        raise HTTPException(
            401,
            "A valid bearer token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    headers = auth_headers(credentials)
    async with httpx.AsyncClient(
        base_url=str(settings.supabase_url).rstrip("/"),
        timeout=10,
    ) as client:
        try:
            response = await client.get("/auth/v1/user", headers=headers)
            if response.status_code in (400, 401, 403, 422):
                raise HTTPException(
                    401,
                    "Invalid or expired bearer token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            response.raise_for_status()
            user = AuthIdentity.model_validate(response.json())
            if not user.is_anonymous and not user.email:
                raise ValueError("Registered identity must have email")
            return user
        except (httpx.HTTPError, ValueError) as error:
            raise HTTPException(502, "Authentication service unavailable") from error


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> CurrentUser:
    user = await get_auth_identity(credentials)
    async with httpx.AsyncClient(
        base_url=str(settings.supabase_url).rstrip("/"), timeout=10
    ) as client:
        try:
            profile = await client.get(
                "/rest/v1/users",
                headers=auth_headers(credentials),
                params={"id": f"eq.{user.id}", "select": "id,is_demo", "limit": "1"},
            )
            profile.raise_for_status()
            rows = profile.json()
            if not isinstance(rows, list) or any(
                not isinstance(row, dict) for row in rows
            ):
                raise TypeError("Invalid profile response")
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise HTTPException(502, "Authentication service unavailable") from error
        if not rows or rows[0].get("is_demo") is not user.is_anonymous:
            raise HTTPException(
                403, "This account is not approved for Document Copilot"
            )
        return CurrentUser(
            id=user.id,
            email=None if user.is_anonymous else user.email,
            is_demo=user.is_anonymous,
        )
