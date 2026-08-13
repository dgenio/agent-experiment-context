from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TraceEvent:
    execution_id: str
    component: str
    event: str
    observed_allocations: tuple[str, ...] = ()
    applied_allocations: tuple[str, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)


class InMemoryTraceSink:
    """Tiny trace sink used by the reference implementation and tests."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)

    def for_execution(self, execution_id: str) -> list[TraceEvent]:
        return [event for event in self.events if event.execution_id == execution_id]
