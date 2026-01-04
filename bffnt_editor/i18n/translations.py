"""
Translation strings for all supported languages.

To add a new language:
1. Add an entry to LANGUAGES dict with code and display name
2. Add a new dict in TRANSLATIONS with the same structure as 'en'
3. Translate all strings

Language codes follow BCP 47 standard (e.g., "en", "pt_BR", "es", "ja")
"""

# Available languages with their display names
LANGUAGES = {
    "en": "English",
    "pt_BR": "Português (Brasil)",
}

# =============================================================================
# ENGLISH (Default)
# =============================================================================
EN = {
    # Window
    "window": {
        "title": "BFFNT Font Editor v1.2",
        "title_with_file": "BFFNT Font Editor v1.2 - {filename}",
        "modified_indicator": " *",
    },
    
    # Menu
    "menu": {
        "file": "&File",
        "edit": "&Edit",
        "view": "&View",
        "help": "&Help",
        
        # File menu items
        "open": "&Open...",
        "save": "&Save",
        "save_as": "Save &As...",
        "export_current_sheet": "Export Current S&heet...",
        "export_all_sheets": "Export &All Sheets...",
        "export_with_metadata": "Export with &Metadata...",
        "import_sheets": "&Import Sheets...",
        "exit": "E&xit",
        
        # Edit menu items  
        "edit_mappings": "Edit Character &Mappings...",
        
        # View menu items
        "zoom_in": "Zoom &In",
        "zoom_out": "Zoom &Out",
        "zoom_reset": "&Reset Zoom",
    },
    
    # Toolbar
    "toolbar": {
        "open": "📂 Open",
        "open_tooltip": "Open a BFFNT font file (Ctrl+O)",
        "save": "💾 Save BFFNT",
        "save_tooltip": "Save modified BFFNT file (Ctrl+Shift+S)",
        "import": "📥 Import Sheets",
        "import_tooltip": "Import modified texture sheets",
        "export": "📤 Export Current Sheet",
        "export_tooltip": "Export current texture sheet",
        "export_all": "📦 Export All",
        "export_all_tooltip": "Export all sheets with metadata",
        "edit_mappings": "✏️ Edit Mappings",
        "edit_mappings_tooltip": "Edit character to glyph mappings",
        "language": "🌐 Language",
        "language_tooltip": "Change application language",
    },
    
    # Tabs
    "tabs": {
        "texture_sheets": "📄 Texture Sheets",
        "character_grid": "🔤 Character Grid",
        "text_preview": "📝 Text Preview",
    },
    
    # Info Panel
    "info": {
        "font_info": "Font Information",
        "texture_info": "Texture Information",
        "character_info": "Character Information",
        "selected_glyph": "Selected Glyph",
        
        # Font info fields
        "version": "Version",
        "platform": "Platform",
        "width": "Width",
        "height": "Height",
        "ascent": "Ascent",
        "line_feed": "Line Feed",
        "encoding": "Encoding",
        
        # Texture info fields
        "sheets": "Sheets",
        "sheet_size": "Sheet Size",
        "cell_size": "Cell Size",
        "cells_per_sheet": "Cells/Sheet",
        "texture_format": "Format",
        
        # Character info fields
        "total_glyphs": "Total Glyphs",
        "mapped_chars": "Mapped Chars",
    },
    
    # Glyph Panel
    "glyph": {
        "index": "Index",
        "character": "Character",
        "unmapped": "(unmapped)",
        "metrics_title": "📐 Glyph Metrics",
        "left": "Left",
        "left_tooltip": "Horizontal offset from cell border to glyph start",
        "width": "Width",
        "width_tooltip": "Actual width of the glyph in pixels",
        "advance": "Advance",
        "advance_tooltip": "Total cursor advance after drawing this glyph",
        "edit_mapping": "✏️ Edit Mapping",
    },
    
    # Sheet viewer
    "sheet": {
        "label": "Sheet:",
        "show_grid": "Show Grid",
        "zoom": "Zoom:",
    },
    
    # Text Preview
    "preview": {
        "enter_text": "Enter text to preview...",
        "scale": "Scale:",
    },
    
    # Dialogs
    "dialog": {
        "mapping_editor_title": "Character Mapping Editor",
        "mapping_editor_info": "Edit character mappings below. Double-click a cell to modify.\nChar Code column shows the Unicode code point (decimal).\nGlyph Index shows which glyph texture is displayed for that character.",
        "edit_selected_glyph": "Edit Selected Glyph Mapping",
        "add_new_mapping": "Add New Mapping",
        "char_code": "Char Code",
        "glyph_index": "Glyph Index",
        "new_char_code": "New Char Code",
        "apply_change": "Apply Change",
        "add_mapping": "Add Mapping",
        "save_changes": "Save Changes",
        "cancel": "Cancel",
        "current_mapping": "Current Mapping",
        "new_mapping": "New Mapping",
        "new_character": "New Character",
        "save": "Save",
    },
    
    # Status messages
    "status": {
        "ready": "Ready - Open a .bffnt file to begin",
        "loading": "Loading font...",
        "parsing": "Parsing BFFNT file...",
        "decoding": "Decoding texture sheets...",
        "converting": "Converting to display format...",
        "extracting": "Extracting glyphs...",
        "processing": "Processing glyph thumbnails...",
        "complete": "Complete!",
        "loaded": "✅ Loaded {filename} - {glyphs} glyphs, {mapped} mapped characters",
        "exported": "📤 Exported sheet {index} to {filename}",
        "exported_all": "📦 Exported {count} sheets to {folder}",
        "imported": "📥 Imported {count} sheets - Save BFFNT to apply changes",
        "saved": "💾 Saved to {filename}",
        "mapping_changed": "✏️ Mapping changed - Save BFFNT to apply",
        "glyph_left_changed": "✏️ Glyph #{index} Left changed to {value}",
        "glyph_width_changed": "✏️ Glyph #{index} Width changed to {value}",
        "glyph_advance_changed": "✏️ Glyph #{index} Advance changed to {value}",
        "language_changed": "🌐 Language changed to {language}",
    },
    
    # Errors and warnings
    "error": {
        "title": "Error",
        "warning_title": "Warning",
        "no_font_loaded": "No font loaded",
        "invalid_input": "Invalid Input",
        "invalid_char_code": "Please enter a valid character code (number or 'char')",
        "failed_export": "Failed to export:\n{error}",
        "failed_import": "Failed to import:\n{error}",
        "failed_save": "Failed to save:\n{error}",
        "failed_load": "Failed to load font:\n{error}",
    },
    
    # Success messages
    "success": {
        "title": "Success",
        "mapping_applied": "Mapped glyph {glyph} to character code {code} ('{char}' if printable)",
    },
}

# =============================================================================
# PORTUGUÊS (Brasil)
# =============================================================================
PT_BR = {
    # Window
    "window": {
        "title": "BFFNT Font Editor v1.2",
        "title_with_file": "BFFNT Font Editor v1.2 - {filename}",
        "modified_indicator": " *",
    },
    
    # Menu
    "menu": {
        "file": "&Arquivo",
        "edit": "&Editar",
        "view": "&Visualizar",
        "help": "&Ajuda",
        
        # File menu items
        "open": "&Abrir...",
        "save": "&Salvar",
        "save_as": "Salvar &Como...",
        "export_current_sheet": "Exportar &Página Atual...",
        "export_all_sheets": "Exportar &Todas as Páginas...",
        "export_with_metadata": "Exportar com &Metadados...",
        "import_sheets": "&Importar Páginas...",
        "exit": "Sai&r",
        
        # Edit menu items
        "edit_mappings": "Editar &Mapeamentos de Caracteres...",
        
        # View menu items
        "zoom_in": "&Aumentar Zoom",
        "zoom_out": "&Diminuir Zoom",
        "zoom_reset": "&Resetar Zoom",
    },
    
    # Toolbar
    "toolbar": {
        "open": "📂 Abrir",
        "open_tooltip": "Abrir arquivo de fonte BFFNT (Ctrl+O)",
        "save": "💾 Salvar BFFNT",
        "save_tooltip": "Salvar arquivo BFFNT modificado (Ctrl+Shift+S)",
        "import": "📥 Importar Páginas",
        "import_tooltip": "Importar páginas de textura modificadas",
        "export": "📤 Exportar Página Atual",
        "export_tooltip": "Exportar página de textura atual",
        "export_all": "📦 Exportar Tudo",
        "export_all_tooltip": "Exportar todas as páginas com metadados",
        "edit_mappings": "✏️ Editar Mapeamentos",
        "edit_mappings_tooltip": "Editar mapeamentos de caracteres para glifos",
        "language": "🌐 Idioma",
        "language_tooltip": "Alterar idioma da aplicação",
    },
    
    # Tabs
    "tabs": {
        "texture_sheets": "📄 Páginas de Textura",
        "character_grid": "🔤 Grade de Caracteres",
        "text_preview": "📝 Pré-visualização de Texto",
    },
    
    # Info Panel
    "info": {
        "font_info": "Informações da Fonte",
        "texture_info": "Informações de Textura",
        "character_info": "Informações de Caracteres",
        "selected_glyph": "Glifo Selecionado",
        
        # Font info fields
        "version": "Versão",
        "platform": "Plataforma",
        "width": "Largura",
        "height": "Altura",
        "ascent": "Ascendente",
        "line_feed": "Avanço de Linha",
        "encoding": "Codificação",
        
        # Texture info fields
        "sheets": "Páginas",
        "sheet_size": "Tamanho da Página",
        "cell_size": "Tamanho da Célula",
        "cells_per_sheet": "Células/Página",
        "texture_format": "Formato",
        
        # Character info fields
        "total_glyphs": "Total de Glifos",
        "mapped_chars": "Chars Mapeados",
    },
    
    # Glyph Panel
    "glyph": {
        "index": "Índice",
        "character": "Caractere",
        "unmapped": "(não mapeado)",
        "metrics_title": "📐 Métricas do Glifo",
        "left": "Esquerda",
        "left_tooltip": "Deslocamento horizontal da borda da célula até o início do glifo",
        "width": "Largura",
        "width_tooltip": "Largura real do glifo em pixels",
        "advance": "Avanço",
        "advance_tooltip": "Avanço total do cursor após desenhar este glifo",
        "edit_mapping": "✏️ Editar Mapeamento",
    },
    
    # Sheet viewer
    "sheet": {
        "label": "Página:",
        "show_grid": "Mostrar Grade",
        "zoom": "Zoom:",
    },
    
    # Text Preview
    "preview": {
        "enter_text": "Digite o texto para pré-visualizar...",
        "scale": "Escala:",
    },
    
    # Dialogs
    "dialog": {
        "mapping_editor_title": "Editor de Mapeamento de Caracteres",
        "mapping_editor_info": "Edite os mapeamentos abaixo. Clique duplo em uma célula para modificar.\nColuna Código do Char mostra o ponto de código Unicode (decimal).\nÍndice do Glifo mostra qual textura de glifo é exibida para esse caractere.",
        "edit_selected_glyph": "Editar Mapeamento do Glifo Selecionado",
        "add_new_mapping": "Adicionar Novo Mapeamento",
        "char_code": "Código do Char",
        "glyph_index": "Índice do Glifo",
        "new_char_code": "Novo Código do Char",
        "apply_change": "Aplicar Alteração",
        "add_mapping": "Adicionar Mapeamento",
        "save_changes": "Salvar Alterações",
        "cancel": "Cancelar",
        "current_mapping": "Mapeamento Atual",
        "new_mapping": "Novo Mapeamento",
        "new_character": "Novo Caractere",
        "save": "Salvar",
    },
    
    # Status messages
    "status": {
        "ready": "Pronto - Abra um arquivo .bffnt para começar",
        "loading": "Carregando fonte...",
        "parsing": "Analisando arquivo BFFNT...",
        "decoding": "Decodificando páginas de textura...",
        "converting": "Convertendo para formato de exibição...",
        "extracting": "Extraindo glifos...",
        "processing": "Processando miniaturas de glifos...",
        "complete": "Completo!",
        "loaded": "✅ Carregado {filename} - {glyphs} glifos, {mapped} caracteres mapeados",
        "exported": "📤 Exportada página {index} para {filename}",
        "exported_all": "📦 Exportadas {count} páginas para {folder}",
        "imported": "📥 Importadas {count} páginas - Salve o BFFNT para aplicar as alterações",
        "saved": "💾 Salvo em {filename}",
        "mapping_changed": "✏️ Mapeamento alterado - Salve o BFFNT para aplicar",
        "glyph_left_changed": "✏️ Glifo #{index} Esquerda alterada para {value}",
        "glyph_width_changed": "✏️ Glifo #{index} Largura alterada para {value}",
        "glyph_advance_changed": "✏️ Glifo #{index} Avanço alterado para {value}",
        "language_changed": "🌐 Idioma alterado para {language}",
    },
    
    # Errors and warnings
    "error": {
        "title": "Erro",
        "warning_title": "Aviso",
        "no_font_loaded": "Nenhuma fonte carregada",
        "invalid_input": "Entrada Inválida",
        "invalid_char_code": "Por favor, insira um código de caractere válido (número ou 'char')",
        "failed_export": "Falha ao exportar:\n{error}",
        "failed_import": "Falha ao importar:\n{error}",
        "failed_save": "Falha ao salvar:\n{error}",
        "failed_load": "Falha ao carregar fonte:\n{error}",
    },
    
    # Success messages
    "success": {
        "title": "Sucesso",
        "mapping_applied": "Mapeado glifo {glyph} para código de caractere {code} ('{char}' se imprimível)",
    },
}

# =============================================================================
# All translations indexed by language code
# =============================================================================
TRANSLATIONS = {
    "en": EN,
    "pt_BR": PT_BR,
}
