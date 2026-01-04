"""
Font Viewer Widget - Custom widgets for displaying font sheets and glyphs.
"""

from typing import Dict, List, Optional, Tuple
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QGridLayout, QLineEdit, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRect, QPoint
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor, QFont,
    QPaintEvent, QMouseEvent, QResizeEvent
)
from PIL import Image

from ..core.parser import BFFNTFile, CharWidthEntry


def pil_to_qpixmap(pil_image: Image.Image) -> QPixmap:
    """Convert PIL Image to QPixmap."""
    if pil_image.mode != 'RGBA':
        pil_image = pil_image.convert('RGBA')
    
    data = pil_image.tobytes('raw', 'RGBA')
    qimg = QImage(data, pil_image.width, pil_image.height, 
                  pil_image.width * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg.copy())


class SheetViewer(QWidget):
    """Widget for displaying a font texture sheet with cell grid overlay."""
    
    cellClicked = pyqtSignal(int, int)  # row, column
    cellHovered = pyqtSignal(int, int)  # row, column
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sheet_pixmap: Optional[QPixmap] = None
        self._cached_scaled_pixmap: Optional[QPixmap] = None
        self._cached_zoom: float = 0.0
        self.cell_width = 0
        self.cell_height = 0
        self.cells_per_row = 0
        self.cells_per_column = 0
        self.zoom = 1.0
        self.show_grid = True
        self.hovered_cell: Optional[Tuple[int, int]] = None
        self.selected_cell: Optional[Tuple[int, int]] = None
        
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    
    def set_sheet(self, pixmap: QPixmap, cell_width: int, cell_height: int,
                  cells_per_row: int, cells_per_column: int):
        """Set the texture sheet to display."""
        self.sheet_pixmap = pixmap
        self._cached_scaled_pixmap = None  # Invalidate cache
        self._cached_zoom = 0.0
        self.cell_width = cell_width + 1  # +1 for padding
        self.cell_height = cell_height + 1
        self.cells_per_row = cells_per_row
        self.cells_per_column = cells_per_column
        self.update()
        self.updateGeometry()
    
    def set_zoom(self, zoom: float):
        """Set zoom level."""
        new_zoom = max(0.25, min(4.0, zoom))
        if new_zoom != self.zoom:
            self.zoom = new_zoom
            self._cached_scaled_pixmap = None  # Invalidate cache
            self._cached_zoom = 0.0
            self.update()
            self.updateGeometry()
    
    def set_show_grid(self, show: bool):
        """Toggle grid visibility."""
        self.show_grid = show
        self.update()
    
    def sizeHint(self) -> QSize:
        if self.sheet_pixmap:
            return QSize(
                int(self.sheet_pixmap.width() * self.zoom),
                int(self.sheet_pixmap.height() * self.zoom)
            )
        return QSize(400, 300)
    
    def minimumSizeHint(self) -> QSize:
        return QSize(200, 150)
    
    def _get_cell_at(self, pos: QPoint) -> Optional[Tuple[int, int]]:
        """Get cell (row, column) at mouse position."""
        if not self.sheet_pixmap or self.cell_width == 0:
            return None
        
        x = int(pos.x() / self.zoom)
        y = int(pos.y() / self.zoom)
        
        col = x // self.cell_width
        row = y // self.cell_height
        
        if 0 <= col < self.cells_per_row and 0 <= row < self.cells_per_column:
            return (row, col)
        return None
    
    def mouseMoveEvent(self, event: QMouseEvent):
        cell = self._get_cell_at(event.pos())
        if cell != self.hovered_cell:
            self.hovered_cell = cell
            if cell:
                self.cellHovered.emit(cell[0], cell[1])
            self.update()
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            cell = self._get_cell_at(event.pos())
            if cell:
                self.selected_cell = cell
                self.cellClicked.emit(cell[0], cell[1])
                self.update()
    
    def leaveEvent(self, event):
        self.hovered_cell = None
        self.update()
    
    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fill background
        painter.fillRect(self.rect(), QColor(30, 30, 30))
        
        if self.sheet_pixmap:
            # Use cached scaled pixmap if available
            if self._cached_scaled_pixmap is None or self._cached_zoom != self.zoom:
                scaled_size = QSize(
                    int(self.sheet_pixmap.width() * self.zoom),
                    int(self.sheet_pixmap.height() * self.zoom)
                )
                self._cached_scaled_pixmap = self.sheet_pixmap.scaled(
                    scaled_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._cached_zoom = self.zoom
            
            scaled_pixmap = self._cached_scaled_pixmap
            scaled_size = scaled_pixmap.size()
            painter.drawPixmap(0, 0, scaled_pixmap)
            
            # Draw grid
            if self.show_grid and self.cell_width > 0:
                pen = QPen(QColor(100, 100, 100, 150))
                pen.setWidth(1)
                painter.setPen(pen)
                
                for row in range(self.cells_per_column + 1):
                    y = int(row * self.cell_height * self.zoom)
                    painter.drawLine(0, y, scaled_size.width(), y)
                
                for col in range(self.cells_per_row + 1):
                    x = int(col * self.cell_width * self.zoom)
                    painter.drawLine(x, 0, x, scaled_size.height())
            
            # Draw hovered cell
            if self.hovered_cell:
                row, col = self.hovered_cell
                rect = QRect(
                    int(col * self.cell_width * self.zoom),
                    int(row * self.cell_height * self.zoom),
                    int(self.cell_width * self.zoom),
                    int(self.cell_height * self.zoom)
                )
                painter.fillRect(rect, QColor(0, 255, 255, 50))
                pen = QPen(QColor(0, 255, 255))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawRect(rect)
            
            # Draw selected cell
            if self.selected_cell:
                row, col = self.selected_cell
                rect = QRect(
                    int(col * self.cell_width * self.zoom),
                    int(row * self.cell_height * self.zoom),
                    int(self.cell_width * self.zoom),
                    int(self.cell_height * self.zoom)
                )
                pen = QPen(QColor(255, 200, 0))
                pen.setWidth(3)
                painter.setPen(pen)
                painter.drawRect(rect)


class GlyphCell(QFrame):
    """Individual glyph cell widget."""
    
    clicked = pyqtSignal(int)  # glyph_index
    rightClicked = pyqtSignal(int, int, object)  # glyph_index, char_code, QPoint (global pos)
    
    def __init__(self, glyph_index: int, pixmap: QPixmap, 
                 char_code: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.glyph_index = glyph_index
        self.char_code = char_code
        self.pixmap = pixmap
        
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.setLineWidth(1)
        self.setFixedSize(64, 80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._hovered = False
    
    def enterEvent(self, event):
        self._hovered = True
        self.update()
    
    def leaveEvent(self, event):
        self._hovered = False
        self.update()
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.glyph_index)
        elif event.button() == Qt.MouseButton.RightButton:
            self.rightClicked.emit(self.glyph_index, self.char_code or 0, event.globalPosition().toPoint())
    
    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
        painter = QPainter(self)
        
        # Background
        if self._hovered:
            painter.fillRect(self.rect(), QColor(60, 60, 80))
        else:
            painter.fillRect(self.rect(), QColor(40, 40, 50))
        
        # Draw glyph centered and scaled to fit
        if self.pixmap and not self.pixmap.isNull():
            # Available space for glyph (leave room for text at bottom)
            available_width = self.width() - 4
            available_height = self.height() - 28  # Leave space for text
            
            # Scale pixmap to fit while maintaining aspect ratio
            scaled = self.pixmap.scaled(
                available_width, available_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            x = (self.width() - scaled.width()) // 2
            y = 2 + (available_height - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        
        # Draw index text
        painter.setPen(QColor(180, 180, 180))
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        
        text = f"#{self.glyph_index}"
        if self.char_code and self.char_code < 0xFFFF:
            try:
                char = chr(self.char_code)
                if char.isprintable():
                    text = f"{char}\n#{self.glyph_index}"
            except:
                pass
        
        text_rect = QRect(0, self.height() - 24, self.width(), 20)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)


class CharacterGrid(QScrollArea):
    """Scrollable grid of character glyphs."""
    
    glyphSelected = pyqtSignal(int, int)  # glyph_index, char_code
    glyphRightClicked = pyqtSignal(int, int, object)  # glyph_index, char_code, QPoint (global pos)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.container = QWidget()
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setSpacing(4)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        # Don't allow columns to stretch - keep fixed cell sizes
        self.grid_layout.setSizeConstraint(QGridLayout.SizeConstraint.SetMinAndMaxSize)
        
        self.setWidget(self.container)
        self.cells: List[GlyphCell] = []
        self.columns = 8
        self._pending_reorganize = False
    
    def set_glyphs(self, glyphs: List[QPixmap], char_map: Dict[int, int]):
        """Set glyphs to display."""
        # Clear existing
        for cell in self.cells:
            cell.deleteLater()
        self.cells.clear()
        
        # Clear layout
        while self.grid_layout.count():
            self.grid_layout.takeAt(0)
        
        # Reverse char_map for lookup
        glyph_to_char = {v: k for k, v in char_map.items()}
        
        # Calculate columns based on current viewport
        cell_width = 68
        viewport_width = self.viewport().width()
        if viewport_width > 100:
            self.columns = max(4, viewport_width // cell_width)
        
        # Add new cells
        for idx, pixmap in enumerate(glyphs):
            char_code = glyph_to_char.get(idx)
            cell = GlyphCell(idx, pixmap, char_code, self.container)
            cell.clicked.connect(lambda i, c=char_code: self.glyphSelected.emit(i, c or 0))
            cell.rightClicked.connect(self._on_cell_right_clicked)
            
            row = idx // self.columns
            col = idx % self.columns
            self.grid_layout.addWidget(cell, row, col)
            self.cells.append(cell)
        
        # Schedule a reorganize after layout settles
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self._deferred_reorganize)
    
    def _on_cell_right_clicked(self, glyph_index: int, char_code: int, pos):
        """Handle cell right-click and propagate signal."""
        self.glyphRightClicked.emit(glyph_index, char_code, pos)
    
    def _deferred_reorganize(self):
        """Reorganize grid after layout has settled."""
        if self.cells:
            cell_width = 68
            new_columns = max(4, self.viewport().width() // cell_width)
            if new_columns != self.columns:
                self.columns = new_columns
                self._reorganize_grid()
    
    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if not self.cells:
            return
        
        # Adjust columns based on width
        cell_width = 68
        new_columns = max(4, self.viewport().width() // cell_width)
        
        if new_columns != self.columns:
            self.columns = new_columns
            self._reorganize_grid()
    
    def _reorganize_grid(self):
        """Reorganize cells in grid after column change."""
        if not self.cells:
            return
        
        # Block signals to prevent recursive updates
        self.grid_layout.setEnabled(False)
        
        # Remove all widgets from layout first (without deleting them)
        for cell in self.cells:
            self.grid_layout.removeWidget(cell)
        
        # Re-add all cells in new grid positions
        for idx, cell in enumerate(self.cells):
            row = idx // self.columns
            col = idx % self.columns
            self.grid_layout.addWidget(cell, row, col)
        
        self.grid_layout.setEnabled(True)
        
        # Force update layout
        self.container.adjustSize()
        self.container.updateGeometry()


class TextPreview(QWidget):
    """Widget for previewing text rendered with the font."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bffnt: Optional[BFFNTFile] = None
        self.glyphs: List[QPixmap] = []
        self.preview_text = ""
        self.scale = 1.0
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Text input
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Text:"))
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Type text to preview...")
        self.text_input.textChanged.connect(self._on_text_changed)
        input_layout.addWidget(self.text_input)
        layout.addLayout(input_layout)
        
        # Preview area
        self.preview_area = PreviewCanvas(self)
        self.preview_area.setMinimumHeight(200)
        layout.addWidget(self.preview_area, 1)
    
    def set_font(self, bffnt: BFFNTFile, glyphs: List[QPixmap]):
        """Set the font for preview."""
        self.bffnt = bffnt
        self.glyphs = glyphs
        self.preview_area.set_font(bffnt, glyphs)
        self._update_preview()
    
    def _on_text_changed(self, text: str):
        self.preview_text = text
        self._update_preview()
    
    def _update_preview(self):
        self.preview_area.set_text(self.preview_text)


class PreviewCanvas(QWidget):
    """Canvas for rendering text preview."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bffnt: Optional[BFFNTFile] = None
        self.glyphs: List[QPixmap] = []
        self.text = ""
        self.scale = 1.5
        self._scaled_glyphs_cache: Dict[int, QPixmap] = {}  # Cache for scaled glyphs
        self._cached_scale = 0.0
        
        self.setMinimumHeight(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    
    def set_font(self, bffnt: BFFNTFile, glyphs: List[QPixmap]):
        self.bffnt = bffnt
        self.glyphs = glyphs
        self._scaled_glyphs_cache.clear()  # Clear cache when font changes
        self._cached_scale = 0.0
        self.update()
    
    def set_text(self, text: str):
        self.text = text
        self.update()
    
    def set_scale(self, scale: float):
        new_scale = max(0.5, min(4.0, scale))
        if new_scale != self.scale:
            self.scale = new_scale
            self._scaled_glyphs_cache.clear()  # Clear cache when scale changes
            self._cached_scale = 0.0
            self.update()
    
    def _get_scaled_glyph(self, glyph_index: int) -> QPixmap:
        """Get a scaled glyph from cache or create it."""
        if self._cached_scale != self.scale:
            self._scaled_glyphs_cache.clear()
            self._cached_scale = self.scale
        
        if glyph_index not in self._scaled_glyphs_cache:
            pixmap = self.glyphs[glyph_index]
            scaled = pixmap.scaled(
                int(pixmap.width() * self.scale),
                int(pixmap.height() * self.scale),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self._scaled_glyphs_cache[glyph_index] = scaled
        
        return self._scaled_glyphs_cache[glyph_index]
    
    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor(20, 20, 25))
        
        if not self.bffnt or not self.glyphs or not self.text:
            # Draw placeholder text
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 
                           "Type text above to preview")
            return
        
        # Set composition mode for proper blending with outlined fonts
        # Lighten mode: uses brighter pixel, making white outlines blend smoothly
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Lighten)
        
        # Render text
        x = 20
        y = 30
        line_height = int(self.bffnt.finf.line_feed * self.scale)
        
        for char in self.text:
            if char == '\n':
                x = 20
                y += line_height
                continue
            
            char_code = ord(char)
            glyph_index = self.bffnt.get_glyph_index(char_code)
            
            if glyph_index == 0xFFFF or glyph_index >= len(self.glyphs):
                # Use default/space width for unmapped characters
                x += int(self.bffnt.finf.default_char_width * self.scale)
                continue
            
            width_info = self.bffnt.get_char_width(glyph_index)
            
            # Get scaled glyph from cache
            scaled_pixmap = self._get_scaled_glyph(glyph_index)
            
            # Get spacing info from CWDH
            if width_info and width_info.char_width > 0:
                left = int(width_info.left * self.scale)
                char_width = int(width_info.char_width * self.scale)
            else:
                # Fallback: use actual glyph width
                left = 0
                char_width = scaled_pixmap.width()
            
            painter.drawPixmap(x + left, y, scaled_pixmap)
            x += char_width
