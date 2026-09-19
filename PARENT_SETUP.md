# Parent Setup Guide: School Email Triage

This step-by-step guide walks you through setting up the School Email Triage tool on your computer.

---

## What This Tool Does

- 📥 **Scans Unread School Emails**: Reads incoming messages from Canvas / Instructure, school district updates, and flyers.
- 🤖 **Classifies by Child**: Uses AI to automatically sort messages to each child based on teacher names, subjects, and grade levels.
- 📅 **Schedules Google Calendar Events**: Adds field trips, conferences, early releases, and assemblies to your calendar with an automatic **24-hour reminder**.
- 📋 **Creates Google Tasks**: Puts homework deadlines and parent action items directly into dedicated Google Tasks lists for each child.
- 🗂️ **Files & Archives**: Applies custom Gmail labels (e.g. `Kids/School - Child 1/10th Grade`) and archives emails out of your main inbox.

---

## Step 1: Install Python & uv

This tool uses [uv](https://docs.astral.sh/uv/), an ultra-fast Python package manager.

### Windows (PowerShell)
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### macOS / Linux (Terminal)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After installation, close and reopen your terminal or PowerShell window.

---

## Step 2: Download the Project

Download the latest release ZIP from the GitHub Releases page and extract it, or clone via git:
```bash
git clone https://github.com/jallers/school-email-triage.git
cd school-email-triage
```

---

## Step 3: Get a Free Google Gemini API Key

1. Visit [Google AI Studio](https://aistudio.google.com/apikey).
2. Sign in with your Google account.
3. Click **Create API Key**.
4. Copy the generated key.

---

## Step 4: Create Google Cloud OAuth Credentials

To allow the tool to securely access your Gmail, Google Calendar, and Google Tasks:

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project dropdown at the top and select **New Project** (name it e.g. `School Triage`).
3. In the search bar at the top, search for and **Enable** these three APIs:
   - **Gmail API**
   - **Google Calendar API**
   - **Google Tasks API**
4. Set up the **OAuth consent screen**:
   - Go to **APIs & Services** > **OAuth consent screen**.
   - User Type: Select **External** and click **Create**.
   - App name: `School Email Triage`.
   - User support email: Select your email.
   - Developer contact email: Enter your email.
   - Click **Save and Continue** through Scopes.
   - On the **Test users** page, click **Add Users** and enter your Google email address.
   - Click **Save and Continue**.
5. Create your OAuth Client ID:
   - Go to **APIs & Services** > **Credentials**.
   - Click **Create Credentials** > **OAuth client ID**.
   - Application type: **Desktop app**.
   - Name: `School Email Triage Client`.
   - Click **Create**.
   - Click **Download JSON** on the confirmation popup.
   - Rename the downloaded file to `credentials.json` and move it into your `school-email-triage` folder.

---

## Step 5: Configure Your `.env` File

Copy the template:
```bash
cp .env.example .env
```
(On Windows PowerShell: `Copy-Item .env.example .env`)

Open `.env` in any text editor:
1. Paste your Gemini key:
   ```ini
   GEMINI_API_KEY=AIzaSy...
   ```
2. Customize your children's details, teachers, and subjects:
   ```ini
   DAUGHTER_NAME=Child 1
   SON_NAME=Child 2
   DAUGHTER_SCHOOL=Lincoln High School
   SON_SCHOOL=Oak Middle School

   DAUGHTER_CURRENT_GRADE=10th Grade
   SON_CURRENT_GRADE=8th Grade

   DAUGHTER_TEACHERS=Smith,Johnson,Davis,Miller
   DAUGHTER_KEYWORDS=Biology, Geometry, World History, English, Spanish

   SON_TEACHERS=Williams,Brown,Jones,Taylor
   SON_KEYWORDS=Physical Science, Algebra, Earth Science, Band, Orchestra
   ```
3. Update the Gmail search query if your school district domain differs:
   ```ini
   SCHOOL_EMAIL_QUERY=from:(*instructure.com OR *schools.org OR *peachjar.com) is:unread
   ```

---

## Step 6: One-Time Google Authorization

Run the one-time authentication command:
```bash
uv run school-email-triage --auth-only
```

- Your default browser will open asking you to sign in to Google.
- If you see a *"Google hasn't verified this app"* screen:
  - Click **Advanced** (in small text at bottom left).
  - Click **Go to School Email Triage (unsafe)**.
- Check the boxes to allow Gmail, Calendar, and Tasks access, then click **Continue**.
- You will see *"The authentication flow has completed. You may close this window."*
- A `token.json` file is now saved locally in your folder.

---

## Step 7: Test with Dry-Run Mode

Before modifying any real emails, run a dry-run preview:
```bash
uv run school-email-triage --dry-run
```
This inspects matching unread emails and displays the AI classification, extracted events, and task items in your terminal without changing anything in your inbox or calendar.

---

## Step 8: Run Live

When ready to triage for real:
```bash
uv run school-email-triage
```
This will:
- Add events to your Google Calendar.
- Create task items in your Google Tasks lists.
- Apply child-specific labels to the emails in Gmail.
- Mark the emails as read and archive them out of your inbox.

---

## Step 9: Automatic Background Scheduling

### Windows (Task Scheduler)
To run automatically every hour in the background (silent headless execution with logs saved to `triage.log`):
```powershell
powershell -ExecutionPolicy Bypass -File .\scheduling\schedule_windows.ps1 -IntervalMinutes 60
```
To view recent background run logs:
```powershell
Get-Content .\triage.log -Tail 20
```

### macOS / Linux (Cron)
```bash
bash scheduling/schedule_cron.sh
```
