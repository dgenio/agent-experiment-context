from __future__ import annotations

from dataclasses import dataclass

from .context import ExperimentAllocationContext
from .tracing import InMemoryTraceSink, TraceEvent


SPECIALIST_EXPERIMENT = "specialist-response-mode-v1"
ORCHESTRATOR_A_EXPERIMENT = "orchestrator-a-routing-v1"


@dataclass(slots=True)
class SharedSpecialist:
    trace_sink: InMemoryTraceSink
    component_id: str = "shared-specialist"

    def answer(self, request: str, context: ExperimentAllocationContext) -> str:
        owned = context.for_owner(self.component_id)
        allocation = context.get_owned(self.component_id, SPECIALIST_EXPERIMENT)

        mode = allocation.arm if allocation is not None else "control"
        if mode == "concise":
            result = f"specialist: {request.strip().lower()}"
        elif mode == "structured":
            result = f"specialist[structured]::request={request.strip().lower()}"
        else:
            # This is the legacy/control behaviour. No experiment configuration
            # must preserve this exact semantic path.
            result = legacy_specialist_answer(request)

        self.trace_sink.emit(
            TraceEvent(
                execution_id=context.execution_id,
                component=self.component_id,
                event="specialist.answer",
                observed_allocations=tuple(sorted(context.allocations)),
                applied_allocations=tuple(sorted(owned)),
                attributes={"mode": mode},
            )
        )
        return result


def legacy_specialist_answer(request: str) -> str:
    """Behaviour that existed before experiment-context support."""

    return f"specialist: {request.strip()}"


@dataclass(slots=True)
class OrchestratorA:
    specialist: SharedSpecialist
    trace_sink: InMemoryTraceSink
    component_id: str = "orchestrator-a"

    def run(self, request: str, context: ExperimentAllocationContext) -> str:
        owned = context.for_owner(self.component_id)
        allocation = context.get_owned(self.component_id, ORCHESTRATOR_A_EXPERIMENT)

        route = allocation.arm if allocation is not None else "control"
        specialist_request = request
        if route == "normalized":
            specialist_request = " ".join(request.split())

        self.trace_sink.emit(
            TraceEvent(
                execution_id=context.execution_id,
                component=self.component_id,
                event="orchestrator.route",
                observed_allocations=tuple(sorted(context.allocations)),
                applied_allocations=tuple(sorted(owned)),
                attributes={"route": route},
            )
        )
        return self.specialist.answer(specialist_request, context)


@dataclass(slots=True)
class OrchestratorB:
    specialist: SharedSpecialist
    trace_sink: InMemoryTraceSink
    component_id: str = "orchestrator-b"

    def run(self, request: str, context: ExperimentAllocationContext) -> str:
        # Orchestrator B deliberately owns no experiment in this reference flow.
        # It can observe the execution context for attribution without applying
        # allocations owned by Orchestrator A or the shared specialist.
        owned = context.for_owner(self.component_id)
        self.trace_sink.emit(
            TraceEvent(
                execution_id=context.execution_id,
                component=self.component_id,
                event="orchestrator.route",
                observed_allocations=tuple(sorted(context.allocations)),
                applied_allocations=tuple(sorted(owned)),
                attributes={"route": "control"},
            )
        )
        return self.specialist.answer(request, context)
