"""Service for managing eval set definitions."""

import json
import os
from pathlib import Path
from typing import Any


class EvalSetService:
    """Service for eval set CRUD operations."""

    def __init__(
        self,
        base_dir: str | Path | None = None,
        eval_sets_subdir: str = "evaluations/eval-sets",
    ):
        """Initialize the eval set service.

        Args:
            base_dir: Base directory for evaluations. Defaults to current working directory.
            eval_sets_subdir: Subdirectory for eval set JSON files.
        """
        self.base_dir = Path(base_dir) if base_dir else Path(os.getcwd())
        self.eval_sets_dir = self.base_dir / eval_sets_subdir

    def ensure_directory(self) -> None:
        """Ensure the eval-sets directory exists."""
        self.eval_sets_dir.mkdir(parents=True, exist_ok=True)

    def list_eval_sets(self) -> list[dict[str, Any]]:
        """List all eval sets from evaluations/eval-sets/.

        Returns:
            List of eval set data dictionaries.
        """
        eval_sets = []
        if not self.eval_sets_dir.exists():
            return eval_sets

        for json_file in self.eval_sets_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                eval_sets.append({
                    "id": data.get("id", json_file.stem),
                    "name": data.get("name", json_file.stem),
                    "evaluatorRefs": data.get("evaluatorRefs", []),
                    "evaluation_count": len(data.get("evaluations", [])),
                    "file_path": str(json_file),
                    "data": data,
                })
            except (json.JSONDecodeError, IOError):
                continue

        return eval_sets

    def load_eval_set(self, eval_set_id: str) -> dict[str, Any] | None:
        """Load an eval set by ID.

        Args:
            eval_set_id: The eval set ID to load.

        Returns:
            The eval set data dictionary, or None if not found.
        """
        if not self.eval_sets_dir.exists():
            return None

        # Try direct file match first
        json_file = self.eval_sets_dir / f"{eval_set_id}.json"
        if json_file.exists():
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None

        # Search by ID field
        for json_file in self.eval_sets_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("id") == eval_set_id:
                    return data
            except (json.JSONDecodeError, IOError):
                continue

        return None

    def create_eval_set(
        self,
        eval_set_id: str,
        name: str,
        evaluator_refs: list[str],
        evaluations: list[dict[str, Any]],
    ) -> str:
        """Create a new eval set JSON file.

        Args:
            eval_set_id: Unique ID for the eval set.
            name: Display name for the eval set.
            evaluator_refs: List of evaluator IDs to include.
            evaluations: List of evaluation/test case definitions.

        Returns:
            The path to the created file.

        Raises:
            ValueError: If ID already exists.
        """
        self.ensure_directory()

        # Check if ID already exists
        existing_file = self.eval_sets_dir / f"{eval_set_id}.json"
        if existing_file.exists():
            raise ValueError(f"Eval set with ID '{eval_set_id}' already exists")

        # Build the eval set JSON structure
        eval_set_data = {
            "version": "1.0",
            "id": eval_set_id,
            "name": name,
            "evaluatorRefs": evaluator_refs,
            "evaluations": evaluations,
        }

        # Write to file
        file_path = self.eval_sets_dir / f"{eval_set_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(eval_set_data, f, indent=2)

        return str(file_path)

    def save_eval_set(self, eval_set_id: str, data: dict[str, Any]) -> str:
        """Save an eval set directly with the given data.

        Args:
            eval_set_id: The eval set ID.
            data: The full eval set data to save.

        Returns:
            The path to the saved file.
        """
        self.ensure_directory()
        file_path = self.eval_sets_dir / f"{eval_set_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return str(file_path)
