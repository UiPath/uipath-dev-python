"""Eval sets and runs endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(tags=["evals"])
logger = logging.getLogger(__name__)


@router.get("/eval-sets")
async def list_eval_sets(request: Request) -> list[dict[str, Any]]:
    """List discovered eval sets."""
    server = request.app.state.server
    sets = server.eval_service.discover_eval_sets()
    return [
        {
            "id": s.id,
            "name": s.name,
            "eval_count": s.eval_count,
            "evaluator_ids": s.evaluator_ids,
        }
        for s in sets
    ]


class CreateEvalSetBody(BaseModel):
    """Body for creating a new eval set."""

    name: str
    evaluator_refs: list[str] = []


@router.post("/eval-sets")
async def create_eval_set(request: Request, body: CreateEvalSetBody) -> dict[str, Any]:
    """Create a new eval set JSON file."""
    server = request.app.state.server
    try:
        info = server.eval_service.create_eval_set(body.name, body.evaluator_refs)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {
        "id": info.id,
        "name": info.name,
        "eval_count": info.eval_count,
        "evaluator_ids": info.evaluator_ids,
    }


class AddEvalItemBody(BaseModel):
    """Body for adding an item to an eval set."""

    name: str
    inputs: dict[str, Any] = {}
    expected_output: Any = None
    expected_behavior: str = ""
    simulation_instructions: str = ""
    evaluation_criterias: dict[str, dict[str, Any]] | None = None


@router.post("/eval-sets/{set_id}/items")
async def add_eval_item(
    request: Request, set_id: str, body: AddEvalItemBody
) -> dict[str, Any]:
    """Add a new item to an eval set."""
    server = request.app.state.server
    try:
        item = server.eval_service.add_eval_item(
            set_id,
            body.name,
            body.inputs,
            body.expected_output,
            expected_behavior=body.expected_behavior,
            simulation_instructions=body.simulation_instructions,
            evaluation_criterias=body.evaluation_criterias,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return item


class UpdateEvalItemBody(BaseModel):
    """Body for updating an eval item."""

    name: str | None = None
    inputs: dict[str, Any] | None = None
    expected_output: Any = ...
    expected_behavior: str | None = None
    simulation_instructions: str | None = None


@router.put("/eval-sets/{set_id}/items/{item_name}")
async def update_eval_item(
    request: Request, set_id: str, item_name: str, body: UpdateEvalItemBody
) -> dict[str, Any]:
    """Update an eval item's fields."""
    server = request.app.state.server
    try:
        kwargs: dict[str, Any] = {}
        if body.name is not None:
            kwargs["name"] = body.name
        if body.inputs is not None:
            kwargs["inputs"] = body.inputs
        if body.expected_output is not ...:
            kwargs["expected_output"] = body.expected_output
        if body.expected_behavior is not None:
            kwargs["expected_behavior"] = body.expected_behavior
        if body.simulation_instructions is not None:
            kwargs["simulation_instructions"] = body.simulation_instructions
        item = server.eval_service.update_eval_item(set_id, item_name, **kwargs)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return item


class UpdateEvalItemCriteriasBody(BaseModel):
    """Body for updating evaluationCriterias on a specific eval item."""

    evaluation_criterias: dict[str, Any]


@router.patch("/eval-sets/{set_id}/items/{item_name}/evaluators")
async def update_eval_item_criterias(
    request: Request, set_id: str, item_name: str, body: UpdateEvalItemCriteriasBody
) -> dict[str, Any]:
    """Update evaluationCriterias for a specific eval item."""
    server = request.app.state.server
    try:
        item = server.eval_service.update_eval_item_criterias(
            set_id, item_name, body.evaluation_criterias
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return item


@router.delete("/eval-sets/{set_id}/items/{item_name}")
async def delete_eval_item(
    request: Request, set_id: str, item_name: str
) -> dict[str, str]:
    """Delete an item from an eval set by name."""
    server = request.app.state.server
    try:
        server.eval_service.delete_eval_item(set_id, item_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return {"status": "ok"}


class UpdateEvalSetEvaluatorsBody(BaseModel):
    """Body for updating evaluators on an eval set."""

    evaluator_refs: list[str]


@router.patch("/eval-sets/{set_id}/evaluators")
async def update_eval_set_evaluators(
    request: Request, set_id: str, body: UpdateEvalSetEvaluatorsBody
) -> dict[str, Any]:
    """Update the evaluators for an eval set."""
    server = request.app.state.server
    try:
        detail = server.eval_service.update_eval_set_evaluators(
            set_id, body.evaluator_refs
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return detail


@router.get("/eval-sets/{set_id}")
async def get_eval_set(request: Request, set_id: str) -> dict[str, Any]:
    """Get full eval set detail including items."""
    server = request.app.state.server
    detail = server.eval_service.get_eval_set_detail(set_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Eval set '{set_id}' not found")
    return detail


@router.post("/eval-sets/{set_id}/runs")
async def start_eval_run(request: Request, set_id: str) -> dict[str, Any]:
    """Start an eval run for the given eval set."""
    server = request.app.state.server
    run = await server.eval_service.start_eval_run(set_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Eval set '{set_id}' not found")
    return run.to_summary()


@router.get("/eval-runs")
async def list_eval_runs(request: Request) -> list[dict[str, Any]]:
    """List all eval runs."""
    server = request.app.state.server
    return [r.to_summary() for r in server.eval_service.list_eval_runs()]


@router.get("/eval-runs/{run_id}")
async def get_eval_run(request: Request, run_id: str) -> dict[str, Any]:
    """Get full eval run detail with per-item results."""
    server = request.app.state.server
    run = server.eval_service.get_eval_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Eval run '{run_id}' not found")
    return run.to_detail()
