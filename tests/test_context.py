from agent_experiment_context import ExperimentAllocation, ExperimentAllocationContext


def test_component_only_resolves_allocations_it_owns() -> None:
    context = (
        ExperimentAllocationContext.empty("e-1")
        .with_allocation(ExperimentAllocation("exp-a", "B", "component-a", "user:1"))
        .with_allocation(ExperimentAllocation("exp-b", "A", "component-b", "user:1"))
    )

    assert set(context.for_owner("component-a")) == {"exp-a"}
    assert context.get_owned("component-a", "exp-b") is None
