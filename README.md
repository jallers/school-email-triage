# School Email Triage Tool

An automated Python CLI tool that triages school emails (from school districts, Canvas/Instructure, flyers, etc.) using the **Gmail API**, **Google Calendar API**, **Google Tasks API**, and **Google GenAI SDK (Gemini 3.5 Flash Lite)** with structured Pydantic schema extraction.

> 💡 **For a complete step-by-step setup walkthrough, check out the [Parent Setup Guide](PARENT_SETUP.md).**

---

## Features

- **OAuth 2.0 Multi-API Scopes**: Single local authorization flow scoped for Gmail (`gmail.modify`), Google Calendar (`calendar.events`), and Google Tasks (`tasks`) with automatic token caching and refresh.
- **Robust MIME Parsing**: Recursively navigates multi-part MIME hierarchies (`multipart/alternative`, `multipart/mixed`, `multipart/related`), decodes base64/quoted-printable payloads, and converts rich HTML newsletters into clean text.
- **Structured LLM Extraction**: Uses Gemini Flash Lite with Pydantic JSON schemas to extract:
  - `target_child`: Categorizes emails by child (e.g., `"daughter"`, `"son"`, or `"general"`).
  - `action_items`: Actionable parent tasks with explicit/implied deadlines.
  - `calendar_events`: Key dates and scheduled events (assemblies, back-to-school nights, conferences) with ISO 8601 timestamps and location/notes.
  - `summary`: High-level summary of the notice.
- **Automated Actions**:
  - Inserts extracted events into your primary Google Calendar with a **24-hour pop-up reminder** (`1440 minutes`).
  - Creates homework and parent action items in child-specific **Google Tasks** lists.
  - Auto-creates and applies matching Gmail labels (e.g. `Kids/School - Child 1/10th Grade`).
  - Marks triaged emails as read and archives them out of your inbox.
- **Safety First**: Includes a `--dry-run` flag to preview all LLM extractions, calendar entries, and label modifications without touching live data.
- **Scheduling**: Includes ready-to-use scheduling scripts for Windows Task Scheduler (`.ps1`), cron (`.sh`), and systemd units (`.service` + `.timer`).

---

## Prerequisites

1. **Python 3.10+** (Tested on Python 3.14)
2. **uv** installed (or standard `pip` / `virtualenv`)
3. **Google Cloud OAuth 2.0 Credentials**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/).
   - Create a project (or select an existing one).
   - Enable **Gmail API**, **Google Calendar API**, and **Google Tasks API**.
   - Configure the OAuth Consent Screen (add your Google account as a test user if in testing status).
   - Under **Credentials**, click **Create Credentials** -> **OAuth client ID** -> select **Desktop app**.
   - Download the JSON file and save it as `credentials.json` in the root of this project.
4. **Gemini API Key**:
   - Obtain a free API key from [Google AI Studio](https://aistudio.google.com/).

---

## Installation & Quick Start

1. **Clone or download the repository**:
   ```bash
   git clone https://github.com/jallers/school-email-triage.git
   cd school-email-triage
   ```

2. **Configure environment**:
   Copy `.env.example` to `.env` and fill in your Gemini API key:
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   ```ini
   GEMINI_API_KEY=AIzaSy...
   GEMINI_MODEL=gemini-3.5-flash-lite
   ```

3. **Install dependencies**:
   ```powershell
   uv sync
   ```

4. **Authenticate Google Account** (first-time only):
   ```powershell
   uv run school-email-triage --auth-only
   ```
   This will open your browser to complete Google OAuth consent and save `token.json` locally for subsequent runs.

---

## Usage

### 1. Offline Mock Simulation (No credentials needed)
Verify the parsing, extraction schemas, and formatting:
```powershell
uv run school-email-triage --mock-test
```

### 2. Dry Run (Preview live emails safely)
Fetches unread emails and runs Gemini extraction without modifying Gmail or Calendar:
```powershell
uv run school-email-triage --dry-run
```

### 3. Live Triage
Processes unread emails, creates calendar events with 24h reminders, applies labels, and marks as read:
```powershell
uv run school-email-triage
```

### 4. Custom Queries & Limits
```powershell
# Custom Gmail search query
uv run school-email-triage --query "from:principal@myschool.org is:unread" --limit 10

# Verbose logging
uv run school-email-triage --dry-run --verbose
```

---

## Automated Scheduling

### Windows Task Scheduler (Recommended on Windows)
Run the included PowerShell script to register an hourly background task:
```powershell
powershell -ExecutionPolicy Bypass -File .\scheduling\schedule_windows.ps1 -IntervalMinutes 60
```
- For dry-run testing via Task Scheduler:
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\scheduling\schedule_windows.ps1 -DryRun
  ```
- To inspect the task: `Get-ScheduledTask -TaskName "SchoolEmailTriage"`
- To manually trigger: `Start-ScheduledTask -TaskName "SchoolEmailTriage"`
- To unregister: `Unregister-ScheduledTask -TaskName "SchoolEmailTriage" -Confirm:$false`

### Linux / macOS (Cron)
```bash
bash scheduling/schedule_cron.sh
```

### Linux (systemd Timer)
```bash
cp scheduling/school-triage.service ~/.config/systemd/user/
cp scheduling/school-triage.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now school-triage.timer
```

---

## Running Tests

Run the full automated test suite:
```powershell
uv run pytest -v
```
Tests cover:
- Multi-part MIME decoding, nested boundaries, character sets, and HTML text stripping.
- Pydantic schema validation for events, action items, and child attribution.
- Gemini API client integration and prompt anchoring.
- Google Calendar event payload structure (start/end format, 24-hour reminder override).
- Gmail label cache, creation, and batch modification.
- End-to-end dry-run and live pipeline orchestration.
