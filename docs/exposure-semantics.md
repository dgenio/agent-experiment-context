# Experiment lifecycle semantics

This experiment asks a narrower question than assignment propagation: when can an intervention legitimately count as an exposure for analysis?

The model keeps four stages separate:

- `assigned`: an experiment arm was selected;
- `observed`: a component received the allocation;
- `materialized`: the component selected behavior because of the allocation;
- `exposed`: the intervention reached a point where it could plausibly affect a measured outcome.

An earlier stage does not automatically imply a later one.

## Counterexamples

A component may observe another component's allocation without being exposed to that experiment. A component may also select a treatment branch before reaching the intervention point. Conversely, if treatment already changes a request before a later downstream failure, that remains an exposure because the treatment could have affected latency, error rate, or downstream behavior.

Repeated specialist calls retain raw exposure events. The reference recorder also offers a first-exposure view deduplicated by `execution_id + component_id + experiment_id`. This is deliberately not user-level deduplication because raw user/session identity is outside the current propagation model.

## Prior art

LaunchDarkly recommends evaluating experiment variations where the context encounters the experience rather than prematurely. Statsig documents qualifying-event handling for assignment sources that can over-count exposures before an intervention actually triggers.

- https://launchdarkly.com/docs/sdk/features/experimentation
- https://docs.statsig.com/statsig-warehouse-native/features/filtering-exposures

## Narrow conclusion

Assignment, propagation, observation, materialization, and exposure should not be treated as synonyms in a composable agent execution.

This does not define one universal statistical exposure rule. Product and experiment semantics may still determine the exact intervention point.
