from supabase import AsyncClient, AsyncClientOptions, acreate_client

from app.config import settings


async def create_user_client(access_token: str) -> AsyncClient:
    return await acreate_client(
        str(settings.supabase_url).rstrip("/"),
        settings.supabase_anon_key.get_secret_value(),
        options=AsyncClientOptions(
            headers={"Authorization": f"Bearer {access_token}"},
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


async def create_admin_client() -> AsyncClient:
    if settings.supabase_service_role_key is None:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not configured")
    return await acreate_client(
        str(settings.supabase_url).rstrip("/"),
        settings.supabase_service_role_key.get_secret_value(),
        options=AsyncClientOptions(
            auto_refresh_token=False,
            persist_session=False,
        ),
    )