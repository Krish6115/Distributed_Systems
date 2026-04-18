"""
distributed_simulation.py — Distributed edge computing simulation engine.

This module transforms the single-node encryption benchmark into a
multi-node distributed system by simulating:

    1. N edge nodes  — each generates/receives data, encrypts it, and
       transmits the ciphertext to an aggregator.
    2. An aggregator node (fog/cloud) — receives encrypted payloads,
       decrypts them, verifies integrity, and collects system metrics.

The number of nodes is derived from the scaling model:

    N = A × D
    (Area in km² × Node density in nodes/km²)

This module reuses the existing encryption modules (AES, ChaCha20,
PRESENT, SPECK), profiling logic (BenchmarkProfiler), and data
generator — it does NOT rewrite any of them.

Parallelism
───────────
When feasible, edge nodes are executed in parallel using Python's
multiprocessing.Pool.  This models real distributed systems where
edge nodes operate independently and concurrently.  If multiprocessing
is unavailable (e.g. OS restrictions), the simulation falls back to
sequential execution with clear per-node structure.
"""

import hashlib
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import psutil

from data_generator import generate_iot_data
from distributed_config import (
    DEFAULT_DATA_TOTAL_BYTES,
    EDGE_TO_AGGREGATOR_DELAY_SEC,
    MAX_WORKERS,
    MIN_CHUNK_BYTES,
    SCENARIOS,
    compute_node_count,
)

# ── Algorithm registry (mirrors main.py) ────────────────────────────
import aes_module
import chacha20_module
import present_module
import speck_module

ALGO_MODULES = {
    "AES":      aes_module,
    "ChaCha20": chacha20_module,
    "PRESENT":  present_module,
    "SPECK":    speck_module,
}


# ═══════════════════════════════════════════════════════════════════
#  Data classes for results
# ═══════════════════════════════════════════════════════════════════

@dataclass
class NodeResult:
    """Metrics captured from a single edge node."""
    node_id: int = 0
    algorithm: str = ""
    data_chunk_bytes: int = 0
    encrypt_time_s: float = 0.0
    cpu_percent: float = 0.0
    throughput_mbps: float = 0.0
    integrity_ok: bool = False
    decrypt_time_s: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id":           self.node_id,
            "algorithm":         self.algorithm,
            "data_chunk_bytes":  self.data_chunk_bytes,
            "encrypt_time_ms":   round(self.encrypt_time_s * 1000, 4),
            "decrypt_time_ms":   round(self.decrypt_time_s * 1000, 4),
            "cpu_percent":       round(self.cpu_percent, 2),
            "throughput_mbps":   round(self.throughput_mbps, 4),
            "integrity_ok":      self.integrity_ok,
        }


@dataclass
class DistributedResult:
    """Aggregated metrics for one (scenario, algorithm) simulation run."""
    scenario: str = ""
    algorithm: str = ""
    area_km2: float = 0.0
    density: float = 0.0
    node_count: int = 0
    total_data_bytes: int = 0
    # System-level metrics
    total_throughput_mbps: float = 0.0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    latency_std_ms: float = 0.0
    load_balance_std_ms: float = 0.0
    scalability_factor: float = 0.0
    total_wall_time_s: float = 0.0
    all_integrity_ok: bool = True
    # Per-node detail
    node_results: List[NodeResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario":              self.scenario,
            "algorithm":             self.algorithm,
            "area_km2":              self.area_km2,
            "density":               self.density,
            "node_count":            self.node_count,
            "total_data_bytes":      self.total_data_bytes,
            "total_throughput_mbps": round(self.total_throughput_mbps, 4),
            "avg_latency_ms":        round(self.avg_latency_ms, 4),
            "max_latency_ms":        round(self.max_latency_ms, 4),
            "min_latency_ms":        round(self.min_latency_ms, 4),
            "latency_std_ms":        round(self.latency_std_ms, 4),
            "load_balance_std_ms":   round(self.load_balance_std_ms, 4),
            "scalability_factor":    round(self.scalability_factor, 4),
            "total_wall_time_s":     round(self.total_wall_time_s, 4),
            "all_integrity_ok":      self.all_integrity_ok,
        }

    def to_flat_rows(self) -> List[Dict[str, Any]]:
        """Return one row per node for CSV export."""
        rows = []
        for nr in self.node_results:
            row = nr.to_dict()
            row.update({
                "scenario":         self.scenario,
                "area_km2":         self.area_km2,
                "density":          self.density,
                "node_count":       self.node_count,
                "total_data_bytes": self.total_data_bytes,
            })
            rows.append(row)
        return rows


# ═══════════════════════════════════════════════════════════════════
#  Edge Node — runs on each simulated device
# ═══════════════════════════════════════════════════════════════════

def _edge_node_task(
    node_id: int,
    algo_name: str,
    data_chunk: bytes,
    key: bytes,
) -> Dict[str, Any]:
    """
    Simulate one edge node's encryption pipeline.

    This function is designed to run in a separate process via
    ProcessPoolExecutor.  It:
        1. Encrypts the data chunk using the specified algorithm.
        2. Records encryption time, CPU usage, and throughput.
        3. Returns a serialisable dict (not a dataclass, for pickling).

    Why a top-level function instead of a method?
    ─────────────────────────────────────────────
    Python's multiprocessing requires pickling of the target callable.
    Module-level functions are picklable; bound methods and lambdas are not.
    """
    module = ALGO_MODULES[algo_name]
    proc = psutil.Process(os.getpid())
    proc.cpu_percent(interval=None)  # prime CPU measurement

    # ── Encrypt ──
    t0 = time.perf_counter()
    nonce, ciphertext, tag = module.encrypt(data_chunk, key)
    encrypt_time = time.perf_counter() - t0

    cpu = proc.cpu_percent(interval=None)

    # ── Simulate network delay (edge → aggregator) ──
    time.sleep(EDGE_TO_AGGREGATOR_DELAY_SEC)

    # ── Compute throughput ──
    if encrypt_time > 0:
        throughput = (len(data_chunk) / (1024 * 1024)) / encrypt_time
    else:
        throughput = float("inf")

    # ── Compute integrity hash (will be verified at aggregator) ──
    original_hash = hashlib.sha256(data_chunk).hexdigest()

    return {
        "node_id":           node_id,
        "algorithm":         algo_name,
        "data_chunk_bytes":  len(data_chunk),
        "encrypt_time_s":    encrypt_time,
        "cpu_percent":       cpu,
        "throughput_mbps":   throughput,
        "nonce":             nonce,
        "ciphertext":        ciphertext,
        "tag":               tag,
        "key":               key,
        "original_hash":     original_hash,
    }


# ═══════════════════════════════════════════════════════════════════
#  Aggregator Node — fog / cloud receiver
# ═══════════════════════════════════════════════════════════════════

class AggregatorNode:
    """
    Simulates the fog/cloud aggregator that receives encrypted data
    from all edge nodes, decrypts it, and verifies integrity.

    In a real distributed system this would be a separate process or
    machine; here we run it in the main process after all edge nodes
    have completed, which models the common "collect-then-process"
    pattern in fog computing architectures.
    """

    def __init__(self):
        self._received: List[Dict] = []

    def receive(self, payloads: List[Dict]):
        """Accept encrypted payloads from all edge nodes."""
        self._received = payloads

    def decrypt_and_verify(self) -> List[NodeResult]:
        """
        Decrypt each payload and verify SHA-256 integrity.

        Returns a list of NodeResult with decrypt_time and integrity
        fields populated.
        """
        results = []
        for payload in self._received:
            algo_name = payload["algorithm"]
            module = ALGO_MODULES[algo_name]

            # ── Decrypt ──
            t0 = time.perf_counter()
            plaintext = module.decrypt(
                payload["nonce"],
                payload["ciphertext"],
                payload["tag"],
                payload["key"],
            )
            decrypt_time = time.perf_counter() - t0

            # ── Verify integrity ──
            decrypted_hash = hashlib.sha256(plaintext).hexdigest()
            integrity_ok = decrypted_hash == payload["original_hash"]

            nr = NodeResult(
                node_id=payload["node_id"],
                algorithm=algo_name,
                data_chunk_bytes=payload["data_chunk_bytes"],
                encrypt_time_s=payload["encrypt_time_s"],
                cpu_percent=payload["cpu_percent"],
                throughput_mbps=payload["throughput_mbps"],
                integrity_ok=integrity_ok,
                decrypt_time_s=decrypt_time,
            )
            results.append(nr)

        return results


# ═══════════════════════════════════════════════════════════════════
#  Orchestrator
# ═══════════════════════════════════════════════════════════════════

class DistributedSimulation:
    """
    Orchestrates a distributed edge computing simulation run.

    Models the full lifecycle:
        1. Compute N = A × D (number of edge nodes).
        2. Generate IoT data and split across N nodes.
        3. Each edge node encrypts its chunk (in parallel via
           ProcessPoolExecutor when N is large enough to benefit).
        4. Aggregator receives, decrypts, and verifies all payloads.
        5. System-wide metrics are computed and returned.
    """

    def __init__(self, max_workers: Optional[int] = MAX_WORKERS):
        self.max_workers = max_workers

    def run(
        self,
        area_km2: float,
        density: float,
        algo_name: str,
        total_data_bytes: int = DEFAULT_DATA_TOTAL_BYTES,
        scenario_label: str = "",
    ) -> DistributedResult:
        """
        Execute one simulation run.

        Parameters
        ----------
        area_km2 : float
            Deployment area in km².
        density : float
            Node density (nodes/km²).
        algo_name : str
            Algorithm name (must be in ALGO_MODULES).
        total_data_bytes : int
            Total data to distribute across all nodes.
        scenario_label : str
            Human-readable label for this scenario.

        Returns
        -------
        DistributedResult
            Complete per-node and system-level metrics.
        """
        # ── Step 1: Compute node count via scaling model ──
        # N = A × D  (see distributed_config.py for justification)
        n_nodes = compute_node_count(area_km2, density)
        logging.info(
            f"  [{algo_name}] Scenario '{scenario_label}': "
            f"Area={area_km2} km², Density={density} nodes/km², "
            f"N={n_nodes} nodes"
        )

        # ── Step 2: Generate and split data ──
        chunk_size = max(MIN_CHUNK_BYTES, total_data_bytes // n_nodes)
        module = ALGO_MODULES[algo_name]
        key = module.generate_key()

        # Generate one data pool and split into node-sized chunks.
        # In a real deployment each node would generate its own sensor
        # data; here we pre-generate to ensure reproducible benchmarking.
        data_pool = generate_iot_data(total_data_bytes)
        chunks = []
        for i in range(n_nodes):
            start = i * chunk_size
            end = start + chunk_size
            if start >= len(data_pool):
                # Wrap around for very large N
                chunk = generate_iot_data(chunk_size)
            else:
                chunk = data_pool[start:end]
                if len(chunk) < chunk_size:
                    chunk += generate_iot_data(chunk_size - len(chunk))
            chunks.append(chunk)

        # ── Step 3: Run edge nodes ──
        wall_start = time.perf_counter()
        payloads = self._run_edge_nodes(n_nodes, algo_name, chunks, key)
        edge_wall_time = time.perf_counter() - wall_start

        # ── Step 4: Aggregator receives and decrypts ──
        aggregator = AggregatorNode()
        aggregator.receive(payloads)
        node_results = aggregator.decrypt_and_verify()

        total_wall_time = time.perf_counter() - wall_start

        # ── Step 5: Compute system-level metrics ──
        return self._build_result(
            scenario_label, algo_name, area_km2, density,
            n_nodes, total_data_bytes, total_wall_time, node_results,
        )

    def _run_edge_nodes(
        self,
        n_nodes: int,
        algo_name: str,
        chunks: List[bytes],
        key: bytes,
    ) -> List[Dict]:
        """
        Execute all edge node tasks.

        Uses ProcessPoolExecutor for parallel execution when N > 4
        (overhead of spawning processes is not worthwhile for fewer nodes).
        Falls back to sequential execution if multiprocessing fails.
        """
        # For small N or if PRESENT/SPECK are slow, sequential is fine
        # and avoids multiprocessing overhead.
        use_parallel = n_nodes > 4

        if use_parallel:
            try:
                return self._run_parallel(n_nodes, algo_name, chunks, key)
            except Exception as e:
                logging.warning(
                    f"  Parallel execution failed ({e}); falling back to sequential."
                )

        return self._run_sequential(n_nodes, algo_name, chunks, key)

    def _run_parallel(
        self, n_nodes, algo_name, chunks, key
    ) -> List[Dict]:
        """Run edge nodes in parallel using ProcessPoolExecutor."""
        payloads = []
        workers = self.max_workers or min(n_nodes, os.cpu_count() or 4)

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _edge_node_task, node_id, algo_name, chunks[node_id], key
                ): node_id
                for node_id in range(n_nodes)
            }
            for future in as_completed(futures):
                payloads.append(future.result())

        # Sort by node_id for deterministic output
        payloads.sort(key=lambda p: p["node_id"])
        return payloads

    def _run_sequential(
        self, n_nodes, algo_name, chunks, key
    ) -> List[Dict]:
        """Run edge nodes sequentially (fallback / small N)."""
        payloads = []
        for node_id in range(n_nodes):
            payload = _edge_node_task(node_id, algo_name, chunks[node_id], key)
            payloads.append(payload)
            if node_id % 50 == 0 and node_id > 0:
                logging.info(f"    ... processed {node_id}/{n_nodes} nodes")
        return payloads

    @staticmethod
    def _build_result(
        scenario, algo_name, area, density, n_nodes,
        total_data, wall_time, node_results,
    ) -> DistributedResult:
        """Compute system-level metrics from per-node results."""
        import statistics

        enc_times = [nr.encrypt_time_s for nr in node_results]
        throughputs = [nr.throughput_mbps for nr in node_results]

        # Total system throughput = sum of individual node throughputs
        # (in a real parallel deployment, nodes work simultaneously)
        total_throughput = sum(throughputs)

        # Average and std of latency (encryption time) across nodes
        avg_lat = statistics.mean(enc_times) * 1000  # ms
        max_lat = max(enc_times) * 1000
        min_lat = min(enc_times) * 1000
        std_lat = statistics.stdev(enc_times) * 1000 if len(enc_times) > 1 else 0.0

        # Load balance: std deviation of encryption times.
        # Lower = more balanced distribution.
        load_std = std_lat

        # Scalability factor: ratio of N-node throughput to single-node
        # throughput.  Ideal linear scaling would give factor = N.
        single_node_throughput = throughputs[0] if throughputs else 1.0
        scalability = total_throughput / single_node_throughput if single_node_throughput > 0 else 0.0

        return DistributedResult(
            scenario=scenario,
            algorithm=algo_name,
            area_km2=area,
            density=density,
            node_count=n_nodes,
            total_data_bytes=total_data,
            total_throughput_mbps=total_throughput,
            avg_latency_ms=avg_lat,
            max_latency_ms=max_lat,
            min_latency_ms=min_lat,
            latency_std_ms=std_lat,
            load_balance_std_ms=load_std,
            scalability_factor=scalability,
            total_wall_time_s=wall_time,
            all_integrity_ok=all(nr.integrity_ok for nr in node_results),
            node_results=node_results,
        )


# ═══════════════════════════════════════════════════════════════════
#  Convenience: run all predefined scenarios
# ═══════════════════════════════════════════════════════════════════

def run_all_scenarios(
    algorithms: Optional[List[str]] = None,
    scenarios: Optional[Dict] = None,
    total_data_bytes: int = DEFAULT_DATA_TOTAL_BYTES,
) -> List[DistributedResult]:
    """
    Run the distributed simulation across all predefined scenarios
    and all algorithms.

    Parameters
    ----------
    algorithms : list of str, optional
        Algorithm names to test (default: all four).
    scenarios : dict, optional
        Scenario definitions (default: SCENARIOS from distributed_config).
    total_data_bytes : int
        Total data per simulation run.

    Returns
    -------
    list of DistributedResult
        One entry per (scenario, algorithm) combination.
    """
    if algorithms is None:
        algorithms = list(ALGO_MODULES.keys())
    if scenarios is None:
        scenarios = SCENARIOS

    sim = DistributedSimulation()
    all_results = []

    for scenario_key, scenario_cfg in scenarios.items():
        area = scenario_cfg["area_km2"]
        density = scenario_cfg["density"]
        label = scenario_cfg["label"]
        n = compute_node_count(area, density)

        logging.info(f"\n{'=' * 60}")
        logging.info(f"  SCENARIO: {label}")
        logging.info(f"  Area={area} km2  Density={density} nodes/km2  N={n}")
        logging.info(f"  {scenario_cfg['description']}")
        logging.info(f"{'=' * 60}")

        for algo_name in algorithms:
            result = sim.run(
                area_km2=area,
                density=density,
                algo_name=algo_name,
                total_data_bytes=total_data_bytes,
                scenario_label=label,
            )
            all_results.append(result)

            logging.info(
                f"  [{algo_name}] OK  nodes={result.node_count}  "
                f"throughput={result.total_throughput_mbps:.2f} MB/s  "
                f"avg_latency={result.avg_latency_ms:.3f} ms  "
                f"integrity={'PASS' if result.all_integrity_ok else 'FAIL'}"
            )

    return all_results
