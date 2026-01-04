@echo off
cd /d "%~dp0"
echo ========================================
echo  BFFNT Font Editor v1.0
echo ========================================
echo.

REM Check if running from source or as installed package
if exist "main.py" (
    REM Running from source - check for venv first
    if exist ".venv\Scripts\python.exe" (
        echo Using virtual environment...
        .venv\Scripts\python.exe -m bffnt_preview.main %*
    ) else if exist "..\venv\Scripts\python.exe" (
        echo Using parent virtual environment...
        ..\venv\Scripts\python.exe -m bffnt_preview.main %*
    ) else (
        echo Using system Python...
        python -m bffnt_preview.main %*
    )
) else (
    echo Error: main.py not found. Run this from the project directory.
    pause
    exit /b 1
)

if errorlevel 1 (
    echo.
    echo ========================================
    echo  Error occurred! Check the output above.
    echo ========================================
    pause
)
echo ========================================
pause
