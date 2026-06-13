@echo off
setlocal
set "SD=%~dp0"

schtasks /Query /TN "DTCB_StockAlert" /FO LIST /V 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Task NOT installed. Run install_alert_service.bat as Admin first.
    pause
    exit /b 0
)

echo.
echo Actions: [S]tart  s[T]op  [L]og  [Q]uit
choice /c STLQ /n /m "Choose: "

if errorlevel 4 goto :eof
if errorlevel 3 (
    if exist "%SD%stock_alert_601991.log" (
        type "%SD%stock_alert_601991.log"
    ) else (
        echo No log file yet.
    )
    pause
    goto :eof
)
if errorlevel 2 (
    schtasks /End /TN "DTCB_StockAlert"
    echo Stopped.
    pause
    goto :eof
)
if errorlevel 1 (
    schtasks /Run /TN "DTCB_StockAlert"
    echo Started.
    pause
)
