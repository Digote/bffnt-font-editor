"""
Internationalization (i18n) module for BFFNT Font Editor.

Easy to add new languages:
1. Add a new language code in LANGUAGES dict
2. Add translations in translations.py with the same key structure
3. That's it!

Usage:
    from .i18n import tr, set_language, get_available_languages
    
    # Get translated string
    label = tr("menu.file")  # Returns "File" or "Arquivo" based on current language
    
    # Change language
    set_language("pt_BR")
"""

from .translations import TRANSLATIONS, LANGUAGES

# Current language (default: English)
_current_language = "en"


def set_language(lang_code: str) -> bool:
    """
    Set the current language.
    
    Args:
        lang_code: Language code (e.g., "en", "pt_BR")
    
    Returns:
        True if language was set successfully, False if not available
    """
    global _current_language
    if lang_code in TRANSLATIONS:
        _current_language = lang_code
        return True
    return False


def get_language() -> str:
    """Get the current language code."""
    return _current_language


def get_available_languages() -> dict:
    """
    Get all available languages.
    
    Returns:
        Dict of {code: display_name} for each language
    """
    return LANGUAGES.copy()


def tr(key: str, **kwargs) -> str:
    """
    Get translated string for a key.
    
    Args:
        key: Translation key using dot notation (e.g., "menu.file")
        **kwargs: Format arguments for string interpolation
    
    Returns:
        Translated string, or the key itself if not found
    
    Example:
        tr("glyph.changed", index=5, value=10)
        # Returns "Glyph #5 Left changed to 10"
    """
    # Get translations for current language
    translations = TRANSLATIONS.get(_current_language, TRANSLATIONS["en"])
    
    # Navigate through nested keys
    keys = key.split(".")
    value = translations
    
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
        else:
            value = None
            break
    
    # Fallback to English if not found
    if value is None and _current_language != "en":
        value = TRANSLATIONS["en"]
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break
    
    # Return key if still not found
    if value is None:
        return key
    
    # Apply format arguments if any
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError):
            return value
    
    return value
