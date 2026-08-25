# Issue #7 — A2A extension transport experiment

## Status

Implementation prepared on the issue branch. Final conclusions must be based on green CI against the pinned official A2A SDK, not on design inspection alone.

## Research question

Can the current A2A extension machinery carry a minimal multi-allocation experiment envelope across agent boundaries while preserving local ownership/materialization, request isolation, and the distinction between propagated context and authority?

## Implementation under test

- `a2a-sdk[http-server]==1.0.0`
- JSON-RPC transport through the official A2A client and server routes
- `A2A-Extensions` activation via `ServiceParametersFactory` / `with_a2a_extensions`
- allocation payload stored in `SendMessageRequest.metadata`
- `RequestContext.requested_extensions` gates decoding
- `RequestContext.metadata` carries the extension payload to the executor
- trusted local registry maps only recognized `(experiment_id, treatment)` pairs to behavior

## Scenarios

| Scenario | Expected evidence |
| --- | --- |
| Two allocations on one call | receiver observes both, materializes only its registered experiment |
| Blocking + streaming | same allocation semantics in both modes |
| Metadata without extension activation | inert / control |
| Unknown experiment | observed but not materialized |
| Forged `owner` / `authorized` / `scope` fields | fields discarded; cannot create local ownership |
| Two concurrent callers | each request keeps its own allocations and behavior |
| Treatment followed by no-allocation request | second request returns to control |
| Same task, continuation without resend | continuation sees no allocation and returns to control |
| Same task, continuation with resend | allocation materializes again |
| Second A2A hop | each specialist materializes only its locally registered experiment |

## Upstream decision gate

Do not open an A2A issue merely because custom experimentation semantics require a custom extension.

After CI and any necessary fixes, choose exactly one:

1. **No upstream action** — existing A2A extension/service-parameter/metadata surfaces are sufficient.
2. **A2A SDK issue/PR** — a generic extension use case is fragile, lossy, request-global, or non-isolated in the SDK.
3. **A2A specification issue** — the protocol cannot express a generic extension-lifecycle requirement needed by the MRE.
4. **OpenFeature follow-up** — transport works, but the experiment reveals a semantic ambiguity around experiment identity/allocation/materialization/exposure.

## Claims deliberately not made

- that A2A should standardize experiment fields;
- that receiving an allocation authenticates the assignment authority;
- that experiment materialization grants tool/resource authorization;
- that materialization is automatically causal exposure;
- that assignment must be request-scoped in the originating experimentation system.
