@echo off
cd /d "%~dp0\.."
echo ========================================
echo  BFFNT Font Editor v1.0
echo ========================================
echo.

REM Check for venv in various locations
if exist ".venv\Scripts\python.exe" (
    echo Using virtual environment...
    .venv\Scripts\python.exe -m bffnt_editor %*
) else if exist "venv\Scripts\python.exe" (
    echo Using venv...
    venv\Scripts\python.exe -m bffnt_editor %*
) else (
    echo Using system Python...
    python -m bffnt_editor %*
)

if errorlevel 1 (
    echo.
    echo ========================================
    echo  Error occurred! Check the output above.
    echo ========================================
    pause
)
