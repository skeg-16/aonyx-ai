import os, subprocess
from app.orchestrator.config import ALLOWED_APPS

def close_all_allowed_apps():
    """Force‑close every executable defined in ALLOWED_APPS.
    Uses `taskkill /F /IM <exe>` on Windows.
    """
    for name, target in ALLOWED_APPS.items():
        # Resolve callables (e.g., Discord lambda) to a path string
        if callable(target):
            try:
                target = target()
            except Exception:
                continue
        exe = os.path.basename(str(target))
        if not exe:
            continue
        # taskkill requires only the executable name
        try:
            subprocess.run(["taskkill", "/F", "/IM", exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    print("All allowed applications terminated.")

if __name__ == "__main__":
    close_all_allowed_apps()
