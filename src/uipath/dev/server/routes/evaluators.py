"""Evaluator catalog endpoint."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["evaluators"])
logger = logging.getLogger(__name__)

# Human-readable metadata keyed by evaluator ID.
# Used to enrich the dynamic discovery from uipath.eval.evaluators.EVALUATORS.
_EVALUATOR_META: dict[str, dict[str, str]] = {
    "uipath-exact-match": {
        "name": "Exact Match",
        "type": "deterministic",
        "category": "output",
        "description": "Checks if actual output exactly matches expected output.",
    },
    "uipath-contains": {
        "name": "Contains",
        "type": "deterministic",
        "category": "output",
        "description": "Checks if actual output contains the expected substring.",
    },
    "uipath-json-similarity": {
        "name": "JSON Similarity",
        "type": "deterministic",
        "category": "output",
        "description": (
            "Compares JSON structures for semantic similarity, "
            "ignoring key ordering and whitespace."
        ),
    },
    "uipath-llm-judge-output-semantic-similarity": {
        "name": "LLM Judge Output",
        "type": "llm",
        "category": "quality",
        "description": (
            "LLM-based evaluation of semantic similarity "
            "between actual and expected output."
        ),
    },
    "uipath-llm-judge-output-strict-json-similarity": {
        "name": "LLM Judge Strict JSON",
        "type": "llm",
        "category": "quality",
        "description": (
            "LLM-based evaluation of strict JSON structural similarity "
            "between actual and expected output."
        ),
    },
    "uipath-llm-judge-trajectory-similarity": {
        "name": "LLM Judge Trajectory",
        "type": "llm",
        "category": "quality",
        "description": (
            "LLM-based evaluation of whether the agent's tool call trajectory "
            "matches the expected sequence."
        ),
    },
    "uipath-llm-judge-trajectory-simulation": {
        "name": "LLM Judge Trajectory Simulation",
        "type": "llm",
        "category": "quality",
        "description": (
            "LLM-based simulation and comparison of agent trajectories "
            "for behavioral evaluation."
        ),
    },
    "uipath-tool-call-order": {
        "name": "Tool Call Order",
        "type": "tool",
        "category": "tools",
        "description": "Validates that tools were called in the expected sequence.",
    },
    "uipath-tool-call-args": {
        "name": "Tool Call Args",
        "type": "tool",
        "category": "tools",
        "description": (
            "Checks if the agent called tools with the expected arguments."
        ),
    },
    "uipath-tool-call-count": {
        "name": "Tool Call Count",
        "type": "tool",
        "category": "tools",
        "description": (
            "Validates that the agent made the expected number of tool calls."
        ),
    },
    "uipath-tool-call-output": {
        "name": "Tool Call Output",
        "type": "tool",
        "category": "tools",
        "description": "Validates the output returned by tool calls.",
    },
}


def _humanize_class_name(name: str) -> str:
    """Convert PascalCase class name to human-readable form."""
    # Strip 'Evaluator' suffix
    name = name.removesuffix("Evaluator")
    # Insert spaces before capitals
    result = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0 and not name[i - 1].isupper():
            result.append(" ")
        result.append(ch)
    return "".join(result)


def _infer_type(cls_name: str) -> str:
    """Infer evaluator type from class name."""
    lower = cls_name.lower()
    if "llm" in lower or "judge" in lower:
        return "llm"
    if "tool" in lower:
        return "tool"
    return "deterministic"


def _infer_type_from_id(ev_type_id: str) -> str:
    """Infer evaluator type from evaluatorTypeId string."""
    lower = ev_type_id.lower()
    if "llm" in lower or "judge" in lower:
        return "llm"
    if "tool" in lower:
        return "tool"
    return "deterministic"


def _load_evaluators() -> list[dict[str, Any]]:
    """Load evaluator metadata from uipath.eval.evaluators.EVALUATORS."""
    try:
        from uipath.eval.evaluators import EVALUATORS

        result: list[dict[str, Any]] = []
        for cls in EVALUATORS:
            ev_id = cls.get_evaluator_id()
            meta = _EVALUATOR_META.get(ev_id, {})

            json_type: dict[str, Any] = {}
            try:
                json_type = cls.generate_json_type()
            except Exception:
                pass

            result.append(
                {
                    "id": ev_id,
                    "name": meta.get("name", _humanize_class_name(cls.__name__)),
                    "type": meta.get("type", _infer_type(cls.__name__)),
                    "category": meta.get("category", "output"),
                    "description": meta.get("description", ""),
                    "config_schema": json_type.get("evaluatorConfigSchema", {}),
                    "criteria_schema": json_type.get("evaluationCriteriaSchema", {}),
                }
            )
        return result
    except Exception:
        logger.debug("Failed to load evaluators from uipath.eval", exc_info=True)
        return []


@router.get("/evaluators")
async def list_evaluators() -> list[dict[str, Any]]:
    """Return metadata for all available evaluators."""
    return _load_evaluators()


@router.get("/llm-models")
async def list_llm_models() -> list[dict[str, Any]]:
    """Return available LLM models from AgentHub."""
    try:
        from uipath.platform import UiPath

        sdk = UiPath()
        models = await sdk.agenthub.get_available_llm_models_async()
        return [{"model_name": m.model_name, "vendor": m.vendor} for m in models]
    except Exception:
        logger.debug("Failed to fetch LLM models from AgentHub", exc_info=True)
        return []


# ------------------------------------------------------------------
# Local evaluator files (evaluations/evaluators/*.json)
# ------------------------------------------------------------------


def _local_evaluators_dir() -> Path:
    return Path.cwd() / "evaluations" / "evaluators"


def _discover_local_evaluators() -> list[dict[str, Any]]:
    """Scan evaluations/evaluators/ for JSON evaluator config files."""
    evals_dir = _local_evaluators_dir()
    if not evals_dir.is_dir():
        return []

    results: list[dict[str, Any]] = []
    for json_file in sorted(evals_dir.glob("*.json")):
        try:
            raw = json.loads(json_file.read_text(encoding="utf-8"))
            config = raw.get("evaluatorConfig", {})
            ev_type_id = raw.get("evaluatorTypeId", "")
            meta = _EVALUATOR_META.get(ev_type_id, {})

            results.append(
                {
                    "id": raw.get("id", json_file.stem),
                    "name": config.get("name", raw.get("name", json_file.stem)),
                    "description": raw.get("description", ""),
                    "evaluator_type_id": ev_type_id,
                    "category": meta.get("category", "output"),
                    "type": meta.get("type", _infer_type_from_id(ev_type_id)),
                    "target_output_key": config.get("targetOutputKey", "*"),
                    "config": config,
                }
            )
        except Exception:
            logger.warning("Failed to parse evaluator: %s", json_file, exc_info=True)

    return results


_CUSTOM_EVALUATOR_TEMPLATE = '''\
from typing import Optional

from uipath.eval.evaluators import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
)
from uipath.eval.models import (
    AgentExecution,
    ErrorEvaluationResult,
    EvaluationResult,
    NumericEvaluationResult,
)


class {class_name}Criteria(BaseEvaluationCriteria):
    """Per-item evaluation criteria for {class_name}."""

    pass  # TODO: add fields like expected_value: str


class {class_name}Config(BaseEvaluatorConfig[{class_name}Criteria]):
    """Configuration for {class_name}."""

    name: str = "{class_name}"
    default_evaluation_criteria: Optional[{class_name}Criteria] = None


class {class_name}(
    BaseEvaluator[{class_name}Criteria, {class_name}Config, None]
):
    """{description}"""

    @classmethod
    def get_evaluator_id(cls) -> str:
        return "{class_name}"

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: {class_name}Criteria,
    ) -> EvaluationResult:
        try:
            output = agent_execution.agent_output
            # TODO: implement evaluation logic
            score = 0.0
            return NumericEvaluationResult(score=score, details="Not implemented yet")
        except Exception as e:
            return ErrorEvaluationResult(error=str(e))
'''


class ScaffoldCustomEvaluatorBody(BaseModel):
    """Body for scaffolding a custom evaluator Python file."""

    name: str
    description: str = ""


@router.post("/custom-evaluators/scaffold")
async def scaffold_custom_evaluator(
    body: ScaffoldCustomEvaluatorBody,
) -> dict[str, Any]:
    """Scaffold a new custom evaluator Python file."""
    class_name = body.name.replace(" ", "").replace("-", "").replace("_", "")
    if not class_name.endswith("Evaluator"):
        class_name += "Evaluator"

    # snake_case filename
    snake = ""
    for i, ch in enumerate(class_name):
        if ch.isupper() and i > 0 and not class_name[i - 1].isupper():
            snake += "_"
        snake += ch.lower()
    filename = f"{snake}.py"

    custom_dir = Path.cwd() / "evaluations" / "evaluators" / "custom"
    custom_dir.mkdir(parents=True, exist_ok=True)

    filepath = custom_dir / filename
    if filepath.exists():
        raise HTTPException(status_code=409, detail=f"File already exists: {filepath}")

    content = _CUSTOM_EVALUATOR_TEMPLATE.format(
        class_name=class_name,
        description=body.description or f"Custom evaluator: {body.name}",
    )
    filepath.write_text(content, encoding="utf-8")

    return {
        "file_path": str(filepath),
        "filename": filename,
        "class_name": class_name,
        "evaluator_id": class_name,
    }


class RegisterCustomEvaluatorBody(BaseModel):
    """Body for registering a custom evaluator."""

    filename: str


@router.post("/custom-evaluators/register")
async def register_custom_evaluator(
    body: RegisterCustomEvaluatorBody,
) -> dict[str, Any]:
    """Register a custom evaluator by running the registration logic."""
    try:
        from uipath.eval.evaluators.registration import register_evaluator

        evaluator_id, spec_path = register_evaluator(body.filename)
        return {
            "evaluator_id": evaluator_id,
            "spec_path": spec_path,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


class CreateEvaluatorBody(BaseModel):
    """Body for creating a new local evaluator JSON file."""

    name: str
    description: str = ""
    evaluator_type_id: str
    config: dict[str, Any] = {}


@router.get("/local-evaluators")
async def list_local_evaluators() -> list[dict[str, Any]]:
    """Return all locally defined evaluator configurations."""
    return _discover_local_evaluators()


@router.post("/local-evaluators")
async def create_local_evaluator(body: CreateEvaluatorBody) -> dict[str, Any]:
    """Create a new evaluator JSON file in evaluations/evaluators/."""
    evals_dir = _local_evaluators_dir()
    evals_dir.mkdir(parents=True, exist_ok=True)

    # Build standard evaluator JSON
    evaluator_id = body.name.replace(" ", "")
    config_block: dict[str, Any] = {"name": evaluator_id, **body.config}
    # Only include defaultEvaluationCriteria when explicitly provided and non-empty;
    # an empty dict fails Pydantic validation for evaluators that require fields like expectedOutput.
    if not config_block.get("defaultEvaluationCriteria"):
        config_block.pop("defaultEvaluationCriteria", None)

    evaluator_json: dict[str, Any] = {
        "version": "1.0",
        "id": evaluator_id,
        "description": body.description,
        "evaluatorTypeId": body.evaluator_type_id,
        "evaluatorConfig": config_block,
    }

    filepath = evals_dir / f"{evaluator_id}.json"
    if filepath.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Evaluator '{evaluator_id}' already exists",
        )

    filepath.write_text(json.dumps(evaluator_json, indent=2), encoding="utf-8")

    meta = _EVALUATOR_META.get(body.evaluator_type_id, {})
    return {
        "id": evaluator_id,
        "name": evaluator_id,
        "description": body.description,
        "evaluator_type_id": body.evaluator_type_id,
        "category": meta.get("category", "output"),
        "type": meta.get("type", _infer_type_from_id(body.evaluator_type_id)),
        "target_output_key": body.config.get("targetOutputKey", "*"),
        "config": evaluator_json["evaluatorConfig"],
    }


class UpdateEvaluatorBody(BaseModel):
    """Body for updating an existing local evaluator JSON file."""

    description: str | None = None
    evaluator_type_id: str | None = None
    config: dict[str, Any] | None = None


@router.put("/local-evaluators/{evaluator_id}")
async def update_local_evaluator(
    evaluator_id: str, body: UpdateEvaluatorBody
) -> dict[str, Any]:
    """Update an existing evaluator JSON file."""
    evals_dir = _local_evaluators_dir()
    filepath = evals_dir / f"{evaluator_id}.json"

    if not filepath.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Evaluator '{evaluator_id}' not found",
        )

    raw = json.loads(filepath.read_text(encoding="utf-8"))

    if body.description is not None:
        raw["description"] = body.description
    if body.evaluator_type_id is not None:
        raw["evaluatorTypeId"] = body.evaluator_type_id
    if body.config is not None:
        config = raw.get("evaluatorConfig", {})
        config.update(body.config)
        raw["evaluatorConfig"] = config

    filepath.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    config = raw.get("evaluatorConfig", {})
    ev_type_id = raw.get("evaluatorTypeId", "")
    meta = _EVALUATOR_META.get(ev_type_id, {})
    return {
        "id": raw.get("id", evaluator_id),
        "name": config.get("name", raw.get("id", evaluator_id)),
        "description": raw.get("description", ""),
        "evaluator_type_id": ev_type_id,
        "category": meta.get("category", "output"),
        "type": meta.get("type", _infer_type_from_id(ev_type_id)),
        "target_output_key": config.get("targetOutputKey", "*"),
        "config": config,
    }
