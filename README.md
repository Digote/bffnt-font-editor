# BFFNT Font Editor v1.0

A modern Python tool for viewing and editing Nintendo Switch `.bffnt` font files.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

## ✨ Features

### 📂 Open & Save
- Open `.bffnt` font files (Nintendo Switch)
- Save modifications back to BFFNT format

### 📄 Texture Sheet Viewer
- View all texture sheets with zoom controls (25%-400%)
- Optional grid overlay to see cell boundaries
- Navigate between multiple sheets

### 📤 Export
- Export current sheet as PNG
- Export all sheets at once
- Export with metadata JSON (for re-importing)

### 📥 Import
- Import modified texture sheets (PNG)
- Supports BC4 texture compression

### 🔤 Character Grid
- View all glyphs in organized grid
- Click to select and inspect details

### ✏️ Mapping Editor
- Edit which Unicode character uses which glyph
- Add new character mappings
- Remap existing characters

### 📐 Glyph Metrics Editor
- **Left**: Horizontal offset from cell border
- **Width**: Actual glyph width in pixels
- **Advance**: Cursor advance after drawing

### 📝 Text Preview
- Type text and see how it renders with the font
- Adjustable scale

### 🌐 Multi-language
- English
- Português (Brasil)
- Easy to add new languages

## 📋 Requirements

- Python 3.10+
- PyQt6
- Pillow
- ReverseBox (for Switch texture deswizzling)

## 🔧 Installation

```bash
pip install -r requirements.txt
```

## 🚀 Usage

### Run the GUI

```bash
# Run without file (use File > Open)
python -m bffnt_preview.main

# Open a specific file
python -m bffnt_preview.main "path/to/font.bffnt"
```

### ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open BFFNT file |
| `Ctrl+S` | Export current sheet |
| `Ctrl+Shift+S` | Save BFFNT file |
| `Ctrl++` | Zoom In |
| `Ctrl+-` | Zoom Out |
| `Ctrl+0` | Reset Zoom |
| `Ctrl+Q` | Exit |

### 🔄 Typical Workflow

1. **Open** a BFFNT file (📂 Open)
2. **Export** with metadata (📦 Export All)
3. **Edit** the PNG files in your image editor
4. **Import** the modified sheets (📥 Import)
5. **Save** as new BFFNT file (💾 Save)

## 📦 Project Structure

```
bffnt_preview/
├── main.py              # Entry point
├── bffnt_parser.py      # BFFNT file parser
├── bffnt_writer.py      # BFFNT file writer
├── texture_decoder.py   # Texture decoding
├── texture_encoder.py   # Texture encoding
├── export_import.py     # Export/Import with metadata
├── i18n/                # Internationalization
│   ├── __init__.py      # Translation API
│   └── translations.py  # Language strings
└── gui/
    ├── main_window.py   # Main application window
    ├── font_viewer.py   # Sheet/Grid/Text viewers
    └── mapping_editor.py # Character mapping editor
```

## 🎮 Supported Formats

| Texture Format | Support |
|----------------|---------|
| RGBA8888 | ✅ Full |
| BC4 (DXT5A) | ✅ Full |
| A8 (Alpha) | ✅ Full |
| LA8 | ✅ Full |
| BC1/DXT1 | 🔄 Via ReverseBox |
| BC3/DXT5 | 🔄 Via ReverseBox |

## 📄 License

MIT License - See [LICENSE](LICENSE) file.

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests
- Add new language translations

## 🔗 Links

- [GitHub Repository](https://github.com/Digote/bffnt-font-editor)
- [Report Issues](https://github.com/Digote/bffnt-font-editor/issues)
