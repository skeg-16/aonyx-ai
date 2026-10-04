import os
import sys

sys.path.insert(0, os.path.abspath('.'))
from app.orchestrator.config import ALLOWED_APPS

# Enable real launching only with '--run' flag
REAL_RUN = "--run" in sys.argv

print("Testing all allowed apps (dry-run unless '--run' specified)...")

failed_apps = []

for name, target in ALLOWED_APPS.items():
    try:
        if callable(target):
            # Evaluate lambda if it's a dynamic path
            target = target()
        # Some targets are shell URIs like 'ms-settings:'
        if target.endswith(':') or target.endswith('.exe'):
            if REAL_RUN:
                os.startfile(target)
                print(f"[OK] {name} -> {target}")
            else:
                print(f"[SIMULATED] {name} -> {target}")
        else:
            print(f"[SKIP] {name} (not a direct executable/URI) -> {target}")
    except Exception as e:
        print(f"[FAIL] {name} -> {target} : {e}")
        failed_apps.append((name, target, str(e)))

print("\n--- SUMMARY ---")
if not failed_apps:
    print("All apps successfully executed via os.startfile!")
else:
    print(f"{len(failed_apps)} apps failed:")
    for name, target, err in failed_apps:
        print(f" - {name}: {err}")
