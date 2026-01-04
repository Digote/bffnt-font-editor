"""
BFFNT Parser - Nintendo Switch Binary Font File Parser

Parses .bffnt files extracting font information, texture data,
character widths, and character code mappings.

Based on documentation and C# reference implementations.
"""

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import BinaryIO, Dict, List, Optional, Tuple
from io import BytesIO


class TextureFormat(IntEnum):
    """Texture formats used in BFFNT files."""
    RGBA8888 = 0
    RGB888 = 1
    RGB5A1 = 2
    RGB565 = 3
    RGBA4444 = 4
    LA8 = 5
    HILO8 = 6
    L8 = 7
    A8 = 8
    LA4 = 9
    L4 = 10
    A4 = 11
    BC4 = 12  # Block Compressed 4 (also known as DXT5A or ATI1)
    BC1 = 13
    BC2 = 14
    BC3 = 15
    BC7 = 16
    BC5 = 17


class CMAPType(IntEnum):
    """Character mapping types."""
    DIRECT = 0
    TABLE = 1
    SCAN = 2


class PlatformType(IntEnum):
    """Platform types for BFFNT files."""
    WII = 0
    CTR = 1  # 3DS
    CAFE = 2  # Wii U
    NX = 3  # Switch


@dataclass
class CharWidthEntry:
    """Width information for a single character."""
    left: int  # Distance from left cell border to character
    glyph_width: int  # Width of the glyph
    char_width: int  # Total character width (advance)


@dataclass
class CWDH:
    """Character Width Data Header section."""
    section_size: int
    first_index: int
    last_index: int
    next_offset: int
    entries: List[CharWidthEntry] = field(default_factory=list)


@dataclass
class CMAPDirect:
    """Direct mapping: sequential glyph indices starting from offset."""
    offset: int


@dataclass 
class CMAPTable:
    """Table mapping: array of glyph indices for each character code."""
    table: List[int]


@dataclass
class CMAPScan:
    """Scan mapping: sparse list of (character_code, glyph_index) pairs."""
    entries: List[Tuple[int, int]]  # (char_code, glyph_index)


@dataclass
class CMAP:
    """Character Map section - maps character codes to glyph indices."""
    section_size: int
    code_begin: int
    code_end: int
    mapping_type: CMAPType
    next_offset: int
    mapping_data: Optional[CMAPDirect | CMAPTable | CMAPScan] = None


@dataclass
class TGLP:
    """Texture Glyph section - contains font texture sheets."""
    section_size: int
    cell_width: int
    cell_height: int
    sheet_count: int
    max_char_width: int
    sheet_size: int
    baseline: int
    texture_format: TextureFormat
    cells_per_row: int
    cells_per_column: int
    sheet_width: int
    sheet_height: int
    sheet_data_offset: int
    sheet_data: List[bytes] = field(default_factory=list)


@dataclass
class FINF:
    """Font Info section - contains general font information."""
    section_size: int
    font_type: int
    height: int
    width: int
    ascent: int
    line_feed: int
    alter_char_index: int
    default_left: int
    default_glyph_width: int
    default_char_width: int
    char_encoding: int
    tglp_offset: int
    cwdh_offset: int
    cmap_offset: int


@dataclass
class KRNG:
    """Kerning section - contains kerning data for character pairs."""
    section_size: int
    data: bytes = field(default_factory=bytes)  # Raw kerning data


@dataclass
class FFNTHeader:
    """FFNT file header."""
    magic: str
    bom: int
    header_size: int
    version: int
    file_size: int
    section_count: int
    platform: PlatformType = PlatformType.NX


@dataclass
class BFFNTFile:
    """Complete BFFNT file structure."""
    header: FFNTHeader
    finf: FINF
    tglp: TGLP
    cwdh_list: List[CWDH] = field(default_factory=list)
    cmap_list: List[CMAP] = field(default_factory=list)
    char_map: Dict[int, int] = field(default_factory=dict)  # char_code -> glyph_index
    krng: Optional[KRNG] = None  # Kerning table (optional)
    
    def get_char_width(self, glyph_index: int) -> Optional[CharWidthEntry]:
        """Get width info for a glyph by its index."""
        for cwdh in self.cwdh_list:
            if cwdh.first_index <= glyph_index <= cwdh.last_index:
                local_index = glyph_index - cwdh.first_index
                if local_index < len(cwdh.entries):
                    return cwdh.entries[local_index]
        return None
    
    def ensure_char_width(self, glyph_index: int) -> CharWidthEntry:
        """
        Get or create width info for a glyph.
        If the glyph doesn't have width info, extends CWDH to include it.
        """
        # First try to get existing entry
        existing = self.get_char_width(glyph_index)
        if existing:
            return existing
        
        # Need to create entry - find or extend the appropriate CWDH
        if not self.cwdh_list:
            # Create first CWDH section
            default_entry = CharWidthEntry(
                left=self.finf.default_left,
                glyph_width=self.finf.default_glyph_width,
                char_width=self.finf.default_char_width
            )
            cwdh = CWDH(
                section_size=0,  # Will be calculated on save
                first_index=glyph_index,
                last_index=glyph_index,
                next_offset=0,
                entries=[default_entry]
            )
            self.cwdh_list.append(cwdh)
            return default_entry
        
        # Find the last CWDH and extend it
        last_cwdh = self.cwdh_list[-1]
        
        # Create default entry using font defaults
        default_entry = CharWidthEntry(
            left=self.finf.default_left,
            glyph_width=self.finf.default_glyph_width,
            char_width=self.finf.default_char_width
        )
        
        if glyph_index > last_cwdh.last_index:
            # Extend to include the new glyph
            # Fill gaps with default entries
            for _ in range(last_cwdh.last_index + 1, glyph_index):
                gap_entry = CharWidthEntry(
                    left=self.finf.default_left,
                    glyph_width=self.finf.default_glyph_width,
                    char_width=self.finf.default_char_width
                )
                last_cwdh.entries.append(gap_entry)
            
            last_cwdh.entries.append(default_entry)
            last_cwdh.last_index = glyph_index
            return default_entry
        elif glyph_index < self.cwdh_list[0].first_index:
            # Prepend entries to first CWDH
            first_cwdh = self.cwdh_list[0]
            new_entries = []
            for _ in range(glyph_index, first_cwdh.first_index):
                new_entries.append(CharWidthEntry(
                    left=self.finf.default_left,
                    glyph_width=self.finf.default_glyph_width,
                    char_width=self.finf.default_char_width
                ))
            first_cwdh.entries = new_entries + first_cwdh.entries
            first_cwdh.first_index = glyph_index
            return new_entries[0]
        
        return default_entry
    
    def get_glyph_index(self, char_code: int) -> int:
        """Get glyph index for a character code. Returns 0xFFFF if not found."""
        return self.char_map.get(char_code, 0xFFFF)
    
    def get_glyph_position(self, glyph_index: int) -> Tuple[int, int, int]:
        """Get (sheet_index, row, column) for a glyph."""
        glyphs_per_sheet = self.tglp.cells_per_row * self.tglp.cells_per_column
        sheet_index = glyph_index // glyphs_per_sheet
        local_index = glyph_index % glyphs_per_sheet
        row = local_index // self.tglp.cells_per_row
        column = local_index % self.tglp.cells_per_row
        return sheet_index, row, column


class BFFNTParser:
    """Parser for BFFNT font files."""
    
    def __init__(self):
        self.little_endian = True
    
    def _read_u8(self, f: BinaryIO) -> int:
        return struct.unpack('B', f.read(1))[0]
    
    def _read_u16(self, f: BinaryIO) -> int:
        fmt = '<H' if self.little_endian else '>H'
        return struct.unpack(fmt, f.read(2))[0]
    
    def _read_s16(self, f: BinaryIO) -> int:
        fmt = '<h' if self.little_endian else '>h'
        return struct.unpack(fmt, f.read(2))[0]
    
    def _read_u32(self, f: BinaryIO) -> int:
        fmt = '<I' if self.little_endian else '>I'
        return struct.unpack(fmt, f.read(4))[0]
    
    def _read_magic(self, f: BinaryIO, length: int = 4) -> str:
        return f.read(length).decode('ascii')
    
    def parse(self, file_path: str) -> BFFNTFile:
        """Parse a BFFNT file and return complete structure."""
        with open(file_path, 'rb') as f:
            return self._parse_stream(f)
    
    def parse_bytes(self, data: bytes) -> BFFNTFile:
        """Parse BFFNT data from bytes."""
        return self._parse_stream(BytesIO(data))
    
    def _parse_stream(self, f: BinaryIO) -> BFFNTFile:
        """Parse BFFNT from a binary stream."""
        # Read header
        header = self._parse_header(f)
        
        # Seek to first section
        f.seek(header.header_size)
        
        # Parse FINF section
        finf = self._parse_finf(f, header.platform)
        
        # Parse TGLP section
        f.seek(finf.tglp_offset - 8)
        tglp = self._parse_tglp(f)
        
        # Parse CWDH sections (linked list)
        cwdh_list = []
        if finf.cwdh_offset != 0:
            f.seek(finf.cwdh_offset - 8)
            self._parse_cwdh_chain(f, cwdh_list)
        
        # Parse CMAP sections (linked list)
        cmap_list = []
        char_map = {}
        if finf.cmap_offset != 0:
            f.seek(finf.cmap_offset - 8)
            self._parse_cmap_chain(f, cmap_list, char_map, header.platform)
        
        # Parse KRNG section if present (scan for it after CMAP sections)
        krng = None
        krng = self._parse_krng_if_present(f, header)
        
        return BFFNTFile(
            header=header,
            finf=finf,
            tglp=tglp,
            cwdh_list=cwdh_list,
            cmap_list=cmap_list,
            char_map=char_map,
            krng=krng
        )
    
    def _parse_header(self, f: BinaryIO) -> FFNTHeader:
        """Parse the FFNT header."""
        magic = self._read_magic(f)
        if magic not in ('FFNT', 'CFNT', 'RFNT', 'TNFR'):
            raise ValueError(f"Invalid magic: {magic}. Expected FFNT, CFNT, RFNT or TNFR")
        
        bom = struct.unpack('>H', f.read(2))[0]
        self.little_endian = (bom == 0xFFFE)
        
        # Determine platform from magic and endianness
        if magic in ('RFNT', 'TNFR'):
            platform = PlatformType.WII
            # Wii uses different header layout
            version = self._read_u16(f)
            file_size = self._read_u32(f)
            header_size = self._read_u16(f)
            section_count = self._read_u16(f)
        else:
            header_size = self._read_u16(f)
            version = self._read_u32(f)
            file_size = self._read_u32(f)
            section_count = self._read_u16(f)
            _ = self._read_u16(f)  # padding
            
            if magic == 'CFNT':
                platform = PlatformType.CTR
            elif self.little_endian:
                platform = PlatformType.NX if version >= 0x04010000 else PlatformType.CTR
            else:
                platform = PlatformType.CAFE
        
        return FFNTHeader(
            magic=magic,
            bom=bom,
            header_size=header_size,
            version=version,
            file_size=file_size,
            section_count=section_count,
            platform=platform
        )
    
    def _parse_finf(self, f: BinaryIO, platform: PlatformType) -> FINF:
        """Parse the FINF (Font Info) section."""
        magic = self._read_magic(f)
        if magic != 'FINF':
            raise ValueError(f"Expected FINF section, got {magic}")
        
        section_size = self._read_u32(f)
        font_type = self._read_u8(f)
        height = self._read_u8(f)
        width = self._read_u8(f)
        ascent = self._read_u8(f)
        line_feed = self._read_u16(f)
        alter_char_index = self._read_u16(f)
        default_left = self._read_u8(f)
        default_glyph_width = self._read_u8(f)
        default_char_width = self._read_u8(f)
        char_encoding = self._read_u8(f)
        tglp_offset = self._read_u32(f)
        cwdh_offset = self._read_u32(f)
        cmap_offset = self._read_u32(f)
        
        return FINF(
            section_size=section_size,
            font_type=font_type,
            height=height,
            width=width,
            ascent=ascent,
            line_feed=line_feed,
            alter_char_index=alter_char_index,
            default_left=default_left,
            default_glyph_width=default_glyph_width,
            default_char_width=default_char_width,
            char_encoding=char_encoding,
            tglp_offset=tglp_offset,
            cwdh_offset=cwdh_offset,
            cmap_offset=cmap_offset
        )
    
    def _parse_tglp(self, f: BinaryIO) -> TGLP:
        """Parse the TGLP (Texture Glyph) section."""
        start_pos = f.tell()
        
        magic = self._read_magic(f)
        if magic != 'TGLP':
            raise ValueError(f"Expected TGLP section, got {magic}")
        
        section_size = self._read_u32(f)
        cell_width = self._read_u8(f)
        cell_height = self._read_u8(f)
        sheet_count = self._read_u8(f)
        max_char_width = self._read_u8(f)
        sheet_size = self._read_u32(f)
        baseline = self._read_u16(f)
        texture_format = TextureFormat(self._read_u16(f))
        cells_per_row = self._read_u16(f)
        cells_per_column = self._read_u16(f)
        sheet_width = self._read_u16(f)
        sheet_height = self._read_u16(f)
        sheet_data_offset = self._read_u32(f)
        
        # Read texture sheet data
        # sheet_data_offset is an absolute file position
        sheet_data = []
        if sheet_data_offset != 0:
            f.seek(sheet_data_offset)
            
            # Check if this is a Switch BNTX texture (single container for all sheets)
            first_bytes = f.read(4)
            f.seek(sheet_data_offset)  # Reset position
            
            if first_bytes == b'BNTX':
                # For Switch BNTX: read the entire BNTX block as a single chunk
                # The BNTX size is stored at offset 0x18 from BNTX start
                f.seek(sheet_data_offset + 0x18)
                bntx_total_size = struct.unpack('<I', f.read(4))[0]
                f.seek(sheet_data_offset)
                
                # Read entire BNTX as single chunk
                sheet_data.append(f.read(bntx_total_size))
            else:
                # Legacy format: read each sheet separately
                for _ in range(sheet_count):
                    sheet_data.append(f.read(sheet_size))
        
        return TGLP(
            section_size=section_size,
            cell_width=cell_width,
            cell_height=cell_height,
            sheet_count=sheet_count,
            max_char_width=max_char_width,
            sheet_size=sheet_size,
            baseline=baseline,
            texture_format=texture_format,
            cells_per_row=cells_per_row,
            cells_per_column=cells_per_column,
            sheet_width=sheet_width,
            sheet_height=sheet_height,
            sheet_data_offset=sheet_data_offset,
            sheet_data=sheet_data
        )
    
    def _parse_cwdh_chain(self, f: BinaryIO, cwdh_list: List[CWDH]) -> None:
        """Parse chain of CWDH sections."""
        magic = self._read_magic(f)
        if magic != 'CWDH':
            raise ValueError(f"Expected CWDH section, got {magic}")
        
        section_size = self._read_u32(f)
        first_index = self._read_u16(f)
        last_index = self._read_u16(f)
        next_offset = self._read_u32(f)
        
        # Read width entries
        entries = []
        for _ in range(last_index - first_index + 1):
            left = self._read_u8(f)
            glyph_width = self._read_u8(f)
            char_width = self._read_u8(f)
            entries.append(CharWidthEntry(left, glyph_width, char_width))
        
        cwdh = CWDH(
            section_size=section_size,
            first_index=first_index,
            last_index=last_index,
            next_offset=next_offset,
            entries=entries
        )
        cwdh_list.append(cwdh)
        
        # Follow linked list
        if next_offset != 0:
            f.seek(next_offset - 8)
            self._parse_cwdh_chain(f, cwdh_list)
    
    def _parse_cmap_chain(self, f: BinaryIO, cmap_list: List[CMAP], 
                          char_map: Dict[int, int], platform: PlatformType) -> None:
        """Parse chain of CMAP sections."""
        magic = self._read_magic(f)
        if magic != 'CMAP':
            raise ValueError(f"Expected CMAP section, got {magic}")
        
        section_size = self._read_u32(f)
        
        # NX uses 32-bit character codes, others use 16-bit
        if platform == PlatformType.NX:
            code_begin = self._read_u32(f)
            code_end = self._read_u32(f)
        else:
            code_begin = self._read_u16(f)
            code_end = self._read_u16(f)
        
        mapping_type = CMAPType(self._read_u16(f))
        _ = self._read_u16(f)  # padding
        next_offset = self._read_u32(f)
        
        mapping_data = None
        
        if mapping_type == CMAPType.DIRECT:
            offset = self._read_u16(f)
            mapping_data = CMAPDirect(offset=offset)
            # Fill char_map - but don't overwrite existing (more specific) mappings
            for code in range(code_begin, code_end + 1):
                idx = code - code_begin + offset
                if idx < 0xFFFF and code not in char_map:
                    char_map[code] = idx
        
        elif mapping_type == CMAPType.TABLE:
            table = []
            for code in range(code_begin, code_end + 1):
                idx = self._read_s16(f)
                table.append(idx)
                if idx != -1:
                    char_map[code] = idx
            mapping_data = CMAPTable(table=table)
        
        elif mapping_type == CMAPType.SCAN:
            entry_count = self._read_u16(f)
            if platform == PlatformType.NX:
                _ = self._read_u16(f)  # padding
            
            entries = []
            for _ in range(entry_count):
                if platform == PlatformType.NX:
                    char_code = self._read_u32(f)
                    glyph_index = self._read_s16(f)
                    _ = self._read_u16(f)  # padding
                else:
                    char_code = self._read_u16(f)
                    glyph_index = self._read_s16(f)
                
                entries.append((char_code, glyph_index))
                if glyph_index != -1:
                    char_map[char_code] = glyph_index
            
            mapping_data = CMAPScan(entries=entries)
        
        cmap = CMAP(
            section_size=section_size,
            code_begin=code_begin,
            code_end=code_end,
            mapping_type=mapping_type,
            next_offset=next_offset,
            mapping_data=mapping_data
        )
        cmap_list.append(cmap)
        
        # Follow linked list
        if next_offset != 0:
            f.seek(next_offset - 8)
            self._parse_cmap_chain(f, cmap_list, char_map, platform)
    
    def _parse_krng_if_present(self, f: BinaryIO, header: FFNTHeader) -> Optional[KRNG]:
        """
        Parse KRNG section if present in the file.
        Scans from current position to end of file looking for KRNG magic.
        """
        # Save current position
        current_pos = f.tell()
        
        # Scan for KRNG section from current position to file size
        try:
            while f.tell() < header.file_size:
                pos = f.tell()
                magic_bytes = f.read(4)
                if len(magic_bytes) < 4:
                    break
                
                if magic_bytes == b'KRNG':
                    # Found KRNG section
                    section_size = self._read_u32(f)
                    # Read the raw kerning data (section_size includes magic and size field)
                    data_size = section_size - 8
                    data = f.read(data_size)
                    return KRNG(section_size=section_size, data=data)
                else:
                    # Not KRNG, continue searching
                    pass
        except Exception:
            pass
        
        # KRNG not found
        f.seek(current_pos)
        return None


def parse_bffnt(file_path: str) -> BFFNTFile:
    """Convenience function to parse a BFFNT file."""
    parser = BFFNTParser()
    return parser.parse(file_path)
