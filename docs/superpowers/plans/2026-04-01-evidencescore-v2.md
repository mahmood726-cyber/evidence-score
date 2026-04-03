# EvidenceScore v2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the degenerate consistency component, switch to equal weights, add sensitivity analysis and percentile ranks, regenerate dashboard with new visualizations.

**Architecture:** Fix MA ID normalization in score_engine.py, add sensitivity.py module for weight robustness analysis, add percentile rank post-processing, create run_v2.py orchestrator, enhance build_dashboard.py with 4 new chart sections.

**Tech Stack:** Python 3, pandas, numpy, scipy (kendalltau, percentileofscore, dirichlet)

---

### Task 1: Add normalize_ma_id() and fix consistency scoring

**Files:**
- Modify: `score_engine.py:1-33` (weights) and `score_engine.py:120-147` (consistency function)
- Test: `tests/test_score.py`

- [ ] **Step 1: Write failing tests for normalize_ma_id**

Add to `tests/test_score.py`:

```python
from score_engine import normalize_ma_id

def test_normalize_ma_id_full_format():
    """Strip _pubN_data from full format."""
    assert normalize_ma_id("CD001155_pub3_data__A5") == "CD001155__A5"
    assert normalize_ma_id("CD000028_pub4_data__A1") == "CD000028__A1"

def test_normalize_ma_id_already_short():
    """Already-normalized IDs pass through unchanged."""
    assert normalize_ma_id("CD011381__A1") == "CD011381__A1"

def test_normalize_ma_id_edge_cases():
    """Edge cases: no __, empty string."""
    assert normalize_ma_id("") == ""
    assert normalize_ma_id("CD001155") == "CD001155"
    assert normalize_ma_id("CD001155_pub3_data__A5__extra") == "CD001155__A5__extra"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Models\EvidenceScore && python -m pytest tests/test_score.py -k "normalize" -v`
Expected: FAIL — `normalize_ma_id` not defined

- [ ] **Step 3: Implement normalize_ma_id and update weights**

In `score_engine.py`, add after line 33 (after the assert):

```python
import re

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
```

Update WEIGHTS (lines 24-30):

```python
WEIGHTS = {
    "audit": 0.20,
    "consistency": 0.20,
    "robustness": 0.20,
    "stability": 0.20,
    "power": 0.20,
}
```

Update `compute_consistency_score` (lines 120-147) to normalize IDs:

```python
def compute_consistency_score(ma_id: str, contradiction_df: pd.DataFrame) -> float:
    if contradiction_df.empty:
        return 100.0

    norm_id = normalize_ma_id(ma_id)
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

    return max(0.0, score)
```

- [ ] **Step 4: Write test for consistency with normalized IDs**

```python
def test_consistency_with_normalized_ids():
    """Consistency works when formats differ (the bug fix)."""
    df = pd.DataFrame([
        {"ma_id_1": "CD001155__A5", "ma_id_2": "CD002000__A1", "contradiction_type": "direct"},
    ])
    # Full-format ID should match short-format contradiction
    score = compute_consistency_score("CD001155_pub3_data__A5", df)
    assert score == 75.0  # 100 - 25 for direct
```

- [ ] **Step 5: Update test_weights_sum_to_one and test_composite_score_perfect**

Update T20 to verify equal weights:
```python
def test_weights_sum_to_one():
    """T20: All component weights must sum to 1.0 and be equal."""
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9
    vals = list(WEIGHTS.values())
    assert all(abs(v - 0.20) < 1e-9 for v in vals), "All weights should be 0.20"
```

Update T24 expected score comment:
```python
def test_composite_score_perfect():
    """T24: Perfect MA with all best indicators should score high."""
    # ... (same fixture setup) ...
    # audit=100, consistency=100, robustness=100, stability=95, power=100
    # weighted = 0.2*100 + 0.2*100 + 0.2*100 + 0.2*95 + 0.2*100 = 99
    assert result["final_score"] >= 95
    assert result["grade"] == "A+"
```

- [ ] **Step 6: Run all tests**

Run: `cd C:\Models\EvidenceScore && python -m pytest tests/test_score.py -v`
Expected: ALL PASS (25 original + 4 new = 29)

- [ ] **Step 7: Commit**

---

### Task 2: Add sensitivity analysis module

**Files:**
- Create: `sensitivity.py`
- Test: `tests/test_score.py` (add tests)

- [ ] **Step 1: Write failing tests**

```python
from sensitivity import run_sensitivity_analysis

def test_sensitivity_analysis_shape():
    """50 schemes produced, all taus in [0,1]."""
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
    """Same seed = same result."""
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Models\EvidenceScore && python -m pytest tests/test_score.py -k "sensitivity" -v`
Expected: FAIL — cannot import `sensitivity`

- [ ] **Step 3: Implement sensitivity.py**

Create `C:\Models\EvidenceScore\sensitivity.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `cd C:\Models\EvidenceScore && python -m pytest tests/test_score.py -k "sensitivity" -v`
Expected: PASS

- [ ] **Step 5: Commit**

---

### Task 3: Add percentile rank and before/after comparison

**Files:**
- Modify: `score_engine.py` (add functions after `save_results`)
- Test: `tests/test_score.py`

- [ ] **Step 1: Write failing tests**

```python
from score_engine import add_percentile_rank, compute_before_after

def test_percentile_rank_bounds():
    """All percentile values in [0, 100]."""
    scores = [
        {"ma_id": f"MA{i}", "final_score": i * 10}
        for i in range(1, 11)
    ]
    result = add_percentile_rank(scores)
    for r in result:
        assert 0 <= r["percentile_rank"] <= 100

def test_percentile_rank_ordering():
    """Higher score = higher percentile."""
    scores = [
        {"ma_id": "LOW", "final_score": 20},
        {"ma_id": "MID", "final_score": 50},
        {"ma_id": "HIGH", "final_score": 90},
    ]
    result = add_percentile_rank(scores)
    by_id = {r["ma_id"]: r["percentile_rank"] for r in result}
    assert by_id["HIGH"] > by_id["MID"] > by_id["LOW"]

def test_before_after_symmetric():
    """Same MAs in both inputs."""
    v1 = [{"ma_id": "A", "final_score": 80, "grade": "A"},
          {"ma_id": "B", "final_score": 60, "grade": "C"}]
    v2 = [{"ma_id": "A", "final_score": 65, "grade": "C"},
          {"ma_id": "B", "final_score": 45, "grade": "F"}]
    result = compute_before_after(v1, v2)
    assert result["n_mas"] == 2
    assert result["v1_mean"] == 70.0
    assert result["v2_mean"] == 55.0
    assert result["grade_changes"]["downgraded"] == 2
```

- [ ] **Step 2: Implement add_percentile_rank and compute_before_after**

Add to `score_engine.py` after `save_results`:

```python
from scipy.stats import percentileofscore as _pctile


def add_percentile_rank(scores: list) -> list:
    """Add percentile_rank (0-100, 1 decimal) to each score dict."""
    all_scores = [s["final_score"] for s in scores]
    for s in scores:
        s["percentile_rank"] = round(
            _pctile(all_scores, s["final_score"], kind="rank"), 1
        )
    return scores


def compute_before_after(v1_scores: list, v2_scores: list) -> dict:
    """Compare v1 and v2 scores for the same MAs."""
    v1_map = {s["ma_id"]: s for s in v1_scores}
    v2_map = {s["ma_id"]: s for s in v2_scores}
    common = set(v1_map) & set(v2_map)

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
    v1_scores_arr = [v1_map[m]["final_score"] for m in common]
    v2_scores_arr = [v2_map[m]["final_score"] for m in common]

    from scipy.stats import spearmanr
    rho = spearmanr(v1_scores_arr, v2_scores_arr).statistic if len(common) > 2 else 1.0

    import numpy as np
    return {
        "n_mas": len(common),
        "v1_mean": round(float(np.mean(v1_scores_arr)), 1),
        "v2_mean": round(float(np.mean(v2_scores_arr)), 1),
        "mean_delta": round(float(np.mean(deltas)), 1),
        "grade_changes": {
            "upgraded": upgraded,
            "downgraded": downgraded,
            "unchanged": unchanged,
        },
        "top_movers": top_movers[:10],
        "rank_correlation": round(float(rho), 4),
    }
```

- [ ] **Step 3: Run tests**

Run: `cd C:\Models\EvidenceScore && python -m pytest tests/test_score.py -k "percentile or before_after" -v`
Expected: PASS

- [ ] **Step 4: Commit**

---

### Task 4: Create run_v2.py orchestrator

**Files:**
- Create: `run_v2.py`

- [ ] **Step 1: Create orchestrator**

```python
"""
EvidenceScore v2.0 — Orchestrator
Runs the full pipeline: score all MAs, sensitivity analysis, before/after, save artifacts.
"""

import io
import sys
import json
import platform

# Windows scipy deadlock prevention (per lessons.md)
if sys.platform == "win32":
    import faulthandler
    faulthandler.dump_traceback_later(30, exit=True)
    try:
        platform._wmi_query = lambda *a, **k: ""
    except Exception:
        pass

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd
from pathlib import Path
from score_engine import (
    compute_all, save_results, add_percentile_rank,
    compute_before_after, RESULTS_DIR,
)
from sensitivity import run_sensitivity_analysis


def main():
    print("=" * 60)
    print("EvidenceScore v2.0 — Full Pipeline")
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
```

- [ ] **Step 2: Run the pipeline**

Run: `cd C:\Models\EvidenceScore && python run_v2.py`
Expected: Scores recomputed, sensitivity analysis passes, before/after generated

- [ ] **Step 3: Verify consistency is no longer degenerate**

Run: `python -c "import pandas as pd; df=pd.read_csv('results/scores.csv'); print(f'consistency mean={df.consistency_score.mean():.1f}, std={df.consistency_score.std():.1f}, min={df.consistency_score.min()}, max={df.consistency_score.max()}')" `

Expected: Mean < 100.0, std > 0

- [ ] **Step 4: Run full test suite**

Run: `cd C:\Models\EvidenceScore && python -m pytest tests/test_score.py -v`
Expected: ALL PASS (35 tests)

- [ ] **Step 5: Commit**

---

### Task 5: Enhance dashboard with new visualizations

**Files:**
- Modify: `build_dashboard.py`

- [ ] **Step 1: Read current build_dashboard.py and add new sections**

Add after existing methodology section:
1. **Percentile rank column** in all tables
2. **Sensitivity heatmap** — canvas-based, 50 rows of tau values
3. **Before/After panel** — side-by-side stat cards + grade distribution shift
4. **Component correlation matrix** — 5x5 colored grid

- [ ] **Step 2: Update data loading to include new JSON files**

Read `sensitivity.json` and `before_after.json` alongside `scores.csv` and `summary.json`.

- [ ] **Step 3: Regenerate dashboard**

Run: `cd C:\Models\EvidenceScore && python build_dashboard.py`

- [ ] **Step 4: Verify dashboard renders**

Open `results/dashboard.html` in browser. Verify all new sections render.

- [ ] **Step 5: Update Command Center link**

Verify `C:\Models\EvidenceCommandCenter\index.html` link to `../EvidenceScore/results/dashboard.html` still works.

- [ ] **Step 6: Commit**

---

### Task 6: Update Command Center with corrected metrics

**Files:**
- Modify: `C:\Models\EvidenceCommandCenter\index.html`

- [ ] **Step 1: Update EvidenceScore metrics in Live Metrics section**

Read new `summary.json` and update the grade distribution bars, mean/median/range values.

- [ ] **Step 2: Update EvidenceScore card description**

Change from "Building" language to reflect v2.0 with equal weights and sensitivity analysis.

- [ ] **Step 3: Verify div balance**

- [ ] **Step 4: Commit**

---

### Task 7: Final verification

- [ ] **Step 1: Run full test suite**

Run: `cd C:\Models\EvidenceScore && python -m pytest tests/test_score.py -v`
Expected: ALL 35+ tests pass

- [ ] **Step 2: Verify key invariants**

- consistency_score varies (not all 100.0)
- sensitivity mean_tau > 0.85
- before_after.json exists with valid comparison
- dashboard.html renders all sections
- Command Center metrics updated

- [ ] **Step 3: Update review-findings.md**

Mark DOM-6 (credit score / consistency degenerate) as FIXED in Command Center review findings.

- [ ] **Step 4: Update INDEX.md**

Change EvidenceScore status from BUILDING to COMPLETE.
