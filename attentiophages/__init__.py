"""Attentiophages: measuring whether an agent feeds its ecosystem or drains it.

The public surface is deliberately small. Everything here is computable from a
post corpus; anything that is not returns :data:`~attentiophages.metrics.UNAVAILABLE`.
"""

from attentiophages.metrics import (
    UNAVAILABLE,
    Coalition,
    SharedIdentity,
    Corpus,
    NetworkImpact,
    Post,
    Unavailable,
    agent_quality,
    amplification_edges,
    attention_units,
    credibility_divergence,
    detect_coalitions,
    endorsement_concentration,
    isolated_clusters,
    network_impact,
    shared_identity_clusters,
)

__version__ = "2.0.0"

__all__ = [
    "UNAVAILABLE",
    "Coalition",
    "Corpus",
    "NetworkImpact",
    "Post",
    "Unavailable",
    "agent_quality",
    "amplification_edges",
    "attention_units",
    "credibility_divergence",
    "detect_coalitions",
    "endorsement_concentration",
    "SharedIdentity",
    "isolated_clusters",
    "network_impact",
    "shared_identity_clusters",
    "__version__",
]
