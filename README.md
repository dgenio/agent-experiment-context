# Agent Experiment Context

A small reference implementation for one architectural question:

> **Where should experiment state live when multiple orchestrators share specialist AI agents?**

The hypothesis explored here is that an A/B variant does **not** belong to a single agent. In a composable many-to-many agent ecosystem, experiment assignments belong to the **end-to-end execution**, while each component materializes only the allocations it owns.

This repository is intentionally small. It is an experiment and reference implementation, **not a proposed standard**.

## The problem

A single header such as:

```text
X-Variant: treatment
```

works only while there is one experiment dimension and one component interpreting it.

Consider a shared-agent topology:

```text
User
 │
 ├── Orchestrator A ──┐
 │                    ├── Shared Specialist ── Tool
 └── Orchestrator B ──┘
```

Now suppose:

- Orchestrator A owns `orchestrator-a-routing-v1`;
- the Shared Specialist owns `specialist-response-mode-v1`;
- both experiments can run simultaneously;
- Orchestrator B also calls the same specialist, but does not participate in Orchestrator A's experiment.

A global `variant=treatment` flag is no longer precise enough.

## Proposed separation

The reference model separates three concerns:

1. **Assignment** — which arm was an assignment unit placed in?
2. **Propagation** — which allocations travel with this execution?
3. **Materialization** — which allocations does a particular component actually apply?

The execution carries an `ExperimentAllocationContext`:

```python
ExperimentAllocationContext(
    execution_id="execution-001",
    allocations={
        "orchestrator-a-routing-v1": ExperimentAllocation(
            experiment_id="orchestrator-a-routing-v1",
            arm="normalized",
            owner="orchestrator-a",
            assignment_unit="user:42",
        ),
        "specialist-response-mode-v1": ExperimentAllocation(
            experiment_id="specialist-response-mode-v1",
            arm="structured",
            owner="shared-specialist",
            assignment_unit="user:42",
        ),
    },
)
```

Every component may carry the context for attribution, but it **must not apply allocations it does not own**.

## Why this is different from a single variant flag

The same execution can legitimately contain multiple independent allocations:

```text
execution-001
  ├── orchestrator-a-routing-v1 = normalized
  └── specialist-response-mode-v1 = structured
```

When Orchestrator B receives the same context, it can preserve attribution without accidentally adopting Orchestrator A's local treatment.

## Zero-diff control invariant

An important migration property is included as an executable test:

> **No experiment allocation → legacy/control behaviour is semantically unchanged.**

`tests/test_zero_diff_control.py` compares the context-aware path against the pre-experiment legacy function over a request corpus.

This is deliberately stronger than saying "control should look similar." It makes backward compatibility a migration invariant.

## Trace attribution

Each component emits a tiny in-memory trace event containing:

- execution ID;
- all allocations visible on the execution;
- allocations actually applied by that component;
- local materialization attributes.

The distinction between **observed** and **applied** allocations makes it possible to reconstruct an end-to-end experiment path without coupling every component to every experiment.

A production implementation could carry the same semantics using OpenTelemetry context/baggage and span attributes; this repository deliberately keeps the transport dependency-free so the semantic model remains visible.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
python examples/demo.py
```

Expected demo shape:

```text
Orchestrator A: specialist[structured]::request=explain invoices
Orchestrator B: specialist[structured]::request=explain invoices

Trace attribution:
- orchestrator-a: observed=(...); applied=('orchestrator-a-routing-v1',); ...
- shared-specialist: observed=(...); applied=('specialist-response-mode-v1',); ...
- orchestrator-b: observed=(...); applied=(); ...
- shared-specialist: observed=(...); applied=('specialist-response-mode-v1',); ...
```

## What this repo does *not* solve

Deliberately out of scope for v0.1:

- statistical assignment algorithms;
- exposure logging semantics;
- cross-experiment interaction detection;
- experiment conflict resolution;
- sticky assignment storage;
- OpenTelemetry wire propagation;
- A2A or MCP transport integration;
- causal analysis;
- authorization of experiment overrides.

Those are follow-up research questions, not hidden assumptions.

## Research questions

1. Which allocations actually need to propagate downstream versus remaining local?
2. Should exposure be recorded when an allocation is assigned, observed, or materially affects behaviour?
3. How should nested/shared agents handle conflicting experiment ownership?
4. What is the correct relationship between experiment context and trace context?
5. Can the control-path equivalence invariant be generalized into a reusable migration/conformance test?

## Motivation

This repository was created while researching a broader idea about production AI systems: organizations increasingly compose shared agents and tools across product boundaries, but common experimentation patterns often assume a single application owns the whole request path.

The goal here is to make one narrow hypothesis falsifiable with code.

## License

MIT.
