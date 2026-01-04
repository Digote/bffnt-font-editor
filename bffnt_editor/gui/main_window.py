"""
Main Window - Primary application window for BFFNT Font Preview Tool.
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

# ============================================================
# LOGGING SETUP - Very detailed logging to file and console
# ============================================================
LOG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(LOG_DIR, 'bffnt_debug.log')

# Create logger
logger = logging.getLogger('BFFNT')
logger.setLevel(logging.DEBUG)

# Clear existing handlers
logger.handlers.clear()

# File handler - detailed log
file_handler = logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(funcName)s: %(message)s'))

# Console handler - also detailed
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))

logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("=" * 60)
logger.info("BFFNT Font Preview Tool - Starting")
logger.info(f"Log file: {LOG_FILE}")
logger.info(f"Python: {sys.executable}")
logger.info(f"Working dir: {os.getcwd()}")
logger.info("=" * 60)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QToolBar, QStatusBar, QFileDialog, QMessageBox,
    QLabel, QSlider, QCheckBox, QScrollArea, QFrame, QSplitter,
    QGroupBox, QFormLayout, QSpinBox, QComboBox, QPushButton,
    QProgressBar, QDialog, QInputDialog
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QPixmap, QFont, QPalette, QColor
from PIL import Image

logger.info("PyQt6 and PIL imports successful")

from ..core.parser import BFFNTFile, parse_bffnt, TextureFormat
from ..texture.decoder import decode_all_sheets, extract_all_glyphs
from ..core.exporter import export_font, import_sheets, apply_imported_sheets
from ..core.writer import save_bffnt, update_bffnt_textures
from ..i18n import tr, set_language, get_language, get_available_languages
from .font_viewer import SheetViewer, CharacterGrid, TextPreview, pil_to_qpixmap
from .mapping_editor import MappingEditorDialog, QuickMappingDialog

logger.info("All module imports successful")


class FontLoadWorker(QThread):
    """Background worker for loading font files."""
    
    progress = pyqtSignal(str, int)  # message, percentage
    finished = pyqtSignal(object, list, list, list)  # bffnt, sheets, sheet_pixmaps, glyph_pixmaps
    error = pyqtSignal(str)  # error message
    
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
    
    def run(self):
        try:
            # Parse file
            self.progress.emit("Parsing BFFNT file...", 10)
            bffnt = parse_bffnt(self.file_path)
            
            # Decode textures
            self.progress.emit("Decoding texture sheets...", 30)
            sheets = decode_all_sheets(bffnt)
            
            # Convert sheets to pixmaps (relatively fast)
            self.progress.emit("Converting to display format...", 50)
            sheet_pixmaps = [pil_to_qpixmap(sheet) for sheet in sheets]
            
            # Extract glyphs
            self.progress.emit("Extracting glyphs...", 60)
            glyphs_pil = extract_all_glyphs(bffnt, sheets)
            
            # Convert glyphs to pixmaps with parallel resizing (this is the slow part)
            self.progress.emit("Processing glyph thumbnails...", 75)
            glyph_pixmaps = self._convert_glyphs_parallel(glyphs_pil)
            
            self.progress.emit("Complete!", 100)
            self.finished.emit(bffnt, sheets, sheet_pixmaps, glyph_pixmaps)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))
    
    def _convert_glyphs_parallel(self, glyphs: List[Image.Image]) -> List[QPixmap]:
        """Convert PIL images to QPixmaps with parallel resizing."""
        def process_one(g: Image.Image) -> QPixmap:
            # Keep original size for better quality - resize only if larger than needed
            # Most glyphs are around 108x128, we want to preserve quality
            max_size = 128
            if g.width > max_size or g.height > max_size:
                # Scale down proportionally
                ratio = min(max_size / g.width, max_size / g.height)
                new_w = int(g.width * ratio)
                new_h = int(g.height * ratio)
                resized = g.resize((new_w, new_h), Image.Resampling.LANCZOS)
            else:
                resized = g
            return pil_to_qpixmap(resized)
        
        # Use more workers for better parallelism (up to CPU count)
        import os
        max_workers = min(8, (os.cpu_count() or 4))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            pixmaps = list(executor.map(process_one, glyphs))
        
        return pixmaps


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.bffnt: Optional[BFFNTFile] = None
        self.sheets: List[Image.Image] = []  # Original unmodified sheets
        self.sheet_pixmaps: List[QPixmap] = []
        self.glyph_pixmaps: List[QPixmap] = []
        self.current_sheet_index = 0
        self.current_file_path: Optional[str] = None
        self.file_modified = False
        self.textures_modified = False  # Track if textures need re-encoding
        self.selected_glyph_index: Optional[int] = None
        
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._apply_dark_theme()
    
    def _setup_ui(self):
        """Setup the main UI layout."""
        self.setWindowTitle(tr("window.title"))
        # Reduced minimum size for better small screen support
        self.setMinimumSize(800, 600)
        self.resize(1400, 900)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel - Info and controls
        left_panel = self._create_info_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Main content tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(False)
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        splitter.addWidget(self.tab_widget)
        
        # Sheet View Tab
        self.sheet_tab = QWidget()
        sheet_layout = QVBoxLayout(self.sheet_tab)
        sheet_layout.setContentsMargins(8, 8, 8, 8)
        
        # Sheet controls
        sheet_controls = QHBoxLayout()
        self.sheet_label = QLabel(tr("sheet.label"))
        sheet_controls.addWidget(self.sheet_label)
        self.sheet_selector = QComboBox()
        self.sheet_selector.currentIndexChanged.connect(self._on_sheet_changed)
        sheet_controls.addWidget(self.sheet_selector)
        
        self.grid_checkbox = QCheckBox(tr("sheet.show_grid"))
        self.grid_checkbox.setChecked(True)
        self.grid_checkbox.toggled.connect(self._on_grid_toggled)
        sheet_controls.addWidget(self.grid_checkbox)
        
        self.zoom_label_prefix = QLabel(tr("sheet.zoom"))
        sheet_controls.addWidget(self.zoom_label_prefix)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(25)
        self.zoom_slider.setMaximum(400)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(150)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        sheet_controls.addWidget(self.zoom_slider)
        self.zoom_label = QLabel("100%")
        sheet_controls.addWidget(self.zoom_label)
        
        sheet_controls.addStretch()
        sheet_layout.addLayout(sheet_controls)
        
        # Sheet viewer in scroll area - enable both scrollbars
        self.sheet_scroll = QScrollArea()
        self.sheet_scroll.setWidgetResizable(False)  # Don't resize, use scrollbars instead
        self.sheet_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sheet_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sheet_viewer = SheetViewer()
        self.sheet_viewer.cellClicked.connect(self._on_cell_clicked)
        self.sheet_viewer.cellHovered.connect(self._on_cell_hovered)
        self.sheet_scroll.setWidget(self.sheet_viewer)
        sheet_layout.addWidget(self.sheet_scroll)
        
        self.tab_widget.addTab(self.sheet_tab, tr("tabs.texture_sheets"))
        
        # Character Grid Tab
        self.char_grid = CharacterGrid()
        self.char_grid.glyphSelected.connect(self._on_glyph_selected)
        self.char_grid.glyphRightClicked.connect(self._on_glyph_right_clicked)
        self.tab_widget.addTab(self.char_grid, tr("tabs.character_grid"))
        
        # Text Preview Tab
        self.text_preview = TextPreview()
        self.tab_widget.addTab(self.text_preview, tr("tabs.text_preview"))
        
        # Set splitter sizes (proportional, will auto-adjust)
        splitter.setSizes([250, 750])
        splitter.setStretchFactor(0, 0)  # Left panel doesn't stretch
        splitter.setStretchFactor(1, 1)  # Right panel stretches
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(tr("status.ready"))
    
    def _create_info_panel(self) -> QWidget:
        """Create the left info panel."""
        panel = QWidget()
        panel.setMaximumWidth(320)
        panel.setMinimumWidth(200)
        
        # Use scroll area for the panel content to handle small screens
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # Font Info Group
        font_group = QGroupBox(tr("info.font_info"))
        font_group.setObjectName("font_info_group")
        font_layout = QFormLayout(font_group)
        font_layout.setSpacing(4)
        font_layout.setContentsMargins(8, 12, 8, 8)
        
        self.info_labels = {}
        self.info_row_labels = {}  # Store row labels for retranslation
        
        # Font info fields: (translation_key, data_key)
        info_fields = [
            ("info.version", "version"),
            ("info.platform", "platform"),
            ("info.width", "width"),
            ("info.height", "height"),
            ("info.ascent", "ascent"),
            ("info.line_feed", "line_feed"),
            ("info.encoding", "encoding"),
        ]
        
        for tr_key, key in info_fields:
            row_label = QLabel(tr(tr_key) + ":")
            row_label.setProperty("tr_key", tr_key)
            self.info_row_labels[key] = row_label
            
            value_label = QLabel("-")
            value_label.setStyleSheet("color: #8af;")
            self.info_labels[key] = value_label
            font_layout.addRow(row_label, value_label)
        
        layout.addWidget(font_group)
        
        # Texture Info Group
        tex_group = QGroupBox(tr("info.texture_info"))
        tex_group.setObjectName("texture_info_group")
        tex_layout = QFormLayout(tex_group)
        tex_layout.setSpacing(4)
        tex_layout.setContentsMargins(8, 12, 8, 8)
        
        # Texture info fields
        tex_fields = [
            ("info.sheets", "sheet_count"),
            ("info.sheet_size", "sheet_size"),
            ("info.cell_size", "cell_size"),
            ("info.cells_per_sheet", "cells_per_sheet"),
            ("info.texture_format", "texture_format"),
        ]
        
        for tr_key, key in tex_fields:
            row_label = QLabel(tr(tr_key) + ":")
            row_label.setProperty("tr_key", tr_key)
            self.info_row_labels[key] = row_label
            
            value_label = QLabel("-")
            value_label.setStyleSheet("color: #8fa;")
            self.info_labels[key] = value_label
            tex_layout.addRow(row_label, value_label)
        
        layout.addWidget(tex_group)
        
        # Character Info Group
        char_group = QGroupBox(tr("info.character_info"))
        char_group.setObjectName("char_info_group")
        char_layout = QFormLayout(char_group)
        char_layout.setSpacing(4)
        char_layout.setContentsMargins(8, 12, 8, 8)
        
        char_fields = [
            ("info.total_glyphs", "total_glyphs"),
            ("info.mapped_chars", "mapped_chars"),
        ]
        
        for tr_key, key in char_fields:
            row_label = QLabel(tr(tr_key) + ":")
            row_label.setProperty("tr_key", tr_key)
            self.info_row_labels[key] = row_label
            
            value_label = QLabel("-")
            value_label.setStyleSheet("color: #fa8;")
            self.info_labels[key] = value_label
            char_layout.addRow(row_label, value_label)
        
        layout.addWidget(char_group)
        
        # Selected Glyph Info
        glyph_group = QGroupBox(tr("info.selected_glyph"))
        glyph_group.setObjectName("glyph_group")
        glyph_layout = QVBoxLayout(glyph_group)
        glyph_layout.setSpacing(4)
        glyph_layout.setContentsMargins(8, 12, 8, 8)
        
        self.glyph_preview = QLabel()
        self.glyph_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.glyph_preview.setMinimumHeight(70)
        self.glyph_preview.setMaximumHeight(100)
        self.glyph_preview.setStyleSheet("background: #222; border-radius: 6px; padding: 6px;")
        glyph_layout.addWidget(self.glyph_preview)
        
        # Non-editable info row
        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        
        # Index
        index_container = QVBoxLayout()
        index_container.setSpacing(0)
        index_label = QLabel("Index")
        index_label.setStyleSheet("color: #6c7086; font-size: 9px;")
        index_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_labels["glyph_index"] = QLabel("-")
        self.info_labels["glyph_index"].setStyleSheet("color: #89b4fa; font-size: 12px; font-weight: bold;")
        self.info_labels["glyph_index"].setAlignment(Qt.AlignmentFlag.AlignCenter)
        index_container.addWidget(index_label)
        index_container.addWidget(self.info_labels["glyph_index"])
        info_row.addLayout(index_container)
        
        # Character
        char_container = QVBoxLayout()
        char_container.setSpacing(0)
        char_label = QLabel("Character")
        char_label.setStyleSheet("color: #6c7086; font-size: 9px;")
        char_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_labels["glyph_char"] = QLabel("-")
        self.info_labels["glyph_char"].setStyleSheet("color: #a6e3a1; font-size: 11px; font-weight: bold;")
        self.info_labels["glyph_char"].setAlignment(Qt.AlignmentFlag.AlignCenter)
        char_container.addWidget(char_label)
        char_container.addWidget(self.info_labels["glyph_char"])
        info_row.addLayout(char_container)
        
        glyph_layout.addLayout(info_row)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #313244;")
        separator.setFixedHeight(1)
        glyph_layout.addWidget(separator)
        
        # Metrics section title
        self.metrics_title_label = QLabel(tr("glyph.metrics_title"))
        self.metrics_title_label.setStyleSheet("color: #cdd6f4; font-size: 10px; font-weight: bold; margin-top: 2px;")
        glyph_layout.addWidget(self.metrics_title_label)
        
        # Metrics in a horizontal compact layout
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(2)
        
        # Left metric
        left_container = QVBoxLayout()
        left_container.setSpacing(0)
        self.left_label = QLabel(tr("glyph.left"))
        self.left_label.setStyleSheet("color: #6c7086; font-size: 9px;")
        self.left_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_label.setToolTip(tr("glyph.left_tooltip"))
        self.glyph_left_spin = QSpinBox()
        self.glyph_left_spin.setRange(-128, 127)
        self.glyph_left_spin.setEnabled(False)
        self.glyph_left_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.glyph_left_spin.setMinimumWidth(45)
        self.glyph_left_spin.setMaximumWidth(55)
        self.glyph_left_spin.valueChanged.connect(self._on_glyph_left_changed)
        self.glyph_left_spin.setToolTip(tr("glyph.left_tooltip"))
        left_container.addWidget(self.left_label)
        left_container.addWidget(self.glyph_left_spin)
        metrics_row.addLayout(left_container)
        
        # Width metric
        width_container = QVBoxLayout()
        width_container.setSpacing(0)
        self.width_label = QLabel(tr("glyph.width"))
        self.width_label.setStyleSheet("color: #6c7086; font-size: 9px;")
        self.width_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.width_label.setToolTip(tr("glyph.width_tooltip"))
        self.glyph_width_spin = QSpinBox()
        self.glyph_width_spin.setRange(0, 255)
        self.glyph_width_spin.setEnabled(False)
        self.glyph_width_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.glyph_width_spin.setMinimumWidth(45)
        self.glyph_width_spin.setMaximumWidth(55)
        self.glyph_width_spin.valueChanged.connect(self._on_glyph_width_changed)
        self.glyph_width_spin.setToolTip(tr("glyph.width_tooltip"))
        width_container.addWidget(self.width_label)
        width_container.addWidget(self.glyph_width_spin)
        metrics_row.addLayout(width_container)
        
        # Advance metric
        advance_container = QVBoxLayout()
        advance_container.setSpacing(0)
        self.advance_label = QLabel(tr("glyph.advance"))
        self.advance_label.setStyleSheet("color: #6c7086; font-size: 9px;")
        self.advance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.advance_label.setToolTip(tr("glyph.advance_tooltip"))
        self.glyph_advance_spin = QSpinBox()
        self.glyph_advance_spin.setRange(0, 255)
        self.glyph_advance_spin.setEnabled(False)
        self.glyph_advance_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.glyph_advance_spin.setMinimumWidth(45)
        self.glyph_advance_spin.setMaximumWidth(55)
        self.glyph_advance_spin.valueChanged.connect(self._on_glyph_advance_changed)
        self.glyph_advance_spin.setToolTip(tr("glyph.advance_tooltip"))
        advance_container.addWidget(self.advance_label)
        advance_container.addWidget(self.glyph_advance_spin)
        metrics_row.addLayout(advance_container)
        
        glyph_layout.addLayout(metrics_row)
        
        # Edit Mapping Button
        self.edit_mapping_btn = QPushButton(tr("glyph.edit_mapping"))
        self.edit_mapping_btn.clicked.connect(self._edit_selected_glyph_mapping)
        self.edit_mapping_btn.setEnabled(False)
        glyph_layout.addWidget(self.edit_mapping_btn)
        
        layout.addWidget(glyph_group)
        
        layout.addStretch()
        
        # Set scroll content and add to panel
        scroll.setWidget(scroll_content)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.addWidget(scroll)
        
        return panel
    
    def _setup_menu(self):
        """Setup menu bar."""
        menubar = self.menuBar()
        
        # File menu
        self.file_menu = menubar.addMenu(tr("menu.file"))
        
        self.menu_open = QAction(tr("menu.open"), self)
        self.menu_open.setShortcut("Ctrl+O")
        self.menu_open.triggered.connect(self._open_file)
        self.file_menu.addAction(self.menu_open)
        
        self.file_menu.addSeparator()
        
        # Save options
        self.menu_save = QAction(tr("menu.save"), self)
        self.menu_save.setShortcut("Ctrl+S")
        self.menu_save.triggered.connect(self._save_bffnt_overwrite)
        self.file_menu.addAction(self.menu_save)
        
        self.menu_save_as = QAction(tr("menu.save_as"), self)
        self.menu_save_as.setShortcut("Ctrl+Shift+S")
        self.menu_save_as.triggered.connect(self._save_bffnt)
        self.file_menu.addAction(self.menu_save_as)
        
        self.file_menu.addSeparator()
        
        self.menu_export_sheet = QAction(tr("menu.export_current_sheet"), self)
        self.menu_export_sheet.triggered.connect(self._export_current_sheet)
        self.file_menu.addAction(self.menu_export_sheet)
        
        self.menu_export_all = QAction(tr("menu.export_all_sheets"), self)
        self.menu_export_all.triggered.connect(self._export_all_sheets)
        self.file_menu.addAction(self.menu_export_all)
        
        self.menu_export_metadata = QAction(tr("menu.export_with_metadata"), self)
        self.menu_export_metadata.triggered.connect(self._export_with_metadata)
        self.file_menu.addAction(self.menu_export_metadata)
        
        self.file_menu.addSeparator()
        
        self.menu_import = QAction(tr("menu.import_sheets"), self)
        self.menu_import.triggered.connect(self._import_sheets)
        self.file_menu.addAction(self.menu_import)
        
        self.file_menu.addSeparator()
        
        self.menu_exit = QAction(tr("menu.exit"), self)
        self.menu_exit.setShortcut("Ctrl+Q")
        self.menu_exit.triggered.connect(self.close)
        self.file_menu.addAction(self.menu_exit)
        
        # Edit menu
        self.edit_menu = menubar.addMenu(tr("menu.edit"))
        
        self.menu_edit_mappings = QAction(tr("menu.edit_mappings"), self)
        self.menu_edit_mappings.triggered.connect(self._open_mapping_editor)
        self.edit_menu.addAction(self.menu_edit_mappings)
        
        # View menu
        self.view_menu = menubar.addMenu(tr("menu.view"))
        
        self.menu_zoom_in = QAction(tr("menu.zoom_in"), self)
        self.menu_zoom_in.setShortcut("Ctrl++")
        self.menu_zoom_in.triggered.connect(lambda: self._adjust_zoom(25))
        self.view_menu.addAction(self.menu_zoom_in)
        
        self.menu_zoom_out = QAction(tr("menu.zoom_out"), self)
        self.menu_zoom_out.setShortcut("Ctrl+-")
        self.menu_zoom_out.triggered.connect(lambda: self._adjust_zoom(-25))
        self.view_menu.addAction(self.menu_zoom_out)
        
        self.menu_zoom_reset = QAction(tr("menu.zoom_reset"), self)
        self.menu_zoom_reset.setShortcut("Ctrl+0")
        self.menu_zoom_reset.triggered.connect(lambda: self.zoom_slider.setValue(100))
        self.view_menu.addAction(self.menu_zoom_reset)
        
        self.view_menu.addSeparator()
        
        # Language submenu
        language_menu = self.view_menu.addMenu("🌐 Language / Idioma")
        self.language_actions = {}
        
        for code, name in get_available_languages().items():
            lang_action = QAction(name, self)
            lang_action.setCheckable(True)
            lang_action.setChecked(code == get_language())
            lang_action.triggered.connect(lambda checked, c=code: self._change_language(c))
            language_menu.addAction(lang_action)
            self.language_actions[code] = lang_action
    
    def _change_language(self, lang_code: str):
        """Change the application language."""
        if set_language(lang_code):
            # Update checkmarks
            for code, action in self.language_actions.items():
                action.setChecked(code == lang_code)
            
            # Get language display name
            lang_name = get_available_languages().get(lang_code, lang_code)
            
            # Show message that restart is recommended for full effect
            self.status_bar.showMessage(tr("status.language_changed", language=lang_name))
            
            # Rebuild menus and toolbar with new language
            self._retranslate_ui()
    
    def _retranslate_ui(self):
        """Update all UI text with current language translations."""
        # Update window title
        self._update_window_title()
        
        # Update tab names
        self.tab_widget.setTabText(0, tr("tabs.texture_sheets"))
        self.tab_widget.setTabText(1, tr("tabs.character_grid"))
        self.tab_widget.setTabText(2, tr("tabs.text_preview"))
        
        # Update menus
        if hasattr(self, 'file_menu'):
            self.file_menu.setTitle(tr("menu.file"))
        if hasattr(self, 'edit_menu'):
            self.edit_menu.setTitle(tr("menu.edit"))
        if hasattr(self, 'view_menu'):
            self.view_menu.setTitle(tr("menu.view"))
        
        # Update menu items
        if hasattr(self, 'menu_open'):
            self.menu_open.setText(tr("menu.open"))
        if hasattr(self, 'menu_save'):
            self.menu_save.setText(tr("menu.save"))
        if hasattr(self, 'menu_save_as'):
            self.menu_save_as.setText(tr("menu.save_as"))
        if hasattr(self, 'menu_export_sheet'):
            self.menu_export_sheet.setText(tr("menu.export_current_sheet"))
        if hasattr(self, 'menu_export_all'):
            self.menu_export_all.setText(tr("menu.export_all_sheets"))
        if hasattr(self, 'menu_export_metadata'):
            self.menu_export_metadata.setText(tr("menu.export_with_metadata"))
        if hasattr(self, 'menu_import'):
            self.menu_import.setText(tr("menu.import_sheets"))
        if hasattr(self, 'menu_exit'):
            self.menu_exit.setText(tr("menu.exit"))
        if hasattr(self, 'menu_edit_mappings'):
            self.menu_edit_mappings.setText(tr("menu.edit_mappings"))
        if hasattr(self, 'menu_zoom_in'):
            self.menu_zoom_in.setText(tr("menu.zoom_in"))
        if hasattr(self, 'menu_zoom_out'):
            self.menu_zoom_out.setText(tr("menu.zoom_out"))
        if hasattr(self, 'menu_zoom_reset'):
            self.menu_zoom_reset.setText(tr("menu.zoom_reset"))
        
        # Update toolbar
        if hasattr(self, 'toolbar_open'):
            self.toolbar_open.setText(tr("toolbar.open"))
            self.toolbar_open.setToolTip(tr("toolbar.open_tooltip"))
        if hasattr(self, 'toolbar_save'):
            self.toolbar_save.setText(tr("toolbar.save"))
            self.toolbar_save.setToolTip(tr("toolbar.save_tooltip"))
        if hasattr(self, 'toolbar_import'):
            self.toolbar_import.setText(tr("toolbar.import"))
            self.toolbar_import.setToolTip(tr("toolbar.import_tooltip"))
        if hasattr(self, 'toolbar_export'):
            self.toolbar_export.setText(tr("toolbar.export"))
            self.toolbar_export.setToolTip(tr("toolbar.export_tooltip"))
        if hasattr(self, 'toolbar_export_all'):
            self.toolbar_export_all.setText(tr("toolbar.export_all"))
            self.toolbar_export_all.setToolTip(tr("toolbar.export_all_tooltip"))
        if hasattr(self, 'toolbar_edit_mappings'):
            self.toolbar_edit_mappings.setText(tr("toolbar.edit_mappings"))
            self.toolbar_edit_mappings.setToolTip(tr("toolbar.edit_mappings_tooltip"))
        
        # Update sheet controls
        if hasattr(self, 'sheet_label'):
            self.sheet_label.setText(tr("sheet.label"))
        if hasattr(self, 'grid_checkbox'):
            self.grid_checkbox.setText(tr("sheet.show_grid"))
        if hasattr(self, 'zoom_label_prefix'):
            self.zoom_label_prefix.setText(tr("sheet.zoom"))
        
        # Update group box titles
        for group in self.findChildren(QGroupBox):
            name = group.objectName()
            if name == "font_info_group":
                group.setTitle(tr("info.font_info"))
            elif name == "texture_info_group":
                group.setTitle(tr("info.texture_info"))
            elif name == "char_info_group":
                group.setTitle(tr("info.character_info"))
            elif name == "glyph_group":
                group.setTitle(tr("info.selected_glyph"))
        
        # Update info row labels
        if hasattr(self, 'info_row_labels'):
            for key, label in self.info_row_labels.items():
                tr_key = label.property("tr_key")
                if tr_key:
                    label.setText(tr(tr_key) + ":")
        
        # Update glyph metrics labels
        if hasattr(self, 'metrics_title_label'):
            self.metrics_title_label.setText(tr("glyph.metrics_title"))
        if hasattr(self, 'left_label'):
            self.left_label.setText(tr("glyph.left"))
            self.left_label.setToolTip(tr("glyph.left_tooltip"))
        if hasattr(self, 'width_label'):
            self.width_label.setText(tr("glyph.width"))
            self.width_label.setToolTip(tr("glyph.width_tooltip"))
        if hasattr(self, 'advance_label'):
            self.advance_label.setText(tr("glyph.advance"))
            self.advance_label.setToolTip(tr("glyph.advance_tooltip"))
        
        # Update Edit Mapping button
        if hasattr(self, 'edit_mapping_btn'):
            self.edit_mapping_btn.setText(tr("glyph.edit_mapping"))
        
        # Update status bar if no file loaded
        if not self.bffnt:
            self.status_bar.showMessage(tr("status.ready"))
    
    def _setup_toolbar(self):
        """Setup toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        # Allow toolbar to wrap on small screens
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        self.main_toolbar = toolbar  # Store reference for retranslation
        
        self.toolbar_open = QAction(tr("toolbar.open"), self)
        self.toolbar_open.setToolTip(tr("toolbar.open_tooltip"))
        self.toolbar_open.triggered.connect(self._open_file)
        toolbar.addAction(self.toolbar_open)
        
        toolbar.addSeparator()
        
        self.toolbar_save = QAction(tr("toolbar.save"), self)
        self.toolbar_save.setToolTip(tr("toolbar.save_tooltip"))
        self.toolbar_save.triggered.connect(self._save_bffnt)
        toolbar.addAction(self.toolbar_save)
        
        toolbar.addSeparator()
        
        self.toolbar_import = QAction(tr("toolbar.import"), self)
        self.toolbar_import.setToolTip(tr("toolbar.import_tooltip"))
        self.toolbar_import.triggered.connect(self._import_sheets)
        toolbar.addAction(self.toolbar_import)
        
        self.toolbar_export = QAction(tr("toolbar.export"), self)
        self.toolbar_export.setToolTip(tr("toolbar.export_tooltip"))
        self.toolbar_export.triggered.connect(self._export_current_sheet)
        toolbar.addAction(self.toolbar_export)
        
        self.toolbar_export_all = QAction(tr("toolbar.export_all"), self)
        self.toolbar_export_all.setToolTip(tr("toolbar.export_all_tooltip"))
        self.toolbar_export_all.triggered.connect(self._export_with_metadata)
        toolbar.addAction(self.toolbar_export_all)
        
        toolbar.addSeparator()
        
        self.toolbar_edit_mappings = QAction(tr("toolbar.edit_mappings"), self)
        self.toolbar_edit_mappings.setToolTip(tr("toolbar.edit_mappings_tooltip"))
        self.toolbar_edit_mappings.triggered.connect(self._open_mapping_editor)
        toolbar.addAction(self.toolbar_edit_mappings)
    
    def _apply_dark_theme(self):
        """Apply dark theme to the application."""
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-size: 13px;
            }
            QMenuBar {
                background-color: #181825;
                color: #cdd6f4;
                font-size: 13px;
                padding: 4px;
            }
            QMenuBar::item {
                padding: 6px 12px;
            }
            QMenuBar::item:selected {
                background-color: #313244;
            }
            QMenu {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #313244;
                font-size: 13px;
            }
            QMenu::item {
                padding: 8px 25px;
            }
            QMenu::item:selected {
                background-color: #45475a;
            }
            QToolBar {
                background-color: #181825;
                border: none;
                spacing: 4px;
                padding: 4px 6px;
            }
            QToolButton {
                background-color: transparent;
                color: #cdd6f4;
                padding: 6px 10px;
                border-radius: 6px;
                font-size: 12px;
            }
            QToolButton:hover {
                background-color: #313244;
            }
            QTabWidget::pane {
                border: 1px solid #313244;
                border-radius: 6px;
                background-color: #1e1e2e;
                top: -1px;
            }
            QTabBar::tab {
                background-color: #181825;
                color: #a6adc8;
                padding: 8px 14px;
                margin-right: 2px;
                margin-bottom: 0px;
                border: 1px solid #313244;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e2e;
                color: #89b4fa;
                font-weight: bold;
                border: 1px solid #45475a;
                border-bottom: 1px solid #1e1e2e;
            }
            QTabBar::tab:hover:!selected {
                background-color: #252535;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #313244;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 8px;
                font-size: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
            QScrollArea {
                border: 1px solid #313244;
                border-radius: 4px;
            }
            QScrollBar:vertical {
                background-color: #181825;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #45475a;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #585b70;
            }
            QScrollBar:horizontal {
                background-color: #181825;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background-color: #45475a;
                border-radius: 6px;
                min-width: 20px;
            }
            QComboBox {
                background-color: #313244;
                border: 2px solid #45475a;
                border-radius: 6px;
                padding: 8px 12px;
                min-width: 120px;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e2e;
                border: 2px solid #45475a;
                selection-background-color: #45475a;
                font-size: 13px;
                padding: 4px;
            }
            QSlider::groove:horizontal {
                background-color: #313244;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background-color: #89b4fa;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background-color: #b4befe;
            }
            QCheckBox {
                spacing: 10px;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 22px;
                height: 22px;
                border-radius: 5px;
                border: 2px solid #45475a;
            }
            QCheckBox::indicator:checked {
                background-color: #89b4fa;
                border-color: #89b4fa;
            }
            QLineEdit {
                background-color: #313244;
                border: 2px solid #45475a;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #89b4fa;
            }
            QPushButton {
                background-color: #313244;
                border: 2px solid #45475a;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45475a;
                border-color: #585b70;
            }
            QPushButton:pressed {
                background-color: #585b70;
            }
            QPushButton:disabled {
                background-color: #252535;
                color: #6c6f85;
                border-color: #313244;
            }
            QStatusBar {
                background-color: #181825;
                color: #a6adc8;
                font-size: 12px;
                padding: 4px;
            }
            QLabel {
                color: #cdd6f4;
                font-size: 12px;
            }
            QSpinBox {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 2px 4px;
                font-size: 11px;
                font-weight: bold;
                color: #cdd6f4;
                min-height: 18px;
            }
            QSpinBox:hover {
                border-color: #585b70;
            }
            QSpinBox:focus {
                border-color: #89b4fa;
            }
            QSpinBox:disabled {
                background-color: #252535;
                color: #6c7086;
                border-color: #313244;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #45475a;
                border: none;
                width: 14px;
                border-radius: 2px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #585b70;
            }
            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {
                background-color: #89b4fa;
            }
            QSpinBox::up-arrow {
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-bottom: 4px solid #cdd6f4;
                width: 0;
                height: 0;
            }
            QSpinBox::down-arrow {
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 4px solid #cdd6f4;
                width: 0;
                height: 0;
            }
        """)
    
    def _open_file(self):
        """Open a BFFNT file."""
        logger.info("Opening file dialog...")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open BFFNT Font File",
            "",
            "BFFNT Files (*.bffnt);;All Files (*.*)"
        )
        
        if file_path:
            logger.info(f"Selected file: {file_path}")
            self.load_font(file_path)
        else:
            logger.info("File dialog cancelled")
    
    def load_font(self, file_path: str):
        """Load and display a BFFNT file using background thread."""
        logger.info(f"Loading font: {file_path}")
        self.current_file_path = file_path
        self.file_modified = False
        
        # Show loading status
        self.status_bar.showMessage(f"Loading {os.path.basename(file_path)}...")
        
        # Create and start worker thread
        self.load_worker = FontLoadWorker(file_path)
        self.load_worker.progress.connect(self._on_load_progress)
        self.load_worker.finished.connect(self._on_load_finished)
        self.load_worker.error.connect(self._on_load_error)
        self.load_worker.start()
    
    def _on_load_progress(self, message: str, percentage: int):
        """Handle loading progress updates."""
        logger.debug(f"Load progress: {message} ({percentage}%)")
        self.status_bar.showMessage(f"{message} ({percentage}%)")
        QApplication.processEvents()
    
    def _on_load_finished(self, bffnt, sheets, sheet_pixmaps, glyph_pixmaps):
        """Handle loading completion."""
        logger.info("=" * 50)
        logger.info("FONT LOADED SUCCESSFULLY")
        logger.info("=" * 50)
        
        self.bffnt = bffnt
        self.sheets = sheets
        self.sheet_pixmaps = sheet_pixmaps
        self.glyph_pixmaps = glyph_pixmaps
        self.textures_modified = False  # Reset - textures are fresh from file
        self.file_modified = False
        
        logger.info(f"Sheets: {len(sheets)}")
        logger.info(f"Sheet size: {sheets[0].size if sheets else 'N/A'}")
        logger.info(f"Sheet mode: {sheets[0].mode if sheets else 'N/A'}")
        logger.info(f"Glyphs: {len(glyph_pixmaps)}")
        logger.info(f"TGLP cells_per_row: {bffnt.tglp.cells_per_row}")
        logger.info(f"TGLP cells_per_column: {bffnt.tglp.cells_per_column}")
        logger.info(f"TGLP cell_width: {bffnt.tglp.cell_width}")
        logger.info(f"TGLP cell_height: {bffnt.tglp.cell_height}")
        
        # Update UI
        self._update_info_panel()
        self._update_sheet_selector()
        self._update_sheet_viewer()
        self._update_character_grid()
        self._update_text_preview()
        
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Font"
        self._update_window_title()
        
        # Show statistics
        total_glyphs = len(self.glyph_pixmaps)
        mapped_chars = len(self.bffnt.char_map)
        self.status_bar.showMessage(
            f"✅ Loaded {file_name} | {total_glyphs} glyphs, {mapped_chars} mapped characters | Ready"
        )
        logger.info(f"Load complete: {total_glyphs} glyphs, {mapped_chars} mapped characters")
    
    def _on_load_error(self, error_message: str):
        """Handle loading errors."""
        logger.error(f"Failed to load font: {error_message}")
        QMessageBox.critical(self, "Error", f"Failed to load font file:\n{error_message}")
        self.status_bar.showMessage("Error loading file")
    
    def _update_info_panel(self):
        """Update the info panel with font data."""
        if not self.bffnt:
            return
        
        header = self.bffnt.header
        finf = self.bffnt.finf
        tglp = self.bffnt.tglp
        
        # Font info
        self.info_labels["version"].setText(f"0x{header.version:08X}")
        self.info_labels["platform"].setText(header.platform.name)
        self.info_labels["width"].setText(str(finf.width))
        self.info_labels["height"].setText(str(finf.height))
        self.info_labels["ascent"].setText(str(finf.ascent))
        self.info_labels["line_feed"].setText(str(finf.line_feed))
        
        encoding_names = {0: "UTF-8", 1: "Unicode", 2: "ShiftJIS", 3: "CP1252"}
        self.info_labels["encoding"].setText(encoding_names.get(finf.char_encoding, "Unknown"))
        
        # Texture info
        self.info_labels["sheet_count"].setText(str(tglp.sheet_count))
        self.info_labels["sheet_size"].setText(f"{tglp.sheet_width} × {tglp.sheet_height}")
        self.info_labels["cell_size"].setText(f"{tglp.cell_width} × {tglp.cell_height}")
        self.info_labels["cells_per_sheet"].setText(
            f"{tglp.cells_per_row} × {tglp.cells_per_column}"
        )
        self.info_labels["texture_format"].setText(tglp.texture_format.name)
        
        # Character info
        total_cells = tglp.cells_per_row * tglp.cells_per_column * tglp.sheet_count
        self.info_labels["total_glyphs"].setText(str(total_cells))
        self.info_labels["mapped_chars"].setText(str(len(self.bffnt.char_map)))
    
    def _update_sheet_selector(self):
        """Update sheet selector combo box."""
        self.sheet_selector.clear()
        if self.bffnt:
            for i in range(self.bffnt.tglp.sheet_count):
                self.sheet_selector.addItem(f"Sheet {i}")
    
    def _update_sheet_viewer(self):
        """Update the sheet viewer with current sheet."""
        if not self.bffnt or not self.sheet_pixmaps:
            return
        
        idx = self.current_sheet_index
        if idx < len(self.sheet_pixmaps):
            tglp = self.bffnt.tglp
            self.sheet_viewer.set_sheet(
                self.sheet_pixmaps[idx],
                tglp.cell_width,
                tglp.cell_height,
                tglp.cells_per_row,
                tglp.cells_per_column
            )
    
    def _update_character_grid(self):
        """Update the character grid with glyphs."""
        if self.glyph_pixmaps and self.bffnt:
            self.char_grid.set_glyphs(self.glyph_pixmaps, self.bffnt.char_map)
    
    def _update_text_preview(self):
        """Update the text preview widget."""
        if self.bffnt and self.glyph_pixmaps:
            # Get full-size glyphs for preview
            glyphs_pil = extract_all_glyphs(self.bffnt, self.sheets)
            preview_pixmaps = [pil_to_qpixmap(g) for g in glyphs_pil]
            self.text_preview.set_font(self.bffnt, preview_pixmaps)
    
    def _on_sheet_changed(self, index: int):
        """Handle sheet selection change."""
        self.current_sheet_index = index
        self._update_sheet_viewer()
    
    def _on_grid_toggled(self, checked: bool):
        """Handle grid visibility toggle."""
        self.sheet_viewer.set_show_grid(checked)
    
    def _on_zoom_changed(self, value: int):
        """Handle zoom slider change."""
        zoom = value / 100.0
        self.sheet_viewer.set_zoom(zoom)
        self.zoom_label.setText(f"{value}%")
    
    def _adjust_zoom(self, delta: int):
        """Adjust zoom by delta percent."""
        current = self.zoom_slider.value()
        self.zoom_slider.setValue(current + delta)
    
    def _on_cell_clicked(self, row: int, col: int):
        """Handle cell click in sheet viewer."""
        if not self.bffnt:
            return
        
        tglp = self.bffnt.tglp
        glyphs_per_sheet = tglp.cells_per_row * tglp.cells_per_column
        glyph_index = self.current_sheet_index * glyphs_per_sheet + row * tglp.cells_per_row + col
        
        self._show_glyph_info(glyph_index)
    
    def _on_cell_hovered(self, row: int, col: int):
        """Handle cell hover in sheet viewer."""
        if not self.bffnt:
            return
        
        tglp = self.bffnt.tglp
        glyphs_per_sheet = tglp.cells_per_row * tglp.cells_per_column
        glyph_index = self.current_sheet_index * glyphs_per_sheet + row * tglp.cells_per_row + col
        
        self.status_bar.showMessage(f"Glyph #{glyph_index} at row {row}, column {col}")
    
    def _on_glyph_right_clicked(self, glyph_index: int, char_code: int, pos):
        """Handle right-click on glyph - show context menu."""
        if not self.bffnt or not self.sheets:
            return
        
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtCore import QPoint
        
        # Create context menu
        menu = QMenu(self)
        
        # Get character label for menu
        char_label = ""
        if char_code and char_code < 0xFFFF:
            try:
                char = chr(char_code)
                if char.isprintable():
                    char_label = f" '{char}'"
            except:
                pass
        
        # Export action
        export_action = menu.addAction(f"📤 Export Glyph #{glyph_index}{char_label}...")
        export_action.triggered.connect(lambda: self._export_single_glyph(glyph_index, char_code))
        
        # Import action
        import_action = menu.addAction(f"📥 Import Glyph #{glyph_index}{char_label}...")
        import_action.triggered.connect(lambda: self._import_single_glyph(glyph_index, char_code))
        
        menu.addSeparator()
        
        # Edit mapping action
        edit_action = menu.addAction(f"✏️ Edit Mapping...")
        edit_action.triggered.connect(lambda: self._edit_glyph_mapping(glyph_index))
        
        # Show menu at cursor position
        menu.exec(pos)
    
    def _export_single_glyph(self, glyph_index: int, char_code: int):
        """Export a single glyph as PNG."""
        if not self.bffnt or not self.sheets:
            return
        
        # Get character label for filename suggestion
        char_label = ""
        if char_code and char_code < 0xFFFF:
            try:
                char = chr(char_code)
                if char.isalnum():
                    char_label = f"_{char}"
            except:
                pass
        
        default_name = f"glyph_{glyph_index}{char_label}.png"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export Glyph #{glyph_index}",
            default_name,
            "PNG Files (*.png)"
        )
        
        if file_path:
            try:
                # Extract the glyph from sheets
                from ..texture.decoder import extract_glyph
                
                sheet_idx, row, col = self.bffnt.get_glyph_position(glyph_index)
                if sheet_idx < len(self.sheets):
                    glyph = extract_glyph(self.sheets[sheet_idx], self.bffnt.tglp, row, col)
                    glyph.save(file_path, "PNG")
                    
                    self.status_bar.showMessage(f"✅ Exported glyph #{glyph_index} to {os.path.basename(file_path)}")
                else:
                    QMessageBox.warning(self, "Error", f"Sheet index {sheet_idx} out of range")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export glyph:\n{str(e)}")
                import traceback
                traceback.print_exc()
    
    def _import_single_glyph(self, glyph_index: int, char_code: int):
        """Import a PNG to replace a single glyph."""
        if not self.bffnt or not self.sheets:
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Import Glyph for #{glyph_index}",
            "",
            "PNG Files (*.png);;All Images (*.png *.jpg *.bmp)"
        )
        
        if file_path:
            try:
                # Load the image
                from PIL import Image
                new_glyph = Image.open(file_path).convert('RGBA')
                
                # Get expected size
                tglp = self.bffnt.tglp
                expected_width = tglp.cell_width
                expected_height = tglp.cell_height
                
                # Resize if needed
                if new_glyph.width != expected_width or new_glyph.height != expected_height:
                    result = QMessageBox.question(
                        self, "Size Mismatch",
                        f"The imported image is {new_glyph.width}x{new_glyph.height}, "
                        f"but the expected size is {expected_width}x{expected_height}.\n\n"
                        "Resize to fit?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if result == QMessageBox.StandardButton.Yes:
                        new_glyph = new_glyph.resize((expected_width, expected_height), Image.Resampling.LANCZOS)
                    else:
                        return
                
                # Get glyph position
                sheet_idx, row, col = self.bffnt.get_glyph_position(glyph_index)
                if sheet_idx >= len(self.sheets):
                    QMessageBox.warning(self, "Error", f"Sheet index {sheet_idx} out of range")
                    return
                
                # Calculate paste position (with 1px padding offset)
                cell_width = tglp.cell_width + 1
                cell_height = tglp.cell_height + 1
                x = col * cell_width + 1
                y = row * cell_height + 1
                
                # Paste the glyph into the sheet
                sheet = self.sheets[sheet_idx]
                if sheet.mode != 'RGBA':
                    sheet = sheet.convert('RGBA')
                sheet.paste(new_glyph, (x, y))
                self.sheets[sheet_idx] = sheet
                
                # Mark as modified
                self.file_modified = True
                self.textures_modified = True  # Important: mark textures as needing re-encoding
                self._update_window_title()
                
                # Refresh UI
                self._refresh_after_import()
                
                self.status_bar.showMessage(f"✅ Imported glyph #{glyph_index} - Remember to save!")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import glyph:\n{str(e)}")
                import traceback
                traceback.print_exc()
    
    def _edit_glyph_mapping(self, glyph_index: int):
        """Edit the mapping for a specific glyph."""
        self.selected_glyph_index = glyph_index
        self._edit_selected_glyph_mapping()
    
    def _refresh_after_import(self):
        """Refresh UI after importing a glyph."""
        # Regenerate pixmaps
        self.sheet_pixmaps = [pil_to_qpixmap(sheet) for sheet in self.sheets]
        
        # Regenerate glyph pixmaps
        from ..texture.decoder import extract_all_glyphs
        glyphs_pil = extract_all_glyphs(self.bffnt, self.sheets)
        
        def process_one(g):
            resized = g.resize((48, 48), Image.Resampling.BILINEAR)
            return pil_to_qpixmap(resized)
        
        from PIL import Image
        self.glyph_pixmaps = [process_one(g) for g in glyphs_pil]
        
        # Update views
        self._update_sheet_viewer()
        self._update_character_grid()
        self._update_text_preview()
    
    def _on_glyph_selected(self, glyph_index: int, char_code: int):
        """Handle glyph selection in character grid."""
        self._show_glyph_info(glyph_index)
    
    def _show_glyph_info(self, glyph_index: int):
        """Show information about a glyph."""
        if not self.bffnt or glyph_index >= len(self.glyph_pixmaps):
            return
        
        # Store selected glyph index
        self.selected_glyph_index = glyph_index
        self.edit_mapping_btn.setEnabled(True)
        
        # Show glyph preview
        pixmap = self.glyph_pixmaps[glyph_index]
        scaled = pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        self.glyph_preview.setPixmap(scaled)
        
        # Find character code for this glyph
        char_code = None
        for code, idx in self.bffnt.char_map.items():
            if idx == glyph_index:
                char_code = code
                break
        
        # Update info labels
        self.info_labels["glyph_index"].setText(str(glyph_index))
        
        if char_code:
            try:
                char = chr(char_code)
                if char.isprintable():
                    self.info_labels["glyph_char"].setText(f"'{char}' (U+{char_code:04X})")
                else:
                    self.info_labels["glyph_char"].setText(f"U+{char_code:04X}")
            except:
                self.info_labels["glyph_char"].setText(f"U+{char_code:04X}")
        else:
            self.info_labels["glyph_char"].setText("(unmapped)")
        
        # Update metric spinboxes - ensure entry exists (creates if missing)
        width_info = self.bffnt.ensure_char_width(glyph_index)
        
        # Block signals to avoid triggering change events during update
        self.glyph_left_spin.blockSignals(True)
        self.glyph_width_spin.blockSignals(True)
        self.glyph_advance_spin.blockSignals(True)
        
        self.glyph_left_spin.setValue(width_info.left)
        self.glyph_width_spin.setValue(width_info.glyph_width)
        self.glyph_advance_spin.setValue(width_info.char_width)
        
        self.glyph_left_spin.setEnabled(True)
        self.glyph_width_spin.setEnabled(True)
        self.glyph_advance_spin.setEnabled(True)
        
        self.glyph_left_spin.blockSignals(False)
        self.glyph_width_spin.blockSignals(False)
        self.glyph_advance_spin.blockSignals(False)
    
    def _export_current_sheet(self):
        """Export the currently displayed sheet."""
        if not self.sheets:
            QMessageBox.warning(self, "Warning", "No font loaded")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Sheet",
            f"sheet_{self.current_sheet_index}.png",
            "PNG Files (*.png);;All Files (*.*)"
        )
        
        if file_path:
            try:
                self.sheets[self.current_sheet_index].save(file_path)
                self.status_bar.showMessage(f"📤 Exported sheet {self.current_sheet_index} to {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export:\n{str(e)}")
    
    def _export_all_sheets(self):
        """Export all texture sheets."""
        if not self.sheets:
            QMessageBox.warning(self, "Warning", "No font loaded")
            return
        
        folder = QFileDialog.getExistingDirectory(self, "Select Export Folder")
        
        if folder:
            try:
                for i, sheet in enumerate(self.sheets):
                    file_path = os.path.join(folder, f"sheet_{i}.png")
                    sheet.save(file_path)
                self.status_bar.showMessage(f"📦 Exported {len(self.sheets)} sheets to {os.path.basename(folder)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export:\n{str(e)}")
    
    def _export_with_metadata(self):
        """Export sheets with metadata JSON containing character mappings."""
        if not self.bffnt or not self.sheets:
            QMessageBox.warning(self, "Warning", "No font loaded")
            return
        
        # Create export options dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Export Options")
        dialog.setMinimumWidth(350)
        layout = QVBoxLayout(dialog)
        
        # Description
        desc = QLabel("Select export options:")
        desc.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(desc)
        
        # Grid guide checkbox
        grid_guide_cb = QCheckBox("Export Grid Guide (sheet_X_guide.png)")
        grid_guide_cb.setToolTip(
            "Creates a copy of each sheet with grid overlay.\n"
            "Use for reference only - do not import back."
        )
        grid_guide_cb.setChecked(True)
        layout.addWidget(grid_guide_cb)
        
        # Grid template checkbox
        grid_template_cb = QCheckBox("Export Grid Template (grid_template.png)")
        grid_template_cb.setToolTip(
            "Creates a transparent PNG with only grid lines.\n"
            "Use as a layer in your image editor."
        )
        grid_template_cb.setChecked(True)
        layout.addWidget(grid_template_cb)
        
        # Info label
        info = QLabel(
            "💡 Tip: The grid files are only for reference.\n"
            "Edit the sheet_X.png files and import those back."
        )
        info.setStyleSheet("color: #888; margin-top: 10px;")
        layout.addWidget(info)
        
        # Buttons
        buttons = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        export_btn = QPushButton("Export")
        export_btn.setDefault(True)
        export_btn.clicked.connect(dialog.accept)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(export_btn)
        layout.addLayout(buttons)
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        folder = QFileDialog.getExistingDirectory(self, "Select Export Folder")
        
        if folder:
            try:
                self.status_bar.showMessage("Exporting with metadata...")
                QApplication.processEvents()
                
                metadata_path = export_font(
                    self.bffnt, self.sheets, folder,
                    export_grid_guide=grid_guide_cb.isChecked(),
                    export_grid_template=grid_template_cb.isChecked()
                )
                
                # Build export summary
                files_exported = [f"{len(self.sheets)} sheets", "metadata.json"]
                if grid_guide_cb.isChecked():
                    files_exported.append(f"{len(self.sheets)} grid guides")
                if grid_template_cb.isChecked():
                    files_exported.append("grid template")
                
                self.status_bar.showMessage(
                    f"📦 Exported {', '.join(files_exported)} to {os.path.basename(folder)}"
                )
                QMessageBox.information(
                    self, "Export Complete",
                    f"Exported to {folder}:\n\n"
                    f"• {len(self.sheets)} sheet PNG files\n"
                    f"• metadata.json\n"
                    f"{'• Grid guides (for reference)' + chr(10) if grid_guide_cb.isChecked() else ''}"
                    f"{'• Grid template (for layer overlay)' if grid_template_cb.isChecked() else ''}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export:\n{str(e)}")
                import traceback
                traceback.print_exc()
    
    def _import_sheets(self):
        """Import modified texture sheets and update the BFFNT."""
        if not self.bffnt:
            QMessageBox.warning(self, "Warning", "No font loaded. Open a BFFNT file first.")
            return
        
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder with Exported Sheets"
        )
        
        if not folder:
            return
        
        try:
            self.status_bar.showMessage("Importing sheets...")
            QApplication.processEvents()
            
            # Import sheets
            new_sheets, metadata = import_sheets(folder)
            
            if not new_sheets:
                QMessageBox.warning(
                    self, "Warning",
                    "No sheet_*.png files found in the selected folder."
                )
                return
            
            # Encode and apply to BFFNT
            self.status_bar.showMessage("Encoding textures...")
            QApplication.processEvents()
            
            new_bntx_data = apply_imported_sheets(self.bffnt, new_sheets)
            update_bffnt_textures(self.bffnt, new_bntx_data, len(new_sheets))
            
            # Update display
            self.sheets = new_sheets
            self.sheet_pixmaps = [pil_to_qpixmap(sheet) for sheet in self.sheets]
            self.textures_modified = True  # Mark that textures need re-encoding
            
            # Re-extract glyphs
            glyphs_pil = extract_all_glyphs(self.bffnt, self.sheets)
            self.glyph_pixmaps = [
                pil_to_qpixmap(g.resize((48, 48), Image.Resampling.LANCZOS))
                for g in glyphs_pil
            ]
            
            self._refresh_ui()
            self.file_modified = True
            self._update_window_title()
            
            self.status_bar.showMessage(
                f"📥 Imported {len(new_sheets)} sheets - File modified (unsaved)"
            )
            QMessageBox.information(
                self, "Import Complete",
                f"Imported {len(new_sheets)} sheets.\n\n"
                "Use File → Save BFFNT to save the modified font file."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def _save_bffnt_overwrite(self):
        """Save BFFNT file, overwriting the original."""
        logger.info("=" * 60)
        logger.info("SAVE (Overwrite) - Called")
        logger.info("=" * 60)
        
        if not self.bffnt:
            QMessageBox.warning(self, "Warning", "No font loaded")
            return
        
        if not self.current_file_path:
            # No file loaded, use Save As instead
            self._save_bffnt()
            return
        
        # Confirm overwrite
        reply = QMessageBox.question(
            self, "Confirm Save",
            f"Overwrite the original file?\n\n{self.current_file_path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            self.status_bar.showMessage("Saving...")
            QApplication.processEvents()
            
            # Only encode textures if they were actually modified
            if self.textures_modified and self.sheets:
                self.status_bar.showMessage("Encoding textures and saving...")
                QApplication.processEvents()
                logger.info(f"Encoding {len(self.sheets)} texture sheets (textures were modified)...")
                new_bntx_data = apply_imported_sheets(self.bffnt, self.sheets)
                update_bffnt_textures(self.bffnt, new_bntx_data, len(self.sheets))
                logger.info(f"Encoded BNTX data: {len(new_bntx_data)} bytes")
            else:
                logger.info("Textures not modified, skipping re-encoding to preserve original data")
            
            save_bffnt(self.bffnt, self.current_file_path)
            
            self.file_modified = False
            self.textures_modified = False  # Reset after successful save
            self._update_window_title()
            self.status_bar.showMessage(f"💾 Saved to {os.path.basename(self.current_file_path)}")
            logger.info(f"Saved to: {self.current_file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def _save_bffnt(self):
        """Save the modified BFFNT file."""
        logger.info("=" * 60)
        logger.info("SAVE AS - Called")
        logger.info("=" * 60)
        if not self.bffnt:
            QMessageBox.warning(self, "Warning", "No font loaded")
            return
        
        # Suggest original filename with _modified suffix, in the same directory
        default_path = ""
        if self.current_file_path:
            directory = os.path.dirname(self.current_file_path)
            base = os.path.splitext(os.path.basename(self.current_file_path))[0]
            default_path = os.path.join(directory, f"{base}_modified.bffnt")
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save BFFNT File",
            default_path,
            "BFFNT Files (*.bffnt);;All Files (*.*)"
        )
        
        if file_path:
            try:
                self.status_bar.showMessage("Saving...")
                QApplication.processEvents()
                
                # Only encode textures if they were actually modified
                if self.textures_modified and self.sheets:
                    self.status_bar.showMessage("Encoding textures and saving...")
                    QApplication.processEvents()
                    logger.info(f"Encoding {len(self.sheets)} texture sheets (textures were modified)...")
                    new_bntx_data = apply_imported_sheets(self.bffnt, self.sheets)
                    update_bffnt_textures(self.bffnt, new_bntx_data, len(self.sheets))
                    logger.info(f"Encoded BNTX data: {len(new_bntx_data)} bytes")
                else:
                    logger.info("Textures not modified, skipping re-encoding to preserve original data")
                
                save_bffnt(self.bffnt, file_path)
                
                self.file_modified = False
                self.textures_modified = False  # Reset after successful save
                self._update_window_title()
                self.status_bar.showMessage(f"💾 Saved to {os.path.basename(file_path)}")
                QMessageBox.information(
                    self, "Save Complete",
                    f"BFFNT saved successfully to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{str(e)}")
                import traceback
                traceback.print_exc()
    
    def _open_mapping_editor(self):
        """Open the character mapping editor dialog."""
        if not self.bffnt:
            QMessageBox.warning(self, "Warning", "No font loaded")
            return
        
        dialog = MappingEditorDialog(self.bffnt, self)
        dialog.mappingChanged.connect(self._on_mapping_changed)
        dialog.exec()
    
    def _update_glyph_width_entry(self, glyph_index: int, left: int = None, 
                                   glyph_width: int = None, char_width: int = None):
        """Update width entry for a specific glyph in the CWDH section."""
        if not self.bffnt:
            return
        
        # Ensure entry exists (creates if missing)
        entry = self.bffnt.ensure_char_width(glyph_index)
        
        if left is not None:
            entry.left = left
        if glyph_width is not None:
            entry.glyph_width = glyph_width
        if char_width is not None:
            entry.char_width = char_width
        
        self.file_modified = True
        self._update_window_title()
    
    def _on_glyph_left_changed(self, value: int):
        """Handle Left value change."""
        if self.selected_glyph_index is not None:
            self._update_glyph_width_entry(self.selected_glyph_index, left=value)
            self.status_bar.showMessage(tr("status.glyph_left_changed", index=self.selected_glyph_index, value=value))
    
    def _on_glyph_width_changed(self, value: int):
        """Handle Width value change."""
        if self.selected_glyph_index is not None:
            self._update_glyph_width_entry(self.selected_glyph_index, glyph_width=value)
            self.status_bar.showMessage(tr("status.glyph_width_changed", index=self.selected_glyph_index, value=value))
    
    def _on_glyph_advance_changed(self, value: int):
        """Handle Advance value change."""
        if self.selected_glyph_index is not None:
            self._update_glyph_width_entry(self.selected_glyph_index, char_width=value)
            self.status_bar.showMessage(tr("status.glyph_advance_changed", index=self.selected_glyph_index, value=value))
    
    def _edit_selected_glyph_mapping(self):
        """Edit the mapping for the currently selected glyph."""
        if not self.bffnt or self.selected_glyph_index is None:
            return
        
        # Find current char code for this glyph
        current_char_code = None
        for code, idx in self.bffnt.char_map.items():
            if idx == self.selected_glyph_index:
                current_char_code = code
                break
        
        dialog = QuickMappingDialog(
            self.selected_glyph_index,
            current_char_code,
            self.bffnt,
            self
        )
        
        if dialog.exec():
            self._on_mapping_changed()
            self._show_glyph_info(self.selected_glyph_index)
    
    def _on_mapping_changed(self):
        """Handle character mapping changes."""
        self.file_modified = True
        self._update_window_title()
        self._update_character_grid()
        self.status_bar.showMessage("✏️ Mapping changed - Save BFFNT to apply")
    
    def _refresh_ui(self):
        """Refresh all UI components after data changes."""
        self._update_info_panel()
        self._update_sheet_viewer()
        self._update_character_grid()
        self._update_text_preview()
    
    def _update_window_title(self):
        """Update window title to show filename and modification status."""
        if self.current_file_path:
            file_name = os.path.basename(self.current_file_path)
            modified_indicator = tr("window.modified_indicator") if self.file_modified else ""
            self.setWindowTitle(tr("window.title_with_file", filename=file_name) + modified_indicator)
        else:
            self.setWindowTitle(tr("window.title"))


def run_app(file_path: str = None):
    """Run the application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    if file_path:
        window.load_font(file_path)
    
    sys.exit(app.exec())
