"""TextArea component that validates JSON input."""

import json

from textual.widgets import TextArea


class JsonInput(TextArea):
    """TextArea that validates JSON on change."""

    def validate_json(self) -> bool:
        """Validate the current text as JSON."""
        text = self.text.strip()
        if not text:
            self.remove_class("invalid")
            return True
        try:
            json.loads(text)
            self.remove_class("invalid")
            return True
        except json.JSONDecodeError:
            self.add_class("invalid")
            return False

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Validate JSON when the text changes."""
        self.validate_json()
