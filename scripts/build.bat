@echo off
REM Build script for BFFNT Font Editor v1.2
REM Creates a standalone Windows executable using PyInstaller

echo ========================================
echo  BFFNT Font Editor - Build Script
echo ========================================
echo.

cd /d "%~dp0\.."

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo.
echo Building executable...
echo.

pyinstaller --noconfirm --onefile --windowed ^
    --name "BFFNT_Font_Editor" ^
    --add-data "bffnt_editor\i18n;bffnt_editor\i18n" ^
    --hidden-import "PyQt6.QtCore" ^
    --hidden-import "PyQt6.QtGui" ^
    --hidden-import "PyQt6.QtWidgets" ^
    --hidden-import "PIL" ^
    --hidden-import "numpy" ^
    --hidden-import "bffnt_editor" ^
    --hidden-import "bffnt_editor.core" ^
    --hidden-import "bffnt_editor.texture" ^
    --hidden-import "bffnt_editor.gui" ^
    --hidden-import "bffnt_editor.i18n" ^
    -m bffnt_editor

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
