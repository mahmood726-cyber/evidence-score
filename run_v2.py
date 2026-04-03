"""
EvidenceScore v2.0 — Orchestrator
Runs the full pipeline: score all MAs, sensitivity analysis, before/after, save artifacts.
"""

import io
import sys
import platform as _platform

# Windows scipy deadlock prevention (per lessons.md)
if sys.platform == "win32":
    import faulthandler
    faulthandler.dump_traceback_later(600, exit=True)
    try:
        _platform._wmi_query = lambda *a, **k: ("10.0.26100", "1", "Multiprocessor Free", 0, 0)
    except Exception:
        pass

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json
import pandas as pd
from pathlib import Path
from score_engine import (
    compute_all, save_results, add_percentile_rank,
    compute_before_after, RESULTS_DIR,
)
from sensitivity import run_sensitivity_analysis


def main():
    print("=" * 60)
    print("EvidenceScore v2.0 -- Full Pipeline")
    print("=" * 60)

    # Load v1 scores for comparison
    v1_csv = RESULTS_DIR / "scores.csv"
    v1_scores = []
    if v1_csv.exists():
        v1_df = pd.read_csv(v1_csv)
        v1_scores = v1_df.to_dict("records")
        print(f"Loaded v1 scores: {len(v1_scores)} MAs (mean={v1_df['final_score'].mean():.1f})")

    # Compute v2 scores
    df = compute_all()
    if df.empty:
        print("ERROR: No scores computed.")
        return

    # Add percentile rank
    records = df.to_dict("records")
    records = add_percentile_rank(records)
    df = pd.DataFrame(records)

    # Save main results
    summary = save_results(df)

    # Sensitivity analysis
    print("\nRunning sensitivity analysis (50 weight schemes)...")
    sens = run_sensitivity_analysis(df, n_schemes=50, seed=42)
    sens_path = RESULTS_DIR / "sensitivity.json"
    with open(sens_path, "w") as f:
        json.dump(sens, f, indent=2)
    print(f"Saved sensitivity to {sens_path}")
    print(f"  Mean Kendall tau: {sens['summary']['mean_tau']:.4f}")
    print(f"  Range: [{sens['summary']['min_tau']:.4f}, {sens['summary']['max_tau']:.4f}]")
    print(f"  Robust: {sens['summary']['robust']}")

    # Before/after comparison
    if v1_scores:
        print("\nComputing before/after comparison...")
        v2_scores = df.to_dict("records")
        ba = compute_before_after(v1_scores, v2_scores)
        ba_path = RESULTS_DIR / "before_after.json"
        with open(ba_path, "w") as f:
            json.dump(ba, f, indent=2)
        print(f"Saved before/after to {ba_path}")
        print(f"  v1 mean: {ba['v1_mean']}, v2 mean: {ba['v2_mean']}")
        print(f"  Mean delta: {ba['mean_delta']}")
        print(f"  Grade changes: {ba['grade_changes']}")
        print(f"  Rank correlation (Spearman): {ba['rank_correlation']}")

    print("\n" + "=" * 60)
    print("v2.0 Pipeline Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
