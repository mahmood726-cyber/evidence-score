"""
Sensitivity analysis for EvidenceScore weight robustness.
Generates random weight vectors (Dirichlet) and measures rank stability via Kendall's tau.
"""

import numpy as np
from scipy.stats import kendalltau


COMPONENT_COLS = [
    "audit_score", "consistency_score", "robustness_score",
    "stability_score", "power_score",
]


def run_sensitivity_analysis(scores_df, n_schemes=50, seed=42):
    """
    Generate n_schemes random weight vectors from Dirichlet(1,1,1,1,1),
    compute final scores under each, compare rankings to base (equal weights)
    via Kendall's tau.
    """
    rng = np.random.default_rng(seed)
    component_matrix = scores_df[COMPONENT_COLS].values  # (N, 5)

    # Base ranking (equal weights)
    base_weights = np.array([0.20, 0.20, 0.20, 0.20, 0.20])
    base_scores = component_matrix @ base_weights
    base_ranks = base_scores.argsort().argsort()

    schemes = []
    for _ in range(n_schemes):
        weights = rng.dirichlet(np.ones(5))
        alt_scores = component_matrix @ weights
        alt_ranks = alt_scores.argsort().argsort()
        tau, _ = kendalltau(base_ranks, alt_ranks)
        schemes.append({
            "weights": weights.round(4).tolist(),
            "kendall_tau": round(float(tau), 4),
            "mean_score": round(float(alt_scores.mean()), 1),
        })

    taus = [s["kendall_tau"] for s in schemes]
    summary = {
        "mean_tau": round(float(np.mean(taus)), 4),
        "min_tau": round(float(np.min(taus)), 4),
        "max_tau": round(float(np.max(taus)), 4),
        "std_tau": round(float(np.std(taus)), 4),
        "robust": float(np.mean(taus)) > 0.85,
    }

    return {
        "n_schemes": n_schemes,
        "seed": seed,
        "base_weights": base_weights.tolist(),
        "schemes": schemes,
        "summary": summary,
    }
