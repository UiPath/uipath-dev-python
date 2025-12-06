"""Mock runtime that replays events from a JSON file."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, cast

from opentelemetry import trace
from uipath.core.chat import UiPathConversationMessageEvent
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeEvent,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathStreamOptions,
)
from uipath.runtime.events import (
    UiPathRuntimeMessageEvent,
    UiPathRuntimeStateEvent,
)
from uipath.runtime.schema import (
    UiPathRuntimeEdge,
    UiPathRuntimeGraph,
    UiPathRuntimeNode,
    UiPathRuntimeSchema,
)

logger = logging.getLogger(__name__)


class MockTemplateRuntime:
    """Mock runtime that replays events from a JSON file."""

    def __init__(
        self,
        events_file: str | Path,
        schema_file: str | Path,
    ) -> None:
        """Initialize the MockTemplateRuntime."""
        self.events_file = Path(events_file)
        self.schema_file = Path(schema_file)
        self.tracer = trace.get_tracer("uipath.dev.mock.template")
        self._events: list[dict[str, Any]] = []
        self._schema_data: dict[str, Any] | None = None
        self._load_events()
        self._load_schema()

    def _load_events(self) -> None:
        """Load events from JSON file."""
        with open(self.events_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            self._events = data
        else:
            raise ValueError("Expected JSON array of events")

    def _load_schema(self) -> None:
        """Load schema from separate JSON file if provided."""
        with open(self.schema_file, "r", encoding="utf-8") as f:
            self._schema_data = json.load(f)

    async def get_schema(self) -> UiPathRuntimeSchema:
        """Get runtime schema from the loaded data or build default."""
        assert self._schema_data is not None
        entry_points = self._schema_data.get("entryPoints", [])
        assert entry_points is not None and len(entry_points) > 0
        ep = entry_points[0]

        # Build graph if present
        graph = None
        if "graph" in ep and ep["graph"]:
            graph_data = ep["graph"]
            nodes = [UiPathRuntimeNode(**node) for node in graph_data.get("nodes", [])]
            edges = [UiPathRuntimeEdge(**edge) for edge in graph_data.get("edges", [])]
            graph = UiPathRuntimeGraph(nodes=nodes, edges=edges)

        return UiPathRuntimeSchema(
            filePath=ep["filePath"],
            uniqueId=ep["uniqueId"],
            type=ep["type"],
            input=ep["input"],
            output=ep["output"],
            graph=graph,
        )

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        """Execute by replaying all events and returning final result."""
        logger.info("MockTemplateRuntime: starting execution")

        # Stream all events and capture the final result
        final_result = None
        async for event in self.stream(
            input=input, options=cast(UiPathStreamOptions, options)
        ):
            if isinstance(event, UiPathRuntimeResult):
                final_result = event

        return final_result or UiPathRuntimeResult(
            output={},
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        """Stream events from the JSON file."""
        logger.info(f"MockTemplateRuntime: streaming {len(self._events)} events")

        with self.tracer.start_as_current_span(
            "template.stream",
            attributes={
                "uipath.runtime.name": "MockTemplateRuntime",
                "uipath.event.count": len(self._events),
            },
        ):
            for i, event_data in enumerate(self._events):
                event_type = event_data.get("event_type")

                # Add small delay between events for realistic streaming
                if i > 0:
                    await asyncio.sleep(0.01)

                try:
                    if event_type == "runtime_message":
                        payload_data = event_data.get("payload", {})

                        conversation_event = (
                            UiPathConversationMessageEvent.model_validate(payload_data)
                        )

                        yield UiPathRuntimeMessageEvent(
                            payload=conversation_event,
                            execution_id=event_data.get("execution_id"),
                            metadata=event_data.get("metadata"),
                        )

                    elif event_type == "runtime_state":
                        yield UiPathRuntimeStateEvent(
                            payload=event_data.get("payload", {}),
                            node_name=event_data.get("node_name"),
                            execution_id=event_data.get("execution_id"),
                            metadata=event_data.get("metadata"),
                        )

                    elif event_type == "runtime_result":
                        yield UiPathRuntimeResult(
                            output=event_data.get("output"),
                            status=UiPathRuntimeStatus(
                                event_data.get("status", "successful")
                            ),
                            execution_id=event_data.get("execution_id"),
                            metadata=event_data.get("metadata"),
                        )

                    else:
                        logger.warning(f"Unknown event type: {event_type}")

                except Exception as e:
                    logger.error(f"Error processing event {i}: {e}", exc_info=True)
                    continue

        logger.info("MockTemplateRuntime: streaming completed")

    async def dispose(self) -> None:
        """Cleanup resources."""
        logger.info("MockTemplateRuntime: dispose() invoked")


def create_template_runtime(
    events_json: str | Path,
    schema_json: str | Path,
) -> MockTemplateRuntime:
    """Create a template runtime from JSON files.

    Args:
        events_json: Path to JSON file containing events array
        schema_json: Path to entry-points.json schema file

    Returns:
        MockTemplateRuntime instance
    """
    return MockTemplateRuntime(
        events_file=events_json,
        schema_file=schema_json,
    )
