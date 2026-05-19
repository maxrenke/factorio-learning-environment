"""
Summarize all result JSONs in research/results/ into a comparison table.

Usage:
    python research/scripts/summarize_results.py
"""

import json
from pathlib import Path


def load_results():
    results_dir = Path("research/results")
    runs = []
    for f in sorted(results_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            runs.append(data)
        except Exception:
            pass
    return runs


def print_matrix(runs):
    if not runs:
        print("No results found in research/results/")
        return

    # Group by model + condition
    cells = {}
    for r in runs:
        key = (r.get("model", "?"), r.get("condition", "?"))
        rate = r.get("summary", {}).get("completion_rate", 0)
        n = r.get("summary", {}).get("completed", 0)
        total = r.get("summary", {}).get("total", 24)
        cells[key] = (n, total, rate)

    models = sorted(set(k[0] for k in cells))
    conditions = sorted(set(k[1] for k in cells))

    # Header
    col_w = 18
    print(f"\n{'Model':<35} " + "  ".join(f"{c:<{col_w}}" for c in conditions))
    print("-" * (35 + col_w * len(conditions) + 4))

    for model in models:
        row = f"{model:<35} "
        for cond in conditions:
            cell = cells.get((model, cond))
            if cell:
                n, total, rate = cell
                row += f"  {n}/{total} ({rate:.0%})".ljust(col_w)
            else:
                row += f"  {'--':<{col_w-2}}"
        print(row)

    print(f"\nFLE paper baseline (Claude 3.5-Sonnet, zero_shot): 7/24 (29%)")


def main():
    runs = load_results()
    print(f"Found {len(runs)} result files")
    print_matrix(runs)

    # Also dump per-task detail for the most recent run
    if runs:
        latest = max(runs, key=lambda r: r.get("date", ""))
        print(f"\n--- Per-task detail: {latest['run_id']} ---")
        for task, result in latest.get("tasks", {}).items():
            status = "PASS" if result["completed"] else "fail"
            print(f"  {task:<40} {status}  score={result['score']}")


if __name__ == "__main__":
    main()
