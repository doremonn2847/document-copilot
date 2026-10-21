from pathlib import Path
from typing import Literal, Self

from pydantic import (
    Field,
    HttpUrl,
    PostgresDsn,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_ai.profiles.openai import openai_model_profile
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
    openai_chat_model: str = Field(default="gpt-4o-mini", min_length=1)
    ingestion_chunk_tokens: int = Field(default=1024, ge=32, le=8191)
    retrieval_candidate_k: int = Field(default=50, ge=3)
    retrieval_top_k: int = Field(default=10, gt=0)
    retrieval_rrf_k: int = Field(default=60, gt=0)
    retrieval_neighbor_radius: int = Field(default=1, ge=0, le=3)
    retrieval_fts_config: Literal["english"] = "english"
    retrieval_fts_keyword_model: str = Field(default="gpt-4o-mini", min_length=1)
    retrieval_fts_keyword_min: int = Field(default=3, ge=3, le=5)
    retrieval_fts_keyword_max: int = Field(default=5, ge=3, le=5)
    retrieval_fts_keyword_fast_path_tokens: int = Field(default=5, gt=0)
    openai_grounding_model: str = Field(default="gpt-4o-mini", min_length=1)
    assistant_reasoning_effort: Literal["none", "minimal", "low", "medium", "high"] = (
        "minimal"
    )
    openai_agent_request_limit: int = Field(default=20, ge=2)
    assistant_output_retries: int = Field(default=1, ge=0, le=1)
    assistant_grounding_repairs: int = Field(default=1, ge=0, le=1)
    assistant_tool_calls: int = Field(default=12, gt=0)
    assistant_search_calls: int = Field(default=4, gt=0)
    assistant_read_batch: int = Field(default=5, gt=0, le=5)
    assistant_max_chunks: int = Field(default=50, gt=0)
    assistant_evidence_chars: int = Field(default=48000, gt=0)
    assistant_tool_chars: int = Field(default=12000, ge=6000)
    # A comparison's single tool response must give every target citable text.
    assistant_comparison_target_chars: int = Field(default=1500, gt=0)
    assistant_max_claims: int = Field(default=20, gt=0, le=20)
    assistant_claim_refs: int = Field(default=5, gt=0, le=5)
    assistant_output_tokens: int = Field(default=3000, gt=0)
    grounding_output_tokens: int = Field(default=2000, gt=0)
    assistant_deadline_seconds: int = Field(default=120, gt=0)
    assistant_history_pairs: int = Field(default=6, ge=0, le=6)
    assistant_history_chars: int = Field(default=12000, ge=0)

    @field_validator(
        "openai_chat_model",
        "openai_grounding_model",
        "openai_embedding_model",
        "retrieval_fts_keyword_model",
    )
    @classmethod
    def nonblank_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Model name must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def validate_retrieval_limits(self) -> Self:
        gpt54_mini_selected = any(
            model == "gpt-5.4-mini" or model.startswith("gpt-5.4-mini-")
            for model in (self.openai_chat_model, self.openai_grounding_model)
        )
        if gpt54_mini_selected and self.assistant_reasoning_effort != "none":
            raise ValueError(
                "This Chat Completions integration uses gpt-5.4-mini's default reasoning; set ASSISTANT_REASONING_EFFORT=none to omit the rejected reasoning_effort parameter"
            )
        if self.assistant_reasoning_effort == "none":
            for model in (self.openai_chat_model, self.openai_grounding_model):
                profile = openai_model_profile(model)
                if (
                    profile
                    and profile.get("openai_supports_reasoning")
                    and not profile.get("openai_supports_reasoning_effort_none")
                ):
                    raise ValueError(
                        "The selected reasoning model cannot disable reasoning"
                    )
        if self.assistant_search_calls > self.assistant_tool_calls:
            raise ValueError("Search budget must not exceed tool budget")
        if self.assistant_tool_chars > self.assistant_evidence_chars:
            raise ValueError("Tool output limit must not exceed evidence budget")
        if self.retrieval_top_k > self.retrieval_candidate_k:
            raise ValueError("Retrieval top_k must not exceed candidate_k")
        if self.retrieval_fts_keyword_min > self.retrieval_fts_keyword_max:
            raise ValueError("Keyword minimum must not exceed maximum")
        return self

    @field_validator("supabase_anon_key", "supabase_service_role_key", "openai_api_key")
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
                raise ValueError(
                    "CORS origins must not contain paths, queries, or fragments"
                )
            if url.username or url.password:
                raise ValueError("CORS origins must not contain credentials")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/") for origin in self.allowed_origins.split(",")
        ]


settings = Settings()
