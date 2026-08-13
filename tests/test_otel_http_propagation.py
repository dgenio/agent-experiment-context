from __future__ import annotations

import json
import multiprocessing as mp
import socket
import time
from contextlib import contextmanager
from queue import Empty
from urllib.request import Request, urlopen

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import set_span_in_context

from agent_experiment_context import (
    ORCHESTRATOR_A_EXPERIMENT,
    SPECIALIST_EXPERIMENT,
    legacy_specialist_answer,
)
from agent_experiment_context.otel_http import (
    PROPAGATOR,
    QueueSpanExporter,
    context_with_wire_allocations,
    run_orchestrator_server,
    run_specialist_server,
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _topology():
    ctx = mp.get_context("spawn")
    telemetry = ctx.Queue()
    processes = []

    specialist_port = _free_port()
    specialist_ready = ctx.Event()
    specialist = ctx.Process(
        target=run_specialist_server,
        args=("127.0.0.1", specialist_port, telemetry, specialist_ready),
    )
    specialist.start()
    processes.append(specialist)
    assert specialist_ready.wait(timeout=10)

    endpoints: dict[str, str] = {}
    for component_id in ("orchestrator-a", "orchestrator-b"):
        port = _free_port()
        ready = ctx.Event()
        process = ctx.Process(
            target=run_orchestrator_server,
            args=(
                component_id,
                "127.0.0.1",
                port,
                f"http://127.0.0.1:{specialist_port}/run",
                telemetry,
                ready,
            ),
        )
        process.start()
        processes.append(process)
        assert ready.wait(timeout=10)
        endpoints[component_id] = f"http://127.0.0.1:{port}/run"

    try:
        yield ctx, telemetry, endpoints
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.join(timeout=5)


def _request_with_allocations(
    telemetry,
    url: str,
    request_text: str,
    allocations: dict[str, str],
    extra_baggage: dict[str, str] | None = None,
) -> tuple[dict, dict[str, str], int]:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(QueueSpanExporter(telemetry)))
    tracer = provider.get_tracer("test-client")

    context = context_with_wire_allocations(allocations)
    if extra_baggage:
        from opentelemetry import baggage

        for key, value in extra_baggage.items():
            context = baggage.set_baggage(key, value, context=context)

    headers: dict[str, str] = {"content-type": "application/json"}
    with tracer.start_as_current_span("client.request", context=context) as span:
        propagation_context = set_span_in_context(span, context)
        PROPAGATOR.inject(headers, context=propagation_context)
        trace_id = span.get_span_context().trace_id
        request = Request(
            url,
            data=json.dumps({"request": request_text}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=10) as response:  # noqa: S310 - local test service only
            payload = json.loads(response.read().decode("utf-8"))

    provider.shutdown()
    return payload, headers, trace_id


def _collect_trace(telemetry, trace_id: int, expected: int = 3) -> list[dict]:
    deadline = time.monotonic() + 5
    events: list[dict] = []
    while time.monotonic() < deadline and len(events) < expected:
        try:
            item = telemetry.get(timeout=0.2)
        except Empty:
            continue
        if item["trace_id"] == trace_id:
            events.append(item)
    return events


def _by_service(events: list[dict], service: str) -> dict:
    return next(event for event in events if event["service"] == service)


def test_allocations_cross_process_boundary_with_scoped_materialization() -> None:
    with _topology() as (_, telemetry, endpoints):
        allocations = {
            ORCHESTRATOR_A_EXPERIMENT: "normalized",
            SPECIALIST_EXPERIMENT: "structured",
        }
        payload, headers, trace_id = _request_with_allocations(
            telemetry,
            endpoints["orchestrator-a"],
            "  Explain   invoices  ",
            allocations,
        )

        assert payload["result"] == "specialist[structured]::request=explain invoices"
        assert payload["trace_id"] == trace_id
        assert "user:" not in headers.get("baggage", "")
        assert "session:" not in headers.get("baggage", "")

        events = _collect_trace(telemetry, trace_id)
        assert len(events) == 3
        orchestrator = _by_service(events, "orchestrator-a")
        specialist = _by_service(events, "shared-specialist")

        assert orchestrator["attributes"]["experiment.applied.ids"] == (
            ORCHESTRATOR_A_EXPERIMENT,
        )
        assert specialist["attributes"]["experiment.applied.ids"] == (
            SPECIALIST_EXPERIMENT,
        )
        assert specialist["parent_span_id"] == orchestrator["span_id"]


def test_shared_specialist_still_scopes_when_called_by_orchestrator_b() -> None:
    with _topology() as (_, telemetry, endpoints):
        allocations = {
            ORCHESTRATOR_A_EXPERIMENT: "normalized",
            SPECIALIST_EXPERIMENT: "structured",
        }
        payload, _, trace_id = _request_with_allocations(
            telemetry,
            endpoints["orchestrator-b"],
            "Explain invoices",
            allocations,
        )
        assert payload["result"] == "specialist[structured]::request=explain invoices"

        events = _collect_trace(telemetry, trace_id)
        orchestrator = _by_service(events, "orchestrator-b")
        specialist = _by_service(events, "shared-specialist")
        assert orchestrator["attributes"]["experiment.applied.ids"] == ()
        assert specialist["attributes"]["experiment.applied.ids"] == (
            SPECIALIST_EXPERIMENT,
        )


def test_unknown_and_forged_metadata_cannot_force_materialization() -> None:
    with _topology() as (_, telemetry, endpoints):
        payload, _, trace_id = _request_with_allocations(
            telemetry,
            endpoints["orchestrator-b"],
            "Hello",
            {"unknown-experiment": "structured"},
            extra_baggage={
                f"exp.owner.{SPECIALIST_EXPERIMENT}": "shared-specialist",
            },
        )
        assert payload["result"] == legacy_specialist_answer("Hello")

        events = _collect_trace(telemetry, trace_id)
        specialist = _by_service(events, "shared-specialist")
        assert specialist["attributes"]["experiment.applied.ids"] == ()
        assert specialist["attributes"]["experiment.observed.ids"] == (
            "unknown-experiment",
        )


def test_no_allocation_preserves_legacy_control_across_http() -> None:
    with _topology() as (_, telemetry, endpoints):
        corpus = [
            "Explain my invoice",
            "  Keep original whitespace  ",
            "UPPER case stays",
        ]
        for request_text in corpus:
            payload, _, _ = _request_with_allocations(
                telemetry,
                endpoints["orchestrator-a"],
                request_text,
                {},
            )
            assert payload["result"] == legacy_specialist_answer(request_text)
