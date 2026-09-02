from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from statistics import mean
from typing import Literal

Arm = Literal["control", "treatment"]


@dataclass(slots=True)
class TenantMemorySpecialist:
    """Tiny model of state shared by multiple assignment units in one tenant."""

    memory: dict[str, list[str]] = field(default_factory=dict)

    def answer(self, *, tenant_id: str, arm: Arm, request: str) -> str:
        tenant_memory = self.memory.setdefault(tenant_id, [])
        if arm == "treatment":
            tenant_memory.append(request.strip().lower())
        remembered = ",".join(tenant_memory) or "empty"
        return f"arm={arm};memory={remembered}"


@dataclass(frozen=True, slots=True)
class RoutedUnit:
    unit_id: str
    difficulty: Literal["easy", "hard"]
    baseline_outcome: float


def treatment_dependent_route(arm: Arm, unit: RoutedUnit) -> bool:
    return arm == "treatment" or unit.difficulty == "hard"


def observed_exposure_mean(arm: Arm, units: Iterable[RoutedUnit]) -> float:
    exposed = [
        unit.baseline_outcome
        for unit in units
        if treatment_dependent_route(arm, unit)
    ]
    if not exposed:
        raise ValueError("no exposed units")
    return mean(exposed)


def intent_to_treat_mean(units: Iterable[RoutedUnit]) -> float:
    outcomes = [unit.baseline_outcome for unit in units]
    if not outcomes:
        raise ValueError("no units")
    return mean(outcomes)


def interacting_outcome(*, experiment_a: Arm, experiment_b: Arm) -> float:
    if experiment_a == "control":
        return 0.0
    return 2.0 if experiment_b == "control" else -2.0


def effect_of_a_given_b(experiment_b: Arm) -> float:
    return (
        interacting_outcome(experiment_a="treatment", experiment_b=experiment_b)
        - interacting_outcome(experiment_a="control", experiment_b=experiment_b)
    )


def marginal_effect_of_a_when_b_balanced() -> float:
    return mean([effect_of_a_given_b("control"), effect_of_a_given_b("treatment")])
