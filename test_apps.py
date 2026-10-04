import os
import sys

# Add current dir to path to import app modules
sys.path.insert(0, os.path.abspath('.'))

from app.orchestrator.tools import open_app
from app.orchestrator.config import ALLOWED_APPS

def mock_startfile(filepath):
    print(f"[MOCK] os.startfile called with: {filepath}")
    # Simulate a file not found error if the path doesn't exist
    if "fxsound" in filepath.lower() or "agy" in filepath.lower() or "acrobat" in filepath.lower():
        # Let's pretend some paths aren't found in system for testing error handling
        if not filepath.endswith(".exe"):
            pass 
    if "fake" in filepath.lower():
        raise FileNotFoundError(f"[WinError 2] The system cannot find the file specified: '{filepath}'")

# Replace os.startfile with our mock
os.startfile = mock_startfile

print("=== ALLOWED APPS TEST ===")
success_count = 0
for app_name in ALLOWED_APPS.keys():
    print(f"Testing allowed app: '{app_name}'")
    result = open_app(app_name)
    print(f"  Result: {result}")
    if result["status"] == "ok":
        success_count += 1
    print("-" * 30)

print("=== DISALLOWED APPS TEST ===")
disallowed_apps = ["malware", "powershell", "fake_app"]
blocked_count = 0
for app_name in disallowed_apps:
    print(f"Testing disallowed app: '{app_name}'")
    result = open_app(app_name)
    print(f"  Result: {result}")
    if result["status"] == "error" and "not in allowlist" in result["data"]:
        blocked_count += 1
    print("-" * 30)

print("=== SUMMARY ===")
print(f"Allowed apps successfully routed: {success_count} / {len(ALLOWED_APPS)}")
print(f"Disallowed apps correctly blocked: {blocked_count} / {len(disallowed_apps)}")
