from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ExperimentAllocation:
    """One stable experiment allocation carried by an execution."""

    experiment_id: str
    arm: str
    owner: str
    assignment_unit: str
    provenance: str = "upstream"


@dataclass(frozen=True, slots=True)
class ExperimentAllocationContext:
    """Execution-scoped, multi-dimensional experiment state.

    The context may contain allocations owned by several components. A component
    must only materialize allocations it explicitly owns.
    """

    execution_id: str
    allocations: Mapping[str, ExperimentAllocation] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "allocations", MappingProxyType(dict(self.allocations)))

    @classmethod
    def empty(cls, execution_id: str) -> "ExperimentAllocationContext":
        return cls(execution_id=execution_id)

    def with_allocation(self, allocation: ExperimentAllocation) -> "ExperimentAllocationContext":
        updated = dict(self.allocations)
        updated[allocation.experiment_id] = allocation
        return ExperimentAllocationContext(self.execution_id, updated)

    def for_owner(self, owner: str) -> Mapping[str, ExperimentAllocation]:
        return MappingProxyType(
            {
                experiment_id: allocation
                for experiment_id, allocation in self.allocations.items()
                if allocation.owner == owner
            }
        )

    def get_owned(self, owner: str, experiment_id: str) -> ExperimentAllocation | None:
        allocation = self.allocations.get(experiment_id)
        if allocation is None or allocation.owner != owner:
            return None
        return allocation
