# Automation: Google Drive → GenAI Pipeline

This folder documents and implements the trigger automation for the GenAI Reporting Pipeline.

Two equivalent approaches are provided — a **Zapier Zap** (no-code) and a **Python watcher** (coded fallback). Both do exactly the same thing.

---

## What gets automated

```
New CSV uploaded to Google Drive folder
              ↓
     Trigger fires automatically
              ↓
   genai_pipeline.py runs on the file
              ↓
  Report saved + team email notification sent
              ↓
     Event logged to trigger_log.csv
```

**Before:** Team member downloads CSV → opens terminal → runs script → copies report → emails team. ~25 minutes, done manually per cycle.  
**After:** Drop CSV in folder. Everything else happens automatically.

---

## Option A — Zapier (no-code)

**Best for:** Teams without a server or technical setup.  
**Requires:** Zapier Starter plan ($19.99/mo) for 3+ step Zaps.  
**Free alternative:** Use Make (Integromat) with the included scenario blueprint.

Full step-by-step setup guide → [`zapier-docs/ZAP_SETUP.md`](zapier-docs/ZAP_SETUP.md)  
Make scenario blueprint (importable) → [`zapier-docs/make_scenario_export.json`](zapier-docs/make_scenario_export.json)

---

## Option B — Python Watcher (coded fallback)

**Best for:** Local use, Google Drive desktop sync, or server deployment.  
**Requires:** Python 3.9+, `watchdog` library. No paid accounts needed.

### Setup

```bash
# Install dependency
pip install -r automation/requirements.txt

# Create the watch folder
mkdir -p data/incoming

# Run the watcher
python automation/pipeline_runner.py
```

### Usage

```bash
# Watch default folder (data/incoming/)
python automation/pipeline_runner.py

# Watch your Google Drive sync folder
python automation/pipeline_runner.py --watch ~/Google\ Drive/Sales\ Reports/Incoming

# Disable email notifications
python automation/pipeline_runner.py --no-email

# Run in background (Linux/Mac)
nohup python automation/pipeline_runner.py > automation/runner.log 2>&1 &
```

### Email notifications (optional)

Set these environment variables to enable email alerts when a report is generated:

```bash
export NOTIFY_EMAIL="ops-team@yourcompany.com"
export SMTP_USER="your-gmail@gmail.com"
export SMTP_PASSWORD="your-app-password"   # Not your main password
                                            # Get one at: myaccount.google.com/apppasswords
```

Or create a `.env` file (already in `.gitignore`):
```
GEMINI_API_KEY=your_gemini_key
NOTIFY_EMAIL=ops-team@yourcompany.com
SMTP_USER=your-gmail@gmail.com
SMTP_PASSWORD=your-app-password
```

---

## Trigger log

Every pipeline run is logged automatically to `automation/trigger_log.csv`:

| triggered_at | file_name | status | report_path | duration_sec |
|---|---|---|---|---|
| 2026-06-13 06:53:08 | sales_jan_2024.csv | SUCCESS | outputs/report_20260613_0653.md | 0.5 |

Status values: `SUCCESS`, `FAILED`, `TIMEOUT`, `ERROR`

---

## Folder structure

```
automation/
├── pipeline_runner.py          # Python watcher (Option B)
├── requirements.txt            # watchdog dependency
├── trigger_log.csv             # Auto-generated run log
└── zapier-docs/
    ├── ZAP_SETUP.md            # Step-by-step Zapier setup (Option A)
    └── make_scenario_export.json  # Importable Make blueprint
```

---

## How this maps to the Zapier Zap

| Zapier step | Python equivalent |
|-------------|------------------|
| Trigger: New File in Folder | `watchdog` FileSystemEventHandler |
| Filter: .csv only | `if path.suffix.lower() != ".csv": return` |
| Action: POST to webhook | `subprocess.run(["python", "genai_pipeline.py"])` |
| Action: Send Email | `smtplib` + Gmail SMTP |
| Zap history log | `automation/trigger_log.csv` |
