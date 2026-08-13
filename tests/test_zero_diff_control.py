from agent_experiment_context import (
    ExperimentAllocationContext,
    InMemoryTraceSink,
    OrchestratorA,
    SharedSpecialist,
    legacy_specialist_answer,
)


def test_no_allocations_preserve_legacy_specialist_semantics() -> None:
    traces = InMemoryTraceSink()
    specialist = SharedSpecialist(traces)
    orchestrator = OrchestratorA(specialist, traces)
    context = ExperimentAllocationContext.empty("control-1")

    corpus = [
        "Explain my invoice",
        "  Keep original whitespace  ",
        "UPPER case stays",
    ]

    for request in corpus:
        assert orchestrator.run(request, context) == legacy_specialist_answer(request)
