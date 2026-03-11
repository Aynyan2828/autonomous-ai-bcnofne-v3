def format_bilingual(ja_text: str, en_text: str) -> str:
    """
    Format text in bilingual standard:
    Japanese
    English
    """
    if not isinstance(ja_text, str):
        ja_text = str(ja_text)
    if not isinstance(en_text, str):
        en_text = str(en_text)
        
    # Trim to avoid extra newlines
    ja_text = ja_text.strip()
    en_text = en_text.strip()
    
    if not ja_text and not en_text:
        return ""
    if not en_text:
        return ja_text
    if not ja_text:
        return en_text
        
    return f"{ja_text}\n{en_text}"

def format_bilingual_list(items: list[tuple[str, str]]) -> str:
    """
    Format a list of bilingual pairs into a string, separated by double newlines.
    """
    formatted_items = [format_bilingual(ja, en) for ja, en in items if ja or en]
    return "\n\n".join(formatted_items)
