import subprocess
import logging
import os
from typing import List, Tuple

logger = logging.getLogger("dev-agent.safety")

# 実行禁止コマンドリスト
DANGEROUS_COMMANDS = [
    "rm -rf /",
    "mkfs",
    "dd if=/dev/zero",
    "shutdown",
    "reboot",
    "format",
    ":(){ :|:& };:", # Fork bomb
]

class SafetyGuard:
    @staticmethod
    def check_git_status() -> Tuple[bool, str]:
        """Git の状態を確認し、未コミットの変更がないかチェックする"""
        try:
            res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
            if res.stdout.strip():
                return False, "Uncommitted changes detected. Please commit or stash before proceeding."
            return True, "Git status clean."
        except Exception as e:
            return False, f"Git status check failed: {e}"

    @staticmethod
    def is_command_safe(command: str) -> Tuple[bool, str]:
        """コマンドが危険でないかチェックする"""
        cmd_lower = command.lower()
        for dangerous in DANGEROUS_COMMANDS:
            if dangerous in cmd_lower:
                return False, f"Dangerous command blocked: {dangerous}"
        
        # 特定のファイルの削除を制限 (例: .env, データベースファイル)
        if "rm " in cmd_lower and (".env" in cmd_lower or ".db" in cmd_lower):
            return False, "Deletion of sensitive files (.env, .db) is blocked."
            
        return True, "Command appears safe."

    @staticmethod
    def validate_modification(file_path: str, new_content: str) -> Tuple[bool, str]:
        """ファイルの変更内容が妥当かチェックする (簡易バリデーション)"""
        if not new_content.strip():
            return False, "Empty content is not allowed."
        
        # 構文チェック (Pythonの場合)
        if file_path.endswith(".py"):
            try:
                compile(new_content, file_path, 'exec')
            except SyntaxError as e:
                return False, f"Syntax error in new content: {e}"
        
        return True, "Modality appears valid."
