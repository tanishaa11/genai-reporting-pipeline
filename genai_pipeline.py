"""
genai_pipeline.py
─────────────────
Replaces a 5-stage manual reporting process with a single pipeline run.

Stages automated:
  1. Data ingestion & validation
  2. Metric computation (revenue, returns, growth, top performers)
  3. Anomaly detection
  4. Executive summary generation via Gemini API (free tier)
  5. Report export to Markdown + plain text

Usage:
  python genai_pipeline.py                         # uses data/sales_data.csv
  python genai_pipeline.py --input path/to/data.csv
  python genai_pipeline.py --no-ai                 # skip Gemini, output stats only
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests


# ── Config ────────────────────────────────────────────────────────────────────

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


# ── 1. Data Ingestion & Validation ────────────────────────────────────────────

def load_and_validate(path: str) -> pd.DataFrame:
    """Load CSV and enforce expected schema."""
    required = {"date", "product", "category", "region",
                "units_sold", "revenue", "returns", "sales_rep"}

    df = pd.read_csv(path, parse_dates=["date"])

    missing = required - set(df.columns)
    if missing:
        sys.exit(f"[ERROR] Missing columns: {missing}")

    df = df.dropna(subset=["revenue", "units_sold"])
    df["net_revenue"] = df["revenue"] - (df["returns"] * (df["revenue"] / df["units_sold"]))
    df["return_rate"] = (df["returns"] / df["units_sold"]).round(4)
    df["month"] = df["date"].dt.to_period("M").astype(str)

    print(f"[✓] Loaded {len(df)} records from {path}")
    return df


# ── 2. Metric Computation ──────────────────────────────────────────────────────

def compute_metrics(df: pd.DataFrame) -> dict:
    """Derive all KPIs needed for the executive summary."""

    total_revenue   = df["revenue"].sum()
    total_net_rev   = df["net_revenue"].sum()
    total_units     = df["units_sold"].sum()
    avg_return_rate = df["return_rate"].mean()

    # Month-over-month revenue
    monthly = df.groupby("month")["revenue"].sum().sort_index()
    mom_growth = monthly.pct_change().dropna()
    best_month  = monthly.idxmax()
    worst_month = monthly.idxmin()
    last_growth = mom_growth.iloc[-1] if len(mom_growth) else 0

    # Product breakdown
    by_product = (
        df.groupby("product")
          .agg(revenue=("revenue","sum"), units=("units_sold","sum"), returns=("returns","sum"))
          .sort_values("revenue", ascending=False)
    )
    top_product = by_product.index[0]

    # Regional breakdown
    by_region = df.groupby("region")["revenue"].sum().sort_values(ascending=False)
    top_region = by_region.index[0]

    # Category breakdown
    by_category = df.groupby("category")["revenue"].sum().sort_values(ascending=False)

    # Sales rep leaderboard
    by_rep = df.groupby("sales_rep")["revenue"].sum().sort_values(ascending=False)
    top_rep = by_rep.index[0]

    # Anomalies — months with return rate > 2 SD above mean
    rep_by_month = df.groupby("month")["return_rate"].mean()
    z = (rep_by_month - rep_by_month.mean()) / (rep_by_month.std() + 1e-9)
    anomalous_months = z[z > 2].index.tolist()

    return {
        "period":          f"{df['date'].min().date()} to {df['date'].max().date()}",
        "total_records":   len(df),
        "total_revenue":   round(total_revenue, 2),
        "total_net_rev":   round(total_net_rev, 2),
        "total_units":     int(total_units),
        "avg_return_rate": round(avg_return_rate * 100, 2),
        "best_month":      best_month,
        "worst_month":     worst_month,
        "mom_growth_pct":  round(last_growth * 100, 2),
        "top_product":     top_product,
        "top_region":      top_region,
        "top_rep":         top_rep,
        "anomalous_months":anomalous_months,
        "by_product":      by_product.to_dict(),
        "by_region":       by_region.to_dict(),
        "by_category":     by_category.to_dict(),
        "monthly_revenue": monthly.to_dict(),
    }


# ── 3. Anomaly Detection (rule-based, no ML needed) ───────────────────────────

def flag_anomalies(metrics: dict) -> list[str]:
    flags = []
    if metrics["avg_return_rate"] > 8:
        flags.append(f"High avg return rate: {metrics['avg_return_rate']}% — investigate fulfilment quality.")
    if metrics["mom_growth_pct"] < -10:
        flags.append(f"Revenue fell {abs(metrics['mom_growth_pct'])}% month-on-month — requires review.")
    if metrics["anomalous_months"]:
        flags.append(f"Elevated return rates detected in: {', '.join(metrics['anomalous_months'])}.")
    return flags or ["No anomalies detected this period."]


# ── 4. Gemini Executive Summary Generation ────────────────────────────────────

PROMPT_TEMPLATE = """
You are a senior business analyst writing a concise executive summary for a leadership team.
Use only the data provided. Be direct. No filler phrases. No markdown headers.
Write 4 short paragraphs:
  1. Overall performance snapshot (revenue, units, return rate)
  2. Standout trends (best/worst month, MoM growth, top product and region)
  3. Risks and anomalies requiring attention
  4. One concrete operational recommendation

DATA:
{metrics_json}

ANOMALIES FLAGGED:
{anomalies}
"""

def generate_summary(metrics: dict, anomalies: list[str], api_key: str) -> str:
    prompt = PROMPT_TEMPLATE.format(
        metrics_json=json.dumps(
            {k: v for k, v in metrics.items() if k not in ("by_product", "by_region", "by_category", "monthly_revenue")},
            indent=2
        ),
        anomalies="\n".join(f"- {a}" for a in anomalies),
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 512},
    }

    resp = requests.post(
        f"{GEMINI_API_URL}?key={api_key}",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"[WARN] Gemini API error {resp.status_code}: {resp.text[:200]}")
        return "[AI summary unavailable — see metrics below]"

    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ── 5. Report Export ───────────────────────────────────────────────────────────

REPORT_TEMPLATE = """# Sales Executive Summary
**Generated:** {timestamp}
**Data period:** {period}  |  **Records processed:** {total_records}

---

## AI-Generated Executive Summary

{summary}

---

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Revenue | ₹{total_revenue:,.0f} |
| Net Revenue (post-returns) | ₹{total_net_rev:,.0f} |
| Total Units Sold | {total_units:,} |
| Avg Return Rate | {avg_return_rate}% |
| Best Month | {best_month} |
| MoM Growth (last period) | {mom_growth_pct}% |
| Top Product | {top_product} |
| Top Region | {top_region} |
| Top Sales Rep | {top_rep} |

---

## Anomalies Flagged

{anomaly_list}

---

## Monthly Revenue Trend

{monthly_table}

---

## Product Breakdown

{product_table}

---

*Pipeline: genai-reporting-pipeline · Model: Gemini 1.5 Flash*
"""

def build_report(metrics: dict, anomalies: list[str], summary: str) -> str:
    monthly_rows = "\n".join(
        f"| {m} | ₹{v:,.0f} |"
        for m, v in metrics["monthly_revenue"].items()
    )
    monthly_table = "| Month | Revenue |\n|-------|---------|\n" + monthly_rows

    prod_rows = "\n".join(
        f"| {p} | ₹{metrics['by_product']['revenue'][p]:,.0f} | {int(metrics['by_product']['units'][p]):,} |"
        for p in metrics["by_product"]["revenue"]
    )
    product_table = "| Product | Revenue | Units |\n|---------|---------|-------|\n" + prod_rows

    return REPORT_TEMPLATE.format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        summary=summary,
        anomaly_list="\n".join(f"- {a}" for a in anomalies),
        monthly_table=monthly_table,
        product_table=product_table,
        **{k: v for k, v in metrics.items() if k not in ("by_product","by_region","by_category","monthly_revenue")},
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GenAI Sales Reporting Pipeline")
    parser.add_argument("--input",  default="data/sales_data.csv", help="Path to sales CSV")
    parser.add_argument("--no-ai",  action="store_true",           help="Skip Gemini, output stats only")
    parser.add_argument("--api-key",default=None,                  help="Gemini API key (or set GEMINI_API_KEY env var)")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("GEMINI_API_KEY", "")

    print("\n── GenAI Reporting Pipeline ─────────────────────")
    print("Stage 1/5  Ingestion & validation...")
    df = load_and_validate(args.input)

    print("Stage 2/5  Computing metrics...")
    metrics = compute_metrics(df)

    print("Stage 3/5  Anomaly detection...")
    anomalies = flag_anomalies(metrics)
    for a in anomalies:
        print(f"           ⚠  {a}")

    if args.no_ai or not api_key:
        if not args.no_ai:
            print("Stage 4/5  [SKIP] No GEMINI_API_KEY set — run with --api-key or set env var.")
        summary = "[Set GEMINI_API_KEY environment variable to enable AI summaries]\n\n" \
                  "To get a free key: https://aistudio.google.com/app/apikey"
    else:
        print("Stage 4/5  Generating AI executive summary via Gemini...")
        summary = generate_summary(metrics, anomalies, api_key)

    print("Stage 5/5  Writing report...")
    report = build_report(metrics, anomalies, summary)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    md_path  = OUTPUT_DIR / f"report_{timestamp}.md"
    txt_path = OUTPUT_DIR / f"report_{timestamp}.txt"

    md_path.write_text(report, encoding="utf-8")
    txt_path.write_text(report, encoding="utf-8")

    print(f"\n[✓] Report saved → {md_path}")
    print("─────────────────────────────────────────────────\n")
    print(report[:800] + "\n...[truncated — open the file for full report]")


if __name__ == "__main__":
    main()
