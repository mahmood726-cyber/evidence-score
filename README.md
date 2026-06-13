# evidence-score

EvidenceScore computes a composite 0-100 trust score for each meta-analysis by
combining signals from four upstream pipelines (MetaAudit, ContradictionMap,
ActionableEvidence, EvidenceOracle).

## What it does

`score_engine.py` aggregates five component scores with configurable weights
(default: equal 0.20 each) and assigns an A+/A/B/C/D/F grade:

- **audit** — deductions per MetaAudit finding
- **consistency** — deductions per ContradictionMap contradiction
- **robustness** — additive ActionableEvidence indicators (PI, significance,
  publication bias, fragility, audit fails)
- **stability** — EvidenceOracle instability prediction
- **power** — k (studies) and total N

`sensitivity.py` measures rank stability of the composite under random Dirichlet
weight vectors via Kendall's tau. `run_v2.py` orchestrates the full pipeline.

`index.html` is the E156 micro-paper landing page (see `E156-PROTOCOL.md`).

## Run

```
python run_v2.py        # full pipeline (requires upstream result CSVs)
python -m pytest -q     # tests
```

The composite weights are heuristic; the score is a triage aid, not a validated
measure of evidence trustworthiness.

## License

Code: MIT. Manuscript: CC-BY-4.0.
