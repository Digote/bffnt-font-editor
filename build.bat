@echo off
REM Build script for BFFNT Font Editor v1.0
REM Creates a standalone Windows executable using PyInstaller

echo ========================================
echo  BFFNT Font Editor - Build Script
echo ========================================
echo.

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo.
echo Building executable...
echo.

cd /d "%~dp0"

pyinstaller --noconfirm --onefile --windowed ^
    --name "BFFNT_Font_Editor" ^
    --icon "icon.ico" ^
    --add-data "i18n;i18n" ^
    --hidden-import "PyQt6.QtCore" ^
    --hidden-import "PyQt6.QtGui" ^
    --hidden-import "PyQt6.QtWidgets" ^
    --hidden-import "PIL" ^
    --hidden-import "reversebox" ^
    main.py

echo.
echo ========================================
if exist "dist\BFFNT_Font_Editor.exe" (
    echo  Build successful!
    echo  Executable: dist\BFFNT_Font_Editor.exe
) else (
    echo  Build failed! Check the errors above.
)
echo ========================================
pause
