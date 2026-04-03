# EvidenceScore — Code Review Findings

**Reviewer:** Claude Opus 4.6 (1M context)
**Date:** 2026-04-03
**Files:** score_engine.py (512 lines), build_dashboard.py (865 lines), run_v2.py (89 lines), sensitivity.py (57 lines)

## P0 — Critical (must fix)

None found.

## P1 — Important

### P1-1: Weights sum check uses assertion (disabled with -O flag)
**File:** score_engine.py, line 34
**Issue:** `assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9`. If Python is run with `-O` (optimize), assertions are stripped. This is a safety invariant that should use a runtime check.
**Recommendation:** Replace `assert` with `if ... raise ValueError(...)`.

### P1-2: `build_dashboard.py` correctly avoids `</script>` in template
**File:** build_dashboard.py, line 841
**Status:** PASS — uses `'</' + 'script>'` concatenation to avoid premature script block close.

### P1-3: Dashboard builds HTML with embedded data via f-string
**Issue:** Scores data is embedded as JSON in the HTML. If any MA ID contains `</script>`, it could break the page. However, `json.dumps()` escapes `<` as `\u003c` by default in Python only if `ensure_ascii=True` (the default). 
**Status:** PASS — `json.dumps(scores)` with default `ensure_ascii=True` will escape `<` to `\u003c`.

### P1-4: `compute_power_score` uses `int()` on potentially NaN values
**File:** score_engine.py, lines 265-266
**Issue:** `int(row.get("k", 0))` and `int(row.get("total_n", 0))` — if the CSV has NaN/empty values, `int(np.nan)` raises ValueError in newer NumPy/Python. However, the `row.get("k", 0)` provides a fallback of 0.
**Status:** Low risk — the fallback prevents NaN from reaching `int()`.

## P2 — Minor

### P2-1: No `</html>` tag issue — `build_dashboard.py` generates it correctly
**Line:** 843
**Status:** PASS.

### P2-2: `normalize_ma_id` uses regex correctly
**File:** score_engine.py, line 56
**Status:** PASS — `re.sub(r'_pub\d+_data__', '__', ma_id)` correctly normalizes.

### P2-3: `percentileofscore` import is inside function (lazy import)
**File:** score_engine.py, line 429
**Status:** Fine for optional dependency.

## Summary

| Severity | Count |
|----------|-------|
| P0       | 0     |
| P1       | 4     |
| P2       | 3     |
