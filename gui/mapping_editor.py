"""
Character Mapping Editor - Dialog for editing character-to-glyph mappings.
"""

from typing import Dict, Optional, Callable
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QSpinBox, QHeaderView, QMessageBox,
    QGroupBox, QFormLayout, QWidget, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont

from ..bffnt_parser import BFFNTFile, CharWidthEntry


class MappingEditorDialog(QDialog):
    """Dialog for editing character mappings."""
    
    mappingChanged = pyqtSignal()  # Emitted when mappings are modified
    
    def __init__(self, bffnt: BFFNTFile, parent=None):
        super().__init__(parent)
        self.bffnt = bffnt
        self.modified_mappings: Dict[int, int] = {}  # char_code -> glyph_index changes
        self.modified_widths: Dict[int, CharWidthEntry] = {}  # glyph_index -> width info changes
        
        self._setup_ui()
        self._apply_dark_theme()
        self._populate_table()
    
    def _setup_ui(self):
        self.setWindowTitle("Character Mapping Editor")
        self.setMinimumSize(700, 500)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Instructions
        info_label = QLabel(
            "Edit character mappings below. Double-click a cell to modify.\n"
            "Char Code column shows the Unicode code point (decimal).\n"
            "Glyph Index shows which glyph texture is displayed for that character."
        )
        info_label.setStyleSheet("color: #a6adc8; padding: 8px;")
        layout.addWidget(info_label)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Char Code", "Character", "Glyph Index", "Left", "Width"
        ])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 80)
        
        self.table.cellChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table)
        
        # Edit single glyph section
        edit_group = QGroupBox("Edit Selected Glyph Mapping")
        edit_layout = QHBoxLayout(edit_group)
        
        edit_layout.addWidget(QLabel("Glyph Index:"))
        self.glyph_index_spin = QSpinBox()
        self.glyph_index_spin.setRange(0, 65535)
        edit_layout.addWidget(self.glyph_index_spin)
        
        edit_layout.addWidget(QLabel("New Char Code:"))
        self.new_char_code = QLineEdit()
        self.new_char_code.setPlaceholderText("e.g. 65 or 'A'")
        self.new_char_code.setMaximumWidth(150)
        edit_layout.addWidget(self.new_char_code)
        
        apply_btn = QPushButton("Apply Change")
        apply_btn.clicked.connect(self._apply_single_change)
        edit_layout.addWidget(apply_btn)
        
        edit_layout.addStretch()
        layout.addWidget(edit_group)
        
        # Add/Remove mapping section
        add_group = QGroupBox("Add New Mapping")
        add_layout = QHBoxLayout(add_group)
        
        add_layout.addWidget(QLabel("Char Code:"))
        self.add_char_code = QLineEdit()
        self.add_char_code.setPlaceholderText("e.g. 65 or 'A'")
        self.add_char_code.setMaximumWidth(120)
        add_layout.addWidget(self.add_char_code)
        
        add_layout.addWidget(QLabel("→ Glyph Index:"))
        self.add_glyph_index = QSpinBox()
        self.add_glyph_index.setRange(0, 65535)
        add_layout.addWidget(self.add_glyph_index)
        
        add_btn = QPushButton("Add Mapping")
        add_btn.clicked.connect(self._add_mapping)
        add_layout.addWidget(add_btn)
        
        add_layout.addStretch()
        layout.addWidget(add_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self._save_changes)
        button_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QTableWidget {
                background-color: #181825;
                color: #cdd6f4;
                gridline-color: #313244;
                border: 1px solid #313244;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #45475a;
            }
            QHeaderView::section {
                background-color: #313244;
                color: #cdd6f4;
                padding: 6px;
                border: none;
                border-right: 1px solid #45475a;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #313244;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #45475a;
                color: #cdd6f4;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
            QPushButton:pressed {
                background-color: #313244;
            }
            QLineEdit, QSpinBox {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QLineEdit:focus, QSpinBox:focus {
                border-color: #89b4fa;
            }
            QLabel {
                color: #cdd6f4;
            }
        """)
    
    def _populate_table(self):
        """Populate the table with current mappings."""
        self.table.blockSignals(True)
        
        # Sort mappings by char code
        sorted_mappings = sorted(self.bffnt.char_map.items())
        
        self.table.setRowCount(len(sorted_mappings))
        
        for row, (char_code, glyph_index) in enumerate(sorted_mappings):
            # Char code
            code_item = QTableWidgetItem(str(char_code))
            code_item.setData(Qt.ItemDataRole.UserRole, char_code)
            code_item.setFlags(code_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, code_item)
            
            # Character display
            try:
                char = chr(char_code)
                if char.isprintable():
                    char_display = f"'{char}' (U+{char_code:04X})"
                else:
                    char_display = f"U+{char_code:04X}"
            except:
                char_display = f"U+{char_code:04X}"
            
            char_item = QTableWidgetItem(char_display)
            char_item.setFlags(char_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, char_item)
            
            # Glyph index (editable)
            glyph_item = QTableWidgetItem(str(glyph_index))
            self.table.setItem(row, 2, glyph_item)
            
            # Width info
            width_info = self.bffnt.get_char_width(glyph_index)
            if width_info:
                left_item = QTableWidgetItem(str(width_info.left))
                width_item = QTableWidgetItem(str(width_info.glyph_width))
            else:
                left_item = QTableWidgetItem("-")
                width_item = QTableWidgetItem("-")
            
            left_item.setFlags(left_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            width_item.setFlags(width_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, left_item)
            self.table.setItem(row, 4, width_item)
        
        self.table.blockSignals(False)
    
    def _on_cell_changed(self, row: int, col: int):
        """Handle cell edit."""
        if col == 2:  # Glyph index column
            char_code = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            try:
                new_glyph_index = int(self.table.item(row, 2).text())
                self.modified_mappings[char_code] = new_glyph_index
            except ValueError:
                pass
    
    def _parse_char_code(self, text: str) -> Optional[int]:
        """Parse a character code from text (number or 'char')."""
        text = text.strip()
        
        # Check if it's a quoted character
        if text.startswith("'") and text.endswith("'") and len(text) >= 3:
            return ord(text[1])
        
        # Try parsing as number
        try:
            if text.startswith("0x"):
                return int(text, 16)
            return int(text)
        except ValueError:
            return None
    
    def _apply_single_change(self):
        """Apply a single glyph mapping change."""
        glyph_index = self.glyph_index_spin.value()
        new_code = self._parse_char_code(self.new_char_code.text())
        
        if new_code is None:
            QMessageBox.warning(self, "Invalid Input", 
                "Please enter a valid character code (number or 'char')")
            return
        
        # Find current char code mapped to this glyph
        old_code = None
        for code, idx in self.bffnt.char_map.items():
            if idx == glyph_index:
                old_code = code
                break
        
        if old_code is not None:
            # Remove old mapping
            self.modified_mappings[old_code] = -1  # Mark for removal
        
        # Add new mapping
        self.modified_mappings[new_code] = glyph_index
        
        # Refresh table
        self._populate_table()
        
        QMessageBox.information(self, "Success", 
            f"Mapped glyph {glyph_index} to character code {new_code} ('{chr(new_code)}' if printable)")
    
    def _add_mapping(self):
        """Add a new character mapping."""
        char_code = self._parse_char_code(self.add_char_code.text())
        glyph_index = self.add_glyph_index.value()
        
        if char_code is None:
            QMessageBox.warning(self, "Invalid Input",
                "Please enter a valid character code")
            return
        
        self.modified_mappings[char_code] = glyph_index
        
        # Update bffnt for display (not saved to file yet)
        self.bffnt.char_map[char_code] = glyph_index
        
        self._populate_table()
        self.add_char_code.clear()
    
    def _save_changes(self):
        """Apply all changes to the BFFNT."""
        # Apply modified mappings
        for char_code, glyph_index in self.modified_mappings.items():
            if glyph_index == -1:
                # Remove mapping
                if char_code in self.bffnt.char_map:
                    del self.bffnt.char_map[char_code]
            else:
                self.bffnt.char_map[char_code] = glyph_index
        
        self.mappingChanged.emit()
        self.accept()
    
    def get_modified_bffnt(self) -> BFFNTFile:
        """Get the modified BFFNT."""
        return self.bffnt


class QuickMappingDialog(QDialog):
    """Quick dialog for editing a single glyph's mapping."""
    
    def __init__(self, glyph_index: int, current_char_code: Optional[int], 
                 bffnt: BFFNTFile, parent=None):
        super().__init__(parent)
        self.glyph_index = glyph_index
        self.current_char_code = current_char_code
        self.bffnt = bffnt
        self.new_char_code: Optional[int] = None
        
        self._setup_ui()
        self._apply_dark_theme()
    
    def _setup_ui(self):
        self.setWindowTitle(f"Edit Mapping - Glyph #{self.glyph_index}")
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout(self)
        
        # Current mapping
        info_group = QGroupBox("Current Mapping")
        info_layout = QFormLayout(info_group)
        
        info_layout.addRow("Glyph Index:", QLabel(str(self.glyph_index)))
        
        if self.current_char_code is not None:
            try:
                char = chr(self.current_char_code)
                if char.isprintable():
                    current_text = f"'{char}' (U+{self.current_char_code:04X})"
                else:
                    current_text = f"U+{self.current_char_code:04X}"
            except:
                current_text = f"U+{self.current_char_code:04X}"
        else:
            current_text = "(unmapped)"
        
        info_layout.addRow("Current Character:", QLabel(current_text))
        layout.addWidget(info_group)
        
        # New mapping
        edit_group = QGroupBox("New Mapping")
        edit_layout = QFormLayout(edit_group)
        
        self.char_input = QLineEdit()
        self.char_input.setPlaceholderText("e.g. 65 or 'A' or 0x41")
        edit_layout.addRow("New Character:", self.char_input)
        
        layout.addWidget(edit_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #313244;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #45475a;
                color: #cdd6f4;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
            QLineEdit {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 6px;
            }
            QLabel {
                color: #cdd6f4;
            }
        """)
    
    def _parse_char_code(self, text: str) -> Optional[int]:
        """Parse a character code from text."""
        text = text.strip()
        
        if text.startswith("'") and text.endswith("'") and len(text) >= 3:
            return ord(text[1])
        
        try:
            if text.startswith("0x"):
                return int(text, 16)
            return int(text)
        except ValueError:
            return None
    
    def _save(self):
        """Save the new mapping."""
        text = self.char_input.text().strip()
        
        if not text:
            QMessageBox.warning(self, "Invalid Input", "Please enter a character code")
            return
        
        new_code = self._parse_char_code(text)
        if new_code is None:
            QMessageBox.warning(self, "Invalid Input",
                "Please enter a valid character code (number, 'char', or 0xHex)")
            return
        
        self.new_char_code = new_code
        
        # Apply the change to bffnt
        # Remove old mapping if exists
        if self.current_char_code is not None:
            if self.current_char_code in self.bffnt.char_map:
                del self.bffnt.char_map[self.current_char_code]
        
        # Add new mapping
        self.bffnt.char_map[new_code] = self.glyph_index
        
        self.accept()
    
    def get_new_char_code(self) -> Optional[int]:
        """Get the new character code after dialog closes."""
        return self.new_char_code
