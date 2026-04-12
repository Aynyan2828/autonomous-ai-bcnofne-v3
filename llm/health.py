import os
import asyncio
import httpx
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm.health")

async def check_ollama():
    load_dotenv()
    base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    mode = os.getenv("AI_PROVIDER_MODE", "local_preferred")
    
    print(f"\n--- BCNOFNe AI Health Check ---")
    print(f"Provider Mode: {mode}")
    print(f"Ollama URL:    {base_url}")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 1. 接続確認
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                print(f"[OK] Ollama is reachable.")
                tags = resp.json()
                models = [m["name"] for m in tags.get("models", [])]
                print(f"[OK] Available models: {', '.join(models)}")
                
                # 2. 設定モデルの存在確認
                required_models = [
                    os.getenv("MODEL_CHAT", "qwen2.5:7b"),
                    os.getenv("MODEL_SUMMARY", "qwen2.5:7b"),
                    os.getenv("MODEL_CODE", "qwen2.5-coder:7b")
                ]
                for m in set(required_models):
                    if m in models or any(m in tag for tag in models):
                        print(f"[OK] Required model '{m}' exists.")
                    else:
                        print(f"[WARN] Required model '{m}' NOT found in Ollama list.")
            else:
                print(f"[ERROR] Ollama returned status {resp.status_code}")
                
    except Exception as e:
        print(f"[ERROR] Could not connect to Ollama at {base_url}")
        print(f"        Detail: {e}")
        print(f"\n[TIP] Windows側のOllamaで OLLAMA_HOST=0.0.0.0 設がされているか確認してください。")
        print(f"      また、ファイアウォールで 11434 ポートが許可されているか確認してください。")

if __name__ == "__main__":
    asyncio.run(check_ollama())
