"""FastMCP server instance and entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastmcp import FastMCP

from notes_mcp.config import Settings
from notes_mcp.logging import configure_logging
from notes_mcp.search import RipgrepSearcher

settings = Settings()
configure_logging(settings.log_level)

logger = structlog.get_logger()

searcher = RipgrepSearcher(bin_path=settings.rg_bin, vault_path=settings.vault)


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Validate vault and ensure PARA directories exist on startup."""
    vault = settings.vault

    if not vault.is_dir():
        logger.warning("server.vault_not_found", path=str(vault))
        vault.mkdir(parents=True, exist_ok=True)
        logger.info("server.vault_created", path=str(vault))

    # Ensure PARA directories exist
    for bucket in settings.para_buckets:
        bucket_dir = vault / bucket
        if not bucket_dir.is_dir():
            bucket_dir.mkdir(parents=True, exist_ok=True)
            logger.info("server.para_created", bucket=bucket)

    logger.info("server.ready", vault=str(vault))
    yield
    logger.info("server.shutdown")


def _build_auth():
    """Build OAuth auth provider if GitHub credentials are configured."""
    if not settings.github_client_id or not settings.github_client_secret:
        return None

    from fastmcp.server.auth.providers.github import GitHubProvider

    return GitHubProvider(
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        base_url=settings.oauth_base_url or f"http://localhost:{settings.port}",
    )


def _build_middleware():
    """Build auth middleware with user allowlist if configured."""
    if not settings.oauth_allowed_users:
        return []

    allowed = {u.strip() for u in settings.oauth_allowed_users.split(",")}

    from fastmcp.server.auth import AuthContext
    from fastmcp.server.middleware import AuthMiddleware

    def require_allowed_user(ctx: AuthContext) -> bool:
        if ctx.token is None:
            logger.warning("auth.rejected", reason="no_token")
            return False
        login = ctx.token.claims.get("login", "")
        if login in allowed:
            logger.info("auth.allowed", login=login)
            return True
        logger.warning("auth.rejected", login=login, reason="not_in_allowlist")
        return False

    return [AuthMiddleware(auth=require_allowed_user)]


mcp = FastMCP(
    name="Notes MCP",
    auth=_build_auth(),
    middleware=_build_middleware(),
    lifespan=_lifespan,
)

# Import tools to register them with the mcp instance
import notes_mcp.tools.navigating  # noqa: F401, E402
import notes_mcp.tools.organizing  # noqa: F401, E402
import notes_mcp.tools.reading  # noqa: F401, E402
import notes_mcp.tools.searching  # noqa: F401, E402
import notes_mcp.tools.writing  # noqa: F401, E402


def main() -> None:
    """Entry point for the MCP server."""
    logger.info(
        "server.starting",
        transport=settings.transport,
        host=settings.host,
        port=settings.port,
        vault=str(settings.vault),
        auth_enabled=settings.github_client_id is not None,
    )
    if settings.transport == "http":
        mcp.run(transport="http", host=settings.host, port=settings.port)
    else:
        mcp.run()
