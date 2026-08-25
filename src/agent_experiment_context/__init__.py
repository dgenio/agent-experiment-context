"""Scoped experiment-allocation primitives used by the research experiments."""

from .a2a_agent import ExperimentAgentExecutor
from .a2a_extension import (
    EXTENSION_URI,
    ExperimentAllocation,
    ExperimentEnvelope,
    ExperimentEvidence,
    LocalExperimentRegistry,
    build_client_call_context,
    build_request_metadata,
    decode_request_context,
)

__all__ = [
    "EXTENSION_URI",
    "ExperimentAgentExecutor",
    "ExperimentAllocation",
    "ExperimentEnvelope",
    "ExperimentEvidence",
    "LocalExperimentRegistry",
    "build_client_call_context",
    "build_request_metadata",
    "decode_request_context",
]
