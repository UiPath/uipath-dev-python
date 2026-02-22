"""FastAPI application factory."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

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

    # Favicon — UiPath orange branded icon
    _favicon_svg = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="6" fill="#FA4616"/>'
        '<text x="16" y="24" font-size="22" text-anchor="middle" fill="#FFFFFF" '
        'font-family="system-ui, -apple-system, sans-serif" font-weight="700">U</text>'
        "</svg>"
    )
    _favicon_bytes = _favicon_svg.encode("utf-8")

    @app.get("/favicon.ico", include_in_schema=False)
    async def _favicon_ico():
        return Response(content=_favicon_bytes, media_type="image/svg+xml")

    @app.get("/favicon.svg", include_in_schema=False)
    async def _favicon_svg_route():
        return Response(content=_favicon_bytes, media_type="image/svg+xml")

    # Store server reference on app state for route access
    app.state.server = server

    auth_enabled = os.environ.get("UIPATH_AUTH_ENABLED", "true").lower() not in (
        "false",
        "0",
        "no",
    )

    # Config endpoint — tells the frontend which features are available
    @app.get("/api/config", include_in_schema=False)
    async def _config():
        return {"auth_enabled": auth_enabled}

    # Register routes
    from uipath.dev.server.routes.entrypoints import router as entrypoints_router
    from uipath.dev.server.routes.graph import router as graph_router
    from uipath.dev.server.routes.reload import router as reload_router
    from uipath.dev.server.routes.runs import router as runs_router
    from uipath.dev.server.ws.handler import router as ws_router

    if auth_enabled:
        from uipath.dev.server.auth import restore_session
        from uipath.dev.server.routes.auth import router as auth_router

        app.include_router(auth_router, prefix="/api")
        restore_session()

    app.include_router(entrypoints_router, prefix="/api")
    app.include_router(runs_router, prefix="/api")
    app.include_router(graph_router, prefix="/api")
    app.include_router(reload_router, prefix="/api")
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
