# EvidenceScore v2.0 — Design Specification

## Date: 2026-04-01
## Status: Approved
## Target: Lancet Digital Health (Original Research)

---

## 1. Problem Statement

EvidenceScore v1.0 computes a 0-100 composite trust score for each of 6,229 Cochrane meta-analyses using 5 weighted components (Audit, Consistency, Robustness, Stability, Power). A critical bug renders the Consistency component degenerate: an MA ID format mismatch between the scores pipeline (`CD001155_pub3_data__A5`) and the ContradictionMap pipeline (`CD011381__A1`) means zero IDs ever match, so `compute_consistency_score()` returns 100.0 for all 6,229 MAs. This inflates every final score by ~20 points and eliminates the discriminative value of 20% of the composite.

Additionally, the v1.0 component weights (30/20/20/15/15) are arbitrary and unjustified — a peer review concern for any composite score.

## 2. Goals

1. Fix the consistency component by normalizing MA IDs across pipelines.
2. Switch to equal weights (0.20 each) with a defensible rationale.
3. Prove weight robustness via sensitivity analysis (50 Dirichlet-sampled weight vectors, Kendall's tau).
4. Add percentile rank alongside absolute grades for dual interpretation.
5. Regenerate the dashboard with new visualizations (sensitivity heatmap, before/after, correlation matrix).
6. All 25 existing tests pass + new tests for normalization, sensitivity, and percentile logic.

## 3. Non-Goals

- External validation against expert ratings (future work, noted as limitation).
- PCA-derived or data-driven weights (equal weighting is the chosen approach).
- Changing the other 4 component scoring algorithms (Audit, Robustness, Stability, Power are unchanged).
- Changing the grade threshold values (A+ >= 90, A >= 80, B >= 70, C >= 60, D >= 50, F < 50).

## 4. Architecture

### 4.1 MA ID Normalization

New function in `score_engine.py`:

```python
def normalize_ma_id(ma_id: str) -> str:
    """
    Normalize MA IDs to common format: {review_id}__{variant}
    
    Input formats:
      - CD001155_pub3_data__A5  -> CD001155__A5
      - CD011381__A1            -> CD011381__A1  (unchanged)
    
    Strategy: Split on '__', take the review_id prefix (strip _pubN_data suffix)
    and the variant suffix.
    """
```

Applied in two places:
1. `compute_consistency_score()` — normalize `ma_id` parameter and both `ma_id_1`/`ma_id_2` columns in contradiction_df at lookup time.
2. Not at CSV load time (preserve original IDs in output for traceability).

### 4.2 Equal Weights

```python
WEIGHTS = {
    "audit": 0.20,
    "consistency": 0.20,
    "robustness": 0.20,
    "stability": 0.20,
    "power": 0.20,
}
```

Rationale for the manuscript: "In the absence of an external criterion for calibration, equal weighting was adopted following the principle of maximum entropy — no component was assigned greater importance a priori. Sensitivity analysis confirmed that rankings were robust to weight perturbation."

### 4.3 Sensitivity Analysis

New module: `sensitivity.py`

```python
def run_sensitivity_analysis(
    scores_df: pd.DataFrame,  # DataFrame with 5 component columns
    n_schemes: int = 50,
    seed: int = 42,
) -> dict:
    """
    Generate n_schemes random weight vectors from Dirichlet(1,1,1,1,1),
    compute final scores under each, compare rankings to base (equal weights)
    via Kendall's tau.
    
    Returns:
        {
            "n_schemes": 50,
            "seed": 42,
            "base_weights": [0.20, 0.20, 0.20, 0.20, 0.20],
            "schemes": [
                {"weights": [...], "kendall_tau": 0.923, "mean_score": 51.2},
                ...
            ],
            "summary": {
                "mean_tau": 0.912,
                "min_tau": 0.847,
                "max_tau": 0.958,
                "std_tau": 0.024,
                "robust": true  // mean_tau > 0.85
            }
        }
    """
```

Dependencies: `scipy.stats.kendalltau`, `numpy.random.dirichlet`. Both already available (scipy used by EvidenceOracle).

### 4.4 Percentile Rank

Added as a post-processing step after all scores are computed:

```python
def add_percentile_rank(scores: list[dict]) -> list[dict]:
    """
    Add 'percentile_rank' field (0-100, rounded to 1 decimal) to each score dict.
    Uses scipy.stats.percentileofscore with kind='rank'.
    """
```

### 4.5 Grade Assignment

No change to thresholds. The `assign_grade()` function remains:
- A+ >= 90, A >= 80, B >= 70, C >= 60, D >= 50, F < 50

Expected shift in distribution (approximate):
- v1 mean: 69.0 → v2 mean: ~49-55 (depends on how many MAs have contradictions)
- More MAs will grade D/F — this is a finding, not a bug
- Percentile rank provides the relative context

### 4.6 Before/After Comparison

New function in `score_engine.py`:

```python
def compute_before_after(v1_scores: list[dict], v2_scores: list[dict]) -> dict:
    """
    Compare v1 and v2 scores for the same MAs.
    
    Returns:
        {
            "n_mas": 6229,
            "v1_mean": 69.0, "v2_mean": X,
            "mean_delta": Y,
            "grade_changes": {"upgraded": N, "downgraded": N, "unchanged": N},
            "top_movers": [...],  # 10 MAs with largest score drops
            "rank_correlation": float  # Spearman rho between v1 and v2 rankings
        }
    """
```

## 5. Output Artifacts

| File | Format | Contents |
|------|--------|----------|
| `results/scores_v2.csv` | CSV, 6229 rows | ma_id, review_id, audit_score, consistency_score, robustness_score, stability_score, power_score, final_score, grade, grade_label, percentile_rank |
| `results/summary_v2.json` | JSON | Aggregate stats, grade distribution, component means, weight scheme |
| `results/sensitivity.json` | JSON | 50 weight vectors + Kendall's tau per scheme + summary stats |
| `results/before_after.json` | JSON | v1 vs v2 comparison metrics |
| `results/dashboard.html` | HTML | Regenerated interactive dashboard |

## 6. Dashboard v2 Enhancements

### Kept from v1:
- Hero section with summary stats
- Score histogram (10 bins, color-coded)
- Grade pie chart with percentages
- Interactive radar chart (5-axis, MA selector dropdown)
- Top 20 / Bottom 20 tables
- Searchable full table (first 200 rows, expandable)
- Methodology section with component explanation cards

### New in v2:
- **Percentile rank column** in all tables
- **Sensitivity heatmap** — 50 rows (weight schemes) x color-coded tau values, with mean/min/max annotation
- **Before/After panel** — side-by-side comparison: v1 vs v2 means, grade distribution shift, top 10 movers
- **Component correlation matrix** — 5x5 heatmap showing Pearson correlations between component scores
- **Score-by-review boxplot** — distribution of scores within each Cochrane review
- **"Equal weights" methodology note** — updated methodology cards explaining the rationale and sensitivity results

## 7. Testing Strategy

### Existing tests (25, must all pass):
- All `test_audit_score_*`, `test_robustness_*`, `test_stability_*`, `test_power_*` — unchanged
- `test_consistency_*` — will need fixture updates to use normalized IDs
- `test_weights_sum_to_one` — updated to verify 0.20 each
- `test_integration_real_data` — updated expectations for new score distribution

### New tests:
- `test_normalize_ma_id_full_format` — `CD001155_pub3_data__A5` -> `CD001155__A5`
- `test_normalize_ma_id_already_short` — `CD011381__A1` -> `CD011381__A1`
- `test_normalize_ma_id_edge_cases` — no `__`, multiple `__`, empty string
- `test_consistency_with_normalized_ids` — verify non-100.0 scores when contradictions exist
- `test_sensitivity_analysis_shape` — 50 schemes, all taus in [0,1]
- `test_sensitivity_analysis_deterministic` — same seed = same result
- `test_percentile_rank_bounds` — all values in [0, 100]
- `test_percentile_rank_ordering` — higher score = higher percentile
- `test_before_after_symmetric` — same MAs in both inputs
- `test_equal_weights` — verify all 5 weights are 0.20

### Validation:
- After scoring, verify consistency_score < 100.0 for MAs involved in contradictions
- Spot-check: MA in ContradictionMap with direct reversal should have consistency_score <= 75
- Verify total scored = 6,229 (no MAs lost in normalization)

## 8. File Changes

| File | Action | Scope |
|------|--------|-------|
| `score_engine.py` | Modify | Add `normalize_ma_id()`, update weights to equal, add `add_percentile_rank()`, add `compute_before_after()` |
| `sensitivity.py` | Create | New module for sensitivity analysis |
| `build_dashboard.py` | Modify | Add new chart sections (heatmap, before/after, correlation, boxplot), update methodology cards |
| `tests/test_score.py` | Modify | Update existing consistency/weight tests, add ~10 new tests |
| `run_v2.py` | Create | Orchestrator: load data → score → sensitivity → before/after → save artifacts → build dashboard |

## 9. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Normalization misses edge cases | Test with full 6,229 MA ID set; verify count before/after |
| Sensitivity tau too low (weights matter too much) | If mean tau < 0.85, report honestly as a limitation; consider dropping weakest component |
| Dashboard too large (>2MB) | Sensitivity data is 50 rows, not 6229; embed summary, link to full JSON |
| scipy import deadlock on Windows | Apply `platform._wmi_query` monkey-patch per lessons.md before scipy import |

## 10. Success Criteria

1. All 35+ tests pass (25 existing + 10 new)
2. consistency_score varies across MAs (not degenerate)
3. Mean Kendall's tau > 0.85 across 50 weight schemes
4. Dashboard loads and renders all new sections
5. Command Center links to updated dashboard
6. `before_after.json` shows the impact clearly
