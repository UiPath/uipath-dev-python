"""UiPath Developer Server."""

import asyncio
from pathlib import Path
from uuid import uuid4

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import UiPathRuntimeFactoryProtocol

from uipath.dev.models import ExecutionMode, ExecutionRun
from uipath.dev.services.run_service import RunService


class ExecuteRequest(BaseModel):
    entrypoint: str
    input_data: dict = {}


class UiPathDeveloperServer:
    """UiPath Developer Server."""

    def __init__(
        self,
        runtime_factory: UiPathRuntimeFactoryProtocol,
        trace_manager: UiPathTraceManager,
        host: str = "0.0.0.0",
        port: int = 2358,
    ):
        self.app = FastAPI(title="UiPath Developer Server")
        self.host = host
        self.port = port

        self.run_service = RunService(
            runtime_factory=runtime_factory,
            trace_manager=trace_manager,
        )

        self._setup_routes()

    async def home(self) -> HTMLResponse:
        """Web UI for testing the API."""
        html_path = Path(__file__).parent / "web" / "index.html"
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    async def start_run(self, request: ExecuteRequest):
        """Start a new execution run."""
        run = ExecutionRun(
            entrypoint=request.entrypoint,
            input_data=request.input_data,
            mode=ExecutionMode.RUN,
        )

        self.run_service.register_run(run)
        asyncio.create_task(self.run_service.execute(run))

        return {"run_id": run.id, "status": run.status}

    def _setup_routes(self):
        self.app.add_api_route(
            "/", self.home, methods=["GET"], response_class=HTMLResponse
        )
        self.app.add_api_route("/runs", self.start_run, methods=["POST"])

    async def run_async(self):
        """Start the FastAPI server."""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()
