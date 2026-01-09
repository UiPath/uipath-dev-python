"""Panel for creating new runs with entrypoint selection and JSON input."""

import json
from typing import Any, Tuple, cast

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Select
from uipath.runtime import UiPathRuntimeFactoryProtocol, UiPathRuntimeProtocol

from uipath.dev.ui.panels._json_schema import mock_json_from_schema
from uipath.dev.ui.widgets.json_input import JsonInput


class NewRunPanel(Container):
    """Panel for creating new runs with a Select entrypoint selector."""

    selected_entrypoint = reactive("")

    def __init__(
        self,
        runtime_factory: UiPathRuntimeFactoryProtocol,
        **kwargs: Any,
    ) -> None:
        """Initialize NewRunPanel using UiPathRuntimeFactoryProtocol."""
        super().__init__(**kwargs)

        self._runtime_factory = runtime_factory

        self.entrypoints: list[str] = []

        self.entrypoint_schemas: dict[str, dict[str, Any]] = {}

        self.initial_input: str = "{}"

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        with Vertical():
            yield Select(
                options=[],
                id="entrypoint-select",
                allow_blank=True,
            )

            yield JsonInput(
                text=self.initial_input,
                language="json",
                id="json-input",
                classes="input-field json-input",
            )

            with Horizontal(classes="run-actions"):
                yield Button(
                    "▶ Run",
                    id="execute-btn",
                    variant="primary",
                    classes="action-btn",
                )
                yield Button(
                    "⏸ Debug",
                    id="debug-btn",
                    variant="primary",
                    classes="action-btn",
                )
                yield Button(
                    "💬 Chat",
                    id="chat-btn",
                    variant="primary",
                    classes="action-btn",
                )


    async def on_mount(self) -> None:
        """Discover entrypoints once, and set the first as default."""
        try:
            discovered = self._runtime_factory.discover_entrypoints()
        except Exception:
            discovered = []

        self.entrypoints = discovered or []

        select = self.query_one("#entrypoint-select", Select)

        json_input = self.query_one("#json-input", JsonInput)
        run_button = self.query_one("#execute-btn", Button)

        if not self.entrypoints:
            self.selected_entrypoint = ""
            select.set_options([("No entrypoints found", "no-entrypoints")])
            select.value = "no-entrypoints"
            select.disabled = True
            run_button.disabled = True
            json_input.text = "{}"
            return

        options = [(ep, ep) for ep in self.entrypoints]
        select.set_options(options)

        # Use the first entrypoint as default
        self.selected_entrypoint = self.entrypoints[0]

        # Lazily fetch schema and populate input BEFORE setting select.value
        # to avoid triggering on_select_changed
        await self._load_schema_and_update_input(self.selected_entrypoint)

        # Set the select value after loading the schema
        select.value = self.selected_entrypoint

    async def _load_schema_and_update_input(self, entrypoint: str) -> None:
        """Ensure schema for entrypoint is loaded, then update JSON input."""
        json_input = self.query_one("#json-input", JsonInput)

        if not entrypoint or entrypoint == "no-entrypoints":
            json_input.text = "{}"
            return

        schema = self.entrypoint_schemas.get(entrypoint)

        if schema is None:
            runtime: UiPathRuntimeProtocol | None = None
            try:
                runtime = await self._runtime_factory.new_runtime(
                    entrypoint, runtime_id="default"
                )
                schema_obj = await runtime.get_schema()

                input_schema = schema_obj.input or {}
                self.entrypoint_schemas[entrypoint] = input_schema
                schema = input_schema
            except Exception as e:
                json_input.text = "{}"
                self.app.notify(
                    f"Error loading schema for '{entrypoint}': {str(e)}",
                    severity="error",
                    timeout=5,
                )
                return
            finally:
                if runtime is not None:
                    await runtime.dispose()

        # Generate mock JSON from schema
        mock_data = mock_json_from_schema(schema)
        json_input.text = json.dumps(mock_data, indent=2)

    async def on_select_changed(self, event: Select.Changed) -> None:
        """Update JSON input when user selects an entrypoint."""
        if event.select.id != "entrypoint-select":
            return

        new_entrypoint = cast(str, event.value) if event.value else ""

        # Only load schema if the entrypoint actually changed
        if new_entrypoint != self.selected_entrypoint:
            self.selected_entrypoint = new_entrypoint
            await self._load_schema_and_update_input(self.selected_entrypoint)

    def get_input_values(self) -> Tuple[str, str]:
        """Get the selected entrypoint and JSON input values."""
        json_input = self.query_one("#json-input", JsonInput)
        return self.selected_entrypoint, json_input.text.strip()

    def reset_form(self) -> None:
        """Reset selection and JSON input to defaults."""
        select = self.query_one("#entrypoint-select", Select)
        json_input = self.query_one("#json-input", JsonInput)

        if not self.entrypoints:
            self.selected_entrypoint = ""
            select.clear()
            json_input.text = "{}"
            return

        self.selected_entrypoint = self.entrypoints[0]
        select.value = self.selected_entrypoint

        schema = self.entrypoint_schemas.get(self.selected_entrypoint)
        if schema is None:
            json_input.text = "{}"
        else:
            json_input.text = json.dumps(
                mock_json_from_schema(schema),
                indent=2,
            )
