# OpenTelemetry HTTP propagation experiment

This experiment tests whether the execution-scoped allocation model survives a real HTTP/process boundary while keeping materialization decisions in trusted local configuration.

## Design choice under test

Only the minimum pair is propagated in OpenTelemetry Baggage:

```text
experiment_id -> treatment
```

The following are deliberately **not** propagated:

- assignment unit;
- raw user/session identity;
- ownership;
- provenance as authorization evidence.

The receiving process evaluates the pair through the same `LocalExperimentRegistry` used by the A2A experiment. Unknown experiment IDs and unknown treatments remain observable but cannot affect local behaviour.

This does **not** authenticate whether the sender is entitled to request a known, locally accepted pair. A caller that can write Baggage can request that pair. Sender authentication and authorization therefore remain a separate boundary that this experiment does not prove.

## Why not serialize the full allocation object?

OpenTelemetry Baggage is useful for cross-process contextual data, but baggage values may propagate further than intended and do not have built-in integrity guarantees. Treating a wire-provided `owner` or assignment subject as trusted would therefore collapse propagation and authorization into one mechanism.

The experiment keeps those responsibilities separate:

- **trace context**: causal continuity;
- **baggage**: minimal experiment allocation hints;
- **local registry**: trusted accepted ID/treatment pairs and local behaviour;
- **span attributes**: explicit evidence of observed vs applied allocations.

## Topology

```text
client
  |
  +--> Orchestrator A process ----HTTP----+
  |                                       |
  +--> Orchestrator B process ----HTTP----+--> Shared Specialist process
```

The implementation uses the Python standard-library HTTP server so the experiment does not accidentally become a framework comparison.

## Evidence produced

Tests verify:

1. one trace continues across client -> orchestrator -> specialist;
2. multiple allocations survive the HTTP boundary;
3. Orchestrator A applies only its own allocation;
4. Orchestrator B does not apply Orchestrator A's allocation;
5. the specialist applies only a locally registered ID/treatment pair;
6. unknown experiment IDs are observable but inert;
7. unknown treatments for known IDs are observable but inert;
8. forged ownership-like baggage cannot create a registered pair;
9. no-allocation requests preserve the legacy/control result;
10. raw user/session identifiers are absent from the baggage header.

## What would still falsify the model?

This experiment is not enough to prove the architecture. The model should still be narrowed if later work shows that:

- trace correlation alone is sufficient and allocation propagation adds no value;
- a dedicated propagation concern/header is materially cleaner than Baggage;
- experiment interaction semantics make a flat allocation map misleading;
- safe propagation across external/untrusted boundaries requires a different trust model;
- callers need an entitlement mechanism for requesting known treatments;
- real A2A/MCP adapters distort or drop the semantics.

## Implementation finding: trace parent and baggage need deliberate recomposition

The first version of this experiment failed in a useful way. The orchestrator and specialist remained on the expected trace path, but experiment allocations disappeared before local materialization.

The failing implementation started a child span from the extracted context and then injected from the implicit current context. In the local OpenTelemetry Python run, that preserved the new span/trace relationship but did not preserve the extracted Baggage for the next outbound request.

The corrected path explicitly combines the newly created span with the previously extracted context before injection:

```python
propagation_context = set_span_in_context(span, extracted)
PROPAGATOR.inject(headers, context=propagation_context)
```

The regression tests now prove both properties together:

- downstream spans stay on the same trace;
- experiment baggage survives the next HTTP boundary.

This is exactly why the transport experiment exists: trace correlation and experiment-allocation propagation are related concerns, but one should not be assumed to prove the other.
