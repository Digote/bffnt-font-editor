"""
Export/Import Manager - Handles exporting and importing BFFNT font data.

Exports font sheets as PNG files with a metadata JSON containing
character mappings and font information.
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from PIL import Image

from .bffnt_parser import (
    BFFNTFile, TGLP, CWDH, CMAP, CMAPType, CMAPDirect, CMAPTable, CMAPScan,
    CharWidthEntry, TextureFormat, PlatformType
)


@dataclass
class ExportMetadata:
    """Metadata exported alongside texture sheets."""
    # Font info
    version: str
    platform: str
    font_width: int
    font_height: int
    ascent: int
    line_feed: int
    char_encoding: int
    
    # Texture info
    sheet_count: int
    sheet_width: int
    sheet_height: int
    cell_width: int
    cell_height: int
    cells_per_row: int
    cells_per_column: int
    texture_format: str
    
    # Character mappings: char_code -> glyph_index
    # Stored as string keys for JSON compatibility
    char_map: Dict[str, int]
    
    # Reverse mapping for convenience: glyph_index -> char_code
    glyph_to_char: Dict[str, int]
    
    # Width info for each glyph: glyph_index -> {left, glyph_width, char_width}
    glyph_widths: Dict[str, Dict[str, int]]


def export_font(bffnt: BFFNTFile, sheets: List[Image.Image], output_dir: str,
                export_grid_guide: bool = False, export_grid_template: bool = False) -> str:
    """
    Export a BFFNT font to PNG sheets and metadata JSON.
    
    Args:
        bffnt: Parsed BFFNT file
        sheets: Decoded texture sheets as PIL Images
        output_dir: Directory to save exported files
        export_grid_guide: If True, exports sheets with grid overlay for reference
        export_grid_template: If True, exports a transparent grid template
        
    Returns:
        Path to the metadata JSON file
    """
    os.makedirs(output_dir, exist_ok=True)
    
    tglp = bffnt.tglp
    cell_width = tglp.cell_width + 1  # +1 for padding
    cell_height = tglp.cell_height + 1
    
    # Export each sheet as PNG
    for i, sheet in enumerate(sheets):
        sheet_path = os.path.join(output_dir, f"sheet_{i}.png")
        sheet.save(sheet_path, "PNG")
        
        # Export grid guide (sheet with grid overlay)
        if export_grid_guide:
            guide = create_grid_overlay(sheet, cell_width, cell_height, 
                                        tglp.cells_per_row, tglp.cells_per_column)
            guide_path = os.path.join(output_dir, f"sheet_{i}_guide.png")
            guide.save(guide_path, "PNG")
    
    # Export grid template (transparent with only grid lines)
    if export_grid_template:
        template = create_grid_template(
            tglp.sheet_width, tglp.sheet_height,
            cell_width, cell_height,
            tglp.cells_per_row, tglp.cells_per_column
        )
        template_path = os.path.join(output_dir, "grid_template.png")
        template.save(template_path, "PNG")
    
    # Build reverse mapping (glyph_index -> char_code)
    glyph_to_char = {}
    for char_code, glyph_index in bffnt.char_map.items():
        # Use first mapping if multiple chars map to same glyph
        if str(glyph_index) not in glyph_to_char:
            glyph_to_char[str(glyph_index)] = char_code
    
    # Build width info
    glyph_widths = {}
    for cwdh in bffnt.cwdh_list:
        for i, entry in enumerate(cwdh.entries):
            glyph_index = cwdh.first_index + i
            glyph_widths[str(glyph_index)] = {
                "left": entry.left,
                "glyph_width": entry.glyph_width,
                "char_width": entry.char_width
            }
    
    # Create metadata
    metadata = ExportMetadata(
        version=f"0x{bffnt.header.version:08X}",
        platform=bffnt.header.platform.name,
        font_width=bffnt.finf.width,
        font_height=bffnt.finf.height,
        ascent=bffnt.finf.ascent,
        line_feed=bffnt.finf.line_feed,
        char_encoding=bffnt.finf.char_encoding,
        
        sheet_count=bffnt.tglp.sheet_count,
        sheet_width=bffnt.tglp.sheet_width,
        sheet_height=bffnt.tglp.sheet_height,
        cell_width=bffnt.tglp.cell_width,
        cell_height=bffnt.tglp.cell_height,
        cells_per_row=bffnt.tglp.cells_per_row,
        cells_per_column=bffnt.tglp.cells_per_column,
        texture_format=bffnt.tglp.texture_format.name,
        
        char_map={str(k): v for k, v in bffnt.char_map.items()},
        glyph_to_char=glyph_to_char,
        glyph_widths=glyph_widths
    )
    
    # Save metadata as JSON
    metadata_path = os.path.join(output_dir, "metadata.json")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(asdict(metadata), f, indent=2, ensure_ascii=False)
    
    return metadata_path


def create_grid_template(width: int, height: int, cell_width: int, cell_height: int,
                         cells_per_row: int, cells_per_column: int,
                         line_color: tuple = (255, 0, 255, 200)) -> Image.Image:
    """
    Create a transparent grid template for use as an overlay layer.
    
    Args:
        width: Image width
        height: Image height
        cell_width: Width of each cell (including padding)
        cell_height: Height of each cell (including padding)
        cells_per_row: Number of cells per row
        cells_per_column: Number of cells per column
        line_color: RGBA color for grid lines (default: magenta with transparency)
        
    Returns:
        Transparent PNG with grid lines
    """
    from PIL import ImageDraw
    
    # Create transparent image
    template = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(template)
    
    # Draw horizontal lines
    for row in range(cells_per_column + 1):
        y = row * cell_height
        draw.line([(0, y), (width, y)], fill=line_color, width=1)
    
    # Draw vertical lines
    for col in range(cells_per_row + 1):
        x = col * cell_width
        draw.line([(x, 0), (x, height)], fill=line_color, width=1)
    
    # Draw cell numbers in each cell (helpful for reference)
    try:
        from PIL import ImageFont
        font = ImageFont.load_default()
    except:
        font = None
    
    glyph_index = 0
    for row in range(cells_per_column):
        for col in range(cells_per_row):
            x = col * cell_width + 2
            y = row * cell_height + 2
            # Draw glyph index number
            if font:
                draw.text((x, y), f"#{glyph_index}", fill=(255, 255, 0, 180), font=font)
            glyph_index += 1
    
    return template


def create_grid_overlay(sheet: Image.Image, cell_width: int, cell_height: int,
                        cells_per_row: int, cells_per_column: int,
                        line_color: tuple = (255, 0, 255, 200)) -> Image.Image:
    """
    Create a copy of a sheet with grid overlay for reference.
    
    Args:
        sheet: Original texture sheet
        cell_width: Width of each cell (including padding)
        cell_height: Height of each cell (including padding)
        cells_per_row: Number of cells per row
        cells_per_column: Number of cells per column
        line_color: RGBA color for grid lines
        
    Returns:
        Sheet with grid overlay
    """
    from PIL import ImageDraw
    
    # Create copy and ensure RGBA
    overlay = sheet.copy()
    if overlay.mode != 'RGBA':
        overlay = overlay.convert('RGBA')
    
    # Create grid template and composite
    grid = create_grid_template(
        overlay.width, overlay.height,
        cell_width, cell_height,
        cells_per_row, cells_per_column,
        line_color
    )
    
    # Composite grid over sheet
    result = Image.alpha_composite(overlay, grid)
    return result


def load_export_metadata(metadata_path: str) -> ExportMetadata:
    """
    Load export metadata from JSON file.
    
    Args:
        metadata_path: Path to metadata.json
        
    Returns:
        ExportMetadata object
    """
    with open(metadata_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return ExportMetadata(
        version=data['version'],
        platform=data['platform'],
        font_width=data['font_width'],
        font_height=data['font_height'],
        ascent=data['ascent'],
        line_feed=data['line_feed'],
        char_encoding=data['char_encoding'],
        
        sheet_count=data['sheet_count'],
        sheet_width=data['sheet_width'],
        sheet_height=data['sheet_height'],
        cell_width=data['cell_width'],
        cell_height=data['cell_height'],
        cells_per_row=data['cells_per_row'],
        cells_per_column=data['cells_per_column'],
        texture_format=data['texture_format'],
        
        char_map=data['char_map'],
        glyph_to_char=data['glyph_to_char'],
        glyph_widths=data['glyph_widths']
    )


def import_sheets(input_dir: str) -> tuple[List[Image.Image], Optional[ExportMetadata]]:
    """
    Import texture sheets and metadata from an export directory.
    
    Args:
        input_dir: Directory containing sheet_*.png and metadata.json
        
    Returns:
        Tuple of (list of sheet images, metadata or None)
    """
    sheets = []
    
    # Load sheets in order
    i = 0
    while True:
        sheet_path = os.path.join(input_dir, f"sheet_{i}.png")
        if not os.path.exists(sheet_path):
            break
        
        sheet = Image.open(sheet_path).convert('RGBA')
        sheets.append(sheet)
        i += 1
    
    # Try to load metadata
    metadata = None
    metadata_path = os.path.join(input_dir, "metadata.json")
    if os.path.exists(metadata_path):
        try:
            metadata = load_export_metadata(metadata_path)
        except Exception as e:
            print(f"Warning: Failed to load metadata: {e}")
    
    return sheets, metadata


def update_bffnt_char_map(bffnt: BFFNTFile, new_char_map: Dict[int, int]) -> None:
    """
    Update the character mapping in a BFFNT file.
    
    This modifies the in-memory BFFNT structure. The changes need to be
    written to file separately using bffnt_writer.
    
    Args:
        bffnt: BFFNT file to modify
        new_char_map: New character code to glyph index mapping
    """
    # Update the main char_map
    bffnt.char_map = dict(new_char_map)
    
    # Note: The CMAP sections would need to be regenerated to reflect
    # the new mappings. For simplicity, we convert all mappings to SCAN type
    # which is the most flexible.
    
    # This is a simplified implementation - a full implementation would
    # need to properly reconstruct CMAP sections based on the mapping ranges


def update_bffnt_glyph_width(bffnt: BFFNTFile, glyph_index: int, 
                              left: int, glyph_width: int, char_width: int) -> bool:
    """
    Update the width information for a specific glyph.
    
    Args:
        bffnt: BFFNT file to modify
        glyph_index: Index of the glyph to modify
        left: Left offset
        glyph_width: Width of the glyph
        char_width: Total character width (advance)
        
    Returns:
        True if successful, False if glyph not found
    """
    for cwdh in bffnt.cwdh_list:
        if cwdh.first_index <= glyph_index <= cwdh.last_index:
            local_index = glyph_index - cwdh.first_index
            if local_index < len(cwdh.entries):
                cwdh.entries[local_index] = CharWidthEntry(left, glyph_width, char_width)
                return True
    return False


def apply_imported_sheets(bffnt: BFFNTFile, sheets: List[Image.Image]) -> bytes:
    """
    Apply imported sheets to a BFFNT file and return modified BNTX data.
    
    This function preserves the original BNTX structure (header, metadata, and
    relocation table _RLT) and only replaces the raw texture data. This ensures
    compatibility with the game, which expects a valid BNTX structure.
    
    Args:
        bffnt: Original BFFNT file
        sheets: New texture sheets
        
    Returns:
        New BNTX texture data to replace in BFFNT
    """
    import struct
    from .texture_encoder import encode_rgba_to_bc4, swizzle_block_linear, calculate_block_height, div_round_up
    from PIL import Image
    
    # Get the original BNTX data
    original_bntx = b''.join(bffnt.tglp.sheet_data)
    
    # Check if it's a valid BNTX
    if original_bntx[:4] != b'BNTX':
        # Fall back to full rebuild if not a valid BNTX
        from .texture_encoder import encode_sheets_for_bffnt
        format_code = 0x1D01  # BC4 by default
        bntx_data, sheet_size = encode_sheets_for_bffnt(sheets, format_code)
        return bntx_data
    
    # Find the texture data region in the original BNTX
    brtd_offset = original_bntx.find(b'BRTD')
    if brtd_offset < 0:
        # No BRTD section, fall back to full rebuild
        from .texture_encoder import encode_sheets_for_bffnt
        format_code = 0x1D01
        bntx_data, sheet_size = encode_sheets_for_bffnt(sheets, format_code)
        return bntx_data
    
    # BRTD header is 16 bytes, texture data follows
    data_start = brtd_offset + 16
    
    # Get file size from BNTX header at offset 0x18
    # This is the size of the BNTX without the _RLT relocation table
    # _RLT follows immediately after this
    file_size = struct.unpack_from('<I', original_bntx, 0x18)[0]
    data_end = file_size  # Texture data ends where _RLT begins
    
    # Sanity check: file_size should be less than total size
    if file_size >= len(original_bntx) or file_size <= data_start:
        # Invalid file_size, use full length
        data_end = len(original_bntx)
    
    original_tex_size = data_end - data_start
    expected_per_sheet = original_tex_size // len(sheets)
    
    # Encode each sheet
    encoded_sheets = []
    for sheet in sheets:
        # Flip Y axis (Switch stores textures upside down)
        flipped = sheet.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        
        # Encode to BC4
        bc4_data = encode_rgba_to_bc4(flipped)
        
        # Swizzle with block-linear layout
        width, height = sheet.size
        bpp = 8  # BC4 = 8 bytes per 4x4 block
        blk_w, blk_h = 4, 4
        
        swizzled = swizzle_block_linear(width, height, blk_w, blk_h, bpp, bc4_data)
        
        # Pad or truncate to match expected size
        if len(swizzled) < expected_per_sheet:
            swizzled = swizzled + bytes(expected_per_sheet - len(swizzled))
        elif len(swizzled) > expected_per_sheet:
            swizzled = swizzled[:expected_per_sheet]
        
        encoded_sheets.append(swizzled)
    
    # Combine encoded sheets
    new_tex_data = b''.join(encoded_sheets)
    
    # Ensure we have exactly the right size
    if len(new_tex_data) < original_tex_size:
        new_tex_data = new_tex_data + bytes(original_tex_size - len(new_tex_data))
    elif len(new_tex_data) > original_tex_size:
        new_tex_data = new_tex_data[:original_tex_size]
    
    # Build the new BNTX by preserving header and _RLT, replacing only texture data
    result = bytearray(original_bntx)
    result[data_start:data_end] = new_tex_data
    
    return bytes(result)
