"""Mock Pharma Compliance Review runtime for demonstration purposes."""

import asyncio
import logging
from typing import Any, AsyncGenerator

from opentelemetry import trace
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeEvent,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathStreamOptions,
)
from uipath.runtime.events import (
    UiPathRuntimeStateEvent,
    UiPathRuntimeStatePhase,
)
from uipath.runtime.schema import (
    UiPathRuntimeEdge,
    UiPathRuntimeGraph,
    UiPathRuntimeNode,
    UiPathRuntimeSchema,
)

ENTRYPOINT_PHARMA = "agent/pharma_compliance.py:review"

logger = logging.getLogger(__name__)

S = UiPathRuntimeStatePhase.STARTED
C = UiPathRuntimeStatePhase.COMPLETED


def _state(
    node: str,
    phase: UiPathRuntimeStatePhase,
    payload: dict[str, Any] | None = None,
) -> UiPathRuntimeStateEvent:
    return UiPathRuntimeStateEvent(node_name=node, phase=phase, payload=payload or {})


class MockPharmaRuntime:
    """Mock runtime that simulates a pharma compliance document review pipeline."""

    def __init__(self, entrypoint: str = ENTRYPOINT_PHARMA) -> None:
        """Initialize the MockPharmaRuntime."""
        self.entrypoint = entrypoint
        self.tracer = trace.get_tracer("uipath.dev.mock.pharma-compliance")

    async def get_schema(self) -> UiPathRuntimeSchema:
        """Get the schema for the pharma compliance review runtime."""
        return UiPathRuntimeSchema(
            filePath=self.entrypoint,
            uniqueId="mock-greeting-runtime",
            type="agent",
            input={
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "Document ID to review (e.g. SOP-2024-0142)",
                    },
                    "review_type": {
                        "type": "string",
                        "enum": ["initial", "amendment", "periodic"],
                        "default": "initial",
                        "description": "Type of compliance review",
                    },
                },
                "required": ["document_id"],
            },
            output={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "findings": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "risk_level": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
                "required": ["status", "findings"],
            },
            graph=UiPathRuntimeGraph(
                nodes=[
                    UiPathRuntimeNode(
                        id="__start__", name="__start__", type="__start__"
                    ),
                    UiPathRuntimeNode(
                        id="extract_metadata",
                        name="extract_metadata",
                        type="node",
                    ),
                    UiPathRuntimeNode(
                        id="classify_document",
                        name="classify_document",
                        type="model",
                        metadata={"model_name": "pharma-doc-classifier-v2"},
                    ),
                    UiPathRuntimeNode(
                        id="check_references",
                        name="check_references",
                        type="tool",
                        metadata={
                            "tool_names": [
                                "fda_database_lookup",
                                "ema_guideline_search",
                            ],
                            "tool_count": 2,
                        },
                    ),
                    UiPathRuntimeNode(
                        id="compliance_review",
                        name="compliance_review",
                        type="model",
                        metadata={"model_name": "gxp-compliance-reviewer"},
                    ),
                    UiPathRuntimeNode(
                        id="risk_assessment",
                        name="risk_assessment",
                        type="node",
                    ),
                    UiPathRuntimeNode(
                        id="generate_report",
                        name="generate_report",
                        type="node",
                    ),
                    UiPathRuntimeNode(id="__end__", name="__end__", type="__end__"),
                ],
                edges=[
                    UiPathRuntimeEdge(source="__start__", target="extract_metadata"),
                    UiPathRuntimeEdge(
                        source="extract_metadata", target="classify_document"
                    ),
                    UiPathRuntimeEdge(
                        source="classify_document", target="check_references"
                    ),
                    UiPathRuntimeEdge(
                        source="check_references", target="compliance_review"
                    ),
                    # Cycle: compliance review can request more references
                    UiPathRuntimeEdge(
                        source="compliance_review",
                        target="check_references",
                        label="needs_more_refs",
                    ),
                    UiPathRuntimeEdge(
                        source="compliance_review", target="risk_assessment"
                    ),
                    # Cycle: high risk triggers re-review with different parameters
                    UiPathRuntimeEdge(
                        source="risk_assessment",
                        target="compliance_review",
                        label="re_review",
                    ),
                    UiPathRuntimeEdge(
                        source="risk_assessment", target="generate_report"
                    ),
                    UiPathRuntimeEdge(source="generate_report", target="__end__"),
                ],
            ),
        )

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        """Execute the pharma compliance review by consuming stream()."""
        result: UiPathRuntimeResult | None = None
        async for event in self.stream(input=input):
            if isinstance(event, UiPathRuntimeResult):
                result = event
        return result or UiPathRuntimeResult(
            output={}, status=UiPathRuntimeStatus.SUCCESSFUL
        )

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        """Stream events from the pharma compliance review pipeline."""
        payload = input or {}
        doc_id = str(payload.get("document_id", "SOP-2024-0142"))
        review_type = str(payload.get("review_type", "initial"))

        root_span = self.tracer.start_span(
            "pharma_compliance.execute",
            attributes={
                "uipath.runtime.name": "PharmaComplianceReview",
                "uipath.runtime.type": "agent",
                "uipath.runtime.entrypoint": self.entrypoint,
                "uipath.input.document_id": doc_id,
                "uipath.input.review_type": review_type,
            },
        )
        root_ctx = trace.set_span_in_context(root_span)
        try:
            # 1. Extract metadata
            yield _state("extract_metadata", S)
            with self.tracer.start_as_current_span(
                "extract_metadata",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "preprocess",
                    "uipath.input.document_id": doc_id,
                },
            ) as span:
                await asyncio.sleep(0.4)
                title = "Standard Operating Procedure: Batch Release Testing"
                version = "3.1"
                department = "Quality Assurance"
                metadata = {
                    "title": title,
                    "version": version,
                    "department": department,
                    "effective_date": "2024-03-15",
                }
                span.set_attribute("uipath.output.title", title)
                span.set_attribute("uipath.output.version", version)
            yield _state("extract_metadata", C, metadata)

            # 2. Classify document
            yield _state("classify_document", S)
            with self.tracer.start_as_current_span(
                "classify_document",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "model",
                    "uipath.input.title": title,
                    "uipath.input.department": department,
                },
            ) as span:
                await asyncio.sleep(0.6)
                category = "GMP"
                regulation = "21 CFR Part 211"
                confidence = 0.94
                classification = {
                    "category": category,
                    "sub_category": "Quality Control",
                    "regulation": regulation,
                    "confidence": confidence,
                }
                span.set_attribute("uipath.output.category", category)
                span.set_attribute("uipath.output.regulation", regulation)
                span.set_attribute("uipath.output.confidence", confidence)
            yield _state("classify_document", C, classification)

            # 3. Check references (first pass)
            yield _state("check_references", S)
            with self.tracer.start_as_current_span(
                "check_references",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "tool",
                    "uipath.input.regulation": regulation,
                    "uipath.input.databases": "FDA,EMA",
                },
            ) as span:
                await asyncio.sleep(0.7)
                ref_results = {
                    "fda_references": 3,
                    "ema_references": 2,
                    "outdated_refs": 1,
                }
                span.set_attribute("uipath.output.total_refs", 5)
                span.set_attribute("uipath.output.outdated_refs", 1)
            yield _state("check_references", C, ref_results)

            # 4. Compliance review (first pass)
            yield _state("compliance_review", S)
            with self.tracer.start_as_current_span(
                "compliance_review",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "model",
                    "uipath.input.category": category,
                    "uipath.input.ref_count": 5,
                    "uipath.input.pass": 1,
                },
            ) as span:
                await asyncio.sleep(0.8)
                findings = [
                    "Section 4.2: Missing temperature range for stability testing",
                    "Section 7.1: Reference to withdrawn FDA guidance (2019-G-0041)",
                    "Appendix B: Sampling plan does not meet ICH Q7 requirements",
                ]
                needs_more = True
                span.set_attribute("uipath.output.findings_count", len(findings))
                span.set_attribute("uipath.output.needs_more_refs", needs_more)
            yield _state("compliance_review", C, {"findings": findings})

            # 5. Cycle back: check_references (second pass — triggered by review)
            yield _state("check_references", S)
            with self.tracer.start_as_current_span(
                "check_references",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "tool",
                    "uipath.input.query": "ICH Q7 sampling requirements",
                    "uipath.input.pass": 2,
                },
            ) as span:
                await asyncio.sleep(0.5)
                span.set_attribute("uipath.output.additional_refs", 2)
            yield _state("check_references", C, {"additional_refs": 2})

            # 6. Compliance review (second pass — with additional refs)
            yield _state("compliance_review", S)
            with self.tracer.start_as_current_span(
                "compliance_review",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "model",
                    "uipath.input.pass": 2,
                    "uipath.input.additional_refs": 2,
                },
            ) as span:
                await asyncio.sleep(0.6)
                findings.append(
                    "Section 5.3: Deviation handling procedure lacks CAPA timeline"
                )
                span.set_attribute("uipath.output.findings_count", len(findings))
                span.set_attribute("uipath.output.review_complete", True)
            yield _state("compliance_review", C, {"findings": findings})

            # 7. Risk assessment
            yield _state("risk_assessment", S)
            with self.tracer.start_as_current_span(
                "risk_assessment",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "compute",
                    "uipath.input.findings_count": len(findings),
                    "uipath.input.review_type": review_type,
                },
            ) as span:
                await asyncio.sleep(0.4)
                risk_level = "medium"
                span.set_attribute("uipath.output.risk_level", risk_level)
                span.set_attribute("uipath.output.risk_score", 6.2)
            yield _state("risk_assessment", C, {"risk_level": risk_level})

            # 8. Generate report
            yield _state("generate_report", S)
            with self.tracer.start_as_current_span(
                "generate_report",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "postprocess",
                    "uipath.input.risk_level": risk_level,
                    "uipath.input.findings_count": len(findings),
                },
            ) as span:
                await asyncio.sleep(0.3)
                recommendation = (
                    "Revise document to address 4 findings before approval. "
                    "Priority: update withdrawn FDA reference and add CAPA timeline."
                )
                span.set_attribute("uipath.output.recommendation", recommendation)
            yield _state("generate_report", C)
        finally:
            root_span.end()

        yield UiPathRuntimeResult(
            output={
                "status": "review_complete",
                "findings": findings,
                "risk_level": risk_level,
                "recommendation": recommendation,
            },
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def dispose(self) -> None:
        """Dispose of any resources used by the pharma compliance runtime."""
        pass
