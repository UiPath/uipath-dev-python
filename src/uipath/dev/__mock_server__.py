"""Run the UiPath Developer Server with a mock runtime factory."""

import logging
import sys
from pathlib import Path

from uipath.core.tracing import UiPathTraceManager

# Add demo to path for local development
demo_path = Path(__file__).parent.parent.parent.parent / "demo"
if demo_path.exists():
    sys.path.insert(0, str(demo_path.parent))


def main():
    """Run the developer server with the mock runtime factory."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-8s %(name)s: %(message)s",
    )

    try:
        # Import from demo (only works locally, not in published package)
        from demo.mock_factory import MockRuntimeFactory
        from uipath.dev.server import UiPathDeveloperServer

        trace_manager = UiPathTraceManager()
        factory = MockRuntimeFactory()
        server = UiPathDeveloperServer(
            runtime_factory=factory, trace_manager=trace_manager
        )
        server.run()
    except ImportError as e:
        print(f"Required dependencies not available: {e}")
        print("Install server dependencies: pip install uipath-dev")


if __name__ == "__main__":
    main()
