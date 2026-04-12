import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("--- Diary Service Import Check ---")
try:
    print("Importing llm...")
    from llm import get_llm_executor
    print("[OK] llm imported.")
    
    print("Importing shared...")
    from shared import init_db
    print("[OK] shared imported.")
    
    print("Importing schemas...")
    from llm.schemas import FinalSummaryResult
    print("[OK] schemas imported.")
    
    print("Test importing TaskType from llm...")
    from llm import TaskType
    print(f"[OK] TaskType imported: {TaskType}")
    
except Exception as e:
    print(f"[ERROR] Import failed: {e}")
    import traceback
    traceback.print_exc()
