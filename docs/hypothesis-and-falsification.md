# Hypothesis and falsification criteria

## Hypothesis

In a composable AI-agent ecosystem with shared downstream agents, experiment state is better modeled as an **execution-scoped set of owned allocations** than as one global variant flag or as state attached to a single agent.

The model is useful only if it preserves four properties:

1. **Independent assignment** — several experiments can coexist in one execution.
2. **Scoped materialization** — a component applies only allocations it owns.
3. **End-to-end attribution** — traces can reconstruct which allocations were visible and which changed behaviour.
4. **Backward-compatible control** — introducing the context does not change behaviour when no experimental allocation is present.

## What would falsify or materially weaken it?

The hypothesis should be rejected or narrowed if one or more of the following hold in realistic systems:

- experiment assignments can be kept entirely local without losing causal attribution or behavioural consistency;
- propagating allocation metadata creates unacceptable coupling, security exposure, or operational cost;
- ownership cannot be defined cleanly for shared/nested agents;
- overlapping experiments require interaction semantics so complex that an execution-scoped allocation map stops being useful;
- exposure logging cannot distinguish "allocation was carried" from "allocation actually affected behaviour";
- control-path equivalence cannot be maintained during migration;
- existing experimentation platforms already provide equivalent semantics cleanly for composable agent graphs, making this layer redundant.

## Questions the current implementation does not answer

### Exposure

When should an exposure be recorded?

- at assignment time;
- when a component observes the allocation;
- only when the allocation materially changes behaviour;
- or at several stages with different event types?

The current trace deliberately distinguishes `observed_allocations` from `applied_allocations`, but does not define statistical exposure semantics.

### Scope and inheritance

Real systems may need scope beyond a simple `owner` string, for example:

- product;
- component;
- agent version;
- capability;
- tool;
- model call.

The minimal owner model is intentionally easy to challenge.

### Trust

A production system must decide who is allowed to create or override allocations. Downstream components should not blindly trust arbitrary client-provided experiment state.

### Privacy

Assignment units can contain sensitive identifiers. The reference implementation uses strings for clarity; production propagation should use privacy-safe identifiers and avoid leaking raw subject data through baggage or logs.

### Interaction effects

Two independently valid experiments can interact. This repository demonstrates propagation and local materialization, not experiment-design correctness.

## Next experiments

1. Replace the in-memory trace sink with OpenTelemetry spans and baggage.
2. Split orchestrators and specialist into separate HTTP processes.
3. Add explicit exposure events and test assignment vs materialization semantics.
4. Add a second specialist experiment and test overlapping allocations.
5. Add a malicious/invalid allocation source and introduce trust validation.
6. Add an A2A or MCP boundary and test context preservation across protocol adapters.
7. Compare the model against an existing experimentation platform rather than a hand-built assignment source.
