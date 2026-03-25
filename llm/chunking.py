from __future__ import annotations

from typing import List


def chunk_text(text: str, chunk_size: int = 1800, overlap: int = 200) -> List[str]:
    if not text:
        return []
        
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunks.append(text[start:end])
        if end == text_length:
            break
        start = max(0, end - overlap)
        if start >= text_length - 50: # あまりにも短い残骸は捨てるか結合するか
            break

    return chunks
