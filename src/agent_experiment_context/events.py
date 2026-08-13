from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class ExperimentEventType(StrEnum):
    ASSIGNED = "assigned"
    OBSERVED = "observed"
    MATERIALIZED = "materialized"
    EXPOSED = "exposed"


@dataclass(frozen=True, slots=True)
class ExperimentEvent:
    event_type: ExperimentEventType
    experiment_id: str
    arm: str
    execution_id: str
    component_id: str
    event_time: float
    reason: str


class ExperimentEventRecorder:
    """Append-only experiment lifecycle evidence."""

    def __init__(self) -> None:
        self.events: list[ExperimentEvent] = []

    def record(self, event_type: ExperimentEventType, *, experiment_id: str, arm: str, execution_id: str, component_id: str, event_time: float, reason: str) -> ExperimentEvent:
        event = ExperimentEvent(event_type, experiment_id, arm, execution_id, component_id, event_time, reason)
        self.events.append(event)
        return event

    def of_type(self, event_type: ExperimentEventType) -> list[ExperimentEvent]:
        return [event for event in self.events if event.event_type == event_type]

    def first_exposures(self) -> list[ExperimentEvent]:
        """First raw exposure per execution/component/experiment, not per user."""
        seen: set[tuple[str, str, str]] = set()
        result: list[ExperimentEvent] = []
        for event in self.of_type(ExperimentEventType.EXPOSED):
            key = (event.execution_id, event.component_id, event.experiment_id)
            if key not in seen:
                seen.add(key)
                result.append(event)
        return result

    def extend(self, events: Iterable[ExperimentEvent]) -> None:
        self.events.extend(events)
