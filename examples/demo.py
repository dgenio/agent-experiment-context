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


def main() -> None:
    traces = InMemoryTraceSink()
    specialist = SharedSpecialist(traces)
    orchestrator_a = OrchestratorA(specialist, traces)
    orchestrator_b = OrchestratorB(specialist, traces)

    context = (
        ExperimentAllocationContext.empty("execution-001")
        .with_allocation(
            ExperimentAllocation(
                experiment_id=ORCHESTRATOR_A_EXPERIMENT,
                arm="normalized",
                owner="orchestrator-a",
                assignment_unit="user:42",
                provenance="experiment-service",
            )
        )
        .with_allocation(
            ExperimentAllocation(
                experiment_id=SPECIALIST_EXPERIMENT,
                arm="structured",
                owner="shared-specialist",
                assignment_unit="user:42",
                provenance="experiment-service",
            )
        )
    )

    print("Orchestrator A:", orchestrator_a.run("  Explain   invoices  ", context))
    print("Orchestrator B:", orchestrator_b.run("Explain invoices", context))
    print("\nTrace attribution:")
    for event in traces.for_execution("execution-001"):
        print(
            f"- {event.component}: observed={event.observed_allocations}; "
            f"applied={event.applied_allocations}; attrs={event.attributes}"
        )


if __name__ == "__main__":
    main()
