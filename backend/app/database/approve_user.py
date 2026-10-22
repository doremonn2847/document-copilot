"""Explicitly approve an active, email-confirmed Auth account; never sends email."""

import argparse
from uuid import UUID

import psycopg

from app.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("user_id", type=UUID)
    args = parser.parse_args()
    with psycopg.connect(
        str(settings.database_url), connect_timeout=10, prepare_threshold=None
    ) as connection:
        result = connection.execute(
            """INSERT INTO public.users (id, email)
            SELECT id, email FROM auth.users
            WHERE id = %s AND email_confirmed_at IS NOT NULL
                AND email IS NOT NULL AND deleted_at IS NULL
            ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
            RETURNING id""",
            (args.user_id,),
        ).fetchone()
        if result is None:
            raise SystemExit(
                "Approval failed: no active, email-confirmed Auth user with that ID"
            )
        print("Account approved")


if __name__ == "__main__":
    main()
