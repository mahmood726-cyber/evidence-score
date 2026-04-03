"""
EvidenceScore — Composite 0-100 trust score for every meta-analysis.

Combines signals from MetaAudit, ContradictionMap, ActionableEvidence,
and EvidenceOracle into a single weighted score with grade labels.
"""

import os
import re
import json
import pandas as pd
import numpy as np
from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"

AUDIT_CSV = Path(r"C:\MetaAudit\results\audit_results.csv")
CONTRADICTION_CSV = Path(r"C:\Models\ContradictionMap\results\contradictions.csv")
VERDICT_CSV = Path(r"C:\Models\ActionableEvidence\results\verdicts.csv")
ORACLE_CSV = Path(r"C:\Models\EvidenceOracle\results\predictions.csv")

# ── Weights ─────────────────────────────────────────────────────────────────
WEIGHTS = {
    "audit": 0.20,
    "consistency": 0.20,
    "robustness": 0.20,
    "stability": 0.20,
    "power": 0.20,
}

# Sanity check: weights must sum to 1.0
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"

# ── Grade labels ────────────────────────────────────────────────────────────
GRADE_THRESHOLDS = [
    (90, "A+", "Highly Trustworthy"),
    (80, "A", "Trustworthy"),
    (70, "B", "Moderately Trustworthy"),
    (60, "C", "Caution Advised"),
    (50, "D", "Significant Concerns"),
    (0, "F", "Unreliable"),
]


def normalize_ma_id(ma_id: str) -> str:
    """
    Normalize MA ID to common format: {review_id}__{variant}.
    Strips _pubN_data from full-format IDs.
    CD001155_pub3_data__A5 -> CD001155__A5
    CD011381__A1 -> CD011381__A1 (unchanged)
    """
    if not ma_id or "__" not in ma_id:
        return ma_id
    return re.sub(r'_pub\d+_data__', '__', ma_id)


def get_grade(score: int) -> tuple:
    """Return (grade_letter, grade_label) for a given 0-100 score."""
    for threshold, letter, label in GRADE_THRESHOLDS:
        if score >= threshold:
            return letter, label
    return "F", "Unreliable"


# ── Data readers ────────────────────────────────────────────────────────────

def read_audit_data(path=None) -> pd.DataFrame:
    """Read MetaAudit results. Returns DataFrame with ma_id, module, severity, detail."""
    p = path or AUDIT_CSV
    if not Path(p).exists():
        return pd.DataFrame(columns=["ma_id", "module", "severity", "detail"])
    return pd.read_csv(p)


def read_contradiction_data(path=None) -> pd.DataFrame:
    """Read ContradictionMap results."""
    p = path or CONTRADICTION_CSV
    if not Path(p).exists():
        return pd.DataFrame(columns=["ma_id_1", "ma_id_2", "contradiction_type"])
    return pd.read_csv(p)


def read_verdict_data(path=None) -> pd.DataFrame:
    """Read ActionableEvidence verdicts."""
    p = path or VERDICT_CSV
    if not Path(p).exists():
        return pd.DataFrame(columns=[
            "ma_id", "review_id", "k", "total_n", "estimate", "p_value",
            "significant", "pi_crosses_null", "robustness", "n_audit_fails",
            "has_pub_bias", "verdict", "failed_criteria"
        ])
    return pd.read_csv(p)


def read_oracle_data(path=None) -> pd.DataFrame:
    """Read EvidenceOracle predictions. Note: keyed by review_id, not ma_id."""
    p = path or ORACLE_CSV
    if not Path(p).exists():
        return pd.DataFrame(columns=[
            "review_id", "true_label", "GradientBoosting_prob"
        ])
    return pd.read_csv(p)


# ── Component score calculators ─────────────────────────────────────────────

def compute_audit_score(ma_id: str, audit_df: pd.DataFrame) -> float:
    """
    Audit Score (0-100): Start at 100, deduct per finding.
    CRITICAL: -20, WARN: -8, FAIL treated as CRITICAL (-20).
    """
    if audit_df.empty:
        return 100.0

    ma_rows = audit_df[audit_df["ma_id"] == ma_id]
    if ma_rows.empty:
        return 100.0

    score = 100.0
    for _, row in ma_rows.iterrows():
        sev = str(row["severity"]).upper()
        if sev == "CRITICAL" or sev == "FAIL":
            score -= 20.0
        elif sev == "WARN":
            score -= 8.0
        # PASS: no deduction

    return max(0.0, score)


def compute_consistency_score(ma_id: str, contradiction_df: pd.DataFrame) -> float:
    """
    Consistency Score (0-100): Start at 100, deduct per contradiction involving this MA.
    Direct: -25, Magnitude: -15, Significance: -10.
    Uses normalized MA IDs to match across pipeline formats.
    """
    if contradiction_df.empty:
        return 100.0

    norm_id = normalize_ma_id(ma_id)

    # Use pre-normalized columns if available, else normalize on the fly
    if "_norm_1" in contradiction_df.columns:
        involved = contradiction_df[
            (contradiction_df["_norm_1"] == norm_id) |
            (contradiction_df["_norm_2"] == norm_id)
        ]
    else:
        involved = contradiction_df[
            (contradiction_df["ma_id_1"].apply(normalize_ma_id) == norm_id) |
            (contradiction_df["ma_id_2"].apply(normalize_ma_id) == norm_id)
        ]

    if involved.empty:
        return 100.0

    score = 100.0
    for _, row in involved.iterrows():
        ctype = str(row["contradiction_type"]).lower()
        if ctype == "direct":
            score -= 25.0
        elif ctype == "magnitude":
            score -= 15.0
        elif ctype == "significance":
            score -= 10.0
        # "none" type: no deduction

    return max(0.0, score)


def compute_robustness_score(ma_id: str, verdict_df: pd.DataFrame) -> float:
    """
    Robustness Score (0-100): Additive from indicators.
    PI doesn't cross null: +30, Significant: +20, No pub bias: +20,
    Robust (not fragile): +20, No audit fails: +10.
    """
    if verdict_df.empty:
        return 50.0  # neutral default when no data

    ma_row = verdict_df[verdict_df["ma_id"] == ma_id]
    if ma_row.empty:
        return 50.0

    row = ma_row.iloc[0]
    score = 0.0

    # PI doesn't cross null: +30
    pi_crosses = row.get("pi_crosses_null", True)
    if isinstance(pi_crosses, str):
        pi_crosses = pi_crosses.strip().lower() == "true"
    if not pi_crosses:
        score += 30.0

    # Significant p-value: +20
    sig = row.get("significant", False)
    if isinstance(sig, str):
        sig = sig.strip().lower() == "true"
    if sig:
        score += 20.0

    # No pub bias: +20
    has_bias = row.get("has_pub_bias", True)
    if isinstance(has_bias, str):
        has_bias = has_bias.strip().lower() == "true"
    if not has_bias:
        score += 20.0

    # Robust: +20
    robustness_val = str(row.get("robustness", "")).lower()
    if robustness_val == "robust":
        score += 20.0
    elif robustness_val == "moderate":
        score += 10.0
    # Fragile, Unstable, not_covered: 0

    # No audit fails: +10
    n_fails = row.get("n_audit_fails", 1)
    if isinstance(n_fails, str):
        n_fails = int(n_fails) if n_fails.strip().isdigit() else 1
    if n_fails == 0:
        score += 10.0

    return min(100.0, max(0.0, score))


def compute_stability_score(ma_id: str, review_id: str, oracle_df: pd.DataFrame) -> float:
    """
    Stability Score (0-100): Based on EvidenceOracle instability prediction.
    Score = 100 * (1 - p_unstable).
    Uses GradientBoosting_prob as the best model's prediction.
    Oracle is keyed by review_id, not ma_id.
    """
    if oracle_df.empty:
        return 50.0  # neutral default when no data

    oracle_row = oracle_df[oracle_df["review_id"] == review_id]
    if oracle_row.empty:
        return 50.0

    row = oracle_row.iloc[0]
    p_unstable = row.get("GradientBoosting_prob", 0.5)
    if p_unstable is None or (isinstance(p_unstable, float) and np.isnan(p_unstable)):
        return 50.0

    p_unstable = float(p_unstable)
    score = 100.0 * (1.0 - p_unstable)
    return min(100.0, max(0.0, score))


def compute_power_score(ma_id: str, verdict_df: pd.DataFrame) -> float:
    """
    Power Score (0-100): Based on k (studies) and total_n (participants).
    k>=10 & n>=1000: 100, k>=5 & n>=500: 75, k>=3 & n>=200: 50, else: 25.
    """
    if verdict_df.empty:
        return 25.0

    ma_row = verdict_df[verdict_df["ma_id"] == ma_id]
    if ma_row.empty:
        return 25.0

    row = ma_row.iloc[0]
    k = int(row.get("k", 0))
    total_n = int(row.get("total_n", 0))

    if k >= 10 and total_n >= 1000:
        return 100.0
    elif k >= 5 and total_n >= 500:
        return 75.0
    elif k >= 3 and total_n >= 200:
        return 50.0
    else:
        return 25.0


# ── Main scoring function ──────────────────────────────────────────────────

def compute_score(
    ma_id: str,
    audit_df: pd.DataFrame,
    contradiction_df: pd.DataFrame,
    verdict_df: pd.DataFrame,
    oracle_df: pd.DataFrame,
) -> dict:
    """
    Compute composite EvidenceScore for a single MA.
    Returns dict with component scores, final score, and grade.
    """
    # Get review_id for oracle lookup
    review_id = ""
    if not verdict_df.empty:
        ma_row = verdict_df[verdict_df["ma_id"] == ma_id]
        if not ma_row.empty:
            review_id = str(ma_row.iloc[0].get("review_id", ""))

    # Compute components
    audit = compute_audit_score(ma_id, audit_df)
    consistency = compute_consistency_score(ma_id, contradiction_df)
    robustness = compute_robustness_score(ma_id, verdict_df)
    stability = compute_stability_score(ma_id, review_id, oracle_df)
    power = compute_power_score(ma_id, verdict_df)

    # Weighted average
    final_raw = (
        WEIGHTS["audit"] * audit
        + WEIGHTS["consistency"] * consistency
        + WEIGHTS["robustness"] * robustness
        + WEIGHTS["stability"] * stability
        + WEIGHTS["power"] * power
    )

    final_score = int(round(min(100.0, max(0.0, final_raw))))
    grade_letter, grade_label = get_grade(final_score)

    return {
        "ma_id": ma_id,
        "review_id": review_id,
        "audit_score": round(audit, 1),
        "consistency_score": round(consistency, 1),
        "robustness_score": round(robustness, 1),
        "stability_score": round(stability, 1),
        "power_score": round(power, 1),
        "final_score": final_score,
        "grade": grade_letter,
        "grade_label": grade_label,
    }


def compute_all(
    audit_path=None,
    contradiction_path=None,
    verdict_path=None,
    oracle_path=None,
) -> pd.DataFrame:
    """
    Compute EvidenceScore for ALL meta-analyses.
    Returns DataFrame sorted by final_score descending.
    """
    print("Loading data sources...")
    audit_df = read_audit_data(audit_path)
    contradiction_df = read_contradiction_data(contradiction_path)
    verdict_df = read_verdict_data(verdict_path)
    oracle_df = read_oracle_data(oracle_path)

    # Pre-normalize contradiction IDs for performance
    if not contradiction_df.empty and "ma_id_1" in contradiction_df.columns:
        contradiction_df = contradiction_df.copy()
        contradiction_df["_norm_1"] = contradiction_df["ma_id_1"].apply(normalize_ma_id)
        contradiction_df["_norm_2"] = contradiction_df["ma_id_2"].apply(normalize_ma_id)

    # Get all unique MA IDs from audit + verdicts
    ma_ids = set()
    if not audit_df.empty:
        ma_ids.update(audit_df["ma_id"].unique())
    if not verdict_df.empty:
        ma_ids.update(verdict_df["ma_id"].unique())

    if not ma_ids:
        print("No MA IDs found in any data source.")
        return pd.DataFrame()

    print(f"Scoring {len(ma_ids)} meta-analyses...")

    results = []
    for i, ma_id in enumerate(sorted(ma_ids)):
        result = compute_score(ma_id, audit_df, contradiction_df, verdict_df, oracle_df)
        results.append(result)
        if (i + 1) % 1000 == 0:
            print(f"  Scored {i + 1}/{len(ma_ids)}...")

    df = pd.DataFrame(results)
    df = df.sort_values("final_score", ascending=False).reset_index(drop=True)

    print(f"Done. Scored {len(df)} meta-analyses.")
    return df


def save_results(df: pd.DataFrame, output_dir=None):
    """Save scored results to CSV and summary JSON."""
    out = Path(output_dir) if output_dir else RESULTS_DIR
    out.mkdir(parents=True, exist_ok=True)

    # Save full CSV
    csv_path = out / "scores.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved scores to {csv_path}")

    # Build summary
    grade_counts = df["grade"].value_counts().to_dict()
    summary = {
        "total_scored": len(df),
        "mean_score": round(float(df["final_score"].mean()), 1),
        "median_score": int(df["final_score"].median()),
        "std_score": round(float(df["final_score"].std()), 1),
        "min_score": int(df["final_score"].min()),
        "max_score": int(df["final_score"].max()),
        "grade_distribution": {
            "A+": grade_counts.get("A+", 0),
            "A": grade_counts.get("A", 0),
            "B": grade_counts.get("B", 0),
            "C": grade_counts.get("C", 0),
            "D": grade_counts.get("D", 0),
            "F": grade_counts.get("F", 0),
        },
        "component_means": {
            "audit": round(float(df["audit_score"].mean()), 1),
            "consistency": round(float(df["consistency_score"].mean()), 1),
            "robustness": round(float(df["robustness_score"].mean()), 1),
            "stability": round(float(df["stability_score"].mean()), 1),
            "power": round(float(df["power_score"].mean()), 1),
        },
        "weights": WEIGHTS,
    }

    json_path = out / "summary.json"
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved summary to {json_path}")

    return summary


# ── Percentile rank ────────────────────────────────────────────────────────

def add_percentile_rank(scores: list) -> list:
    """Add percentile_rank (0-100, 1 decimal) to each score dict."""
    from scipy.stats import percentileofscore
    all_vals = [s["final_score"] for s in scores]
    for s in scores:
        s["percentile_rank"] = round(
            percentileofscore(all_vals, s["final_score"], kind="rank"), 1
        )
    return scores


# ── Before/After comparison ────────────────────────────────────────────────

def compute_before_after(v1_scores: list, v2_scores: list) -> dict:
    """Compare v1 and v2 scores for the same MAs."""
    from scipy.stats import spearmanr

    v1_map = {s["ma_id"]: s for s in v1_scores}
    v2_map = {s["ma_id"]: s for s in v2_scores}
    common = sorted(set(v1_map) & set(v2_map))

    deltas = []
    upgraded, downgraded, unchanged = 0, 0, 0
    top_movers = []

    for ma_id in common:
        d = v2_map[ma_id]["final_score"] - v1_map[ma_id]["final_score"]
        deltas.append(d)
        if v2_map[ma_id]["grade"] != v1_map[ma_id]["grade"]:
            if v2_map[ma_id]["final_score"] > v1_map[ma_id]["final_score"]:
                upgraded += 1
            else:
                downgraded += 1
        else:
            unchanged += 1
        top_movers.append({
            "ma_id": ma_id,
            "v1_score": v1_map[ma_id]["final_score"],
            "v2_score": v2_map[ma_id]["final_score"],
            "delta": d,
        })

    top_movers.sort(key=lambda x: x["delta"])
    v1_arr = [v1_map[m]["final_score"] for m in common]
    v2_arr = [v2_map[m]["final_score"] for m in common]

    rho = spearmanr(v1_arr, v2_arr).statistic if len(common) > 2 else 1.0

    return {
        "n_mas": len(common),
        "v1_mean": round(float(np.mean(v1_arr)), 1),
        "v2_mean": round(float(np.mean(v2_arr)), 1),
        "mean_delta": round(float(np.mean(deltas)), 1),
        "grade_changes": {
            "upgraded": upgraded,
            "downgraded": downgraded,
            "unchanged": unchanged,
        },
        "top_movers": top_movers[:10],
        "rank_correlation": round(float(rho), 4),
    }


# ── CLI entrypoint ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    df = compute_all()
    summary = save_results(df)

    print("\n" + "=" * 60)
    print("EvidenceScore Summary")
    print("=" * 60)
    print(f"Total scored:  {summary['total_scored']}")
    print(f"Mean score:    {summary['mean_score']}")
    print(f"Median score:  {summary['median_score']}")
    print(f"Std dev:       {summary['std_score']}")
    print(f"Range:         {summary['min_score']} - {summary['max_score']}")
    print()
    print("Grade Distribution:")
    for grade, count in summary["grade_distribution"].items():
        pct = 100 * count / summary["total_scored"] if summary["total_scored"] > 0 else 0
        print(f"  {grade:3s}: {count:5d}  ({pct:5.1f}%)")
    print()
    print("Component Means:")
    for comp, mean in summary["component_means"].items():
        print(f"  {comp:15s}: {mean:5.1f}")
