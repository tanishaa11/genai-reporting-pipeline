# Zapier Automation: Google Drive → GenAI Pipeline

## What this Zap does

Watches a Google Drive folder for new CSV uploads.  
The moment a file lands, it triggers the GenAI reporting pipeline automatically —  
no manual download, no manual run, no manual report distribution.

```
New CSV in Google Drive
        ↓
  Zapier detects file
        ↓
  Webhook fires to pipeline runner
        ↓
  genai_pipeline.py executes
        ↓
  Report saved to Drive + emailed to team
```

**Time saved per report cycle:** ~25 minutes of manual work eliminated.

---

## Zap configuration (step by step)

### Step 1 — Trigger: Google Drive › New File in Folder

| Field | Value |
|-------|-------|
| App | Google Drive |
| Event | New File in Folder |
| Drive | My Drive |
| Folder | `/Sales Reports/Incoming` |
| File types to watch | `.csv` only |

> **Screenshot:** `screenshots/01_trigger_google_drive.png`

---

### Step 2 — Filter: Only CSV files

Add a **Filter by Zapier** step before the action to prevent non-CSV uploads from triggering the pipeline.

| Field | Value |
|-------|-------|
| Field | File Name |
| Condition | Contains |
| Value | `.csv` |

> **Screenshot:** `screenshots/02_filter_csv_only.png`

---

### Step 3 — Action: Webhooks by Zapier › POST

This fires a POST request to the pipeline runner (see `automation/pipeline_runner.py`).

| Field | Value |
|-------|-------|
| App | Webhooks by Zapier |
| Event | POST |
| URL | `http://your-server-ip:8080/run` |
| Payload Type | JSON |
| Data — `file_name` | `{{File Name}}` (from Step 1) |
| Data — `file_url` | `{{File URL}}` (from Step 1) |
| Data — `triggered_at` | `{{zap_meta_humanize_timestamp}}` |

> **Screenshot:** `screenshots/03_action_webhook_post.png`

---

### Step 4 — Action: Gmail › Send Email

After the pipeline runs and saves the report, a second action emails it to the team.

| Field | Value |
|-------|-------|
| App | Gmail |
| Event | Send Email |
| To | `ops-team@yourcompany.com` |
| Subject | `Sales Report Ready — {{File Name}} — {{zap_meta_humanize_timestamp}}` |
| Body | `New sales report generated from {{File Name}}. Report saved to Google Drive: /Sales Reports/Outputs/` |

> **Screenshot:** `screenshots/04_action_send_email.png`

---

### Step 5 — Action: Google Drive › Upload File (optional)

Saves the generated Markdown report back to a Drive output folder.

| Field | Value |
|-------|-------|
| App | Google Drive |
| Event | Upload File |
| Drive | My Drive |
| Folder | `/Sales Reports/Outputs` |
| File | Output from pipeline runner |

> **Screenshot:** `screenshots/05_action_upload_report.png`

---

## Zap summary

```
Trigger:   Google Drive — New File in Folder (/Sales Reports/Incoming)
Filter:    File Name contains .csv
Action 1:  Webhooks — POST → pipeline_runner.py
Action 2:  Gmail — Send report notification to team
Action 3:  Google Drive — Upload generated report to /Outputs
```

**Plan required:** Zapier Free (2-step) covers Trigger + 1 Action.  
Full 3-action flow requires Zapier Starter ($19.99/month) or use the Python fallback below.

---

## Free alternative: Make (formerly Integromat)

Make offers the same workflow with a more generous free tier (1,000 operations/month).

Equivalent Make scenario:
```
Watch Files (Google Drive) → HTTP POST → Send Email (Gmail)
```

See `automation/make_scenario_export.json` for an importable Make scenario blueprint.

---

## Notes for recruiters / reviewers

This Zap was designed and documented as part of an AI operations portfolio project.  
The coded fallback (`automation/pipeline_runner.py`) implements the same trigger logic  
locally using Python's `watchdog` library — fully runnable without a Zapier account.
