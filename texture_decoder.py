"""
Texture Decoder - Decodes font texture sheets from BFFNT files.

For Nintendo Switch (NX) platform, BFFNT files contain embedded BNTX textures.
"""

import struct
from dataclasses import dataclass
from typing import List, Tuple
from PIL import Image

# Try to import numpy for faster processing
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from .bffnt_parser import BFFNTFile, TGLP, TextureFormat, PlatformType


# ============================================================================
# BNTX Parser (embedded in BFFNT for Switch)
# ============================================================================

@dataclass
class BNTXTexture:
    """Parsed texture info from BNTX file."""
    name: str
    width: int
    height: int
    format: int
    tile_mode: int
    size_range: int  # Block height log2
    alignment: int
    num_mips: int
    data: bytes
    array_count: int = 1
    image_size: int = 0  # Size of one sheet in bytes


def parse_bntx(data: bytes) -> List[BNTXTexture]:
    """
    Parse a BNTX file and extract texture information.
    
    BNTX is Nintendo's binary texture format for Switch.
    """
    if data[:4] != b'BNTX':
        raise ValueError("Not a valid BNTX file")
    
    # Determine endianness
    bom = struct.unpack_from('>H', data, 0xC)[0]
    e = '<' if bom == 0xFFFE else '>'
    
    # Find BRTI section (texture info)
    brti_offset = data.find(b'BRTI')
    if brti_offset < 0:
        raise ValueError("BRTI section not found in BNTX")
    
    brti = data[brti_offset:]
    
    # Parse BRTI fields (corrected offsets based on analysis)
    # 0x04: Section size
    # 0x10: Flags (1 byte) + Dims (1 byte)
    # 0x12: Tile Mode (2 bytes)
    # 0x14: Swizzle (2 bytes)
    # 0x16: NumMips (2 bytes)
    # 0x18: NumSamples (4 bytes) 
    # 0x1C: Format (4 bytes) - 0x1D01 = BC4 UNORM
    # 0x20: GPU Access (4 bytes)
    # 0x24: Width (4 bytes)
    # 0x28: Height (4 bytes)
    # 0x2C: Depth (4 bytes)
    # 0x30: Array Count (4 bytes)
    # 0x38: Texture Layout (4 bytes) - contains block height in bits 0-2
    # 0x50: Image Size (4 bytes)
    # 0x54: Alignment (4 bytes)
    
    tile_mode = struct.unpack_from(e + 'H', brti, 0x12)[0]
    num_mips = struct.unpack_from(e + 'H', brti, 0x16)[0]
    format_code = struct.unpack_from(e + 'I', brti, 0x1C)[0]
    
    width = struct.unpack_from(e + 'I', brti, 0x24)[0]
    height = struct.unpack_from(e + 'I', brti, 0x28)[0]
    depth = struct.unpack_from(e + 'I', brti, 0x2C)[0]
    array_count = struct.unpack_from(e + 'I', brti, 0x30)[0]
    
    tex_layout = struct.unpack_from(e + 'I', brti, 0x38)[0]
    size_range = tex_layout & 0x7
    
    image_size = struct.unpack_from(e + 'I', brti, 0x50)[0]
    alignment = struct.unpack_from(e + 'I', brti, 0x54)[0]
    
    # Get name from string table (if available)
    # Name pointer is at 0x60 in BRTI, contains offset relative to BNTX start
    name_offset = struct.unpack_from(e + 'q', brti, 0x60)[0]
    name = "texture"
    if name_offset > 0 and name_offset < len(data):
        name_len = struct.unpack_from(e + 'H', data, name_offset)[0]
        name = data[name_offset + 2:name_offset + 2 + name_len].decode('utf-8', errors='ignore').strip('\0')
    
    # Find texture data - typically starts at 0x1000 (page aligned)
    # Or check for BRTD section which marks the data block
    brtd_offset = data.find(b'BRTD')
    if brtd_offset >= 0:
        # BRTD header is 16 bytes, data follows
        data_start = brtd_offset + 16
    else:
        # Fallback: data starts at 0x1000
        data_start = 0x1000
    
    # For texture arrays, we need to read image_size * array_count bytes
    total_data_size = image_size * array_count
    tex_data = data[data_start:data_start + total_data_size]
    
    return [BNTXTexture(
        name=name,
        width=width,
        height=height,
        format=format_code,
        tile_mode=tile_mode,
        size_range=size_range,
        alignment=alignment,
        num_mips=num_mips,
        data=tex_data,
        array_count=array_count,
        image_size=image_size
    )]


# ============================================================================
# Swizzle/Deswizzle (from BNTX-Extractor by AboodXD + Switch Toolbox)
# ============================================================================

def div_round_up(n: int, d: int) -> int:
    return (n + d - 1) // d


def round_up(x: int, y: int) -> int:
    return ((x - 1) | (y - 1)) + 1


def pow2_round_up(x: int) -> int:
    """Round up to the nearest power of 2."""
    x -= 1
    x |= x >> 1
    x |= x >> 2
    x |= x >> 4
    x |= x >> 8
    x |= x >> 16
    return x + 1


def calculate_block_height(height_in_blocks: int) -> int:
    """
    Calculate the correct block height for deswizzling.
    
    Based on Switch Toolbox's TegraX1Swizzle.GetBlockHeight method.
    For compressed textures, height should be in blocks (pixels / 4).
    """
    block_height = pow2_round_up(div_round_up(height_in_blocks, 8))
    
    # Cap at 16 (maximum effective GOB height for most textures)
    if block_height > 16:
        block_height = 16
    
    return block_height


def get_addr_block_linear(x: int, y: int, image_width: int, bytes_per_pixel: int, 
                          base_address: int, block_height: int) -> int:
    """
    Calculate address for block-linear tiling (from Tegra X1 TRM).
    """
    image_width_in_gobs = div_round_up(image_width * bytes_per_pixel, 64)
    
    gob_address = (base_address
                   + (y // (8 * block_height)) * 512 * block_height * image_width_in_gobs
                   + (x * bytes_per_pixel // 64) * 512 * block_height
                   + (y % (8 * block_height) // 8) * 512)
    
    x_bytes = x * bytes_per_pixel
    
    address = (gob_address 
               + ((x_bytes % 64) // 32) * 256 
               + ((y % 8) // 2) * 64
               + ((x_bytes % 32) // 16) * 32 
               + (y % 2) * 16 
               + (x_bytes % 16))
    
    return address


def deswizzle_block_linear(width: int, height: int, blk_width: int, blk_height: int,
                           bpp: int, data: bytes) -> bytes:
    """
    Deswizzle block-linear tiled data.
    
    Args:
        width: Texture width in pixels
        height: Texture height in pixels  
        blk_width: Block width (1 for uncompressed, 4 for BCn)
        blk_height: Block height (1 for uncompressed, 4 for BCn)
        bpp: Bytes per pixel/block
        data: Raw texture data
        
    Returns:
        Deswizzled data
    """
    # Work in blocks for compressed formats
    width_in_blocks = div_round_up(width, blk_width)
    height_in_blocks = div_round_up(height, blk_height)
    
    # Calculate the correct block height for this texture
    # This is the key fix - use height in blocks, not pixels
    gob_block_height = calculate_block_height(height_in_blocks)
    
    linear_size = width_in_blocks * height_in_blocks * bpp
    result = bytearray(linear_size)
    
    for y in range(height_in_blocks):
        for x in range(width_in_blocks):
            pos = get_addr_block_linear(x, y, width_in_blocks, bpp, 0, gob_block_height)
            pos_linear = (y * width_in_blocks + x) * bpp
            
            if pos + bpp <= len(data) and pos_linear + bpp <= linear_size:
                result[pos_linear:pos_linear + bpp] = data[pos:pos + bpp]
    
    return bytes(result)


# ============================================================================
# BC4 Decoder
# ============================================================================

def decode_bc4_block(block_data: bytes) -> bytes:
    """
    Decode a single BC4 (ATI1/DXT5A) 4x4 block.
    """
    if len(block_data) < 8:
        return bytes(16)
    
    alpha0 = block_data[0]
    alpha1 = block_data[1]
    
    alphas = [0] * 8
    alphas[0] = alpha0
    alphas[1] = alpha1
    
    if alpha0 > alpha1:
        alphas[2] = (6 * alpha0 + 1 * alpha1) // 7
        alphas[3] = (5 * alpha0 + 2 * alpha1) // 7
        alphas[4] = (4 * alpha0 + 3 * alpha1) // 7
        alphas[5] = (3 * alpha0 + 4 * alpha1) // 7
        alphas[6] = (2 * alpha0 + 5 * alpha1) // 7
        alphas[7] = (1 * alpha0 + 6 * alpha1) // 7
    else:
        alphas[2] = (4 * alpha0 + 1 * alpha1) // 5
        alphas[3] = (3 * alpha0 + 2 * alpha1) // 5
        alphas[4] = (2 * alpha0 + 3 * alpha1) // 5
        alphas[5] = (1 * alpha0 + 4 * alpha1) // 5
        alphas[6] = 0
        alphas[7] = 255
    
    indices = int.from_bytes(block_data[2:8], 'little')
    
    result = bytearray(16)
    for i in range(16):
        idx = (indices >> (i * 3)) & 0x7
        result[i] = alphas[idx]
    
    return bytes(result)


def decode_bc4_to_rgba(data: bytes, width: int, height: int) -> bytes:
    """
    Decode BC4 texture to RGBA8888.
    Uses NumPy for faster processing if available.
    """
    if HAS_NUMPY:
        return _decode_bc4_to_rgba_numpy(data, width, height)
    return _decode_bc4_to_rgba_slow(data, width, height)


def _decode_bc4_to_rgba_numpy(data: bytes, width: int, height: int) -> bytes:
    """Fast BC4 decoding using NumPy vectorization."""
    block_width = div_round_up(width, 4)
    block_height = div_round_up(height, 4)
    total_blocks = block_width * block_height
    
    # Prepare output array
    output = np.zeros((height, width, 4), dtype=np.uint8)
    output[:, :, :3] = 255  # RGB = white
    
    # Process data as numpy array
    data_arr = np.frombuffer(data, dtype=np.uint8)
    
    for block_idx in range(total_blocks):
        block_offset = block_idx * 8
        if block_offset + 8 > len(data_arr):
            continue
            
        bx = block_idx % block_width
        by = block_idx // block_width
        
        # Decode block
        alpha0 = int(data_arr[block_offset])
        alpha1 = int(data_arr[block_offset + 1])
        
        # Build alpha lookup table
        alphas = np.zeros(8, dtype=np.uint8)
        alphas[0] = alpha0
        alphas[1] = alpha1
        
        if alpha0 > alpha1:
            alphas[2] = (6 * alpha0 + 1 * alpha1) // 7
            alphas[3] = (5 * alpha0 + 2 * alpha1) // 7
            alphas[4] = (4 * alpha0 + 3 * alpha1) // 7
            alphas[5] = (3 * alpha0 + 4 * alpha1) // 7
            alphas[6] = (2 * alpha0 + 5 * alpha1) // 7
            alphas[7] = (1 * alpha0 + 6 * alpha1) // 7
        else:
            alphas[2] = (4 * alpha0 + 1 * alpha1) // 5
            alphas[3] = (3 * alpha0 + 2 * alpha1) // 5
            alphas[4] = (2 * alpha0 + 3 * alpha1) // 5
            alphas[5] = (1 * alpha0 + 4 * alpha1) // 5
            alphas[6] = 0
            alphas[7] = 255
        
        # Get 48-bit index data
        indices = int.from_bytes(data_arr[block_offset + 2:block_offset + 8].tobytes(), 'little')
        
        # Extract indices for all 16 pixels
        for py in range(4):
            for px in range(4):
                x = bx * 4 + px
                y = by * 4 + py
                if x < width and y < height:
                    pixel_idx = py * 4 + px
                    idx = (indices >> (pixel_idx * 3)) & 0x7
                    output[y, x, 3] = alphas[idx]
    
    return output.tobytes()


def _decode_bc4_to_rgba_slow(data: bytes, width: int, height: int) -> bytes:
    """Original BC4 decoding (fallback when NumPy not available)."""
    block_width = div_round_up(width, 4)
    block_height = div_round_up(height, 4)
    
    output = bytearray(width * height * 4)
    
    for by in range(block_height):
        for bx in range(block_width):
            block_idx = by * block_width + bx
            block_offset = block_idx * 8
            
            if block_offset + 8 <= len(data):
                block = decode_bc4_block(data[block_offset:block_offset + 8])
            else:
                block = bytes(16)
            
            for py in range(4):
                for px in range(4):
                    x = bx * 4 + px
                    y = by * 4 + py
                    
                    if x < width and y < height:
                        pixel_idx = py * 4 + px
                        out_offset = (y * width + x) * 4
                        alpha = block[pixel_idx]
                        
                        output[out_offset] = 255
                        output[out_offset + 1] = 255
                        output[out_offset + 2] = 255
                        output[out_offset + 3] = alpha
    
    return bytes(output)


# ============================================================================
# BNTX Format Constants
# ============================================================================

def get_format_info(format_code: int) -> Tuple[int, int, int]:
    """Get format info: (bpp, blk_width, blk_height)"""
    # Format code: low word is format type, high byte is variant
    # 0x1D01 = BC4 UNORM, 0x1D02 = BC4 SNORM
    # 0x1A01 = BC1, 0x1C01 = BC3
    
    format_map = {
        0x0101: (1, 1, 1),    # R8
        0x0201: (2, 1, 1),    # R8G8
        0x0301: (3, 1, 1),    # R8G8B8
        0x0B01: (4, 1, 1),    # R8G8B8A8
        0x1A01: (8, 4, 4),    # BC1
        0x1A06: (8, 4, 4),    # BC1 SRGB
        0x1B01: (16, 4, 4),   # BC2
        0x1C01: (16, 4, 4),   # BC3
        0x1C06: (16, 4, 4),   # BC3 SRGB
        0x1D01: (8, 4, 4),    # BC4 UNORM
        0x1D02: (8, 4, 4),    # BC4 SNORM
        0x1E01: (16, 4, 4),   # BC5 UNORM
        0x1E02: (16, 4, 4),   # BC5 SNORM
        0x2001: (16, 4, 4),   # BC7 UNORM
        0x2006: (16, 4, 4),   # BC7 SRGB
    }
    return format_map.get(format_code, (4, 1, 1))


# ============================================================================
# Main Decoding Functions
# ============================================================================

def decode_bntx_sheet(tex: BNTXTexture, sheet_index: int) -> Image.Image:
    """
    Decode a single texture sheet from BNTX data.
    """
    bpp, blk_width, blk_height = get_format_info(tex.format)
    
    # Calculate the size of a single sheet
    # Note: tex.image_size is the TOTAL size for all sheets, not per-sheet
    calculated_sheet_size = div_round_up(tex.width, blk_width) * div_round_up(tex.height, blk_height) * bpp
    sheet_size = calculated_sheet_size
    
    # Extract data for this sheet
    data_start = sheet_index * sheet_size
    sheet_data = tex.data[data_start:data_start + sheet_size]
    
    # Deswizzle (always use block-linear for Switch textures)
    deswizzled = deswizzle_block_linear(
        tex.width, tex.height,
        blk_width, blk_height,
        bpp,
        sheet_data
    )
    
    # Decode to RGBA
    if tex.format in (0x1D01, 0x1D02):  # BC4
        rgba_data = decode_bc4_to_rgba(deswizzled, tex.width, tex.height)
    elif tex.format in (0x0B01,):  # RGBA8
        expected = tex.width * tex.height * 4
        rgba_data = deswizzled[:expected] if len(deswizzled) >= expected else deswizzled + bytes(expected - len(deswizzled))
    else:
        # Treat as single channel
        output = bytearray(tex.width * tex.height * 4)
        for i in range(min(len(deswizzled), tex.width * tex.height)):
            v = deswizzled[i]
            out_offset = i * 4
            output[out_offset] = 255
            output[out_offset + 1] = 255
            output[out_offset + 2] = 255
            output[out_offset + 3] = v
        rgba_data = bytes(output)
    
    # Create image
    image = Image.frombytes('RGBA', (tex.width, tex.height), rgba_data)
    
    # Flip Y axis (Switch textures are stored upside down)
    image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    
    return image


def decode_all_sheets(bffnt: BFFNTFile) -> List[Image.Image]:
    """
    Decode all texture sheets from a BFFNT file.
    """
    is_switch = bffnt.header.platform == PlatformType.NX
    
    if is_switch:
        # Combine all sheet data into single BNTX
        combined_data = b''.join(bffnt.tglp.sheet_data)
        
        if combined_data[:4] == b'BNTX':
            textures = parse_bntx(combined_data)
            
            if not textures:
                return _decode_legacy_sheets(bffnt)
            
            tex = textures[0]
            sheets = []
            
            # Decode each sheet in the texture array
            # Use array_count from BNTX which contains the actual number of texture layers
            num_sheets = tex.array_count if tex.array_count > 1 else 1
            
            for i in range(num_sheets):
                try:
                    sheet = decode_bntx_sheet(tex, i)
                    sheets.append(sheet)
                except Exception as e:
                    print(f"Failed to decode sheet {i}: {e}")
                    sheets.append(Image.new('RGBA', 
                        (tex.width, tex.height), 
                        (255, 0, 255, 255)))
            
            return sheets
    
    return _decode_legacy_sheets(bffnt)


def _decode_legacy_sheets(bffnt: BFFNTFile) -> List[Image.Image]:
    """Decode sheets for non-Switch platforms."""
    tglp = bffnt.tglp
    sheets = []
    
    for i, raw_data in enumerate(tglp.sheet_data):
        try:
            if tglp.texture_format == TextureFormat.BC4:
                rgba_data = decode_bc4_to_rgba(raw_data, tglp.sheet_width, tglp.sheet_height)
            else:
                output = bytearray(tglp.sheet_width * tglp.sheet_height * 4)
                for j in range(min(len(raw_data), tglp.sheet_width * tglp.sheet_height)):
                    v = raw_data[j]
                    out_offset = j * 4
                    output[out_offset] = 255
                    output[out_offset + 1] = 255
                    output[out_offset + 2] = 255
                    output[out_offset + 3] = v
                rgba_data = bytes(output)
            
            image = Image.frombytes('RGBA', (tglp.sheet_width, tglp.sheet_height), rgba_data)
            
            if bffnt.header.platform.value >= PlatformType.CAFE.value:
                image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            
            sheets.append(image)
        except Exception as e:
            print(f"Failed to decode sheet {i}: {e}")
            sheets.append(Image.new('RGBA', 
                (tglp.sheet_width, tglp.sheet_height), 
                (255, 0, 255, 255)))
    
    return sheets


def extract_glyph(sheet: Image.Image, tglp: TGLP, 
                  row: int, column: int) -> Image.Image:
    """
    Extract a single glyph from a texture sheet.
    """
    cell_width = tglp.cell_width + 1
    cell_height = tglp.cell_height + 1
    
    x = column * cell_width + 1
    y = row * cell_height + 1
    
    return sheet.crop((x, y, x + tglp.cell_width, y + tglp.cell_height))


def extract_all_glyphs(bffnt: BFFNTFile, sheets: List[Image.Image]) -> List[Image.Image]:
    """
    Extract all glyphs from decoded texture sheets.
    Optimized to pre-calculate coordinates and minimize method calls.
    """
    glyphs = []
    tglp = bffnt.tglp
    
    # Pre-calculate cell dimensions
    cell_width = tglp.cell_width + 1
    cell_height = tglp.cell_height + 1
    glyph_w = tglp.cell_width
    glyph_h = tglp.cell_height
    rows = tglp.cells_per_column
    cols = tglp.cells_per_row
    
    for sheet in sheets:
        # Pre-calculate all crop boxes for this sheet
        for row in range(rows):
            y = row * cell_height + 1
            for col in range(cols):
                x = col * cell_width + 1
                # Use tuple directly for crop (slightly faster)
                glyphs.append(sheet.crop((x, y, x + glyph_w, y + glyph_h)))
    
    return glyphs
