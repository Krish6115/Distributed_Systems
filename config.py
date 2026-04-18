"""
config.py — Central configuration for encryption benchmark experiments.

All tuneable parameters live here so experiments are reproducible
and easy to adjust from a single location.
"""

# ──────────────────────────────────────────────
# Data sizes (in bytes) to benchmark
# ──────────────────────────────────────────────
DATA_SIZES = {
    "1KB":   1 * 1024,
    "10KB":  10 * 1024,
    "100KB": 100 * 1024,
    "1MB":   1 * 1024 * 1024,
}

# ──────────────────────────────────────────────
# Experiment repetitions per (algorithm, size) pair
# ──────────────────────────────────────────────
DEFAULT_ITERATIONS = 5

# ──────────────────────────────────────────────
# Simulated edge / network transmission delay (seconds)
# Injected between encrypt → decrypt in each iteration
# to model real edge-to-cloud pipeline latency.
# ──────────────────────────────────────────────
EDGE_DELAY_SEC = 0.05

# ──────────────────────────────────────────────
# Algorithm registry (display names & module refs)
# ──────────────────────────────────────────────
ALGORITHMS = ["AES", "ChaCha20", "PRESENT", "SPECK"]

# ──────────────────────────────────────────────
# Output paths
# ──────────────────────────────────────────────
RESULTS_DIR  = "results"
RESULTS_CSV  = f"{RESULTS_DIR}/benchmark_results.csv"
RESULTS_JSON = f"{RESULTS_DIR}/benchmark_results.json"
GRAPHS_DIR   = f"{RESULTS_DIR}/graphs"

# ──────────────────────────────────────────────
# Distributed simulation output paths
# ──────────────────────────────────────────────
DISTRIBUTED_RESULTS_DIR = f"{RESULTS_DIR}/distributed"
DISTRIBUTED_GRAPHS_DIR  = f"{RESULTS_DIR}/distributed_graphs"

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
LOG_FILE = f"{RESULTS_DIR}/experiment.log"
LOG_LEVEL = "INFO"
