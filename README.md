# GenAI Reporting Pipeline

**Replaced a 5-stage manual sales reporting process with a single command.**

| | Before | After |
|--|--------|-------|
| Step 1 | Download CSV, open Excel | `python genai_pipeline.py` |
| Step 2 | Clean & filter data manually | Pandas validation + enrichment |
| Step 3 | Calculate KPIs in formula cells | Python metric engine |
| Step 4 | Check for anomalies by eye | Rule-based anomaly detection |
| Step 5 | Write summary email to leadership | Gemini 1.5 Flash executive summary |

**Result:** One command. Zero manual steps. Full stakeholder report in seconds.

---

## How it works

```
data/sales_data.csv
       ↓
  Validation & enrichment (Pandas)
       ↓
  KPI computation (revenue, returns, MoM growth, top performers)
       ↓
  Anomaly detection (statistical flagging)
       ↓
  Executive summary (Gemini 1.5 Flash — free tier)
       ↓
outputs/report_YYYYMMDD.md  ← ready to share
```

**See a real output:** [`outputs/sample_report.md`](outputs/sample_report.md)

---

## Automation (Zapier equivalent)

Drop a CSV into a watched folder → pipeline fires automatically.

```
New CSV in folder
      ↓
pipeline_runner.py detects it (watchdog)
      ↓
genai_pipeline.py runs automatically
      ↓
Report saved + email notification sent
```

Full Zapier setup guide → [`automation/zapier-docs/ZAP_SETUP.md`](automation/zapier-docs/ZAP_SETUP.md)  
Coded Python fallback → [`automation/pipeline_runner.py`](automation/pipeline_runner.py)  
Make (Integromat) blueprint → [`automation/zapier-docs/make_scenario_export.json`](automation/zapier-docs/make_scenario_export.json)

**Live trigger log** (from actual test run):

| triggered_at | file | status | duration |
|---|---|---|---|
| 2026-06-13 06:53:08 | sales_jan_2024.csv | SUCCESS | 0.5s |

---

## Setup

```bash
git clone https://github.com/tanishaa11/genai-reporting-pipeline
cd genai-reporting-pipeline
pip install -r requirements.txt

# Get a free Gemini API key → https://aistudio.google.com/app/apikey
export GEMINI_API_KEY="your_key_here"

python genai_pipeline.py
```

No API key? Run without AI summary:
```bash
python genai_pipeline.py --no-ai
```

---

## Stack

`Python` `Pandas` `Google Gemini API` `Requests` `Watchdog` `Zapier` `Make`

---

**Related project:** [E-Commerce Ops Dashboard](https://github.com/tanishaa11/ecommerce-ops-dashboard) — replaced 3 manual trackers with one SQL pipeline
