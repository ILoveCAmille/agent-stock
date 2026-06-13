@echo off
:: AI Stock Alert System - Install All Tasks
:: Right-click -> Run as Administrator
setlocal

set "SD=%~dp0"
set "PP=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"

if not exist "%PP%" (
    echo [ERROR] Python not found at: %PP%
    echo Run "where python" to find your path, then edit this script.
    pause
    exit /b 1
)

echo ============================================
echo   AI Stock Alert System - Installer
echo ============================================
echo.
echo Python : %PP%
echo.

:: ---- Task 1: DTCB Position Monitor ----
echo [1/3] Installing DTCB Position Monitor...
set "SP1=%SD%stock_alert_601991.py"
schtasks /Delete /TN "DTCB_StockAlert" /F 2>nul
schtasks /Create /TN "DTCB_StockAlert" /TR "\"%PP%\" \"%SP1%\"" /SC ONLOGON /DELAY 0000:30 /RL HIGHEST /F
if %ERRORLEVEL% EQU 0 (
    echo   [OK] DTCB_StockAlert installed
    schtasks /Run /TN "DTCB_StockAlert"
    echo   [OK] Started
) else (
    echo   [FAIL] DTCB_StockAlert
)

:: ---- Task 2: Market TOP10 Scanner ----
echo.
echo [2/3] Installing Market TOP10 Scanner...
set "SP2=%SD%market_top10_alert.py"
schtasks /Delete /TN "AI_Top10_Scan" /F 2>nul
schtasks /Create /TN "AI_Top10_Scan" /TR "\"%PP%\" \"%SP2%\"" /SC ONLOGON /DELAY 0000:35 /RL HIGHEST /F
if %ERRORLEVEL% EQU 0 (
    echo   [OK] AI_Top10_Scan installed
    schtasks /Run /TN "AI_Top10_Scan"
    echo   [OK] Started
) else (
    echo   [FAIL] AI_Top10_Scan
)

:: ---- Task 3: Weekly Market Report ----
echo.
echo [3/3] Installing Weekly Market Report...
set "SP3=%SD%weekly_market_report.py"
schtasks /Delete /TN "AI_WeeklyReport" /F 2>nul
schtasks /Create /TN "AI_WeeklyReport" /TR "\"%PP%\" \"%SP3%\"" /SC WEEKLY /D SAT /ST 10:00 /RL HIGHEST /F
if %ERRORLEVEL% EQU 0 (
    echo   [OK] AI_WeeklyReport installed (runs Saturday 10:00 AM)
) else (
    echo   [FAIL] AI_WeeklyReport
)

echo.
echo ============================================
echo   INSTALL COMPLETE - 3 tasks installed
echo ============================================
echo.
echo   1. DTCB_StockAlert  - Position monitor (every 5min, trading hrs)
echo      Log: stock_alert_601991.log
echo   2. AI_Top10_Scan    - Daily TOP10 picks (09:35 & 14:30)
echo      Log: market_top10_alert.log
echo   3. AI_WeeklyReport  - Weekly summary + outlook (Sat 10:00)
echo      Log: weekly_market_report.log
echo.
echo All tasks auto-run. No manual action needed.
echo.
echo --- Uninstall all ---
echo   schtasks /Delete /TN DTCB_StockAlert /F
echo   schtasks /Delete /TN AI_Top10_Scan /F
echo   schtasks /Delete /TN AI_WeeklyReport /F

pause
