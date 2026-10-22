"""Copy local configuration into the Railway services without printing values.

Run it yourself after `railway login` and `railway link` (from the repo root):

    python deploy/push_railway_env.py --backend-url https://<backend domain> \
        --frontend-url https://<frontend domain>

Backend: every key in backend/.env except SUPABASE_SERVICE_ROLE_KEY (only admin
scripts need it) and ALLOWED_ORIGINS, which becomes the frontend URL.
Frontend: the public VITE_SUPABASE_* keys from frontend/.env, plus
VITE_API_BASE_URL set to the backend URL. Values go to `railway variable set
--stdin`, so they never appear on a command line or in this script's output.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BACKEND_SKIP = {"SUPABASE_SERVICE_ROLE_KEY", "ALLOWED_ORIGINS"}
FRONTEND_KEYS = ("VITE_SUPABASE_URL", "VITE_SUPABASE_ANON_KEY")


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip().removeprefix("export ").strip()] = value
    return values


def origin(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc or parts.path not in ("", "/"):
        raise SystemExit(f"Expected an https origin without a path: {url}")
    return f"https://{parts.netloc}"


def push(service: str, values: dict[str, str]) -> None:
    for key, value in values.items():
        if not value:
            raise SystemExit(f"{key} is empty; fix the local .env first")
        result = subprocess.run(
            [
                "railway",
                "variable",
                "set",
                key,
                "--stdin",
                "--service",
                service,
                "--skip-deploys",
            ],
            input=value,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            # Railway's error text does not include the value sent on stdin.
            raise SystemExit(
                f"Setting {key} on {service} failed: {result.stderr.strip()}"
            )
        print(f"{service}: set {key}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backend-url", required=True)
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument("--backend-service", default="backend")
    parser.add_argument("--frontend-service", default="frontend")
    args = parser.parse_args()
    backend_url, frontend_url = origin(args.backend_url), origin(args.frontend_url)

    backend = {
        key: value
        for key, value in read_env(ROOT / "backend" / ".env").items()
        if key not in BACKEND_SKIP
    }
    backend["ALLOWED_ORIGINS"] = frontend_url
    frontend_env = read_env(ROOT / "frontend" / ".env")
    missing = [key for key in FRONTEND_KEYS if key not in frontend_env]
    if missing:
        raise SystemExit(f"frontend/.env lacks {', '.join(missing)}")
    frontend = {key: frontend_env[key] for key in FRONTEND_KEYS}
    frontend["VITE_API_BASE_URL"] = backend_url

    push(args.backend_service, backend)
    push(args.frontend_service, frontend)
    print("Done. Redeploy both services so they pick up the variables.")


if __name__ == "__main__":
    sys.exit(main())
