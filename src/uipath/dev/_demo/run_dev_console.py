from uipath.core.tracing import UiPathTraceManager

from uipath.dev import UiPathDeveloperConsole
from uipath.dev._demo.mock_runtime import MockRuntimeFactory


def main():
    trace_manager = UiPathTraceManager()
    factory = MockRuntimeFactory()
    app = UiPathDeveloperConsole(runtime_factory=factory, trace_manager=trace_manager)
    app.run()


if __name__ == "__main__":
    main()
