"""Panel for creating new runs with entrypoint selection and JSON input."""

import json
from typing import Any, Tuple, cast

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Select, TabbedContent, TabPane, TextArea
from uipath.runtime import UiPathRuntimeFactoryProtocol, UiPathRuntimeProtocol

from uipath.dev.ui.widgets.json_input import JsonInput


def mock_json_from_schema(schema: dict[str, Any]) -> Any:
    """Generate a mock JSON value based on a given JSON schema.

    - For object schemas: returns a dict of mocked properties.
    - For arrays: returns a list with one mocked item.
    - For primitives: returns a sensible example / default / enum[0].
    """

    def _mock_value(sub_schema: dict[str, Any], required: bool = True) -> Any:
        # 1) Default wins
        if "default" in sub_schema:
            return sub_schema["default"]

        t = sub_schema.get("type")

        # 2) Enums: pick the first option
        enum = sub_schema.get("enum")
        if enum and isinstance(enum, list):
            return enum[0]

        # 3) Objects: recurse into mock_json_from_schema
        if t == "object":
            if "properties" not in sub_schema:
                return {}
            return mock_json_from_schema(sub_schema)

        # 4) Arrays: mock a single item based on "items" schema
        if t == "array":
            item_schema = sub_schema.get("items", {})
            # If items is not a dict, just return empty list
            if not isinstance(item_schema, dict):
                return []
            return [_mock_value(item_schema, required=True)]

        # 5) Primitives
        if t == "string":
            # If there's a format, we could specialize later (email, date, etc.)
            return "example" if required else ""

        if t == "integer":
            return 0

        if t == "number":
            return 0.0

        if t == "boolean":
            return True if required else False

        # 6) Fallback
        return None

    # Top-level: if it's an object with properties, build a dict
    if schema.get("type") == "object":
        if "properties" not in schema:
            return {}

        props: dict[str, Any] = schema.get("properties", {})
        required_keys = set(schema.get("required", []))
        result: dict[str, Any] = {}

        for key, prop_schema in props.items():
            if not isinstance(prop_schema, dict):
                continue
            is_required = key in required_keys
            result[key] = _mock_value(prop_schema, required=is_required)

        return result

    # If it's not an object schema, just mock the value directly
    return _mock_value(schema, required=True)


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

        self.conversational: bool = False
        self.initial_input: str = "{}"

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        with TabbedContent():
            with TabPane("New run", id="new-tab"):
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
                            "⏯ Debug",
                            id="debug-btn",
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

        json_input = self.query_one("#json-input", TextArea)
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
        select.value = self.selected_entrypoint

        # Lazily fetch schema and populate input
        await self._load_schema_and_update_input(self.selected_entrypoint)

    async def _load_schema_and_update_input(self, entrypoint: str) -> None:
        """Ensure schema for entrypoint is loaded, then update JSON input."""
        json_input = self.query_one("#json-input", TextArea)

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
            except Exception:
                schema = {}
                self.entrypoint_schemas[entrypoint] = schema
            finally:
                if runtime is not None:
                    await runtime.dispose()

        json_input.text = json.dumps(
            mock_json_from_schema(schema),
            indent=2,
        )

    async def on_select_changed(self, event: Select.Changed) -> None:
        """Update JSON input when user selects an entrypoint."""
        self.selected_entrypoint = cast(str, event.value) if event.value else ""

        await self._load_schema_and_update_input(self.selected_entrypoint)

    def get_input_values(self) -> Tuple[str, str, bool]:
        """Get the selected entrypoint and JSON input values."""
        json_input = self.query_one("#json-input", TextArea)
        return self.selected_entrypoint, json_input.text.strip(), self.conversational

    def reset_form(self) -> None:
        """Reset selection and JSON input to defaults."""
        select = self.query_one("#entrypoint-select", Select)
        json_input = self.query_one("#json-input", TextArea)

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
