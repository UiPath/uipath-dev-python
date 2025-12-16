"""Panel for creating and editing evaluators."""

import json
from typing import Any, Callable

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    ListItem,
    ListView,
    Static,
    TextArea,
)

from uipath.dev.models.evaluator_types import EVALUATOR_TYPES


class EvaluatorFormPanel(Vertical):
    """Panel for evaluator creation and editing."""

    def __init__(
        self,
        on_save: Callable[[dict[str, Any]], None] | None = None,
        on_delete: Callable[[str], None] | None = None,
        on_close: Callable[[], None] | None = None,
        **kwargs,
    ):
        """Initialize the evaluator form panel.

        Args:
            on_save: Callback with form data when save/create is clicked.
            on_delete: Callback with evaluator_id when delete is clicked.
            on_close: Callback when close/cancel is clicked.
        """
        super().__init__(**kwargs)
        self.on_save = on_save
        self.on_delete = on_delete
        self.on_close = on_close

        # Current state
        self._mode: str = "templates"  # templates, create, edit
        self._selected_type_id: str = ""
        self._selected_type_def: dict[str, Any] = {}
        self._editing_evaluator_id: str = ""
        self._editing_evaluator_data: dict[str, Any] = {}
        self._external_container: ScrollableContainer | None = None

    def compose(self) -> ComposeResult:
        """Compose the panel UI."""
        yield ScrollableContainer(id="evaluator-form-content")

    async def on_mount(self) -> None:
        """Show templates list on mount."""
        await self.show_templates()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        btn_id = event.button.id or ""

        if btn_id == "create-evaluator-btn":
            await self._handle_create()
        elif btn_id == "save-edited-evaluator-btn":
            await self._handle_save_edit()
        elif btn_id == "delete-edited-evaluator-btn":
            await self._handle_delete()
        elif btn_id == "close-evaluator-edit-btn":
            if self.on_close:
                self.on_close()
            await self.show_templates()

    async def show_templates(self) -> None:
        """Show the evaluator templates list."""
        self._mode = "templates"
        self._external_container = None  # Clear external container reference
        content = self.query_one("#evaluator-form-content", ScrollableContainer)
        await self._clear_content(content)

        # Header
        await content.mount(
            Static("[bold]Select a Template[/bold]", classes="panel-title")
        )
        await content.mount(
            Static(
                "[dim]Choose an evaluator type to create from[/dim]",
                classes="helper-text",
            )
        )

        # Templates list
        templates_list = ListView(
            id="evaluator-templates-list", classes="eval-items-list"
        )
        await content.mount(templates_list)

        for type_id, type_def in EVALUATOR_TYPES.items():
            type_name = type_def.get("name", type_id)
            category = type_def.get("category", "")

            display = f"{type_name}"
            if category:
                display += f" [{category}]"

            item = ListItem(Static(display), classes="eval-list-item")
            item.type_id = type_id  # type: ignore
            item.type_def = type_def  # type: ignore
            await templates_list.append(item)

    async def show_create_form(self, type_id: str, type_def: dict[str, Any]) -> None:
        """Show the create form for a specific evaluator type in this panel's content."""
        self._mode = "create"
        self._selected_type_id = type_id
        self._selected_type_def = type_def
        self._external_container = None  # Not using external container for this mode

        content = self.query_one("#evaluator-form-content", ScrollableContainer)
        await self._clear_content(content)
        await self._populate_create_form(content, type_id, type_def)
        self.refresh(layout=True)

    async def populate_create_form_in_container(
        self,
        container: ScrollableContainer,
        type_id: str,
        type_def: dict[str, Any],
    ) -> None:
        """Populate the create form into an external container (e.g., right panel).

        This stores the type info for later use by get_create_form_data().
        """
        self._mode = "create"
        self._selected_type_id = type_id
        self._selected_type_def = type_def
        self._external_container = container  # Store reference for form data collection
        await self._populate_create_form(container, type_id, type_def)

    async def _populate_create_form(
        self,
        content: ScrollableContainer,
        type_id: str,
        type_def: dict[str, Any],
    ) -> None:
        """Populate create form widgets into a container."""
        type_name = type_def.get("name", type_id)
        description = type_def.get("description", "")
        config_fields = type_def.get("config_fields", [])
        criteria_fields = type_def.get("criteria_fields", [])

        # Close button
        await content.mount(Button("✕", id="close-right-panel-btn", classes="close-btn"))

        # Header
        await content.mount(
            Static(f"[bold]Create {type_name}[/bold]", classes="panel-title")
        )
        if description:
            await content.mount(
                Static(f"[dim]{description}[/dim]", classes="helper-text")
            )

        # Evaluator ID
        await content.mount(
            Static("[bold]Evaluator ID *[/bold]", classes="detail-row")
        )
        await content.mount(Input(placeholder="my-evaluator", id="new-evaluator-id"))

        # Description
        await content.mount(Static("[bold]Description[/bold]", classes="detail-row"))
        await content.mount(
            Input(
                placeholder="Description of this evaluator", id="new-evaluator-desc"
            )
        )

        # Configuration fields
        if config_fields:
            await content.mount(
                Static("[bold]Configuration[/bold]", classes="section-header")
            )
            await self._mount_config_fields(content, config_fields, prefix="config")

        # Criteria fields
        if criteria_fields:
            await content.mount(
                Static(
                    "[bold]Default Evaluation Criteria[/bold]",
                    classes="section-header",
                )
            )
            await content.mount(
                Static(
                    "[dim]These values will be used as defaults when running evaluations.[/dim]",
                    classes="helper-text",
                )
            )
            await self._mount_criteria_fields(content, criteria_fields, prefix="criteria")

        # Create button
        button_row = Horizontal(classes="button-row")
        await content.mount(button_row)
        await button_row.mount(
            Button(
                "Create Evaluator",
                id="create-evaluator-btn",
                variant="primary",
                classes="small-btn",
            )
        )

    async def show_edit_form(self, evaluator_id: str, ev_data: dict[str, Any]) -> None:
        """Show the edit form for an existing evaluator.

        Args:
            evaluator_id: The evaluator ID.
            ev_data: The evaluator data (loaded by parent).
        """
        self._mode = "edit"
        self._editing_evaluator_id = evaluator_id
        self._editing_evaluator_data = ev_data
        self._external_container = None  # Not using external container for edit mode

        content = self.query_one("#evaluator-form-content", ScrollableContainer)
        await self._clear_content(content)

        # Get type info
        ev_type = ev_data.get("evaluatorTypeId", "")
        type_def = EVALUATOR_TYPES.get(ev_type, {})
        type_name = type_def.get("name", ev_type)
        type_description = type_def.get("description", "")
        config_fields = type_def.get("config_fields", [])
        criteria_fields = type_def.get("criteria_fields", [])

        # Get current values
        ev_config = ev_data.get("evaluatorConfig", ev_data.get("config", {}))
        default_criteria = ev_config.get("defaultEvaluationCriteria", {})

        # Header
        await content.mount(
            Static(f"[bold]Edit {type_name}[/bold]", classes="panel-title")
        )
        if type_description:
            await content.mount(
                Static(f"[dim]{type_description}[/dim]", classes="helper-text")
            )

        # Evaluator ID (read-only)
        await content.mount(
            Static("[bold]Evaluator ID *[/bold]", classes="detail-row")
        )
        await content.mount(Static(f"[dim]{evaluator_id}[/dim]", classes="detail-row"))

        # Description
        description = ev_data.get("description", "")
        await content.mount(Static("[bold]Description[/bold]", classes="detail-row"))
        await content.mount(
            Input(
                value=description,
                placeholder="Description of this evaluator",
                id="edit-evaluator-desc",
            )
        )

        # Configuration fields
        if config_fields:
            await content.mount(
                Static("[bold]Configuration[/bold]", classes="section-header")
            )
            await self._mount_config_fields(
                content, config_fields, prefix="edit-config",
                current_values=ev_config
            )

        # Criteria fields
        if criteria_fields:
            await content.mount(
                Static(
                    "[bold]Default Evaluation Criteria[/bold]",
                    classes="section-header",
                )
            )
            await content.mount(
                Static(
                    "[dim]These values will be used as defaults when running evaluations.[/dim]",
                    classes="helper-text",
                )
            )
            await self._mount_criteria_fields(
                content, criteria_fields, prefix="edit-criteria",
                current_values=default_criteria
            )

        # Buttons
        button_row = Horizontal(classes="button-row")
        await content.mount(button_row)
        await button_row.mount(
            Button("Save", id="save-edited-evaluator-btn", variant="primary", classes="small-btn")
        )
        await button_row.mount(
            Button("Delete", id="delete-edited-evaluator-btn", variant="error", classes="small-btn")
        )
        await button_row.mount(
            Button("Close", id="close-evaluator-edit-btn", variant="default", classes="small-btn")
        )

        self.refresh(layout=True)

    def show_placeholder(self) -> None:
        """Show placeholder text."""
        self._mode = "templates"
        try:
            content = self.query_one("#evaluator-form-content", ScrollableContainer)
            self._clear_content_sync(content)
            content.mount(
                Static(
                    "[dim]Click '+ Add' to create a new evaluator, or select an existing evaluator from the list.[/dim]",
                    classes="helper-text",
                )
            )
        except Exception:
            pass

    def get_selected_type(self) -> tuple[str, dict[str, Any]]:
        """Get the currently selected type ID and definition."""
        return self._selected_type_id, self._selected_type_def

    # =========================================================================
    # Form Data Collection
    # =========================================================================

    def get_create_form_data(self) -> dict[str, Any] | None:
        """Collect data from the create form."""
        try:
            # Query from external container if form is in right panel, otherwise from self
            query_target = self._external_container if self._external_container else self
            evaluator_id = query_target.query_one("#new-evaluator-id", Input).value.strip()
            description = query_target.query_one("#new-evaluator-desc", Input).value.strip()

            if not evaluator_id:
                self.app.notify("Please enter an evaluator ID", severity="error")
                return None

            config = self._collect_config_values("config")
            config["name"] = evaluator_id
            criteria = self._collect_criteria_values("criteria")

            return {
                "evaluator_id": evaluator_id,
                "type_id": self._selected_type_id,
                "description": description,
                "config": config,
                "default_criteria": criteria if criteria else None,
            }
        except Exception as e:
            self.app.notify(f"Error collecting form data: {e}", severity="error")
            return None

    def get_edit_form_data(self) -> dict[str, Any] | None:
        """Collect data from the edit form."""
        try:
            description = self.query_one("#edit-evaluator-desc", Input).value.strip()
            config = self._collect_config_values("edit-config")
            config["name"] = self._editing_evaluator_id
            criteria = self._collect_criteria_values("edit-criteria")

            return {
                "evaluator_id": self._editing_evaluator_id,
                "type_id": self._editing_evaluator_data.get("evaluatorTypeId", ""),
                "description": description,
                "config": config,
                "default_criteria": criteria if criteria else {},
            }
        except Exception as e:
            self.app.notify(f"Error collecting form data: {e}", severity="error")
            return None

    async def _clear_content(self, content: ScrollableContainer) -> None:
        """Clear all children from container."""
        for child in list(content.children):
            child.remove()

    def _clear_content_sync(self, content: ScrollableContainer) -> None:
        """Clear all children from container (sync version)."""
        for child in list(content.children):
            child.remove()

    async def _mount_config_fields(
        self,
        content: ScrollableContainer,
        fields: list[dict[str, Any]],
        prefix: str,
        current_values: dict[str, Any] | None = None,
        fallback_values: dict[str, Any] | None = None,
    ) -> None:
        """Mount configuration fields."""
        current_values = current_values or {}
        fallback_values = fallback_values or {}

        for field in fields:
            field_name = field.get("name", "")
            if field_name == "name":
                continue

            field_label = field.get("label", field_name)
            field_type = field.get("type", "string")
            field_default = field.get("default", "")
            field_desc = field.get("description", "")
            required = field.get("required", False)

            current_value = current_values.get(
                field_name, fallback_values.get(field_name, field_default)
            )

            label_text = f"[bold]{field_label}{'*' if required else ''}[/bold]"
            await content.mount(Static(label_text, classes="detail-row"))
            if field_desc:
                await content.mount(
                    Static(f"[dim]{field_desc}[/dim]", classes="helper-text")
                )

            if field_type == "boolean":
                await content.mount(
                    Checkbox(
                        field_label,
                        value=bool(current_value),
                        id=f"{prefix}-{field_name}",
                    )
                )
            else:
                value_str = (
                    json.dumps(current_value)
                    if isinstance(current_value, (dict, list))
                    else str(current_value or "")
                )
                if "\n" in value_str or field_type in ("text", "textarea"):
                    await content.mount(
                        TextArea(
                            value_str,
                            id=f"{prefix}-{field_name}",
                            classes="detail-json",
                        )
                    )
                else:
                    await content.mount(
                        Input(
                            value=value_str,
                            placeholder=field_label,
                            id=f"{prefix}-{field_name}",
                        )
                    )

    async def _mount_criteria_fields(
        self,
        content: ScrollableContainer,
        fields: list[dict[str, Any]],
        prefix: str,
        current_values: dict[str, Any] | None = None,
        fallback_values: dict[str, Any] | None = None,
    ) -> None:
        """Mount criteria fields."""
        current_values = current_values or {}
        fallback_values = fallback_values or {}

        for field in fields:
            field_name = field.get("name", "")
            field_label = field.get("label", field_name)
            field_type = field.get("type", "string")
            required = field.get("required", False)

            current_value = current_values.get(
                field_name, fallback_values.get(field_name, "")
            )

            label_text = f"[bold]{field_label}{'*' if required else ''}[/bold]"
            await content.mount(Static(label_text, classes="detail-row"))

            if field_type == "boolean":
                await content.mount(
                    Checkbox(
                        field_label,
                        value=bool(current_value),
                        id=f"{prefix}-{field_name}",
                    )
                )
            else:
                value_str = (
                    json.dumps(current_value)
                    if isinstance(current_value, (dict, list))
                    else str(current_value or "")
                )
                await content.mount(
                    Input(
                        value=value_str,
                        placeholder=field_label,
                        id=f"{prefix}-{field_name}",
                    )
                )

    def _collect_config_values(self, prefix: str) -> dict[str, Any]:
        """Collect configuration values from form."""
        config: dict[str, Any] = {}
        type_def = self._selected_type_def if self._mode == "create" else EVALUATOR_TYPES.get(
            self._editing_evaluator_data.get("evaluatorTypeId", ""), {}
        )
        config_fields = type_def.get("config_fields", [])

        # Query from external container if form is in right panel (create mode), otherwise from self
        query_target = self._external_container if (self._mode == "create" and self._external_container) else self

        for field in config_fields:
            field_name = field.get("name", "")
            field_type = field.get("type", "string")
            if field_name == "name":
                continue

            try:
                widget_id = f"#{prefix}-{field_name}"
                if field_type == "boolean":
                    checkbox = query_target.query_one(widget_id, Checkbox)
                    config[field_name] = checkbox.value
                else:
                    try:
                        textarea = query_target.query_one(widget_id, TextArea)
                        value = textarea.text.strip()
                    except Exception:
                        input_widget = query_target.query_one(widget_id, Input)
                        value = input_widget.value.strip()
                    if value:
                        if value.startswith("{") or value.startswith("["):
                            try:
                                config[field_name] = json.loads(value)
                            except json.JSONDecodeError:
                                config[field_name] = value
                        else:
                            config[field_name] = value
            except Exception:
                pass

        return config

    def _collect_criteria_values(self, prefix: str) -> dict[str, Any]:
        """Collect criteria values from form."""
        criteria: dict[str, Any] = {}
        type_def = self._selected_type_def if self._mode == "create" else EVALUATOR_TYPES.get(
            self._editing_evaluator_data.get("evaluatorTypeId", ""), {}
        )
        criteria_fields = type_def.get("criteria_fields", [])

        # Query from external container if form is in right panel (create mode), otherwise from self
        query_target = self._external_container if (self._mode == "create" and self._external_container) else self

        for field in criteria_fields:
            field_name = field.get("name", "")
            field_type = field.get("type", "string")

            try:
                widget_id = f"#{prefix}-{field_name}"
                if field_type == "boolean":
                    checkbox = query_target.query_one(widget_id, Checkbox)
                    criteria[field_name] = checkbox.value
                else:
                    input_widget = query_target.query_one(widget_id, Input)
                    value = input_widget.value.strip()
                    if value:
                        if value.startswith("{") or value.startswith("["):
                            try:
                                criteria[field_name] = json.loads(value)
                            except json.JSONDecodeError:
                                criteria[field_name] = value
                        else:
                            criteria[field_name] = value
            except Exception:
                pass

        return criteria

    async def _handle_create(self) -> None:
        """Collect form data and emit to parent for persistence."""
        form_data = self.get_create_form_data()
        if not form_data:
            return

        # Mark as create mode
        form_data["is_create"] = True

        # Emit data to parent for persistence
        if self.on_save:
            self.on_save(form_data)

    async def _handle_save_edit(self) -> None:
        """Collect form data and emit to parent for persistence."""
        form_data = self.get_edit_form_data()
        if not form_data:
            return

        # Mark as edit mode
        form_data["is_create"] = False

        # Emit data to parent for persistence
        if self.on_save:
            self.on_save(form_data)

    async def _handle_delete(self) -> None:
        """Emit evaluator_id to parent for deletion."""
        if not self._editing_evaluator_id:
            return

        # Emit evaluator_id to parent for persistence
        if self.on_delete:
            self.on_delete(self._editing_evaluator_id)
