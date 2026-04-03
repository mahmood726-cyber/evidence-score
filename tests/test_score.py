"""
Tests for EvidenceScore engine.
25 tests covering component calculations, edge cases, boundaries, and integration.
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from score_engine import (
    compute_audit_score,
    compute_consistency_score,
    compute_robustness_score,
    compute_stability_score,
    compute_power_score,
    compute_score,
    compute_all,
    get_grade,
    normalize_ma_id,
    add_percentile_rank,
    compute_before_after,
    WEIGHTS,
    AUDIT_CSV,
    CONTRADICTION_CSV,
    VERDICT_CSV,
    ORACLE_CSV,
)
from sensitivity import run_sensitivity_analysis


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def empty_audit():
    return pd.DataFrame(columns=["ma_id", "module", "severity", "detail"])


@pytest.fixture
def empty_contradictions():
    return pd.DataFrame(columns=["ma_id_1", "ma_id_2", "contradiction_type"])


@pytest.fixture
def empty_verdicts():
    return pd.DataFrame(columns=[
        "ma_id", "review_id", "k", "total_n", "estimate", "p_value",
        "significant", "pi_crosses_null", "robustness", "n_audit_fails",
        "has_pub_bias", "verdict", "failed_criteria"
    ])


@pytest.fixture
def empty_oracle():
    return pd.DataFrame(columns=["review_id", "true_label", "GradientBoosting_prob"])


@pytest.fixture
def sample_audit():
    return pd.DataFrame([
        {"ma_id": "MA001", "module": "fragility", "severity": "CRITICAL", "detail": "fragile"},
        {"ma_id": "MA001", "module": "pub_bias", "severity": "WARN", "detail": "possible bias"},
        {"ma_id": "MA001", "module": "model_misspec", "severity": "PASS", "detail": "ok"},
        {"ma_id": "MA002", "module": "fragility", "severity": "PASS", "detail": "ok"},
        {"ma_id": "MA002", "module": "pub_bias", "severity": "PASS", "detail": "ok"},
    ])


@pytest.fixture
def sample_contradictions():
    return pd.DataFrame([
        {"ma_id_1": "MA001", "ma_id_2": "MA003", "contradiction_type": "direct"},
        {"ma_id_1": "MA004", "ma_id_2": "MA001", "contradiction_type": "significance"},
        {"ma_id_1": "MA002", "ma_id_2": "MA005", "contradiction_type": "magnitude"},
    ])


@pytest.fixture
def sample_verdicts():
    return pd.DataFrame([
        {
            "ma_id": "MA001", "review_id": "R001", "k": 15, "total_n": 5000,
            "estimate": 0.5, "p_value": 0.001, "significant": True,
            "pi_crosses_null": False, "robustness": "Robust",
            "n_audit_fails": 0, "has_pub_bias": False,
            "verdict": "ACTIONABLE", "failed_criteria": ""
        },
        {
            "ma_id": "MA002", "review_id": "R002", "k": 3, "total_n": 150,
            "estimate": 0.2, "p_value": 0.08, "significant": False,
            "pi_crosses_null": True, "robustness": "Fragile",
            "n_audit_fails": 3, "has_pub_bias": True,
            "verdict": "NOT YET", "failed_criteria": "robustness;pub_bias"
        },
    ])


@pytest.fixture
def sample_oracle():
    return pd.DataFrame([
        {"review_id": "R001", "true_label": 0, "GradientBoosting_prob": 0.1},
        {"review_id": "R002", "true_label": 1, "GradientBoosting_prob": 0.9},
    ])


# ── Test 1-5: Audit Score ───────────────────────────────────────────────────

def test_audit_score_no_data(empty_audit):
    """T1: No audit data returns 100."""
    assert compute_audit_score("MA001", empty_audit) == 100.0


def test_audit_score_all_pass(sample_audit):
    """T2: MA with only PASS findings scores 100."""
    assert compute_audit_score("MA002", sample_audit) == 100.0


def test_audit_score_critical_and_warn(sample_audit):
    """T3: CRITICAL (-20) + WARN (-8) = 72."""
    assert compute_audit_score("MA001", sample_audit) == 72.0


def test_audit_score_all_critical():
    """T4: 6 CRITICAL findings = 100 - 120, floored at 0."""
    df = pd.DataFrame([
        {"ma_id": "MA_BAD", "module": f"mod{i}", "severity": "CRITICAL", "detail": "bad"}
        for i in range(6)
    ])
    assert compute_audit_score("MA_BAD", df) == 0.0


def test_audit_score_fail_treated_as_critical():
    """T5: FAIL severity treated same as CRITICAL (-20)."""
    df = pd.DataFrame([
        {"ma_id": "MA001", "module": "integrity", "severity": "FAIL", "detail": "failed"},
    ])
    assert compute_audit_score("MA001", df) == 80.0


# ── Test 6-9: Consistency Score ─────────────────────────────────────────────

def test_consistency_no_contradictions(empty_contradictions):
    """T6: No contradictions = 100."""
    assert compute_consistency_score("MA001", empty_contradictions) == 100.0


def test_consistency_direct_contradiction(sample_contradictions):
    """T7: MA001 has 1 direct (-25) + 1 significance (-10) = 65."""
    assert compute_consistency_score("MA001", sample_contradictions) == 65.0


def test_consistency_magnitude(sample_contradictions):
    """T8: MA002 has 1 magnitude (-15) = 85."""
    assert compute_consistency_score("MA002", sample_contradictions) == 85.0


def test_consistency_floor():
    """T9: Many contradictions floor at 0."""
    df = pd.DataFrame([
        {"ma_id_1": "MA_BAD", "ma_id_2": f"MA_X{i}", "contradiction_type": "direct"}
        for i in range(5)
    ])
    assert compute_consistency_score("MA_BAD", df) == 0.0


# ── Test 10-13: Robustness Score ────────────────────────────────────────────

def test_robustness_perfect(sample_verdicts):
    """T10: MA001 — all positive indicators: 30+20+20+20+10 = 100."""
    assert compute_robustness_score("MA001", sample_verdicts) == 100.0


def test_robustness_worst_case(sample_verdicts):
    """T11: MA002 — pi crosses null, not significant, has bias, fragile, has fails = 0."""
    assert compute_robustness_score("MA002", sample_verdicts) == 0.0


def test_robustness_no_data(empty_verdicts):
    """T12: No data returns neutral 50."""
    assert compute_robustness_score("MA_UNKNOWN", empty_verdicts) == 50.0


def test_robustness_moderate():
    """T13: Moderate robustness gives +10 instead of +20."""
    df = pd.DataFrame([{
        "ma_id": "MA_MOD", "review_id": "R_MOD", "k": 5, "total_n": 500,
        "estimate": 0.3, "p_value": 0.01, "significant": True,
        "pi_crosses_null": True, "robustness": "Moderate",
        "n_audit_fails": 0, "has_pub_bias": False,
        "verdict": "NOT YET", "failed_criteria": ""
    }])
    # significant +20, no pub bias +20, moderate +10, no fails +10 = 60
    # pi crosses null: no +30
    assert compute_robustness_score("MA_MOD", df) == 60.0


# ── Test 14-16: Stability Score ─────────────────────────────────────────────

def test_stability_low_risk(sample_oracle):
    """T14: p_unstable=0.1 -> score=90."""
    assert compute_stability_score("MA001", "R001", sample_oracle) == 90.0


def test_stability_high_risk(sample_oracle):
    """T15: p_unstable=0.9 -> score=10."""
    assert abs(compute_stability_score("MA002", "R002", sample_oracle) - 10.0) < 1e-6


def test_stability_no_data(empty_oracle):
    """T16: No oracle data returns neutral 50."""
    assert compute_stability_score("MA001", "R001", empty_oracle) == 50.0


# ── Test 17-19: Power Score ─────────────────────────────────────────────────

def test_power_high(sample_verdicts):
    """T17: k=15, n=5000 -> 100."""
    assert compute_power_score("MA001", sample_verdicts) == 100.0


def test_power_low(sample_verdicts):
    """T18: k=3, n=150 -> 25 (below 200 threshold)."""
    assert compute_power_score("MA002", sample_verdicts) == 25.0


def test_power_medium():
    """T19: k=7, n=600 -> 75."""
    df = pd.DataFrame([{
        "ma_id": "MA_MED", "review_id": "R_MED", "k": 7, "total_n": 600,
        "estimate": 0.3, "p_value": 0.05, "significant": True,
        "pi_crosses_null": False, "robustness": "Moderate",
        "n_audit_fails": 0, "has_pub_bias": False,
        "verdict": "NOT YET", "failed_criteria": ""
    }])
    assert compute_power_score("MA_MED", df) == 75.0


# ── Test 20: Weight normalization ───────────────────────────────────────────

def test_weights_sum_to_one():
    """T20: All component weights must sum to 1.0 and be equal."""
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9
    vals = list(WEIGHTS.values())
    assert all(abs(v - 0.20) < 1e-9 for v in vals), "All weights should be 0.20"


# ── Test 21-22: Grade assignment ────────────────────────────────────────────

def test_grade_boundaries():
    """T21: Test all grade boundary values."""
    assert get_grade(100) == ("A+", "Highly Trustworthy")
    assert get_grade(95) == ("A+", "Highly Trustworthy")
    assert get_grade(90) == ("A+", "Highly Trustworthy")
    assert get_grade(89) == ("A", "Trustworthy")
    assert get_grade(80) == ("A", "Trustworthy")
    assert get_grade(79) == ("B", "Moderately Trustworthy")
    assert get_grade(70) == ("B", "Moderately Trustworthy")
    assert get_grade(69) == ("C", "Caution Advised")
    assert get_grade(60) == ("C", "Caution Advised")
    assert get_grade(59) == ("D", "Significant Concerns")
    assert get_grade(50) == ("D", "Significant Concerns")
    assert get_grade(49) == ("F", "Unreliable")
    assert get_grade(0) == ("F", "Unreliable")


def test_grade_extreme():
    """T22: Grade at score 0 and 100."""
    assert get_grade(0) == ("F", "Unreliable")
    assert get_grade(100) == ("A+", "Highly Trustworthy")


# ── Test 23: Score clamping ─────────────────────────────────────────────────

def test_score_clamping(
    sample_audit, sample_contradictions, sample_verdicts, sample_oracle
):
    """T23: Final score is always clamped 0-100."""
    result = compute_score(
        "MA001", sample_audit, sample_contradictions, sample_verdicts, sample_oracle
    )
    assert 0 <= result["final_score"] <= 100


# ── Test 24: Composite score computation ────────────────────────────────────

def test_composite_score_perfect():
    """T24: Perfect MA with all best indicators should score high."""
    audit_df = pd.DataFrame([
        {"ma_id": "PERFECT", "module": "fragility", "severity": "PASS", "detail": "ok"},
    ])
    contradiction_df = pd.DataFrame(columns=["ma_id_1", "ma_id_2", "contradiction_type"])
    verdict_df = pd.DataFrame([{
        "ma_id": "PERFECT", "review_id": "R_PERFECT", "k": 20, "total_n": 10000,
        "estimate": 0.5, "p_value": 0.0001, "significant": True,
        "pi_crosses_null": False, "robustness": "Robust",
        "n_audit_fails": 0, "has_pub_bias": False,
        "verdict": "ACTIONABLE", "failed_criteria": ""
    }])
    oracle_df = pd.DataFrame([
        {"review_id": "R_PERFECT", "true_label": 0, "GradientBoosting_prob": 0.05},
    ])

    result = compute_score("PERFECT", audit_df, contradiction_df, verdict_df, oracle_df)

    # audit=100, consistency=100, robustness=100, stability=95, power=100
    # weighted = 0.2*100 + 0.2*100 + 0.2*100 + 0.2*95 + 0.2*100 = 99
    assert result["final_score"] >= 95
    assert result["grade"] == "A+"


# ── Test 25: Integration with real data ─────────────────────────────────────

def test_integration_real_data():
    """T25: Integration test with actual data files if they exist."""
    if not AUDIT_CSV.exists():
        pytest.skip("Real data files not available")

    df = compute_all()
    assert len(df) > 0
    assert "final_score" in df.columns
    assert "grade" in df.columns

    # All scores must be 0-100
    assert df["final_score"].min() >= 0
    assert df["final_score"].max() <= 100

    # All grades must be valid
    valid_grades = {"A+", "A", "B", "C", "D", "F"}
    assert set(df["grade"].unique()).issubset(valid_grades)

    # Component scores must be 0-100
    for col in ["audit_score", "consistency_score", "robustness_score",
                "stability_score", "power_score"]:
        assert df[col].min() >= 0.0, f"{col} has values below 0"
        assert df[col].max() <= 100.0, f"{col} has values above 100"

    print(f"Integration test: {len(df)} MAs scored, "
          f"mean={df['final_score'].mean():.1f}, "
          f"median={df['final_score'].median()}")


# ── Test 26-28: normalize_ma_id ────────────────────────────────────────────

def test_normalize_ma_id_full_format():
    """T26: Strip _pubN_data from full format."""
    assert normalize_ma_id("CD001155_pub3_data__A5") == "CD001155__A5"
    assert normalize_ma_id("CD000028_pub4_data__A1") == "CD000028__A1"


def test_normalize_ma_id_already_short():
    """T27: Already-normalized IDs pass through unchanged."""
    assert normalize_ma_id("CD011381__A1") == "CD011381__A1"


def test_normalize_ma_id_edge_cases():
    """T28: Edge cases: no __, empty string."""
    assert normalize_ma_id("") == ""
    assert normalize_ma_id("CD001155") == "CD001155"


# ── Test 29: Consistency with normalized IDs ───────────────────────────────

def test_consistency_with_normalized_ids():
    """T29: Consistency works when formats differ (the bug fix)."""
    df = pd.DataFrame([
        {"ma_id_1": "CD001155__A5", "ma_id_2": "CD002000__A1",
         "contradiction_type": "direct"},
    ])
    score = compute_consistency_score("CD001155_pub3_data__A5", df)
    assert score == 75.0  # 100 - 25 for direct


# ── Test 30-31: Sensitivity analysis ───────────────────────────────────────

def test_sensitivity_analysis_shape():
    """T30: 50 schemes produced, all taus in [0,1]."""
    scores_df = pd.DataFrame({
        "audit_score": np.random.default_rng(42).uniform(0, 100, 100),
        "consistency_score": np.random.default_rng(43).uniform(0, 100, 100),
        "robustness_score": np.random.default_rng(44).uniform(0, 100, 100),
        "stability_score": np.random.default_rng(45).uniform(0, 100, 100),
        "power_score": np.random.default_rng(46).uniform(0, 100, 100),
    })
    result = run_sensitivity_analysis(scores_df, n_schemes=50, seed=42)
    assert len(result["schemes"]) == 50
    assert all(0 <= s["kendall_tau"] <= 1 for s in result["schemes"])
    assert "mean_tau" in result["summary"]


def test_sensitivity_analysis_deterministic():
    """T31: Same seed = same result."""
    scores_df = pd.DataFrame({
        "audit_score": [80, 60, 40, 90, 70],
        "consistency_score": [100, 50, 30, 80, 60],
        "robustness_score": [90, 20, 10, 70, 50],
        "stability_score": [70, 80, 60, 40, 90],
        "power_score": [100, 25, 50, 75, 50],
    })
    r1 = run_sensitivity_analysis(scores_df, n_schemes=10, seed=99)
    r2 = run_sensitivity_analysis(scores_df, n_schemes=10, seed=99)
    assert r1["summary"]["mean_tau"] == r2["summary"]["mean_tau"]


# ── Test 32-33: Percentile rank ────────────────────────────────────────────

def test_percentile_rank_bounds():
    """T32: All percentile values in [0, 100]."""
    scores = [{"ma_id": f"MA{i}", "final_score": i * 10} for i in range(1, 11)]
    result = add_percentile_rank(scores)
    for r in result:
        assert 0 <= r["percentile_rank"] <= 100


def test_percentile_rank_ordering():
    """T33: Higher score = higher percentile."""
    scores = [
        {"ma_id": "LOW", "final_score": 20},
        {"ma_id": "MID", "final_score": 50},
        {"ma_id": "HIGH", "final_score": 90},
    ]
    result = add_percentile_rank(scores)
    by_id = {r["ma_id"]: r["percentile_rank"] for r in result}
    assert by_id["HIGH"] > by_id["MID"] > by_id["LOW"]


# ── Test 34: Before/after ──────────────────────────────────────────────────

def test_before_after_symmetric():
    """T34: Same MAs in both inputs."""
    v1 = [{"ma_id": "A", "final_score": 80, "grade": "A"},
          {"ma_id": "B", "final_score": 60, "grade": "C"}]
    v2 = [{"ma_id": "A", "final_score": 65, "grade": "C"},
          {"ma_id": "B", "final_score": 45, "grade": "F"}]
    result = compute_before_after(v1, v2)
    assert result["n_mas"] == 2
    assert result["v1_mean"] == 70.0
    assert result["v2_mean"] == 55.0
    assert result["grade_changes"]["downgraded"] == 2


# ── Test 35: Equal weights ─────────────────────────────────────────────────

def test_equal_weights():
    """T35: Verify all 5 weights are exactly 0.20."""
    assert len(WEIGHTS) == 5
    for name, w in WEIGHTS.items():
        assert abs(w - 0.20) < 1e-9, f"Weight {name} should be 0.20, got {w}"
