"""Service for managing evaluator instances."""

import json
import os
from pathlib import Path
from typing import Any

from uipath.dev.models.evaluator_types import get_evaluator_type


class EvaluatorService:
    """Service for evaluator CRUD operations."""

    def __init__(
        self,
        base_dir: str | Path | None = None,
        evaluators_subdir: str = "evaluations/evaluators",
    ):
        """Initialize the evaluator service.

        Args:
            base_dir: Base directory for evaluations. Defaults to current working directory.
            evaluators_subdir: Subdirectory for evaluator JSON files.
        """
        self.base_dir = Path(base_dir) if base_dir else Path(os.getcwd())
        self.evaluators_dir = self.base_dir / evaluators_subdir

    def ensure_directory(self) -> None:
        """Ensure the evaluators directory exists."""
        self.evaluators_dir.mkdir(parents=True, exist_ok=True)

    def list_evaluators(self) -> list[dict[str, Any]]:
        """List all evaluator instances from evaluations/evaluators/.

        Returns:
            List of evaluator data dictionaries with id, description, and type info.
        """
        evaluators = []
        if not self.evaluators_dir.exists():
            return evaluators

        for json_file in self.evaluators_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                evaluators.append({
                    "id": data.get("id", json_file.stem),
                    "description": data.get("description", ""),
                    "evaluatorTypeId": data.get("evaluatorTypeId", ""),
                    "file_path": str(json_file),
                    "data": data,
                })
            except (json.JSONDecodeError, IOError):
                continue

        return evaluators

    def load_evaluator(self, evaluator_id: str) -> dict[str, Any] | None:
        """Load an evaluator by ID.

        Args:
            evaluator_id: The evaluator ID to load.

        Returns:
            The evaluator data dictionary, or None if not found.
        """
        if not self.evaluators_dir.exists():
            return None

        # Try direct file match first
        json_file = self.evaluators_dir / f"{evaluator_id}.json"
        if json_file.exists():
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None

        # Search by ID field in all files
        for json_file in self.evaluators_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("id") == evaluator_id:
                    return data
            except (json.JSONDecodeError, IOError):
                continue

        return None

    def create_evaluator(
        self,
        evaluator_id: str,
        evaluator_type_id: str,
        description: str,
        config: dict[str, Any],
        default_criteria: dict[str, Any] | None = None,
    ) -> str:
        """Create a new evaluator JSON file.

        Args:
            evaluator_id: Unique ID for the evaluator.
            evaluator_type_id: The evaluator type ID (e.g., 'uipath-exact-match').
            description: Description of the evaluator.
            config: Configuration dictionary for the evaluator.
            default_criteria: Optional default evaluation criteria.

        Returns:
            The path to the created file.

        Raises:
            ValueError: If the evaluator type is invalid or ID already exists.
        """
        self.ensure_directory()

        # Validate evaluator type
        type_def = get_evaluator_type(evaluator_type_id)
        if not type_def:
            raise ValueError(f"Invalid evaluator type: {evaluator_type_id}")

        # Check if ID already exists
        existing_file = self.evaluators_dir / f"{evaluator_id}.json"
        if existing_file.exists():
            raise ValueError(f"Evaluator with ID '{evaluator_id}' already exists")

        # Build evaluator config
        evaluator_config = config.copy() if config else {}
        if default_criteria:
            evaluator_config["defaultEvaluationCriteria"] = default_criteria

        # Build the evaluator JSON structure
        evaluator_data = {
            "version": "1.0",
            "id": evaluator_id,
            "description": description,
            "evaluatorTypeId": evaluator_type_id,
            "evaluatorConfig": evaluator_config,
        }

        # Write to file
        file_path = self.evaluators_dir / f"{evaluator_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(evaluator_data, f, indent=2)

        return str(file_path)

    def save_evaluator(self, evaluator_id: str, data: dict[str, Any]) -> str:
        """Save an evaluator directly with the given data.

        Args:
            evaluator_id: The evaluator ID.
            data: The full evaluator data to save.

        Returns:
            The path to the saved file.
        """
        self.ensure_directory()

        # Build the evaluator JSON structure
        evaluator_data = {
            "version": "1.0",
            "id": data.get("id", evaluator_id),
            "description": data.get("description", ""),
            "evaluatorTypeId": data.get("evaluatorTypeId", ""),
            "evaluatorConfig": data.get("evaluatorConfig", data.get("config", {})),
        }
        if data.get("defaultCriteria"):
            evaluator_data["evaluatorConfig"]["defaultEvaluationCriteria"] = data[
                "defaultCriteria"
            ]

        # Find existing file for this evaluator
        file_path = None
        if self.evaluators_dir.exists():
            # First check direct filename match
            direct_path = self.evaluators_dir / f"{evaluator_id}.json"
            if direct_path.exists():
                file_path = direct_path
            else:
                # Search by ID field in all files
                for json_file in self.evaluators_dir.glob("*.json"):
                    try:
                        with open(json_file, "r", encoding="utf-8") as f:
                            existing_data = json.load(f)
                        if existing_data.get("id") == evaluator_id:
                            file_path = json_file
                            break
                    except (json.JSONDecodeError, IOError):
                        continue

        # Default to ID-based filename if no existing file found
        if file_path is None:
            file_path = self.evaluators_dir / f"{evaluator_id}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(evaluator_data, f, indent=2)
        return str(file_path)

    def delete_evaluator(self, evaluator_id: str) -> bool:
        """Delete an evaluator by ID.

        Args:
            evaluator_id: The evaluator ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        file_path = self.evaluators_dir / f"{evaluator_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False
