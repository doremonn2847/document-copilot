from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def current_user(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    return user
