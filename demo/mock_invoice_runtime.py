"""Mock Financial Invoice Processing runtime for demonstration purposes."""

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

ENTRYPOINT_INVOICE = "agent/invoice_processing.py:process"

logger = logging.getLogger(__name__)

S = UiPathRuntimeStatePhase.STARTED
C = UiPathRuntimeStatePhase.COMPLETED


def _state(
    node: str,
    phase: UiPathRuntimeStatePhase,
    payload: dict[str, Any] | None = None,
) -> UiPathRuntimeStateEvent:
    return UiPathRuntimeStateEvent(node_name=node, phase=phase, payload=payload or {})


class MockInvoiceRuntime:
    """Mock runtime that simulates a financial invoice processing pipeline."""

    def __init__(self, entrypoint: str = ENTRYPOINT_INVOICE) -> None:
        """Initialize the MockInvoiceRuntime."""
        self.entrypoint = entrypoint
        self.tracer = trace.get_tracer("uipath.dev.mock.invoice-processing")

    async def get_schema(self) -> UiPathRuntimeSchema:
        """Get the schema for the invoice processing runtime."""
        return UiPathRuntimeSchema(
            filePath=self.entrypoint,
            uniqueId="mock-invoice-processing-runtime",
            type="agent",
            input={
                "type": "object",
                "properties": {
                    "invoice_id": {
                        "type": "string",
                        "description": "Invoice ID to process (e.g. INV-2024-08731)",
                    },
                    "currency": {
                        "type": "string",
                        "enum": ["USD", "EUR", "GBP"],
                        "default": "USD",
                        "description": "Invoice currency",
                    },
                },
                "required": ["invoice_id"],
            },
            output={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "total_amount": {"type": "number"},
                    "line_items_count": {"type": "integer"},
                    "fraud_score": {"type": "number"},
                    "approval_level": {"type": "string"},
                    "payment_reference": {"type": "string"},
                },
                "required": ["status", "total_amount"],
            },
            graph=UiPathRuntimeGraph(
                nodes=[
                    UiPathRuntimeNode(
                        id="__start__", name="__start__", type="__start__"
                    ),
                    UiPathRuntimeNode(
                        id="ingest_document",
                        name="ingest_document",
                        type="node",
                    ),
                    UiPathRuntimeNode(
                        id="extract_line_items",
                        name="extract_line_items",
                        type="model",
                        metadata={"model_name": "invoice-extractor-v3"},
                    ),
                    UiPathRuntimeNode(
                        id="validate_amounts",
                        name="validate_amounts",
                        type="node",
                    ),
                    UiPathRuntimeNode(
                        id="fraud_check",
                        name="fraud_check",
                        type="model",
                        metadata={"model_name": "fraud-detection-ensemble"},
                    ),
                    UiPathRuntimeNode(
                        id="approval_routing",
                        name="approval_routing",
                        type="node",
                    ),
                    UiPathRuntimeNode(
                        id="generate_payment",
                        name="generate_payment",
                        type="node",
                    ),
                    UiPathRuntimeNode(id="__end__", name="__end__", type="__end__"),
                ],
                edges=[
                    UiPathRuntimeEdge(source="__start__", target="ingest_document"),
                    UiPathRuntimeEdge(
                        source="ingest_document", target="extract_line_items"
                    ),
                    UiPathRuntimeEdge(
                        source="extract_line_items", target="validate_amounts"
                    ),
                    # Cycle: validation mismatch triggers re-extraction
                    UiPathRuntimeEdge(
                        source="validate_amounts",
                        target="extract_line_items",
                        label="mismatch",
                    ),
                    UiPathRuntimeEdge(source="validate_amounts", target="fraud_check"),
                    # Cycle: fraud flag triggers re-validation with stricter rules
                    UiPathRuntimeEdge(
                        source="fraud_check",
                        target="validate_amounts",
                        label="re_validate",
                    ),
                    UiPathRuntimeEdge(source="fraud_check", target="approval_routing"),
                    UiPathRuntimeEdge(
                        source="approval_routing", target="generate_payment"
                    ),
                    UiPathRuntimeEdge(source="generate_payment", target="__end__"),
                ],
            ),
        )

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        """Execute the invoice processing runtime by consuming stream()."""
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
        """Stream events from the invoice processing pipeline."""
        payload = input or {}
        invoice_id = str(payload.get("invoice_id", "INV-2024-08731"))
        currency = str(payload.get("currency", "USD"))

        root_span = self.tracer.start_span(
            "invoice_processing.execute",
            attributes={
                "uipath.runtime.name": "InvoiceProcessingRuntime",
                "uipath.runtime.type": "agent",
                "uipath.runtime.entrypoint": self.entrypoint,
                "uipath.input.invoice_id": invoice_id,
                "uipath.input.currency": currency,
            },
        )
        root_ctx = trace.set_span_in_context(root_span)
        try:
            # 1. Ingest document — parse the invoice PDF
            yield _state("ingest_document", S)
            with self.tracer.start_as_current_span(
                "ingest_document",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "preprocess",
                    "uipath.input.invoice_id": invoice_id,
                    "uipath.input.format": "PDF",
                },
            ) as span:
                await asyncio.sleep(0.4)
                vendor = "Merck KGaA"
                vendor_id = "VND-00412"
                pages = 3
                doc_metadata = {
                    "vendor": vendor,
                    "vendor_id": vendor_id,
                    "invoice_date": "2024-11-15",
                    "due_date": "2024-12-15",
                    "pages": pages,
                }
                span.set_attribute("uipath.output.vendor", vendor)
                span.set_attribute("uipath.output.vendor_id", vendor_id)
                span.set_attribute("uipath.output.pages", pages)
            yield _state("ingest_document", C, doc_metadata)

            # 2. Extract line items (first pass) — AI reads the invoice
            yield _state("extract_line_items", S)
            with self.tracer.start_as_current_span(
                "extract_line_items",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "model",
                    "uipath.input.vendor": vendor,
                    "uipath.input.pages": pages,
                    "uipath.input.pass": 1,
                },
            ) as span:
                await asyncio.sleep(0.7)
                line_items = [
                    {
                        "description": "API-Grade Reagent Lot #R-2024-881",
                        "qty": 500,
                        "unit_price": 42.50,
                        "amount": 21250.00,
                    },
                    {
                        "description": "HPLC Column (C18, 250mm)",
                        "qty": 12,
                        "unit_price": 890.00,
                        "amount": 10680.00,
                    },
                    {
                        "description": "Lab Consumables Bundle Q4",
                        "qty": 1,
                        "unit_price": 3450.00,
                        "amount": 3450.00,
                    },
                ]
                subtotal = 35380.00
                tax = 2830.40
                extracted_total = 38210.40
                span.set_attribute("uipath.output.line_items_count", len(line_items))
                span.set_attribute("uipath.output.subtotal", subtotal)
                span.set_attribute("uipath.output.extracted_total", extracted_total)
            yield _state(
                "extract_line_items",
                C,
                {
                    "line_items_count": len(line_items),
                    "subtotal": subtotal,
                    "tax": tax,
                    "total": extracted_total,
                },
            )

            # 3. Validate amounts (first pass) — totals don't match
            yield _state("validate_amounts", S)
            with self.tracer.start_as_current_span(
                "validate_amounts",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "validation",
                    "uipath.input.extracted_total": extracted_total,
                    "uipath.input.expected_tax_rate": 0.08,
                    "uipath.input.pass": 1,
                },
            ) as span:
                await asyncio.sleep(0.4)
                expected_tax = subtotal * 0.08
                mismatch = abs(tax - expected_tax) > 0.01
                span.set_attribute("uipath.output.expected_tax", expected_tax)
                span.set_attribute("uipath.output.actual_tax", tax)
                span.set_attribute("uipath.output.mismatch", mismatch)
            yield _state(
                "validate_amounts",
                C,
                {"mismatch": mismatch, "expected_tax": expected_tax},
            )

            # 4. Cycle back: re-extract line items (tax correction)
            yield _state("extract_line_items", S)
            with self.tracer.start_as_current_span(
                "extract_line_items",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "model",
                    "uipath.input.reason": "tax_mismatch_correction",
                    "uipath.input.pass": 2,
                },
            ) as span:
                await asyncio.sleep(0.5)
                tax = expected_tax  # 2830.40 → correct
                corrected_total = subtotal + tax
                span.set_attribute("uipath.output.corrected_tax", tax)
                span.set_attribute("uipath.output.corrected_total", corrected_total)
            yield _state(
                "extract_line_items",
                C,
                {"corrected_total": corrected_total, "tax": tax},
            )

            # 5. Validate amounts (second pass) — now correct
            yield _state("validate_amounts", S)
            with self.tracer.start_as_current_span(
                "validate_amounts",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "validation",
                    "uipath.input.corrected_total": corrected_total,
                    "uipath.input.pass": 2,
                },
            ) as span:
                await asyncio.sleep(0.3)
                span.set_attribute("uipath.output.valid", True)
                span.set_attribute("uipath.output.total_verified", corrected_total)
            yield _state("validate_amounts", C, {"valid": True})

            # 6. Fraud check
            yield _state("fraud_check", S)
            with self.tracer.start_as_current_span(
                "fraud_check",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "model",
                    "uipath.input.vendor_id": vendor_id,
                    "uipath.input.total_amount": corrected_total,
                    "uipath.input.line_items_count": len(line_items),
                },
            ) as span:
                await asyncio.sleep(0.6)
                fraud_score = 0.12
                fraud_flags = ["vendor_new_banking_details"]
                span.set_attribute("uipath.output.fraud_score", fraud_score)
                span.set_attribute("uipath.output.flags_count", len(fraud_flags))
                span.set_attribute("uipath.output.flags", ",".join(fraud_flags))
                span.set_attribute("uipath.output.passed", True)
            yield _state(
                "fraud_check",
                C,
                {"fraud_score": fraud_score, "flags": fraud_flags},
            )

            # 7. Approval routing
            yield _state("approval_routing", S)
            with self.tracer.start_as_current_span(
                "approval_routing",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "routing",
                    "uipath.input.total_amount": corrected_total,
                    "uipath.input.fraud_score": fraud_score,
                    "uipath.input.vendor": vendor,
                },
            ) as span:
                await asyncio.sleep(0.3)
                # Amount > 25K requires manager approval
                approval_level = (
                    "manager" if corrected_total > 25000 else "auto_approved"
                )
                approver = "Sarah Chen (Finance Director)"
                span.set_attribute("uipath.output.approval_level", approval_level)
                span.set_attribute("uipath.output.approver", approver)
                span.set_attribute(
                    "uipath.output.threshold_exceeded", corrected_total > 25000
                )
            yield _state(
                "approval_routing",
                C,
                {"approval_level": approval_level, "approver": approver},
            )

            # 8. Generate payment
            yield _state("generate_payment", S)
            with self.tracer.start_as_current_span(
                "generate_payment",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "postprocess",
                    "uipath.input.approval_level": approval_level,
                    "uipath.input.total_amount": corrected_total,
                    "uipath.input.currency": currency,
                },
            ) as span:
                await asyncio.sleep(0.4)
                payment_ref = "PAY-2024-11-08731"
                span.set_attribute("uipath.output.payment_reference", payment_ref)
                span.set_attribute("uipath.output.payment_method", "SWIFT")
                span.set_attribute("uipath.output.scheduled_date", "2024-12-10")
            yield _state(
                "generate_payment",
                C,
                {"payment_reference": payment_ref},
            )
        finally:
            root_span.end()

        yield UiPathRuntimeResult(
            output={
                "status": "approved_pending_payment",
                "total_amount": corrected_total,
                "line_items_count": len(line_items),
                "fraud_score": fraud_score,
                "approval_level": approval_level,
                "payment_reference": payment_ref,
            },
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def dispose(self) -> None:
        """Dispose of any resources used by the invoice processing runtime."""
        pass
