"""Eval set creation panel for creating new eval sets."""

from typing import Any, Callable

from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.widgets import Button, Input, Static


class EvalSetCreatePanel(Vertical):
    """Panel for creating a new eval set."""

    def __init__(
        self,
        on_create: Callable[[dict[str, Any]], None] | None = None,
        on_close: Callable[[], None] | None = None,
        **kwargs,
    ):
        """Initialize the eval set create panel.

        Args:
            on_create: Callback with form data when create is clicked.
            on_close: Callback when close button is clicked.
        """
        super().__init__(**kwargs)
        self.on_create = on_create
        self.on_close = on_close

    def compose(self) -> ComposeResult:
        """Compose the panel UI."""
        yield ScrollableContainer(id="eval-set-create-content")

    def on_mount(self) -> None:
        """Handle mount event - populate the form."""
        self.call_later(self._populate_form)

    async def _populate_form(self) -> None:
        """Populate the form."""
        try:
            content = self.query_one("#eval-set-create-content", ScrollableContainer)
            await content.remove_children()

            # Close button
            await content.mount(
                Button("✕", id="close-eval-set-create-btn", classes="close-btn")
            )

            # Form fields
            await content.mount(
                Static("[bold]Eval Set ID *[/bold]", classes="detail-row")
            )
            await content.mount(
                Input(placeholder="my-eval-set", id="new-eval-set-id-input")
            )

            await content.mount(Static("[bold]Name[/bold]", classes="detail-row"))
            await content.mount(
                Input(placeholder="My Evaluation Set", id="new-eval-set-name-input")
            )

            await content.mount(
                Static(
                    "[dim]After creation, assign evaluators and add evaluations from the tabs.[/dim]",
                    classes="helper-text",
                )
            )

            # Create button
            await content.mount(
                Button(
                    "Create Eval Set",
                    id="create-eval-set-btn",
                    variant="primary",
                    classes="small-btn",
                )
            )

        except Exception:
            pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        btn_id = event.button.id or ""

        if btn_id == "close-eval-set-create-btn":
            event.stop()
            if self.on_close:
                self.on_close()
        elif btn_id == "create-eval-set-btn":
            event.stop()
            await self._handle_create()

    async def _handle_create(self) -> None:
        """Collect form data and emit to parent."""
        try:
            id_input = self.query_one("#new-eval-set-id-input", Input)
            name_input = self.query_one("#new-eval-set-name-input", Input)

            eval_set_id = id_input.value.strip()
            if not eval_set_id:
                self.app.notify("Please enter an eval set ID", severity="error")
                return

            name = name_input.value.strip() or eval_set_id

            # Build form data to emit
            form_data: dict[str, Any] = {
                "eval_set_id": eval_set_id,
                "name": name,
                "evaluator_refs": [],
                "evaluations": [],
            }

            if self.on_create:
                self.on_create(form_data)

        except Exception as e:
            self.app.notify(f"Error collecting form data: {e}", severity="error")

    def reset(self) -> None:
        """Reset the form to initial state."""
        self.call_later(self._populate_form)
