"""Set an existing app user's password without a recovery redirect."""

from getpass import getpass
from uuid import UUID

import httpx

from app.config import settings


def main() -> None:
    user_id = UUID(input("Supabase Auth user UID: ").strip())
    password = getpass("New app user password (hidden): ")
    if not password or password != getpass("Confirm password (hidden): "):
        raise SystemExit("Passwords are empty or do not match; nothing changed")
    key = settings.supabase_service_role_key.get_secret_value()
    try:
        response = httpx.put(
            f"{str(settings.supabase_url).rstrip('/')}/auth/v1/admin/users/{user_id}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            json={"password": password},
            timeout=10,
        )
    except httpx.HTTPError:
        raise SystemExit(
            "Admin API request failed; verify the account before retrying"
        ) from None
    if response.status_code != 200:
        raise SystemExit(
            f"Password update rejected (HTTP {response.status_code}). "
            "Check the user UID, service-role key, and project password policy."
        )
    print("App user password updated. Run: uv run python scripts/check_sign_in.py")


if __name__ == "__main__":
    main()
