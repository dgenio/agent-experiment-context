# Research grounding

This repository intentionally separates runtime semantics from experiment-design validity.

Relevant prior art:

- Google collaboration-network experiments show that network contamination can bias user-level A/B tests and motivate choosing randomization units that reduce interference.
- Microsoft experimentation guidance documents tenant/cluster randomization when users share a consistency boundary, triggered analysis with counterfactual trigger semantics, and the fact that overlapping experiment interactions are often uncommon but still require isolation when expected.

Primary references:

- https://research.google/pubs/designing-ab-tests-in-a-collaboration-network/
- https://www.microsoft.com/en-us/research/group/experimentation-platform-exp/articles/why-tenant-randomized-a-b-test-is-challenging-and-tenant-pairing-may-not-work/
- https://www.microsoft.com/en-us/research/?p=806938
- https://www.microsoft.com/en-us/research/group/experimentation-platform-exp/articles/a-b-interactions-a-call-to-relax/

The agent-specific research question is not whether these statistical principles are new. It is where their assumptions become easy to violate when shared agents introduce persistent state, dynamic routing, and independently owned experimental components.