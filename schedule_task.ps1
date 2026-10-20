<#
.SYNOPSIS
Registers or updates the Windows Scheduled Task for Bangalore Startup Job Finder.
Configured for daily execution at 08:00 Asia/Kolkata.
#>

param(
    [string]$Time = "08:00",
    [string]$TaskName = "BangaloreStartupJobFinderDaily"
)

$ErrorActionPreference = "Stop"
$WorkingDir = "F:\jobs"
$ScriptPath = Join-Path $WorkingDir "run_daily.bat"

Write-Host "Configuring Windows Scheduled Task: $TaskName" -ForegroundColor Cyan
Write-Host "Target Run Time: $Time (Daily, Asia/Kolkata / IST)" -ForegroundColor Cyan
Write-Host "Action Script: $ScriptPath" -ForegroundColor Cyan

# Check if script exists
if (-not (Test-Path $ScriptPath)) {
    throw "Target execution script not found at $ScriptPath"
}

# 1. Action
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$ScriptPath`"" -WorkingDirectory $WorkingDir

# 2. Daily Trigger at 08:30 AM
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time

# 3. Settings: Run whether network available, retry on failure
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# 4. Principal (Current User)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

# 5. Register Task
try {
    # Unregister if already exists to ensure fresh configuration
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Write-Host "Existing task '$TaskName' found. Replacing with updated configuration..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    $Task = New-ScheduledTask -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal
    Register-ScheduledTask -TaskName $TaskName -InputObject $Task | Out-Null
    Write-Host "SUCCESS: Scheduled task '$TaskName' registered successfully!" -ForegroundColor Green

    # Output task info
    $Registered = Get-ScheduledTask -TaskName $TaskName
    $Info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "`nTask Details:" -ForegroundColor White
    Write-Host "  Name:         $($Registered.TaskName)"
    Write-Host "  State:        $($Registered.State)"
    Write-Host "  Next Run:     $($Info.NextRunTime)"
    Write-Host "  Action:       cmd.exe /c `"$ScriptPath`""
}
catch {
    Write-Error "Failed to register scheduled task: $_"
    exit 1
}
