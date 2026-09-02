# Interference, randomization scope, and causal validity

This bounded experiment tests three ways a composable agent graph can make an otherwise familiar A/B design untrustworthy.

## 1. Shared state can contaminate control

A specialist with tenant-scoped memory is shared by independently randomized users. A treatment execution writes state; a later control execution in the same tenant reads it. The control outcome therefore depends on another unit's treatment assignment.

That is an interference problem, not a context-propagation bug. If state cannot be isolated, the randomization unit may need to expand to the state-sharing boundary (for example tenant/cluster). If the shared state is global and has temporal carryover, a time-block/switchback design with an explicit washout assumption may be more appropriate.

The repo does **not** claim one universal randomization unit. It makes the dependency explicit: randomization must respect the boundary across which one unit's treatment can change another unit's outcome.

## 2. Observed exposure can be post-treatment selection

The second counterexample deliberately lets treatment change whether a unit is routed to the specialist. Easy and hard units have different baseline outcomes, but treatment itself changes no outcome.

If we compare only executions that actually reached the specialist, treatment appears better even though the true treatment effect is zero. The problem is that observed exposure is downstream of assignment.

This is why triggered analysis needs a trigger with valid counterfactual semantics. An execution being *observed* at a downstream component is not automatically a statistically safe analysis population.

## 3. Concurrent experiments can interact

The third counterexample runs two independently assigned experiments. Experiment A has a +2 effect when B is control and a -2 effect when B is treatment. With B balanced 50/50, A's marginal effect is exactly zero.

Independent overlapping experiments are often safe in large experimentation systems, so this repo does not assume interaction is common. It instead argues that composable agent changes deserve an interaction check when one treatment can alter the prompt, tool set, route, state, or input seen by another experimental component.

## Decision table

| System property | Default experiment concern | Candidate response |
|---|---|---|
| Stateless, unit-isolated execution | ordinary consistency | user/session assignment as product semantics require |
| Persistent per-user memory | repeated-unit consistency | randomize stably at user (or broader) |
| Shared tenant/team memory | cross-user interference | isolate state or randomize tenant/cluster |
| Global/shared state with carryover | temporal interference | isolate state, or consider blocked/switchback design with washout |
| Treatment changes downstream routing/exposure | post-randomization selection | intent-to-treat or counterfactual/qualifying trigger |
| Concurrent treatments alter each other's inputs/behavior | interaction | segment/test interaction or isolate experiments if material |

## What this establishes

The execution context is useful for carrying allocations and reconstructing paths, but **it is not the randomization design**. The correct assignment unit and analysis population depend on interference, persistence, routing, and the estimand.

A concise formulation for the book is:

> Assignment is statistical. Allocation is contextual. Materialization is architectural. Exposure is causal. Interference determines whether the randomization design is valid.

## What remains unproven

- how frequent meaningful interactions are in real shared-agent fleets;
- which real agent-state mechanisms create practically important carryover;
- when cluster or switchback designs recover enough power to be operationally useful;
- how to estimate effects under partial interference rather than merely detect the hazard;
- how multi-agent tool routing changes the counterfactual trigger definition in production systems.
