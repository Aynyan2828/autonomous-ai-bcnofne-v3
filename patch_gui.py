import re

with open('gui/main.py', 'r', encoding='utf-8') as f:
    text = f.read()

new_func = """@app.post("/api/proposals/{proposal_id}/reject")
async def reject_proposal_api(proposal_id: str):
    \"\"\"(Security Note: DB(memory-service)を直接更新してREJECTにする)\"\"\"
    try:
        async with httpx.AsyncClient() as client:
            u_resp = await client.patch(f"http://memory-service:8003/proposals/{proposal_id}", json={"status": "REJECTED"})
            if u_resp.status_code == 200:
                return {"status": "success", "message": f"{proposal_id} の改修案を破棄したばい。"}
            return {"status": "error", "message": "破棄データの更新に失敗したばい...。"}
    except Exception as e:
        return {"status": "error", "message": f"通信エラーが発生したばい：{e}"}"""

text = re.sub(r'@app\.post\("/api/proposals/\{proposal_id\}/reject"\).*?return \{"status": "error", "message": f"通信エラーが発生したばい：\{e\}"\}', new_func, text, flags=re.DOTALL)

with open('gui/main.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)

print("Done")
