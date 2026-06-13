"""
pipeline_runner.py
──────────────────
Coded fallback for the Zapier automation.
Implements the same trigger logic locally — no Zapier account needed.

What it does:
  1. Watches a local folder (or synced Google Drive folder) for new .csv files
  2. Automatically runs genai_pipeline.py when a new file is detected
  3. Sends an email notification with the report path when complete
  4. Logs every trigger event to automation/trigger_log.csv

This is the equivalent of the Zapier Zap documented in:
  automation/zapier-docs/ZAP_SETUP.md

Usage:
  # Watch default folder (data/incoming/)
  python automation/pipeline_runner.py

  # Watch a custom folder (e.g. Google Drive sync path)
  python automation/pipeline_runner.py --watch ~/Google Drive/Sales\ Reports/Incoming

  # Watch without email notifications
  python automation/pipeline_runner.py --no-email

  # Run as a background service (Linux/Mac)
  nohup python automation/pipeline_runner.py &

Environment variables (set in .env or export):
  GEMINI_API_KEY     — Gemini API key for AI summaries
  NOTIFY_EMAIL       — recipient email for report notifications
  SMTP_HOST          — SMTP server (default: smtp.gmail.com)
  SMTP_PORT          — SMTP port (default: 587)
  SMTP_USER          — sender Gmail address
  SMTP_PASSWORD      — Gmail App Password (not your main password)
                       Get one at: myaccount.google.com/apppasswords
"""

import argparse
import csv
import logging
import os
import smtplib
import subprocess
import sys
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    sys.exit(
        "[ERROR] watchdog not installed.\n"
        "Run: pip install watchdog\n"
        "Or:  pip install -r automation/requirements.txt"
    )

# ── Config ─────────────────────────────────────────────────────────────────────

WATCH_DIR    = Path("data/incoming")
LOG_PATH     = Path("automation/trigger_log.csv")
PIPELINE     = Path("genai_pipeline.py")
OUTPUT_DIR   = Path("outputs")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("pipeline_runner")


# ── Trigger Log ────────────────────────────────────────────────────────────────

def init_log():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        with open(LOG_PATH, "w", newline="") as f:
            csv.writer(f).writerow(
                ["triggered_at", "file_name", "status", "report_path", "duration_sec"]
            )

def write_log(file_name, status, report_path="", duration=0):
    with open(LOG_PATH, "a", newline="") as f:
        csv.writer(f).writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            file_name, status, report_path, round(duration, 1)
        ])


# ── Email Notification ─────────────────────────────────────────────────────────

def send_notification(file_name: str, report_path: str, duration: float):
    notify_email = os.getenv("NOTIFY_EMAIL")
    smtp_user    = os.getenv("SMTP_USER")
    smtp_pass    = os.getenv("SMTP_PASSWORD")

    if not all([notify_email, smtp_user, smtp_pass]):
        log.warning("Email skipped — set NOTIFY_EMAIL, SMTP_USER, SMTP_PASSWORD to enable.")
        return

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    subject = f"Sales Report Ready — {file_name}"
    body = f"""A new sales CSV was detected and processed automatically.

File detected : {file_name}
Triggered at  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Pipeline ran  : {duration:.1f} seconds
Report saved  : {report_path}

This notification was sent automatically by pipeline_runner.py.
Equivalent Zapier Zap: automation/zapier-docs/ZAP_SETUP.md
"""

    msg = MIMEMultipart()
    msg["From"]    = smtp_user
    msg["To"]      = notify_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        log.info(f"Notification sent → {notify_email}")
    except Exception as e:
        log.warning(f"Email failed: {e}")


# ── Pipeline Trigger ────────────────────────────────────────────────────────────

def run_pipeline(csv_path: Path, send_email: bool):
    log.info(f"── New file detected: {csv_path.name} ──────────────────")
    start = time.time()

    api_key = os.getenv("GEMINI_API_KEY", "")
    cmd = [
        sys.executable, str(PIPELINE),
        "--input", str(csv_path),
    ]
    if not api_key:
        cmd.append("--no-ai")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        duration = time.time() - start

        if result.returncode == 0:
            # Find the most recently created report
            reports = sorted(OUTPUT_DIR.glob("report_*.md"), key=lambda p: p.stat().st_mtime)
            report_path = str(reports[-1]) if reports else "unknown"

            log.info(f"Pipeline complete in {duration:.1f}s → {report_path}")
            write_log(csv_path.name, "SUCCESS", report_path, duration)

            if send_email:
                send_notification(csv_path.name, report_path, duration)
        else:
            log.error(f"Pipeline failed:\n{result.stderr}")
            write_log(csv_path.name, "FAILED", "", duration)

    except subprocess.TimeoutExpired:
        log.error("Pipeline timed out after 120 seconds")
        write_log(csv_path.name, "TIMEOUT")
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        write_log(csv_path.name, "ERROR")


# ── File System Watcher ────────────────────────────────────────────────────────

class CSVHandler(FileSystemEventHandler):
    def __init__(self, send_email: bool):
        self.send_email  = send_email
        self._processing = set()   # debounce — avoid double triggers

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() != ".csv":
            return
        if path in self._processing:
            return

        self._processing.add(path)
        # Small delay — ensure file is fully written before reading
        time.sleep(1.5)
        run_pipeline(path, self.send_email)
        self._processing.discard(path)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GenAI Pipeline — Folder Watcher")
    parser.add_argument("--watch",    default=str(WATCH_DIR), help="Folder to watch")
    parser.add_argument("--no-email", action="store_true",    help="Disable email notifications")
    args = parser.parse_args()

    watch_path = Path(args.watch)
    watch_path.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    init_log()

    log.info("── GenAI Pipeline Runner ─────────────────────────")
    log.info(f"Watching : {watch_path.resolve()}")
    log.info(f"Trigger  : New .csv file in folder")
    log.info(f"Action   : Run genai_pipeline.py automatically")
    log.info(f"Email    : {'disabled' if args.no_email else 'enabled (set NOTIFY_EMAIL)'}")
    log.info(f"Log      : {LOG_PATH}")
    log.info("Equivalent Zapier Zap → automation/zapier-docs/ZAP_SETUP.md")
    log.info("──────────────────────────────────────────────────")
    log.info("Waiting for new CSV files... (Ctrl+C to stop)\n")

    handler  = CSVHandler(send_email=not args.no_email)
    observer = Observer()
    observer.schedule(handler, str(watch_path), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping watcher...")
        observer.stop()

    observer.join()
    log.info("Pipeline runner stopped.")


if __name__ == "__main__":
    main()
