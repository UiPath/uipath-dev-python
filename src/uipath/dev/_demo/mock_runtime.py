"""Minimal demo script to run UiPathDevTerminal with mock runtimes."""

import logging

from uipath.runtime import (
    UiPathRuntimeProtocol,
)

from uipath.dev._demo.mock_context_runtime import ENTRYPOINT_CONTEXT, MockContextRuntime
from uipath.dev._demo.mock_greeting_runtime import (
    ENTRYPOINT_GREETING,
    MockGreetingRuntime,
)
from uipath.dev._demo.mock_numbers_runtime import (
    ENTRYPOINT_ANALYZE_NUMBERS,
    MockNumberAnalyticsRuntime,
)
from uipath.dev._demo.mock_support_runtime import (
    ENTRYPOINT_SUPPORT_CHAT,
    MockSupportChatRuntime,
)

logger = logging.getLogger(__name__)


class MockRuntimeFactory:
    """Runtime factory compatible with UiPathRuntimeFactoryProtocol."""

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
        if entrypoint == ENTRYPOINT_CONTEXT:
            return MockContextRuntime(entrypoint=entrypoint)

        # Fallback: still return something so the demo doesn't explode
        logger.warning(
            "Unknown entrypoint %r, falling back to GreetingRuntime", entrypoint
        )
        return MockGreetingRuntime(entrypoint=entrypoint)

    def discover_runtimes(self) -> list[UiPathRuntimeProtocol]:
        """Return prototype instances for discovery (not really used by the UI)."""
        return [
            MockGreetingRuntime(entrypoint=ENTRYPOINT_GREETING),
            MockNumberAnalyticsRuntime(entrypoint=ENTRYPOINT_ANALYZE_NUMBERS),
            MockSupportChatRuntime(entrypoint=ENTRYPOINT_SUPPORT_CHAT),
            MockContextRuntime(entrypoint=ENTRYPOINT_CONTEXT),
        ]

    def discover_entrypoints(self) -> list[str]:
        """Return all available entrypoints."""
        return [
            ENTRYPOINT_CONTEXT,
            ENTRYPOINT_GREETING,
            ENTRYPOINT_ANALYZE_NUMBERS,
            ENTRYPOINT_SUPPORT_CHAT,
        ]
