@echo off
rem Janim's command line on Windows: one ordinary process per call. It runs on
rem the checkout's virtual environment when there is one, otherwise on the py
rem launcher's 3.14 or on python3.14 from the PATH.
setlocal
set "VENV=%~dp0..\.venv\Scripts\python.exe"
if exist "%VENV%" (
    "%VENV%" -m janim.cli %*
    exit /b
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3.14 -m janim.cli %*
    exit /b
)
python3.14 -m janim.cli %*
