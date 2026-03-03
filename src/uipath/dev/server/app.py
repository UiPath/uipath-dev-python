"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from uipath.dev.server import UiPathDeveloperServer

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
FRONTEND_DIR = Path(__file__).parent / "frontend"

_FALLBACK_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>UiPath Developer Server</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background: #0f172a; color: #e2e8f0; display: flex; align-items: center;
           justify-content: center; min-height: 100vh; padding: 2rem; }
    .card { background: #1e293b; border-radius: 12px; padding: 2.5rem;
            max-width: 560px; width: 100%%; box-shadow: 0 4px 24px rgba(0,0,0,.4); }
    h1 { font-size: 1.5rem; margin-bottom: .5rem; color: #f8fafc; }
    .subtitle { color: #94a3b8; margin-bottom: 1.5rem; }
    .status { background: #172033; border-radius: 8px; padding: 1rem 1.25rem;
              margin-bottom: 1.5rem; border-left: 4px solid %(accent)s; }
    .status h2 { font-size: .875rem; text-transform: uppercase; letter-spacing: .05em;
                 color: %(accent)s; margin-bottom: .5rem; }
    .status p { color: #cbd5e1; font-size: .875rem; line-height: 1.6; }
    code { background: #0f172a; padding: .15em .4em; border-radius: 4px;
           font-size: .8125rem; color: #7dd3fc; }
    .api-ok { color: #4ade80; font-weight: 600; }
    a { color: #7dd3fc; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="card">
    <h1>UiPath Developer Server</h1>
    <p class="subtitle">The API is running. %(message)s</p>
    <div class="status">
      <h2>%(status_title)s</h2>
      <p>%(status_body)s</p>
    </div>
    <p style="font-size:.875rem;color:#94a3b8;">
      API docs: <a href="/docs">/docs</a> &nbsp;|&nbsp;
      Entrypoints: <a href="/api/entrypoints">/api/entrypoints</a>
    </p>
  </div>
</body>
</html>
"""


def _fallback_html() -> str:
    """Return an informative HTML page when the frontend is not available."""
    if not FRONTEND_DIR.exists():
        return _FALLBACK_HTML % dict(
            accent="#f59e0b",
            message="The frontend is not included in this installation.",
            status_title="No Frontend Source",
            status_body=(
                "The frontend source directory was not found. "
                "If you installed from PyPI, the pre-built static files should "
                "be included. Try reinstalling with "
                "<code>pip install uipath-dev</code>."
            ),
        )

    return _FALLBACK_HTML % dict(
        accent="#ef4444",
        message="The frontend has not been built yet.",
        status_title="Build Required",
        status_body=(
            "Run the following commands to build the frontend:<br><br>"
            "<code>cd src/uipath/dev/server/frontend</code><br>"
            "<code>npm install</code><br>"
            "<code>npm run build</code><br><br>"
            "Then restart the server. Check the server logs for build errors."
        ),
    )


def create_app(server: UiPathDeveloperServer) -> FastAPI:
    """Create a FastAPI application wired to the given server instance."""
    app = FastAPI(
        title="UiPath Developer Server",
        description="Web API and WebSocket backend for the UiPath Developer Console",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store server reference on app state for route access
    app.state.server = server

    auth_enabled = os.environ.get("UIPATH_AUTH_ENABLED", "true").lower() not in (
        "false",
        "0",
        "no",
    )

    # Read user's pyproject.toml from CWD (once at startup)
    _user_project: dict[str, str | None] = {
        "project_name": None,
        "project_version": None,
        "project_authors": None,
    }
    _pyproject_path = Path.cwd() / "pyproject.toml"
    if _pyproject_path.is_file():
        try:
            import tomllib

            with open(_pyproject_path, "rb") as f:
                _pydata = tomllib.load(f)
            _proj = _pydata.get("project", {})
            _user_project["project_name"] = _proj.get("name")
            _user_project["project_version"] = _proj.get("version")
            _authors = _proj.get("authors")
            if _authors and isinstance(_authors, list) and len(_authors) > 0:
                _user_project["project_authors"] = (
                    _authors[0].get("name")
                    if isinstance(_authors[0], dict)
                    else str(_authors[0])
                )
        except Exception:
            pass

    # Config endpoint — tells the frontend which features are available
    @app.get("/api/config", include_in_schema=False)
    async def _config():
        return {"auth_enabled": auth_enabled, **_user_project}

    # Register routes
    from uipath.dev.server.routes.agent import router as agent_router
    from uipath.dev.server.routes.entrypoints import router as entrypoints_router
    from uipath.dev.server.routes.evals import router as evals_router
    from uipath.dev.server.routes.evaluators import router as evaluators_router
    from uipath.dev.server.routes.files import router as files_router
    from uipath.dev.server.routes.graph import router as graph_router
    from uipath.dev.server.routes.reload import router as reload_router
    from uipath.dev.server.routes.runs import router as runs_router
    from uipath.dev.server.ws.handler import router as ws_router

    if auth_enabled:
        from uipath.dev.server.auth import get_auth_state, restore_session
        from uipath.dev.server.routes.auth import router as auth_router

        app.include_router(auth_router, prefix="/api")
        restore_session()

        # Reload the runtime factory when authentication completes so the
        # newly-written credentials are picked up by subsequent runs.
        def _on_authenticated() -> None:
            async def _safe_reload() -> None:
                # Wait for active runs to finish before reloading
                while any(
                    r.status in ("pending", "running")
                    for r in server.run_service.runs.values()
                ):
                    await asyncio.sleep(1)
                await server.reload_factory()

            def _on_reload_done(t: asyncio.Task[None]) -> None:
                try:
                    t.result()
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception("Factory reload after login failed")

            task = asyncio.create_task(_safe_reload())
            task.add_done_callback(_on_reload_done)

        get_auth_state()._on_authenticated = _on_authenticated

    app.include_router(entrypoints_router, prefix="/api")
    app.include_router(runs_router, prefix="/api")
    app.include_router(graph_router, prefix="/api")
    app.include_router(reload_router, prefix="/api")
    app.include_router(evaluators_router, prefix="/api")
    app.include_router(evals_router, prefix="/api")
    app.include_router(agent_router, prefix="/api")
    app.include_router(files_router, prefix="/api")

    from uipath.dev.server.routes.statedb import router as statedb_router

    app.include_router(statedb_router, prefix="/api")
    app.include_router(ws_router)

    # Auto-build frontend if source is available and build is stale
    from uipath.dev.server.frontend_build import ensure_frontend_built

    frontend_ready = ensure_frontend_built()

    # Serve static frontend files if built, otherwise serve fallback page
    if frontend_ready and (STATIC_DIR / "index.html").exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    else:
        fallback = _fallback_html()

        @app.get("/", response_class=HTMLResponse)
        async def _fallback_page():
            return fallback

    return app
