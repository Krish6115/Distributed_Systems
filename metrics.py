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

# ── Constants ───────────────────────────────────────────────────────
# Minimum wall-clock window (seconds) needed for psutil.cpu_times()
# to register a non-zero delta.  Windows has ~15.6 ms timer granularity,
# so we use 250 ms to guarantee several ticks and a stable reading.
_MIN_CPU_WINDOW_S = 0.25


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
        # Prime CPU measurement
        self._start_cpu_times = self._process.cpu_times()

        # Start memory tracking
        tracemalloc.start()

        # Record start time
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Elapsed time
        self.result.elapsed_time_s = time.perf_counter() - self._start_time

        # CPU usage (calculate from process CPU times)
        end_cpu_times = self._process.cpu_times()
        cpu_time_used = (end_cpu_times.user - self._start_cpu_times.user) + \
                        (end_cpu_times.system - self._start_cpu_times.system)

        if self.result.elapsed_time_s > 0:
            if cpu_time_used > 0:
                cpu_percent = (cpu_time_used / self.result.elapsed_time_s) * 100.0
            else:
                # Operation finished too fast for cpu_times() resolution.
                # Mark as -1.0 so run_benchmark() knows to calibrate.
                cpu_percent = -1.0
            self.result.cpu_percent = min(cpu_percent, 100.0 * psutil.cpu_count())
        else:
            self.result.cpu_percent = 0.0

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


def calibrate_cpu(func, args, kwargs, single_run_time_s):
    """
    Measure true CPU utilisation by repeating *func* enough times for
    psutil.cpu_times() to register a measurable delta.

    This is called automatically when a single invocation is too fast
    for the OS process-time counter (~15.6 ms resolution on Windows).

    Parameters
    ----------
    func : callable
        The encrypt / decrypt function to profile.
    args : tuple
        Positional arguments forwarded to *func*.
    kwargs : dict
        Keyword arguments forwarded to *func*.
    single_run_time_s : float
        Elapsed wall-clock time of one invocation (used to estimate
        how many repetitions are needed).

    Returns
    -------
    float
        Measured CPU utilisation as a percentage (e.g. 95.3).
    """
    process = psutil.Process(os.getpid())

    # Estimate iterations needed to fill the measurement window
    if single_run_time_s > 0:
        n_iters = max(1, int(_MIN_CPU_WINDOW_S / single_run_time_s) + 1)
    else:
        n_iters = 5000
    n_iters = min(n_iters, 50000)  # safety cap

    start_cpu = process.cpu_times()
    start_wall = time.perf_counter()

    for _ in range(n_iters):
        func(*args, **kwargs)

    wall_time = time.perf_counter() - start_wall
    end_cpu = process.cpu_times()
    cpu_delta = (end_cpu.user - start_cpu.user) + \
                (end_cpu.system - start_cpu.system)

    if wall_time > 0 and cpu_delta > 0:
        return min((cpu_delta / wall_time) * 100.0, 100.0 * psutil.cpu_count())

    # Fallback: purely CPU-bound with no I/O waits → ~100% of one core
    return 100.0


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

    res = prof.result

    # ── CPU calibration for fast operations ──────────────────────────
    # If the single run was too fast for cpu_times() resolution (marked
    # as -1.0 by the profiler), repeat the function in a tight loop for
    # ~250 ms to accumulate a measurable CPU-time delta.
    if res.cpu_percent < 0:
        res.cpu_percent = calibrate_cpu(func, args, kwargs, res.elapsed_time_s)

    # Simulate edge / network transmission delay between encrypt → decrypt
    if edge_delay > 0:
        time.sleep(edge_delay)

    res.algorithm = algorithm
    res.operation = operation
    res.data_size_label = data_size_label
    res.iteration = iteration
    return res, result_data
