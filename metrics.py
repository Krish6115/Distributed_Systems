"""
metrics.py — Performance measurement utilities for encryption benchmarks.

Provides a context‑manager‑based profiler that captures:
    • Wall‑clock time  (high‑resolution via time.perf_counter)
    • CPU utilisation   (via psutil)
    • Peak memory delta (via psutil / tracemalloc)
    • Throughput        (bytes / second)

Usage:
    from metrics import BenchmarkProfiler

    with BenchmarkProfiler(data_size_bytes=1024) as prof:
        ciphertext = encrypt(data)

    print(prof.results)   # dict with all metrics
"""

import time
import tracemalloc
import psutil
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class BenchmarkResult:
    """Container for a single benchmark measurement."""
    algorithm: str = ""
    operation: str = ""        # "encrypt" | "decrypt"
    data_size_label: str = ""
    data_size_bytes: int = 0
    elapsed_time_s: float = 0.0
    cpu_percent: float = 0.0
    memory_peak_kb: float = 0.0
    throughput_mbps: float = 0.0
    iteration: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "operation": self.operation,
            "data_size_label": self.data_size_label,
            "data_size_bytes": self.data_size_bytes,
            "elapsed_time_ms": round(self.elapsed_time_s * 1000, 4),
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_peak_kb": round(self.memory_peak_kb, 2),
            "throughput_mbps": round(self.throughput_mbps, 4),
            "iteration": self.iteration,
        }


class BenchmarkProfiler:
    """
    Context manager that profiles a block of code.

    Parameters
    ----------
    data_size_bytes : int
        Size of the data being processed (used for throughput calc).
    """

    def __init__(self, data_size_bytes: int = 0):
        self.data_size_bytes = data_size_bytes
        self._process = psutil.Process(os.getpid())
        self.result = BenchmarkResult(data_size_bytes=data_size_bytes)

    def __enter__(self):
        # Prime CPU measurement (first call returns 0.0 on some platforms)
        self._process.cpu_percent(interval=None)

        # Start memory tracking
        tracemalloc.start()

        # Record start time
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Elapsed time
        self.result.elapsed_time_s = time.perf_counter() - self._start_time

        # CPU usage (percentage over the profiled interval)
        self.result.cpu_percent = self._process.cpu_percent(interval=None)

        # Peak memory (KB)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.result.memory_peak_kb = peak / 1024.0

        # Throughput (MB/s)
        if self.result.elapsed_time_s > 0:
            self.result.throughput_mbps = (
                (self.data_size_bytes / (1024 * 1024))
                / self.result.elapsed_time_s
            )
        else:
            self.result.throughput_mbps = float("inf")

        return False  # don't suppress exceptions


def run_benchmark(
    algorithm: str,
    operation: str,
    data_size_label: str,
    data_size_bytes: int,
    func,
    *args,
    iteration: int = 1,
    edge_delay: float = None,
    **kwargs,
) -> BenchmarkResult:
    """
    Run *func* inside a profiler and return a populated BenchmarkResult.

    Parameters
    ----------
    algorithm : str       – e.g. "AES", "ChaCha20"
    operation : str       – "encrypt" or "decrypt"
    data_size_label : str – e.g. "1KB", "1MB"
    data_size_bytes : int – raw byte count
    func : callable       – the function to profile
    *args, **kwargs       – forwarded to *func*
    iteration : int       – experiment iteration number
    edge_delay : float    – seconds to sleep after profiling to simulate
                            edge-to-cloud transmission latency (defaults
                            to config.EDGE_DELAY_SEC)

    Returns
    -------
    (BenchmarkResult, result_data)
    """
    import config as _cfg

    if edge_delay is None:
        edge_delay = _cfg.EDGE_DELAY_SEC

    with BenchmarkProfiler(data_size_bytes) as prof:
        result_data = func(*args, **kwargs)

    # Simulate edge / network transmission delay between encrypt → decrypt
    if edge_delay > 0:
        time.sleep(edge_delay)

    res = prof.result
    res.algorithm = algorithm
    res.operation = operation
    res.data_size_label = data_size_label
    res.iteration = iteration
    return res, result_data
