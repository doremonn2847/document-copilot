# Production image for the Railway backend service. Python and uv match local
# development; secrets come from Railway variables, never from a copied .env.
FROM python:3.14.7-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
RUN uv sync --locked

EXPOSE 8001
# Railway terminates HTTPS and sets PORT; trust its forwarded headers.
CMD ["sh", "-c", "exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001} --proxy-headers --forwarded-allow-ips='*'"]
