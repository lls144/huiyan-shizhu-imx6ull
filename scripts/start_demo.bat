@echo off
setlocal

rem Resolve the repository from this script location; do not depend on the
rem caller's current directory or on a globally installed Python.
for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
set "PYTHON_EXE=%REPO_ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Demo launcher could not find .venv\Scripts\python.exe
    echo Expected repository root: %REPO_ROOT%
    pause
    exit /b 1
)

pushd "%REPO_ROOT%"
"%PYTHON_EXE%" -m pc.gui --source camera --roi-mode fixed_normalized
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
