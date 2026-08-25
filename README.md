# agent-experiment-context

Small, falsifiable experiments around **experiment context in composable agent systems**.

The repository is intentionally not an experimentation platform. It tests narrow semantic and interoperability questions such as:

- several experiment allocations coexisting on one execution;
- assignment/allocation propagating without becoming authorization;
- each component materializing only locally recognized experiments;
- observation, materialization, and exposure remaining distinct;
- no-allocation behavior staying equivalent to control.

## A2A Extensions experiment (#7) — PASS

Issue [#7](https://github.com/dgenio/agent-experiment-context/issues/7) asked whether the existing A2A extension mechanism is already sufficient to carry a minimal scoped experiment-allocation envelope across agent boundaries.

The experiment passed against the published `a2a-sdk` 1.1.2 JSON-RPC client/server path. A custom extension is activated through the standard `A2A-Extensions` service parameter; the extension payload lives in request metadata and contains only:

```json
{
  "allocations": [
    {"experiment_id": "specialist-mode-v1", "treatment": "structured"}
  ]
}
```

Local components decide which experiment IDs/treatments they recognize. Wire fields such as `owner`, `authorized`, or `scope` are deliberately not part of the trusted model.

The validated suite covers:

- blocking and streaming A2A calls;
- two simultaneous allocations;
- local-only materialization;
- unknown/forged ownership metadata remaining inert;
- two callers hitting the same shared specialist concurrently;
- no-allocation control after treatment;
- task continuation with and without explicit context resend;
- a second A2A hop where each specialist resolves ownership independently.

A useful lifecycle result is that this carrier is request-scoped: later requests for the same A2A task do not implicitly inherit an earlier allocation. The context must be resent if the same allocation should remain active.

The first falsification run against A2A Python 1.0.0 also surfaced a historical nested-request-metadata conversion problem. That was already fixed upstream in A2A Python 1.1.0 (#1081); the same scenarios pass on 1.1.2, so no new upstream A2A issue is warranted.

**Decision:** the existing A2A extension + service-parameter + request-metadata surfaces are sufficient for this bounded Experiment Context transport use case. Keep experiment assignment semantics and local materialization outside core A2A.

See [`docs/a2a-experiment-allocation-extension-v1.md`](docs/a2a-experiment-allocation-extension-v1.md) for the experimental extension contract and [`docs/issue-7-results.md`](docs/issue-7-results.md) for the evidence/decision record.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check .
pytest -q
```

## Decision discipline

A successful experiment can conclude **no upstream change is needed**. An A2A issue/PR is warranted only if the protocol or SDK fails at a generic extension/interoperability boundary that can be reduced to a small MRE.
