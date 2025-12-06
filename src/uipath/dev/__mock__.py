"""Run the UiPath Developer Console with a mock runtime factory."""

import sys
from pathlib import Path

from uipath.core.tracing import UiPathTraceManager

from uipath.dev import UiPathDeveloperConsole

# Add demo to path for local development
demo_path = Path(__file__).parent.parent.parent.parent / "demo"
if demo_path.exists():
    sys.path.insert(0, str(demo_path.parent))


def main():
    """Run the developer console with the mock runtime factory."""
    try:
        # Import from demo (only works locally, not in published package)
        from demo.mock_factory import MockRuntimeFactory

        trace_manager = UiPathTraceManager()
        factory = MockRuntimeFactory()
        app = UiPathDeveloperConsole(
            runtime_factory=factory, trace_manager=trace_manager
        )
        app.run()
    except ImportError:
        print("Demo not available in installed package")


if __name__ == "__main__":
    main()
