# Experimental A2A extension: scoped experiment allocations v1

**Status:** repository-local falsification contract; not an A2A standard proposal.

**Extension URI:**

```text
https://github.com/dgenio/agent-experiment-context/blob/main/docs/a2a-experiment-allocation-extension-v1.md
```

## Purpose

Carry a small set of **already-resolved experiment allocations** across an A2A request boundary so downstream components can independently decide whether an allocation changes their local behavior.

The extension does not perform assignment, authorization, policy evaluation, analytics, or causal inference.

## Activation

The client activates the extension using A2A's standard service parameter:

```text
A2A-Extensions: <extension URI>
```

Metadata carrying this payload is intentionally inert if the extension was not requested for the interaction.

## Request metadata

The request metadata object uses the extension URI as its key:

```json
{
  "<extension URI>": {
    "allocations": [
      {
        "experiment_id": "specialist-response-mode-v1",
        "treatment": "structured"
      }
    ]
  }
}
```

### Allocation fields

| Field | Required | Meaning |
| --- | --- | --- |
| `experiment_id` | yes | Stable identity of the experiment whose allocation has already been resolved upstream. |
| `treatment` | yes | The allocated arm/treatment identity. |

No assignment-unit identifier is transported by this experiment.

## Trust boundary

The wire representation is **context, not authority**.

A receiving component:

1. may observe all syntactically valid allocations;
2. materializes only experiment IDs/treatments present in trusted local registration;
3. ignores wire-only claims such as `owner`, `authorized`, `scope`, or provenance fields;
4. must keep authorization/delegation decisions separate from experiment materialization.

The experiment deliberately accepts no remote `owner` field into its local model.

This contract also does not prove that the sender was entitled to choose a valid allocation. A production system still needs an appropriate trust boundary for assignment input. That question is deliberately outside this transport experiment.

## Multiple allocations

One execution can carry more than one allocation:

```json
{
  "allocations": [
    {
      "experiment_id": "orchestrator-routing-v1",
      "treatment": "normalized"
    },
    {
      "experiment_id": "specialist-response-mode-v1",
      "treatment": "structured"
    }
  ]
}
```

A shared specialist can observe both while materializing only the second.

## Forwarding

An intermediate agent may forward the minimal envelope to another A2A hop. Forwarding does not make that intermediate agent the assignment or authorization authority. Each receiver independently applies its trusted local registry.

## Lifecycle semantics tested here

The extension is treated as **request-scoped**:

- activation is a service parameter on a client call;
- the allocation payload is request metadata;
- a later request for the same A2A task does not implicitly inherit the earlier allocation;
- clients must explicitly resend the extension context when the same allocation should remain active on a continuation.

This is a deliberate observation of the current carrier model, not a proposal that all experimentation systems must use request-scoped assignment.

## Observation, materialization, exposure

This experiment emits evidence for:

- **observed** — the component decoded the allocation;
- **materialized** — trusted local registration caused behavior to change.

It does not infer experiment **exposure** merely from either event. Exposure remains a later semantic boundary that depends on whether the intervention could plausibly affect the measured outcome.
