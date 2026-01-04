"""
BFFNT Writer - Writes modified BFFNT files back to disk.

Reconstructs the binary BFFNT format from the parsed data structure,
allowing modifications to be saved.
"""

import struct
from typing import BinaryIO, Dict, List, Optional
from io import BytesIO

from .bffnt_parser import (
    BFFNTFile, FFNTHeader, FINF, TGLP, CWDH, CMAP, KRNG,
    CMAPType, CMAPDirect, CMAPTable, CMAPScan,
    CharWidthEntry, TextureFormat, PlatformType
)


class BFFNTWriter:
    """Writer for BFFNT font files."""
    
    def __init__(self, bffnt: BFFNTFile):
        self.bffnt = bffnt
        self.little_endian = True
    
    def _write_u8(self, f: BinaryIO, value: int) -> None:
        f.write(struct.pack('B', value & 0xFF))
    
    def _write_u16(self, f: BinaryIO, value: int) -> None:
        fmt = '<H' if self.little_endian else '>H'
        f.write(struct.pack(fmt, value & 0xFFFF))
    
    def _write_s16(self, f: BinaryIO, value: int) -> None:
        fmt = '<h' if self.little_endian else '>h'
        f.write(struct.pack(fmt, value))
    
    def _write_u32(self, f: BinaryIO, value: int) -> None:
        fmt = '<I' if self.little_endian else '>I'
        f.write(struct.pack(fmt, value & 0xFFFFFFFF))
    
    def _write_magic(self, f: BinaryIO, magic: str) -> None:
        f.write(magic.encode('ascii'))
    
    def _align(self, f: BinaryIO, alignment: int) -> None:
        """Align file position to given boundary."""
        pos = f.tell()
        aligned = (pos + alignment - 1) & ~(alignment - 1)
        if aligned > pos:
            f.write(bytes(aligned - pos))
    
    def write(self, output_path: str) -> None:
        """
        Write the BFFNT file to disk.
        
        Args:
            output_path: Path to save the BFFNT file
        """
        with open(output_path, 'wb') as f:
            self._write_stream(f)
    
    def write_bytes(self) -> bytes:
        """
        Write the BFFNT file and return as bytes.
        
        Returns:
            Complete BFFNT file as bytes
        """
        buffer = BytesIO()
        self._write_stream(buffer)
        return buffer.getvalue()
    
    def _write_stream(self, f: BinaryIO) -> None:
        """Write BFFNT to a binary stream."""
        header = self.bffnt.header
        
        # Determine endianness from original file
        self.little_endian = (header.bom == 0xFFFE)
        
        # Write header placeholder (will update later with final sizes)
        header_start = f.tell()
        self._write_header_placeholder(f)
        
        # Write FINF section placeholder
        finf_start = f.tell()
        self._write_finf_placeholder(f)
        
        # Write TGLP section header (without data)
        tglp_start = f.tell()
        self._write_tglp_placeholder(f)
        
        # Align to 0x1000 and write texture data
        # The alignment is relative to file start for Switch BFFNT
        self._align(f, 0x1000)
        texture_data_start = f.tell()
        self._write_texture_data(f)
        
        # After texture data, align to 4 bytes
        self._align(f, 4)
        
        # Write CWDH sections
        cwdh_start = f.tell()
        self._write_cwdh_chain(f)
        
        # Align to 4 bytes before CMAP
        self._align(f, 4)
        
        # Write CMAP sections
        cmap_start = f.tell()
        self._write_cmap_chain(f)
        
        # Write KRNG section if present
        if self.bffnt.krng is not None:
            self._write_krng(f)
        
        # Get final file size
        file_size = f.tell()
        
        # Calculate actual TGLP section size (header + texture data)
        tglp_section_size = texture_data_start - tglp_start + sum(len(sheet) for sheet in self.bffnt.tglp.sheet_data)
        
        # Go back and update TGLP section with correct values
        # sheet_data_offset is absolute file position
        f.seek(tglp_start)
        self._write_tglp_with_offset(f, texture_data_start, tglp_section_size)
        
        # Go back and update offsets in FINF
        # Offsets are absolute position + 8 (pointing past magic and section_size)
        f.seek(finf_start)
        self._write_finf(f, tglp_start + 8, cwdh_start + 8, cmap_start + 8)
        
        # Go back and update header with final file size
        f.seek(header_start)
        self._write_header(f, file_size)
    
    def _write_header_placeholder(self, f: BinaryIO) -> None:
        """Write header with placeholder values."""
        f.write(bytes(self.bffnt.header.header_size))
    
    def _write_header(self, f: BinaryIO, file_size: int) -> None:
        """Write the FFNT header with correct values."""
        header = self.bffnt.header
        
        self._write_magic(f, header.magic)
        
        # BOM
        f.write(struct.pack('>H', header.bom))
        
        self._write_u16(f, header.header_size)
        self._write_u32(f, header.version)
        self._write_u32(f, file_size)
        self._write_u16(f, header.section_count)
        self._write_u16(f, 0)  # padding
    
    def _write_finf_placeholder(self, f: BinaryIO) -> None:
        """Write FINF with placeholder for offsets."""
        self._write_magic(f, 'FINF')
        f.write(bytes(self.bffnt.finf.section_size - 4))
    
    def _write_finf(self, f: BinaryIO, tglp_offset: int, cwdh_offset: int, cmap_offset: int) -> None:
        """Write the FINF section with correct offsets."""
        finf = self.bffnt.finf
        
        self._write_magic(f, 'FINF')
        self._write_u32(f, finf.section_size)
        self._write_u8(f, finf.font_type)
        self._write_u8(f, finf.height)
        self._write_u8(f, finf.width)
        self._write_u8(f, finf.ascent)
        self._write_u16(f, finf.line_feed)
        self._write_u16(f, finf.alter_char_index)
        self._write_u8(f, finf.default_left)
        self._write_u8(f, finf.default_glyph_width)
        self._write_u8(f, finf.default_char_width)
        self._write_u8(f, finf.char_encoding)
        self._write_u32(f, tglp_offset)
        self._write_u32(f, cwdh_offset)
        self._write_u32(f, cmap_offset)
    
    def _write_tglp_placeholder(self, f: BinaryIO) -> None:
        """
        Write the TGLP section header with placeholder for data offset.
        """
        tglp = self.bffnt.tglp
        
        self._write_magic(f, 'TGLP')
        self._write_u32(f, 0)  # Placeholder for section_size
        self._write_u8(f, tglp.cell_width)
        self._write_u8(f, tglp.cell_height)
        self._write_u8(f, tglp.sheet_count)
        self._write_u8(f, tglp.max_char_width)
        self._write_u32(f, tglp.sheet_size)
        self._write_u16(f, tglp.baseline)
        self._write_u16(f, tglp.texture_format.value)
        self._write_u16(f, tglp.cells_per_row)
        self._write_u16(f, tglp.cells_per_column)
        self._write_u16(f, tglp.sheet_width)
        self._write_u16(f, tglp.sheet_height)
        self._write_u32(f, 0)  # Placeholder for sheet_data_offset
    
    def _write_tglp_with_offset(self, f: BinaryIO, sheet_data_offset: int, section_size: int) -> None:
        """
        Write the TGLP section header with correct data offset and section size.
        
        Args:
            sheet_data_offset: Absolute file position of sheet data
            section_size: Total size of TGLP section including texture data
        """
        tglp = self.bffnt.tglp
        
        self._write_magic(f, 'TGLP')
        self._write_u32(f, section_size)
        self._write_u8(f, tglp.cell_width)
        self._write_u8(f, tglp.cell_height)
        self._write_u8(f, tglp.sheet_count)
        self._write_u8(f, tglp.max_char_width)
        self._write_u32(f, tglp.sheet_size)
        self._write_u16(f, tglp.baseline)
        self._write_u16(f, tglp.texture_format.value)
        self._write_u16(f, tglp.cells_per_row)
        self._write_u16(f, tglp.cells_per_column)
        self._write_u16(f, tglp.sheet_width)
        self._write_u16(f, tglp.sheet_height)
        self._write_u32(f, sheet_data_offset)
    
    def _write_cwdh_chain(self, f: BinaryIO) -> None:
        """Write all CWDH sections as a linked list."""
        cwdh_list = self.bffnt.cwdh_list
        
        for i, cwdh in enumerate(cwdh_list):
            section_start = f.tell()
            
            self._write_magic(f, 'CWDH')
            
            # Placeholder for section size (will update after writing)
            section_size_pos = f.tell()
            self._write_u32(f, 0)
            
            self._write_u16(f, cwdh.first_index)
            self._write_u16(f, cwdh.last_index)
            
            # Write next offset (0 for last section)
            next_offset_pos = f.tell()
            self._write_u32(f, 0)  # Placeholder
            
            # Write width entries
            for entry in cwdh.entries:
                self._write_u8(f, entry.left)
                self._write_u8(f, entry.glyph_width)
                self._write_u8(f, entry.char_width)
            
            # Align to 4 bytes
            self._align(f, 4)
            
            # Calculate and update section size (includes magic)
            section_end = f.tell()
            section_size = section_end - section_start
            f.seek(section_size_pos)
            self._write_u32(f, section_size)
            f.seek(section_end)
            
            # Update next offset if not last
            if i < len(cwdh_list) - 1:
                current_end = f.tell()
                # next_offset points to the position after magic+size (8 bytes) of the next section
                next_section_start = current_end + 8
                f.seek(next_offset_pos)
                self._write_u32(f, next_section_start)
                f.seek(current_end)
    
    def _write_cmap_chain(self, f: BinaryIO) -> None:
        """Write all CMAP sections as a linked list."""
        cmap_list = self.bffnt.cmap_list
        is_nx = self.bffnt.header.platform == PlatformType.NX
        
        for i, cmap in enumerate(cmap_list):
            section_start = f.tell()
            
            self._write_magic(f, 'CMAP')
            
            # We'll update section size later
            section_size_pos = f.tell()
            self._write_u32(f, 0)  # Placeholder
            
            # Character code range
            if is_nx:
                self._write_u32(f, cmap.code_begin)
                self._write_u32(f, cmap.code_end)
            else:
                self._write_u16(f, cmap.code_begin)
                self._write_u16(f, cmap.code_end)
            
            self._write_u16(f, cmap.mapping_type.value)
            self._write_u16(f, 0)  # padding
            
            next_offset_pos = f.tell()
            self._write_u32(f, 0)  # Placeholder for next offset
            
            # Write mapping data
            if cmap.mapping_type == CMAPType.DIRECT and isinstance(cmap.mapping_data, CMAPDirect):
                self._write_u16(f, cmap.mapping_data.offset)
            
            elif cmap.mapping_type == CMAPType.TABLE and isinstance(cmap.mapping_data, CMAPTable):
                for idx in cmap.mapping_data.table:
                    self._write_s16(f, idx)
            
            elif cmap.mapping_type == CMAPType.SCAN and isinstance(cmap.mapping_data, CMAPScan):
                self._write_u16(f, len(cmap.mapping_data.entries))
                if is_nx:
                    self._write_u16(f, 0)  # padding
                
                for char_code, glyph_index in cmap.mapping_data.entries:
                    if is_nx:
                        self._write_u32(f, char_code)
                        self._write_s16(f, glyph_index)
                        self._write_u16(f, 0)  # padding
                    else:
                        self._write_u16(f, char_code)
                        self._write_s16(f, glyph_index)
            
            # Align to 4 bytes
            self._align(f, 4)
            
            # Calculate and update section size (includes magic)
            section_end = f.tell()
            section_size = section_end - section_start
            f.seek(section_size_pos)
            self._write_u32(f, section_size)
            f.seek(section_end)
            
            # Update next offset if not last
            if i < len(cmap_list) - 1:
                current_end = f.tell()
                # next_offset points to the position after magic+size (8 bytes) of the next section
                next_section_start = current_end + 8
                f.seek(next_offset_pos)
                self._write_u32(f, next_section_start)
                f.seek(current_end)
    
    def _write_texture_data(self, f: BinaryIO) -> None:
        """Write texture sheet data."""
        for sheet_data in self.bffnt.tglp.sheet_data:
            f.write(sheet_data)
    
    def _write_krng(self, f: BinaryIO) -> None:
        """Write KRNG (kerning) section."""
        krng = self.bffnt.krng
        if krng is None:
            return
        
        section_start = f.tell()
        self._write_magic(f, 'KRNG')
        self._write_u32(f, krng.section_size)
        f.write(krng.data)


def _build_char_map_from_cmap(cmap_list: List[CMAP]) -> Dict[int, int]:
    """Build char_map from CMAP structures."""
    char_map = {}
    for cmap in cmap_list:
        if cmap.mapping_type == CMAPType.DIRECT and isinstance(cmap.mapping_data, CMAPDirect):
            for i, code in enumerate(range(cmap.code_begin, cmap.code_end + 1)):
                glyph = cmap.mapping_data.offset + i
                if glyph >= 0:
                    char_map[code] = glyph
        elif cmap.mapping_type == CMAPType.TABLE and isinstance(cmap.mapping_data, CMAPTable):
            for i, glyph in enumerate(cmap.mapping_data.table):
                code = cmap.code_begin + i
                if glyph >= 0:
                    char_map[code] = glyph
        elif cmap.mapping_type == CMAPType.SCAN and isinstance(cmap.mapping_data, CMAPScan):
            for code, glyph in cmap.mapping_data.entries:
                if glyph >= 0:
                    char_map[code] = glyph
    return char_map


def sync_char_map_to_cmap(bffnt: BFFNTFile) -> None:
    """
    Synchronize the char_map dictionary back to the CMAP structures.
    
    This function MODIFIES existing CMAP structures in-place rather than
    rebuilding them, to maintain compatibility with the game which expects
    the exact same CMAP structure.
    
    For updates: modifies glyph indices in existing CMAP entries
    For additions: adds new entries to the last SCAN-type CMAP, or creates one
    For deletions: marks entries as -1 (invalid)
    """
    if not bffnt.char_map:
        return
    
    # Build char_map from current CMAP structures
    original_char_map = _build_char_map_from_cmap(bffnt.cmap_list)
    
    # Check if there are any differences
    if bffnt.char_map == original_char_map:
        # No changes, keep original CMAP structures
        return
    
    # Find what changed
    new_mappings = {}  # char_code -> glyph for new entries
    updated_mappings = {}  # char_code -> glyph for updated entries
    deleted_codes = set()  # char_codes that were removed
    
    # Find updates and additions
    for code, glyph in bffnt.char_map.items():
        if code not in original_char_map:
            new_mappings[code] = glyph
        elif original_char_map[code] != glyph:
            updated_mappings[code] = glyph
    
    # Find deletions
    for code in original_char_map:
        if code not in bffnt.char_map:
            deleted_codes.add(code)
    
    # Apply updates to existing CMAP structures
    for cmap in bffnt.cmap_list:
        if cmap.mapping_type == CMAPType.DIRECT and isinstance(cmap.mapping_data, CMAPDirect):
            # DIRECT mapping - check if any code in range was updated
            for code in range(cmap.code_begin, cmap.code_end + 1):
                if code in updated_mappings or code in deleted_codes:
                    # Can't modify DIRECT easily - convert to SCAN
                    entries = []
                    for i, c in enumerate(range(cmap.code_begin, cmap.code_end + 1)):
                        original_glyph = cmap.mapping_data.offset + i
                        if c in deleted_codes:
                            continue  # Skip deleted
                        elif c in updated_mappings:
                            entries.append((c, updated_mappings[c]))
                            del updated_mappings[c]
                        else:
                            entries.append((c, original_glyph))
                    cmap.mapping_type = CMAPType.SCAN
                    cmap.mapping_data = CMAPScan(entries=entries)
                    if entries:
                        cmap.code_begin = entries[0][0]
                        cmap.code_end = entries[-1][0]
                    break
                    
        elif cmap.mapping_type == CMAPType.TABLE and isinstance(cmap.mapping_data, CMAPTable):
            # TABLE mapping - update entries in place
            for i, code in enumerate(range(cmap.code_begin, cmap.code_end + 1)):
                if code in updated_mappings:
                    cmap.mapping_data.table[i] = updated_mappings[code]
                    del updated_mappings[code]
                elif code in deleted_codes:
                    cmap.mapping_data.table[i] = -1  # Mark as invalid
                    
        elif cmap.mapping_type == CMAPType.SCAN and isinstance(cmap.mapping_data, CMAPScan):
            # SCAN mapping - update entries in place
            new_entries = []
            for code, glyph in cmap.mapping_data.entries:
                if code in deleted_codes:
                    continue  # Skip deleted
                elif code in updated_mappings:
                    new_entries.append((code, updated_mappings[code]))
                    del updated_mappings[code]
                else:
                    new_entries.append((code, glyph))
            cmap.mapping_data.entries = new_entries
            if new_entries:
                cmap.code_begin = min(e[0] for e in new_entries)
                cmap.code_end = max(e[0] for e in new_entries)
    
    # Add new mappings - FIRST try to add to existing TABLE CMAPs if the code is in range
    # This is important because some games only check TABLE CMAPs for certain character ranges
    if new_mappings:
        codes_added_to_table = set()
        
        # First pass: add to TABLE CMAPs where possible
        for cmap in bffnt.cmap_list:
            if cmap.mapping_type == CMAPType.TABLE and isinstance(cmap.mapping_data, CMAPTable):
                for code, glyph in list(new_mappings.items()):
                    if cmap.code_begin <= code <= cmap.code_end:
                        # This code falls within this TABLE's range - add it here!
                        idx = code - cmap.code_begin
                        if 0 <= idx < len(cmap.mapping_data.table):
                            cmap.mapping_data.table[idx] = glyph
                            codes_added_to_table.add(code)
        
        # Remove codes that were added to TABLE from new_mappings
        for code in codes_added_to_table:
            del new_mappings[code]
    
    # Add remaining new mappings to the last SCAN CMAP, or create one
    if new_mappings:
        # Find the last SCAN CMAP
        scan_cmap = None
        for cmap in reversed(bffnt.cmap_list):
            if cmap.mapping_type == CMAPType.SCAN and isinstance(cmap.mapping_data, CMAPScan):
                scan_cmap = cmap
                break
        
        if scan_cmap is None:
            # Create a new SCAN CMAP
            entries = sorted(new_mappings.items())
            scan_cmap = CMAP(
                section_size=0,
                code_begin=entries[0][0],
                code_end=entries[-1][0],
                mapping_type=CMAPType.SCAN,
                next_offset=0,
                mapping_data=CMAPScan(entries=entries)
            )
            bffnt.cmap_list.append(scan_cmap)
        else:
            # Add to existing SCAN CMAP
            current_entries = list(scan_cmap.mapping_data.entries)
            for code, glyph in new_mappings.items():
                current_entries.append((code, glyph))
            # Sort by char code
            current_entries.sort(key=lambda x: x[0])
            scan_cmap.mapping_data.entries = current_entries
            scan_cmap.code_begin = min(e[0] for e in current_entries)
            scan_cmap.code_end = max(e[0] for e in current_entries)


def save_bffnt(bffnt: BFFNTFile, output_path: str) -> None:
    """
    Convenience function to save a BFFNT file.
    
    Args:
        bffnt: BFFNT file structure to save
        output_path: Path to save the file
    """
    # Sync char_map back to CMAP structures before saving
    sync_char_map_to_cmap(bffnt)
    
    writer = BFFNTWriter(bffnt)
    writer.write(output_path)


def update_bffnt_textures(bffnt: BFFNTFile, new_bntx_data: bytes, num_sheets: int = None) -> None:
    """
    Update the texture data in a BFFNT file.
    
    For Switch (NX) platform, the BNTX blob is divided into num_sheets parts,
    each of size (total_size / num_sheets). This matches how the original
    format stores the data and how Switch Toolbox handles it.
    
    Args:
        bffnt: BFFNT file to modify
        new_bntx_data: New BNTX texture data (complete blob)
        num_sheets: Number of texture sheets in the BNTX array
    """
    if num_sheets is None or num_sheets < 1:
        num_sheets = bffnt.tglp.sheet_count if bffnt.tglp.sheet_count > 0 else 1
    
    # Calculate the size per sheet (BNTX is divided evenly)
    total_size = len(new_bntx_data)
    sheet_size = total_size // num_sheets
    
    # Divide the BNTX data into sheet_count parts
    # This is how Switch Toolbox does it
    sheet_data_list = []
    offset = 0
    for i in range(num_sheets):
        chunk = new_bntx_data[offset:offset + sheet_size]
        sheet_data_list.append(chunk)
        offset += sheet_size
    
    # Handle any remaining bytes (shouldn't happen if aligned correctly)
    if offset < total_size:
        # Append remaining bytes to the last sheet
        sheet_data_list[-1] = sheet_data_list[-1] + new_bntx_data[offset:]
        sheet_size = len(sheet_data_list[0])  # Recalculate
    
    bffnt.tglp.sheet_data = sheet_data_list
    bffnt.tglp.sheet_size = sheet_size
    bffnt.tglp.sheet_count = num_sheets
