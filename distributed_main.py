"""
distributed_main.py — CLI entry point for the distributed edge computing simulation.

This is the NEW entry point for the distributed simulation layer.  The original
main.py remains untouched and continues to work for single-node benchmarks.

Usage examples
──────────────
    # Run all predefined scenarios (small / medium / large) with all algorithms
    python distributed_main.py

    # Custom single scenario
    python distributed_main.py --area 50 --density 20

    # Specific algorithms only
    python distributed_main.py --algorithms AES ChaCha20

    # Regenerate graphs from existing results
    python distributed_main.py --graphs-only

    # Custom output directory
    python distributed_main.py --output results_v2
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
from distributed_config import SCENARIOS, compute_node_count, DEFAULT_DATA_TOTAL_BYTES
from distributed_simulation import run_all_scenarios, DistributedSimulation, ALGO_MODULES
from distributed_visualization import generate_all_distributed_graphs
from architecture_diagram import generate_architecture_diagram


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
#  Result storage
# ═══════════════════════════════════════════════════════════════════

def save_distributed_results(
    summary_results: List[Dict],
    flat_rows: List[Dict],
    output_dir: str,
):
    """Save distributed simulation results to JSON and CSV."""
    os.makedirs(output_dir, exist_ok=True)

    # JSON — system-level summary (one entry per scenario × algorithm)
    json_path = os.path.join(output_dir, "distributed_results.json")
    with open(json_path, "w") as f:
        json.dump(summary_results, f, indent=2)
    logging.info(f"  [FILE] Summary results saved to {json_path}")

    # CSV — flat table (one row per node per scenario × algorithm)
    csv_path = os.path.join(output_dir, "distributed_results.csv")
    if flat_rows:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=flat_rows[0].keys())
            writer.writeheader()
            writer.writerows(flat_rows)
        logging.info(f"  [FILE] Per-node results saved to {csv_path}")


# ═══════════════════════════════════════════════════════════════════
#  Summary report
# ═══════════════════════════════════════════════════════════════════

def print_distributed_summary(summary_results: List[Dict]):
    """Print a formatted console summary of the distributed simulation."""
    print("\n" + "=" * 90)
    print("  DISTRIBUTED EDGE COMPUTING SIMULATION -- SUMMARY")
    print("=" * 90)

    headers = [
        "Scenario", "Algorithm", "Nodes",
        "Throughput (MB/s)", "Avg Latency (ms)",
        "Scalability", "Wall Time (s)", "Integrity",
    ]

    rows = []
    for r in summary_results:
        rows.append([
            r["scenario"],
            r["algorithm"],
            r["node_count"],
            f"{r['total_throughput_mbps']:.2f}",
            f"{r['avg_latency_ms']:.3f}",
            f"{r['scalability_factor']:.2f}",
            f"{r['total_wall_time_s']:.2f}",
            "PASS" if r["all_integrity_ok"] else "FAIL",
        ])

    print("\n" + tabulate(rows, headers=headers, tablefmt="grid", numalign="right"))

    # ── Best-algorithm recommendation per scenario ──
    print("\n" + "-" * 90)
    print("  SCALABILITY RECOMMENDATIONS")
    print("-" * 90)

    df = pd.DataFrame(summary_results)
    for scenario in df["scenario"].unique():
        subset = df[df["scenario"] == scenario]
        best_throughput = subset.loc[subset["total_throughput_mbps"].idxmax(), "algorithm"]
        best_latency = subset.loc[subset["avg_latency_ms"].idxmin(), "algorithm"]
        best_scale = subset.loc[subset["scalability_factor"].idxmax(), "algorithm"]
        n = subset.iloc[0]["node_count"]

        print(f"\n  [{scenario}] ({n} nodes)")
        print(f"    > Highest throughput  : {best_throughput}")
        print(f"    > Lowest latency      : {best_latency}")
        print(f"    > Best scalability    : {best_scale}")

    print("\n" + "=" * 90)
    print("  Key Insights:")
    print("     - Algorithms with low per-node overhead scale more linearly")
    print("     - PRESENT/SPECK (lightweight ciphers) may show lower per-node")
    print("       latency but similar total throughput to AES/ChaCha20")
    print("     - Scalability factor close to N indicates near-ideal parallelism")
    print("     - High load_balance_std indicates uneven work distribution")
    print("=" * 90 + "\n")


# ═══════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="Distributed Edge Computing Encryption Simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scaling Model:
  N = A × D  (Nodes = Area_km² × Density_nodes/km²)

Predefined Scenarios:
  Small  : A=1 km²,   D=5   → N=5    nodes
  Medium : A=10 km²,  D=10  → N=100  nodes
  Large  : A=100 km², D=10  → N=1000 nodes

Examples:
  python distributed_main.py
  python distributed_main.py --area 50 --density 20
  python distributed_main.py --algorithms AES ChaCha20
  python distributed_main.py --graphs-only
        """,
    )
    parser.add_argument(
        "--algorithms", "-a",
        nargs="+",
        choices=list(ALGO_MODULES.keys()),
        default=list(ALGO_MODULES.keys()),
        help="Algorithms to simulate (default: all four)",
    )
    parser.add_argument(
        "--area",
        type=float, default=None,
        help="Custom area in km² (overrides predefined scenarios)",
    )
    parser.add_argument(
        "--density",
        type=float, default=None,
        help="Custom node density (nodes/km²)",
    )
    parser.add_argument(
        "--data-size",
        type=int, default=DEFAULT_DATA_TOTAL_BYTES,
        help=f"Total data bytes to distribute (default: {DEFAULT_DATA_TOTAL_BYTES})",
    )
    parser.add_argument(
        "--output", "-o",
        default=config.RESULTS_DIR,
        help=f"Output directory (default: {config.RESULTS_DIR})",
    )
    parser.add_argument(
        "--graphs-only",
        action="store_true",
        help="Skip simulation; only regenerate graphs from existing JSON",
    )
    parser.add_argument(
        "--no-graphs",
        action="store_true",
        help="Run simulation but skip graph generation",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    dist_output = os.path.join(args.output, "distributed")
    graphs_dir = os.path.join(args.output, "distributed_graphs")
    log_file = os.path.join(dist_output, "distributed_experiment.log")
    _setup_logging(log_file)

    # ── Graphs-only mode ──
    if args.graphs_only:
        json_path = os.path.join(dist_output, "distributed_results.json")
        if not os.path.exists(json_path):
            logging.error(f"No results found at {json_path}. Run simulation first.")
            sys.exit(1)
        with open(json_path) as f:
            summary_results = json.load(f)
        generate_all_distributed_graphs(summary_results, output_dir=graphs_dir)
        generate_architecture_diagram(output_dir=graphs_dir)
        return

    # ── Build scenario(s) ──
    if args.area is not None:
        # Custom single scenario
        density = args.density or 10.0
        n = compute_node_count(args.area, density)
        custom_scenarios = {
            "custom": {
                "label": f"Custom ({args.area} km², {density}/km²)",
                "area_km2": args.area,
                "density": density,
                "description": f"User-defined: {n} nodes",
            }
        }
        scenarios = custom_scenarios
    else:
        scenarios = SCENARIOS

    # ── Run simulation ──
    logging.info("=" * 70)
    logging.info("  DISTRIBUTED EDGE COMPUTING SIMULATION")
    logging.info("=" * 70)
    logging.info(f"  Algorithms  : {', '.join(args.algorithms)}")
    logging.info(f"  Scenarios  : {', '.join(s['label'] for s in scenarios.values())}")
    logging.info(f"  Data size   : {args.data_size} bytes total")
    logging.info("=" * 70)

    start_time = time.time()
    distributed_results = run_all_scenarios(
        algorithms=args.algorithms,
        scenarios=scenarios,
        total_data_bytes=args.data_size,
    )
    elapsed = time.time() - start_time

    logging.info(f"\n  Total simulation time: {elapsed:.2f}s")

    # ── Collect results ──
    summary_results = [dr.to_dict() for dr in distributed_results]
    flat_rows = []
    for dr in distributed_results:
        flat_rows.extend(dr.to_flat_rows())

    # ── Save ──
    save_distributed_results(summary_results, flat_rows, dist_output)

    # ── Summary ──
    print_distributed_summary(summary_results)

    # ── Graphs ──
    if not args.no_graphs:
        generate_all_distributed_graphs(
            summary_results,
            detailed_results=distributed_results,
            output_dir=graphs_dir,
        )
        generate_architecture_diagram(output_dir=graphs_dir)


if __name__ == "__main__":
    main()
