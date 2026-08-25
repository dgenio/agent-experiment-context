# Issue #7 — A2A extension transport experiment

## Status

**PASS — no new upstream A2A issue required for this bounded use case.**

The final experiment ran against `a2a-sdk[grpc,http-server]==1.1.2`, the latest A2A Python SDK release available from PyPI in CI at the time of the experiment. CI is green on Python 3.11 and 3.12: Ruff passes and all 12 tests pass on both interpreters.

## Research question

Can the current A2A extension machinery carry a minimal multi-allocation experiment envelope across agent boundaries while preserving local ownership/materialization, request isolation, and the distinction between propagated context and authority?

**Answer:** yes for the scenarios exercised here. The existing A2A service-parameter, request-metadata, and extension surfaces are sufficient; the experiment did not uncover a current protocol or SDK gap that justifies a new upstream issue.

## Validated implementation

- `a2a-sdk[grpc,http-server]==1.1.2`
- JSON-RPC transport through the official A2A client and server routes
- `A2A-Extensions` activation via `ServiceParametersFactory` / `with_a2a_extensions`
- allocation payload stored in `SendMessageRequest.metadata`
- `RequestContext.requested_extensions` gates decoding
- `RequestContext.metadata` carries the extension payload to the executor
- trusted local registry maps only recognized `(experiment_id, treatment)` pairs to behavior
- wire representation contains only `experiment_id` + `treatment`

## Evidence

| Scenario | Observed result |
| --- | --- |
| Two allocations on one call | receiver observes both and materializes only its locally registered experiment |
| Blocking + streaming | same allocation semantics in both modes |
| Metadata without extension activation | inert; default/control behavior remains unchanged |
| Unknown experiment/treatment | observed but not materialized; default/control remains active |
| Forged `owner` / `authorized` / `scope` fields | decoder discards them; they cannot create local ownership or authority |
| Two concurrent callers | each request keeps its own allocations and local behavior; no cross-request leakage observed |
| Treatment followed by no-allocation request | second request returns to control |
| Same task, continuation without resend | continuation sees no allocation and returns to control |
| Same task, continuation with resend | allocation materializes again |
| Second A2A hop | same minimal envelope can be forwarded; each specialist materializes only its locally registered experiment |

The task-continuation result is particularly useful: the carrier tested here is **request-scoped**, not task-persistent. If an allocation is intended to remain active on a later A2A request for the same task, the client must resend it. That observation should not be generalized into a claim that the originating experimentation system must assign per request; it only describes this transport boundary.

## Historical finding while falsifying the hypothesis

The first integration run used `a2a-sdk==1.0.0`. Unit decoding worked, but real A2A calls arrived with nested request metadata exposed as raw protobuf `Value` objects, so the extension payload could not be consumed as the normal Python dict/list shape expected by the decoder.

Repository archaeology showed this was already a known/fixed SDK defect rather than a new experiment-context gap. A2A Python v1.1.0 shipped the fix tracked by upstream #1081 (`RequestContext.metadata` now converts nested protobuf structures with `json_format.MessageToDict`). Re-running the same experiment on the current installable 1.1.2 release made all integration scenarios pass.

**Consequence:** do not open a duplicate A2A issue for the v1.0.0 behavior. The experiment instead provides an additional downstream confirmation that the existing metadata fix is necessary for extension payloads containing nested structures.

## What this proves

For the bounded topology tested here, A2A can transport experiment allocation context without standardizing experimentation fields in the core protocol:

```text
assignment / allocation semantics
            |
            v
custom A2A extension
  experiment_id + treatment
            |
            v
receiver observes envelope
            |
            v
trusted local registry
            |
            v
local materialization only
```

Multiple allocations can coexist on one execution, and a shared specialist does not need to understand or materialize allocations owned by other components.

The experiment also supports the intended proof boundary:

> Propagation makes an allocation observable; it does not make the payload an authorization or ownership credential.

## What this does NOT prove

- that the sender was entitled to assign a syntactically valid experiment/treatment;
- that experiment materialization grants tool/resource authorization;
- that materialization is equivalent to causal exposure;
- that the same extension representation is optimal for every transport/binding;
- that allocation persistence across task continuations should be automatic;
- that A2A should standardize experiment-specific fields;
- that interaction/conflict semantics for multiple experiments are solved.

## Upstream decision

**A2A specification:** no action.

**A2A Python SDK:** no new issue/PR from this experiment. The only SDK defect encountered was the historical nested-metadata conversion behavior in 1.0.0, already fixed upstream in 1.1.0 (#1081).

**OpenFeature:** no immediate follow-up solely from this transport experiment. The result is compatible with the existing public position that experiment identity/allocation semantics can remain separate from the transport and from local materialization. Bring this evidence upstream only if it advances an active design question rather than repeating that position.

## Reusable result

The strongest result is not a new A2A feature request. It is a validated interoperability pattern:

> **Carry a minimal experiment allocation envelope through a custom A2A extension; require explicit extension activation; treat the envelope as context rather than authority; and let each receiver materialize only locally trusted experiment IDs/treatments.**
