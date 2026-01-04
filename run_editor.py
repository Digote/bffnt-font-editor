#!/usr/bin/env python
"""
BFFNT Font Editor - Standalone entry point for PyInstaller.
"""
import sys
import os

# Add the package to path if needed
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    app_path = os.path.dirname(sys.executable)
else:
    app_path = os.path.dirname(os.path.abspath(__file__))

# Import and run
from bffnt_editor.gui.main_window import run_app

if __name__ == "__main__":
    file_path = None
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            sys.exit(1)
    
    run_app(file_path)
