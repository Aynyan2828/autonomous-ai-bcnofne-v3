import re
import json
from typing import List, Any, Dict

def clean_json_string(text: str) -> str:
    """
    LLM (特に7Bクラス) が出力しがちな JSON 以外のノイズを削ぎ落とす。
    Markdown のコードブロックや、JSON前後の解説テキストを除去する。
    """
    text = text.strip()
    
    # Markdown コードブロックの除去
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if json_match:
        text = json_match.group(1)
    
    # 最初と最後の { } を探す (JSON Object 用)
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    if first_brace != -1 and last_brace != -1:
        text = text[first_brace:last_brace+1]
        
    return text

def repair_json(text: str) -> Dict[str, Any]:
    """
    不完全な JSON (末尾のカンマ忘れ、クォートミス等) を簡易的に修復してパースを試みる。
    """
    cleaned = clean_json_string(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # 簡易修復: 末尾のカンマ + 閉じの中かっこ不足などの対応
        # 7Bはよく ] } を忘れる
        temp = cleaned
        if not temp.endswith('}'):
            temp += '}'
        try:
            return json.loads(temp)
        except:
            # これでもダメなら、さらにアグレッシブな置換（実務では慎重に）
            # ここでは最小限に留める
            raise

def chunk_text(text: str, max_chars: int = 4000) -> List[str]:
    """
    長文を一定の文字数（簡易的なトークン代わり）で分割する。
    改行で区切るように努める。
    """
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    current_pos = 0
    while current_pos < len(text):
        end_pos = current_pos + max_chars
        if end_pos >= len(text):
            chunks.append(text[current_pos:])
            break
            
        # なるべく改行で区切る
        last_newline = text.rfind('\n', current_pos, end_pos)
        if last_newline != -1 and last_newline > current_pos + (max_chars // 2):
            end_pos = last_newline
            
        chunks.append(text[current_pos:end_pos].strip())
        current_pos = end_pos
        
    return chunks
