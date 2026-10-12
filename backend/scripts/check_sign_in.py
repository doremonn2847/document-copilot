"""Check a real Supabase password sign-in against the local FastAPI app."""

import argparse
from getpass import getpass

import httpx
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-status", type=int, choices=(200, 403), default=200)
    args = parser.parse_args()
    email = input("Account email: ").strip()
    password = getpass("Account password (hidden): ")
    try:
        response = httpx.post(
            f"{str(settings.supabase_url).rstrip('/')}/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": settings.supabase_anon_key.get_secret_value()},
            json={"email": email, "password": password},
            timeout=10,
        )
    except httpx.HTTPError:
        raise SystemExit("Cannot reach Supabase Auth; check your connection") from None
    if response.status_code != 200:
        try:
            code = response.json().get("error_code", "unknown")
        except ValueError:
            code = "unknown"
        explanations = {
            "invalid_credentials": "Supabase rejected this email/password combination.",
            "email_not_confirmed": "The account email has not been confirmed.",
            "email_provider_disabled": "Email authentication is disabled in this project.",
            "user_banned": "The account is banned.",
            "over_request_rate_limit": "Too many requests; wait before retrying.",
            "validation_failed": "Supabase rejected the sign-in request format.",
        }
        if code not in explanations:
            code = "unknown"
        raise SystemExit(
            f"Sign-in failed (HTTP {response.status_code}, code: {code}). "
            + explanations.get(code, "Check the Supabase Auth logs for the reason.")
        )
    token = response.json()["access_token"]
    # Exercise real backend dependencies without requiring a separate server.
    with TestClient(app) as client:
        result = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    print(f"/auth/me: HTTP {result.status_code}")
    if result.status_code != args.expected_status:
        raise SystemExit(f"FAIL: expected HTTP {args.expected_status}")
    if result.status_code == 200:
        identity = result.json()
        print(f"Verified account: {identity['email']} ({identity['id']})")
    print("PASS")


if __name__ == "__main__":
    main()
