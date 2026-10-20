@echo off
REM ==============================================================================
REM Bangalore Startup Job Finder - Daily Execution Wrapper
REM Target Schedule: Daily at 08:00 Asia/Kolkata
REM ==============================================================================

cd /d "F:\jobs"
echo [%date% %time%] Starting daily job discovery pipeline... >> logs\scheduler.log

"C:\Users\Chethan_Gowda\AppData\Local\Programs\Python\Python312\python.exe" main.py >> logs\scheduler.log 2>&1

set EXIT_CODE=%ERRORLEVEL%
if %EXIT_CODE% EQU 0 (
    echo [%date% %time%] Daily job discovery completed successfully. >> logs\scheduler.log
) else (
    echo [%date% %time%] ERROR: Daily job discovery exited with code %EXIT_CODE%. >> logs\scheduler.log
)

exit /b %EXIT_CODE%
