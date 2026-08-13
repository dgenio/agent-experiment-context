from agent_experiment_context import (
    ORCHESTRATOR_A_EXPERIMENT,
    SPECIALIST_EXPERIMENT,
    ExperimentAllocation,
    ExperimentAllocationContext,
    InMemoryTraceSink,
    OrchestratorA,
    OrchestratorB,
    SharedSpecialist,
)


def build_context() -> ExperimentAllocationContext:
    return (
        ExperimentAllocationContext.empty("e2e-1")
        .with_allocation(
            ExperimentAllocation(
                ORCHESTRATOR_A_EXPERIMENT,
                "normalized",
                "orchestrator-a",
                "session:123",
            )
        )
        .with_allocation(
            ExperimentAllocation(
                SPECIALIST_EXPERIMENT,
                "structured",
                "shared-specialist",
                "session:123",
            )
        )
    )


def test_shared_specialist_materializes_only_its_own_allocation() -> None:
    traces = InMemoryTraceSink()
    specialist = SharedSpecialist(traces)
    orchestrator_a = OrchestratorA(specialist, traces)
    orchestrator_b = OrchestratorB(specialist, traces)
    context = build_context()

    result_a = orchestrator_a.run("  Explain   invoices  ", context)
    result_b = orchestrator_b.run("Explain invoices", context)

    assert result_a == "specialist[structured]::request=explain invoices"
    assert result_b == "specialist[structured]::request=explain invoices"

    events = traces.for_execution("e2e-1")
    a_route = next(e for e in events if e.component == "orchestrator-a")
    b_route = next(e for e in events if e.component == "orchestrator-b")
    specialist_events = [e for e in events if e.component == "shared-specialist"]

    assert a_route.applied_allocations == (ORCHESTRATOR_A_EXPERIMENT,)
    assert b_route.applied_allocations == ()
    assert all(e.applied_allocations == (SPECIALIST_EXPERIMENT,) for e in specialist_events)


def test_trace_keeps_allocation_attribution_across_call_graph() -> None:
    traces = InMemoryTraceSink()
    specialist = SharedSpecialist(traces)
    OrchestratorA(specialist, traces).run("hello", build_context())

    events = traces.for_execution("e2e-1")
    expected = tuple(sorted((ORCHESTRATOR_A_EXPERIMENT, SPECIALIST_EXPERIMENT)))
    assert events
    assert all(event.observed_allocations == expected for event in events)
