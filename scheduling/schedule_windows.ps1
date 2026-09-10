# Windows Task Scheduler Setup for School Email Triage
# Run this script in PowerShell to register a scheduled task that executes every hour.

param (
    [string]$TaskName = "SchoolEmailTriage",
    [int]$IntervalMinutes = 60,
    [switch]$DryRun
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir

Write-Host "Setting up Windows Scheduled Task: '$TaskName'" -ForegroundColor Cyan
Write-Host "Project Directory: $projectDir" -ForegroundColor Gray
Write-Host "Trigger Interval: Every $IntervalMinutes minutes" -ForegroundColor Gray

# Locate uv executable
$uvPath = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uvPath) {
    Write-Error "Could not find 'uv' on PATH. Please ensure uv is installed and in your PATH environment variable."
    exit 1
}

$arguments = "run school-email-triage"
if ($DryRun) {
    $arguments += " --dry-run"
}

# Define the action
$action = New-ScheduledTaskAction -Execute $uvPath -Argument $arguments -WorkingDirectory $projectDir

# Define the trigger: starts now, repeats every $IntervalMinutes minutes indefinitely
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)

# Define task settings
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable

try {
    # Check if task already exists and unregister it first
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Existing task '$TaskName' found. Replacing..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    # Register the new task
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Periodically runs School Email Triage using Gmail and Gemini API."
    Write-Host "Successfully registered Windows Scheduled Task '$TaskName'!" -ForegroundColor Green
    Write-Host "To test run manually: Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Cyan
    Write-Host "To view task: Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Cyan
    Write-Host "To remove: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor DarkGray
} catch {
    Write-Error "Failed to register scheduled task: $_"
    exit 1
}
