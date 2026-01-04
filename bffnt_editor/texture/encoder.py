"""
Texture Encoder - Encodes images back to BFFNT-compatible formats.

For Nintendo Switch (NX) platform, this produces BC4-compressed BNTX textures
with proper block-linear swizzling.
"""

import struct
from dataclasses import dataclass
from typing import List, Tuple
from PIL import Image

from .decoder import (
    div_round_up, round_up, pow2_round_up, calculate_block_height,
    get_addr_block_linear, get_format_info
)


# ============================================================================
# BC4 Encoder (Lossless for grayscale/alpha data)
# ============================================================================

def encode_bc4_block(pixels: bytes) -> bytes:
    """
    Encode a 4x4 block of alpha values to BC4 format.
    
    BC4 stores 16 alpha values using 2 endpoint values + 48-bit indices.
    We use optimal encoding to minimize quality loss.
    
    Args:
        pixels: 16 bytes, one alpha value per pixel in row-major order
        
    Returns:
        8 bytes of BC4 encoded data
    """
    if len(pixels) < 16:
        pixels = pixels + bytes(16 - len(pixels))
    
    # Find min and max alpha values
    min_alpha = min(pixels)
    max_alpha = max(pixels)
    
    # Choose encoding mode based on the range of values
    # Mode 1: alpha0 > alpha1 - uses 8 interpolated values
    # Mode 2: alpha0 <= alpha1 - uses 6 interpolated values + 0 and 255
    
    if min_alpha == max_alpha:
        # All pixels are the same - trivial case
        alpha0 = min_alpha
        alpha1 = min_alpha
        indices = 0  # All indices point to alpha0
    else:
        # Use mode with 8 interpolated values (alpha0 > alpha1)
        # This gives best precision for most cases
        alpha0 = max_alpha
        alpha1 = min_alpha
        
        # Pre-compute interpolated values
        alphas = [0] * 8
        alphas[0] = alpha0
        alphas[1] = alpha1
        alphas[2] = (6 * alpha0 + 1 * alpha1 + 3) // 7
        alphas[3] = (5 * alpha0 + 2 * alpha1 + 3) // 7
        alphas[4] = (4 * alpha0 + 3 * alpha1 + 3) // 7
        alphas[5] = (3 * alpha0 + 4 * alpha1 + 3) // 7
        alphas[6] = (2 * alpha0 + 5 * alpha1 + 3) // 7
        alphas[7] = (1 * alpha0 + 6 * alpha1 + 3) // 7
        
        # Find best index for each pixel
        indices = 0
        for i in range(16):
            pixel_value = pixels[i]
            
            # Find closest alpha value
            best_idx = 0
            best_diff = abs(alphas[0] - pixel_value)
            
            for j in range(1, 8):
                diff = abs(alphas[j] - pixel_value)
                if diff < best_diff:
                    best_diff = diff
                    best_idx = j
            
            indices |= best_idx << (i * 3)
    
    # Pack the result
    result = bytearray(8)
    result[0] = alpha0
    result[1] = alpha1
    result[2:8] = indices.to_bytes(6, 'little')
    
    return bytes(result)


def encode_rgba_to_bc4(image: Image.Image) -> bytes:
    """
    Encode an RGBA image to BC4 format using the alpha channel.
    
    Args:
        image: PIL Image in RGBA format
        
    Returns:
        BC4 encoded bytes
    """
    width, height = image.size
    
    # Get alpha channel
    if image.mode == 'RGBA':
        alpha = image.split()[3]
    elif image.mode == 'LA':
        alpha = image.split()[1]
    elif image.mode == 'L':
        alpha = image
    else:
        # Convert to get alpha
        alpha = image.convert('RGBA').split()[3]
    
    alpha_data = alpha.tobytes()
    
    block_width = div_round_up(width, 4)
    block_height = div_round_up(height, 4)
    
    result = bytearray(block_width * block_height * 8)
    
    for by in range(block_height):
        for bx in range(block_width):
            # Extract 4x4 block of alpha values
            block_pixels = bytearray(16)
            
            for py in range(4):
                for px in range(4):
                    x = bx * 4 + px
                    y = by * 4 + py
                    
                    if x < width and y < height:
                        idx = y * width + x
                        block_pixels[py * 4 + px] = alpha_data[idx]
                    else:
                        # Pad with last valid pixel or 0
                        block_pixels[py * 4 + px] = 0
            
            # Encode block
            encoded = encode_bc4_block(bytes(block_pixels))
            
            # Write to output
            block_idx = by * block_width + bx
            out_offset = block_idx * 8
            result[out_offset:out_offset + 8] = encoded
    
    return bytes(result)


# ============================================================================
# Swizzle (reverse of deswizzle)
# ============================================================================

def swizzle_block_linear(width: int, height: int, blk_width: int, blk_height: int,
                         bpp: int, data: bytes) -> bytes:
    """
    Swizzle linear data to block-linear tiled format.
    
    This is the reverse of deswizzle_block_linear.
    
    Args:
        width: Texture width in pixels
        height: Texture height in pixels  
        blk_width: Block width (1 for uncompressed, 4 for BCn)
        blk_height: Block height (1 for uncompressed, 4 for BCn)
        bpp: Bytes per pixel/block
        data: Linear texture data
        
    Returns:
        Swizzled data suitable for Switch GPU
    """
    # Work in blocks for compressed formats
    width_in_blocks = div_round_up(width, blk_width)
    height_in_blocks = div_round_up(height, blk_height)
    
    # Calculate the correct block height for this texture
    gob_block_height = calculate_block_height(height_in_blocks)
    
    # Calculate required buffer size with proper alignment
    # GOBs are 512 bytes, we need proper padding
    image_width_in_gobs = div_round_up(width_in_blocks * bpp, 64)
    height_in_gob_blocks = div_round_up(height_in_blocks, 8 * gob_block_height)
    
    swizzled_size = image_width_in_gobs * height_in_gob_blocks * 512 * gob_block_height
    
    # Ensure we have enough space
    linear_size = width_in_blocks * height_in_blocks * bpp
    swizzled_size = max(swizzled_size, linear_size)
    
    result = bytearray(swizzled_size)
    
    for y in range(height_in_blocks):
        for x in range(width_in_blocks):
            pos_linear = (y * width_in_blocks + x) * bpp
            pos = get_addr_block_linear(x, y, width_in_blocks, bpp, 0, gob_block_height)
            
            if pos_linear + bpp <= len(data) and pos + bpp <= swizzled_size:
                result[pos:pos + bpp] = data[pos_linear:pos_linear + bpp]
    
    return bytes(result)


# ============================================================================
# BNTX Builder
# ============================================================================

@dataclass
class BNTXBuildParams:
    """Parameters for building a BNTX file."""
    name: str = "font_texture"
    width: int = 1024
    height: int = 1024
    format_code: int = 0x1D01  # BC4 UNORM
    array_count: int = 1
    alignment: int = 512


def build_bntx(sheets: List[Image.Image], params: BNTXBuildParams = None) -> bytes:
    """
    Build a BNTX file from a list of texture sheets.
    
    Args:
        sheets: List of PIL Images (will use alpha channel for BC4)
        params: Build parameters
        
    Returns:
        Complete BNTX file bytes
    """
    if params is None:
        params = BNTXBuildParams()
    
    if not sheets:
        raise ValueError("No sheets provided")
    
    # Get dimensions from first sheet
    width, height = sheets[0].size
    params.width = width
    params.height = height
    params.array_count = len(sheets)
    
    # Get format info
    bpp, blk_width, blk_height = get_format_info(params.format_code)
    
    # Encode all sheets
    encoded_sheets = []
    for sheet in sheets:
        # Flip Y axis (Switch stores textures upside down)
        flipped = sheet.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        
        # Encode to BC4
        linear_data = encode_rgba_to_bc4(flipped)
        
        # Swizzle
        swizzled = swizzle_block_linear(width, height, blk_width, blk_height, bpp, linear_data)
        encoded_sheets.append(swizzled)
    
    # Calculate sizes
    sheet_size = len(encoded_sheets[0]) if encoded_sheets else 0
    total_texture_size = sheet_size * len(encoded_sheets)
    
    # Build BNTX structure
    # This is a simplified BNTX that should work for font textures
    
    # Calculate offsets
    bntx_header_size = 0x20
    nx_header_size = 0x28
    brti_size = 0x100
    str_table_size = 0x20  # Name + padding
    brtd_header_size = 0x10
    
    # Data starts at 0x1000 (page aligned)
    data_offset = 0x1000
    
    # Total file size
    file_size = data_offset + total_texture_size
    
    # Build the file
    result = bytearray(file_size)
    
    # BNTX Header (0x00)
    result[0:4] = b'BNTX'
    result[0x04:0x08] = struct.pack('<I', 0x20)  # Data array offset
    result[0x08:0x0C] = struct.pack('<I', file_size)
    result[0x0C:0x0E] = struct.pack('>H', 0xFFFE)  # BOM (little endian)
    result[0x0E:0x10] = struct.pack('<H', 0x40)  # FormatRevision
    result[0x10:0x14] = struct.pack('<I', len(params.name) + 2)  # File name offset (relative)
    result[0x14:0x16] = struct.pack('<H', 0)  # Strings offset (relative)
    result[0x16:0x18] = struct.pack('<H', 0)  # Relocation offset
    result[0x18:0x1C] = struct.pack('<I', file_size)  # File size
    
    # NX Header (0x20) - "NX  " block
    result[0x20:0x24] = b'NX  '
    result[0x24:0x28] = struct.pack('<I', 1)  # Texture count
    result[0x28:0x30] = struct.pack('<q', 0x38)  # Texture info array offset (relative to 0x28)
    result[0x30:0x38] = struct.pack('<q', 0x48)  # Texture data block offset (relative to 0x30)
    result[0x38:0x40] = struct.pack('<q', 0x60)  # Texture dict offset (relative to 0x38)
    result[0x40:0x48] = struct.pack('<q', 0x200 - 0x40)  # String dict offset (relative to 0x40)
    
    # BRTI Section (Texture Info) at 0x60
    brti_offset = 0x60
    result[brti_offset:brti_offset+4] = b'BRTI'
    result[brti_offset+0x04:brti_offset+0x08] = struct.pack('<I', brti_size)  # Section size
    result[brti_offset+0x08:brti_offset+0x0C] = struct.pack('<I', brti_size)  # Unknown
    
    # BRTI fields
    result[brti_offset+0x10] = 0x01  # Flags
    result[brti_offset+0x11] = 0x02  # Dims (2D)
    result[brti_offset+0x12:brti_offset+0x14] = struct.pack('<H', 0x00)  # Tile mode (block linear)
    result[brti_offset+0x14:brti_offset+0x16] = struct.pack('<H', 0x00)  # Swizzle
    result[brti_offset+0x16:brti_offset+0x18] = struct.pack('<H', 1)  # NumMips
    result[brti_offset+0x18:brti_offset+0x1C] = struct.pack('<I', 1)  # NumSamples
    result[brti_offset+0x1C:brti_offset+0x20] = struct.pack('<I', params.format_code)  # Format
    result[brti_offset+0x20:brti_offset+0x24] = struct.pack('<I', 0x01)  # GPU Access
    result[brti_offset+0x24:brti_offset+0x28] = struct.pack('<I', width)  # Width
    result[brti_offset+0x28:brti_offset+0x2C] = struct.pack('<I', height)  # Height
    result[brti_offset+0x2C:brti_offset+0x30] = struct.pack('<I', 1)  # Depth
    result[brti_offset+0x30:brti_offset+0x34] = struct.pack('<I', params.array_count)  # Array count
    
    # Texture layout - block height encoded in bits 0-2
    block_height_log2 = 0
    height_in_blocks = div_round_up(height, blk_height)
    gob_block_height = calculate_block_height(height_in_blocks)
    while (1 << block_height_log2) < gob_block_height and block_height_log2 < 4:
        block_height_log2 += 1
    result[brti_offset+0x38:brti_offset+0x3C] = struct.pack('<I', block_height_log2)
    
    # Image size and alignment
    result[brti_offset+0x50:brti_offset+0x54] = struct.pack('<I', sheet_size)
    result[brti_offset+0x54:brti_offset+0x58] = struct.pack('<I', params.alignment)
    
    # Name pointer (offset 0x60 in BRTI)
    name_offset = 0x200
    result[brti_offset+0x60:brti_offset+0x68] = struct.pack('<q', name_offset)
    
    # Write name at name_offset
    name_bytes = params.name.encode('utf-8')
    result[name_offset:name_offset+2] = struct.pack('<H', len(name_bytes))
    result[name_offset+2:name_offset+2+len(name_bytes)] = name_bytes
    
    # BRTD Section header (marks start of texture data)
    brtd_offset = data_offset - brtd_header_size
    result[brtd_offset:brtd_offset+4] = b'BRTD'
    result[brtd_offset+0x04:brtd_offset+0x08] = struct.pack('<I', total_texture_size + brtd_header_size)
    
    # Write texture data
    offset = data_offset
    for sheet_data in encoded_sheets:
        result[offset:offset+len(sheet_data)] = sheet_data
        offset += sheet_size
    
    return bytes(result)


def encode_sheets_for_bffnt(sheets: List[Image.Image], texture_format: int = 0x1D01) -> Tuple[bytes, int]:
    """
    Encode sheet images for embedding in BFFNT.
    
    Args:
        sheets: List of PIL Images
        texture_format: BNTX format code (default BC4 UNORM)
        
    Returns:
        Tuple of (BNTX bytes, sheet size)
    """
    params = BNTXBuildParams(format_code=texture_format)
    bntx_data = build_bntx(sheets, params)
    
    # Calculate individual sheet size for TGLP
    if sheets:
        bpp, blk_width, blk_height = get_format_info(texture_format)
        width, height = sheets[0].size
        width_in_blocks = div_round_up(width, blk_width)
        height_in_blocks = div_round_up(height, blk_height)
        sheet_size = width_in_blocks * height_in_blocks * bpp
    else:
        sheet_size = 0
    
    return bntx_data, sheet_size
