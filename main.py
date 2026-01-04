"""
BFFNT Font Editor v1.0 - Main entry point.

A modern Python tool to view and edit Nintendo Switch .bffnt font files.

Usage:
    python -m bffnt_preview.main [font_file.bffnt]
"""

import sys
import os


def main():
    """Main entry point."""
    # Get file path from command line if provided
    file_path = None
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            sys.exit(1)
    
    # Import and run GUI
    from .gui.main_window import run_app
    run_app(file_path)


if __name__ == "__main__":
    main()
