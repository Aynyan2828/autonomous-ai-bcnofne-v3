from typing import Literal

TaskType = Literal[
    "chat",
    "summary",
    "chunk_summary",
    "final_summary",
    "classification",
    "notification",
    "code",
    "repair",
]
