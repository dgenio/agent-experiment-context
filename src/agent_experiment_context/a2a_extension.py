"""A deliberately small A2A extension experiment for scoped allocations.

The module keeps the wire model intentionally narrower than the in-process model:
only ``experiment_id`` and ``treatment`` cross the boundary. Ownership,
authorization, provenance, assignment-unit identity, and exposure semantics remain
local concerns.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from a2a.client.client import ClientCallContext
from a2a.client.service_parameters import (
    ServiceParametersFactory,
    with_a2a_extensions,
)
from a2a.server.agent_execution import RequestContext
from google.protobuf.struct_pb2 import Struct

EXTENSION_URI = (
    "https://github.com/dgenio/agent-experiment-context/"
    "blob/main/docs/a2a-experiment-allocation-extension-v1.md"
)


@dataclass(frozen=True, slots=True)
class ExperimentAllocation:
    """One already-resolved experiment allocation."""

    experiment_id: str
    treatment: str

    def to_wire(self) -> dict[str, str]:
        return {
            "experiment_id": self.experiment_id,
            "treatment": self.treatment,
        }


@dataclass(frozen=True, slots=True)
class ExperimentEnvelope:
    """Execution-scoped set of experiment allocations."""

    allocations: tuple[ExperimentAllocation, ...] = ()

    @classmethod
    def from_pairs(cls, *pairs: tuple[str, str]) -> ExperimentEnvelope:
        return cls(tuple(ExperimentAllocation(*pair) for pair in pairs))

    def to_wire(self) -> dict[str, list[dict[str, str]]]:
        return {
            "allocations": [
                allocation.to_wire() for allocation in self.allocations
            ]
        }


@dataclass(frozen=True, slots=True)
class ExperimentEvidence:
    """What one component observed and materialized for one request."""

    component_id: str
    observed: tuple[ExperimentAllocation, ...]
    materialized: tuple[ExperimentAllocation, ...]
    ignored: tuple[ExperimentAllocation, ...]
    effective_behavior: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "observed": [allocation.to_wire() for allocation in self.observed],
            "materialized": [
                allocation.to_wire() for allocation in self.materialized
            ],
            "ignored": [allocation.to_wire() for allocation in self.ignored],
            "effective_behavior": self.effective_behavior,
        }


class LocalExperimentRegistry:
    """Trusted local mapping from experiment allocations to local behavior.

    A wire payload never declares ownership. The receiving component decides which
    experiment identifiers it recognizes and which treatments can materialize.
    """

    def __init__(
        self,
        component_id: str,
        experiments: Mapping[str, Mapping[str, str]],
        *,
        default_behavior: str = "control",
    ) -> None:
        self.component_id = component_id
        self._experiments = {
            experiment_id: dict(treatments)
            for experiment_id, treatments in experiments.items()
        }
        self._default_behavior = default_behavior

    def evaluate(self, envelope: ExperimentEnvelope) -> ExperimentEvidence:
        materialized: list[ExperimentAllocation] = []
        ignored: list[ExperimentAllocation] = []
        behavior = self._default_behavior

        for allocation in envelope.allocations:
            treatments = self._experiments.get(allocation.experiment_id)
            if treatments is None or allocation.treatment not in treatments:
                ignored.append(allocation)
                continue

            materialized.append(allocation)
            behavior = treatments[allocation.treatment]

        return ExperimentEvidence(
            component_id=self.component_id,
            observed=envelope.allocations,
            materialized=tuple(materialized),
            ignored=tuple(ignored),
            effective_behavior=behavior,
        )


def build_request_metadata(
    envelope: ExperimentEnvelope,
    *,
    extra_wire_fields: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
) -> Struct:
    """Serialize the minimal allocation envelope into A2A request metadata.

    ``extra_wire_fields`` exists only for negative tests. It makes it possible to
    attach fields such as ``owner`` or ``authorized`` and prove that the decoder
    ignores them rather than treating them as trusted authority.
    """

    allocations: list[dict[str, Any]] = []
    extras = extra_wire_fields or {}
    for allocation in envelope.allocations:
        item: dict[str, Any] = allocation.to_wire()
        item.update(extras.get((allocation.experiment_id, allocation.treatment), {}))
        allocations.append(item)

    metadata = Struct()
    metadata.update({EXTENSION_URI: {"allocations": allocations}})
    return metadata


def build_client_call_context() -> ClientCallContext:
    """Activate the experiment-allocation extension for one A2A client call."""

    service_parameters = ServiceParametersFactory.create(
        [with_a2a_extensions([EXTENSION_URI])]
    )
    return ClientCallContext(service_parameters=service_parameters)


def decode_request_context(context: RequestContext) -> ExperimentEnvelope:
    """Decode an activated extension from an A2A ``RequestContext``.

    Metadata without extension activation is intentionally inert. Only the two
    minimal fields are accepted into the local model; authority-looking fields are
    dropped at the boundary.
    """

    if EXTENSION_URI not in context.requested_extensions:
        return ExperimentEnvelope()

    payload = context.metadata.get(EXTENSION_URI)
    if not isinstance(payload, dict):
        return ExperimentEnvelope()

    raw_allocations = payload.get("allocations")
    if not isinstance(raw_allocations, list):
        return ExperimentEnvelope()

    allocations: list[ExperimentAllocation] = []
    for raw in raw_allocations:
        if not isinstance(raw, dict):
            continue
        experiment_id = raw.get("experiment_id")
        treatment = raw.get("treatment")
        if not isinstance(experiment_id, str) or not experiment_id:
            continue
        if not isinstance(treatment, str) or not treatment:
            continue
        allocations.append(
            ExperimentAllocation(
                experiment_id=experiment_id,
                treatment=treatment,
            )
        )

    return ExperimentEnvelope(tuple(allocations))
