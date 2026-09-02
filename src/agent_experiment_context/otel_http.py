from __future__ import annotations

import json
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from multiprocessing.synchronize import Event
from queue import Queue
from urllib.request import Request, urlopen

from opentelemetry import baggage
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.context import Context
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import (
    SpanKind,
    get_current_span,
    set_span_in_context,
)
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from .a2a_extension import (
    ExperimentEnvelope,
    ExperimentEvidence,
    LocalExperimentRegistry,
)

WIRE_PREFIX = "exp.alloc."
ORCHESTRATOR_A_EXPERIMENT = "orchestrator-a-routing-v1"
SPECIALIST_EXPERIMENT = "specialist-response-mode-v1"
PROPAGATOR = CompositePropagator(
    [TraceContextTextMapPropagator(), W3CBaggagePropagator()]
)


REGISTRIES = {
    "orchestrator-a": LocalExperimentRegistry(
        "orchestrator-a",
        {ORCHESTRATOR_A_EXPERIMENT: {"normalized": "normalized"}},
    ),
    "orchestrator-b": LocalExperimentRegistry("orchestrator-b", {}),
    "shared-specialist": LocalExperimentRegistry(
        "shared-specialist",
        {
            SPECIALIST_EXPERIMENT: {
                "concise": "concise",
                "structured": "structured",
            }
        },
    ),
}


def legacy_specialist_answer(request: str) -> str:
    """Behaviour used when no locally recognized treatment materializes."""

    return f"specialist: {request.strip()}"


def _evaluate(component_id: str, observed: Mapping[str, str]) -> ExperimentEvidence:
    envelope = ExperimentEnvelope.from_pairs(*observed.items())
    return REGISTRIES[component_id].evaluate(envelope)


def _materialized_allocations(evidence: ExperimentEvidence) -> dict[str, str]:
    return {
        allocation.experiment_id: allocation.treatment
        for allocation in evidence.materialized
    }


def context_with_wire_allocations(
    allocations: Mapping[str, str], context: Context | None = None
) -> Context:
    """Attach only experiment-id -> treatment pairs to OTel Baggage.

    Assignment units, provenance, and ownership are intentionally absent from the
    wire representation.
    """

    current = context or Context()
    for experiment_id, treatment in allocations.items():
        current = baggage.set_baggage(
            f"{WIRE_PREFIX}{experiment_id}",
            treatment,
            context=current,
        )
    return current


def wire_allocations(context: Context) -> dict[str, str]:
    all_baggage = baggage.get_all(context=context)
    return {
        key.removeprefix(WIRE_PREFIX): str(value)
        for key, value in all_baggage.items()
        if key.startswith(WIRE_PREFIX)
    }


def _trace_attributes(
    observed: Mapping[str, str], applied: Mapping[str, str]
) -> dict[str, object]:
    observed_ids = tuple(sorted(observed))
    applied_ids = tuple(sorted(applied))
    return {
        "experiment.observed.ids": observed_ids,
        "experiment.applied.ids": applied_ids,
        "experiment.applied.treatments": tuple(
            applied[item] for item in applied_ids
        ),
    }


class QueueSpanExporter(SpanExporter):
    """Export compact span evidence to a multiprocessing-compatible queue."""

    def __init__(self, sink: Queue) -> None:
        self._sink = sink

    def export(self, spans) -> SpanExportResult:  # type: ignore[no-untyped-def]
        for span in spans:
            context = span.get_span_context()
            parent_span_id = span.parent.span_id if span.parent is not None else 0
            self._sink.put(
                {
                    "service": span.resource.attributes.get("service.name"),
                    "name": span.name,
                    "trace_id": context.trace_id,
                    "span_id": context.span_id,
                    "parent_span_id": parent_span_id,
                    "attributes": dict(span.attributes or {}),
                }
            )
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def build_tracer(service_name: str, sink: Queue):
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(SimpleSpanProcessor(QueueSpanExporter(sink)))
    return provider, provider.get_tracer("agent_experiment_context.otel_http")


def _headers_from_message(headers) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return {key.lower(): value for key, value in headers.items()}


def _post_json(url: str, payload: dict[str, str], headers: Mapping[str, str]) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json", **dict(headers)},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _specialist_result(
    request: str, evidence: ExperimentEvidence
) -> tuple[str, str]:
    mode = dict(evidence.local_behaviors).get(SPECIALIST_EXPERIMENT, "control")
    if mode == "concise":
        return f"specialist: {request.strip().lower()}", mode
    if mode == "structured":
        return f"specialist[structured]::request={request.strip().lower()}", mode
    return legacy_specialist_answer(request), "control"


def run_specialist_server(
    host: str,
    port: int,
    telemetry_sink: Queue,
    ready: Event,
) -> None:
    provider, tracer = build_tracer("shared-specialist", telemetry_sink)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib HTTP handler contract
            length = int(self.headers.get("content-length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            extracted = PROPAGATOR.extract(carrier=_headers_from_message(self.headers))

            with tracer.start_as_current_span(
                "shared-specialist.request",
                context=extracted,
                kind=SpanKind.SERVER,
            ) as span:
                observed = wire_allocations(extracted)
                evidence = _evaluate("shared-specialist", observed)
                applied = _materialized_allocations(evidence)
                result, mode = _specialist_result(
                    str(body.get("request", "")), evidence
                )
                for key, value in _trace_attributes(observed, applied).items():
                    span.set_attribute(key, value)
                span.set_attribute("specialist.mode", mode)
                trace_id = get_current_span().get_span_context().trace_id
                response = {"result": result, "trace_id": trace_id}

            encoded = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return None

    server = ThreadingHTTPServer((host, port), Handler)
    ready.set()
    try:
        server.serve_forever()
    finally:
        provider.shutdown()
        server.server_close()


def run_orchestrator_server(
    component_id: str,
    host: str,
    port: int,
    specialist_url: str,
    telemetry_sink: Queue,
    ready: Event,
) -> None:
    provider, tracer = build_tracer(component_id, telemetry_sink)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib HTTP handler contract
            length = int(self.headers.get("content-length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            extracted = PROPAGATOR.extract(carrier=_headers_from_message(self.headers))

            with tracer.start_as_current_span(
                f"{component_id}.request",
                context=extracted,
                kind=SpanKind.SERVER,
            ) as span:
                observed = wire_allocations(extracted)
                evidence = _evaluate(component_id, observed)
                applied = _materialized_allocations(evidence)
                request_text = str(body.get("request", ""))
                route = dict(evidence.local_behaviors).get(
                    ORCHESTRATOR_A_EXPERIMENT, "control"
                )
                if component_id == "orchestrator-a" and route == "normalized":
                    request_text = " ".join(request_text.split())

                for key, value in _trace_attributes(observed, applied).items():
                    span.set_attribute(key, value)
                span.set_attribute("orchestrator.route", route)

                downstream_headers: dict[str, str] = {}
                propagation_context = set_span_in_context(span, extracted)
                PROPAGATOR.inject(downstream_headers, context=propagation_context)
                downstream = _post_json(
                    specialist_url,
                    {"request": request_text},
                    downstream_headers,
                )
                response = {
                    "result": downstream["result"],
                    "trace_id": downstream["trace_id"],
                }

            encoded = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return None

    server = ThreadingHTTPServer((host, port), Handler)
    ready.set()
    try:
        server.serve_forever()
    finally:
        provider.shutdown()
        server.server_close()
