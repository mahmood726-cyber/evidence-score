"""
Build an interactive single-file HTML dashboard for EvidenceScore results.
Reads scores.csv and summary.json, outputs dashboard.html.
"""

import os
import json
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
SCORES_CSV = RESULTS_DIR / "scores.csv"
SUMMARY_JSON = RESULTS_DIR / "summary.json"
OUTPUT_HTML = RESULTS_DIR / "dashboard.html"


def read_scores():
    """Read scores.csv and return list of dicts."""
    rows = []
    with open(SCORES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def read_summary():
    """Read summary.json."""
    with open(SUMMARY_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def build_html(scores, summary):
    """Build the complete HTML dashboard string."""
    # Prepare JSON data for embedding
    scores_json = json.dumps(scores)
    summary_json = json.dumps(summary)

    # Top 20 and bottom 20
    top20 = scores[:20]
    bottom20 = scores[-20:]

    # Grade distribution for pie chart
    grade_dist = summary["grade_distribution"]
    component_means = summary["component_means"]

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EvidenceScore Dashboard</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #1a1a2e;
    color: #e0e0e0;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    line-height: 1.6;
}}
.es-container {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
}}

/* Hero */
.es-hero {{
    text-align: center;
    padding: 60px 20px 40px;
    background: linear-gradient(135deg, #16213e 0%, #1a1a2e 50%, #0f3460 100%);
    border-bottom: 2px solid #0f3460;
    margin-bottom: 30px;
}}
.es-hero h1 {{
    font-size: 2.8rem;
    font-weight: 700;
    color: #e0e0e0;
    margin-bottom: 10px;
}}
.es-hero h1 span {{ color: #00d4aa; }}
.es-hero p {{
    font-size: 1.2rem;
    color: #8892b0;
    max-width: 700px;
    margin: 0 auto;
}}
.es-stats-row {{
    display: flex;
    justify-content: center;
    gap: 40px;
    margin-top: 30px;
    flex-wrap: wrap;
}}
.es-stat-card {{
    text-align: center;
    padding: 15px 25px;
    background: rgba(255,255,255,0.05);
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.1);
    min-width: 140px;
}}
.es-stat-card .es-stat-value {{
    font-size: 2.2rem;
    font-weight: 700;
    color: #00d4aa;
}}
.es-stat-card .es-stat-label {{
    font-size: 0.85rem;
    color: #8892b0;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* Sections */
.es-section {{
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 30px;
    margin-bottom: 25px;
}}
.es-section h2 {{
    font-size: 1.5rem;
    color: #e0e0e0;
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
}}

/* Chart containers */
.es-chart-row {{
    display: flex;
    gap: 25px;
    flex-wrap: wrap;
}}
.es-chart-box {{
    flex: 1;
    min-width: 300px;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 20px;
    text-align: center;
}}
.es-chart-box h3 {{
    font-size: 1.1rem;
    color: #8892b0;
    margin-bottom: 15px;
}}
canvas {{ max-width: 100%; }}

/* Tables */
.es-table-wrap {{
    overflow-x: auto;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
}}
th, td {{
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}}
th {{
    background: rgba(255,255,255,0.05);
    color: #8892b0;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.8rem;
    letter-spacing: 0.5px;
    position: sticky;
    top: 0;
    z-index: 2;
}}
tr:hover td {{
    background: rgba(255,255,255,0.03);
}}

/* Grade badges */
.es-grade {{
    display: inline-block;
    padding: 4px 12px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.85rem;
    text-align: center;
    min-width: 40px;
}}
.es-grade-aplus {{ background: #059669; color: #fff; }}
.es-grade-a {{ background: #10b981; color: #fff; }}
.es-grade-b {{ background: #3b82f6; color: #fff; }}
.es-grade-c {{ background: #f59e0b; color: #1a1a2e; }}
.es-grade-d {{ background: #f97316; color: #1a1a2e; }}
.es-grade-f {{ background: #ef4444; color: #fff; }}

/* Score bar */
.es-score-bar {{
    display: inline-block;
    height: 8px;
    border-radius: 4px;
    vertical-align: middle;
    margin-left: 8px;
}}

/* Search */
.es-search-box {{
    width: 100%;
    padding: 12px 16px;
    font-size: 1rem;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px;
    color: #e0e0e0;
    margin-bottom: 15px;
    outline: none;
}}
.es-search-box:focus {{
    border-color: #00d4aa;
    box-shadow: 0 0 0 2px rgba(0,212,170,0.2);
}}
.es-search-box::placeholder {{ color: #555; }}

/* Radar */
.es-radar-select {{
    padding: 8px 12px;
    font-size: 0.9rem;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 6px;
    color: #e0e0e0;
    margin-bottom: 15px;
    max-width: 400px;
}}

/* Scrollable table */
.es-scrollable {{
    max-height: 600px;
    overflow-y: auto;
}}

/* Methodology */
.es-method {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 15px;
}}
.es-method-card {{
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 18px;
}}
.es-method-card h4 {{
    font-size: 1rem;
    color: #00d4aa;
    margin-bottom: 8px;
}}
.es-method-card p {{
    font-size: 0.85rem;
    color: #8892b0;
}}
.es-method-card .es-weight {{
    display: inline-block;
    padding: 2px 8px;
    background: rgba(0,212,170,0.15);
    border-radius: 4px;
    font-size: 0.8rem;
    color: #00d4aa;
    margin-bottom: 8px;
}}

/* Footer */
.es-footer {{
    text-align: center;
    padding: 30px;
    color: #555;
    font-size: 0.85rem;
}}
.es-footer a {{ color: #00d4aa; text-decoration: none; }}

/* Responsive */
@media (max-width: 768px) {{
    .es-hero h1 {{ font-size: 1.8rem; }}
    .es-stats-row {{ gap: 15px; }}
    .es-stat-card {{ min-width: 100px; padding: 10px 15px; }}
    .es-stat-card .es-stat-value {{ font-size: 1.6rem; }}
    .es-chart-row {{ flex-direction: column; }}
}}
</style>
</head>
<body>

<!-- Hero Section -->
<div class="es-hero">
    <h1><span>EvidenceScore</span> Dashboard</h1>
    <p>A composite 0-100 trust score for every meta-analysis, combining audit quality, consistency, robustness, stability, and statistical power.</p>
    <div class="es-stats-row">
        <div class="es-stat-card">
            <div class="es-stat-value" id="es-total">{summary['total_scored']:,}</div>
            <div class="es-stat-label">MAs Scored</div>
        </div>
        <div class="es-stat-card">
            <div class="es-stat-value" id="es-mean">{summary['mean_score']}</div>
            <div class="es-stat-label">Mean Score</div>
        </div>
        <div class="es-stat-card">
            <div class="es-stat-value" id="es-median">{summary['median_score']}</div>
            <div class="es-stat-label">Median Score</div>
        </div>
        <div class="es-stat-card">
            <div class="es-stat-value" id="es-range">{summary['min_score']}-{summary['max_score']}</div>
            <div class="es-stat-label">Score Range</div>
        </div>
    </div>
</div>

<div class="es-container">

<!-- Charts Row -->
<div class="es-chart-row">
    <div class="es-chart-box">
        <h3>Score Distribution</h3>
        <canvas id="es-histogram" width="600" height="350"></canvas>
    </div>
    <div class="es-chart-box">
        <h3>Grade Distribution</h3>
        <canvas id="es-pie" width="400" height="350"></canvas>
    </div>
</div>

<!-- Radar Chart for Selected MA -->
<div class="es-section">
    <h2>Component Breakdown</h2>
    <p style="color:#8892b0;margin-bottom:15px;">Select a meta-analysis to view its component radar chart.</p>
    <select class="es-radar-select" id="es-radar-select" aria-label="Select meta-analysis for component breakdown">
        <option value="">-- Select MA --</option>
    </select>
    <div style="display:flex;gap:30px;flex-wrap:wrap;align-items:center;">
        <canvas id="es-radar" width="420" height="420"></canvas>
        <div id="es-radar-details" style="flex:1;min-width:250px;"></div>
    </div>
</div>

<!-- Top 20 -->
<div class="es-section">
    <h2>Top 20 Most Trustworthy Meta-Analyses</h2>
    <div class="es-table-wrap">
        <table id="es-top-table">
            <thead>
                <tr>
                    <th>#</th><th>MA ID</th><th>Review</th><th>Score</th>
                    <th>Grade</th><th>Audit</th><th>Consistency</th>
                    <th>Robustness</th><th>Stability</th><th>Power</th>
                </tr>
            </thead>
            <tbody id="es-top-body"></tbody>
        </table>
    </div>
</div>

<!-- Bottom 20 -->
<div class="es-section">
    <h2>Bottom 20 Least Trustworthy Meta-Analyses</h2>
    <div class="es-table-wrap">
        <table id="es-bottom-table">
            <thead>
                <tr>
                    <th>#</th><th>MA ID</th><th>Review</th><th>Score</th>
                    <th>Grade</th><th>Audit</th><th>Consistency</th>
                    <th>Robustness</th><th>Stability</th><th>Power</th>
                </tr>
            </thead>
            <tbody id="es-bottom-body"></tbody>
        </table>
    </div>
</div>

<!-- Searchable Full Table -->
<div class="es-section">
    <h2>All Meta-Analyses</h2>
    <input type="text" class="es-search-box" id="es-search" placeholder="Search by MA ID or Review ID..." aria-label="Search meta-analyses">
    <div class="es-table-wrap es-scrollable">
        <table id="es-all-table">
            <thead>
                <tr>
                    <th>#</th><th>MA ID</th><th>Review</th><th>Score</th>
                    <th>Grade</th><th>Audit</th><th>Consistency</th>
                    <th>Robustness</th><th>Stability</th><th>Power</th>
                </tr>
            </thead>
            <tbody id="es-all-body"></tbody>
        </table>
    </div>
    <div id="es-showing" style="color:#8892b0;font-size:0.85rem;margin-top:10px;"></div>
</div>

<!-- Methodology -->
<div class="es-section">
    <h2>Scoring Methodology</h2>
    <div class="es-method">
        <div class="es-method-card">
            <h4>Audit Score</h4>
            <div class="es-weight">Weight: 30%</div>
            <p>Starts at 100. Each CRITICAL finding deducts 20 points, each WARNING deducts 8 points. Based on 11 MetaAudit detectors covering prediction gaps, model misspecification, excess significance, publication bias, fragility, overlap, and more.</p>
        </div>
        <div class="es-method-card">
            <h4>Consistency Score</h4>
            <div class="es-weight">Weight: 20%</div>
            <p>Starts at 100. Deductions per contradiction: direct (-25), magnitude (-15), significance (-10). Measures whether different MAs on similar topics agree.</p>
        </div>
        <div class="es-method-card">
            <h4>Robustness Score</h4>
            <div class="es-weight">Weight: 20%</div>
            <p>Additive: PI not crossing null (+30), significant p-value (+20), no publication bias (+20), robust fragility (+20), no audit failures (+10). Max 100.</p>
        </div>
        <div class="es-method-card">
            <h4>Stability Score</h4>
            <div class="es-weight">Weight: 15%</div>
            <p>Based on EvidenceOracle ML predictions. Score = 100 x (1 - probability of instability). Uses gradient boosting model with AUC 0.925.</p>
        </div>
        <div class="es-method-card">
            <h4>Power Score</h4>
            <div class="es-weight">Weight: 15%</div>
            <p>Based on number of studies (k) and total sample size (N). Thresholds: k&ge;10 &amp; N&ge;1000 = 100, k&ge;5 &amp; N&ge;500 = 75, k&ge;3 &amp; N&ge;200 = 50, else 25.</p>
        </div>
    </div>
</div>

<!-- Footer -->
<div class="es-footer">
    <p>EvidenceScore combines signals from <strong>MetaAudit</strong>, <strong>ContradictionMap</strong>, <strong>ActionableEvidence</strong>, and <strong>EvidenceOracle</strong>.</p>
    <p>Covering {summary['total_scored']:,} Cochrane meta-analyses. Generated {__import__('datetime').date.today().isoformat()}.</p>
</div>

</div>

<script>
// ── Data ───────────────────────────────────────────────────────────────────
var ES_DATA = {scores_json};
var ES_SUMMARY = {summary_json};

// ── Grade helpers ──────────────────────────────────────────────────────────
function esGradeClass(g) {{
    var m = {{'A+':'es-grade-aplus','A':'es-grade-a','B':'es-grade-b',
              'C':'es-grade-c','D':'es-grade-d','F':'es-grade-f'}};
    return m[g] || 'es-grade-f';
}}

function esGradeColor(g) {{
    var m = {{'A+':'#059669','A':'#10b981','B':'#3b82f6',
              'C':'#f59e0b','D':'#f97316','F':'#ef4444'}};
    return m[g] || '#ef4444';
}}

function esScoreColor(s) {{
    s = parseFloat(s);
    if (s >= 90) return '#059669';
    if (s >= 80) return '#10b981';
    if (s >= 70) return '#3b82f6';
    if (s >= 60) return '#f59e0b';
    if (s >= 50) return '#f97316';
    return '#ef4444';
}}

// ── Table rendering ────────────────────────────────────────────────────────
function esRenderRow(d, idx) {{
    var gc = esGradeClass(d.grade);
    var sc = esScoreColor(d.final_score);
    var barW = Math.max(2, parseFloat(d.final_score));
    return '<tr>' +
        '<td>' + (idx + 1) + '</td>' +
        '<td style="font-family:monospace;font-size:0.85rem;">' + d.ma_id + '</td>' +
        '<td>' + (d.review_id || '') + '</td>' +
        '<td><strong style="color:' + sc + '">' + d.final_score + '</strong>' +
            '<span class="es-score-bar" style="width:' + barW + 'px;background:' + sc + '"></' + 'span></td>' +
        '<td><span class="es-grade ' + gc + '">' + d.grade + '</span></td>' +
        '<td>' + d.audit_score + '</td>' +
        '<td>' + d.consistency_score + '</td>' +
        '<td>' + d.robustness_score + '</td>' +
        '<td>' + d.stability_score + '</td>' +
        '<td>' + d.power_score + '</td>' +
    '</tr>';
}}

function esPopulateTable(bodyId, data, start) {{
    var body = document.getElementById(bodyId);
    var html = '';
    for (var i = 0; i < data.length; i++) {{
        html += esRenderRow(data[i], (start || 0) + i);
    }}
    body.innerHTML = html;
}}

// Top 20 and Bottom 20
esPopulateTable('es-top-body', ES_DATA.slice(0, 20), 0);
esPopulateTable('es-bottom-body', ES_DATA.slice(-20).reverse(), ES_DATA.length - 20);

// Full table (initial: first 200)
var esAllShown = 200;
function esRenderAll(filter) {{
    var body = document.getElementById('es-all-body');
    var html = '';
    var count = 0;
    var total = 0;
    for (var i = 0; i < ES_DATA.length; i++) {{
        var d = ES_DATA[i];
        if (filter && d.ma_id.toLowerCase().indexOf(filter) === -1 &&
            (d.review_id || '').toLowerCase().indexOf(filter) === -1) continue;
        total++;
        if (count < esAllShown) {{
            html += esRenderRow(d, i);
            count++;
        }}
    }}
    body.innerHTML = html;
    document.getElementById('es-showing').textContent =
        'Showing ' + count + ' of ' + total + ' meta-analyses' +
        (total < ES_DATA.length ? ' (filtered)' : '') +
        (count < total ? ' — scroll or refine search to see more' : '');
}}
esRenderAll('');

document.getElementById('es-search').addEventListener('input', function() {{
    esAllShown = 500;
    esRenderAll(this.value.trim().toLowerCase());
}});

// ── Histogram ──────────────────────────────────────────────────────────────
(function() {{
    var canvas = document.getElementById('es-histogram');
    var ctx = canvas.getContext('2d');
    var W = canvas.width, H = canvas.height;
    var pad = {{t:30,r:20,b:50,l:55}};
    var cW = W - pad.l - pad.r;
    var cH = H - pad.t - pad.b;

    // Build bins 0-9, 10-19, ..., 90-100
    var bins = new Array(10).fill(0);
    for (var i = 0; i < ES_DATA.length; i++) {{
        var s = parseInt(ES_DATA[i].final_score);
        var b = Math.min(9, Math.floor(s / 10));
        bins[b]++;
    }}
    var maxBin = Math.max.apply(null, bins);

    // Background
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, W, H);

    // Grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 1;
    for (var g = 0; g <= 5; g++) {{
        var y = pad.t + cH - (g / 5) * cH;
        ctx.beginPath();
        ctx.moveTo(pad.l, y);
        ctx.lineTo(pad.l + cW, y);
        ctx.stroke();
        // Y axis label
        ctx.fillStyle = '#8892b0';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(Math.round(maxBin * g / 5), pad.l - 8, y + 4);
    }}

    // Bars
    var barW = cW / 10 - 4;
    var labels = ['0-9','10-19','20-29','30-39','40-49','50-59','60-69','70-79','80-89','90-100'];
    var colors = ['#ef4444','#ef4444','#ef4444','#ef4444','#f97316','#f97316','#f59e0b','#3b82f6','#10b981','#059669'];

    for (var i = 0; i < 10; i++) {{
        var x = pad.l + i * (cW / 10) + 2;
        var barH = maxBin > 0 ? (bins[i] / maxBin) * cH : 0;
        var y = pad.t + cH - barH;

        ctx.fillStyle = colors[i];
        ctx.beginPath();
        // Rounded top
        var r = Math.min(4, barW/2, barH/2);
        if (barH > 0) {{
            ctx.moveTo(x, y + barH);
            ctx.lineTo(x, y + r);
            ctx.quadraticCurveTo(x, y, x + r, y);
            ctx.lineTo(x + barW - r, y);
            ctx.quadraticCurveTo(x + barW, y, x + barW, y + r);
            ctx.lineTo(x + barW, y + barH);
        }}
        ctx.fill();

        // Count label on top
        if (bins[i] > 0) {{
            ctx.fillStyle = '#e0e0e0';
            ctx.font = '11px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(bins[i], x + barW / 2, y - 6);
        }}

        // X axis label
        ctx.fillStyle = '#8892b0';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.save();
        ctx.translate(x + barW / 2, pad.t + cH + 15);
        ctx.fillText(labels[i], 0, 0);
        ctx.restore();
    }}

    // Axis labels
    ctx.fillStyle = '#8892b0';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('EvidenceScore', pad.l + cW / 2, H - 5);
    ctx.save();
    ctx.translate(12, pad.t + cH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Count', 0, 0);
    ctx.restore();
}})();

// ── Pie Chart ──────────────────────────────────────────────────────────────
(function() {{
    var canvas = document.getElementById('es-pie');
    var ctx = canvas.getContext('2d');
    var W = canvas.width, H = canvas.height;
    var cx = W / 2 - 40, cy = H / 2, R = Math.min(cx, cy) - 30;

    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, W, H);

    var gd = ES_SUMMARY.grade_distribution;
    var grades = ['A+', 'A', 'B', 'C', 'D', 'F'];
    var gColors = {{'A+':'#059669','A':'#10b981','B':'#3b82f6',
                   'C':'#f59e0b','D':'#f97316','F':'#ef4444'}};
    var total = 0;
    for (var i = 0; i < grades.length; i++) total += (gd[grades[i]] || 0);

    var angle = -Math.PI / 2;
    for (var i = 0; i < grades.length; i++) {{
        var count = gd[grades[i]] || 0;
        if (count === 0) continue;
        var slice = (count / total) * 2 * Math.PI;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.arc(cx, cy, R, angle, angle + slice);
        ctx.closePath();
        ctx.fillStyle = gColors[grades[i]];
        ctx.fill();
        ctx.strokeStyle = '#1a1a2e';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Label
        var mid = angle + slice / 2;
        var lx = cx + Math.cos(mid) * (R * 0.65);
        var ly = cy + Math.sin(mid) * (R * 0.65);
        var pct = ((count / total) * 100).toFixed(1);
        if (parseFloat(pct) >= 3) {{
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 13px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(grades[i], lx, ly - 8);
            ctx.font = '11px sans-serif';
            ctx.fillText(pct + '%', lx, ly + 8);
        }}

        angle += slice;
    }}

    // Legend
    var lx = W - 100, ly = 40;
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'left';
    for (var i = 0; i < grades.length; i++) {{
        var count = gd[grades[i]] || 0;
        ctx.fillStyle = gColors[grades[i]];
        ctx.fillRect(lx, ly + i * 22, 14, 14);
        ctx.fillStyle = '#e0e0e0';
        ctx.fillText(grades[i] + ': ' + count, lx + 20, ly + i * 22 + 11);
    }}
}})();

// ── Radar Chart ────────────────────────────────────────────────────────────
var esRadarCanvas = document.getElementById('es-radar');
var esRadarCtx = esRadarCanvas.getContext('2d');
var esRadarSelect = document.getElementById('es-radar-select');

// Populate select with all MAs
(function() {{
    var frag = document.createDocumentFragment();
    for (var i = 0; i < ES_DATA.length; i++) {{
        var opt = document.createElement('option');
        opt.value = i;
        opt.textContent = ES_DATA[i].ma_id + ' (Score: ' + ES_DATA[i].final_score + ', ' + ES_DATA[i].grade + ')';
        frag.appendChild(opt);
    }}
    esRadarSelect.appendChild(frag);
}})();

function esDrawRadar(idx) {{
    var canvas = esRadarCanvas;
    var ctx = esRadarCtx;
    var W = canvas.width, H = canvas.height;
    var cx = W / 2, cy = H / 2, R = Math.min(cx, cy) - 50;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, W, H);

    var labels = ['Audit', 'Consistency', 'Robustness', 'Stability', 'Power'];
    var n = labels.length;
    var angleStep = (2 * Math.PI) / n;
    var startAngle = -Math.PI / 2;

    // Grid rings
    for (var ring = 1; ring <= 5; ring++) {{
        var r = (ring / 5) * R;
        ctx.beginPath();
        for (var i = 0; i < n; i++) {{
            var a = startAngle + i * angleStep;
            var x = cx + Math.cos(a) * r;
            var y = cy + Math.sin(a) * r;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }}
        ctx.closePath();
        ctx.strokeStyle = 'rgba(255,255,255,0.1)';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Ring value label
        ctx.fillStyle = '#555';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(ring * 20, cx, cy - r - 3);
    }}

    // Spokes + labels
    for (var i = 0; i < n; i++) {{
        var a = startAngle + i * angleStep;
        var ex = cx + Math.cos(a) * R;
        var ey = cy + Math.sin(a) * R;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(ex, ey);
        ctx.strokeStyle = 'rgba(255,255,255,0.08)';
        ctx.stroke();

        // Labels
        var lx = cx + Math.cos(a) * (R + 25);
        var ly = cy + Math.sin(a) * (R + 25);
        ctx.fillStyle = '#8892b0';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(labels[i], lx, ly);
    }}

    if (idx === null || idx === undefined || idx === '') return;

    var d = ES_DATA[idx];
    var values = [
        parseFloat(d.audit_score),
        parseFloat(d.consistency_score),
        parseFloat(d.robustness_score),
        parseFloat(d.stability_score),
        parseFloat(d.power_score)
    ];

    // Data polygon
    ctx.beginPath();
    for (var i = 0; i < n; i++) {{
        var a = startAngle + i * angleStep;
        var v = Math.max(0, Math.min(100, values[i]));
        var r = (v / 100) * R;
        var x = cx + Math.cos(a) * r;
        var y = cy + Math.sin(a) * r;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }}
    ctx.closePath();
    ctx.fillStyle = 'rgba(0, 212, 170, 0.2)';
    ctx.fill();
    ctx.strokeStyle = '#00d4aa';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Data points
    for (var i = 0; i < n; i++) {{
        var a = startAngle + i * angleStep;
        var v = Math.max(0, Math.min(100, values[i]));
        var r = (v / 100) * R;
        var x = cx + Math.cos(a) * r;
        var y = cy + Math.sin(a) * r;
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, 2 * Math.PI);
        ctx.fillStyle = '#00d4aa';
        ctx.fill();
        ctx.strokeStyle = '#1a1a2e';
        ctx.lineWidth = 2;
        ctx.stroke();
    }}

    // Details panel
    var details = document.getElementById('es-radar-details');
    details.innerHTML =
        '<div style="padding:15px;background:rgba(255,255,255,0.03);border-radius:10px;border:1px solid rgba(255,255,255,0.08)">' +
        '<h3 style="color:#e0e0e0;margin-bottom:10px;font-size:1.1rem;">' + d.ma_id + '</h3>' +
        '<div style="font-size:2.5rem;font-weight:700;color:' + esScoreColor(d.final_score) + '">' +
            d.final_score + '<span style="font-size:1rem;color:#8892b0"> / 100</span></div>' +
        '<div style="margin:8px 0"><span class="es-grade ' + esGradeClass(d.grade) + '">' + d.grade + '</span> ' +
            '<span style="color:#8892b0">' + d.grade_label + '</span></div>' +
        '<hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:12px 0">' +
        '<table style="width:100%;font-size:0.9rem;">' +
        '<tr><td style="color:#8892b0">Review ID</td><td style="text-align:right">' + (d.review_id || 'N/A') + '</td></tr>' +
        '<tr><td style="color:#8892b0">Audit</td><td style="text-align:right;color:' + esScoreColor(d.audit_score) + '">' + d.audit_score + '</td></tr>' +
        '<tr><td style="color:#8892b0">Consistency</td><td style="text-align:right;color:' + esScoreColor(d.consistency_score) + '">' + d.consistency_score + '</td></tr>' +
        '<tr><td style="color:#8892b0">Robustness</td><td style="text-align:right;color:' + esScoreColor(d.robustness_score) + '">' + d.robustness_score + '</td></tr>' +
        '<tr><td style="color:#8892b0">Stability</td><td style="text-align:right;color:' + esScoreColor(d.stability_score) + '">' + d.stability_score + '</td></tr>' +
        '<tr><td style="color:#8892b0">Power</td><td style="text-align:right;color:' + esScoreColor(d.power_score) + '">' + d.power_score + '</td></tr>' +
        '</table></div>';
}}

// Initial radar (empty)
esDrawRadar(null);

esRadarSelect.addEventListener('change', function() {{
    var v = this.value;
    esDrawRadar(v === '' ? null : parseInt(v));
}});

// Auto-select first MA for demo
if (ES_DATA.length > 0) {{
    esRadarSelect.value = '0';
    esDrawRadar(0);
}}
</' + 'script>
</body>
</html>'''

    return html


def main():
    print("Reading scores and summary...")
    scores = read_scores()
    summary = read_summary()

    print(f"Building dashboard for {len(scores)} meta-analyses...")
    html = build_html(scores, summary)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard saved to {OUTPUT_HTML}")
    print(f"  File size: {os.path.getsize(OUTPUT_HTML) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
