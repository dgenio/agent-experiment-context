from types import SimpleNamespace

from google.protobuf.json_format import MessageToDict

from agent_experiment_context import (
    EXTENSION_URI,
    ExperimentEnvelope,
    LocalExperimentRegistry,
    build_request_metadata,
    decode_request_context,
)


def _context(*, activated: bool, metadata: dict) -> SimpleNamespace:
    return SimpleNamespace(
        requested_extensions={EXTENSION_URI} if activated else set(),
        metadata=metadata,
    )


def test_metadata_without_extension_activation_is_inert() -> None:
    envelope = ExperimentEnvelope.from_pairs(("specialist-mode-v1", "structured"))
    metadata = MessageToDict(build_request_metadata(envelope))

    decoded = decode_request_context(_context(activated=False, metadata=metadata))

    assert decoded.allocations == ()


def test_decoder_drops_authority_looking_fields() -> None:
    envelope = ExperimentEnvelope.from_pairs(("unknown-v1", "treatment"))
    metadata = MessageToDict(
        build_request_metadata(
            envelope,
            extra_wire_fields={
                ("unknown-v1", "treatment"): {
                    "owner": "shared-specialist",
                    "authorized": True,
                    "scope": "admin",
                }
            },
        )
    )

    decoded = decode_request_context(_context(activated=True, metadata=metadata))

    assert decoded == envelope
    assert decoded.allocations[0].to_wire() == {
        "experiment_id": "unknown-v1",
        "treatment": "treatment",
    }


def test_local_registry_is_the_materialization_boundary() -> None:
    registry = LocalExperimentRegistry(
        "shared-specialist",
        {
            "specialist-mode-v1": {
                "structured": "structured-response",
            }
        },
    )
    envelope = ExperimentEnvelope.from_pairs(
        ("orchestrator-routing-v1", "treatment-a"),
        ("specialist-mode-v1", "structured"),
    )

    evidence = registry.evaluate(envelope)

    assert evidence.observed == envelope.allocations
    assert evidence.materialized == (envelope.allocations[1],)
    assert evidence.ignored == (envelope.allocations[0],)
    assert evidence.effective_behavior == "structured-response"


def test_unknown_treatment_is_inert() -> None:
    registry = LocalExperimentRegistry(
        "shared-specialist",
        {"specialist-mode-v1": {"structured": "structured-response"}},
    )

    evidence = registry.evaluate(
        ExperimentEnvelope.from_pairs(("specialist-mode-v1", "does-not-exist"))
    )

    assert evidence.materialized == ()
    assert len(evidence.ignored) == 1
    assert evidence.effective_behavior == "control"
