@echo off
rem Create the checkout's virtual environment with Janim's pinned dependencies
rem and make the checkout importable from it. PYTHON selects the interpreter;
rem otherwise the py launcher's 3.14, else uv (it fetches 3.14 and seeds pip:
rem its python3.14.exe is a launcher that venv cannot copy), else python3.14
rem on the PATH.
setlocal
for %%I in ("%~dp0..") do set "JANIM_ROOT=%%~fI"
set "VENV=%JANIM_ROOT%\.venv"
if defined PYTHON goto given
where py >nul 2>nul && goto py
where uv >nul 2>nul && goto uv
set "PYTHON=python3.14"
:given
%PYTHON% -m venv "%VENV%" || exit /b 1
goto install
:py
py -3.14 -m venv "%VENV%" || exit /b 1
goto install
:uv
uv venv --seed --python 3.14 "%VENV%" || exit /b 1
:install
"%VENV%\Scripts\python.exe" "%JANIM_ROOT%\scripts\bootstrap.py" "%JANIM_ROOT%" || exit /b 1
