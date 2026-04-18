"""
distributed_config.py — Configuration for the distributed edge computing simulation.

Scaling Model
─────────────
In real-world IoT / edge deployments the number of edge devices (N) in a
geographic region is a function of two factors:

    N = A × D

where:
    A = coverage area in km²  (e.g. a factory floor, a city district)
    D = node density in nodes/km²  (determined by sensor spacing, use-case)

This linear model is widely used in wireless sensor network (WSN) research
(see: Akyildiz et al., "Wireless sensor networks: a survey", Computer
Networks 2002) because it captures the fundamental relationship between
physical deployment scale and computational load.

Why multiple nodes are necessary
────────────────────────────────
Edge computing distributes cryptographic workloads across many lightweight
devices rather than centralising them.  This is essential because:
  1. Data sovereignty — sensitive data (medical, industrial) must be
     encrypted *before* leaving the device, not at a remote cloud.
  2. Latency — real-time applications (autonomous vehicles, factory
     robotics) cannot tolerate round-trip cloud encryption.
  3. Bandwidth — encrypting at the edge reduces plaintext traffic on
     constrained wireless links.
  4. Fault tolerance — losing one node does not halt the entire system.

Evaluating encryption algorithms under multi-node conditions reveals
scalability bottlenecks (CPU contention, memory pressure) that are
invisible in single-node benchmarks.
"""

# ═══════════════════════════════════════════════════════════════════
#  Scaling model parameters
# ═══════════════════════════════════════════════════════════════════

# Default node density (nodes per km²).
# Typical real-world densities:
#   - Smart agriculture:   1–5  nodes/km²
#   - Urban IoT:          10–50 nodes/km²
#   - Industrial factory: 50–200 nodes/km²  (small area, high density)
DEFAULT_NODE_DENSITY = 10  # nodes per km²


def compute_node_count(area_km2: float, density: float = DEFAULT_NODE_DENSITY) -> int:
    """
    Compute number of edge nodes using the scaling model N = A × D.

    Parameters
    ----------
    area_km2 : float
        Coverage area in square kilometres.
    density : float
        Node density (nodes per km²).

    Returns
    -------
    int
        Number of nodes (minimum 1).
    """
    return max(1, int(area_km2 * density))


# ═══════════════════════════════════════════════════════════════════
#  Pre-defined deployment scenarios
# ═══════════════════════════════════════════════════════════════════

SCENARIOS = {
    "small": {
        "label":       "Small Scale",
        "area_km2":    1.0,
        "density":     5.0,        # N = 1 × 5 = 5 nodes
        "description": "Single building / small factory floor",
    },
    "medium": {
        "label":       "Medium Scale",
        "area_km2":    10.0,
        "density":     10.0,       # N = 10 × 10 = 100 nodes
        "description": "Campus / industrial park",
    },
    "large": {
        "label":       "Large Scale",
        "area_km2":    100.0,
        "density":     10.0,       # N = 100 × 10 = 1000 nodes
        "description": "City district / smart-city deployment",
    },
}

# ═══════════════════════════════════════════════════════════════════
#  Simulation defaults
# ═══════════════════════════════════════════════════════════════════

# Total data to distribute across all nodes in one simulation run (bytes).
# Each node gets  DATA_TOTAL_BYTES / N  bytes (minimum 64 B).
DEFAULT_DATA_TOTAL_BYTES = 100 * 1024  # 100 KB

# Minimum data chunk per node (bytes).  Prevents degenerate cases where
# N is so large that each node gets < 1 record.
MIN_CHUNK_BYTES = 64

# Simulated one-way edge → aggregator network latency (seconds).
# Models a single wireless hop (Wi-Fi / LoRa / 5G).
EDGE_TO_AGGREGATOR_DELAY_SEC = 0.002

# Maximum number of parallel worker processes.
# Set to None to use all available CPU cores.
MAX_WORKERS = None
