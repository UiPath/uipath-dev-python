"""Run the UiPath Developer Server with a mock runtime factory."""

import asyncio
import sys
from pathlib import Path

from uipath.core.tracing import UiPathTraceManager

from uipath.dev import UiPathDeveloperServer

# Add demo to path for local development
demo_path = Path(__file__).parent.parent.parent.parent / "demo"
if demo_path.exists():
    sys.path.insert(0, str(demo_path.parent))


async def main_async():
    """Run the API server with the mock runtime factory."""
    try:
        # Import from demo (only works locally, not in published package)
        from demo.mock_factory import MockRuntimeFactory

        trace_manager = UiPathTraceManager()
        factory = MockRuntimeFactory()

        try:
            app = UiPathDeveloperServer(
                runtime_factory=factory,
                trace_manager=trace_manager,
                host="localhost",
                port=2358,
            )
            print("Starting UiPath Developer Server on http://localhost:2358")
            await app.run_async()

        finally:
            await factory.dispose()

    except ImportError:
        print("Demo not available in installed package")


def main():
    """Entry point for the API server."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
