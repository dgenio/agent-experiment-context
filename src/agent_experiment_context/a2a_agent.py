"""Tiny A2A agent used to falsify experiment-context assumptions."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from a2a.helpers.proto_helpers import new_task_from_user_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Message, Part, Role, TaskState

from .a2a_extension import (
    EXTENSION_URI,
    ExperimentEnvelope,
    LocalExperimentRegistry,
    decode_request_context,
)

Forwarder = Callable[[ExperimentEnvelope], Awaitable[dict[str, Any]]]


class ExperimentAgentExecutor(AgentExecutor):
    """Materialize only locally registered allocations and emit evidence."""

    def __init__(
        self,
        registry: LocalExperimentRegistry,
        *,
        forwarder: Forwarder | None = None,
    ) -> None:
        self._registry = registry
        self._forwarder = forwarder

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        envelope = decode_request_context(context)
        evidence = self._registry.evaluate(envelope)
        payload = evidence.to_dict()

        if self._forwarder is not None:
            payload["downstream"] = await self._forwarder(envelope)

        user_input = context.get_user_input()
        if user_input.startswith("task:"):
            await self._execute_task(context, event_queue, payload, user_input)
            return

        await event_queue.enqueue_event(
            Message(
                role=Role.ROLE_AGENT,
                message_id=str(uuid.uuid4()),
                parts=[Part(text=json.dumps(payload, sort_keys=True))],
                extensions=(
                    [EXTENSION_URI]
                    if EXTENSION_URI in context.requested_extensions
                    else []
                ),
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancellation is not part of this experiment")

    async def _execute_task(
        self,
        context: RequestContext,
        event_queue: EventQueue,
        payload: dict[str, Any],
        user_input: str,
    ) -> None:
        task = context.current_task
        if task is None:
            if context.message is None:
                return
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        message = updater.new_agent_message(
            [Part(text=json.dumps(payload, sort_keys=True))]
        )

        if user_input == "task:complete":
            await updater.update_status(TaskState.TASK_STATE_COMPLETED, message=message)
            return

        await updater.update_status(
            TaskState.TASK_STATE_INPUT_REQUIRED,
            message=message,
        )
