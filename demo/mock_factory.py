"""Minimal demo script to run UiPathDevTerminal with mock runtimes."""

import logging
from pathlib import Path

from uipath.runtime import (
    UiPathRuntimeProtocol,
)

from demo.mock_greeting_runtime import (
    ENTRYPOINT_GREETING,
    MockGreetingRuntime,
)
from demo.mock_numbers_runtime import (
    ENTRYPOINT_ANALYZE_NUMBERS,
    MockNumberAnalyticsRuntime,
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
TEMPLATE_RUNTIMES = {
    "chat/movies.py:graph": (
        "chat_agent/events.json",
        "chat_agent/entry-points.json",
    ),
}


class MockRuntimeFactory:
    """Runtime factory compatible with UiPathRuntimeFactoryProtocol."""

    def __init__(self):
        """Initialize the mock runtime factory."""
        self.demo_dir = Path(__file__).parent

    async def new_runtime(
        self, entrypoint: str, runtime_id: str
    ) -> UiPathRuntimeProtocol:
        """Create a new runtime instance for the given entrypoint."""
        if entrypoint == ENTRYPOINT_GREETING:
            return MockGreetingRuntime(entrypoint=entrypoint)
        if entrypoint == ENTRYPOINT_ANALYZE_NUMBERS:
            return MockNumberAnalyticsRuntime(entrypoint=entrypoint)
        if entrypoint == ENTRYPOINT_SUPPORT_CHAT:
            return MockSupportChatRuntime(entrypoint=entrypoint)
        if entrypoint == ENTRYPOINT_TELEMETRY:
            return MockTelemetryRuntime(entrypoint=entrypoint)

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
            "Unknown entrypoint %r, falling back to GreetingRuntime", entrypoint
        )
        return MockGreetingRuntime(entrypoint=entrypoint)

    async def discover_runtimes(self) -> list[UiPathRuntimeProtocol]:
        """Return prototype instances for discovery (not really used by the UI)."""
        runtimes: list[UiPathRuntimeProtocol] = [
            MockGreetingRuntime(entrypoint=ENTRYPOINT_GREETING),
            MockNumberAnalyticsRuntime(entrypoint=ENTRYPOINT_ANALYZE_NUMBERS),
            MockSupportChatRuntime(entrypoint=ENTRYPOINT_SUPPORT_CHAT),
            MockTelemetryRuntime(entrypoint=ENTRYPOINT_TELEMETRY),
        ]

        for entrypoint in TEMPLATE_RUNTIMES.keys():
            try:
                runtime: UiPathRuntimeProtocol = await self.new_runtime(
                    entrypoint, runtime_id="discovery"
                )
                runtimes.append(runtime)
            except Exception as e:
                logger.error(f"Failed to load template runtime '{entrypoint}': {e}")

        return runtimes

    def discover_entrypoints(self) -> list[str]:
        """Return all available entrypoints."""
        return [
            ENTRYPOINT_TELEMETRY,
            ENTRYPOINT_GREETING,
            ENTRYPOINT_ANALYZE_NUMBERS,
            ENTRYPOINT_SUPPORT_CHAT,
            *TEMPLATE_RUNTIMES.keys(),
        ]

    async def dispose(self) -> None:
        """Dispose of any resources (no-op for mock)."""
        pass
