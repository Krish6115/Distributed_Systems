"""
main.py — CLI entry point for the edge‑device encryption benchmark.

Usage examples:
    # Run full benchmark with defaults (all algorithms, all sizes, 5 iterations)
    python main.py

    # Custom run
    python main.py --algorithms AES ChaCha20 --sizes 1KB 10KB --iterations 10

    # Only generate graphs from existing results
    python main.py --graphs-only

    # Specify output directory
    python main.py --output results_v2
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from typing import List, Dict

import pandas as pd

from tabulate import tabulate

import config
from data_generator import generate_iot_data
from metrics import run_benchmark, BenchmarkResult
from edge_simulator import edge_pipeline
from visualization import generate_all_graphs

# ── Algorithm registry ──────────────────────────────────────────────
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
#  Logging setup
# ═══════════════════════════════════════════════════════════════════

def _setup_logging(log_file: str):
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode="w", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ═══════════════════════════════════════════════════════════════════
#  Core benchmark logic
# ═══════════════════════════════════════════════════════════════════

def run_experiments(
    algorithms: List[str],
    data_sizes: Dict[str, int],
    iterations: int,
) -> List[Dict]:
    """
    Run the full experiment matrix and return a list of result dicts.
    """
    all_results: List[Dict] = []
    total_runs = len(algorithms) * len(data_sizes) * iterations * 2  # ×2 for enc+dec
    current_run = 0

    logging.info("=" * 70)
    logging.info("  EDGE DEVICE ENCRYPTION BENCHMARK")
    logging.info("=" * 70)
    logging.info(f"  Algorithms : {', '.join(algorithms)}")
    logging.info(f"  Data sizes : {', '.join(data_sizes.keys())}")
    logging.info(f"  Iterations : {iterations}")
    logging.info(f"  Total runs : {total_runs}")
    logging.info("=" * 70)

    for algo_name in algorithms:
        module = ALGO_MODULES[algo_name]
        key = module.generate_key()

        # ── Warmup: prime the module to avoid cold-start overhead ──
        # The first-ever call loads C extensions, triggers page faults,
        # and initialises tracemalloc — all of which inflate timing.
        # A single throwaway encrypt+decrypt eliminates this artefact.
        _warmup_data = generate_iot_data(64)
        _wn, _wc, _wt = module.encrypt(_warmup_data, key)
        module.decrypt(_wn, _wc, _wt, key)

        logging.info(f"\n{'─' * 50}")
        logging.info(f"  Algorithm: {algo_name}  (key={len(key)*8} bits)")
        logging.info(f"{'─' * 50}")

        for size_label, size_bytes in data_sizes.items():
            # Generate data once per size (same data for fair comparison)
            data = generate_iot_data(size_bytes)
            logging.info(f"  [{algo_name}] data_size={size_label} ({size_bytes} bytes)")

            for i in range(1, iterations + 1):
                # ── Encryption ──
                current_run += 1
                enc_result, enc_output = run_benchmark(
                    algo_name,
                    "encrypt",
                    size_label,
                    size_bytes,
                    module.encrypt,
                    data, key,
                    iteration=i,
                )
                nonce, ciphertext, tag = enc_output
                all_results.append(enc_result.to_dict())
                _progress(current_run, total_runs, algo_name, "enc", size_label, i, enc_result)

                # ── Decryption ──
                current_run += 1
                dec_result, dec_output = run_benchmark(
                    algo_name,
                    "decrypt",
                    size_label,
                    size_bytes,
                    module.decrypt,
                    nonce, ciphertext, tag, key,
                    iteration=i,
                )
                all_results.append(dec_result.to_dict())
                _progress(current_run, total_runs, algo_name, "dec", size_label, i, dec_result)

                # ── Integrity check ──
                assert dec_output == data, (
                    f"INTEGRITY FAILURE: {algo_name} {size_label} iter {i}"
                )

        # Run full edge pipeline once per algorithm for demonstration
        pipeline_result = edge_pipeline(
            module.encrypt, module.decrypt, key,
            generate_iot_data(1024),
        )
        logging.info(
            f"  [{algo_name}] Edge pipeline integrity: "
            f"{'✓ PASS' if pipeline_result['integrity_ok'] else '✗ FAIL'}"
        )

    return all_results


def _progress(run, total, algo, op, size, iteration, result: BenchmarkResult):
    pct = run / total * 100
    logging.info(
        f"  [{run:>4}/{total}] {pct:5.1f}%  {algo:<10} {op:<4} "
        f"{size:<6} iter={iteration}  "
        f"time={result.elapsed_time_s*1000:>10.3f}ms  "
        f"throughput={result.throughput_mbps:>8.2f}MB/s"
    )


# ═══════════════════════════════════════════════════════════════════
#  Result storage
# ═══════════════════════════════════════════════════════════════════

def save_results(results: List[Dict], output_dir: str):
    """Save results to CSV and JSON."""
    os.makedirs(output_dir, exist_ok=True)

    # JSON
    json_path = os.path.join(output_dir, "benchmark_results.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    logging.info(f"  📄 Results saved to {json_path}")

    # CSV
    csv_path = os.path.join(output_dir, "benchmark_results.csv")
    if results:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        logging.info(f"  📄 Results saved to {csv_path}")


# ═══════════════════════════════════════════════════════════════════
#  Summary report
# ═══════════════════════════════════════════════════════════════════

def print_summary(results: List[Dict]):
    """Print a nicely formatted console summary using pandas aggregation."""
    print("\n" + "=" * 80)
    print("  [RESULTS]  BENCHMARK SUMMARY")
    print("=" * 80)

    # ── Build DataFrame & aggregate via pandas (idiomatic, scalable) ──
    df = pd.DataFrame(results)

    agg_metrics = {
        "elapsed_time_ms": "mean",
        "cpu_percent":     "mean",
        "memory_peak_kb":  "mean",
        "throughput_mbps":  "mean",
    }

    def _format_table(op: str) -> list:
        """Return a tabulate-ready list for the given operation."""
        subset = df[df["operation"] == op]
        if subset.empty:
            return []
        grouped = (
            subset
            .groupby("algorithm", sort=False)
            .agg(agg_metrics)
            .reindex(config.ALGORITHMS)     # preserve canonical order
            .dropna(how="all")
        )
        rows = []
        for algo, row in grouped.iterrows():
            rows.append([
                algo,
                f"{row['elapsed_time_ms']:.3f}",
                f"{row['cpu_percent']:.1f}",
                f"{row['memory_peak_kb']:.1f}",
                f"{row['throughput_mbps']:.2f}",
            ])
        return rows

    headers = ["Algorithm", "Avg Time (ms)", "Avg CPU %",
               "Avg Mem (KB)", "Avg Throughput (MB/s)"]

    # ── Encryption summary ──
    print("\n  >> ENCRYPTION (averaged across all sizes & iterations)\n")
    print(tabulate(_format_table("encrypt"), headers=headers,
                   tablefmt="fancy_grid", numalign="right"))

    # ── Decryption summary ──
    print("\n  >> DECRYPTION (averaged across all sizes & iterations)\n")
    print(tabulate(_format_table("decrypt"), headers=headers,
                   tablefmt="fancy_grid", numalign="right"))

    # ── Best-algorithm recommendation (pandas-driven) ──
    print("\n" + "-" * 80)
    print("  [TROPHY]  RECOMMENDATION FOR EDGE DEVICES")
    print("-" * 80)

    enc_df = df[df["operation"] == "encrypt"]
    if not enc_df.empty:
        enc_agg = (
            enc_df
            .groupby("algorithm")
            .agg(agg_metrics)
        )
        best_speed = enc_agg["throughput_mbps"].idxmax()
        best_mem   = enc_agg["memory_peak_kb"].idxmin()
        best_cpu   = enc_agg["cpu_percent"].idxmin()

        print(f"\n  [FAST] Fastest throughput  : {best_speed}")
        print(f"  [MEM]  Lowest memory      : {best_mem}")
        print(f"  [CPU]  Lowest CPU usage   : {best_cpu}")

        # ── Overall Best Algorithm (composite scoring) ──
        # Rank each algorithm across 4 metrics; lower rank = better
        # throughput: higher is better; time, cpu, memory: lower is better
        scores = {}
        algos = list(enc_agg.index)
        rank_throughput = enc_agg["throughput_mbps"].rank(ascending=False)
        rank_time       = enc_agg["elapsed_time_ms"].rank(ascending=True)
        rank_cpu        = enc_agg["cpu_percent"].rank(ascending=True)
        rank_mem        = enc_agg["memory_peak_kb"].rank(ascending=True)

        for algo in algos:
            scores[algo] = (rank_throughput[algo] + rank_time[algo] +
                            rank_cpu[algo] + rank_mem[algo])

        overall_best = min(scores, key=scores.get)

        print(f"\n  {'='*60}")
        print(f"  [BEST OVERALL] >>> {overall_best} <<<")
        print(f"  {'='*60}")
        print(f"  (Composite score based on throughput, latency, CPU, memory)")
        print(f"  Scores: ", end="")
        for algo in algos:
            marker = " *** " if algo == overall_best else "     "
            print(f"{marker}{algo}={scores[algo]:.1f}", end="")
        print()

    print()
    print("  [TIP] For resource-constrained edge devices:")
    print("     - AES-256-GCM excels on hardware with AES-NI support")
    print("     - ChaCha20-Poly1305 is optimal for software-only ARM/RISC-V")
    print("     - SPECK offers the best speed-to-gate-count ratio")
    print("     - PRESENT is designed for ultra-low gate count (RFID/smart cards)")
    print("=" * 80 + "\n")


# ═══════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="Edge Device Encryption Algorithm Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --algorithms AES ChaCha20 --sizes 1KB 10KB --iterations 10
  python main.py --graphs-only
        """,
    )
    parser.add_argument(
        "--algorithms", "-a",
        nargs="+",
        choices=config.ALGORITHMS,
        default=config.ALGORITHMS,
        help="Algorithms to benchmark (default: all four)",
    )
    parser.add_argument(
        "--sizes", "-s",
        nargs="+",
        choices=list(config.DATA_SIZES.keys()),
        default=list(config.DATA_SIZES.keys()),
        help="Data sizes to test (default: 1KB 10KB 100KB)",
    )
    parser.add_argument(
        "--iterations", "-n",
        type=int,
        default=config.DEFAULT_ITERATIONS,
        help=f"Repetitions per experiment (default: {config.DEFAULT_ITERATIONS})",
    )
    parser.add_argument(
        "--output", "-o",
        default=config.RESULTS_DIR,
        help=f"Output directory (default: {config.RESULTS_DIR})",
    )
    parser.add_argument(
        "--graphs-only",
        action="store_true",
        help="Skip benchmarks; only regenerate graphs from existing JSON",
    )
    parser.add_argument(
        "--no-graphs",
        action="store_true",
        help="Run benchmarks but skip graph generation",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    log_file = os.path.join(args.output, "experiment.log")
    _setup_logging(log_file)

    if args.graphs_only:
        json_path = os.path.join(args.output, "benchmark_results.json")
        if not os.path.exists(json_path):
            logging.error(f"No results found at {json_path}. Run benchmarks first.")
            sys.exit(1)
        with open(json_path) as f:
            results = json.load(f)
        # Update graphs dir for custom output
        config.GRAPHS_DIR = os.path.join(args.output, "graphs")
        config.RESULTS_JSON = json_path
        generate_all_graphs(results)
        return

    # Build the size map from selected sizes
    selected_sizes = {k: config.DATA_SIZES[k] for k in args.sizes}

    start_time = time.time()
    results = run_experiments(args.algorithms, selected_sizes, args.iterations)
    elapsed = time.time() - start_time

    logging.info(f"\n  Total benchmark time: {elapsed:.2f}s")

    # Save
    save_results(results, args.output)

    # Summary
    print_summary(results)

    # Graphs
    if not args.no_graphs:
        config.GRAPHS_DIR = os.path.join(args.output, "graphs")
        config.RESULTS_JSON = os.path.join(args.output, "benchmark_results.json")
        generate_all_graphs(results)


if __name__ == "__main__":
    main()
