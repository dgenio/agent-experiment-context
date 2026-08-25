from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from a2a.client.base_client import BaseClient
from a2a.client.client import ClientConfig
from a2a.client.client_factory import ClientFactory
from a2a.server.events.in_memory_queue_manager import InMemoryQueueManager
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentExtension,
    AgentInterface,
    Message,
    Part,
    Role,
    SendMessageRequest,
    TaskState,
)
from a2a.utils import TransportProtocol
from starlette.applications import Starlette

from agent_experiment_context import (
    EXTENSION_URI,
    ExperimentAgentExecutor,
    ExperimentEnvelope,
    LocalExperimentRegistry,
    build_client_call_context,
    build_request_metadata,
)


@dataclass
class Endpoint:
    client: BaseClient
    httpx_client: httpx.AsyncClient
    executor: ExperimentAgentExecutor
    app: Starlette
    card: AgentCard
    base_url: str

    async def close(self) -> None:
        await self.client.close()
        if not self.httpx_client.is_closed:
            await self.httpx_client.aclose()


def _agent_card(name: str, base_url: str) -> AgentCard:
    return AgentCard(
        name=name,
        description=f"{name} for the experiment-context falsification suite",
        version="0.1.0",
        capabilities=AgentCapabilities(
            streaming=True,
            push_notifications=False,
            extensions=[
                AgentExtension(
                    uri=EXTENSION_URI,
                    description="Scoped experiment-allocation context",
                )
            ],
        ),
        skills=[],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        supported_interfaces=[
            AgentInterface(
                protocol_binding=TransportProtocol.JSONRPC,
                url=base_url,
            )
        ],
    )


def _endpoint(
    name: str,
    registry: LocalExperimentRegistry,
    *,
    forwarder=None,
) -> Endpoint:
    base_url = f"http://{name.lower().replace(' ', '-')}"
    card = _agent_card(name, base_url)
    executor = ExperimentAgentExecutor(registry, forwarder=forwarder)
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=card,
        queue_manager=InMemoryQueueManager(),
    )
    app = Starlette(
        routes=[
            *create_agent_card_routes(agent_card=card, card_url="/"),
            *create_jsonrpc_routes(request_handler=handler, rpc_url="/"),
        ]
    )
    httpx_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=base_url,
    )
    client = ClientFactory(
        config=ClientConfig(
            httpx_client=httpx_client,
            supported_protocol_bindings=[TransportProtocol.JSONRPC],
        )
    ).create(card)
    return Endpoint(
        client=client,
        httpx_client=httpx_client,
        executor=executor,
        app=app,
        card=card,
        base_url=base_url,
    )


def _additional_client(endpoint: Endpoint) -> tuple[BaseClient, httpx.AsyncClient]:
    httpx_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=endpoint.app),
        base_url=endpoint.base_url,
    )
    client = ClientFactory(
        config=ClientConfig(
            httpx_client=httpx_client,
            supported_protocol_bindings=[TransportProtocol.JSONRPC],
        )
    ).create(endpoint.card)
    return client, httpx_client


async def _send(
    client: BaseClient,
    *,
    text: str,
    envelope: ExperimentEnvelope | None = None,
    activate_extension: bool = True,
    streaming: bool = False,
    task_id: str | None = None,
    extra_wire_fields=None,
) -> list[Any]:
    client._config.streaming = streaming
    message = Message(
        role=Role.ROLE_USER,
        message_id=str(uuid.uuid4()),
        parts=[Part(text=text)],
    )
    if task_id is not None:
        message.task_id = task_id

    request = SendMessageRequest(message=message)
    if envelope is not None:
        request.metadata.CopyFrom(
            build_request_metadata(
                envelope,
                extra_wire_fields=extra_wire_fields,
            )
        )

    kwargs: dict[str, Any] = {"request": request}
    if activate_extension:
        kwargs["context"] = build_client_call_context()

    return [event async for event in client.send_message(**kwargs)]


def _direct_payload(events: list[Any]) -> dict[str, Any]:
    assert len(events) == 1
    event = events[0]
    assert event.HasField("message")
    return json.loads(event.message.parts[0].text)


def _last_status_payload(events: list[Any]) -> dict[str, Any]:
    status_updates = [
        event.status_update for event in events if event.HasField("status_update")
    ]
    assert status_updates
    message = status_updates[-1].status.message
    assert message.parts
    return json.loads(message.parts[0].text)


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_two_allocations_cross_a2a_boundary(streaming: bool) -> None:
    endpoint = _endpoint(
        "Shared Specialist",
        LocalExperimentRegistry(
            "shared-specialist",
            {
                "specialist-response-mode-v1": {
                    "structured": "structured-response",
                }
            },
        ),
    )
    try:
        envelope = ExperimentEnvelope.from_pairs(
            ("orchestrator-a-routing-v1", "normalized"),
            ("specialist-response-mode-v1", "structured"),
        )

        payload = _direct_payload(
            await _send(
                endpoint.client,
                text="run",
                envelope=envelope,
                streaming=streaming,
            )
        )

        assert payload["observed"] == [
            {
                "experiment_id": "orchestrator-a-routing-v1",
                "treatment": "normalized",
            },
            {
                "experiment_id": "specialist-response-mode-v1",
                "treatment": "structured",
            },
        ]
        assert payload["materialized"] == [
            {
                "experiment_id": "specialist-response-mode-v1",
                "treatment": "structured",
            }
        ]
        assert payload["local_behaviors"] == {
            "specialist-response-mode-v1": "structured-response"
        }
        assert payload["default_behavior"] == "control"
    finally:
        await endpoint.close()


@pytest.mark.asyncio
async def test_extension_activation_is_required_for_materialization() -> None:
    endpoint = _endpoint(
        "Shared Specialist",
        LocalExperimentRegistry(
            "shared-specialist",
            {"specialist-mode-v1": {"structured": "structured-response"}},
        ),
    )
    try:
        envelope = ExperimentEnvelope.from_pairs(("specialist-mode-v1", "structured"))

        payload = _direct_payload(
            await _send(
                endpoint.client,
                text="run",
                envelope=envelope,
                activate_extension=False,
            )
        )

        assert payload["observed"] == []
        assert payload["materialized"] == []
        assert payload["local_behaviors"] == {}
        assert payload["default_behavior"] == "control"
    finally:
        await endpoint.close()


@pytest.mark.asyncio
async def test_forged_owner_and_authority_fields_cannot_create_ownership() -> None:
    endpoint = _endpoint(
        "Shared Specialist",
        LocalExperimentRegistry(
            "shared-specialist",
            {"specialist-mode-v1": {"structured": "structured-response"}},
        ),
    )
    try:
        envelope = ExperimentEnvelope.from_pairs(("not-owned-v1", "treatment"))
        payload = _direct_payload(
            await _send(
                endpoint.client,
                text="run",
                envelope=envelope,
                extra_wire_fields={
                    ("not-owned-v1", "treatment"): {
                        "owner": "shared-specialist",
                        "authorized": True,
                        "scope": "all",
                    }
                },
            )
        )

        assert payload["observed"] == [
            {"experiment_id": "not-owned-v1", "treatment": "treatment"}
        ]
        assert payload["materialized"] == []
        assert payload["ignored"] == [
            {"experiment_id": "not-owned-v1", "treatment": "treatment"}
        ]
        assert payload["local_behaviors"] == {}
        assert payload["default_behavior"] == "control"
    finally:
        await endpoint.close()


@pytest.mark.asyncio
async def test_shared_specialist_isolates_two_orchestrators_concurrently() -> None:
    endpoint_a = _endpoint(
        "Shared Specialist A Client",
        LocalExperimentRegistry(
            "shared-specialist",
            {
                "specialist-mode-v1": {
                    "structured": "structured-response",
                    "compact": "compact-response",
                }
            },
        ),
    )
    client_b, httpx_client_b = _additional_client(endpoint_a)
    try:
        envelope_a = ExperimentEnvelope.from_pairs(
            ("orchestrator-a-v1", "treatment-a"),
            ("specialist-mode-v1", "structured"),
        )
        envelope_b = ExperimentEnvelope.from_pairs(
            ("orchestrator-b-v1", "treatment-b"),
            ("specialist-mode-v1", "compact"),
        )

        events_a, events_b = await asyncio.gather(
            _send(endpoint_a.client, text="from-a", envelope=envelope_a),
            _send(client_b, text="from-b", envelope=envelope_b),
        )
        payload_a = _direct_payload(events_a)
        payload_b = _direct_payload(events_b)

        assert payload_a["local_behaviors"] == {
            "specialist-mode-v1": "structured-response"
        }
        assert payload_b["local_behaviors"] == {
            "specialist-mode-v1": "compact-response"
        }
        assert payload_a["observed"] != payload_b["observed"]
    finally:
        await client_b.close()
        if not httpx_client_b.is_closed:
            await httpx_client_b.aclose()
        await endpoint_a.close()


@pytest.mark.asyncio
async def test_no_allocation_request_after_treatment_returns_to_control() -> None:
    endpoint = _endpoint(
        "Shared Specialist",
        LocalExperimentRegistry(
            "shared-specialist",
            {"specialist-mode-v1": {"structured": "structured-response"}},
        ),
    )
    try:
        treatment = ExperimentEnvelope.from_pairs(
            ("specialist-mode-v1", "structured")
        )
        treatment_payload = _direct_payload(
            await _send(endpoint.client, text="treatment", envelope=treatment)
        )
        control_payload = _direct_payload(
            await _send(endpoint.client, text="control", envelope=None)
        )

        assert treatment_payload["local_behaviors"] == {
            "specialist-mode-v1": "structured-response"
        }
        assert control_payload["observed"] == []
        assert control_payload["materialized"] == []
        assert control_payload["local_behaviors"] == {}
        assert control_payload["default_behavior"] == "control"
    finally:
        await endpoint.close()


@pytest.mark.asyncio
async def test_task_continuation_requires_explicit_context_resend() -> None:
    endpoint = _endpoint(
        "Lifecycle Specialist",
        LocalExperimentRegistry(
            "lifecycle-specialist",
            {"specialist-mode-v1": {"structured": "structured-response"}},
        ),
    )
    try:
        envelope = ExperimentEnvelope.from_pairs(("specialist-mode-v1", "structured"))

        first_events = await _send(
            endpoint.client,
            text="task:start",
            envelope=envelope,
            streaming=True,
        )
        task_events = [event.task for event in first_events if event.HasField("task")]
        assert task_events
        task_id = task_events[0].id
        assert _last_status_payload(first_events)["local_behaviors"] == {
            "specialist-mode-v1": "structured-response"
        }

        without_context = await _send(
            endpoint.client,
            text="task:continue",
            envelope=None,
            activate_extension=False,
            streaming=True,
            task_id=task_id,
        )
        without_context_payload = _last_status_payload(without_context)
        assert without_context_payload["local_behaviors"] == {}
        assert without_context_payload["default_behavior"] == "control"

        with_context_again = await _send(
            endpoint.client,
            text="task:complete",
            envelope=envelope,
            streaming=True,
            task_id=task_id,
        )
        completed_updates = [
            event.status_update
            for event in with_context_again
            if event.HasField("status_update")
        ]
        assert completed_updates[-1].status.state == TaskState.TASK_STATE_COMPLETED
        assert _last_status_payload(with_context_again)["local_behaviors"] == {
            "specialist-mode-v1": "structured-response"
        }
    finally:
        await endpoint.close()


@pytest.mark.asyncio
async def test_second_a2a_hop_forwards_allocations_without_transitive_ownership(
) -> None:
    second = _endpoint(
        "Second Specialist",
        LocalExperimentRegistry(
            "second-specialist",
            {"second-hop-mode-v1": {"v2": "second-hop-v2"}},
        ),
    )

    async def forwarder(envelope: ExperimentEnvelope) -> dict[str, Any]:
        return _direct_payload(
            await _send(
                second.client,
                text="forwarded",
                envelope=envelope,
                streaming=False,
            )
        )

    shared = _endpoint(
        "Shared Specialist",
        LocalExperimentRegistry(
            "shared-specialist",
            {"specialist-mode-v1": {"structured": "structured-response"}},
        ),
        forwarder=forwarder,
    )

    try:
        envelope = ExperimentEnvelope.from_pairs(
            ("orchestrator-routing-v1", "normalized"),
            ("specialist-mode-v1", "structured"),
            ("second-hop-mode-v1", "v2"),
        )

        payload = _direct_payload(
            await _send(shared.client, text="run-chain", envelope=envelope)
        )

        assert payload["materialized"] == [
            {
                "experiment_id": "specialist-mode-v1",
                "treatment": "structured",
            }
        ]
        assert payload["local_behaviors"] == {
            "specialist-mode-v1": "structured-response"
        }
        downstream = payload["downstream"]
        assert downstream["materialized"] == [
            {"experiment_id": "second-hop-mode-v1", "treatment": "v2"}
        ]
        assert downstream["ignored"] == [
            {
                "experiment_id": "orchestrator-routing-v1",
                "treatment": "normalized",
            },
            {
                "experiment_id": "specialist-mode-v1",
                "treatment": "structured",
            },
        ]
        assert downstream["local_behaviors"] == {
            "second-hop-mode-v1": "second-hop-v2"
        }
    finally:
        await shared.close()
        await second.close()
