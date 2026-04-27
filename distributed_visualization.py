"""
distributed_visualization.py — Graphs for distributed edge computing simulation.

Generates publication-quality charts that visualise how encryption algorithms
scale across different deployment sizes (number of edge nodes).

This module complements (and does NOT modify) the existing visualization.py,
which handles single-node benchmark graphs.

Graphs generated
----------------
    1. Performance vs Number of Nodes       (line chart, log Y)
    2. Throughput vs Area Size              (bar chart, log Y + labels)
    3. Latency vs Node Count               (line chart, log Y)
    4. Algorithm comparison under load      (grouped bar, log Y + labels)
    5. Load distribution across nodes       (box plot, log Y)
    6. Scalability summary dashboard        (2x2 composite, log Y)

NOTE: All charts use logarithmic Y-axes where the value range across
algorithms exceeds 100x.  Numeric value labels are added to bar charts
so that no algorithm's bar is invisible regardless of scale differences.
"""

import os
from collections import defaultdict
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# -- Style constants ----------------------------------------------------------
COLORS = {
    "AES":      "#2563eb",
    "ChaCha20": "#16a34a",
    "PRESENT":  "#dc2626",
    "SPECK":    "#9333ea",
}
MARKERS = {"AES": "o", "ChaCha20": "s", "PRESENT": "^", "SPECK": "D"}

FONT = {"family": "sans-serif", "size": 11}
matplotlib.rc("font", **FONT)


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _needs_log_scale(values_list):
    """Return True if the value range exceeds 100x."""
    flat = [v for v in values_list if v > 0]
    if len(flat) < 2:
        return False
    return max(flat) / min(flat) > 100


def _add_bar_labels(ax, bars, fontsize=7):
    """Add value labels on top of each bar."""
    for bar in bars:
        h = bar.get_height()
        if h <= 0:
            continue
        if h >= 1000:
            label = f"{h:,.0f}"
        elif h >= 1:
            label = f"{h:.2f}"
        elif h >= 0.001:
            label = f"{h:.4f}"
        else:
            label = f"{h:.2e}"
        ax.text(
            bar.get_x() + bar.get_width() / 2, h, label,
            ha="center", va="bottom", fontsize=fontsize,
            fontweight="bold", rotation=45,
        )


# =============================================================================
#  1. Performance (Encryption Time) vs Number of Nodes
# =============================================================================

def plot_performance_vs_nodes(results: List[Dict], output_dir: str):
    """
    Line chart: average encryption time per node vs total node count.
    One line per algorithm.  Uses log Y when range is large.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    algo_data = defaultdict(lambda: {"nodes": [], "latency": []})
    for r in results:
        algo_data[r["algorithm"]]["nodes"].append(r["node_count"])
        algo_data[r["algorithm"]]["latency"].append(r["avg_latency_ms"])

    all_latencies = [r["avg_latency_ms"] for r in results if r["avg_latency_ms"] > 0]

    for algo, d in algo_data.items():
        ax.plot(
            d["nodes"], d["latency"],
            marker=MARKERS.get(algo, "o"),
            color=COLORS.get(algo, "#888"),
            linewidth=2, markersize=8,
            label=algo,
        )
        # Add value annotations on each point
        for x_val, y_val in zip(d["nodes"], d["latency"]):
            label = f"{y_val:.2f}" if y_val >= 0.01 else f"{y_val:.4f}"
            ax.annotate(label, (x_val, y_val), textcoords="offset points",
                        xytext=(0, 8), ha="center", fontsize=7, fontweight="bold",
                        color=COLORS.get(algo, "#888"))

    ax.set_xlabel("Number of Edge Nodes (N)", fontweight="bold")
    ax.set_ylabel("Avg Encryption Latency per Node (ms)", fontweight="bold")
    ax.set_title("Encryption Performance vs Number of Nodes", fontweight="bold", fontsize=14)
    ax.legend(framealpha=0.9)
    ax.grid(alpha=0.3)
    ax.set_xscale("log")
    if _needs_log_scale(all_latencies):
        ax.set_yscale("log")
    fig.tight_layout()

    _ensure_dir(output_dir)
    fig.savefig(os.path.join(output_dir, "performance_vs_nodes.png"), dpi=150)
    plt.close(fig)
    print("  [OK] saved performance_vs_nodes.png")


# =============================================================================
#  2. Throughput vs Area Size
# =============================================================================

def plot_throughput_vs_area(results: List[Dict], output_dir: str):
    """Bar chart: total system throughput at each area scale.  Log Y + labels."""
    fig, ax = plt.subplots(figsize=(10, 6))

    algo_data = defaultdict(lambda: {"areas": [], "throughput": []})
    for r in results:
        algo_data[r["algorithm"]]["areas"].append(r["area_km2"])
        algo_data[r["algorithm"]]["throughput"].append(r["total_throughput_mbps"])

    algorithms = list(algo_data.keys())
    areas = sorted(set(r["area_km2"] for r in results))
    n_algos = len(algorithms)
    bar_width = 0.18
    x = np.arange(len(areas))

    all_vals = [r["total_throughput_mbps"] for r in results if r["total_throughput_mbps"] > 0]
    use_log = _needs_log_scale(all_vals)

    all_bars = []
    for i, algo in enumerate(algorithms):
        area_to_tp = dict(zip(algo_data[algo]["areas"], algo_data[algo]["throughput"]))
        vals = [area_to_tp.get(a, 0) for a in areas]
        bars = ax.bar(
            x + i * bar_width, vals, bar_width,
            label=algo, color=COLORS.get(algo, "#888"),
            edgecolor="white", linewidth=0.5,
        )
        all_bars.extend(bars)

    if use_log:
        ax.set_yscale("log")

    _add_bar_labels(ax, all_bars, fontsize=7)

    ax.set_xlabel("Area (km2)", fontweight="bold")
    ax.set_ylabel("Total System Throughput (MB/s)", fontweight="bold")
    ax.set_title("System Throughput vs Deployment Area", fontweight="bold", fontsize=14)
    ax.set_xticks(x + bar_width * (n_algos - 1) / 2)
    ax.set_xticklabels([f"{a} km2" for a in areas])
    ax.legend(framealpha=0.9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    _ensure_dir(output_dir)
    fig.savefig(os.path.join(output_dir, "throughput_vs_area.png"), dpi=150)
    plt.close(fig)
    print("  [OK] saved throughput_vs_area.png")


# =============================================================================
#  3. Latency vs Node Count
# =============================================================================

def plot_latency_vs_nodes(results: List[Dict], output_dir: str):
    """Line chart with error bars: avg +/- std latency vs node count.  Log Y."""
    fig, ax = plt.subplots(figsize=(10, 6))

    algo_data = defaultdict(lambda: {"nodes": [], "avg": [], "std": []})
    for r in results:
        algo_data[r["algorithm"]]["nodes"].append(r["node_count"])
        algo_data[r["algorithm"]]["avg"].append(r["avg_latency_ms"])
        algo_data[r["algorithm"]]["std"].append(r["latency_std_ms"])

    all_latencies = [r["avg_latency_ms"] for r in results if r["avg_latency_ms"] > 0]

    for algo, d in algo_data.items():
        ax.errorbar(
            d["nodes"], d["avg"], yerr=d["std"],
            marker=MARKERS.get(algo, "o"),
            color=COLORS.get(algo, "#888"),
            linewidth=2, markersize=8, capsize=4,
            label=algo,
        )

    ax.set_xlabel("Number of Edge Nodes (N)", fontweight="bold")
    ax.set_ylabel("Latency (ms) -- avg +/- std", fontweight="bold")
    ax.set_title("Encryption Latency vs Node Count", fontweight="bold", fontsize=14)
    ax.legend(framealpha=0.9)
    ax.grid(alpha=0.3)
    ax.set_xscale("log")
    if _needs_log_scale(all_latencies):
        ax.set_yscale("log")
    fig.tight_layout()

    _ensure_dir(output_dir)
    fig.savefig(os.path.join(output_dir, "latency_vs_nodes.png"), dpi=150)
    plt.close(fig)
    print("  [OK] saved latency_vs_nodes.png")


# =============================================================================
#  4. Algorithm Comparison Under Distributed Load
# =============================================================================

def plot_algorithm_comparison(results: List[Dict], output_dir: str):
    """Grouped bar chart: algorithms across all scenarios.  Log Y + labels."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(
        "Algorithm Comparison Under Distributed Load",
        fontweight="bold", fontsize=15, y=1.02,
    )

    metrics = [
        ("avg_latency_ms",        "Avg Latency (ms)"),
        ("total_throughput_mbps", "Total Throughput (MB/s)"),
        ("scalability_factor",    "Scalability Factor"),
    ]

    scenarios = sorted(set(r["scenario"] for r in results))
    algorithms = sorted(set(r["algorithm"] for r in results))
    bar_width = 0.18
    x = np.arange(len(scenarios))

    for ax_idx, (metric_key, metric_label) in enumerate(metrics):
        ax = axes[ax_idx]
        all_metric_vals = [r[metric_key] for r in results if r[metric_key] > 0]
        use_log = _needs_log_scale(all_metric_vals)

        all_bars = []
        for i, algo in enumerate(algorithms):
            vals = []
            for scenario in scenarios:
                match = [r for r in results if r["scenario"] == scenario and r["algorithm"] == algo]
                vals.append(match[0][metric_key] if match else 0)
            bars = ax.bar(
                x + i * bar_width, vals, bar_width,
                label=algo, color=COLORS.get(algo, "#888"),
                edgecolor="white", linewidth=0.5,
            )
            all_bars.extend(bars)

        if use_log:
            ax.set_yscale("log")

        _add_bar_labels(ax, all_bars, fontsize=6)

        ax.set_xlabel("Scenario", fontweight="bold")
        ax.set_ylabel(metric_label, fontweight="bold")
        ax.set_title(metric_label, fontweight="bold", fontsize=12)
        ax.set_xticks(x + bar_width * (len(algorithms) - 1) / 2)
        ax.set_xticklabels(scenarios, fontsize=9)
        ax.grid(axis="y", alpha=0.3)

    # Single legend
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=11, framealpha=0.9)
    fig.tight_layout(rect=[0, 0.06, 1, 0.96])

    _ensure_dir(output_dir)
    fig.savefig(os.path.join(output_dir, "algorithm_comparison.png"), dpi=150)
    plt.close(fig)
    print("  [OK] saved algorithm_comparison.png")


# =============================================================================
#  5. Load Distribution (Box plot of per-node encryption times)
# =============================================================================

def plot_load_distribution(detailed_results, output_dir: str):
    """
    Box plot showing distribution of per-node encryption times for
    each (scenario, algorithm) combination.  Uses log Y when range is large.
    """
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(
        "Load Distribution Across Edge Nodes",
        fontweight="bold", fontsize=15, y=1.02,
    )

    # Group by scenario
    scenario_groups = defaultdict(list)
    for dr in detailed_results:
        scenario_groups[dr.scenario].append(dr)

    for ax_idx, (scenario, drs) in enumerate(sorted(scenario_groups.items())):
        if ax_idx >= 3:
            break
        ax = axes[ax_idx]
        data_list = []
        labels = []
        colors_list = []
        all_times = []
        for dr in sorted(drs, key=lambda d: d.algorithm):
            enc_times_ms = [nr.encrypt_time_s * 1000 for nr in dr.node_results]
            data_list.append(enc_times_ms)
            labels.append(dr.algorithm)
            colors_list.append(COLORS.get(dr.algorithm, "#888"))
            all_times.extend(enc_times_ms)

        bp = ax.boxplot(
            data_list, labels=labels, patch_artist=True,
            medianprops=dict(color="black", linewidth=2),
        )
        for patch, color in zip(bp["boxes"], colors_list):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        if _needs_log_scale(all_times):
            ax.set_yscale("log")

        ax.set_title(f"{scenario}\n(N={drs[0].node_count} nodes)", fontweight="bold", fontsize=11)
        ax.set_ylabel("Encryption Time (ms)", fontweight="bold")
        ax.grid(axis="y", alpha=0.3)

    fig.tight_layout(rect=[0, 0, 1, 0.96])

    _ensure_dir(output_dir)
    fig.savefig(os.path.join(output_dir, "load_distribution.png"), dpi=150)
    plt.close(fig)
    print("  [OK] saved load_distribution.png")


# =============================================================================
#  6. Scalability Summary Dashboard (2x2)
# =============================================================================

def plot_scalability_dashboard(results: List[Dict], output_dir: str):
    """2x2 composite figure summarising key scalability metrics.  Log Y."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        "Distributed Encryption -- Scalability Dashboard",
        fontweight="bold", fontsize=16, y=0.98,
    )

    algo_data = defaultdict(lambda: {"nodes": [], "throughput": [], "latency": [], "scale": []})
    for r in results:
        algo_data[r["algorithm"]]["nodes"].append(r["node_count"])
        algo_data[r["algorithm"]]["throughput"].append(r["total_throughput_mbps"])
        algo_data[r["algorithm"]]["latency"].append(r["avg_latency_ms"])
        algo_data[r["algorithm"]]["scale"].append(r["scalability_factor"])

    def _plot_line(ax, y_key, ylabel, title):
        all_vals = []
        for algo, d in algo_data.items():
            ax.plot(d["nodes"], d[y_key], marker=MARKERS.get(algo, "o"),
                    color=COLORS.get(algo, "#888"), linewidth=2, markersize=7, label=algo)
            all_vals.extend(d[y_key])
        ax.set_xlabel("Nodes")
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontweight="bold")
        ax.set_xscale("log")
        if _needs_log_scale([v for v in all_vals if v > 0]):
            ax.set_yscale("log")
        ax.grid(alpha=0.3)

    # Top-left: throughput vs nodes
    _plot_line(axes[0][0], "throughput", "Total Throughput (MB/s)", "Throughput vs Nodes")

    # Top-right: latency vs nodes
    _plot_line(axes[0][1], "latency", "Avg Latency (ms)", "Latency vs Nodes")

    # Bottom-left: scalability factor vs nodes
    ax = axes[1][0]
    for algo, d in algo_data.items():
        ax.plot(d["nodes"], d["scale"], marker=MARKERS.get(algo, "o"),
                color=COLORS.get(algo, "#888"), linewidth=2, markersize=7, label=algo)
    all_nodes = sorted(set(r["node_count"] for r in results))
    ax.plot(all_nodes, all_nodes, "--", color="#999", linewidth=1, label="Ideal (linear)")
    ax.set_xlabel("Nodes")
    ax.set_ylabel("Scalability Factor")
    ax.set_title("Scalability Factor vs Nodes", fontweight="bold")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.grid(alpha=0.3)

    # Bottom-right: wall time vs nodes
    ax = axes[1][1]
    wall_vals = []
    for algo in algo_data:
        wall_data = [(r["node_count"], r["total_wall_time_s"])
                     for r in results if r["algorithm"] == algo]
        wall_data.sort()
        nodes, times = zip(*wall_data) if wall_data else ([], [])
        ax.plot(nodes, times, marker=MARKERS.get(algo, "o"),
                color=COLORS.get(algo, "#888"), linewidth=2, markersize=7, label=algo)
        wall_vals.extend(times)
    ax.set_xlabel("Nodes")
    ax.set_ylabel("Total Wall Time (s)")
    ax.set_title("Wall Time vs Nodes", fontweight="bold")
    ax.set_xscale("log")
    if _needs_log_scale([v for v in wall_vals if v > 0]):
        ax.set_yscale("log")
    ax.grid(alpha=0.3)

    # Single legend
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=11, framealpha=0.9)
    fig.tight_layout(rect=[0, 0.06, 1, 0.95])

    _ensure_dir(output_dir)
    fig.savefig(os.path.join(output_dir, "scalability_dashboard.png"), dpi=150)
    plt.close(fig)
    print("  [OK] saved scalability_dashboard.png")


# =============================================================================
#  Public API
# =============================================================================

def generate_all_distributed_graphs(
    summary_results: List[Dict],
    detailed_results=None,
    output_dir: str = "results/distributed_graphs",
):
    """
    Generate the complete suite of distributed simulation graphs.

    Parameters
    ----------
    summary_results : list of dict
        System-level results (from DistributedResult.to_dict()).
    detailed_results : list of DistributedResult, optional
        Full objects with per-node data (needed for load distribution plot).
    output_dir : str
        Directory for graph output.
    """
    print("\n[GRAPHS] Generating distributed simulation graphs...")
    plot_performance_vs_nodes(summary_results, output_dir)
    plot_throughput_vs_area(summary_results, output_dir)
    plot_latency_vs_nodes(summary_results, output_dir)
    plot_algorithm_comparison(summary_results, output_dir)
    plot_scalability_dashboard(summary_results, output_dir)

    if detailed_results is not None:
        plot_load_distribution(detailed_results, output_dir)

    print(f"   All distributed graphs saved to {output_dir}/\n")
