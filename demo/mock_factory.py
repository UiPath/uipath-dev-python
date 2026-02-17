"""Minimal demo script to run UiPathDevTerminal with mock runtimes."""

import logging
from pathlib import Path

from uipath.runtime import (
    UiPathRuntimeFactorySettings,
    UiPathRuntimeProtocol,
    UiPathRuntimeStorageProtocol,
)

from demo.mock_invoice_runtime import (
    ENTRYPOINT_INVOICE,
    MockInvoiceRuntime,
)
from demo.mock_movies_runtime import (
    ENTRYPOINT_MOVIES,
    MockMoviesRuntime,
)
from demo.mock_pharma_runtime import (
    ENTRYPOINT_PHARMA,
    MockPharmaRuntime,
)
from demo.mock_support_runtime import (
    ENTRYPOINT_SUPPORT_CHAT,
    MockSupportChatRuntime,
)
from demo.mock_telemetry_runtime import (
    ENTRYPOINT_TELEMETRY,
    MockTelemetryRuntime,
)
from demo.mock_template_runtime import (
    create_template_runtime,
)

logger = logging.getLogger(__name__)

# Template mappings: entrypoint -> (events_file, schema_file)
TEMPLATE_RUNTIMES: dict[str, tuple[str, str]] = {}


class MockRuntimeFactory:
    """Runtime factory compatible with UiPathRuntimeFactoryProtocol."""

    def __init__(self):
        """Initialize the mock runtime factory."""
        self.demo_dir = Path(__file__).parent

    async def new_runtime(
        self, entrypoint: str, runtime_id: str, **kwargs
    ) -> UiPathRuntimeProtocol:
        """Create a new runtime instance for the given entrypoint."""
        if entrypoint == ENTRYPOINT_PHARMA:
            return MockPharmaRuntime(entrypoint=entrypoint)
        if entrypoint == ENTRYPOINT_INVOICE:
            return MockInvoiceRuntime(entrypoint=entrypoint)
        if entrypoint == ENTRYPOINT_SUPPORT_CHAT:
            return MockSupportChatRuntime(entrypoint=entrypoint)
        if entrypoint == ENTRYPOINT_TELEMETRY:
            return MockTelemetryRuntime(entrypoint=entrypoint)
        if entrypoint == ENTRYPOINT_MOVIES:
            return MockMoviesRuntime(entrypoint=entrypoint)

        if entrypoint in TEMPLATE_RUNTIMES:
            events_file, schema_file = TEMPLATE_RUNTIMES[entrypoint]

            events_path = self.demo_dir / events_file
            schema_path = self.demo_dir / schema_file

            return create_template_runtime(
                events_json=events_path,
                schema_json=schema_path,
            )

        # Fallback: still return something so the demo doesn't explode
        logger.warning(
            "Unknown entrypoint %r, falling back to PharmaRuntime", entrypoint
        )
        return MockPharmaRuntime(entrypoint=entrypoint)

    async def get_settings(self) -> UiPathRuntimeFactorySettings | None:
        """Return factory settings (no-op for mock)."""
        return UiPathRuntimeFactorySettings()

    async def get_storage(self) -> UiPathRuntimeStorageProtocol | None:
        """Return factory storage (no-op for mock)."""
        return None

    def discover_entrypoints(self) -> list[str]:
        """Return all available entrypoints."""
        return [
            ENTRYPOINT_TELEMETRY,
            ENTRYPOINT_PHARMA,
            ENTRYPOINT_INVOICE,
            ENTRYPOINT_SUPPORT_CHAT,
            ENTRYPOINT_MOVIES,
            *TEMPLATE_RUNTIMES.keys(),
        ]

    async def dispose(self) -> None:
        """Dispose of any resources (no-op for mock)."""
        pass
