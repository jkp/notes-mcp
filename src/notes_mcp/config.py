"""Configuration via environment variables using pydantic-settings."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NOTES_MCP_", env_file=".env", extra="ignore"
    )

    # Vault
    vault_path: Path = Path("~/notes")
    rg_bin: str = "rg"

    # NTFY push notifications (empty URL = disabled)
    ntfy_url: str = ""
    ntfy_topic: str = ""

    # Server
    transport: Literal["stdio", "http"] = "stdio"
    host: str = "0.0.0.0"
    port: int = 10200
    mcp_path: str = "/mcp"  # set to "/" when behind a path-stripping reverse proxy
    log_level: str = "INFO"

    # Auth (optional, for HTTP transport)
    github_client_id: str | None = None
    github_client_secret: str | None = None
    oauth_base_url: str | None = None
    oauth_allowed_users: str | None = None
    oauth_state_dir: Path | None = None

    # PARA bucket names (configurable to match vault naming convention)
    para_bucket_names: str = "projects,areas,resources,archive"

    @property
    def vault(self) -> Path:
        return self.vault_path.expanduser().resolve()

    @property
    def para_buckets(self) -> list[str]:
        return [b.strip() for b in self.para_bucket_names.split(",")]
