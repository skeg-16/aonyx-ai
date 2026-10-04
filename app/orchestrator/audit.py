import json
import time
from .config import AUDIT_LOG_PATH

def log_tool_execution(tool_name, validated_args, permission_result, duration, outcome):
    """
    Logs every tool call to a local file. Never log file contents or secrets directly
    if they are part of the outcome, but we do log the success/fail outcome.
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Sanitize args or outcome if necessary (keep simple for now)
    entry = {
        "timestamp": timestamp,
        "tool": tool_name,
        "args": validated_args,
        "permission": permission_result,
        "duration": round(duration, 2),
        "outcome": outcome
    }
    
    try:
        with open(AUDIT_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"Failed to write audit log: {e}")
