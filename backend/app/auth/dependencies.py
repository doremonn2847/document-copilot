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
    email: str


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            401,
            "A valid bearer token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    headers = {
        "apikey": settings.supabase_anon_key.get_secret_value(),
        "Authorization": f"Bearer {credentials.credentials}",
    }
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
            user = CurrentUser.model_validate(response.json())
            profile = await client.get(
                "/rest/v1/users",
                headers=headers,
                params={"id": f"eq.{user.id}", "select": "id", "limit": "1"},
            )
            profile.raise_for_status()
        except (httpx.HTTPError, ValueError) as error:
            raise HTTPException(502, "Authentication service unavailable") from error
        if not profile.json():
            raise HTTPException(
                403, "This account is not approved for Document Copilot"
            )
        return user
