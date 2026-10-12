from pathlib import Path

from pydantic import Field, HttpUrl, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    supabase_url: HttpUrl
    supabase_anon_key: SecretStr
    supabase_service_role_key: SecretStr
    database_url: PostgresDsn = Field(repr=False)
    openai_api_key: SecretStr
    allowed_origins: str = Field(min_length=1)

    openai_embedding_model: str = Field(default="text-embedding-3-small", min_length=1)
    openai_embedding_dimensions: int = Field(default=1536, gt=0)
    openai_chat_model: str = Field(default="gpt-4.1", min_length=1)

    @field_validator(
        "supabase_anon_key", "supabase_service_role_key", "openai_api_key"
    )
    @classmethod
    def require_nonempty_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("Credential must not be empty")
        return value

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, value: str) -> str:
        for origin in value.split(","):
            url = HttpUrl(origin.strip())
            if url.path not in (None, "/") or url.query or url.fragment:
                raise ValueError("CORS origins must not contain paths, queries, or fragments")
            if url.username or url.password:
                raise ValueError("CORS origins must not contain credentials")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.allowed_origins.split(",")]


settings = Settings()
